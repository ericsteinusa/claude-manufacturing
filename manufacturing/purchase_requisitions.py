"""purchase_requisitions.py — Internal purchase-requisition workflow.

An employee in any department raises a requisition; their department
manager authorizes (or denies) it; authorized requisitions are routed to
the Purchasing Department Manager for final approval or denial.

This is distinct from ``purchase_orders.py`` (outbound supplier POs).
Requisitions live on their own tables and, once approved by Purchasing,
form a queue that can later be turned into a supplier PO.

Identity is established with an in-screen "Acting as" selector rather than
a login session, matching the app's one-process-per-screen architecture.

Run standalone:  ``python -m manufacturing.purchase_requisitions``
"""

import sys
import psycopg2
from .db_pg import get_db_connection
from .accounts import get_current_user_email
from .purchase_requisitions_core import can_authorize
from .purchase_orders_core import (load_products, next_po_number,
                                   ensure_po_tables)
from PyQt6 import QtCore, QtGui, QtWidgets
from .qt_theme import (
    BUTTON_STYLE, INPUT_STYLE, COMBO_STYLE, LABEL_STYLE,
    apply_blue_palette as _apply_blue_palette, ro as _ro,
)


def get_db():
    return get_db_connection()


REQ_COLORS = {
    "draft":         "#ffffff",
    "submitted":     "#cce5ff",
    "dept_approved": "#d1ecf1",
    "dept_denied":   "#f8d7da",
    "approved":      "#d4edda",
    "denied":        "#f5c6cb",
    "cancelled":     "#dcdcdc",
}

# Human-readable status labels.
REQ_STATUS_LABELS = {
    "draft":         "Draft",
    "submitted":     "Submitted",
    "dept_approved": "Dept Approved",
    "dept_denied":   "Dept Denied",
    "approved":      "Approved",
    "denied":        "Denied",
    "cancelled":     "Cancelled",
}


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase_requisition (
            id SERIAL PRIMARY KEY,
            req_number TEXT NOT NULL UNIQUE,
            requester_id INTEGER,
            dept_id INTEGER,
            dept_sub_id INTEGER,
            needed_date TEXT,
            justification TEXT,
            status TEXT DEFAULT 'draft',
            created_date TEXT,
            po_id INTEGER
        )
    """)
    # Link to a generated supplier PO (added to pre-existing tables too).
    conn.execute(
        "ALTER TABLE purchase_requisition "
        "ADD COLUMN IF NOT EXISTS po_id INTEGER")
    # Requester's sub-department, captured for display (added to pre-existing
    # tables too); authorization is still gated at the department level.
    conn.execute(
        "ALTER TABLE purchase_requisition "
        "ADD COLUMN IF NOT EXISTS dept_sub_id INTEGER")
    conn.execute(
        "ALTER TABLE purchase_requisition "
        "ADD COLUMN IF NOT EXISTS created_by TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS requisition_item (
            id SERIAL PRIMARY KEY,
            req_id INTEGER NOT NULL REFERENCES purchase_requisition(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty INTEGER DEFAULT 1,
            est_unit_price REAL DEFAULT 0.0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS requisition_approval (
            id SERIAL PRIMARY KEY,
            req_id INTEGER NOT NULL REFERENCES purchase_requisition(id),
            level TEXT,
            approver_id INTEGER,
            decision TEXT,
            comment TEXT,
            decided_date TEXT
        )
    """)
    conn.commit()
    conn.close()


def _today():
    return QtCore.QDate.currentDate().toString("yyyy-MM-dd")


