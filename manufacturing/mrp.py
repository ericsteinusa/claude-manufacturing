"""mrp.py — Material Requirements Planning engine (read-only suggestions).

PR 3 of the BOM/MRP track. Given demand, on-hand and in-flight supply, this
nets requirements and explodes BOMs level by level to suggest **planned
orders** — purchase suggestions for bought items, work-order suggestions for
made items. This PR only *computes and displays* them; releasing a planned
order into a requisition / work order is PR 4.

Design notes / v1 scope (deliberate, documented boundaries):

* **Quantity planning, not time-phased buckets.** Requirements are netted on
  totals and a single ``need_date`` is recorded; weekly bucketing and
  lead-time offset scheduling are a later refinement. ``lead_time_days`` is
  carried on each planned order so PR 4 can derive a start date.
* **Demand** = firm sales orders (``sales_order.status='confirmed'``). Draft
  orders aren't firm; shipped/invoiced/cancelled are done. A forecast/MPS
  source can be added later.
* **Scheduled receipts** = open purchase orders (``status='sent'``, remaining
  ``qty_ordered - qty_received``) and open work orders (``status`` in
  planned/open/in_progress). On-hand is ``product.amount``; safety stock is
  ``product.reorder_point``.
* **Dependent demand** comes from the make orders this run plans (the BOM
  explosion). Components already committed to existing open work orders are
  assumed reflected in on-hand, not separately netted.

The planning math (:func:`compute_levels`, :func:`plan_orders`) is pure so it
can be unit tested without a database; the DB layer just gathers inputs and
persists the result.
"""

import sys
from collections import defaultdict
from datetime import date, timedelta

from PyQt6 import QtCore, QtGui, QtWidgets

from .bom import explode_quantity
from .db_pg import get_db_connection


BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; "
    "border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid "
    "rgb(85, 255, 255);}"
)
INPUT_STYLE = (
    "QLineEdit{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
)
LABEL_STYLE = "color: white; font-size: 13px;"

COLOR_MAKE = "#d4edda"  # green tint
COLOR_BUY = "#fff3cd"   # amber tint

# Status sets that count as live demand / in-flight supply.
DEMAND_SO_STATUSES = ("confirmed",)
OPEN_PO_STATUS = "sent"
OPEN_WO_STATUSES = ("planned", "open", "in_progress")


def get_db():
    return get_db_connection()


# ── Pure planning core ──────────────────────────────────────────────────

def compute_levels(product_ids, edges):
    """Low-level codes for the BOM graph.

    ``edges`` is an iterable of ``(parent, component)`` pairs. Returns
    ``{product_id: level}`` where a top-level item (never a component) is 0 and
    each component sits at least one level below every parent that uses it.
    Processing items in ascending level guarantees a parent's dependent demand
    is known before the component is planned. The cycle guard in
    :mod:`bom` keeps this graph acyclic, so the relaxation terminates.
    """
    level = {pid: 0 for pid in product_ids}
    for p, c in edges:
        level.setdefault(p, 0)
        level.setdefault(c, 0)
    changed = True
    while changed:
        changed = False
        for p, c in edges:
            if level[c] < level[p] + 1:
                level[c] = level[p] + 1
                changed = True
    return level


def plan_orders(products, bom_lines, demand, on_hand,
                scheduled_receipts, safety):
    """Net requirements and explode BOMs level by level (pure).

    Parameters
    ----------
    products : dict
        ``{pid: {'item_type': str, 'lead_time_days': int}}``.
    bom_lines : dict
        ``{parent_pid: [(component_pid, qty_per, scrap_pct), ...]}``.
    demand, on_hand, scheduled_receipts, safety : dict
        ``{pid: number}`` lookups (missing keys treated as 0).

    Returns
    -------
    list of dict
        ``{'product_id', 'order_type', 'qty', 'lead_time_days'}``, ordered
        parents-first. ``order_type`` is 'make' when the item has a BOM (or is
        flagged make) else 'buy'. Lot-for-lot: the planned quantity is exactly
        the net requirement.
    """
    edges = [(p, c) for p, lines in bom_lines.items()
             for (c, _qty, _scrap) in lines]
    all_ids = set(products) | set(demand) | set(on_hand) \
        | set(scheduled_receipts) | set(safety)
    for p, c in edges:
        all_ids.add(p)
        all_ids.add(c)

    level = compute_levels(all_ids, edges)
    gross = defaultdict(float)
    for pid, qty in demand.items():
        gross[pid] += qty

    planned = []
    eps = 1e-9
    for pid in sorted(all_ids, key=lambda x: (level.get(x, 0), x)):
        required = gross.get(pid, 0.0) + safety.get(pid, 0.0)
        available = on_hand.get(pid, 0.0) + scheduled_receipts.get(pid, 0.0)
        net = required - available
        if net <= eps:
            continue
        has_bom = bool(bom_lines.get(pid))
        item_type = (products.get(pid, {}).get("item_type") or "buy")
        order_type = "make" if (has_bom or item_type == "make") else "buy"
        planned.append({
            "product_id": pid,
            "order_type": order_type,
            "qty": net,
            "lead_time_days":
                products.get(pid, {}).get("lead_time_days", 0) or 0,
        })
        if has_bom:
            for component, qty_per, scrap in bom_lines[pid]:
                gross[component] += explode_quantity(qty_per, net, scrap)
    return planned


