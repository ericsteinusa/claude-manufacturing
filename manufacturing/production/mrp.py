"""mrp.py — Material Requirements Planning engine (time-phased, lead-time offsetting).

Given demand from confirmed Sales Orders (bucketed by ship_date), on-hand stock,
open POs, and open WOs, this module:
  - Nets requirements level-by-level through the BOM
  - Offsets each component's need date by the parent's lead time
  - Persists planned orders with both start_date and due_date
  - Releases buy suggestions as draft purchase requisitions, make suggestions
    as planned work orders with BOM-exploded material lists

Safety stock = product.reorder_point (set per product in Inventory).
"""

import math
import sys
from collections import defaultdict
from datetime import date, timedelta

from PyQt6 import QtGui, QtWidgets
from ..qt_theme import (
    BUTTON_STYLE,
    INPUT_STYLE,
    LABEL_STYLE,
    apply_blue_palette as _apply_blue_palette,
    ro as _ro,
)


from ..accounts import get_current_user_email
from .bom import explode_bom_to_wo
from ..db_pg import get_db_connection
from ..mrp_core import compute_levels, plan_orders, plan_orders_dated, next_sequence_number
from ..purchase_requisitions import _next_req_num

# Re-exported so callers/tests can reach the pure planning core.
__all__ = ["compute_levels", "plan_orders"]


COLOR_MAKE = "#d4edda"
COLOR_BUY  = "#fff3cd"

DEMAND_SO_STATUSES = ("confirmed",)
OPEN_PO_STATUS     = "sent"
OPEN_WO_STATUSES   = ("planned", "open", "in_progress")


def get_db():
    return get_db_connection()


# ── Schema ──────────────────────────────────────────────────────────────

