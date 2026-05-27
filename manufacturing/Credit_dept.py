import sys
import sqlite3
from db_pg import get_db
import os
import csv
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets


BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton%(hover)s{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE = "QLineEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}"
COMBO_STYLE = "QComboBox{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}QComboBox QAbstractItemView{background-color%(white)s;}"
DATE_STYLE = "QDateEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 4px;}"
SPIN_STYLE = "QDoubleSpinBox{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 4px;}"
TEXT_STYLE = "QTextEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}"
LABEL_STYLE = "color%(white)s;font-size:13px;"
TAB_STYLE = (
    "QTabWidget:%(pane)s{border:1px solid black;}"
    "QTabBar:%(tab)s{background%(white)s; border:2px solid black; padding:6px 18px;"
    " border-bottom%(none)s; border-radius:4px 4px 0 0;}"
    "QTabBar:%(tab)s%(selected)s{background%(rgb)s(85,255,255); font-weight%(bold)s;}"
    "QTabBar:%(tab)s%(hover)s{background%(rgb)s(85,255,255);}"
)

CREDIT_STATUS_COLORS = {
    "good": QtGui.QColor(212, 237, 218),
    "hold": QtGui.QColor(255, 243, 205),
    "suspended": QtGui.QColor(248, 215, 218),
    "closed": QtGui.QColor(220, 220, 220),
}

APP_STATUS_COLORS = {
    "pending": QtGui.QColor(255, 243, 205),
    "approved": QtGui.QColor(212, 237, 218),
    "denied": QtGui.QColor(248, 215, 218),
}

OVERDUE_COLORS = [
    (30, QtGui.QColor(255, 243, 205)),   # 1–30 days — yellow
    (60, QtGui.QColor(255, 224, 178)),   # 31–60 days — orange-ish
    (90, QtGui.QColor(248, 215, 218)),   # 61–90 days — light red
    (999, QtGui.QColor(220, 53, 69, 80)),  # 90+ days  — red
]


def get_db():
    conn = get_db()
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credit_account (
            id              SERIAL PRIMARY KEY,
            customer_id     INTEGER NOT NULL UNIQUE REFERENCES customer(id),
            credit_limit    REAL    NOT NULL DEFAULT 0.0,
            status          TEXT    NOT NULL DEFAULT 'good',
            terms           TEXT,
            opened_date     TEXT    NOT NULL,
            notes           TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credit_application (
            id               SERIAL PRIMARY KEY,
            customer_id      INTEGER NOT NULL REFERENCES customer(id),
            applied_date     TEXT    NOT NULL,
            requested_limit  REAL    NOT NULL DEFAULT 0.0,
            approved_limit   REAL,
            status           TEXT    NOT NULL DEFAULT 'pending',
            reviewed_by      TEXT,
            review_date      TEXT,
            notes            TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credit_limit_history (
            id           SERIAL PRIMARY KEY,
            customer_id  INTEGER NOT NULL REFERENCES customer(id),
            changed_date TEXT    NOT NULL,
            old_limit    REAL,
            new_limit    REAL    NOT NULL,
            old_status   TEXT,
            new_status   TEXT,
            changed_by   TEXT,
            reason       TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collection_activity (
            id              SERIAL PRIMARY KEY,
            customer_id     INTEGER NOT NULL REFERENCES customer(id),
            activity_date   TEXT    NOT NULL DEFAULT (date('now')),
            activity_type   TEXT    NOT NULL DEFAULT 'Call',
            contact_name    TEXT    DEFAULT '',
            notes           TEXT    DEFAULT '',
            amount_promised REAL    DEFAULT NULL,
            promise_date    TEXT    DEFAULT NULL,
            follow_up_date  TEXT    DEFAULT NULL,
            status          TEXT    NOT NULL DEFAULT 'Open',
            created_by      TEXT    DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


def _apply_blue_palette(widget):
    pal = widget.palette()
    for g in (QtGui.QPalette.ColorGroup.Active,
              QtGui.QPalette.ColorGroup.Inactive,
              QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(g, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(g, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _money(v):
    return f"${v:,.2f}"


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter):
    item = QtWidgets.QTableWidgetItem(str(text))
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(align)
    return item


def _customer_display(row):
    company = (row["company_name"] or "").strip()
    contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    return company if company else contact


def _ar_balance(customer_id):
    """Return total open AR balance for a customer."""
    conn = get_db()
    result = conn.execute("""
        SELECT COALESCE(SUM(ai.amount - COALESCE(p.paid, 0)), 0)
        FROM ar_invoice ai
        LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM ar_payment GROUP BY invoice_id) p
            ON p.invoice_id = ai.id
        WHERE ai.customer_id = %s AND ai.status IN ('open', 'partial')
    """, (customer_id,)).fetchone()[0]
    conn.close()
    return result


def _overdue_color(days: int) -> QtGui.QColor:
    for threshold, color in OVERDUE_COLORS:
        if days <= threshold:
            return color
    return OVERDUE_COLORS[-1][1]


def _export_table_to_csv(table: QtWidgets.QTableWidget, parent=None):
    """Open a Save dialog and export a QTableWidget to CSV."""
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent, "Export to CSV", "", "CSV Files (*.csv)")
    if not path:
        return
    headers = [table.horizontalHeaderItem(c).text()
               for c in range(table.columnCount())]
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in range(table.rowCount()):
                row_data = []
                for c in range(table.columnCount()):
                    item = table.item(r, c)
                    row_data.append(item.text() if item else "")
                writer.writerow(row_data)
        QtWidgets.QMessageBox.information(parent, "Export Complete",
                                          f"Exported {table.rowCount()} rows to:\n{path}")
    except OSError as e:
        QtWidgets.QMessageBox.warning(parent, "Export Failed", str(e))


# ── Dialogs ────────────────────────────────────────────────────────────────

class NewApplicationDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, preselect_customer_id=None):
        super().__init__(parent)
        self.setWindowTitle("New Credit Application")
        self.setFixedSize(500, 340)
        _apply_blue_palette(self)
        self._preselect = preselect_customer_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("New Credit Application")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color%(white)s;font-size:15px;font-weight%(bold)s;")
        layout.addWidget(title)

        def row(lbl_text, widget, lbl_w=130):
            r = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(lbl_text)
            lbl.setFixedWidth(lbl_w)
            lbl.setStyleSheet(LABEL_STYLE)
            r.addWidget(lbl)
            r.addWidget(widget)
            return r

        self.cust_combo = QtWidgets.QComboBox()
        self.cust_combo.setStyleSheet(COMBO_STYLE)
        conn = get_db()
        customers = conn.execute(
            "SELECT id, first_name, last_name, company_name FROM customer "
            "ORDER BY company_name, last_name, first_name"
        ).fetchall()
        conn.close()
        for c in customers:
            self.cust_combo.addItem(_customer_display(c), c["id"])
        if self._preselect:
            idx = self.cust_combo.findData(self._preselect)
            if idx >= 0:
                self.cust_combo.setCurrentIndex(idx)
        layout.addLayout(row("Customer:", self.cust_combo))

        self.app_date = QtWidgets.QDateEdit()
        self.app_date.setStyleSheet(DATE_STYLE)
        self.app_date.setCalendarPopup(True)
        self.app_date.setDisplayFormat("MM/dd/yyyy")
        self.app_date.setDate(QtCore.QDate.currentDate())
        layout.addLayout(row("Application Date:", self.app_date))

        self.req_limit = QtWidgets.QDoubleSpinBox()
        self.req_limit.setStyleSheet(SPIN_STYLE)
        self.req_limit.setRange(0, 9999999)
        self.req_limit.setDecimals(2)
        self.req_limit.setPrefix("$ ")
        layout.addLayout(row("Requested Limit:", self.req_limit))

        self.notes = QtWidgets.QTextEdit()
        self.notes.setStyleSheet(TEXT_STYLE)
        self.notes.setFixedHeight(70)
        self.notes.setPlaceholderText("Notes / reason for application...")
        layout.addLayout(row("Notes:", self.notes))

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Submit", self._on_save), ("Cancel", self.reject)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

    def _on_save(self):
        if self.cust_combo.currentData() is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Select a customer.")
            return
        if self.req_limit.value() <= 0:
            QtWidgets.QMessageBox.warning(self, "Error", "Requested limit must be greater than zero.")
            return
        conn = get_db()
        conn.execute("""
            INSERT INTO credit_application (customer_id, applied_date, requested_limit, notes)
            VALUES (%s, %s, %s, %s)
        """, (self.cust_combo.currentData(),
              self.app_date.date().toString("yyyy-MM-dd"),
              self.req_limit.value(),
              self.notes.toPlainText().strip() or None))
        conn.commit()
        conn.close()
        self.accept()


class ReviewApplicationDialog(QtWidgets.QDialog):
    def __init__(self, app_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Application")
        self.setFixedSize(500, 380)
        self._app_id = app_id
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        conn = get_db()
        app = conn.execute("""
            SELECT ca.*, c.first_name, c.last_name, c.company_name
            FROM credit_application ca JOIN customer c ON c.id = ca.customer_id
            WHERE ca.id = %s
        """, (self._app_id,)).fetchone()
        conn.close()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)

        info = QtWidgets.QLabel(
            f"Customer: {_customer_display(app)}\n"
            f"Applied: {app['applied_date']}   Requested: {_money(app['requested_limit'])}"
        )
        info.setStyleSheet("color%(white)s;font-size:13px;")
        info.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        def row(lbl_text, widget, lbl_w=130):
            r = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(lbl_text)
            lbl.setFixedWidth(lbl_w)
            lbl.setStyleSheet(LABEL_STYLE)
            r.addWidget(lbl)
            r.addWidget(widget)
            return r

        self.decision = QtWidgets.QComboBox()
        self.decision.setStyleSheet(COMBO_STYLE)
        self.decision.addItems(["approved", "denied"])
        layout.addLayout(row("Decision:", self.decision))

        self.approved_limit = QtWidgets.QDoubleSpinBox()
        self.approved_limit.setStyleSheet(SPIN_STYLE)
        self.approved_limit.setRange(0, 9999999)
        self.approved_limit.setDecimals(2)
        self.approved_limit.setPrefix("$ ")
        self.approved_limit.setValue(app["requested_limit"])
        layout.addLayout(row("Approved Limit:", self.approved_limit))

        self.reviewer = QtWidgets.QLineEdit()
        self.reviewer.setStyleSheet(INPUT_STYLE)
        self.reviewer.setPlaceholderText("Reviewer name")
        layout.addLayout(row("Reviewed By:", self.reviewer))

        self.review_date = QtWidgets.QDateEdit()
        self.review_date.setStyleSheet(DATE_STYLE)
        self.review_date.setCalendarPopup(True)
        self.review_date.setDisplayFormat("MM/dd/yyyy")
        self.review_date.setDate(QtCore.QDate.currentDate())
        layout.addLayout(row("Review Date:", self.review_date))

        self.notes = QtWidgets.QTextEdit()
        self.notes.setStyleSheet(TEXT_STYLE)
        self.notes.setFixedHeight(70)
        self.notes.setPlaceholderText("Review notes...")
        if app["notes"]:
            self.notes.setPlainText(app["notes"])
        layout.addLayout(row("Notes:", self.notes))

        self.auto_update_chk = QtWidgets.QCheckBox("Update / create credit account automatically")
        self.auto_update_chk.setStyleSheet("color%(white)s;font-size:12px;")
        self.auto_update_chk.setChecked(True)
        layout.addWidget(self.auto_update_chk)

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Save Decision", self._on_save), ("Cancel", self.reject)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

    def _on_save(self):
        decision = self.decision.currentText()
        approved_limit = self.approved_limit.value() if decision == "approved" else None
        reviewer = self.reviewer.text().strip() or None
        review_date = self.review_date.date().toString("yyyy-MM-dd")
        notes = self.notes.toPlainText().strip() or None

        conn = get_db()
        conn.execute("""
            UPDATE credit_application
            SET status=%s, approved_limit=%s, reviewed_by=%s, review_date=%s, notes=%s
            WHERE id=%s
        """, (decision, approved_limit, reviewer, review_date, notes, self._app_id))

        if decision == "approved" and self.auto_update_chk.isChecked() and approved_limit:
            app = conn.execute(
                "SELECT customer_id FROM credit_application WHERE id=%s", (self._app_id,)
            ).fetchone()
            cid = app["customer_id"]
            existing = conn.execute(
                "SELECT id, credit_limit, status FROM credit_account WHERE customer_id=%s", (cid,)
            ).fetchone()
            if existing:
                old_limit = existing["credit_limit"]
                old_status = existing["status"]
                conn.execute("""
                    UPDATE credit_account SET credit_limit=%s, status='good' WHERE customer_id=%s
                """, (approved_limit, cid))
            else:
                old_limit = old_status = None
                conn.execute("""
                    INSERT INTO credit_account (customer_id, credit_limit, status, opened_date)
                    VALUES (%s, %s, 'good', %s)
                """, (cid, approved_limit, review_date))
            # log the limit change
            conn.execute("""
                INSERT INTO credit_limit_history
                    (customer_id, changed_date, old_limit, new_limit, old_status, new_status, changed_by, reason)
                VALUES (%s, %s, %s, %s, %s, 'good', %s, 'Application approved')
            """, (cid, review_date, old_limit, approved_limit, old_status, reviewer))

        conn.commit()
        conn.close()
        self.accept()


# ── Main window ────────────────────────────────────────────────────────────

ACTIVITY_TYPES = ["Call", "Email", "Letter", "Visit", "Payment Arrangement", "Other"]
ACTIVITY_STATUSES = ["Open", "Pending", "Resolved", "Escalated"]

RISK_COLORS = {
    "Low": QtGui.QColor(212, 237, 218),
    "Medium": QtGui.QColor(255, 243, 205),
    "High": QtGui.QColor(255, 200, 150),
    "Critical": QtGui.QColor(248, 215, 218),
}

_TAB_KEYS = {'credit': 0, 'aging': 5, 'collections': 6, 'risk': 7}


class CreditDeptWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, initial_tab=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._acct_row_ids = []
        self._app_row_ids = []
        self._hist_row_ids = []
        self._overdue_cust_ids = []
        self._build_ui()
        self._load_accounts()
        self._load_applications()
        self._refresh_summary()
        self._refresh_overdue()
        self._refresh_limit_history()
        # Run auto-hold silently on startup
        held = self._run_auto_hold(silent=True)
        if held:
            self._load_accounts()
            self._refresh_summary()
        if initial_tab in _TAB_KEYS:
            self.tabs.setCurrentIndex(_TAB_KEYS[initial_tab])

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        outer.addWidget(self.tabs)
        self.tabs.addTab(self._build_accounts_tab(), "Credit Accounts")
        self.tabs.addTab(self._build_applications_tab(), "Applications")
        self.tabs.addTab(self._build_overdue_tab(), "Overdue Report")
        self.tabs.addTab(self._build_limit_history_tab(), "Limit History")
        self.tabs.addTab(self._build_summary_tab(), "Summary")
        self.tabs.addTab(self._build_aging_tab(), "A/R Aging")
        self.tabs.addTab(self._build_collections_tab(), "Collections")
        self.tabs.addTab(self._build_risk_tab(), "Risk Scoring")
        self.tabs.currentChanged.connect(self._on_tab_change)

    # ── Credit Accounts tab ────────────────────────────────────────────────

    def _build_accounts_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.acct_table = QtWidgets.QTableWidget()
        self.acct_table.setColumnCount(8)
        self.acct_table.setHorizontalHeaderLabels(
            ["Customer", "Credit Limit", "AR Balance", "Available", "Status", "Terms", "Opened", "Alert"])
        hh = self.acct_table.horizontalHeader()
        hh.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5, 6, 7):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.acct_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.acct_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.acct_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.acct_table.setAlternatingRowColors(True)
        self.acct_table.verticalHeader().setVisible(False)
        self.acct_table.clicked.connect(self._on_acct_row_clicked)
        layout.addWidget(self.acct_table, stretch=1)

        sr = QtWidgets.QHBoxLayout()
        sl = QtWidgets.QLabel("Search:")
        sl.setStyleSheet(LABEL_STYLE)
        sr.addWidget(sl)
        self.acct_search = QtWidgets.QLineEdit()
        self.acct_search.setStyleSheet(INPUT_STYLE)
        self.acct_search.setFixedWidth(220)
        self.acct_search.setPlaceholderText("Company or customer name")
        self.acct_search.returnPressed.connect(self._on_acct_search)
        sr.addWidget(self.acct_search)

        self.acct_status_filter = QtWidgets.QComboBox()
        self.acct_status_filter.setStyleSheet(COMBO_STYLE)
        self.acct_status_filter.addItems(["(all status)", "good", "hold", "suspended", "closed"])
        sr.addWidget(self.acct_status_filter)

        for t, fn in (("Search", self._on_acct_search), ("Show All", self._load_accounts)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            sr.addWidget(b)

        auto_hold_btn = QtWidgets.QPushButton("Run Auto-Hold Check")
        auto_hold_btn.setStyleSheet(BUTTON_STYLE)
        auto_hold_btn.setFixedHeight(30)
        auto_hold_btn.clicked.connect(self._on_auto_hold_clicked)
        sr.addWidget(auto_hold_btn)
        sr.addStretch()
        layout.addLayout(sr)

        # Edit form
        fg = QtWidgets.QGroupBox("Credit Account Record")
        fg.setStyleSheet(
            "QGroupBox{color%(white)s;font-weight%(bold)s;border:1px solid white;margin-top:8px;}"
            "QGroupBox:%(title)s{subcontrol-origin%(margin)s;left:10px;}")
        grid = QtWidgets.QGridLayout(fg)
        grid.setSpacing(6)

        def lbl(t):
            lbl = QtWidgets.QLabel(t)
            lbl.setStyleSheet(LABEL_STYLE)
            return lbl

        def inp(ph=""):
            e = QtWidgets.QLineEdit()
            e.setStyleSheet(INPUT_STYLE)
            e.setPlaceholderText(ph)
            return e

        self.af_cust_combo = QtWidgets.QComboBox()
        self.af_cust_combo.setStyleSheet(COMBO_STYLE)
        self.af_cust_combo.setMinimumWidth(220)
        self._refresh_customer_combo(self.af_cust_combo)

        self.af_limit = QtWidgets.QDoubleSpinBox()
        self.af_limit.setStyleSheet(SPIN_STYLE)
        self.af_limit.setRange(0, 9999999)
        self.af_limit.setDecimals(2)
        self.af_limit.setPrefix("$ ")

        self.af_status = QtWidgets.QComboBox()
        self.af_status.setStyleSheet(COMBO_STYLE)
        self.af_status.addItems(["good", "hold", "suspended", "closed"])

        self.af_terms = inp("Net 30, Net 60, etc.")
        self.af_opened = QtWidgets.QDateEdit()
        self.af_opened.setStyleSheet(DATE_STYLE)
        self.af_opened.setCalendarPopup(True)
        self.af_opened.setDisplayFormat("MM/dd/yyyy")
        self.af_opened.setDate(QtCore.QDate.currentDate())
        self.af_notes = inp("Notes")
        self.af_changed_by = inp("Your name (for history log)")
        self.af_reason = inp("Reason for change (for history log)")

        grid.addWidget(lbl("Customer:"), 0, 0)
        grid.addWidget(self.af_cust_combo, 0, 1)
        grid.addWidget(lbl("Credit Limit:"), 0, 2)
        grid.addWidget(self.af_limit, 0, 3)
        grid.addWidget(lbl("Status:"), 0, 4)
        grid.addWidget(self.af_status, 0, 5)
        grid.addWidget(lbl("Terms:"), 1, 0)
        grid.addWidget(self.af_terms, 1, 1)
        grid.addWidget(lbl("Opened Date:"), 1, 2)
        grid.addWidget(self.af_opened, 1, 3)
        grid.addWidget(lbl("Notes:"), 1, 4)
        grid.addWidget(self.af_notes, 1, 5)
        grid.addWidget(lbl("Changed By:"), 2, 0)
        grid.addWidget(self.af_changed_by, 2, 1)
        grid.addWidget(lbl("Reason:"), 2, 2)
        grid.addWidget(self.af_reason, 2, 3, 1, 3)
        layout.addWidget(fg)

        br = QtWidgets.QHBoxLayout()
        for t, fn in (("Add New", self._on_acct_add), ("Update Selected", self._on_acct_update),
                      ("Delete Selected", self._on_acct_delete), ("Clear", self._acct_clear)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(34)
            b.clicked.connect(fn)
            br.addWidget(b)
        br.addStretch()
        layout.addLayout(br)
        return w

    # ── Applications tab ───────────────────────────────────────────────────

    def _build_applications_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        fr.setSpacing(8)

        def fl(t):
            lbl = QtWidgets.QLabel(t)
            lbl.setStyleSheet(LABEL_STYLE)
            return lbl

        self.app_status_filter = QtWidgets.QComboBox()
        self.app_status_filter.setStyleSheet(COMBO_STYLE)
        self.app_status_filter.addItems(["(all status)", "pending", "approved", "denied"])

        self.app_from = QtWidgets.QDateEdit()
        self.app_from.setStyleSheet(DATE_STYLE)
        self.app_from.setCalendarPopup(True)
        self.app_from.setDisplayFormat("MM/dd/yyyy")
        self.app_from.setDate(QtCore.QDate.currentDate().addDays(-180))

        self.app_to = QtWidgets.QDateEdit()
        self.app_to.setStyleSheet(DATE_STYLE)
        self.app_to.setCalendarPopup(True)
        self.app_to.setDisplayFormat("MM/dd/yyyy")
        self.app_to.setDate(QtCore.QDate.currentDate())

        fr.addWidget(fl("Status:"))
        fr.addWidget(self.app_status_filter)
        fr.addWidget(fl("From:"))
        fr.addWidget(self.app_from)
        fr.addWidget(fl("To:"))
        fr.addWidget(self.app_to)
        for t, fn in (("Apply", self._load_applications), ("Show All", self._app_show_all)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            fr.addWidget(b)
        fr.addStretch()
        layout.addLayout(fr)

        self.app_table = QtWidgets.QTableWidget()
        self.app_table.setColumnCount(8)
        self.app_table.setHorizontalHeaderLabels([
            "Customer", "Applied Date", "Requested", "Approved",
            "Status", "Reviewed By", "Review Date", "Notes"
        ])
        hh = self.app_table.horizontalHeader()
        hh.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5, 6):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.app_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.app_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.app_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.app_table.setAlternatingRowColors(True)
        self.app_table.verticalHeader().setVisible(False)
        layout.addWidget(self.app_table, stretch=1)

        ar = QtWidgets.QHBoxLayout()
        for t, fn in (("New Application", self._on_new_application),
                      ("Review Selected", self._on_review_application),
                      ("Delete Selected", self._on_delete_application)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(fn)
            ar.addWidget(b)
        ar.addStretch()
        layout.addLayout(ar)
        return w

    # ── Overdue Report tab ─────────────────────────────────────────────────

    def _build_overdue_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Overdue Invoices Report")
        title.setStyleSheet("color%(white)s;font-size:14px;font-weight%(bold)s;")
        hdr.addWidget(title)
        ref_btn = QtWidgets.QPushButton("Refresh")
        ref_btn.setStyleSheet(BUTTON_STYLE)
        ref_btn.setFixedHeight(30)
        ref_btn.clicked.connect(self._refresh_overdue)
        hdr.addWidget(ref_btn)
        exp_btn = QtWidgets.QPushButton("Export CSV")
        exp_btn.setStyleSheet(BUTTON_STYLE)
        exp_btn.setFixedHeight(30)
        exp_btn.clicked.connect(lambda: _export_table_to_csv(self.overdue_table, self))
        hdr.addWidget(exp_btn)
        hdr.addStretch()
        layout.addLayout(hdr)

        legend = QtWidgets.QLabel(
            "  Legend:  1–30 days ■   31–60 days ■   61–90 days ■   91+ days ■")
        legend.setStyleSheet("color%(white)s;font-size:11px;")
        layout.addWidget(legend)

        self.overdue_table = QtWidgets.QTableWidget()
        self.overdue_table.setColumnCount(7)
        self.overdue_table.setHorizontalHeaderLabels([
            "Customer", "Invoice #", "Invoice Date", "Due Date",
            "Days Overdue", "Balance Due", "Credit Status"
        ])
        oh = self.overdue_table.horizontalHeader()
        oh.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        oh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        oh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for c in (2, 3, 4, 5, 6):
            oh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.overdue_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.overdue_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.overdue_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.overdue_table.verticalHeader().setVisible(False)
        layout.addWidget(self.overdue_table, stretch=1)

        self.overdue_totals_lbl = QtWidgets.QLabel("")
        self.overdue_totals_lbl.setStyleSheet("color%(white)s;font-size:13px;")
        layout.addWidget(self.overdue_totals_lbl)
        return w

    # ── Limit History tab ──────────────────────────────────────────────────

    def _build_limit_history_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Credit Limit Change History")
        title.setStyleSheet("color%(white)s;font-size:14px;font-weight%(bold)s;")
        hdr.addWidget(title)

        self.hist_cust_filter = QtWidgets.QComboBox()
        self.hist_cust_filter.setStyleSheet(COMBO_STYLE)
        self.hist_cust_filter.setMinimumWidth(200)
        self._refresh_customer_combo(self.hist_cust_filter, all_label="(all customers)")

        self.hist_from = QtWidgets.QDateEdit()
        self.hist_from.setStyleSheet(DATE_STYLE)
        self.hist_from.setCalendarPopup(True)
        self.hist_from.setDisplayFormat("MM/dd/yyyy")
        self.hist_from.setDate(QtCore.QDate.currentDate().addDays(-365))
        self.hist_to = QtWidgets.QDateEdit()
        self.hist_to.setStyleSheet(DATE_STYLE)
        self.hist_to.setCalendarPopup(True)
        self.hist_to.setDisplayFormat("MM/dd/yyyy")
        self.hist_to.setDate(QtCore.QDate.currentDate())

        def fl(t):
            lbl = QtWidgets.QLabel(t)
            lbl.setStyleSheet(LABEL_STYLE)
            return lbl

        hdr.addWidget(fl("Customer:"))
        hdr.addWidget(self.hist_cust_filter)
        hdr.addWidget(fl("From:"))
        hdr.addWidget(self.hist_from)
        hdr.addWidget(fl("To:"))
        hdr.addWidget(self.hist_to)
        ref_btn = QtWidgets.QPushButton("Apply")
        ref_btn.setStyleSheet(BUTTON_STYLE)
        ref_btn.setFixedHeight(30)
        ref_btn.clicked.connect(self._refresh_limit_history)
        hdr.addWidget(ref_btn)
        hdr.addStretch()
        layout.addLayout(hdr)

        self.hist_table = QtWidgets.QTableWidget()
        self.hist_table.setColumnCount(7)
        self.hist_table.setHorizontalHeaderLabels([
            "Customer", "Changed Date", "Old Limit", "New Limit",
            "Old Status", "New Status", "Changed By / Reason"
        ])
        lh = self.hist_table.horizontalHeader()
        lh.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        lh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        lh.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5):
            lh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.hist_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hist_table.setAlternatingRowColors(True)
        self.hist_table.verticalHeader().setVisible(False)
        layout.addWidget(self.hist_table, stretch=1)
        return w

    # ── Summary tab ────────────────────────────────────────────────────────

    def _build_summary_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Credit Exposure Summary")
        title.setStyleSheet("color%(white)s;font-size:14px;font-weight%(bold)s;")
        hdr.addWidget(title)
        ref_btn = QtWidgets.QPushButton("Refresh")
        ref_btn.setStyleSheet(BUTTON_STYLE)
        ref_btn.setFixedHeight(30)
        ref_btn.clicked.connect(self._refresh_summary)
        hdr.addWidget(ref_btn)
        exp_btn = QtWidgets.QPushButton("Export CSV")
        exp_btn.setStyleSheet(BUTTON_STYLE)
        exp_btn.setFixedHeight(30)
        exp_btn.clicked.connect(lambda: _export_table_to_csv(self.summary_table, self))
        hdr.addWidget(exp_btn)
        hdr.addStretch()
        layout.addLayout(hdr)

        self.summary_stats_lbl = QtWidgets.QLabel("")
        self.summary_stats_lbl.setStyleSheet("color%(white)s;font-size:13px;")
        layout.addWidget(self.summary_stats_lbl)

        self.summary_table = QtWidgets.QTableWidget()
        self.summary_table.setColumnCount(6)
        self.summary_table.setHorizontalHeaderLabels([
            "Customer", "Status", "Credit Limit", "AR Balance", "Available Credit", "Utilization %"
        ])
        sh = self.summary_table.horizontalHeader()
        sh.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        sh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5):
            sh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.summary_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.verticalHeader().setVisible(False)
        layout.addWidget(self.summary_table, stretch=1)
        return w

    # ── Credit Account data ────────────────────────────────────────────────

    def _refresh_customer_combo(self, combo, all_label=None):
        conn = get_db()
        customers = conn.execute(
            "SELECT id, first_name, last_name, company_name FROM customer "
            "ORDER BY company_name, last_name, first_name"
        ).fetchall()
        conn.close()
        combo.clear()
        combo.addItem(all_label if all_label else "-- select --", None)
        for c in customers:
            combo.addItem(_customer_display(c), c["id"])

    def _load_accounts(self, search=None):
        self.acct_search.blockSignals(True)
        if not search:
            self.acct_search.clear()
        self.acct_search.blockSignals(False)

        status_filter = self.acct_status_filter.currentText()
        conn = get_db()
        q = (
            "SELECT ca.id, ca.customer_id, c.first_name, c.last_name, c.company_name, "
            "ca.credit_limit, ca.status, ca.terms, ca.opened_date, ca.notes "
            "FROM credit_account ca JOIN customer c ON c.id = ca.customer_id WHERE 1=1"
        )
        params = []
        if search:
            q += " AND (c.company_name LIKE %s OR c.last_name LIKE %s)"
            params += [f"%{search}%", f"%{search}%"]
        if status_filter != "(all status)":
            q += " AND ca.status = %s"
            params.append(status_filter)
        q += " ORDER BY c.company_name, c.last_name, c.first_name"
        rows = conn.execute(q, params).fetchall()
        conn.close()

        self.acct_table.setRowCount(0)
        self._acct_row_ids = []
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter

        for row in rows:
            r = self.acct_table.rowCount()
            self.acct_table.insertRow(r)
            self._acct_row_ids.append(row["id"])
            ar_bal = _ar_balance(row["customer_id"])
            available = max(0.0, row["credit_limit"] - ar_bal)
            over_limit = ar_bal > row["credit_limit"] and row["credit_limit"] > 0
            alert = "⚠ OVER LIMIT" if over_limit else ""
            color = CREDIT_STATUS_COLORS.get(row["status"], QtGui.QColor(255, 255, 255))
            for c, (val, algn) in enumerate([
                (_customer_display(row), QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (_money(row["credit_limit"]), right),
                (_money(ar_bal), right),
                (_money(available), right),
                (row["status"].upper(), center),
                (row["terms"] or "", QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["opened_date"], center),
                (alert, center),
            ]):
                item = _ro(val, algn)
                item.setBackground(color)
                if c == 7 and over_limit:
                    item.setForeground(QtGui.QColor(180, 0, 0))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.acct_table.setItem(r, c, item)

    def _on_acct_search(self):
        self._load_accounts(search=self.acct_search.text().strip() or None)

    def _on_acct_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._acct_row_ids):
            return
        conn = get_db()
        acct = conn.execute("SELECT * FROM credit_account WHERE id=%s", (self._acct_row_ids[row],)).fetchone()
        conn.close()
        if not acct:
            return
        idx = self.af_cust_combo.findData(acct["customer_id"])
        if idx >= 0:
            self.af_cust_combo.setCurrentIndex(idx)
        self.af_limit.setValue(acct["credit_limit"])
        self.af_status.setCurrentText(acct["status"])
        self.af_terms.setText(acct["terms"] or "")
        self.af_notes.setText(acct["notes"] or "")
        self.af_changed_by.clear()
        self.af_reason.clear()
        try:
            parts = acct["opened_date"].split("-")
            self.af_opened.setDate(QtCore.QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        except (ValueError, IndexError, AttributeError):
            self.af_opened.setDate(QtCore.QDate.currentDate())

    def _acct_clear(self):
        self.af_cust_combo.setCurrentIndex(0)
        self.af_limit.setValue(0.0)
        self.af_status.setCurrentIndex(0)
        self.af_terms.clear()
        self.af_notes.clear()
        self.af_changed_by.clear()
        self.af_reason.clear()
        self.af_opened.setDate(QtCore.QDate.currentDate())
        self.acct_table.clearSelection()

    def _collect_acct_form(self):
        cid = self.af_cust_combo.currentData()
        if cid is None:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Select a customer.")
            return None
        return {
            "customer_id": cid,
            "credit_limit": self.af_limit.value(),
            "status": self.af_status.currentText(),
            "terms": self.af_terms.text().strip() or None,
            "opened_date": self.af_opened.date().toString("yyyy-MM-dd"),
            "notes": self.af_notes.text().strip() or None,
            "changed_by": self.af_changed_by.text().strip() or None,
            "reason": self.af_reason.text().strip() or None,
        }

    def _on_acct_add(self):
        data = self._collect_acct_form()
        if not data:
            return
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO credit_account (customer_id, credit_limit, status, terms, opened_date, notes)
                VALUES (%(customer_id)s, %(credit_limit)s, %(status)s, %(terms)s, %(opened_date)s, %(notes)s)
            """, data)
            # log the initial entry
            conn.execute("""
                INSERT INTO credit_limit_history
                    (customer_id, changed_date, old_limit, new_limit, old_status, new_status, changed_by, reason)
                VALUES (%s, %s, NULL, %s, NULL, %s, %s, %s)
            """, (data["customer_id"], date.today().isoformat(),
                  data["credit_limit"], data["status"],
                  data["changed_by"], data["reason"] or "Account opened"))
            conn.commit()
        except sqlite3.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate", "A credit account already exists for this customer.")
            conn.close()
            return
        conn.close()
        self._acct_clear()
        self._load_accounts()
        self._refresh_summary()
        self._refresh_limit_history()

    def _on_acct_update(self):
        row = self.acct_table.currentRow()
        if row < 0 or row >= len(self._acct_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select an account first.")
            return
        data = self._collect_acct_form()
        if not data:
            return
        acct_id = self._acct_row_ids[row]
        conn = get_db()
        old = conn.execute(
            "SELECT credit_limit, status FROM credit_account WHERE id=%s", (acct_id,)
        ).fetchone()
        data["id"] = acct_id
        conn.execute("""
            UPDATE credit_account
            SET customer_id=%(customer_id)s, credit_limit=%(credit_limit)s, status=%(status)s,
                terms=%(terms)s, opened_date=%(opened_date)s, notes=%(notes)s
            WHERE id=%(id)s
        """, data)
        # log if limit or status changed
        if old and (old["credit_limit"] != data["credit_limit"] or old["status"] != data["status"]):
            conn.execute("""
                INSERT INTO credit_limit_history
                    (customer_id, changed_date, old_limit, new_limit, old_status, new_status, changed_by, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (data["customer_id"], date.today().isoformat(),
                  old["credit_limit"], data["credit_limit"],
                  old["status"], data["status"],
                  data["changed_by"], data["reason"]))
        conn.commit()
        conn.close()
        self._load_accounts()
        self._refresh_summary()
        self._refresh_limit_history()

    def _on_acct_delete(self):
        row = self.acct_table.currentRow()
        if row < 0 or row >= len(self._acct_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select an account first.")
            return
        if (QtWidgets.QMessageBox.question(
                self, "Confirm Delete", "Delete this credit account%s",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            conn = get_db()
            conn.execute("DELETE FROM credit_account WHERE id=%s", (self._acct_row_ids[row],))
            conn.commit()
            conn.close()
            self._acct_clear()
            self._load_accounts()
            self._refresh_summary()

    # ── Auto-Hold logic ────────────────────────────────────────────────────

    def _run_auto_hold(self, silent=False):
        """Check all 'good' accounts. Auto-set to 'hold' if AR balance > credit limit.
        Returns list of customer names that were held."""
        conn = get_db()
        accounts = conn.execute(
            "SELECT ca.id, ca.customer_id, ca.credit_limit, c.first_name, c.last_name, c.company_name "
            "FROM credit_account ca JOIN customer c ON c.id = ca.customer_id "
            "WHERE ca.status = 'good'"
        ).fetchall()
        conn.close()

        held = []
        for acct in accounts:
            bal = _ar_balance(acct["customer_id"])
            if bal > acct["credit_limit"] and acct["credit_limit"] > 0:
                conn = get_db()
                conn.execute(
                    "UPDATE credit_account SET status='hold' WHERE id=%s", (acct["id"],))
                conn.execute("""
                    INSERT INTO credit_limit_history
                        (customer_id, changed_date, old_limit, new_limit, old_status, new_status, changed_by, reason)
                    VALUES (%s, %s, %s, %s, 'good', 'hold', 'System', 'Auto-hold: AR balance exceeded credit limit')
                """, (acct["customer_id"], date.today().isoformat(),
                      acct["credit_limit"], acct["credit_limit"]))
                conn.commit()
                conn.close()
                held.append(_customer_display(acct))

        if not silent and held:
            QtWidgets.QMessageBox.warning(
                self, "Auto-Hold Applied",
                f"{len(held)} account(s) placed on hold:\n\n" + "\n".join(held))
        elif not silent:
            QtWidgets.QMessageBox.information(
                self, "Auto-Hold Check", "No accounts exceed their credit limit. No changes made.")
        return held

    def _on_auto_hold_clicked(self):
        held = self._run_auto_hold(silent=False)
        if held:
            self._load_accounts()
            self._refresh_summary()
            self._refresh_limit_history()

    # ── Applications data ──────────────────────────────────────────────────

    def _load_applications(self):
        status = self.app_status_filter.currentText()
        from_s = self.app_from.date().toString("yyyy-MM-dd")
        to_s = self.app_to.date().toString("yyyy-MM-dd")
        conn = get_db()
        q = (
            "SELECT ca.id, ca.customer_id, c.first_name, c.last_name, c.company_name, "
            "ca.applied_date, ca.requested_limit, ca.approved_limit, ca.status, "
            "ca.reviewed_by, ca.review_date, ca.notes "
            "FROM credit_application ca JOIN customer c ON c.id = ca.customer_id "
            "WHERE ca.applied_date BETWEEN %s AND %s"
        )
        params = [from_s, to_s]
        if status != "(all status)":
            q += " AND ca.status = %s"
            params.append(status)
        q += " ORDER BY ca.applied_date DESC"
        rows = conn.execute(q, params).fetchall()
        conn.close()

        self.app_table.setRowCount(0)
        self._app_row_ids = []
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter

        for row in rows:
            r = self.app_table.rowCount()
            self.app_table.insertRow(r)
            self._app_row_ids.append(row["id"])
            color = APP_STATUS_COLORS.get(row["status"], QtGui.QColor(255, 255, 255))
            approved_str = _money(row["approved_limit"]) if row["approved_limit"] is not None else ""
            for c, (val, algn) in enumerate([
                (_customer_display(row), QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["applied_date"], center),
                (_money(row["requested_limit"]), right),
                (approved_str, right),
                (row["status"].upper(), center),
                (row["reviewed_by"] or "", QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["review_date"] or "", center),
                (row["notes"] or "", QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
            ]):
                item = _ro(val, algn)
                item.setBackground(color)
                self.app_table.setItem(r, c, item)

    def _app_show_all(self):
        self.app_status_filter.setCurrentIndex(0)
        self.app_from.setDate(QtCore.QDate(2000, 1, 1))
        self.app_to.setDate(QtCore.QDate.currentDate())
        self._load_applications()

    def _on_new_application(self):
        dlg = NewApplicationDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._load_applications()

    def _on_review_application(self):
        row = self.app_table.currentRow()
        if row < 0 or row >= len(self._app_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select an application first.")
            return
        app_id = self._app_row_ids[row]
        conn = get_db()
        status = conn.execute(
            "SELECT status FROM credit_application WHERE id=%s", (app_id,)
        ).fetchone()["status"]
        conn.close()
        if status != "pending":
            QtWidgets.QMessageBox.information(
                self, "Already Reviewed", f"This application has already been {status}.")
            return
        dlg = ReviewApplicationDialog(app_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._load_applications()
            self._load_accounts()
            self._refresh_summary()
            self._refresh_limit_history()

    def _on_delete_application(self):
        row = self.app_table.currentRow()
        if row < 0 or row >= len(self._app_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select an application first.")
            return
        if (QtWidgets.QMessageBox.question(
                self, "Confirm Delete", "Delete this application%s",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            conn = get_db()
            conn.execute("DELETE FROM credit_application WHERE id=%s", (self._app_row_ids[row],))
            conn.commit()
            conn.close()
            self._load_applications()

    # ── Overdue Report data ────────────────────────────────────────────────

    def _refresh_overdue(self):
        today = date.today().isoformat()
        conn = get_db()
        rows = conn.execute("""
            SELECT ai.id, ai.invoice_number, ai.due_date, ai.invoice_date,
                   ai.amount - COALESCE(p.paid, 0) AS balance,
                   c.id AS customer_id, c.first_name, c.last_name, c.company_name,
                   ca.status AS credit_status
            FROM ar_invoice ai
            JOIN customer c ON c.id = ai.customer_id
            LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM ar_payment GROUP BY invoice_id) p
                ON p.invoice_id = ai.id
            LEFT JOIN credit_account ca ON ca.customer_id = c.id
            WHERE ai.status IN ('open','partial') AND ai.due_date < %s
            ORDER BY ai.due_date ASC
        """, (today,)).fetchall()
        conn.close()

        self.overdue_table.setRowCount(0)
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter

        total_overdue = 0.0
        today_d = date.today()
        for row in rows:
            try:
                due_d = date.fromisoformat(row["due_date"])
                days_over = (today_d - due_d).days
            except (ValueError, TypeError):
                days_over = 0
            balance = row["balance"] or 0.0
            if balance <= 0:
                continue
            total_overdue += balance
            color = _overdue_color(days_over)
            credit_status = (row["credit_status"] or "").upper()

            r = self.overdue_table.rowCount()
            self.overdue_table.insertRow(r)
            for c, (val, algn) in enumerate([
                (_customer_display(row), QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["invoice_number"], QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["invoice_date"] or "", center),
                (row["due_date"] or "", center),
                (str(days_over), right),
                (_money(balance), right),
                (credit_status, center),
            ]):
                item = _ro(val, algn)
                item.setBackground(color)
                self.overdue_table.setItem(r, c, item)

        count = self.overdue_table.rowCount()
        self.overdue_totals_lbl.setText(
            f"Overdue invoices: {count}    Total overdue balance: {_money(total_overdue)}")

    # ── Limit History data ─────────────────────────────────────────────────

    def _refresh_limit_history(self):
        cid = self.hist_cust_filter.currentData()
        from_s = self.hist_from.date().toString("yyyy-MM-dd")
        to_s = self.hist_to.date().toString("yyyy-MM-dd")
        conn = get_db()
        q = (
            "SELECT h.id, h.customer_id, c.first_name, c.last_name, c.company_name, "
            "h.changed_date, h.old_limit, h.new_limit, h.old_status, h.new_status, "
            "h.changed_by, h.reason "
            "FROM credit_limit_history h JOIN customer c ON c.id = h.customer_id "
            "WHERE h.changed_date BETWEEN %s AND %s"
        )
        params = [from_s, to_s]
        if cid:
            q += " AND h.customer_id = %s"
            params.append(cid)
        q += " ORDER BY h.changed_date DESC, h.id DESC"
        rows = conn.execute(q, params).fetchall()
        conn.close()

        self.hist_table.setRowCount(0)
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter

        for row in rows:
            r = self.hist_table.rowCount()
            self.hist_table.insertRow(r)
            old_lim = _money(row["old_limit"]) if row["old_limit"] is not None else "(new)"
            by_reason = " / ".join(filter(None, [row["changed_by"], row["reason"]])) or ""
            for c, (val, algn) in enumerate([
                (_customer_display(row), QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["changed_date"], center),
                (old_lim, right),
                (_money(row["new_limit"]), right),
                (row["old_status"] or "", center),
                (row["new_status"] or "", center),
                (by_reason, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
            ]):
                self.hist_table.setItem(r, c, _ro(val, algn))

    # ── Summary data ───────────────────────────────────────────────────────

    def _refresh_summary(self):
        conn = get_db()
        rows = conn.execute("""
            SELECT ca.customer_id, c.first_name, c.last_name, c.company_name,
                   ca.credit_limit, ca.status
            FROM credit_account ca JOIN customer c ON c.id = ca.customer_id
            ORDER BY c.company_name, c.last_name, c.first_name
        """).fetchall()
        conn.close()

        self.summary_table.setRowCount(0)
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter

        total_limit = total_balance = 0.0
        for row in rows:
            ar_bal = _ar_balance(row["customer_id"])
            available = max(0.0, row["credit_limit"] - ar_bal)
            util_pct = (ar_bal / row["credit_limit"] * 100) if row["credit_limit"] > 0 else 0.0
            color = CREDIT_STATUS_COLORS.get(row["status"], QtGui.QColor(255, 255, 255))
            r = self.summary_table.rowCount()
            self.summary_table.insertRow(r)
            for c, (val, algn) in enumerate([
                (_customer_display(row), QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["status"].upper(), center),
                (_money(row["credit_limit"]), right),
                (_money(ar_bal), right),
                (_money(available), right),
                (f"{util_pct:.1f}%", right),
            ]):
                item = _ro(val, algn)
                item.setBackground(color)
                self.summary_table.setItem(r, c, item)
            total_limit += row["credit_limit"]
            total_balance += ar_bal

        conn = get_db()
        pending_count = conn.execute(
            "SELECT COUNT(*) FROM credit_application WHERE status='pending'"
        ).fetchone()[0]
        conn.close()

        total_avail = max(0.0, total_limit - total_balance)
        overall_util = (total_balance / total_limit * 100) if total_limit > 0 else 0.0
        self.summary_stats_lbl.setText(
            f"Total Credit Extended: {_money(total_limit)}     "
            f"Total AR Balance: {_money(total_balance)}     "
            f"Total Available: {_money(total_avail)}     "
            f"Overall Utilization: {overall_util:.1f}%     "
            f"Pending Applications: {pending_count}"
        )

    # ── A/R Aging tab ──────────────────────────────────────────────────────

    def _build_aging_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Accounts Receivable Aging Report")
        title.setStyleSheet("color%(white)s;font-size:14px;font-weight%(bold)s;")
        hdr.addWidget(title)

        hdr.addWidget(QtWidgets.QLabel("  As of:") if False else self._make_lbl("  As of:"))
        self.aging_as_of = QtWidgets.QDateEdit()
        self.aging_as_of.setStyleSheet(DATE_STYLE)
        self.aging_as_of.setCalendarPopup(True)
        self.aging_as_of.setDisplayFormat("MM/dd/yyyy")
        self.aging_as_of.setDate(QtCore.QDate.currentDate())
        hdr.addWidget(self.aging_as_of)

        ref_btn = QtWidgets.QPushButton("Refresh")
        ref_btn.setStyleSheet(BUTTON_STYLE)
        ref_btn.setFixedHeight(30)
        ref_btn.clicked.connect(self._refresh_aging)
        hdr.addWidget(ref_btn)
        exp_btn = QtWidgets.QPushButton("Export CSV")
        exp_btn.setStyleSheet(BUTTON_STYLE)
        exp_btn.setFixedHeight(30)
        exp_btn.clicked.connect(lambda: _export_table_to_csv(self.aging_table, self))
        hdr.addWidget(exp_btn)
        hdr.addStretch()
        layout.addLayout(hdr)

        self.aging_table = QtWidgets.QTableWidget()
        self.aging_table.setColumnCount(8)
        self.aging_table.setHorizontalHeaderLabels([
            "Customer", "Current", "1–30 Days", "31–60 Days",
            "61–90 Days", "91+ Days", "Total Balance", "Credit Limit"
        ])
        ah = self.aging_table.horizontalHeader()
        ah.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        ah.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in range(1, 8):
            ah.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.aging_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.aging_table.setAlternatingRowColors(True)
        self.aging_table.verticalHeader().setVisible(False)
        layout.addWidget(self.aging_table, stretch=1)

        self.aging_totals_lbl = QtWidgets.QLabel("")
        self.aging_totals_lbl.setStyleSheet("color%(white)s;font-size:13px;")
        self.aging_totals_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.aging_totals_lbl)
        return w

    def _make_lbl(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(LABEL_STYLE)
        return lbl

    def _refresh_aging(self):
        as_of = self.aging_as_of.date().toString("yyyy-MM-dd")
        conn = get_db()
        rows = conn.execute("""
            SELECT ai.due_date, ai.invoice_date,
                   ai.amount - COALESCE(p.paid, 0) AS balance,
                   c.id AS customer_id, c.first_name, c.last_name, c.company_name,
                   ca.credit_limit
            FROM ar_invoice ai
            JOIN customer c ON c.id = ai.customer_id
            LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM ar_payment GROUP BY invoice_id) p
                ON p.invoice_id = ai.id
            LEFT JOIN credit_account ca ON ca.customer_id = c.id
            WHERE ai.status IN ('open','partial') AND ai.invoice_date <= %s
            ORDER BY c.company_name, c.last_name, c.first_name
        """, (as_of,)).fetchall()
        conn.close()

        # Bucket per customer
        buckets: dict = {}
        as_of_d = date.fromisoformat(as_of)
        for row in rows:
            bal = row["balance"] or 0.0
            if bal <= 0:
                continue
            cid = row["customer_id"]
            if cid not in buckets:
                buckets[cid] = {
                    "name": _customer_display(row),
                    "limit": row["credit_limit"] or 0.0,
                    "current": 0.0, "d30": 0.0, "d60": 0.0, "d90": 0.0, "d90p": 0.0,
                }
            try:
                due = date.fromisoformat(row["due_date"])
                days_over = (as_of_d - due).days
            except (ValueError, TypeError):
                days_over = 0
            b = buckets[cid]
            if days_over <= 0:
                b["current"] += bal
            elif days_over <= 30:
                b["d30"] += bal
            elif days_over <= 60:
                b["d60"] += bal
            elif days_over <= 90:
                b["d90"] += bal
            else:
                b["d90p"] += bal

        self.aging_table.setRowCount(0)
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        left = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        totals = {"current": 0.0, "d30": 0.0, "d60": 0.0, "d90": 0.0, "d90p": 0.0, "total": 0.0}

        for cid, b in sorted(buckets.items(), key=lambda x: x[1]["name"]):
            total = b["current"] + b["d30"] + b["d60"] + b["d90"] + b["d90p"]
            r = self.aging_table.rowCount()
            self.aging_table.insertRow(r)
            # row color driven by worst bucket
            if b["d90p"] > 0:
                row_color = QtGui.QColor(248, 215, 218)
            elif b["d90"] > 0:
                row_color = QtGui.QColor(255, 200, 150)
            elif b["d60"] > 0:
                row_color = QtGui.QColor(255, 224, 178)
            elif b["d30"] > 0:
                row_color = QtGui.QColor(255, 243, 205)
            else:
                row_color = QtGui.QColor(212, 237, 218)

            for c, (val, algn) in enumerate([
                (b["name"], left),
                (_money(b["current"]), right), (_money(b["d30"]), right),
                (_money(b["d60"]), right), (_money(b["d90"]), right),
                (_money(b["d90p"]), right), (_money(total), right),
                (_money(b["limit"]), right),
            ]):
                it = _ro(val, algn)
                it.setBackground(row_color)
                self.aging_table.setItem(r, c, it)
            for k, v in [("current", b["current"]), ("d30", b["d30"]), ("d60", b["d60"]),
                         ("d90", b["d90"]), ("d90p", b["d90p"]), ("total", total)]:
                totals[k] += v

        # Totals row
        if buckets:
            r = self.aging_table.rowCount()
            self.aging_table.insertRow(r)
            bold = QtGui.QFont()
            bold.setBold(True)
            bg = QtGui.QColor(200, 220, 255)
            for c, val in enumerate([
                "TOTALS", _money(totals["current"]), _money(totals["d30"]),
                _money(totals["d60"]), _money(totals["d90"]), _money(totals["d90p"]),
                _money(totals["total"]), "",
            ]):
                algn = left if c == 0 else right
                it = _ro(val, algn)
                it.setFont(bold)
                it.setBackground(bg)
                self.aging_table.setItem(r, c, it)

        self.aging_totals_lbl.setText(
            f"Customers: {len(buckets)}  |  "
            f"Current: {_money(totals['current'])}  |  "
            f"1–30: {_money(totals['d30'])}  |  "
            f"31–60: {_money(totals['d60'])}  |  "
            f"61–90: {_money(totals['d90'])}  |  "
            f"91+: {_money(totals['d90p'])}  |  "
            f"Total: {_money(totals['total'])}"
        )

    # ── Collections tab ─────────────────────────────────────────────────────

    def _build_collections_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # Left: customer list with overdue balances
        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 6, 0)

        lv.addWidget(self._make_lbl("Customers with Open Balances"))

        self.col_cust_tbl = QtWidgets.QTableWidget(0, 3)
        self.col_cust_tbl.setHorizontalHeaderLabels(["Customer", "Balance", "Activities"])
        ch = self.col_cust_tbl.horizontalHeader()
        ch.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        ch.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        ch.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ch.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.col_cust_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.col_cust_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.col_cust_tbl.setAlternatingRowColors(True)
        self.col_cust_tbl.verticalHeader().setVisible(False)
        self.col_cust_tbl.itemSelectionChanged.connect(self._on_col_cust_select)
        lv.addWidget(self.col_cust_tbl, stretch=1)

        ref_cust_btn = QtWidgets.QPushButton("Refresh List")
        ref_cust_btn.setStyleSheet(BUTTON_STYLE)
        ref_cust_btn.setFixedHeight(28)
        ref_cust_btn.clicked.connect(self._refresh_col_customers)
        lv.addWidget(ref_cust_btn)
        splitter.addWidget(left)

        # Right: activity log + form
        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(6, 0, 0, 0)

        self.col_cust_lbl = QtWidgets.QLabel("Select a customer to view activities")
        self.col_cust_lbl.setStyleSheet("color%(white)s;font-weight%(bold)s;font-size:13px;")
        rv.addWidget(self.col_cust_lbl)

        # Filter bar
        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(self._make_lbl("Status:"))
        self.col_status_filter = QtWidgets.QComboBox()
        self.col_status_filter.setStyleSheet(COMBO_STYLE)
        self.col_status_filter.addItem("All")
        [self.col_status_filter.addItem(s) for s in ACTIVITY_STATUSES]
        self.col_status_filter.currentIndexChanged.connect(self._refresh_col_activities)
        fb.addWidget(self.col_status_filter)
        fb.addWidget(self._make_lbl("Follow-up Due:"))
        self.col_due_filter = QtWidgets.QComboBox()
        self.col_due_filter.setStyleSheet(COMBO_STYLE)
        self.col_due_filter.addItems(["All Dates", "Today", "This Week", "Overdue"])
        self.col_due_filter.currentIndexChanged.connect(self._refresh_col_activities)
        fb.addWidget(self.col_due_filter)
        fb.addStretch()
        exp_btn = QtWidgets.QPushButton("Export CSV")
        exp_btn.setStyleSheet(BUTTON_STYLE)
        exp_btn.setFixedHeight(28)
        exp_btn.clicked.connect(lambda: _export_table_to_csv(self.col_act_tbl, self))
        fb.addWidget(exp_btn)
        rv.addLayout(fb)

        self.col_act_tbl = QtWidgets.QTableWidget(0, 8)
        self.col_act_tbl.setHorizontalHeaderLabels([
            "ID", "Date", "Type", "Contact", "Notes", "Promised", "Follow-up", "Status"
        ])
        ah = self.col_act_tbl.horizontalHeader()
        ah.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        ah.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.col_act_tbl.setColumnWidth(0, 40)
        self.col_act_tbl.setColumnWidth(1, 90)
        self.col_act_tbl.setColumnWidth(2, 110)
        self.col_act_tbl.setColumnWidth(3, 100)
        self.col_act_tbl.setColumnWidth(5, 90)
        self.col_act_tbl.setColumnWidth(6, 90)
        self.col_act_tbl.setColumnWidth(7, 90)
        self.col_act_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.col_act_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.col_act_tbl.setAlternatingRowColors(True)
        self.col_act_tbl.verticalHeader().setVisible(False)
        self.col_act_tbl.itemSelectionChanged.connect(self._on_col_act_select)
        rv.addWidget(self.col_act_tbl, stretch=1)

        # Activity form
        fg = QtWidgets.QGroupBox("Log Activity")
        fg.setStyleSheet("QGroupBox{color%(white)s;font-weight%(bold)s;border:1px solid white;margin-top:8px;}"
                         "QGroupBox:%(title)s{subcontrol-origin%(margin)s;left:10px;}")
        fl = QtWidgets.QFormLayout(fg)
        fl.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)

        self.col_ef_date = QtWidgets.QDateEdit()
        self.col_ef_date.setStyleSheet(DATE_STYLE)
        self.col_ef_date.setCalendarPopup(True)
        self.col_ef_date.setDisplayFormat("MM/dd/yyyy")
        self.col_ef_date.setDate(QtCore.QDate.currentDate())

        self.col_ef_type = QtWidgets.QComboBox()
        self.col_ef_type.setStyleSheet(COMBO_STYLE)
        [self.col_ef_type.addItem(t) for t in ACTIVITY_TYPES]

        self.col_ef_contact = QtWidgets.QLineEdit()
        self.col_ef_contact.setStyleSheet(INPUT_STYLE)
        self.col_ef_notes = QtWidgets.QLineEdit()
        self.col_ef_notes.setStyleSheet(INPUT_STYLE)

        self.col_ef_promised = QtWidgets.QDoubleSpinBox()
        self.col_ef_promised.setStyleSheet(SPIN_STYLE)
        self.col_ef_promised.setRange(0, 9_999_999)
        self.col_ef_promised.setDecimals(2)
        self.col_ef_promised.setPrefix("$ ")
        self.col_ef_promised.setSpecialValueText("(none)")

        self.col_ef_promise_date = QtWidgets.QDateEdit()
        self.col_ef_promise_date.setStyleSheet(DATE_STYLE)
        self.col_ef_promise_date.setCalendarPopup(True)
        self.col_ef_promise_date.setDisplayFormat("MM/dd/yyyy")
        self.col_ef_promise_date.setSpecialValueText("(none)")
        self.col_ef_promise_date.setDate(QtCore.QDate.currentDate())

        self.col_ef_followup = QtWidgets.QDateEdit()
        self.col_ef_followup.setStyleSheet(DATE_STYLE)
        self.col_ef_followup.setCalendarPopup(True)
        self.col_ef_followup.setDisplayFormat("MM/dd/yyyy")
        self.col_ef_followup.setSpecialValueText("(none)")
        self.col_ef_followup.setDate(QtCore.QDate.currentDate().addDays(7))

        self.col_ef_status = QtWidgets.QComboBox()
        self.col_ef_status.setStyleSheet(COMBO_STYLE)
        [self.col_ef_status.addItem(s) for s in ACTIVITY_STATUSES]

        self.col_ef_by = QtWidgets.QLineEdit()
        self.col_ef_by.setStyleSheet(INPUT_STYLE)

        fl.addRow(self._make_lbl("Date:"), self.col_ef_date)
        fl.addRow(self._make_lbl("Type:"), self.col_ef_type)
        fl.addRow(self._make_lbl("Contact:"), self.col_ef_contact)
        fl.addRow(self._make_lbl("Notes:"), self.col_ef_notes)
        fl.addRow(self._make_lbl("Amount Promised:"), self.col_ef_promised)
        fl.addRow(self._make_lbl("Promise Date:"), self.col_ef_promise_date)
        fl.addRow(self._make_lbl("Follow-up Date:"), self.col_ef_followup)
        fl.addRow(self._make_lbl("Status:"), self.col_ef_status)
        fl.addRow(self._make_lbl("Created By:"), self.col_ef_by)
        rv.addWidget(fg)

        btn_row = QtWidgets.QHBoxLayout()
        for txt, slot in [("Log Activity", self._on_col_add),
                          ("Update", self._on_col_update),
                          ("Delete", self._on_col_delete),
                          ("Clear", self._on_col_clear)]:
            b = QtWidgets.QPushButton(txt)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        rv.addLayout(btn_row)
        splitter.addWidget(right)
        splitter.setSizes([300, 800])
        v.addWidget(splitter)
        self._col_selected_cid = None
        self._col_selected_act_id = None
        return w

    # ── Risk Scoring tab ─────────────────────────────────────────────────────

    def _build_risk_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Credit Risk Scoring")
        title.setStyleSheet("color%(white)s;font-size:14px;font-weight%(bold)s;")
        hdr.addWidget(title)
        ref_btn = QtWidgets.QPushButton("Run Scoring")
        ref_btn.setStyleSheet(BUTTON_STYLE)
        ref_btn.setFixedHeight(30)
        ref_btn.clicked.connect(self._refresh_risk)
        hdr.addWidget(ref_btn)
        exp_btn = QtWidgets.QPushButton("Export CSV")
        exp_btn.setStyleSheet(BUTTON_STYLE)
        exp_btn.setFixedHeight(30)
        exp_btn.clicked.connect(lambda: _export_table_to_csv(self.risk_tbl, self))
        hdr.addWidget(exp_btn)
        hdr.addStretch()
        layout_lbl = QtWidgets.QLabel(
            "Score: 0–30 Low  |  31–60 Medium  |  61–80 High  |  81–100 Critical")
        layout_lbl.setStyleSheet("color%(rgba)s(255,255,255,200);font-size:11px;")
        hdr.addWidget(layout_lbl)
        v.addLayout(hdr)

        self.risk_tbl = QtWidgets.QTableWidget(0, 9)
        self.risk_tbl.setHorizontalHeaderLabels([
            "Customer", "Status", "Utilization %", "Max Days Over",
            "Avg Days Over", "Open Invoices", "Risk Score", "Risk Level", "Recommendation"
        ])
        rh = self.risk_tbl.horizontalHeader()
        rh.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        rh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        rh.setSectionResizeMode(8, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in range(1, 8):
            rh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.risk_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.risk_tbl.setAlternatingRowColors(True)
        self.risk_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.risk_tbl, stretch=1)

        self.risk_summary_lbl = QtWidgets.QLabel("")
        self.risk_summary_lbl.setStyleSheet("color%(white)s;font-size:13px;")
        v.addWidget(self.risk_summary_lbl)
        return w

    def _refresh_risk(self):
        today = date.today()
        conn = get_db()
        accounts = conn.execute("""
            SELECT ca.customer_id, ca.credit_limit, ca.status,
                   c.first_name, c.last_name, c.company_name
            FROM credit_account ca JOIN customer c ON c.id=ca.customer_id
            ORDER BY c.company_name, c.last_name, c.first_name
        """).fetchall()

        # Gather overdue invoice stats per customer
        inv_rows = conn.execute("""
            SELECT ai.customer_id, ai.due_date,
                   ai.amount - COALESCE(p.paid, 0) AS balance
            FROM ar_invoice ai
            LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM ar_payment GROUP BY invoice_id) p
                ON p.invoice_id = ai.id
            WHERE ai.status IN ('open','partial')
        """).fetchall()
        conn.close()

        inv_map: dict = {}
        for row in inv_rows:
            bal = row["balance"] or 0.0
            if bal <= 0:
                continue
            cid = row["customer_id"]
            if cid not in inv_map:
                inv_map[cid] = {"balances": [], "days": [], "count": 0}
            inv_map[cid]["balances"].append(bal)
            inv_map[cid]["count"] += 1
            try:
                due_d = date.fromisoformat(row["due_date"])
                days_over = max(0, (today - due_d).days)
                inv_map[cid]["days"].append(days_over)
            except (ValueError, TypeError):
                inv_map[cid]["days"].append(0)

        self.risk_tbl.setRowCount(0)
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        left = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter

        risk_counts = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}

        for acct in accounts:
            cid = acct["customer_id"]
            limit = acct["credit_limit"] or 0.0
            status = acct["status"]
            info = inv_map.get(cid, {"balances": [], "days": [], "count": 0})

            ar_bal = sum(info["balances"])
            max_days = max(info["days"]) if info["days"] else 0
            avg_days = (sum(info["days"]) / len(info["days"])) if info["days"] else 0.0
            util_pct = (ar_bal / limit * 100) if limit > 0 else 0.0
            open_inv = info["count"]

            # Scoring components (0–100)
            # Status: good=0, hold=20, suspended=35, closed=10
            status_pts = {"good": 0, "hold": 20, "suspended": 35, "closed": 10}.get(status, 0)
            # Utilization: 0%=0pts, 100%=30pts, >100%=40pts
            util_pts = min(40, util_pct * 0.4) if util_pct <= 100 else 40
            # Max days overdue: 0=0, 30=15, 60=20, 90=25, 90+=30
            if max_days == 0:
                days_pts = 0
            elif max_days <= 30:
                days_pts = 10
            elif max_days <= 60:
                days_pts = 20
            elif max_days <= 90:
                days_pts = 25
            else:
                days_pts = 30

            score = min(100, round(status_pts + util_pts + days_pts))

            if score <= 30:
                level = "Low"
            elif score <= 60:
                level = "Medium"
            elif score <= 80:
                level = "High"
            else:
                level = "Critical"

            if level == "Low":
                rec = "No action required"
            elif level == "Medium":
                rec = "Monitor closely"
            elif level == "High":
                rec = "Review credit limit; consider hold"
            else:
                rec = "Place on hold; initiate collections"

            risk_counts[level] += 1
            color = RISK_COLORS.get(level, QtGui.QColor(255, 255, 255))
            r = self.risk_tbl.rowCount()
            self.risk_tbl.insertRow(r)
            for c, (val, algn) in enumerate([
                (_customer_display(acct), left),
                (status.upper(), center),
                (f"{util_pct:.1f}%", right),
                (str(max_days), right),
                (f"{avg_days:.1f}", right),
                (str(open_inv), right),
                (str(score), right),
                (level, center),
                (rec, left),
            ]):
                it = _ro(val, algn)
                it.setBackground(color)
                if c == 6:
                    font = it.font()
                    font.setBold(True)
                    it.setFont(font)
                self.risk_tbl.setItem(r, c, it)

        self.risk_summary_lbl.setText(
            f"Total accounts: {len(accounts)}  |  "
            f"Low: {risk_counts['Low']}  |  "
            f"Medium: {risk_counts['Medium']}  |  "
            f"High: {risk_counts['High']}  |  "
            f"Critical: {risk_counts['Critical']}"
        )

    # ── Collections data ─────────────────────────────────────────────────────

    def _refresh_col_customers(self):
        conn = get_db()
        custs = conn.execute("""
            SELECT DISTINCT c.id, c.first_name, c.last_name, c.company_name
            FROM ar_invoice ai
            JOIN customer c ON c.id=ai.customer_id
            LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM ar_payment GROUP BY invoice_id) p
                ON p.invoice_id=ai.id
            WHERE ai.status IN ('open','partial')
            ORDER BY c.company_name, c.last_name, c.first_name
        """).fetchall()
        act_counts = {r[0]: r[1] for r in conn.execute(
            "SELECT customer_id, COUNT(*) FROM collection_activity GROUP BY customer_id"
        ).fetchall()}
        conn.close()

        self.col_cust_tbl.setRowCount(0)
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        left = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        for cust in custs:
            bal = _ar_balance(cust["id"])
            if bal <= 0:
                continue
            r = self.col_cust_tbl.rowCount()
            self.col_cust_tbl.insertRow(r)
            self.col_cust_tbl.setItem(r, 0, _ro(_customer_display(cust), left))
            self.col_cust_tbl.setItem(r, 1, _ro(_money(bal), right))
            self.col_cust_tbl.setItem(r, 2, _ro(str(act_counts.get(cust["id"], 0)), center))
            self.col_cust_tbl.item(r, 0).setData(QtCore.Qt.ItemDataRole.UserRole, cust["id"])

    def _on_col_cust_select(self):
        rows = self.col_cust_tbl.selectionModel().selectedRows()
        if not rows:
            return
        cid = self.col_cust_tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        name = self.col_cust_tbl.item(rows[0].row(), 0).text()
        bal = self.col_cust_tbl.item(rows[0].row(), 1).text()
        self._col_selected_cid = cid
        self.col_cust_lbl.setText(f"Activities — {name}  (Balance: {bal})")
        self._refresh_col_activities()

    def _refresh_col_activities(self):
        cid = getattr(self, "_col_selected_cid", None)
        if not cid:
            self.col_act_tbl.setRowCount(0)
            return
        status_f = self.col_status_filter.currentText()
        due_f = self.col_due_filter.currentText()
        today = date.today()

        conn = get_db()
        q = "SELECT * FROM collection_activity WHERE customer_id=%s"
        params = [cid]
        if status_f != "All":
            q += " AND status=%s"
            params.append(status_f)
        q += " ORDER BY activity_date DESC, id DESC"
        rows = conn.execute(q, params).fetchall()
        conn.close()

        STATUS_COLORS_COL = {
            "Open": QtGui.QColor(255, 243, 205),
            "Pending": QtGui.QColor(200, 230, 255),
            "Resolved": QtGui.QColor(212, 237, 218),
            "Escalated": QtGui.QColor(248, 215, 218),
        }
        self.col_act_tbl.setRowCount(0)
        self._col_act_ids = []
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        left = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter

        for row in rows:
            # Apply due-date filter
            if due_f != "All Dates" and row["follow_up_date"]:
                try:
                    fu = date.fromisoformat(row["follow_up_date"])
                    if due_f == "Today" and fu != today:
                        continue
                    elif due_f == "This Week":
                        wk_end = today + __import__('datetime').timedelta(days=6)
                        if not (today <= fu <= wk_end):
                            continue
                    elif due_f == "Overdue" and fu >= today:
                        continue
                except ValueError:
                    pass

            color = STATUS_COLORS_COL.get(row["status"], QtGui.QColor(255, 255, 255))
            promised_str = _money(row["amount_promised"]) if row["amount_promised"] else ""
            r = self.col_act_tbl.rowCount()
            self.col_act_tbl.insertRow(r)
            self._col_act_ids.append(row["id"])
            for c, (val, algn) in enumerate([
                (str(row["id"]), center),
                (row["activity_date"], center),
                (row["activity_type"], left),
                (row["contact_name"] or "", left),
                (row["notes"] or "", left),
                (promised_str, right),
                (row["follow_up_date"] or "", center),
                (row["status"], center),
            ]):
                it = _ro(val, algn)
                it.setBackground(color)
                self.col_act_tbl.setItem(r, c, it)
            self.col_act_tbl.item(r, 0).setData(QtCore.Qt.ItemDataRole.UserRole, row["id"])

    def _on_col_act_select(self):
        rows = self.col_act_tbl.selectionModel().selectedRows()
        if not rows:
            return
        aid = self.col_act_tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        self._col_selected_act_id = aid
        conn = get_db()
        row = conn.execute("SELECT * FROM collection_activity WHERE id=%s", (aid,)).fetchone()
        conn.close()
        if not row:
            return
        self.col_ef_date.setDate(QtCore.QDate.fromString(row["activity_date"], "yyyy-MM-dd"))
        idx = self.col_ef_type.findText(row["activity_type"])
        if idx >= 0:
            self.col_ef_type.setCurrentIndex(idx)
        self.col_ef_contact.setText(row["contact_name"] or "")
        self.col_ef_notes.setText(row["notes"] or "")
        self.col_ef_promised.setValue(row["amount_promised"] or 0.0)
        if row["promise_date"]:
            self.col_ef_promise_date.setDate(QtCore.QDate.fromString(row["promise_date"], "yyyy-MM-dd"))
        if row["follow_up_date"]:
            self.col_ef_followup.setDate(QtCore.QDate.fromString(row["follow_up_date"], "yyyy-MM-dd"))
        idx = self.col_ef_status.findText(row["status"])
        if idx >= 0:
            self.col_ef_status.setCurrentIndex(idx)
        self.col_ef_by.setText(row["created_by"] or "")

    def _col_form_values(self):
        promised = self.col_ef_promised.value() if self.col_ef_promised.value() > 0 else None
        return {
            "activity_date": self.col_ef_date.date().toString("yyyy-MM-dd"),
            "activity_type": self.col_ef_type.currentText(),
            "contact_name": self.col_ef_contact.text().strip() or None,
            "notes": self.col_ef_notes.text().strip() or None,
            "amount_promised": promised,
            "promise_date": self.col_ef_promise_date.date().toString("yyyy-MM-dd") if promised else None,
            "follow_up_date": self.col_ef_followup.date().toString("yyyy-MM-dd"),
            "status": self.col_ef_status.currentText(),
            "created_by": self.col_ef_by.text().strip() or None,
        }

    def _on_col_add(self):
        cid = getattr(self, "_col_selected_cid", None)
        if not cid:
            QtWidgets.QMessageBox.warning(self, "No Customer", "Select a customer first.")
            return
        vals = self._col_form_values()
        conn = get_db()
        conn.execute("""
            INSERT INTO collection_activity
                (customer_id, activity_date, activity_type, contact_name, notes,
                 amount_promised, promise_date, follow_up_date, status, created_by)
            VALUES (%(customer_id)s, %(activity_date)s, %(activity_type)s, %(contact_name)s, %(notes)s,
                    %(amount_promised)s, %(promise_date)s, %(follow_up_date)s, %(status)s, %(created_by)s)
        """, {**vals, "customer_id": cid})
        conn.commit()
        conn.close()
        self._refresh_col_activities()
        self._refresh_col_customers()
        self._on_col_clear()

    def _on_col_update(self):
        aid = getattr(self, "_col_selected_act_id", None)
        if not aid:
            QtWidgets.QMessageBox.warning(self, "No Activity", "Select an activity first.")
            return
        vals = self._col_form_values()
        conn = get_db()
        conn.execute("""
            UPDATE collection_activity SET
                activity_date=%(activity_date)s, activity_type=%(activity_type)s,
                contact_name=%(contact_name)s, notes=%(notes)s,
                amount_promised=%(amount_promised)s, promise_date=%(promise_date)s,
                follow_up_date=%(follow_up_date)s, status=%(status)s, created_by=%(created_by)s
            WHERE id=%(id)s
        """, {**vals, "id": aid})
        conn.commit()
        conn.close()
        self._refresh_col_activities()

    def _on_col_delete(self):
        aid = getattr(self, "_col_selected_act_id", None)
        if not aid:
            QtWidgets.QMessageBox.warning(self, "No Activity", "Select an activity first.")
            return
        if QtWidgets.QMessageBox.question(
            self, "Delete", "Delete this activity log entry%s",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM collection_activity WHERE id=%s", (aid,))
            conn.commit()
            conn.close()
            self._col_selected_act_id = None
            self._refresh_col_activities()
            self._refresh_col_customers()

    def _on_col_clear(self):
        self.col_ef_date.setDate(QtCore.QDate.currentDate())
        self.col_ef_type.setCurrentIndex(0)
        self.col_ef_contact.clear()
        self.col_ef_notes.clear()
        self.col_ef_promised.setValue(0.0)
        self.col_ef_promise_date.setDate(QtCore.QDate.currentDate())
        self.col_ef_followup.setDate(QtCore.QDate.currentDate().addDays(7))
        self.col_ef_status.setCurrentIndex(0)
        self.col_ef_by.clear()
        self.col_act_tbl.clearSelection()
        self._col_selected_act_id = None

    # ── Tab change ────────────────────────────────────────────────────────────

    def _on_tab_change(self, idx):
        if idx == 5:    # A/R Aging
            self._refresh_aging()
        elif idx == 6:  # Collections
            self._refresh_col_customers()
        elif idx == 7:  # Risk Scoring
            self._refresh_risk()


class CreditDept(QtWidgets.QMainWindow):
    def __init__(self, initial_tab=None):
        super().__init__()
        self.setWindowTitle("Credit Department")
        self.resize(1150, 700)
        _apply_blue_palette(self)
        self.setCentralWidget(CreditDeptWidget(initial_tab=initial_tab))


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = CreditDept(sys.argv[1] if len(sys.argv) > 1 else None)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