def _next_req_num(conn=None):
    """Return the next REQ-YYYY-NNNN number.

    Accepts an optional *conn* so callers inside an open transaction can pass
    their connection — uncommitted rows on the same connection are then
    visible,
    preventing duplicate numbers when several requisitions are inserted in one
    transaction.  When called without a connection a fresh one is opened and
    closed (backwards-compatible, but subject to the usual gap/race caveats).
    """
    from .mrp_core import next_sequence_number
    import datetime
    yr = datetime.date.today().year
    prefix = f"REQ-{yr}-"
    own_conn = conn is None
    if own_conn:
        conn = get_db()
    try:
        rows = conn.execute(
            "SELECT req_number FROM purchase_requisition "
            "WHERE req_number LIKE %s", (prefix + "%",)
        ).fetchall()
    finally:
        if own_conn:
            conn.close()
    return next_sequence_number([r["req_number"] for r in rows], prefix)


# Roles permitted to authorize requisitions, matching the role names
# actually present in the ``roles`` table. Senior leadership can authorize
# any department; the rest only their own.


def _load_people():
    """People with their department and role, for the 'Acting as' picker."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT p.id,
                   p.first_name, p.last_name,
                   p.dept_id, d.dept_name,
                   p.dept_sub_id, ds.dept_sub_name,
                   r.role_name
            FROM people p
            LEFT JOIN dept d ON d.dept_id = p.dept_id
            LEFT JOIN dept_sub ds ON ds.dept_sub_id = p.dept_sub_id
            LEFT JOIN user_roles ur ON ur.people_id = p.id
            LEFT JOIN roles r ON r.id = ur.role_id
            ORDER BY p.last_name, p.first_name
        """).fetchall()
    except psycopg2.OperationalError:
        rows = []
    conn.close()
    return rows


# ── Dialogs ─────────────────────────────────────────────────────────────