# ── Schema ──────────────────────────────────────────────────────────────

def init_mrp_tables(conn):
    """Create the planned-order tables (idempotent)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mrp_run (
            id SERIAL PRIMARY KEY,
            run_date TEXT,
            horizon_days INTEGER,
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mrp_planned_order (
            id SERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES mrp_run(id),
            product_id INTEGER NOT NULL,
            order_type TEXT,
            qty REAL,
            need_date TEXT,
            lead_time_days INTEGER DEFAULT 0,
            status TEXT DEFAULT 'suggested'
        )
    """)


# ── DB input gathering ──────────────────────────────────────────────────

def _gather_inputs(conn, horizon_days=None):
    """Collect demand/supply lookups from the live tables."""
    products = {}
    for r in conn.execute(
        "SELECT id, COALESCE(item_type, 'buy') AS item_type, "
        "COALESCE(lead_time_days, 0) AS lead_time_days FROM product"
    ).fetchall():
        products[r["id"]] = {
            "item_type": r["item_type"],
            "lead_time_days": r["lead_time_days"],
        }

    bom_lines = defaultdict(list)
    for r in conn.execute(
        "SELECT product_id, component_id, qty_required, "
        "COALESCE(scrap_pct, 0.0) AS scrap_pct FROM bom"
    ).fetchall():
        bom_lines[r["product_id"]].append(
            (r["component_id"], r["qty_required"], r["scrap_pct"]))

    # Firm sales-order demand, optionally limited to the horizon by ship date.
    placeholders = ",".join(["%s"] * len(DEMAND_SO_STATUSES))
    demand_sql = (
        "SELECT si.product_id AS pid, SUM(si.qty) AS qty "
        "FROM so_item si JOIN sales_order so ON so.id = si.so_id "
        f"WHERE so.status IN ({placeholders}) AND si.product_id IS NOT NULL"
    )
    params = list(DEMAND_SO_STATUSES)
    if horizon_days is not None:
        cutoff = (date.today() + timedelta(days=horizon_days)).isoformat()
        demand_sql += " AND (so.ship_date IS NULL OR so.ship_date <= %s)"
        params.append(cutoff)
    demand_sql += " GROUP BY si.product_id"
    demand = {r["pid"]: float(r["qty"] or 0)
              for r in conn.execute(demand_sql, params).fetchall()}

    on_hand = {r["id"]: float(r["amount"] or 0) for r in conn.execute(
        "SELECT id, COALESCE(amount, 0) AS amount FROM product").fetchall()}
    safety = {r["id"]: float(r["reorder_point"] or 0) for r in conn.execute(
        "SELECT id, COALESCE(reorder_point, 0) AS reorder_point "
        "FROM product").fetchall()}

    scheduled = defaultdict(float)
    for r in conn.execute(
        "SELECT pi.product_id AS pid, "
        "SUM(GREATEST(pi.qty_ordered - COALESCE(pi.qty_received, 0), 0)) AS q "
        "FROM po_item pi JOIN purchase_order po ON po.id = pi.po_id "
        "WHERE po.status = %s AND pi.product_id IS NOT NULL "
        "GROUP BY pi.product_id", (OPEN_PO_STATUS,)
    ).fetchall():
        scheduled[r["pid"]] += float(r["q"] or 0)
    wo_placeholders = ",".join(["%s"] * len(OPEN_WO_STATUSES))
    for r in conn.execute(
        "SELECT product_id AS pid, SUM(quantity) AS q FROM work_order "
        f"WHERE status IN ({wo_placeholders}) AND product_id IS NOT NULL "
        "GROUP BY product_id", list(OPEN_WO_STATUSES)
    ).fetchall():
        scheduled[r["pid"]] += float(r["q"] or 0)

    return products, bom_lines, demand, on_hand, dict(scheduled), safety


def run_mrp(horizon_days=None, notes=""):
    """Run MRP against the live tables and persist a planned-order set.

    Returns ``(run_id, planned_count)``.
    """
    conn = get_db()
    try:
        init_mrp_tables(conn)
        products, bom_lines, demand, on_hand, scheduled, safety = \
            _gather_inputs(conn, horizon_days)
        planned = plan_orders(products, bom_lines, demand, on_hand,
                              scheduled, safety)
        run_date = date.today().isoformat()
        cur = conn.execute(
            "INSERT INTO mrp_run (run_date, horizon_days, notes) "
            "VALUES (%s, %s, %s) RETURNING id",
            (run_date, horizon_days, notes))
        run_id = cur.fetchone()["id"]
        # v1: a single need date (today). Time-phasing is a later refinement;
        # lead_time_days is carried so PR 4 can derive a start date.
        need = run_date
        for po in planned:
            conn.execute(
                "INSERT INTO mrp_planned_order "
                "(run_id, product_id, order_type, qty, need_date, "
                "lead_time_days, status) "
                "VALUES (%s,%s,%s,%s,%s,%s,'suggested')",
                (run_id, po["product_id"], po["order_type"],
                 po["qty"], need, po["lead_time_days"]))
        conn.commit()
        return run_id, len(planned)
    finally:
        conn.close()


