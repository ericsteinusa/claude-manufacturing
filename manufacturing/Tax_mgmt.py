"""
Tax_mgmt.py — Tax Management module
Tabs: Tax Calendar | Tax Filing | Tax Payments | Tax Reports
"""
import sys
from .db_pg import get_db
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets



def _conn():
    c = get_db()
    return c


def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS tax_calendar (
            id          SERIAL PRIMARY KEY,
            tax_type    TEXT    NOT NULL,
            description TEXT    DEFAULT '',
            due_date    TEXT    NOT NULL,
            period      TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'Pending',
            notes       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS tax_filing (
            id           SERIAL PRIMARY KEY,
            tax_type     TEXT    NOT NULL,
            jurisdiction TEXT    DEFAULT '',
            period       TEXT    DEFAULT '',
            amount_due   REAL    DEFAULT 0.0,
            amount_paid  REAL    DEFAULT 0.0,
            filed_date   TEXT    DEFAULT '',
            due_date     TEXT    DEFAULT '',
            status       TEXT    DEFAULT 'Pending',
            reference    TEXT    DEFAULT '',
            notes        TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS tax_payment (
            id           SERIAL PRIMARY KEY,
            filing_id    INTEGER DEFAULT NULL,
            tax_type     TEXT    NOT NULL,
            jurisdiction TEXT    DEFAULT '',
            period       TEXT    DEFAULT '',
            amount       REAL    DEFAULT 0.0,
            payment_date TEXT    DEFAULT '',
            method       TEXT    DEFAULT '',
            reference    TEXT    DEFAULT '',
            notes        TEXT    DEFAULT ''
        );
        """)
        if con.execute("SELECT COUNT(*) FROM tax_calendar").fetchone()[0] == 0:
            _seed_calendar(con)


def _seed_calendar(con):
    today = date.today()
    yr = today.year
    entries = [
        ("Federal Income Tax", "Quarterly estimated payment Q1", f"{yr}-04-15", f"Q1 {yr}", "Pending", ""),
        ("Federal Income Tax", "Quarterly estimated payment Q2", f"{yr}-06-15", f"Q2 {yr}", "Pending", ""),
        ("Federal Income Tax", "Quarterly estimated payment Q3", f"{yr}-09-15", f"Q3 {yr}", "Pending", ""),
        ("Federal Income Tax", "Quarterly estimated payment Q4", f"{yr + 1}-01-15", f"Q4 {yr}", "Pending", ""),
        ("Payroll Tax (941)", "Monthly deposit", f"{yr}-{today.month:02d}-15",
         f"{today.strftime('%b %Y')}", "Pending", ""),
        ("State Income Tax", "Annual filing", f"{yr}-04-15", f"FY {yr - 1}", "Pending", ""),
        ("Sales Tax", "Monthly filing", f"{yr}-{today.month:02d}-20", f"{today.strftime('%b %Y')}", "Pending", ""),
    ]
    con.executemany(
        "INSERT INTO tax_calendar (tax_type, description, due_date, period, status, notes) VALUES (%s,%s,%s,%s,%s,%s)",
        entries,
    )


BTN_STYLE = (
    "QPushButton{background-color:white;border:2px solid black;border-radius:8px;"
    "padding:4px 10px;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
    "QPushButton:disabled{background-color:#cccccc;color:#888888;}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid #aaa;background:white;}"
    "QTabBar::tab{background:#cce0ff;padding:6px 14px;font-weight:bold;}"
    "QTabBar::tab:selected{background:white;border-bottom:2px solid rgb(0,85,255);}"
)

TAX_TYPES = ["Federal Income Tax", "State Income Tax", "Payroll Tax (941)", "Sales Tax",
             "Property Tax", "Excise Tax", "Other"]
JURISDICTIONS = ["Federal", "State", "Local", "Multi-Jurisdiction"]
FILING_STATUSES = ["Pending", "Filed", "Late", "Amended", "Closed"]
PAYMENT_METHODS = ["ACH", "Check", "Wire Transfer", "Credit Card", "Online Portal"]
CAL_STATUSES = ["Pending", "Completed", "Late", "Waived"]

STATUS_COLORS = {
    "Pending": QtGui.QColor(255, 255, 210),
    "Filed": QtGui.QColor(200, 255, 210),
    "Completed": QtGui.QColor(200, 255, 210),
    "Late": QtGui.QColor(255, 200, 200),
    "Amended": QtGui.QColor(200, 230, 255),
    "Closed": QtGui.QColor(220, 220, 220),
    "Waived": QtGui.QColor(220, 220, 220),
}

_TAB_KEYS = {
    # Tab 0 – Tax Calendar
    'tax_cal': 0,
    # Tab 1 – Tax Filing
    'tax_filing': 1,
    # Tab 2 – Tax Payments
    'tax_pay': 2,
    # Tab 3 – Tax Reports
    'tax_rpts': 3,
}


def _apply_blue_palette(widget):
    pal = QtGui.QPalette()
    blue = QtGui.QColor(0, 85, 255)
    pal.setColor(QtGui.QPalette.ColorRole.Window, blue)
    pal.setColor(QtGui.QPalette.ColorRole.Button, blue)
    pal.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(255, 255, 255))
    pal.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(0, 0, 0))
    pal.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(0, 0, 0))
    widget.setPalette(pal)


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft):
    item = QtWidgets.QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
    item.setTextAlignment(align | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return item


def _ro_r(text):
    return _ro(text, QtCore.Qt.AlignmentFlag.AlignRight)


def _money(v):
    try:
        return f"{float(v):,.2f}" if v else "0.00"
    except Exception:
        return "0.00"


def _color_row(table, row, status):
    color = STATUS_COLORS.get(status)
    if color:
        for c in range(table.columnCount()):
            it = table.item(row, c)
            if it:
                it.setBackground(color)


# ══════════════════════════════════════════════════════════════════════════════
# Calendar Entry Dialog
# ══════════════════════════════════════════════════════════════════════════════
class CalendarDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, row_data=None):
        super().__init__(parent)
        self.setWindowTitle("Tax Calendar Entry")
        self.setMinimumWidth(420)
        v = QtWidgets.QVBoxLayout(self)
        fl = QtWidgets.QFormLayout()

        self.ef_type = QtWidgets.QComboBox()
        self.ef_type.addItems(TAX_TYPES)
        self.ef_type.setEditable(True)

        self.ef_desc = QtWidgets.QLineEdit()
        self.ef_due = QtWidgets.QDateEdit(calendarPopup=True)
        self.ef_due.setDisplayFormat("yyyy-MM-dd")
        self.ef_due.setDate(QtCore.QDate.currentDate())
        self.ef_period = QtWidgets.QLineEdit()
        self.ef_status = QtWidgets.QComboBox()
        self.ef_status.addItems(CAL_STATUSES)
        self.ef_notes = QtWidgets.QLineEdit()

        fl.addRow("Tax Type:", self.ef_type)
        fl.addRow("Description:", self.ef_desc)
        fl.addRow("Due Date:", self.ef_due)
        fl.addRow("Period:", self.ef_period)
        fl.addRow("Status:", self.ef_status)
        fl.addRow("Notes:", self.ef_notes)
        v.addLayout(fl)

        bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        if row_data:
            self.ef_type.setCurrentText(row_data["tax_type"])
            self.ef_desc.setText(row_data["description"])
            self.ef_due.setDate(QtCore.QDate.fromString(row_data["due_date"], "yyyy-MM-dd"))
            self.ef_period.setText(row_data["period"])
            self.ef_status.setCurrentText(row_data["status"])
            self.ef_notes.setText(row_data["notes"])

    def values(self):
        return {
            "tax_type": self.ef_type.currentText().strip(),
            "description": self.ef_desc.text().strip(),
            "due_date": self.ef_due.date().toString("yyyy-MM-dd"),
            "period": self.ef_period.text().strip(),
            "status": self.ef_status.currentText(),
            "notes": self.ef_notes.text().strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Filing Dialog
# ══════════════════════════════════════════════════════════════════════════════
class FilingDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, row_data=None):
        super().__init__(parent)
        self.setWindowTitle("Tax Filing")
        self.setMinimumWidth(440)
        v = QtWidgets.QVBoxLayout(self)
        fl = QtWidgets.QFormLayout()

        self.ef_type = QtWidgets.QComboBox()
        self.ef_type.addItems(TAX_TYPES)
        self.ef_type.setEditable(True)
        self.ef_jur = QtWidgets.QComboBox()
        self.ef_jur.addItems(JURISDICTIONS)
        self.ef_jur.setEditable(True)
        self.ef_period = QtWidgets.QLineEdit()
        self.ef_amount_due = QtWidgets.QDoubleSpinBox()
        self.ef_amount_due.setRange(0, 999_999_999)
        self.ef_amount_due.setDecimals(2)
        self.ef_amount_due.setGroupSeparatorShown(True)
        self.ef_amount_paid = QtWidgets.QDoubleSpinBox()
        self.ef_amount_paid.setRange(0, 999_999_999)
        self.ef_amount_paid.setDecimals(2)
        self.ef_amount_paid.setGroupSeparatorShown(True)
        self.ef_due_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.ef_due_date.setDisplayFormat("yyyy-MM-dd")
        self.ef_due_date.setDate(QtCore.QDate.currentDate())
        self.ef_filed_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.ef_filed_date.setDisplayFormat("yyyy-MM-dd")
        self.ef_filed_date.setDate(QtCore.QDate.currentDate())
        self.ef_status = QtWidgets.QComboBox()
        self.ef_status.addItems(FILING_STATUSES)
        self.ef_ref = QtWidgets.QLineEdit()
        self.ef_notes = QtWidgets.QLineEdit()

        fl.addRow("Tax Type:", self.ef_type)
        fl.addRow("Jurisdiction:", self.ef_jur)
        fl.addRow("Period:", self.ef_period)
        fl.addRow("Amount Due ($):", self.ef_amount_due)
        fl.addRow("Amount Paid ($):", self.ef_amount_paid)
        fl.addRow("Due Date:", self.ef_due_date)
        fl.addRow("Filed Date:", self.ef_filed_date)
        fl.addRow("Status:", self.ef_status)
        fl.addRow("Reference #:", self.ef_ref)
        fl.addRow("Notes:", self.ef_notes)
        v.addLayout(fl)

        bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        if row_data:
            self.ef_type.setCurrentText(row_data["tax_type"])
            self.ef_jur.setCurrentText(row_data["jurisdiction"])
            self.ef_period.setText(row_data["period"])
            self.ef_amount_due.setValue(float(row_data["amount_due"] or 0))
            self.ef_amount_paid.setValue(float(row_data["amount_paid"] or 0))
            if row_data["due_date"]:
                self.ef_due_date.setDate(QtCore.QDate.fromString(row_data["due_date"], "yyyy-MM-dd"))
            if row_data["filed_date"]:
                self.ef_filed_date.setDate(QtCore.QDate.fromString(row_data["filed_date"], "yyyy-MM-dd"))
            self.ef_status.setCurrentText(row_data["status"])
            self.ef_ref.setText(row_data["reference"])
            self.ef_notes.setText(row_data["notes"])

    def values(self):
        return {
            "tax_type": self.ef_type.currentText().strip(),
            "jurisdiction": self.ef_jur.currentText().strip(),
            "period": self.ef_period.text().strip(),
            "amount_due": self.ef_amount_due.value(),
            "amount_paid": self.ef_amount_paid.value(),
            "due_date": self.ef_due_date.date().toString("yyyy-MM-dd"),
            "filed_date": self.ef_filed_date.date().toString("yyyy-MM-dd"),
            "status": self.ef_status.currentText(),
            "reference": self.ef_ref.text().strip(),
            "notes": self.ef_notes.text().strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Payment Dialog
# ══════════════════════════════════════════════════════════════════════════════
class PaymentDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, row_data=None):
        super().__init__(parent)
        self.setWindowTitle("Tax Payment")
        self.setMinimumWidth(420)
        v = QtWidgets.QVBoxLayout(self)
        fl = QtWidgets.QFormLayout()

        self.ef_type = QtWidgets.QComboBox()
        self.ef_type.addItems(TAX_TYPES)
        self.ef_type.setEditable(True)
        self.ef_jur = QtWidgets.QComboBox()
        self.ef_jur.addItems(JURISDICTIONS)
        self.ef_jur.setEditable(True)
        self.ef_period = QtWidgets.QLineEdit()
        self.ef_amount = QtWidgets.QDoubleSpinBox()
        self.ef_amount.setRange(0, 999_999_999)
        self.ef_amount.setDecimals(2)
        self.ef_amount.setGroupSeparatorShown(True)
        self.ef_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.ef_date.setDisplayFormat("yyyy-MM-dd")
        self.ef_date.setDate(QtCore.QDate.currentDate())
        self.ef_method = QtWidgets.QComboBox()
        self.ef_method.addItems(PAYMENT_METHODS)
        self.ef_ref = QtWidgets.QLineEdit()
        self.ef_notes = QtWidgets.QLineEdit()

        fl.addRow("Tax Type:", self.ef_type)
        fl.addRow("Jurisdiction:", self.ef_jur)
        fl.addRow("Period:", self.ef_period)
        fl.addRow("Amount ($):", self.ef_amount)
        fl.addRow("Payment Date:", self.ef_date)
        fl.addRow("Payment Method:", self.ef_method)
        fl.addRow("Reference #:", self.ef_ref)
        fl.addRow("Notes:", self.ef_notes)
        v.addLayout(fl)

        bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        if row_data:
            self.ef_type.setCurrentText(row_data["tax_type"])
            self.ef_jur.setCurrentText(row_data["jurisdiction"])
            self.ef_period.setText(row_data["period"])
            self.ef_amount.setValue(float(row_data["amount"] or 0))
            if row_data["payment_date"]:
                self.ef_date.setDate(QtCore.QDate.fromString(row_data["payment_date"], "yyyy-MM-dd"))
            self.ef_method.setCurrentText(row_data["method"])
            self.ef_ref.setText(row_data["reference"])
            self.ef_notes.setText(row_data["notes"])

    def values(self):
        return {
            "tax_type": self.ef_type.currentText().strip(),
            "jurisdiction": self.ef_jur.currentText().strip(),
            "period": self.ef_period.text().strip(),
            "amount": self.ef_amount.value(),
            "payment_date": self.ef_date.date().toString("yyyy-MM-dd"),
            "method": self.ef_method.currentText(),
            "reference": self.ef_ref.text().strip(),
            "notes": self.ef_notes.text().strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Main Tax Management Window
# ══════════════════════════════════════════════════════════════════════════════
class TaxMgmtWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, initial_tab=None):
        super().__init__(parent)
        init_db()
        _apply_blue_palette(self)
        self._build_ui()
        self._refresh_calendar()
        self._refresh_filings()
        self._refresh_payments()
        self._refresh_reports()
        if initial_tab in _TAB_KEYS:
            self.tabs.setCurrentIndex(_TAB_KEYS[initial_tab])

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        title = QtWidgets.QLabel("Tax Management")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;color:white;padding:4px;")
        root.addWidget(title)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_calendar_tab(), "Tax Calendar")
        self.tabs.addTab(self._build_filing_tab(), "Tax Filing")
        self.tabs.addTab(self._build_payment_tab(), "Tax Payments")
        self.tabs.addTab(self._build_reports_tab(), "Tax Reports")

    # ── Tax Calendar tab ──────────────────────────────────────────────────────
    def _build_calendar_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Status:"))
        self.cal_status_filter = QtWidgets.QComboBox()
        self.cal_status_filter.addItems(["All Statuses"] + CAL_STATUSES)
        self.cal_status_filter.currentIndexChanged.connect(self._refresh_calendar)
        fb.addWidget(self.cal_status_filter)
        fb.addWidget(QtWidgets.QLabel("Tax Type:"))
        self.cal_type_filter = QtWidgets.QComboBox()
        self.cal_type_filter.addItems(["All Types"] + TAX_TYPES)
        self.cal_type_filter.currentIndexChanged.connect(self._refresh_calendar)
        fb.addWidget(self.cal_type_filter)
        fb.addStretch()
        v.addLayout(fb)

        self.cal_tbl = QtWidgets.QTableWidget(0, 6)
        self.cal_tbl.setHorizontalHeaderLabels(
            ["ID", "Tax Type", "Description", "Due Date", "Period", "Status"]
        )
        self.cal_tbl.setColumnWidth(0, 45)
        self.cal_tbl.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.cal_tbl.setColumnWidth(1, 160)
        self.cal_tbl.setColumnWidth(3, 95)
        self.cal_tbl.setColumnWidth(4, 90)
        self.cal_tbl.setColumnWidth(5, 90)
        self.cal_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.cal_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cal_tbl.setAlternatingRowColors(True)
        self.cal_tbl.verticalHeader().setDefaultSectionSize(24)
        self.cal_tbl.itemDoubleClicked.connect(self._edit_calendar_entry)
        v.addWidget(self.cal_tbl)

        bb = QtWidgets.QHBoxLayout()
        for label, slot in [("Add Entry", self._add_calendar_entry),
                            ("Edit Entry", self._edit_calendar_entry),
                            ("Delete Entry", self._delete_calendar_entry),
                            ("Mark Completed", self._mark_cal_completed)]:
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(BTN_STYLE)
            btn.clicked.connect(slot)
            bb.addWidget(btn)
        bb.addStretch()
        v.addLayout(bb)
        return w

    def _refresh_calendar(self):
        status_f = self.cal_status_filter.currentText() if hasattr(self, 'cal_status_filter') else "All Statuses"
        type_f = self.cal_type_filter.currentText() if hasattr(self, 'cal_type_filter') else "All Types"
        with _conn() as con:
            q = "SELECT id, tax_type, description, due_date, period, status FROM tax_calendar WHERE 1=1"
            params = []
            if status_f != "All Statuses":
                q += " AND status=%s"
                params.append(status_f)
            if type_f != "All Types":
                q += " AND tax_type=%s"
                params.append(type_f)
            q += " ORDER BY due_date"
            rows = con.execute(q, params).fetchall()
        self.cal_tbl.setRowCount(0)
        for row in rows:
            r = self.cal_tbl.rowCount()
            self.cal_tbl.insertRow(r)
            self.cal_tbl.setItem(r, 0, _ro(row["id"], QtCore.Qt.AlignmentFlag.AlignRight))
            self.cal_tbl.setItem(r, 1, _ro(row["tax_type"]))
            self.cal_tbl.setItem(r, 2, _ro(row["description"]))
            self.cal_tbl.setItem(r, 3, _ro(row["due_date"]))
            self.cal_tbl.setItem(r, 4, _ro(row["period"]))
            self.cal_tbl.setItem(r, 5, _ro(row["status"]))
            _color_row(self.cal_tbl, r, row["status"])

    def _add_calendar_entry(self, *_):
        dlg = CalendarDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute(
                    "INSERT INTO tax_calendar (tax_type, description, due_date, period, status, notes) VALUES (%s,%s,%s,%s,%s,%s)",
                    (v["tax_type"], v["description"], v["due_date"], v["period"], v["status"], v["notes"])
                )
            self._refresh_calendar()

    def _edit_calendar_entry(self, *_):
        rows = self.cal_tbl.selectedItems()
        if not rows:
            return
        row_id = int(self.cal_tbl.item(self.cal_tbl.currentRow(), 0).text())
        with _conn() as con:
            rd = con.execute("SELECT * FROM tax_calendar WHERE id=%s", (row_id,)).fetchone()
        if not rd:
            return
        dlg = CalendarDialog(self, row_data=rd)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute(
                    "UPDATE tax_calendar SET tax_type=%s, description=%s, due_date=%s, period=%s, status=%s, notes=%s WHERE id=%s",
                    (v["tax_type"], v["description"], v["due_date"], v["period"], v["status"], v["notes"], row_id)
                )
            self._refresh_calendar()

    def _delete_calendar_entry(self, *_):
        rows = self.cal_tbl.selectedItems()
        if not rows:
            return
        row_id = int(self.cal_tbl.item(self.cal_tbl.currentRow(), 0).text())
        if QtWidgets.QMessageBox.question(self, "Delete", "Delete this calendar entry%s") == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute("DELETE FROM tax_calendar WHERE id=%s", (row_id,))
            self._refresh_calendar()

    def _mark_cal_completed(self, *_):
        rows = self.cal_tbl.selectedItems()
        if not rows:
            return
        row_id = int(self.cal_tbl.item(self.cal_tbl.currentRow(), 0).text())
        with _conn() as con:
            con.execute("UPDATE tax_calendar SET status='Completed' WHERE id=%s", (row_id,))
        self._refresh_calendar()

    # ── Tax Filing tab ────────────────────────────────────────────────────────
    def _build_filing_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Status:"))
        self.fil_status_filter = QtWidgets.QComboBox()
        self.fil_status_filter.addItems(["All Statuses"] + FILING_STATUSES)
        self.fil_status_filter.currentIndexChanged.connect(self._refresh_filings)
        fb.addWidget(self.fil_status_filter)
        fb.addWidget(QtWidgets.QLabel("Tax Type:"))
        self.fil_type_filter = QtWidgets.QComboBox()
        self.fil_type_filter.addItems(["All Types"] + TAX_TYPES)
        self.fil_type_filter.currentIndexChanged.connect(self._refresh_filings)
        fb.addWidget(self.fil_type_filter)
        fb.addStretch()
        v.addLayout(fb)

        self.fil_tbl = QtWidgets.QTableWidget(0, 9)
        self.fil_tbl.setHorizontalHeaderLabels(
            ["ID", "Tax Type", "Jurisdiction", "Period", "Amount Due", "Amount Paid", "Due Date", "Filed Date", "Status"]
        )
        self.fil_tbl.setColumnWidth(0, 45)
        self.fil_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.fil_tbl.setColumnWidth(2, 110)
        self.fil_tbl.setColumnWidth(3, 80)
        self.fil_tbl.setColumnWidth(4, 100)
        self.fil_tbl.setColumnWidth(5, 100)
        self.fil_tbl.setColumnWidth(6, 90)
        self.fil_tbl.setColumnWidth(7, 90)
        self.fil_tbl.setColumnWidth(8, 80)
        self.fil_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.fil_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.fil_tbl.setAlternatingRowColors(True)
        self.fil_tbl.verticalHeader().setDefaultSectionSize(24)
        self.fil_tbl.itemDoubleClicked.connect(self._edit_filing)
        v.addWidget(self.fil_tbl)

        self.fil_total_lbl = QtWidgets.QLabel("Total Due: $0.00  |  Total Paid: $0.00  |  Balance: $0.00")
        self.fil_total_lbl.setStyleSheet("font-weight:bold;padding:4px;")
        v.addWidget(self.fil_total_lbl)

        bb = QtWidgets.QHBoxLayout()
        for label, slot in [("Add Filing", self._add_filing),
                            ("Edit Filing", self._edit_filing),
                            ("Delete Filing", self._delete_filing),
                            ("Mark Filed", self._mark_filed)]:
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(BTN_STYLE)
            btn.clicked.connect(slot)
            bb.addWidget(btn)
        bb.addStretch()
        v.addLayout(bb)
        return w

    def _refresh_filings(self):
        status_f = self.fil_status_filter.currentText() if hasattr(self, 'fil_status_filter') else "All Statuses"
        type_f = self.fil_type_filter.currentText() if hasattr(self, 'fil_type_filter') else "All Types"
        with _conn() as con:
            q = "SELECT * FROM tax_filing WHERE 1=1"
            params = []
            if status_f != "All Statuses":
                q += " AND status=%s"
                params.append(status_f)
            if type_f != "All Types":
                q += " AND tax_type=%s"
                params.append(type_f)
            q += " ORDER BY due_date DESC"
            rows = con.execute(q, params).fetchall()
        self.fil_tbl.setRowCount(0)
        total_due = total_paid = 0.0
        for row in rows:
            r = self.fil_tbl.rowCount()
            self.fil_tbl.insertRow(r)
            self.fil_tbl.setItem(r, 0, _ro(row["id"], QtCore.Qt.AlignmentFlag.AlignRight))
            self.fil_tbl.setItem(r, 1, _ro(row["tax_type"]))
            self.fil_tbl.setItem(r, 2, _ro(row["jurisdiction"]))
            self.fil_tbl.setItem(r, 3, _ro(row["period"]))
            self.fil_tbl.setItem(r, 4, _ro_r(_money(row["amount_due"])))
            self.fil_tbl.setItem(r, 5, _ro_r(_money(row["amount_paid"])))
            self.fil_tbl.setItem(r, 6, _ro(row["due_date"]))
            self.fil_tbl.setItem(r, 7, _ro(row["filed_date"]))
            self.fil_tbl.setItem(r, 8, _ro(row["status"]))
            _color_row(self.fil_tbl, r, row["status"])
            total_due += float(row["amount_due"] or 0)
            total_paid += float(row["amount_paid"] or 0)
        bal = total_due - total_paid
        self.fil_total_lbl.setText(
            f"Total Due: ${total_due:,.2f}  |  Total Paid: ${total_paid:,.2f}  |  Balance: ${bal:,.2f}"
        )

    def _add_filing(self, *_):
        dlg = FilingDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute(
                    "INSERT INTO tax_filing (tax_type,jurisdiction,period,amount_due,amount_paid,due_date,filed_date,status,reference,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (v["tax_type"], v["jurisdiction"], v["period"], v["amount_due"], v["amount_paid"],
                     v["due_date"], v["filed_date"], v["status"], v["reference"], v["notes"])
                )
            self._refresh_filings()
            self._refresh_reports()

    def _edit_filing(self, *_):
        if not self.fil_tbl.selectedItems():
            return
        row_id = int(self.fil_tbl.item(self.fil_tbl.currentRow(), 0).text())
        with _conn() as con:
            rd = con.execute("SELECT * FROM tax_filing WHERE id=%s", (row_id,)).fetchone()
        if not rd:
            return
        dlg = FilingDialog(self, row_data=rd)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute(
                    "UPDATE tax_filing SET tax_type=%s,jurisdiction=%s,period=%s,amount_due=%s,amount_paid=%s,due_date=%s,filed_date=%s,status=%s,reference=%s,notes=%s WHERE id=%s",
                    (v["tax_type"], v["jurisdiction"], v["period"], v["amount_due"], v["amount_paid"],
                     v["due_date"], v["filed_date"], v["status"], v["reference"], v["notes"], row_id)
                )
            self._refresh_filings()
            self._refresh_reports()

    def _delete_filing(self, *_):
        if not self.fil_tbl.selectedItems():
            return
        row_id = int(self.fil_tbl.item(self.fil_tbl.currentRow(), 0).text())
        if QtWidgets.QMessageBox.question(self, "Delete", "Delete this filing%s") == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute("DELETE FROM tax_filing WHERE id=%s", (row_id,))
            self._refresh_filings()
            self._refresh_reports()

    def _mark_filed(self, *_):
        if not self.fil_tbl.selectedItems():
            return
        row_id = int(self.fil_tbl.item(self.fil_tbl.currentRow(), 0).text())
        today = date.today().isoformat()
        with _conn() as con:
            con.execute("UPDATE tax_filing SET status='Filed', filed_date=%s WHERE id=%s", (today, row_id))
        self._refresh_filings()
        self._refresh_reports()

    # ── Tax Payments tab ──────────────────────────────────────────────────────
    def _build_payment_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Tax Type:"))
        self.pay_type_filter = QtWidgets.QComboBox()
        self.pay_type_filter.addItems(["All Types"] + TAX_TYPES)
        self.pay_type_filter.currentIndexChanged.connect(self._refresh_payments)
        fb.addWidget(self.pay_type_filter)
        fb.addWidget(QtWidgets.QLabel("Method:"))
        self.pay_method_filter = QtWidgets.QComboBox()
        self.pay_method_filter.addItems(["All Methods"] + PAYMENT_METHODS)
        self.pay_method_filter.currentIndexChanged.connect(self._refresh_payments)
        fb.addWidget(self.pay_method_filter)
        fb.addStretch()
        v.addLayout(fb)

        self.pay_tbl = QtWidgets.QTableWidget(0, 8)
        self.pay_tbl.setHorizontalHeaderLabels(
            ["ID", "Tax Type", "Jurisdiction", "Period", "Amount", "Payment Date", "Method", "Reference"]
        )
        self.pay_tbl.setColumnWidth(0, 45)
        self.pay_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.pay_tbl.setColumnWidth(2, 110)
        self.pay_tbl.setColumnWidth(3, 80)
        self.pay_tbl.setColumnWidth(4, 100)
        self.pay_tbl.setColumnWidth(5, 100)
        self.pay_tbl.setColumnWidth(6, 110)
        self.pay_tbl.setColumnWidth(7, 120)
        self.pay_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.pay_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pay_tbl.setAlternatingRowColors(True)
        self.pay_tbl.verticalHeader().setDefaultSectionSize(24)
        self.pay_tbl.itemDoubleClicked.connect(self._edit_payment)
        v.addWidget(self.pay_tbl)

        self.pay_total_lbl = QtWidgets.QLabel("Total Payments: $0.00")
        self.pay_total_lbl.setStyleSheet("font-weight:bold;padding:4px;")
        v.addWidget(self.pay_total_lbl)

        bb = QtWidgets.QHBoxLayout()
        for label, slot in [("Add Payment", self._add_payment),
                            ("Edit Payment", self._edit_payment),
                            ("Delete Payment", self._delete_payment)]:
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(BTN_STYLE)
            btn.clicked.connect(slot)
            bb.addWidget(btn)
        bb.addStretch()
        v.addLayout(bb)
        return w

    def _refresh_payments(self):
        type_f = self.pay_type_filter.currentText() if hasattr(self, 'pay_type_filter') else "All Types"
        method_f = self.pay_method_filter.currentText() if hasattr(self, 'pay_method_filter') else "All Methods"
        with _conn() as con:
            q = "SELECT * FROM tax_payment WHERE 1=1"
            params = []
            if type_f != "All Types":
                q += " AND tax_type=%s"
                params.append(type_f)
            if method_f != "All Methods":
                q += " AND method=%s"
                params.append(method_f)
            q += " ORDER BY payment_date DESC"
            rows = con.execute(q, params).fetchall()
        self.pay_tbl.setRowCount(0)
        total = 0.0
        for row in rows:
            r = self.pay_tbl.rowCount()
            self.pay_tbl.insertRow(r)
            self.pay_tbl.setItem(r, 0, _ro(row["id"], QtCore.Qt.AlignmentFlag.AlignRight))
            self.pay_tbl.setItem(r, 1, _ro(row["tax_type"]))
            self.pay_tbl.setItem(r, 2, _ro(row["jurisdiction"]))
            self.pay_tbl.setItem(r, 3, _ro(row["period"]))
            self.pay_tbl.setItem(r, 4, _ro_r(_money(row["amount"])))
            self.pay_tbl.setItem(r, 5, _ro(row["payment_date"]))
            self.pay_tbl.setItem(r, 6, _ro(row["method"]))
            self.pay_tbl.setItem(r, 7, _ro(row["reference"]))
            total += float(row["amount"] or 0)
        self.pay_total_lbl.setText(f"Total Payments: ${total:,.2f}")

    def _add_payment(self, *_):
        dlg = PaymentDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute(
                    "INSERT INTO tax_payment (tax_type,jurisdiction,period,amount,payment_date,method,reference,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (v["tax_type"], v["jurisdiction"], v["period"], v["amount"],
                     v["payment_date"], v["method"], v["reference"], v["notes"])
                )
            self._refresh_payments()
            self._refresh_reports()

    def _edit_payment(self, *_):
        if not self.pay_tbl.selectedItems():
            return
        row_id = int(self.pay_tbl.item(self.pay_tbl.currentRow(), 0).text())
        with _conn() as con:
            rd = con.execute("SELECT * FROM tax_payment WHERE id=%s", (row_id,)).fetchone()
        if not rd:
            return
        dlg = PaymentDialog(self, row_data=rd)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute(
                    "UPDATE tax_payment SET tax_type=%s,jurisdiction=%s,period=%s,amount=%s,payment_date=%s,method=%s,reference=%s,notes=%s WHERE id=%s",
                    (v["tax_type"], v["jurisdiction"], v["period"], v["amount"],
                     v["payment_date"], v["method"], v["reference"], v["notes"], row_id)
                )
            self._refresh_payments()
            self._refresh_reports()

    def _delete_payment(self, *_):
        if not self.pay_tbl.selectedItems():
            return
        row_id = int(self.pay_tbl.item(self.pay_tbl.currentRow(), 0).text())
        if QtWidgets.QMessageBox.question(self, "Delete", "Delete this payment%s") == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute("DELETE FROM tax_payment WHERE id=%s", (row_id,))
            self._refresh_payments()
            self._refresh_reports()

    # ── Tax Reports tab ───────────────────────────────────────────────────────
    def _build_reports_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        hdr = QtWidgets.QLabel("Tax Summary Report")
        hdr.setStyleSheet("font-size:16px;font-weight:bold;padding:4px;")
        v.addWidget(hdr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # Filing summary by type
        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.addWidget(QtWidgets.QLabel("<b>Filings by Tax Type</b>"))
        self.rpt_filing_tbl = QtWidgets.QTableWidget(0, 4)
        self.rpt_filing_tbl.setHorizontalHeaderLabels(["Tax Type", "Count", "Total Due", "Total Paid"])
        self.rpt_filing_tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rpt_filing_tbl.setColumnWidth(1, 55)
        self.rpt_filing_tbl.setColumnWidth(2, 100)
        self.rpt_filing_tbl.setColumnWidth(3, 100)
        self.rpt_filing_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rpt_filing_tbl.setAlternatingRowColors(True)
        self.rpt_filing_tbl.verticalHeader().setDefaultSectionSize(24)
        lv.addWidget(self.rpt_filing_tbl)
        splitter.addWidget(left)

        # Payment summary by type
        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.addWidget(QtWidgets.QLabel("<b>Payments by Tax Type</b>"))
        self.rpt_payment_tbl = QtWidgets.QTableWidget(0, 3)
        self.rpt_payment_tbl.setHorizontalHeaderLabels(["Tax Type", "Count", "Total Paid"])
        self.rpt_payment_tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rpt_payment_tbl.setColumnWidth(1, 55)
        self.rpt_payment_tbl.setColumnWidth(2, 100)
        self.rpt_payment_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rpt_payment_tbl.setAlternatingRowColors(True)
        self.rpt_payment_tbl.verticalHeader().setDefaultSectionSize(24)
        rv.addWidget(self.rpt_payment_tbl)
        splitter.addWidget(right)

        v.addWidget(splitter)

        # Upcoming deadlines
        v.addWidget(QtWidgets.QLabel("<b>Upcoming Deadlines (next 60 days)</b>"))
        self.rpt_upcoming_tbl = QtWidgets.QTableWidget(0, 4)
        self.rpt_upcoming_tbl.setHorizontalHeaderLabels(["Tax Type", "Description", "Due Date", "Status"])
        self.rpt_upcoming_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rpt_upcoming_tbl.setColumnWidth(0, 160)
        self.rpt_upcoming_tbl.setColumnWidth(2, 90)
        self.rpt_upcoming_tbl.setColumnWidth(3, 90)
        self.rpt_upcoming_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rpt_upcoming_tbl.setAlternatingRowColors(True)
        self.rpt_upcoming_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.rpt_upcoming_tbl)

        btn = QtWidgets.QPushButton("Refresh Report")
        btn.setStyleSheet(BTN_STYLE)
        btn.clicked.connect(self._refresh_reports)
        v.addWidget(btn)
        return w

    def _refresh_reports(self):
        if not hasattr(self, 'rpt_filing_tbl'):
            return
        with _conn() as con:
            fil_rows = con.execute(
                "SELECT tax_type, COUNT(*) as cnt, SUM(amount_due) as due, SUM(amount_paid) as paid FROM tax_filing GROUP BY tax_type ORDER BY tax_type"
            ).fetchall()
            pay_rows = con.execute(
                "SELECT tax_type, COUNT(*) as cnt, SUM(amount) as total FROM tax_payment GROUP BY tax_type ORDER BY tax_type"
            ).fetchall()
            today = date.today().isoformat()
            from datetime import timedelta
            cutoff = (date.today() + timedelta(days=60)).isoformat()
            upcoming = con.execute(
                "SELECT tax_type, description, due_date, status FROM tax_calendar WHERE due_date BETWEEN %s AND %s ORDER BY due_date",
                (today, cutoff)
            ).fetchall()

        self.rpt_filing_tbl.setRowCount(0)
        for row in fil_rows:
            r = self.rpt_filing_tbl.rowCount()
            self.rpt_filing_tbl.insertRow(r)
            self.rpt_filing_tbl.setItem(r, 0, _ro(row["tax_type"]))
            self.rpt_filing_tbl.setItem(r, 1, _ro_r(str(row["cnt"])))
            self.rpt_filing_tbl.setItem(r, 2, _ro_r(_money(row["due"])))
            self.rpt_filing_tbl.setItem(r, 3, _ro_r(_money(row["paid"])))

        self.rpt_payment_tbl.setRowCount(0)
        for row in pay_rows:
            r = self.rpt_payment_tbl.rowCount()
            self.rpt_payment_tbl.insertRow(r)
            self.rpt_payment_tbl.setItem(r, 0, _ro(row["tax_type"]))
            self.rpt_payment_tbl.setItem(r, 1, _ro_r(str(row["cnt"])))
            self.rpt_payment_tbl.setItem(r, 2, _ro_r(_money(row["total"])))

        self.rpt_upcoming_tbl.setRowCount(0)
        for row in upcoming:
            r = self.rpt_upcoming_tbl.rowCount()
            self.rpt_upcoming_tbl.insertRow(r)
            self.rpt_upcoming_tbl.setItem(r, 0, _ro(row["tax_type"]))
            self.rpt_upcoming_tbl.setItem(r, 1, _ro(row["description"]))
            self.rpt_upcoming_tbl.setItem(r, 2, _ro(row["due_date"]))
            self.rpt_upcoming_tbl.setItem(r, 3, _ro(row["status"]))
            _color_row(self.rpt_upcoming_tbl, r, row["status"])


class TaxWindow(QtWidgets.QMainWindow):
    def __init__(self, initial_tab=None):
        super().__init__()
        self.setWindowTitle("Tax Management")
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self.setCentralWidget(TaxMgmtWidget(initial_tab=initial_tab))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = TaxWindow(sys.argv[1] if len(sys.argv) > 1 else None)
    win.show()
    sys.exit(app.exec())
