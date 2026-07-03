"""seed_sample_operations.py — sample data for routing/costing/lot/approval.

Covers four feature areas added by the "Phase 3-6 core modules" work that
previously had zero sample data:

  routing_core           workcenters, product routings, WO operations
                          (some started/completed to show shop-floor progress)
  lot_core                raw-material and finished-good lots + serial
                          numbers across every status
  costing_core            GL account map, standard cost rolls (via the real
                          BOM-exploding roll_standard_cost()), and one WO
                          actual-cost/variance record
  approval_workflow_core  approval rules for PO/requisition/GL-journal, plus
                          real approval_step instances against the sample
                          purchase requisitions (pending/approved/rejected/
                          escalated)

Depends on sample products + BOMs (``seed_sample_products``) and sample work
orders (``seed_sample_wos``) for product/WO ids to hang routings and
operations off of. If ``seed_sample_purchasing`` has also been run, its
SMPL-REQ- requisitions get real approval_step workflows; otherwise only the
approval rule configuration is seeded.

Workcenters/routings are tagged via a ``created_by`` column added here (the
core tables don't define one). Lots, serial numbers, cost rolls and WO
actual-cost rows use their native ``created_by`` column. Approval rules are
tagged via their ``notes`` column. WO operations and approval steps aren't
tagged directly — they're identified by the SMPL-WO- / SMPL-REQ- rows they
hang off of, which are themselves sample data.

Usage::

    python -m manufacturing.seeds.seed_sample_operations            # add (idempotent)
    python -m manufacturing.seeds.seed_sample_operations --reset     # remove + re-add
    python -m manufacturing.seeds.seed_sample_operations --remove    # remove only
"""

import argparse
import sys
from datetime import date, timedelta

from ..db_pg import get_db_connection
from ..lot_core import ensure_lot_tables, create_lot, update_lot_status, \
    consume_lot_qty, create_serial, update_serial_status, get_lot_by_number
from ..routing_core import ensure_routing_tables, create_workcenter, \
    create_routing_step, populate_wo_operations, get_wo_operations, \
    start_wo_operation, complete_wo_operation
from ..costing_core import ensure_costing_tables, set_gl_account_map, \
    get_gl_account_map, roll_standard_cost, save_wo_actual_cost
from ..approval_workflow_core import ensure_approval_tables, \
    create_approval_rule, submit_for_approval, decide_step, \
    check_escalations

TAG = "SMPL-OPS-"
TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


# ---------------------------------------------------------------------------
# Table setup
# ---------------------------------------------------------------------------