def get_latest_run(conn):
    return conn.execute(
        "SELECT * FROM mrp_run ORDER BY id DESC LIMIT 1").fetchone()


def get_planned_orders(conn, run_id):
    return conn.execute(
        "SELECT po.id, po.product_id, p.name AS product_name, "
        "p.uom, po.order_type, po.qty, po.need_date, po.lead_time_days, "
        "po.status FROM mrp_planned_order po "
        "JOIN product p ON p.id = po.product_id "
        "WHERE po.run_id = %s ORDER BY po.order_type, p.name",
        (run_id,)).fetchall()


# ── Read-only results view ──────────────────────────────────────────────

def _apply_blue_palette(widget):
    pal = widget.palette()
    for group in (QtGui.QPalette.ColorGroup.Active,
                  QtGui.QPalette.ColorGroup.Inactive,
                  QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(group, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(group, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _ro(text):
    item = QtWidgets.QTableWidgetItem(text)
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    return item


class MrpWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        conn = get_db()
        init_mrp_tables(conn)
        conn.commit()
        conn.close()
        self._load_latest()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        top = QtWidgets.QHBoxLayout()
        lbl_h = QtWidgets.QLabel("Horizon:")
        lbl_h.setStyleSheet(LABEL_STYLE)
        top.addWidget(lbl_h)
        self.horizon = QtWidgets.QSpinBox()
        self.horizon.setRange(1, 3650)
        self.horizon.setValue(30)
        self.horizon.setSuffix(" days")
        self.horizon.setStyleSheet(INPUT_STYLE)
        top.addWidget(self.horizon)

        b_run = QtWidgets.QPushButton("Run MRP")
        b_run.setStyleSheet(BUTTON_STYLE)
        b_run.setFixedHeight(30)
        b_run.clicked.connect(self._on_run)
        top.addWidget(b_run)

        self.status_lbl = QtWidgets.QLabel("")
        self.status_lbl.setStyleSheet(LABEL_STYLE)
        top.addWidget(self.status_lbl)
        top.addStretch()
        v.addLayout(top)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Product", "Order Type", "Suggested Qty", "UoM",
             "Lead Time", "Status"])
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in range(1, 6):
            hh.setSectionResizeMode(
                c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table, stretch=1)

        hint = QtWidgets.QLabel(
            "Suggestions are read-only. Releasing a planned order into a "
            "requisition or work order is coming in a later update.")
        hint.setStyleSheet("color: white; font-style: italic;")
        hint.setWordWrap(True)
        v.addWidget(hint)

    def _on_run(self):
        try:
            run_id, count = run_mrp(self.horizon.value())
        except Exception as exc:  # surface DB/query errors to the user
            QtWidgets.QMessageBox.critical(self, "MRP Error", str(exc))
            return
        self.status_lbl.setText(f"Run #{run_id}: {count} planned order(s)")
        self._load_run(run_id)

    def _load_latest(self):
        conn = get_db()
        run = get_latest_run(conn)
        conn.close()
        if run is None:
            self.status_lbl.setText("No runs yet — click Run MRP.")
            self.table.setRowCount(0)
            return
        self.status_lbl.setText(
            f"Last run #{run['id']} on {run['run_date']}")
        self._load_run(run["id"])

    def _load_run(self, run_id):
        conn = get_db()
        rows = get_planned_orders(conn, run_id)
        conn.close()
        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            order_type = (row["order_type"] or "").capitalize()
            status = (row["status"] or "").capitalize()
            self.table.setItem(r, 0, _ro(row["product_name"] or ""))
            self.table.setItem(r, 1, _ro(order_type))
            self.table.setItem(r, 2, _ro(f"{row['qty']:g}"))
            self.table.setItem(r, 3, _ro(row["uom"] or "ea"))
            self.table.setItem(
                r, 4, _ro(f"{row['lead_time_days'] or 0} d"))
            self.table.setItem(r, 5, _ro(status))
            bg = QtGui.QColor(
                COLOR_MAKE if row["order_type"] == "make" else COLOR_BUY)
            for c in range(6):
                self.table.item(r, c).setBackground(bg)


class MrpWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Material Requirements Planning")
        self.resize(960, 640)
        _apply_blue_palette(self)
        self.setCentralWidget(MrpWidget())


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MrpWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
