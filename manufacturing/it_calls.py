import sys
import psycopg2
from .db_pg import get_db
from .accounts import get_current_user_email
from PyQt6 import QtCore, QtGui, QtWidgets
from .qt_theme import (
    BLUE,
    BUTTON_STYLE,
    INPUT_STYLE,
    COMBO_STYLE,
    LABEL_STYLE,
    apply_blue_palette as _apply_blue_palette,
    ro as _ro,
)

from .button_nav import ButtonNav

TEXT_STYLE = (
    "QPlainTextEdit{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
)
TICKET_COLORS = {
    "open":        "#ffffff",
    "in_progress": "#fff3cd",
    "resolved":    "#d4edda",
    "closed":      "#dcdcdc",
    "on_hold":     "#f8d7da",
}

PRIORITY_COLORS = {
    "critical": QtGui.QColor(248, 215, 218),
    "high":     QtGui.QColor(255, 243, 205),
    "medium":   QtGui.QColor(220, 235, 255),
}

ASSET_STATUS_COLORS = {
    "active":    "#d4edda",
    "spare":     "#d1ecf1",
    "repair":    "#fff3cd",
    "retired":   "#dcdcdc",
    "lost":      "#f8d7da",
}


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS it_ticket (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_number TEXT NOT NULL UNIQUE,
            requester     TEXT,
            department    TEXT,
            issue_type    TEXT,
            description   TEXT NOT NULL,
            priority      TEXT DEFAULT 'medium',
            assigned_to   TEXT,
            submitted_date TEXT,
            due_date      TEXT,
            resolved_date TEXT,
            status        TEXT DEFAULT 'open',
            notes         TEXT,
            created_by    TEXT
        )
    """)
    conn.execute("""
        ALTER TABLE it_ticket
        ADD COLUMN IF NOT EXISTS created_by TEXT
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS it_asset (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_tag    TEXT NOT NULL UNIQUE,
            asset_type   TEXT,
            make         TEXT,
            model        TEXT,
            serial_number TEXT,
            assigned_to  TEXT,
            department   TEXT,
            purchase_date TEXT,
            warranty_exp TEXT,
            status       TEXT DEFAULT 'active',
            notes        TEXT
        )
    """)
    conn.commit()
    conn.close()


def _next_ticket_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM it_ticket WHERE ticket_number LIKE ?", (
                f"TKT-{yr}-%",)
        ).fetchone()[0]
    except psycopg2.OperationalError:
        count = 0
    conn.close()
    return f"TKT-{yr}-{count + 1:04d}"


# ── Dialogs ─────────────────────────────────────────────────────────────

class NewTicketDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Support Ticket")
        self.resize(500, 420)
        _apply_blue_palette(self)
        self.ticket_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.ticket_num = QtWidgets.QLineEdit(_next_ticket_num())
        self.ticket_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Ticket #:"), self.ticket_num)

        self.requester = QtWidgets.QLineEdit()
        self.requester.setStyleSheet(INPUT_STYLE)
        self.requester.setPlaceholderText("Person submitting the request")
        layout.addRow(lbl("Requester:"), self.requester)

        self.department = QtWidgets.QLineEdit()
        self.department.setStyleSheet(INPUT_STYLE)
        self.department.setPlaceholderText("Requester's department")
        layout.addRow(lbl("Department:"), self.department)

        self.issue_type = QtWidgets.QComboBox()
        self.issue_type.setStyleSheet(COMBO_STYLE)
        for t in ("Hardware", "Software", "Network", "Email", "Phone", "Printer",  # noqa: E501
                  "Access / Permissions", "Account", "Other"):
            self.issue_type.addItem(t, t)
        layout.addRow(lbl("Issue Type:"), self.issue_type)

        self.description = QtWidgets.QPlainTextEdit()
        self.description.setStyleSheet(TEXT_STYLE)
        self.description.setPlaceholderText("Describe the problem (required)")
        self.description.setFixedHeight(80)
        layout.addRow(lbl("Description:"), self.description)

        self.priority_combo = QtWidgets.QComboBox()
        self.priority_combo.setStyleSheet(COMBO_STYLE)
        for s in ("low", "medium", "high", "critical"):
            self.priority_combo.addItem(s.capitalize(), s)
        self.priority_combo.setCurrentIndex(1)
        layout.addRow(lbl("Priority:"), self.priority_combo)

        self.assigned_to = QtWidgets.QLineEdit()
        self.assigned_to.setStyleSheet(INPUT_STYLE)
        self.assigned_to.setPlaceholderText("Assigned technician")
        layout.addRow(lbl("Assigned To:"), self.assigned_to)

        self.submitted_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.submitted_date.setCalendarPopup(True)
        self.submitted_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Submitted:"), self.submitted_date)

        self.due_date = QtWidgets.QDateEdit(
    QtCore.QDate.currentDate().addDays(3))
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Notes:"), self.notes)

        created_by_lbl = QtWidgets.QLabel(
            get_current_user_email() or "(unknown)")
        created_by_lbl.setStyleSheet(LABEL_STYLE)
        layout.addRow(lbl("Created by:"), created_by_lbl)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        num = self.ticket_num.text().strip()
        desc = self.description.toPlainText().strip()
        if not num or not desc:
            QtWidgets.QMessageBox.warning(self, "Input Error",
                                          "Ticket number and description are "
                                          "required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO it_ticket (ticket_number, requester, department, "
                "issue_type, description, priority, assigned_to, "
                "submitted_date, due_date, notes, created_by)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (num, self.requester.text().strip(), self.department.text().strip(),  # noqa: E501
                 self.issue_type.currentData(), desc,
                 self.priority_combo.currentData(),
                 self.assigned_to.text().strip(),
                 self.submitted_date.date().toString("yyyy-MM-dd"),
                 self.due_date.date().toString("yyyy-MM-dd"),
                 self.notes.text().strip(),
                 get_current_user_email() or None)
            )
            self.ticket_id = cur.lastrowid
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"Ticket number '{num}' already exists.")  # noqa: E501
            conn.close()
            return
        conn.close()
        self.accept()


class NewAssetDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New IT Asset")
        self.resize(500, 390)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.asset_tag = QtWidgets.QLineEdit()
        self.asset_tag.setStyleSheet(INPUT_STYLE)
        self.asset_tag.setPlaceholderText("Unique asset tag (required)")
        layout.addRow(lbl("Asset Tag:"), self.asset_tag)

        self.asset_type = QtWidgets.QComboBox()
        self.asset_type.setStyleSheet(COMBO_STYLE)
        for t in ("Desktop", "Laptop", "Monitor", "Server", "Printer", "Phone",
                  "Tablet", "Switch", "Router", "UPS", "Other"):
            self.asset_type.addItem(t, t)
        layout.addRow(lbl("Type:"), self.asset_type)

        self.make = QtWidgets.QLineEdit()
        self.make.setStyleSheet(INPUT_STYLE)
        self.make.setPlaceholderText("e.g. Dell, HP, Cisco")
        layout.addRow(lbl("Make:"), self.make)

        self.model = QtWidgets.QLineEdit()
        self.model.setStyleSheet(INPUT_STYLE)
        self.model.setPlaceholderText("Model name / number")
        layout.addRow(lbl("Model:"), self.model)

        self.serial = QtWidgets.QLineEdit()
        self.serial.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Serial #:"), self.serial)

        self.assigned_to = QtWidgets.QLineEdit()
        self.assigned_to.setStyleSheet(INPUT_STYLE)
        self.assigned_to.setPlaceholderText(
            "Assigned user (leave blank if spare)")
        layout.addRow(lbl("Assigned To:"), self.assigned_to)

        self.department = QtWidgets.QLineEdit()
        self.department.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Department:"), self.department)

        self.purchase_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.purchase_date.setCalendarPopup(True)
        self.purchase_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Purchase Date:"), self.purchase_date)

        self.warranty_exp = QtWidgets.QDateEdit(
            QtCore.QDate.currentDate().addYears(3))
        self.warranty_exp.setCalendarPopup(True)
        self.warranty_exp.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Warranty Exp:"), self.warranty_exp)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("active", "spare", "repair", "retired", "lost"):
            self.status_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Notes:"), self.notes)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        tag = self.asset_tag.text().strip()
        if not tag:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Asset tag is required.")
            return
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO it_asset (asset_tag, asset_type, make, model, "
                "serial_number,"
                " assigned_to, department, purchase_date, warranty_exp, "
                "status, notes)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (tag, self.asset_type.currentData(),
                 self.make.text().strip(), self.model.text().strip(),
                 self.serial.text().strip(), self.assigned_to.text().strip(),
                 self.department.text().strip(),
                 self.purchase_date.date().toString("yyyy-MM-dd"),
                 self.warranty_exp.date().toString("yyyy-MM-dd"),
                 self.status_combo.currentData(),
                 self.notes.text().strip())
            )
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"Asset tag '{tag}' already exists.")
            conn.close()
            return
        conn.close()
        self.accept()


# ── Embeddable Widget ───────────────────────────────────────────────────

class ITSupportWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._ticket_row_ids = []
        self._selected_ticket_id = None
        self._asset_row_ids = []
        self._build_ui()
        init_db()
        self._refresh_tickets()
        self._refresh_assets()

    def _build_ui(self):
        self._tabs = ButtonNav()
        self._tabs.setStyleSheet(
            "QTabWidget::pane{border:1px solid black;}"
            "QTabBar::tab{background:white;border:2px solid black;padding:6px "
            "18px;"
            "border-bottom:none;border-radius:4px 4px 0 0;}"
            "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"  # noqa: E501
            "QTabBar::tab:hover{background:rgb(85,255,255);}"
        )
        self._tabs.currentChanged.connect(self._on_tab_changed)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self._tabs)
        self._build_tickets_tab()
        self._build_assets_tab()

    def _on_tab_changed(self, index):
        if index == 0:
            self._refresh_tickets()
        elif index == 1:
            self._refresh_assets()

    # ── Tickets tab ─────────────────────────────────────────────────────────

    def _build_tickets_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()

        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.tkt_status_filter = QtWidgets.QComboBox()
        self.tkt_status_filter.setStyleSheet(COMBO_STYLE)
        self.tkt_status_filter.addItem("Open & In Progress", "open")
        self.tkt_status_filter.addItem("In Progress only", "in_progress")
        self.tkt_status_filter.addItem("On Hold", "on_hold")
        self.tkt_status_filter.addItem("Resolved", "resolved")
        self.tkt_status_filter.addItem("Closed", "closed")
        self.tkt_status_filter.addItem("All", None)
        self.tkt_status_filter.currentIndexChanged.connect(
            self._refresh_tickets)
        fr.addWidget(self.tkt_status_filter)

        fr.addSpacing(10)
        lbl_p = QtWidgets.QLabel("Priority:")
        lbl_p.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_p)
        self.tkt_pri_filter = QtWidgets.QComboBox()
        self.tkt_pri_filter.setStyleSheet(COMBO_STYLE)
        self.tkt_pri_filter.addItem("(all)", None)
        for s in ("low", "medium", "high", "critical"):
            self.tkt_pri_filter.addItem(s.capitalize(), s)
        self.tkt_pri_filter.currentIndexChanged.connect(self._refresh_tickets)
        fr.addWidget(self.tkt_pri_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self.tkt_search = QtWidgets.QLineEdit()
        self.tkt_search.setStyleSheet(INPUT_STYLE)
        self.tkt_search.setFixedWidth(160)
        self.tkt_search.returnPressed.connect(self._refresh_tickets)
        fr.addWidget(self.tkt_search)
        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_tkt_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.tkt_table = QtWidgets.QTableWidget()
        self.tkt_table.setColumnCount(9)
        self.tkt_table.setHorizontalHeaderLabels(
            ["Ticket #", "Requester", "Department", "Issue Type",
             "Priority", "Assigned To", "Due Date", "Status", "Created By"]
        )
        hh = self.tkt_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6, 7, 8):
            hh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tkt_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tkt_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tkt_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tkt_table.setAlternatingRowColors(True)
        self.tkt_table.verticalHeader().setVisible(False)
        self.tkt_table.clicked.connect(self._on_ticket_clicked)
        splitter.addWidget(self.tkt_table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Description / Notes for Selected Ticket")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.tkt_detail_text = QtWidgets.QPlainTextEdit()
        self.tkt_detail_text.setReadOnly(True)
        self.tkt_detail_text.setStyleSheet(
            "QPlainTextEdit{background-color: white; border: 1px solid black;}")  # noqa: E501
        dv.addWidget(self.tkt_detail_text)
        splitter.addWidget(detail_w)
        splitter.setSizes([420, 160])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Ticket",      self._on_new_ticket),
            ("Assign / Start",
    lambda: self._set_tkt_status("in_progress",
     "Mark as In Progress?")),
            ("Mark On Hold",    lambda: self._set_tkt_status(
                "on_hold",     "Put On Hold?")),
            ("Mark Resolved",   lambda: self._set_tkt_status(
                "resolved",    "Mark as Resolved?")),
            ("Close Ticket",    lambda: self._set_tkt_status(
                "closed",      "Close this ticket?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Support Tickets")

    def _refresh_tickets(self):
        status_val = self.tkt_status_filter.currentData()
        priority = self.tkt_pri_filter.currentData()
        term = self.tkt_search.text().strip()

        base = "SELECT * FROM it_ticket"
        conds, params = [], []
        if status_val == "open":
            conds.append("status IN ('open','in_progress')")
        elif status_val:
            conds.append("status = ?")
            params.append(status_val)
        if priority:
            conds.append("priority = ?")
            params.append(priority)
        if term:
            conds.append(
                "(ticket_number LIKE ? OR requester LIKE ? OR description "
                "LIKE ?)")
            params += [f"%{term}%", f"%{term}%", f"%{term}%"]
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        conn = get_db()
        try:
            rows = conn.execute(
                base + where + " ORDER BY submitted_date DESC, ticket_number "
                               "DESC", params
            ).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.tkt_table.setRowCount(0)
        self._ticket_row_ids = []
        for row in rows:
            r = self.tkt_table.rowCount()
            self.tkt_table.insertRow(r)
            self._ticket_row_ids.append(row["id"])
            self.tkt_table.setItem(r, 0, _ro(row["ticket_number"]))
            self.tkt_table.setItem(r, 1, _ro(row["requester"] or ""))
            self.tkt_table.setItem(r, 2, _ro(row["department"] or ""))
            self.tkt_table.setItem(r, 3, _ro(row["issue_type"] or ""))
            self.tkt_table.setItem(r, 4, _ro(row["priority"].capitalize()))
            self.tkt_table.setItem(r, 5, _ro(row["assigned_to"] or ""))
            self.tkt_table.setItem(r, 6, _ro(row["due_date"] or ""))
            self.tkt_table.setItem(
    r, 7, _ro(
        row["status"].replace(
            "_", " ").capitalize()))
            self.tkt_table.setItem(r, 8, _ro(row["created_by"] or ""))
            bg = QtGui.QColor(TICKET_COLORS.get(row["status"], "#ffffff"))
            for col in range(9):
                self.tkt_table.item(r, col).setBackground(bg)
            if row["status"] not in ("resolved", "closed"):
                pc = PRIORITY_COLORS.get(row["priority"])
                if pc:
                    self.tkt_table.item(r, 4).setBackground(pc)

        self._selected_ticket_id = None
        self.tkt_detail_text.clear()

    def _on_tkt_show_all(self):
        self.tkt_search.clear()
        self.tkt_status_filter.blockSignals(True)
        self.tkt_status_filter.setCurrentIndex(
            self.tkt_status_filter.count() - 1)
        self.tkt_status_filter.blockSignals(False)
        self.tkt_pri_filter.blockSignals(True)
        self.tkt_pri_filter.setCurrentIndex(0)
        self.tkt_pri_filter.blockSignals(False)
        self._refresh_tickets()

    def _on_ticket_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._ticket_row_ids):
            return
        self._selected_ticket_id = self._ticket_row_ids[row]
        conn = get_db()
        rec = conn.execute(
            "SELECT * FROM it_ticket WHERE id = ?", (self._selected_ticket_id,)
        ).fetchone()
        conn.close()
        if not rec:
            return
        lines = [
            f"Ticket:      {rec['ticket_number']}",
            f"Requester:   {
    rec['requester'] or '—'}  |  Dept: {
        rec['department'] or '—'}",
            f"Issue Type:  {
    rec['issue_type'] or '—'}  |  Priority: {
        rec['priority'].capitalize()}",
            f"Assigned To: {rec['assigned_to'] or '—'}",
            f"Submitted:   {
    rec['submitted_date'] or '—'}  |  Due: {
        rec['due_date'] or '—'}",
            "",
            "Description:",
            rec["description"] or "",
        ]
        if rec["notes"]:
            lines += ["", "Notes:", rec["notes"]]
        self.tkt_detail_text.setPlainText("\n".join(lines))

    def _on_new_ticket(self):
        dlg = NewTicketDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_tickets()

    def _set_tkt_status(self, new_status, msg):
        if self._selected_ticket_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a ticket first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            extra = ""
            params = [new_status]
            if new_status == "resolved":
                extra = ", resolved_date = ?"
                params.append(
    QtCore.QDate.currentDate().toString("yyyy-MM-dd"))
            params.append(self._selected_ticket_id)
            conn.execute(
    f"UPDATE it_ticket SET status = ?{extra} WHERE id = ?",
     params)
            conn.commit()
            conn.close()
            self._refresh_tickets()

    # ── Assets tab ──────────────────────────────────────────────────────────

    def _build_assets_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.asset_status_filter = QtWidgets.QComboBox()
        self.asset_status_filter.setStyleSheet(COMBO_STYLE)
        self.asset_status_filter.addItem("Active", "active")
        self.asset_status_filter.addItem("Spare", "spare")
        self.asset_status_filter.addItem("In Repair", "repair")
        self.asset_status_filter.addItem("Retired", "retired")
        self.asset_status_filter.addItem("All", None)
        self.asset_status_filter.currentIndexChanged.connect(
            self._refresh_assets)
        fr.addWidget(self.asset_status_filter)

        fr.addSpacing(10)
        lbl_t = QtWidgets.QLabel("Type:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.asset_type_filter = QtWidgets.QComboBox()
        self.asset_type_filter.setStyleSheet(COMBO_STYLE)
        self.asset_type_filter.addItem("(all)", None)
        for t in ("Desktop", "Laptop", "Monitor", "Server", "Printer", "Phone",
                  "Tablet", "Switch", "Router", "UPS", "Other"):
            self.asset_type_filter.addItem(t, t)
        self.asset_type_filter.currentIndexChanged.connect(
            self._refresh_assets)
        fr.addWidget(self.asset_type_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self.asset_search = QtWidgets.QLineEdit()
        self.asset_search.setStyleSheet(INPUT_STYLE)
        self.asset_search.setFixedWidth(160)
        self.asset_search.returnPressed.connect(self._refresh_assets)
        fr.addWidget(self.asset_search)
        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_asset_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        self.asset_table = QtWidgets.QTableWidget()
        self.asset_table.setColumnCount(9)
        self.asset_table.setHorizontalHeaderLabels(
            ["Asset Tag", "Type", "Make", "Model", "Serial #",
             "Assigned To", "Department", "Warranty Exp", "Status"]
        )
        hh = self.asset_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 4, 5, 6, 7, 8):
            hh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.asset_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.asset_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.asset_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.asset_table.setAlternatingRowColors(True)
        self.asset_table.verticalHeader().setVisible(False)
        v.addWidget(self.asset_table, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add Asset",      self._on_new_asset),
            ("Mark Spare",     lambda: self._set_asset_status(
                "spare",   "Mark as Spare?")),
            ("Send to Repair", lambda: self._set_asset_status(
                "repair",  "Send to Repair?")),
            ("Mark Retired",   lambda: self._set_asset_status(
                "retired", "Retire this asset?")),
            ("Mark Active",    lambda: self._set_asset_status(
                "active",  "Mark as Active?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Assets")

    def _refresh_assets(self):
        status_val = self.asset_status_filter.currentData()
        asset_type = self.asset_type_filter.currentData()
        term = self.asset_search.text().strip()

        base = "SELECT * FROM it_asset"
        conds, params = [], []
        if status_val:
            conds.append("status = ?")
            params.append(status_val)
        if asset_type:
            conds.append("asset_type = ?")
            params.append(asset_type)
        if term:
            conds.append("(asset_tag LIKE ? OR make LIKE ? OR model LIKE ?"
                         " OR assigned_to LIKE ? OR serial_number LIKE ?)")
            params += [f"%{term}%"] * 5
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        conn = get_db()
        try:
            rows = conn.execute(
                base + where + " ORDER BY asset_type, asset_tag", params
            ).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.asset_table.setRowCount(0)
        self._asset_row_ids = []
        for row in rows:
            r = self.asset_table.rowCount()
            self.asset_table.insertRow(r)
            self._asset_row_ids.append(row["id"])
            self.asset_table.setItem(r, 0, _ro(row["asset_tag"]))
            self.asset_table.setItem(r, 1, _ro(row["asset_type"] or ""))
            self.asset_table.setItem(r, 2, _ro(row["make"] or ""))
            self.asset_table.setItem(r, 3, _ro(row["model"] or ""))
            self.asset_table.setItem(r, 4, _ro(row["serial_number"] or ""))
            self.asset_table.setItem(r, 5, _ro(row["assigned_to"] or ""))
            self.asset_table.setItem(r, 6, _ro(row["department"] or ""))
            self.asset_table.setItem(r, 7, _ro(row["warranty_exp"] or ""))
            self.asset_table.setItem(r, 8, _ro(row["status"].capitalize()))
            bg = QtGui.QColor(
    ASSET_STATUS_COLORS.get(
        row["status"], "#ffffff"))
            for col in range(9):
                self.asset_table.item(r, col).setBackground(bg)

    def _on_asset_show_all(self):
        self.asset_search.clear()
        self.asset_status_filter.blockSignals(True)
        self.asset_status_filter.setCurrentIndex(4)
        self.asset_status_filter.blockSignals(False)
        self.asset_type_filter.blockSignals(True)
        self.asset_type_filter.setCurrentIndex(0)
        self.asset_type_filter.blockSignals(False)
        self._refresh_assets()

    def _on_new_asset(self):
        dlg = NewAssetDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_assets()

    def _set_asset_status(self, new_status, msg):
        row = self.asset_table.currentRow()
        if row < 0 or row >= len(self._asset_row_ids):
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an asset first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE it_asset SET status = ? WHERE id = ?",
                         (new_status, self._asset_row_ids[row]))
            conn.commit()
            conn.close()
            self._refresh_assets()


# ── Standalone Window ───────────────────────────────────────────────────

class ITSupportMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = f"IT Support — {email}" if email else "IT Support"
        self.setWindowTitle(title)
        self.resize(1020, 680)
        _apply_blue_palette(self)
        from .it_calls_reports import ITSupportReportsWidget
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(0)
        tabs = ButtonNav()
        tabs.setStyleSheet(
            "QTabWidget::pane{border:1px solid black;}"
            "QTabBar::tab{background:white;border:2px solid black;padding:6px "
            "18px;"
            "border-bottom:none;border-radius:4px 4px 0 0;}"
            "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"  # noqa: E501
            "QTabBar::tab:hover{background:rgb(85,255,255);}"
        )
        tabs.addTab(ITSupportWidget(), "Support Calls")
        tabs.addTab(ITSupportReportsWidget(), "Reports")
        v.addWidget(tabs)


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = ITSupportMenu()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
