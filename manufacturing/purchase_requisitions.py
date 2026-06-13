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
from .purchase_orders import _load_products
from PyQt6 import QtCore, QtGui, QtWidgets


def get_db():
    return get_db_connection()


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
COMBO_STYLE = (
    "QComboBox{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
    "QComboBox QAbstractItemView{background-color: white;}"
)
LABEL_STYLE = "color: white; font-size: 13px;"

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
            needed_date TEXT,
            justification TEXT,
            status TEXT DEFAULT 'draft',
            created_date TEXT
        )
    """)
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


def _today():
    return QtCore.QDate.currentDate().toString("yyyy-MM-dd")


def _next_req_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM purchase_requisition "
        "WHERE req_number LIKE %s", (f"REQ-{yr}-%",)
    ).fetchone()[0]
    conn.close()
    return f"REQ-{yr}-{count + 1:04d}"


def _is_manager(role_name):
    """Managers (and Admins) may authorize their department's requests."""
    return role_name in ("Manager", "Admin")


def _load_people():
    """People with their department and role, for the 'Acting as' picker."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT p.id,
                   p.first_name, p.last_name,
                   p.dept_id, d.dept_name,
                   r.role_name
            FROM people p
            LEFT JOIN dept d ON d.dept_id = p.dept_id
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

    def __init__(self, requester_id, dept_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Purchase Requisition")
        self.resize(480, 260)
        _apply_blue_palette(self)
        self._requester_id = requester_id
        self._dept_id = dept_id
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
                "dept_id, needed_date, justification, status, created_date) "
                "VALUES (%s,%s,%s,%s,%s,'draft',%s) RETURNING id",
                (req_num, self._requester_id, self._dept_id,
                 self.needed_date.date().toString("yyyy-MM-dd"),
                 self.justification.text().strip(), _today())
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
        for p in _load_products():
            self.product_combo.addItem(p["product_name"], p["id"])
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
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Req #", "Requester", "Department", "Needed By",
             "Items", "Est. Total", "Status"])
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        for c in range(6):
            hh.setSectionResizeMode(
                c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Stretch)
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
            self.table.setItem(r, 3, _ro(row["needed_date"] or ""))
            self.table.setItem(r, 4, _ro(str(row["item_count"])))
            self.table.setItem(r, 5, _ro(f"${row['total']:,.2f}"))
            self.table.setItem(
                r, 6, _ro(REQ_STATUS_LABELS.get(status, status)))
            bg = QtGui.QColor(REQ_COLORS.get(status, "#ffffff"))
            for col in range(7):
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
                SELECT ri.description, p.product_name, ri.qty,
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


# ── Department screen ───────────────────────────────────────────────────

class RequisitionsWidget(_RequisitionViewBase):
    """Shared screen: raise requests and (as a manager) authorize them.

    The acting person is chosen from a top-bar selector; their role and
    department gate which actions are available.
    """

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
            role = p["role_name"] or "Employee"
            self.person_combo.addItem(
                f"{name} — {dept} [{role}]", p["id"])
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
        is_mgr = _is_manager((p["role_name"] if p else None) or "")
        sel = self._selected_id is not None
        is_own = bool(p) and sel and self._selected_requester() == p["id"]
        submitted = self._selected_status == "submitted"
        draft = self._selected_status == "draft"
        self._buttons["new"].setEnabled(bool(p))
        self._buttons["add"].setEnabled(is_own and draft)
        self._buttons["submit"].setEnabled(is_own and draft)
        self._buttons["cancel"].setEnabled(
            is_own and self._selected_status in ("draft", "submitted"))
        # A manager may authorize/deny submitted requests in their own dept,
        # but not their own request.
        can_decide = (is_mgr and submitted and bool(p)
                      and self._selected_dept() == p["dept_id"]
                      and not is_own)
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
        dlg = NewRequisitionDialog(p["id"], p["dept_id"], self)
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
        dlg = DecisionDialog(title, self)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self._record_decision(
            "department", p["id"], decision, dlg.comment, new_status)
        self.refresh()

    def _confirm(self, msg):
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No)
        return reply == QtWidgets.QMessageBox.StandardButton.Yes


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
        br.addStretch()
        v.addLayout(br)
        self._on_selection_changed()

    def _fetch_rows(self):
        conn = get_db()
        if self.include_decided.isChecked():
            cond = "pr.status IN ('dept_approved','approved','denied')"
        else:
            cond = "pr.status = 'dept_approved'"
        try:
            rows = conn.execute(
                _ROW_QUERY + " WHERE " + cond +
                " ORDER BY pr.id DESC").fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()
        return rows

    def _on_selection_changed(self):
        if not hasattr(self, "btn_approve"):
            return
        pending = self._selected_status == "dept_approved"
        self.btn_approve.setEnabled(pending)
        self.btn_deny.setEnabled(pending)

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


# Shared SELECT used by both views; callers append WHERE/ORDER BY.
_ROW_QUERY = """
    SELECT pr.id, pr.req_number, pr.needed_date, pr.status,
           pr.requester_id, pr.dept_id,
           pe.first_name, pe.last_name, d.dept_name,
           (SELECT COUNT(*) FROM requisition_item ri
            WHERE ri.req_id = pr.id) AS item_count,
           (SELECT COALESCE(SUM(ri.qty * ri.est_unit_price), 0)
            FROM requisition_item ri WHERE ri.req_id = pr.id) AS total
    FROM purchase_requisition pr
    LEFT JOIN people pe ON pe.id = pr.requester_id
    LEFT JOIN dept d ON d.dept_id = pr.dept_id
"""


# ── Standalone window ───────────────────────────────────────────────────

class PurchaseRequisitionsWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Purchase Requisitions")
        self.resize(1040, 700)
        _apply_blue_palette(self)
        self.setCentralWidget(RequisitionsWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = PurchaseRequisitionsWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