class NewRequisitionDialog(QtWidgets.QDialog):
    """Create a draft requisition for the acting person's department."""

    def __init__(self, requester_id, dept_id, dept_sub_id=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Purchase Requisition")
        self.resize(480, 260)
        _apply_blue_palette(self)
        self._requester_id = requester_id
        self._dept_id = dept_id
        self._dept_sub_id = dept_sub_id
        self.req_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.req_num = QtWidgets.QLineEdit(_next_req_num())
        self.req_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Requisition #:"), self.req_num)

        self.needed_date = QtWidgets.QDateEdit(
            QtCore.QDate.currentDate().addDays(7))
        self.needed_date.setCalendarPopup(True)
        self.needed_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Needed By:"), self.needed_date)

        self.justification = QtWidgets.QLineEdit()
        self.justification.setStyleSheet(INPUT_STYLE)
        self.justification.setPlaceholderText("Reason for the request")
        layout.addRow(lbl("Justification:"), self.justification)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        req_num = self.req_num.text().strip()
        if not req_num:
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Requisition number is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO purchase_requisition (req_number, requester_id, "
                "dept_id, dept_sub_id, needed_date, justification, status, "
                "created_date, created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,'draft',%s,%s) RETURNING id",
                (req_num, self._requester_id, self._dept_id,
                 self._dept_sub_id,
                 self.needed_date.date().toString("yyyy-MM-dd"),
                 self.justification.text().strip(), _today(),
                 get_current_user_email() or None)
            )
            self.req_id = cur.fetchone()["id"]
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(
                self, "Duplicate",
                f"Requisition '{req_num}' already exists.")
            conn.close()
            return
        conn.close()
        self.accept()


class AddRequisitionItemDialog(QtWidgets.QDialog):
    def __init__(self, req_id, req_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Item — {req_number}")
        self.resize(460, 240)
        _apply_blue_palette(self)
        self._req_id = req_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.product_combo = QtWidgets.QComboBox()
        self.product_combo.setStyleSheet(COMBO_STYLE)
        self.product_combo.currentIndexChanged.connect(
            self._on_product_changed)
        self.product_combo.addItem("(none)", None)
        _pconn = get_db()
        for p in load_products(_pconn):
            self.product_combo.addItem(p["product_name"], p["id"])
        _pconn.close()
        layout.addRow(lbl("Product (opt):"), self.product_combo)

        self.desc = QtWidgets.QLineEdit()
        self.desc.setStyleSheet(INPUT_STYLE)
        self.desc.setPlaceholderText("Description (required)")
        layout.addRow(lbl("Description:"), self.desc)

        self.qty = QtWidgets.QSpinBox()
        self.qty.setRange(1, 999999)
        self.qty.setValue(1)
        self.qty.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Qty:"), self.qty)

        self.est_price = QtWidgets.QDoubleSpinBox()
        self.est_price.setRange(0.0, 9999999.99)
        self.est_price.setDecimals(2)
        self.est_price.setPrefix("$ ")
        self.est_price.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Est. Unit Price:"), self.est_price)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_product_changed(self):
        pid = self.product_combo.currentData()
        if pid is not None and not self.desc.text():
            self.desc.setText(self.product_combo.currentText())

    def _on_ok(self):
        desc = self.desc.text().strip()
        if not desc:
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Description is required.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO requisition_item (req_id, description, product_id, "
            "qty, est_unit_price) VALUES (%s,%s,%s,%s,%s)",
            (self._req_id, desc, self.product_combo.currentData(),
             self.qty.value(), self.est_price.value())
        )
        conn.commit()
        conn.close()
        self.accept()


class DecisionDialog(QtWidgets.QDialog):
    """Capture an optional comment for an approve/deny decision."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(420, 200)
        _apply_blue_palette(self)
        self.comment = ""
        self._build_ui(title)

    def _build_ui(self, title):
        v = QtWidgets.QVBoxLayout(self)
        lbl = QtWidgets.QLabel(title)
        lbl.setStyleSheet(LABEL_STYLE)
        v.addWidget(lbl)
        self.edit = QtWidgets.QPlainTextEdit()
        self.edit.setStyleSheet(
            "QPlainTextEdit{background-color: white; border: 2px solid "
            "black; border-radius: 4px;}")
        self.edit.setPlaceholderText("Comment (optional)")
        v.addWidget(self.edit)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _on_ok(self):
        self.comment = self.edit.toPlainText().strip()
        self.accept()


# ── Shared base ─────────────────────────────────────────────────────────

class _RequisitionViewBase(QtWidgets.QWidget):
    """Master/detail view of requisitions with a line-item + history split.

    Subclasses supply the row query (``_fetch_rows``) and the action button
    row (``_build_actions``).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._row_ids = []
        self._selected_id = None
        self._selected_number = None
        self._selected_status = None
        init_db()
        self._build_ui()
        self.refresh()

    # -- layout --
    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)
        self._build_header(v)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            ["Req #", "Requester", "Department", "Sub-Dept", "Needed By",
             "Items", "Est. Total", "Status", "Created By"])
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        for c in range(7):
            hh.setSectionResizeMode(
                c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
            8, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.clicked.connect(self._on_row_clicked)
        splitter.addWidget(self.table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QHBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)

        items_box = QtWidgets.QVBoxLayout()
        il = QtWidgets.QLabel("Line Items")
        il.setStyleSheet(
            "color: white; font-weight: bold; font-size: 13px;")
        items_box.addWidget(il)
        self.item_table = QtWidgets.QTableWidget()
        self.item_table.setColumnCount(4)
        self.item_table.setHorizontalHeaderLabels(
            ["Description", "Product", "Qty", "Est. Unit Price"])
        ih = self.item_table.horizontalHeader()
        ih.setStyleSheet("color: black; font-weight: bold;")
        ih.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            ih.setSectionResizeMode(
                c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.item_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.item_table.verticalHeader().setVisible(False)
        self.item_table.setAlternatingRowColors(True)
        items_box.addWidget(self.item_table)
        dv.addLayout(items_box, stretch=2)

        hist_box = QtWidgets.QVBoxLayout()
        hl = QtWidgets.QLabel("Approval History")
        hl.setStyleSheet(
            "color: white; font-weight: bold; font-size: 13px;")
        hist_box.addWidget(hl)
        self.hist_table = QtWidgets.QTableWidget()
        self.hist_table.setColumnCount(4)
        self.hist_table.setHorizontalHeaderLabels(
            ["Level", "Decision", "By", "Comment"])
        hth = self.hist_table.horizontalHeader()
        hth.setStyleSheet("color: black; font-weight: bold;")
        for c in (0, 1, 2):
            hth.setSectionResizeMode(
                c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hth.setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.hist_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hist_table.verticalHeader().setVisible(False)
        self.hist_table.setAlternatingRowColors(True)
        hist_box.addWidget(self.hist_table)
        dv.addLayout(hist_box, stretch=1)

        splitter.addWidget(detail_w)
        splitter.setSizes([380, 180])
        v.addWidget(splitter, stretch=1)

        self._build_actions(v)

    def _build_header(self, v):
        """Filter/identity row — subclasses override."""
        pass

    def _build_actions(self, v):
        """Action button row — subclasses override."""
        pass

    # -- data --
    def _fetch_rows(self):
        raise NotImplementedError

    def refresh(self):
        rows = self._fetch_rows()
        self.table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._row_ids.append(row["id"])
            name = f"{row['first_name'] or ''} " \
                   f"{row['last_name'] or ''}".strip()
            status = row["status"]
            self.table.setItem(r, 0, _ro(row["req_number"]))
            self.table.setItem(r, 1, _ro(name))
            self.table.setItem(r, 2, _ro(row["dept_name"] or ""))
            self.table.setItem(r, 3, _ro(row["dept_sub_name"] or ""))
            self.table.setItem(r, 4, _ro(row["needed_date"] or ""))
            self.table.setItem(r, 5, _ro(str(row["item_count"])))
            self.table.setItem(r, 6, _ro(f"${row['total']:,.2f}"))
            self.table.setItem(
                r, 7, _ro(REQ_STATUS_LABELS.get(status, status)))
            self.table.setItem(r, 8, _ro(row["created_by"] or ""))
            bg = QtGui.QColor(REQ_COLORS.get(status, "#ffffff"))
            for col in range(9):
                self.table.item(r, col).setBackground(bg)
        self._selected_id = None
        self._selected_number = None
        self._selected_status = None
        self.item_table.setRowCount(0)
        self.hist_table.setRowCount(0)
        self._on_selection_changed()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        self._selected_id = self._row_ids[row]
        self._selected_number = self.table.item(row, 0).text()
        self._selected_status = self._status_for_row(row)
        self._refresh_detail()
        self._on_selection_changed()

    def _status_for_row(self, row):
        conn = get_db()
        rec = conn.execute(
            "SELECT status FROM purchase_requisition WHERE id = %s",
            (self._row_ids[row],)).fetchone()
        conn.close()
        return rec["status"] if rec else None

    def _refresh_detail(self):
        self.item_table.setRowCount(0)
        self.hist_table.setRowCount(0)
        if self._selected_id is None:
            return
        conn = get_db()
        try:
            items = conn.execute("""
                SELECT ri.description, p.name AS product_name, ri.qty,
                       ri.est_unit_price
                FROM requisition_item ri
                LEFT JOIN product p ON p.id = ri.product_id
                WHERE ri.req_id = %s
            """, (self._selected_id,)).fetchall()
            hist = conn.execute("""
                SELECT ra.level, ra.decision, ra.comment,
                       pe.first_name, pe.last_name
                FROM requisition_approval ra
                LEFT JOIN people pe ON pe.id = ra.approver_id
                WHERE ra.req_id = %s
                ORDER BY ra.id
            """, (self._selected_id,)).fetchall()
        except psycopg2.OperationalError:
            items, hist = [], []
        conn.close()

        for it in items:
            r = self.item_table.rowCount()
            self.item_table.insertRow(r)
            self.item_table.setItem(r, 0, _ro(it["description"]))
            self.item_table.setItem(r, 1, _ro(it["product_name"] or ""))
            self.item_table.setItem(r, 2, _ro(str(it["qty"])))
            self.item_table.setItem(
                r, 3, _ro(f"${it['est_unit_price']:,.2f}"))

        for h in hist:
            r = self.hist_table.rowCount()
            self.hist_table.insertRow(r)
            by = f"{h['first_name'] or ''} " \
                 f"{h['last_name'] or ''}".strip()
            self.hist_table.setItem(
                r, 0, _ro((h["level"] or "").capitalize()))
            self.hist_table.setItem(
                r, 1, _ro((h["decision"] or "").capitalize()))
            self.hist_table.setItem(r, 2, _ro(by))
            self.hist_table.setItem(r, 3, _ro(h["comment"] or ""))

    def _on_selection_changed(self):
        """Hook for subclasses to enable/disable actions."""
        pass

    # -- shared helpers for subclasses --
    def _require_selection(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a requisition first.")
            return False
        return True

    def _record_decision(self, level, approver_id, decision, comment,
                         new_status):
        conn = get_db()
        conn.execute(
            "INSERT INTO requisition_approval (req_id, level, approver_id, "
            "decision, comment, decided_date) VALUES (%s,%s,%s,%s,%s,%s)",
            (self._selected_id, level, approver_id, decision, comment,
             _today()))
        conn.execute(
            "UPDATE purchase_requisition SET status = %s WHERE id = %s",
            (new_status, self._selected_id))
        conn.commit()
        conn.close()

    def _confirm(self, msg):
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No)
        return reply == QtWidgets.QMessageBox.StandardButton.Yes


# ── Department screen ───────────────────────────────────────────────────

class RequisitionsWidget(_RequisitionViewBase):
    """Shared screen: raise requests and (as a manager) authorize them.

    The acting person is chosen from a top-bar selector; their role and
    department gate which actions are available.

    ``default_dept`` (the host department's name) pre-selects the first
    person in that department, so the screen opens scoped to whoever
    launched it rather than to the first person company-wide.
    """

    def __init__(self, default_dept=None, parent=None):
        self._default_dept = default_dept
        super().__init__(parent)

    def _select_default_person(self):
        """Pre-select the first person in the host department, if given."""
        dept = getattr(self, "_default_dept", None)
        if not dept:
            return
        for i in range(self.person_combo.count()):
            pid = self.person_combo.itemData(i)
            person = next((p for p in self._people if p["id"] == pid), None)
            if person and person["dept_name"] == dept:
                self.person_combo.setCurrentIndex(i)
                return

    def _build_header(self, v):
        hr = QtWidgets.QHBoxLayout()
        lbl_a = QtWidgets.QLabel("Acting as:")
        lbl_a.setStyleSheet(LABEL_STYLE)
        hr.addWidget(lbl_a)
        self.person_combo = QtWidgets.QComboBox()
        self.person_combo.setStyleSheet(COMBO_STYLE)
        self.person_combo.setMinimumWidth(220)
        self._people = _load_people()
        for p in self._people:
            name = f"{p['first_name'] or ''} " \
                   f"{p['last_name'] or ''}".strip() or "(unnamed)"
            dept = p["dept_name"] or "no dept"
            sub = p["dept_sub_name"]
            where = f"{dept} / {sub}" if sub else dept
            role = p["role_name"] or "Employee"
            self.person_combo.addItem(
                f"{name} — {where} [{role}]", p["id"])
        # Select the host-department default before wiring the change signal,
        # so it doesn't fire a refresh() before the table is built.
        self._select_default_person()
        self.person_combo.currentIndexChanged.connect(self._on_person_changed)
        hr.addWidget(self.person_combo)

        self.role_lbl = QtWidgets.QLabel("")
        self.role_lbl.setStyleSheet(
            "color: white; font-weight: bold; font-size: 13px;")
        hr.addWidget(self.role_lbl)

        hr.addSpacing(16)
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        hr.addWidget(lbl_s)
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.setStyleSheet(COMBO_STYLE)
        self.status_filter.addItem("(all)", None)
        for s, label in REQ_STATUS_LABELS.items():
            self.status_filter.addItem(label, s)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        hr.addWidget(self.status_filter)
        hr.addStretch()
        v.addLayout(hr)

    def _build_actions(self, v):
        br = QtWidgets.QHBoxLayout()
        self._buttons = {}
        for key, text, slot in (
            ("new", "New Requisition", self._on_new),
            ("add", "Add Item", self._on_add_item),
            ("submit", "Submit", self._on_submit),
            ("cancel", "Cancel", self._on_cancel),
            ("authorize", "Authorize", lambda: self._on_dept_decision(
                "approved", "dept_approved", "Authorize Requisition")),
            ("deny", "Deny", lambda: self._on_dept_decision(
                "denied", "dept_denied", "Deny Requisition")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
            self._buttons[key] = b
        br.addStretch()
        v.addLayout(br)
        self._on_person_changed()

    # -- acting person --
    def _acting(self):
        pid = self.person_combo.currentData()
        for p in self._people:
            if p["id"] == pid:
                return p
        return None

    def _on_person_changed(self):
        p = self._acting()
        role = (p["role_name"] if p else None) or "Employee"
        self.role_lbl.setText(f"Role: {role}")
        self.refresh()

    def _on_selection_changed(self):
        if not hasattr(self, "_buttons"):
            return
        p = self._acting()
        role = (p["role_name"] if p else None) or ""
        sel = self._selected_id is not None
        is_own = bool(p) and sel and self._selected_requester() == p["id"]
        draft = self._selected_status == "draft"
        self._buttons["new"].setEnabled(bool(p))
        self._buttons["add"].setEnabled(is_own and draft)
        self._buttons["submit"].setEnabled(is_own and draft)
        self._buttons["cancel"].setEnabled(
            is_own and self._selected_status in ("draft", "submitted"))
        can_decide = can_authorize(
            role,
            self._selected_status or "",
            self._selected_dept(),
            p["dept_id"] if p else None,
            is_own,
        )
        self._buttons["authorize"].setEnabled(can_decide)
        self._buttons["deny"].setEnabled(can_decide)

    def _selected_requester(self):
        return self._selected_field("requester_id")

    def _selected_dept(self):
        return self._selected_field("dept_id")

    def _selected_field(self, field):
        if self._selected_id is None:
            return None
        conn = get_db()
        rec = conn.execute(
            f"SELECT {field} FROM purchase_requisition WHERE id = %s",
            (self._selected_id,)).fetchone()
        conn.close()
        return rec[field] if rec else None

    # -- query --
    def _fetch_rows(self):
        status = self.status_filter.currentData()
        conn = get_db()
        conds, params = [], []
        if status:
            conds.append("pr.status = %s")
            params.append(status)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        try:
            rows = conn.execute(_ROW_QUERY + where +
                                " ORDER BY pr.id DESC", params).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()
        return rows

    # -- actions --
    def _on_new(self):
        p = self._acting()
        if not p:
            QtWidgets.QMessageBox.warning(
                self, "No Person", "Select who you are acting as first.")
            return
        dlg = NewRequisitionDialog(
            p["id"], p["dept_id"], p["dept_sub_id"], self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_add_item(self):
        if not self._require_selection():
            return
        dlg = AddRequisitionItemDialog(
            self._selected_id, self._selected_number, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_submit(self):
        if not self._require_selection():
            return
        conn = get_db()
        n = conn.execute(
            "SELECT COUNT(*) FROM requisition_item WHERE req_id = %s",
            (self._selected_id,)).fetchone()[0]
        conn.close()
        if n == 0:
            QtWidgets.QMessageBox.warning(
                self, "No Items",
                "Add at least one line item before submitting.")
            return
        if not self._confirm("Submit this requisition to your "
                             "department manager?"):
            return
        conn = get_db()
        conn.execute(
            "UPDATE purchase_requisition SET status = 'submitted' "
            "WHERE id = %s", (self._selected_id,))
        conn.commit()
        conn.close()
        self.refresh()

    def _on_cancel(self):
        if not self._require_selection():
            return
        if not self._confirm("Cancel (withdraw) this requisition?"):
            return
        conn = get_db()
        conn.execute(
            "UPDATE purchase_requisition SET status = 'cancelled' "
            "WHERE id = %s", (self._selected_id,))
        conn.commit()
        conn.close()
        self.refresh()

    def _on_dept_decision(self, decision, new_status, title):
        if not self._require_selection():
            return
        p = self._acting()
        if p is None:
            return
        dlg = DecisionDialog(title, self)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self._record_decision(
            "department", p["id"], decision, dlg.comment, new_status)
        self.refresh()


# ── Purchasing Manager inbox ────────────────────────────────────────────

class RequisitionApprovalsWidget(_RequisitionViewBase):
    """Purchasing Manager's queue of department-approved requisitions."""

    def _build_header(self, v):
        hr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Requisition Approvals — Purchasing")
        title.setStyleSheet(
            "color: white; font-weight: bold; font-size: 14px;")
        hr.addWidget(title)
        hr.addSpacing(20)
        self.include_decided = QtWidgets.QCheckBox("Include decided")
        self.include_decided.setStyleSheet("color: white;")
        self.include_decided.stateChanged.connect(self.refresh)
        hr.addWidget(self.include_decided)
        hr.addStretch()
        v.addLayout(hr)

    def _build_actions(self, v):
        br = QtWidgets.QHBoxLayout()
        self.btn_approve = QtWidgets.QPushButton("Approve")
        self.btn_deny = QtWidgets.QPushButton("Deny")
        for b, slot in ((self.btn_approve,
                         lambda: self._decide("approved", "approved",
                                              "Approve Requisition")),
                        (self.btn_deny,
                         lambda: self._decide("denied", "denied",
                                              "Deny Requisition"))):
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        self.btn_create_po = QtWidgets.QPushButton("Create PO")
        self.btn_create_po.setStyleSheet(BUTTON_STYLE)
        self.btn_create_po.setFixedHeight(32)
        self.btn_create_po.clicked.connect(self._on_create_po)
        br.addWidget(self.btn_create_po)
        br.addStretch()
        v.addLayout(br)
        self._on_selection_changed()

    def _fetch_rows(self):
        conn = get_db()
        if self.include_decided.isChecked():
            cond = "pr.status IN ('dept_approved','approved','denied')"
        else:
            # Pending decisions plus approved requisitions still awaiting
            # conversion to a PO.
            cond = ("(pr.status = 'dept_approved' OR "
                    "(pr.status = 'approved' AND pr.po_id IS NULL))")
        try:
            rows = conn.execute(
                _ROW_QUERY + " WHERE " + cond +
                " ORDER BY pr.id DESC").fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()
        return rows

    def _on_selection_changed(self):
        if not hasattr(self, "btn_create_po"):
            return
        pending = self._selected_status == "dept_approved"
        self.btn_approve.setEnabled(pending)
        self.btn_deny.setEnabled(pending)
        self.btn_create_po.setEnabled(
            self._selected_status == "approved"
            and self._selected_req_field("po_id") is None)

    def _selected_req_field(self, field):
        if self._selected_id is None:
            return None
        conn = get_db()
        rec = conn.execute(
            f"SELECT {field} FROM purchase_requisition WHERE id = %s",
            (self._selected_id,)).fetchone()
        conn.close()
        return rec[field] if rec else None

    def _decide(self, decision, new_status, title):
        if not self._require_selection():
            return
        if self._selected_status != "dept_approved":
            QtWidgets.QMessageBox.warning(
                self, "Not Pending",
                "Only department-approved requisitions can be decided.")
            return
        dlg = DecisionDialog(title, self)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        # approver_id left NULL: the Purchasing Manager acts as the role,
        # no in-screen person selector on this inbox.
        self._record_decision(
            "purchasing", None, decision, dlg.comment, new_status)
        self.refresh()

    def _on_create_po(self):
        if not self._require_selection():
            return
        if self._selected_status != "approved":
            QtWidgets.QMessageBox.warning(
                self, "Not Approved",
                "Only approved requisitions can become a PO.")
            return
        existing = self._selected_req_field("po_id")
        if existing:
            conn = get_db()
            po = conn.execute(
                "SELECT po_number FROM purchase_order WHERE id = %s",
                (existing,)).fetchone()
            conn.close()
            num = po["po_number"] if po else f"#{existing}"
            QtWidgets.QMessageBox.information(
                self, "Already Converted",
                f"This requisition is already linked to PO {num}.")
            return
        if not self._confirm(
                "Create a draft purchase order from this requisition? "
                "Line items carry over; set the supplier afterward in the "
                "Purchase Orders screen."):
            return

        needed = self._selected_req_field("needed_date")
        expected = needed or QtCore.QDate.currentDate().addDays(
            14).toString("yyyy-MM-dd")
        conn = get_db()
        ensure_po_tables(conn)
        po_number = next_po_number(conn)
        po_id = conn.execute(
            "INSERT INTO purchase_order (po_number, supplier_id, "
            "order_date, expected_date, status, notes, created_by) "
            "VALUES (%s, NULL, %s, %s, 'draft', %s, %s) RETURNING id",
            (po_number, _today(), expected,
             f"From requisition {self._selected_number}",
             get_current_user_email() or None)
        ).fetchone()["id"]
        items = conn.execute(
            "SELECT description, product_id, qty, est_unit_price "
            "FROM requisition_item WHERE req_id = %s",
            (self._selected_id,)).fetchall()
        for it in items:
            conn.execute(
                "INSERT INTO po_item (po_id, description, product_id, "
                "qty_ordered, unit_price) VALUES (%s,%s,%s,%s,%s)",
                (po_id, it["description"], it["product_id"], it["qty"],
                 it["est_unit_price"]))
        conn.execute(
            "UPDATE purchase_requisition SET po_id = %s WHERE id = %s",
            (po_id, self._selected_id))
        conn.commit()
        conn.close()
        QtWidgets.QMessageBox.information(
            self, "PO Created",
            f"Created draft {po_number} from {self._selected_number} "
            f"({len(items)} item(s)).\nSet the supplier in the Purchase "
            f"Orders screen.")
        self.refresh()


# Shared SELECT used by both views; callers append WHERE/ORDER BY.
_ROW_QUERY = """
    SELECT pr.id, pr.req_number, pr.needed_date, pr.status,
           pr.requester_id, pr.dept_id, pr.dept_sub_id, pr.created_by,
           pe.first_name, pe.last_name, d.dept_name, ds.dept_sub_name,
           (SELECT COUNT(*) FROM requisition_item ri
            WHERE ri.req_id = pr.id) AS item_count,
           (SELECT COALESCE(SUM(ri.qty * ri.est_unit_price), 0)
            FROM requisition_item ri WHERE ri.req_id = pr.id) AS total
    FROM purchase_requisition pr
    LEFT JOIN people pe ON pe.id = pr.requester_id
    LEFT JOIN dept d ON d.dept_id = pr.dept_id
    LEFT JOIN dept_sub ds ON ds.dept_sub_id = pr.dept_sub_id
"""


# ── Standalone window ───────────────────────────────────────────────────

class PurchaseRequisitionsWindow(QtWidgets.QMainWindow):
    def __init__(self, default_dept=None):
        super().__init__()
        email = get_current_user_email()
        title = (f"Purchase Requisitions — {email}"
                 if email else "Purchase Requisitions")
        self.setWindowTitle(title)
        _apply_blue_palette(self)
        self.setCentralWidget(RequisitionsWidget(default_dept))


def main():
    init_db()
    # Optional positional arg: the host department to scope the picker to.
    default_dept = sys.argv[1] if len(sys.argv) > 1 else None
    app = QtWidgets.QApplication(sys.argv)
    window = PurchaseRequisitionsWindow(default_dept)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