def init_mrp_tables(conn):
    """Create / migrate the planned-order tables (idempotent)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mrp_run (
            id SERIAL PRIMARY KEY,
            run_date TEXT,
            horizon_days INTEGER,
            notes TEXT,
            created_by TEXT
        )
    """)
    conn.execute(
        "ALTER TABLE mrp_run ADD COLUMN IF NOT EXISTS created_by TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mrp_planned_order (
            id SERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES mrp_run(id),
            product_id INTEGER NOT NULL,
            order_type TEXT,
            qty REAL,
            need_date TEXT,
            start_date TEXT,
            lead_time_days INTEGER DEFAULT 0,
            status TEXT DEFAULT 'suggested',
            released_ref TEXT
        )
    """)
    conn.execute(
        "ALTER TABLE mrp_planned_order "
        "ADD COLUMN IF NOT EXISTS released_ref TEXT")
    conn.execute(
        "ALTER TABLE mrp_planned_order "
        "ADD COLUMN IF NOT EXISTS start_date TEXT")


# ── DB input gathering ──────────────────────────────────────────────────

def _gather_inputs(conn, horizon_days=None):
    """Collect demand/supply lookups from the live tables.

    Returns
    -------
    products, bom_lines, demand_dated, on_hand, scheduled, safety

    ``demand_dated`` is ``{pid: [(qty, date), ...]}`` keyed by SO ship_date
    (falls back to today + 30 when NULL). The time-phased planner uses this
    to back-schedule component need dates via lead-time offsetting.
    """
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

    # Demand bucketed by SO ship_date for time-phased planning.
    fallback = (date.today() + timedelta(days=30)).isoformat()
    placeholders = ",".join(["%s"] * len(DEMAND_SO_STATUSES))
    demand_sql = (
        "SELECT si.product_id AS pid, SUM(si.qty) AS qty, "
        f"COALESCE(so.ship_date, %s) AS need_date "
        "FROM so_item si JOIN sales_order so ON so.id = si.so_id "
        f"WHERE so.status IN ({placeholders}) AND si.product_id IS NOT NULL"
    )
    params: list = [fallback] + list(DEMAND_SO_STATUSES)
    if horizon_days is not None:
        cutoff = (date.today() + timedelta(days=horizon_days)).isoformat()
        demand_sql += " AND (so.ship_date IS NULL OR so.ship_date <= %s)"
        params.append(cutoff)
    demand_sql += " GROUP BY si.product_id, need_date"

    demand_dated: dict = {}
    for r in conn.execute(demand_sql, params).fetchall():
        nd = r["need_date"]
        if isinstance(nd, str):
            nd = date.fromisoformat(nd)
        demand_dated.setdefault(r["pid"], []).append(
            (float(r["qty"] or 0), nd))

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

    return products, bom_lines, demand_dated, on_hand, dict(scheduled), safety


def run_mrp(horizon_days=None, notes="", created_by=None):
    """Run time-phased MRP against the live tables and persist a planned-order set.

    Returns ``(run_id, planned_count)``.
    Each planned order stores both ``start_date`` (when to begin) and
    ``need_date`` (due date = when the parent needs it).
    """
    conn = get_db()
    try:
        init_mrp_tables(conn)
        products, bom_lines, demand_dated, on_hand, scheduled, safety = \
            _gather_inputs(conn, horizon_days)
        planned = plan_orders_dated(
            products, bom_lines, demand_dated, on_hand, scheduled, safety)

        run_date = date.today().isoformat()
        cur = conn.execute(
            "INSERT INTO mrp_run (run_date, horizon_days, notes, created_by) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (run_date, horizon_days, notes, created_by))
        run_id = cur.fetchone()["id"]

        for po in planned:
            conn.execute(
                "INSERT INTO mrp_planned_order "
                "(run_id, product_id, order_type, qty, need_date, "
                "start_date, lead_time_days, status) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'suggested')",
                (run_id, po["product_id"], po["order_type"],
                 po["qty"], po["due_date"], po["start_date"],
                 po["lead_time_days"]))
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
        "p.uom, po.order_type, po.qty, po.need_date, po.start_date, "
        "po.lead_time_days, po.status, po.released_ref "
        "FROM mrp_planned_order po "
        "JOIN product p ON p.id = po.product_id "
        "WHERE po.run_id = %s ORDER BY po.start_date ASC NULLS LAST, p.name",
        (run_id,)).fetchall()


# ── Release into requisitions / work orders ─────────────────────────────

def release_planned_orders(order_ids):
    """Turn suggested planned orders into real requisitions / work orders.

    Buy suggestions → single draft purchase requisition.
    Make suggestions → individual planned work orders (BOM-exploded).
    Returns ``{'requisition': req_number|None, 'work_orders': [...],
               'released': n, 'skipped': n}``.
    """
    if not order_ids:
        return {"requisition": None, "work_orders": [], "released": 0,
                "skipped": 0}
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT po.id, po.product_id, po.order_type, po.qty, po.status, "
            "po.lead_time_days, po.start_date, po.need_date, "
            "p.name AS product_name, "
            "COALESCE(p.purchase_price, 0) AS price "
            "FROM mrp_planned_order po JOIN product p ON p.id = po.product_id "
            "WHERE po.id = ANY(%s)", (list(order_ids),)
        ).fetchall()
        actionable = [r for r in rows if r["status"] == "suggested"]
        skipped = len(rows) - len(actionable)
        buys  = [r for r in actionable if r["order_type"] == "buy"]
        makes = [r for r in actionable if r["order_type"] == "make"]

        req_number  = _create_requisition(conn, buys) if buys else None
        work_orders = [_create_work_order(conn, r) for r in makes]

        conn.commit()
        return {"requisition": req_number, "work_orders": work_orders,
                "released": len(actionable), "skipped": skipped}
    finally:
        conn.close()


def _create_requisition(conn, buys):
    req_number = _next_req_num(conn)
    today = date.today().isoformat()
    dept = conn.execute(
        "SELECT dept_id FROM dept WHERE dept_name = %s", ("Purchasing",)
    ).fetchone()
    dept_id = dept["dept_id"] if dept else None
    cur = conn.execute(
        "INSERT INTO purchase_requisition (req_number, requester_id, "
        "dept_id, dept_sub_id, needed_date, justification, status, "
        "created_date, created_by) "
        "VALUES (%s,NULL,%s,NULL,%s,%s,'draft',%s,%s) RETURNING id",
        (req_number, dept_id, today, "Generated by MRP", today,
         get_current_user_email() or None))
    req_id = cur.fetchone()["id"]
    for r in buys:
        conn.execute(
            "INSERT INTO requisition_item (req_id, description, product_id, "
            "qty, est_unit_price) VALUES (%s,%s,%s,%s,%s)",
            (req_id, r["product_name"], r["product_id"],
             int(math.ceil(r["qty"])), r["price"]))
        conn.execute(
            "UPDATE mrp_planned_order SET status = 'released', "
            "released_ref = %s WHERE id = %s", (req_number, r["id"]))
    return req_number


def _next_wo_number(conn):
    prefix = f"WO-{date.today().year}-"
    rows = conn.execute(
        "SELECT wo_number FROM work_order WHERE wo_number LIKE %s",
        (prefix + "%",)).fetchall()
    return next_sequence_number([r["wo_number"] for r in rows], prefix)


def _create_work_order(conn, row):
    """Create a planned work order using the MRP-computed start and due dates."""
    wo_number = _next_wo_number(conn)
    today = date.today().isoformat()

    # Use planned dates when available; fall back to today + lead time.
    start = row["start_date"] or today
    due   = row["need_date"] or (
        date.today() + timedelta(days=row["lead_time_days"] or 0)).isoformat()

    qty = int(math.ceil(row["qty"]))
    cur = conn.execute(
        "INSERT INTO work_order (wo_number, product_id, description, "
        "quantity, start_date, due_date, status, notes, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,'planned',%s,%s) RETURNING id",
        (wo_number, row["product_id"], row["product_name"], qty,
         start, due, "Generated by MRP",
         get_current_user_email() or None))
    wo_id = cur.fetchone()["id"]
    explode_bom_to_wo(conn, wo_id, row["product_id"], qty)
    conn.execute(
        "UPDATE mrp_planned_order SET status = 'released', "
        "released_ref = %s WHERE id = %s", (wo_number, row["id"]))
    return wo_number


# ── Qt widget ───────────────────────────────────────────────────────────

class MrpWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._current_run_id = None
        self._row_ids = []
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
        self.horizon.setValue(90)
        self.horizon.setSuffix(" days")
        self.horizon.setStyleSheet(INPUT_STYLE)
        top.addWidget(self.horizon)

        b_run = QtWidgets.QPushButton("Run MRP")
        b_run.setStyleSheet(BUTTON_STYLE)
        b_run.setFixedHeight(30)
        b_run.clicked.connect(self._on_run)
        top.addWidget(b_run)

        b_release = QtWidgets.QPushButton("Release Selected")
        b_release.setStyleSheet(BUTTON_STYLE)
        b_release.setFixedHeight(30)
        b_release.clicked.connect(self._on_release)
        top.addWidget(b_release)

        self.status_lbl = QtWidgets.QLabel("")
        self.status_lbl.setStyleSheet(LABEL_STYLE)
        top.addWidget(self.status_lbl)
        top.addStretch()
        v.addLayout(top)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Product", "Order Type", "Qty", "UoM",
            "Lead Time", "Start Date", "Due Date", "Status",
        ])
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in range(1, 8):
            hh.setSectionResizeMode(
                c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table, stretch=1)

        hint = QtWidgets.QLabel(
            "Rows are sorted by Start Date — earliest actions first. "
            "Select rows and click Release Selected: buy lines become a "
            "draft purchase requisition; make lines become planned work "
            "orders with BOM-exploded materials. Already-released rows "
            "are skipped.")
        hint.setStyleSheet("color: white; font-style: italic;")
        hint.setWordWrap(True)
        v.addWidget(hint)

    def _on_run(self):
        email = get_current_user_email()
        try:
            run_id, count = run_mrp(self.horizon.value(),
                                    created_by=email or None)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "MRP Error", str(exc))
            return
        by = f" by {email}" if email else ""
        self.status_lbl.setText(
            f"Run #{run_id}{by}: {count} planned order(s)")
        self._load_run(run_id)

    def _load_latest(self):
        conn = get_db()
        run = get_latest_run(conn)
        conn.close()
        if run is None:
            self.status_lbl.setText("No runs yet — click Run MRP.")
            self.table.setRowCount(0)
            return
        by = f" by {run['created_by']}" if run["created_by"] else ""
        self.status_lbl.setText(
            f"Last run #{run['id']} on {run['run_date']}{by}")
        self._load_run(run["id"])

    def _load_run(self, run_id):
        self._current_run_id = run_id
        conn = get_db()
        rows = get_planned_orders(conn, run_id)
        conn.close()
        self.table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._row_ids.append((row["id"], row["status"]))
            status = (row["status"] or "").capitalize()
            lt = row["lead_time_days"] or 0
            self.table.setItem(r, 0, _ro(row["product_name"] or ""))
            self.table.setItem(r, 1, _ro((row["order_type"] or "").capitalize()))
            self.table.setItem(r, 2, _ro(f"{row['qty']:g}"))
            self.table.setItem(r, 3, _ro(row["uom"] or "ea"))
            self.table.setItem(r, 4, _ro(f"{lt} d" if lt else "—"))
            self.table.setItem(r, 5, _ro(row["start_date"] or "—"))
            self.table.setItem(r, 6, _ro(row["need_date"] or "—"))
            self.table.setItem(r, 7, _ro(status))
            bg = QtGui.QColor(
                COLOR_MAKE if row["order_type"] == "make" else COLOR_BUY)
            for c in range(8):
                self.table.item(r, c).setBackground(bg)

    def _on_release(self):
        if self._current_run_id is None:
            return
        selected_rows = {idx.row() for idx in
                         self.table.selectionModel().selectedRows()}
        ids = [self._row_ids[r][0] for r in selected_rows
               if r < len(self._row_ids)
               and self._row_ids[r][1] == "suggested"]
        if not ids:
            QtWidgets.QMessageBox.information(
                self, "Nothing to Release",
                "Select one or more suggested rows first.")
            return
        try:
            summary = release_planned_orders(ids)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Release Error", str(exc))
            return
        parts = []
        if summary["requisition"]:
            parts.append(f"Requisition {summary['requisition']}")
        if summary["work_orders"]:
            parts.append("Work orders: " + ", ".join(summary["work_orders"]))
        if summary["skipped"]:
            parts.append(f"{summary['skipped']} already-released skipped")
        QtWidgets.QMessageBox.information(
            self, "Released",
            "\n".join(parts) or "Nothing released.")
        self._load_run(self._current_run_id)


class MrpWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Material Requirements Planning — {email}"
                 if email else "Material Requirements Planning")
        self.setWindowTitle(title)
        _apply_blue_palette(self)
        self.setCentralWidget(MrpWidget())


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MrpWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