def _ensure_tables(conn):
    # routing_core / lot_core backfill FK columns onto these; they only exist
    # today via the Qt inventory/work-order screens, so create them here too
    # so this seed works standalone (mirrors production/inventory.py DDL).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory_transaction (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES product(id),
            trans_date TEXT,
            trans_type TEXT,
            quantity REAL DEFAULT 0,
            reference TEXT,
            notes TEXT
        )
    """)
    ensure_routing_tables(conn)
    ensure_lot_tables(conn)
    ensure_costing_tables(conn)
    ensure_approval_tables(conn)
    conn.execute("ALTER TABLE workcenter ADD COLUMN IF NOT EXISTS created_by TEXT")
    conn.execute("ALTER TABLE routing ADD COLUMN IF NOT EXISTS created_by TEXT")
    conn.commit()


def _sample_product_ids(conn):
    rows = conn.execute(
        "SELECT id, name FROM product WHERE bin = 'SAMPLE'").fetchall()
    return {r["name"]: r["id"] for r in rows}


def _sample_wo_ids(conn):
    rows = conn.execute(
        "SELECT id, wo_number, product_id, quantity FROM work_order "
        "WHERE wo_number LIKE 'SMPL-WO-%'").fetchall()
    return {r["wo_number"]: dict(r) for r in rows}


# ---------------------------------------------------------------------------
# Workcenters + routings + WO operations
# ---------------------------------------------------------------------------

# name, dept, capacity_hours_per_day, labor_rate, overhead_rate
WORKCENTERS = [
    ("Cutting Station",     "Production", 8.0, 22.50, 8.00),
    ("Paint Booth",         "Production", 6.0, 19.00, 12.00),
    ("Wheel Building",      "Production", 8.0, 24.00, 6.00),
    ("Final Assembly",      "Production", 8.0, 21.00, 9.00),
    ("Quality Inspection",  "Quality",    8.0, 26.00, 5.00),
]

# product_name -> [(seq, operation_name, workcenter_name, std_hours)]
ROUTINGS = {
    "Bike Frame": [
        (10, "Cut Tube",    "Cutting Station", 0.5),
        (20, "Weld Frame",  "Cutting Station", 1.0),
        (30, "Paint Frame", "Paint Booth",     0.75),
    ],
    "Wheel Assembly": [
        (10, "Build Wheel",     "Wheel Building",     0.4),
        (20, "True & Inspect",  "Quality Inspection", 0.2),
    ],
    "Mountain Bike": [
        (10, "Final Assembly", "Final Assembly",     1.5),
        (20, "QA Inspection",  "Quality Inspection", 0.3),
    ],
    "Road Bike": [
        (10, "Final Assembly", "Final Assembly",     1.4),
        (20, "QA Inspection",  "Quality Inspection", 0.3),
    ],
}


def _workcenters_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM workcenter WHERE created_by=%s", (TAG,)
    ).fetchone()[0] > 0


def _seed_workcenters(conn):
    ids = {}
    n = 0
    for name, dept, cap, rate, oh in WORKCENTERS:
        row = conn.execute(
            "SELECT id FROM workcenter WHERE name=%s", (name,)).fetchone()
        if row:
            ids[name] = row["id"]
            continue
        wc_id = create_workcenter(conn, name, dept=dept,
                                   capacity_hours_per_day=cap, labor_rate=rate)
        conn.execute(
            "UPDATE workcenter SET created_by=%s, overhead_rate=%s WHERE id=%s",
            (TAG, oh, wc_id))
        ids[name] = wc_id
        n += 1
    return ids, n


def _seed_routings(conn, wc_ids, product_ids):
    n = 0
    for product_name, steps in ROUTINGS.items():
        product_id = product_ids.get(product_name)
        if product_id is None:
            print(f"  skip routing (missing product): {product_name!r}",
                  file=sys.stderr)
            continue
        for seq, op_name, wc_name, std_hours in steps:
            exists = conn.execute(
                "SELECT 1 FROM routing WHERE product_id=%s AND operation_seq=%s",
                (product_id, seq)).fetchone()
            if exists:
                continue
            rid = create_routing_step(
                conn, product_id, seq, op_name,
                workcenter_id=wc_ids.get(wc_name), std_hours=std_hours)
            conn.execute(
                "UPDATE routing SET created_by=%s WHERE id=%s", (TAG, rid))
            n += 1
    return n


# WO suffix -> operations to advance: [(operation_seq, action, actual_hours)]
# action: 'start' or 'complete'
WO_PROGRESS = {
    "3": [(10, "complete", 0.6), (20, "start", None)],
    "4": [(10, "complete", 4.0), (20, "complete", 2.0)],
}


def _seed_wo_operations(conn, product_ids, wo_ids):
    op_n = 0
    for wo_number, wo in wo_ids.items():
        if wo_number.endswith("-5"):
            continue  # cancelled WO — never entered production
        if wo["product_id"] is None:
            continue
        op_n += populate_wo_operations(conn, wo["id"], wo["product_id"])

    for suffix, actions in WO_PROGRESS.items():
        wo = wo_ids.get(f"SMPL-WO-{suffix}")
        if not wo:
            continue
        ops = {op["operation_seq"]: op for op in get_wo_operations(conn, wo["id"])}
        for seq, action, actual_hours in actions:
            op = ops.get(seq)
            if not op:
                continue
            if action == "start" and op["status"] == "pending":
                start_wo_operation(conn, op["id"])
            elif action == "complete" and op["status"] in ("pending", "in_progress"):
                complete_wo_operation(conn, op["id"], actual_hours,
                                      completed_by="Sample Seed")
    return op_n


def _remove_workcenters_routings(conn, wo_ids):
    op_n = 0
    wo_id_list = [wo["id"] for wo in wo_ids.values()]
    if wo_id_list:
        op_n = conn.execute(
            "DELETE FROM wo_operation WHERE wo_id = ANY(%s)", (wo_id_list,)
        ).rowcount
    rt_n = conn.execute(
        "DELETE FROM routing WHERE created_by=%s", (TAG,)).rowcount
    wc_n = conn.execute(
        "DELETE FROM workcenter WHERE created_by=%s", (TAG,)).rowcount
    return wc_n, rt_n, op_n


# ---------------------------------------------------------------------------
# Lots + serial numbers
# ---------------------------------------------------------------------------

# lot_number_suffix, product_name, qty, status, received_offset_days,
# expiry_offset_days (None = no expiry), notes
LOTS = [
    ("STEEL-01", "Steel Tube",     400, "available", -30, None,
     "Incoming coil stock"),
    ("RIM-01",   "Rim",             30, "quarantine",  -5, None,
     "Awaiting incoming inspection"),
    ("PAINT-01", "Paint Can",       15, "hold",       -10, None,
     "Batch recalled by supplier pending QA review"),
    ("TUBE-01",  "Inner Tube",      25, "available", -100,  25,
     "Rubber compound approaching shelf-life limit"),
    ("HBAR-01",  "Handlebar",        5, "rejected",  -15, None,
     "Failed dimensional check, returned to supplier"),
    ("TIRE-01",  "Tire",            20, "consumed",  -60, None,
     "Fully consumed in production"),
    ("WHEEL-01", "Wheel Assembly",   8, "available",  -3, None,
     "Produced on SMPL-WO-4"),
]

# serial suffix range, product_name, lot_suffix (or None), qty, issued_count
SERIALS = [
    ("WA", "Wheel Assembly", "WHEEL-01", 8, 2),
]


def _lots_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM lot WHERE created_by=%s", (TAG,)
    ).fetchone()[0] > 0


def _seed_lots(conn, product_ids):
    lot_ids = {}
    n = 0
    for suffix, product_name, qty, status, recv_off, exp_off, notes in LOTS:
        product_id = product_ids.get(product_name)
        if product_id is None:
            print(f"  skip lot (missing product): {product_name!r}",
                  file=sys.stderr)
            continue
        lot_number = TAG + suffix
        existing = get_lot_by_number(conn, lot_number)
        if existing:
            lot_ids[suffix] = existing["id"]
            continue
        expiry = _d(exp_off) if exp_off is not None else None
        lot_id = create_lot(
            conn, product_id, qty, received_date=_d(recv_off),
            expiry_date=expiry, lot_number=lot_number, notes=notes,
            created_by=TAG)
        if status == "consumed":
            consume_lot_qty(conn, lot_id, qty)
        elif status != "available":
            update_lot_status(conn, lot_id, status, notes=notes)
        lot_ids[suffix] = lot_id
        n += 1
    return lot_ids, n


def _seed_serials(conn, lot_ids, product_ids):
    n = 0
    for prefix, product_name, lot_suffix, qty, issued_n in SERIALS:
        product_id = product_ids.get(product_name)
        if product_id is None:
            continue
        lot_id = lot_ids.get(lot_suffix) if lot_suffix else None
        for i in range(1, qty + 1):
            serial_number = f"{TAG}SN-{prefix}-{i:04d}"
            if conn.execute(
                    "SELECT 1 FROM serial_number WHERE serial_number=%s",
                    (serial_number,)).fetchone():
                continue
            sn_id = create_serial(conn, serial_number, product_id,
                                   lot_id=lot_id, created_by=TAG)
            if i <= issued_n:
                update_serial_status(conn, sn_id, "issued")
            n += 1
    return n


def _remove_lots_serials(conn):
    sn_n = conn.execute(
        "DELETE FROM serial_number WHERE created_by=%s", (TAG,)).rowcount
    lot_n = conn.execute(
        "DELETE FROM lot WHERE created_by=%s", (TAG,)).rowcount
    return lot_n, sn_n


# ---------------------------------------------------------------------------
# Costing: GL account map + standard cost rolls + one WO actual-cost record
# ---------------------------------------------------------------------------

# category -> (account_number, description). Numbers match the chart of
# accounts in seed_sample_accounting.py (no FK enforced, so this works even
# if that seed hasn't been run — the numbers just won't resolve to a real
# gl_account row until it has).
GL_MAP = {
    "raw_material":      ("1200", "Inventory — raw material"),
    "wip":               ("1200", "Inventory — work in process"),
    "finished_goods":    ("1200", "Inventory — finished goods"),
    "cogs":              ("5000", "Direct Materials (COGS)"),
    "material_variance": ("5000", "Material variance posts to Direct Materials"),
    "labor_variance":    ("5100", "Labor variance posts to Direct Labor"),
    "ap_payable":        ("2000", "Accounts Payable"),
}


def _costing_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM cost_roll WHERE created_by=%s", (TAG,)
    ).fetchone()[0] > 0


def _seed_gl_map(conn):
    current = get_gl_account_map(conn)
    n = 0
    for category, (acct, desc) in GL_MAP.items():
        if category in current:
            continue
        set_gl_account_map(conn, category, acct, description=desc)
        n += 1
    return n


def _seed_cost_rolls(conn, product_ids):
    n = 0
    for top_level in ("Mountain Bike", "Road Bike"):
        product_id = product_ids.get(top_level)
        if product_id is None:
            continue
        roll_standard_cost(conn, product_id, created_by=TAG)
        n += 1
    return n


def _seed_wo_cost_actual(conn, wo_ids):
    wo = wo_ids.get("SMPL-WO-4")
    if not wo:
        return None
    return save_wo_actual_cost(conn, wo["id"], created_by=TAG)


def _remove_costing(conn, wo_ids):
    cr_n = conn.execute(
        "DELETE FROM cost_roll WHERE created_by=%s", (TAG,)).rowcount
    wc_n = conn.execute(
        "DELETE FROM wo_cost_actual WHERE created_by=%s", (TAG,)).rowcount
    gl_n = conn.execute(
        "DELETE FROM gl_account_map WHERE category = ANY(%s)",
        (list(GL_MAP.keys()),)).rowcount
    return cr_n, wc_n, gl_n


# ---------------------------------------------------------------------------
# Approval workflow
# ---------------------------------------------------------------------------

# entity_type, approver_role, seq, threshold_amount, escalate_after_hours
APPROVAL_RULES = [
    ("purchase_requisition", "Department Manager", 10,    100.0, 24.0),
    ("purchase_requisition", "Purchasing Manager",  20,  1000.0, 48.0),
    ("purchase_order",       "Purchasing Manager",  10,  1000.0, 24.0),
    ("purchase_order",       "Vice President",      20, 10000.0, 48.0),
    ("gl_journal",           "Controller",           10, 10000.0, 24.0),
]

# SMPL-REQ- suffix -> steps to decide (seq -> decision), plus whether to
# force-escalate the lowest-seq step instead of deciding it.
REQ_OUTCOMES = {
    "002": {"escalate": True},
    "003": {10: "approved"},
    "004": {10: "rejected"},
    "005": {10: "approved", 20: "approved"},
    "006": {10: "rejected"},
}


def _approval_rules_present(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM approval_rule WHERE notes=%s", (TAG,)
    ).fetchone()[0] > 0


def _seed_approval_rules(conn):
    n = 0
    for entity_type, role, seq, threshold, escalate_hrs in APPROVAL_RULES:
        exists = conn.execute(
            "SELECT 1 FROM approval_rule WHERE entity_type=%s AND seq=%s "
            "AND approver_role=%s", (entity_type, seq, role)).fetchone()
        if exists:
            continue
        create_approval_rule(
            conn, entity_type, role, seq=seq, threshold_amount=threshold,
            escalate_after_hours=escalate_hrs, notes=TAG)
        n += 1
    return n


def _requisition_amount(conn, req_id):
    row = conn.execute(
        "SELECT COALESCE(SUM(qty * est_unit_price), 0) AS amt "
        "FROM requisition_item WHERE req_id=%s", (req_id,)).fetchone()
    return float(row["amt"]) if row else 0.0


def _seed_approval_steps(conn):
    reqs = conn.execute(
        "SELECT id, req_number FROM purchase_requisition "
        "WHERE req_number LIKE 'SMPL-REQ-%'").fetchall()
    if not reqs:
        print("  no SMPL-REQ- requisitions found; run seed_sample_purchasing "
              "first for approval_step demo data (rules seeded regardless)")
        return 0

    step_n = 0
    for req in reqs:
        suffix = req["req_number"].replace("SMPL-REQ-", "")
        outcome = REQ_OUTCOMES.get(suffix)
        if not outcome:
            continue  # draft / cancelled reqs never entered the workflow
        amount = _requisition_amount(conn, req["id"])
        step_ids = submit_for_approval(
            conn, "purchase_requisition", req["id"], amount,
            requested_by=TAG)
        step_n += len(step_ids)
        if not step_ids:
            continue

        status = conn.execute(
            "SELECT s.id, s.seq, s.status FROM approval_step s "
            "WHERE s.entity_type='purchase_requisition' AND s.entity_id=%s "
            "ORDER BY s.seq", (req["id"],)).fetchall()
        by_seq = {r["seq"]: r for r in status}

        if outcome.get("escalate"):
            lowest = min(by_seq.values(), key=lambda r: r["seq"])
            if lowest["status"] == "pending":
                conn.execute(
                    "UPDATE approval_step SET created_at = NOW() - "
                    "(r.escalate_after_hours + 6) * INTERVAL '1 hour' "
                    "FROM approval_rule r WHERE approval_step.rule_id = r.id "
                    "AND approval_step.id = %s", (lowest["id"],))
                check_escalations(conn)
            continue

        for seq, decision in outcome.items():
            step = by_seq.get(seq)
            if not step or step["status"] != "pending":
                continue
            try:
                decide_step(conn, step["id"], decision, decided_by=TAG)
            except ValueError:
                pass
    return step_n


def _remove_approval(conn):
    rule_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM approval_rule WHERE notes=%s", (TAG,)).fetchall()]
    step_n = 0
    if rule_ids:
        step_n = conn.execute(
            "DELETE FROM approval_step WHERE rule_id = ANY(%s)",
            (rule_ids,)).rowcount
    # Steps created against requisitions reference our tagged rules via
    # rule_id, so the delete above covers them too.
    rule_n = conn.execute(
        "DELETE FROM approval_rule WHERE notes=%s", (TAG,)).rowcount
    return rule_n, step_n


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Seed sample routing/lot/costing/approval-workflow data.")
    parser.add_argument("--reset", action="store_true",
                        help="remove existing sample data, then re-seed")
    parser.add_argument("--remove", action="store_true",
                        help="remove sample data only (no seeding)")
    args = parser.parse_args(argv)

    conn = get_db_connection()
    try:
        _ensure_tables(conn)
        wo_ids = _sample_wo_ids(conn)

        if args.remove or args.reset:
            wc_n, rt_n, op_n = _remove_workcenters_routings(conn, wo_ids)
            lot_n, sn_n = _remove_lots_serials(conn)
            cr_n, wca_n, gl_n = _remove_costing(conn, wo_ids)
            rule_n, step_n = _remove_approval(conn)
            conn.commit()
            print(f"removed {wc_n} workcenters, {rt_n} routing steps, "
                  f"{op_n} WO operations, {lot_n} lots, {sn_n} serials, "
                  f"{cr_n} cost rolls, {wca_n} WO cost records, "
                  f"{gl_n} GL map entries, {rule_n} approval rules "
                  f"({step_n} steps)")
            if args.remove:
                return

        product_ids = _sample_product_ids(conn)

        if _workcenters_present(conn):
            print("Workcenters/routings already present; use --reset to recreate.")
        else:
            wc_ids, wc_n = _seed_workcenters(conn)
            rt_n = _seed_routings(conn, wc_ids, product_ids)
            op_n = _seed_wo_operations(conn, product_ids, wo_ids)
            conn.commit()
            print(f"inserted {wc_n} workcenters, {rt_n} routing steps, "
                  f"{op_n} WO operation sets")

        if _lots_present(conn):
            print("Lots/serials already present; use --reset to recreate.")
        else:
            lot_ids, lot_n = _seed_lots(conn, product_ids)
            sn_n = _seed_serials(conn, lot_ids, product_ids)
            conn.commit()
            print(f"inserted {lot_n} lots, {sn_n} serial numbers")

        if _costing_present(conn):
            print("Cost rolls already present; use --reset to recreate.")
        else:
            gl_n = _seed_gl_map(conn)
            cr_n = _seed_cost_rolls(conn, product_ids)
            wca = _seed_wo_cost_actual(conn, wo_ids)
            conn.commit()
            wca_msg = "1 WO cost record" if wca else "0 WO cost records"
            print(f"inserted {gl_n} GL map entries, {cr_n} cost rolls, "
                  f"{wca_msg}")

        if _approval_rules_present(conn):
            print("Approval rules already present; use --reset to recreate.")
        else:
            rule_n = _seed_approval_rules(conn)
            conn.commit()
            print(f"inserted {rule_n} approval rules")
        step_n = _seed_approval_steps(conn)
        conn.commit()
        if step_n:
            print(f"inserted/updated {step_n} approval steps")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
