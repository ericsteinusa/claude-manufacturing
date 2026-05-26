import sys
import sqlite3
from .db_connection import get_db_connection
import os
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets
from gl_utils import post_gl_entry


BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton%(hover)s{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE = "QLineEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}"
COMBO_STYLE = "QComboBox{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}QComboBox QAbstractItemView{background-color%(white)s;}"
DATE_STYLE = "QDateEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 4px;}"
SPIN_STYLE = "QDoubleSpinBox{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 4px;}"
LABEL_STYLE = "color%(white)s;font-size:13px;"
TAB_STYLE = ("QTabWidget:%(pane)s{border:1px solid black;}"
             "QTabBar:%(tab)s{background%(white)s; border:2px solid black; padding:6px 18px;"
             " border-bottom%(none)s; border-radius:4px 4px 0 0;}"
             "QTabBar:%(tab)s%(selected)s{background%(rgb)s(85,255,255); font-weight%(bold)s;}"
             "QTabBar:%(tab)s%(hover)s{background%(rgb)s(85,255,255);}")

STATUS_COLORS = {
    "open": QtGui.QColor(255, 255, 255),
    "partial": QtGui.QColor(255, 243, 205),
    "paid": QtGui.QColor(212, 237, 218),
    "void": QtGui.QColor(220, 220, 220),
}


def get_db():
    conn = get_db_connection()
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer (
            id           SERIAL PRIMARY KEY,
            first_name   TEXT,
            last_name    TEXT,
            company_name TEXT,
            phone_number TEXT,
            address      TEXT,
            city         TEXT,
            state        TEXT,
            zip_code     TEXT,
            email        TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ar_invoice (
            id             SERIAL PRIMARY KEY,
            customer_id    INTEGER NOT NULL REFERENCES customer(id),
            invoice_number TEXT NOT NULL UNIQUE,
            invoice_date   TEXT NOT NULL,
            due_date       TEXT NOT NULL,
            amount         REAL NOT NULL,
            description    TEXT,
            status         TEXT NOT NULL DEFAULT 'open'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ar_payment (
            id             SERIAL PRIMARY KEY,
            invoice_id     INTEGER NOT NULL REFERENCES ar_invoice(id),
            payment_date   TEXT NOT NULL,
            amount         REAL NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'Check',
            reference      TEXT,
            notes          TEXT
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
    """Return primary display string for a customer row."""
    company = (row["company_name"] or "").strip()
    contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    return company if company else contact


def _next_inv_num():
    yr = date.today().year
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM ar_invoice WHERE invoice_number LIKE %s",
                     (f"AR-{yr}-%",)).fetchone()[0]
    conn.close()
    return f"AR-{yr}-{n + 1:04d}"


# ── Dialogs ────────────────────────────────────────────────────────────────

class NewInvoiceDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, preselect_customer_id=None):
        super().__init__(parent)
        self.setWindowTitle("New Invoice")
        self.setFixedSize(480, 320)
        _apply_blue_palette(self)
        self._preselect = preselect_customer_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("New Accounts Receivable Invoice")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color%(white)s;font-size:15px;font-weight%(bold)s;")
        layout.addWidget(title)

        def row(lbl_text, widget, lbl_w=110):
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
            "SELECT id, first_name, last_name, company_name FROM customer ORDER BY company_name, last_name, first_name"
        ).fetchall()
        conn.close()
        for c in customers:
            self.cust_combo.addItem(_customer_display(c), c["id"])
        if self._preselect:
            idx = self.cust_combo.findData(self._preselect)
            if idx >= 0:
                self.cust_combo.setCurrentIndex(idx)
        layout.addLayout(row("Customer:", self.cust_combo))

        self.inv_num = QtWidgets.QLineEdit(_next_inv_num())
        self.inv_num.setStyleSheet(INPUT_STYLE)
        layout.addLayout(row("Invoice #:", self.inv_num))

        self.inv_date = QtWidgets.QDateEdit()
        self.inv_date.setStyleSheet(DATE_STYLE)
        self.inv_date.setCalendarPopup(True)
        self.inv_date.setDisplayFormat("MM/dd/yyyy")
        self.inv_date.setDate(QtCore.QDate.currentDate())
        layout.addLayout(row("Invoice Date:", self.inv_date))

        self.due_date = QtWidgets.QDateEdit()
        self.due_date.setStyleSheet(DATE_STYLE)
        self.due_date.setCalendarPopup(True)
        self.due_date.setDisplayFormat("MM/dd/yyyy")
        self.due_date.setDate(QtCore.QDate.currentDate().addDays(30))
        layout.addLayout(row("Due Date:", self.due_date))

        self.amount = QtWidgets.QDoubleSpinBox()
        self.amount.setStyleSheet(SPIN_STYLE)
        self.amount.setRange(0, 99999999)
        self.amount.setDecimals(2)
        self.amount.setPrefix("$ ")
        layout.addLayout(row("Amount:", self.amount))

        self.desc = QtWidgets.QLineEdit()
        self.desc.setStyleSheet(INPUT_STYLE)
        self.desc.setPlaceholderText("Description / order reference")
        layout.addLayout(row("Description:", self.desc))

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Save", self._on_save), ("Cancel", self.reject)):
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
        if self.amount.value() <= 0:
            QtWidgets.QMessageBox.warning(self, "Error", "Amount must be greater than zero.")
            return
        inv_num = self.inv_num.text().strip()
        inv_date = self.inv_date.date().toString("yyyy-MM-dd")
        amount = self.amount.value()
        desc = self.desc.text().strip() or None
        cust = self.cust_combo.currentText()
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO ar_invoice (customer_id, invoice_number, invoice_date, due_date, amount, description)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (self.cust_combo.currentData(), inv_num, inv_date,
                  self.due_date.date().toString("yyyy-MM-dd"), amount, desc))
            conn.commit()
        except sqlite3.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate", "Invoice number already exists.")
            conn.close()
            return
        conn.close()
        # Post draft GL entry: DR Accounts Receivable (1100), CR Sales Revenue (4000)
        post_gl_entry(
            journal_date=inv_date,
            reference=inv_num,
            description=f"AR Invoice – {cust}",
            lines=[
                ("1100", amount, 0.0, f"AR Invoice {inv_num}"),
                ("4000", 0.0, amount, f"AR Invoice {inv_num}"),
            ],
        )
        self.accept()


class RecordPaymentDialog(QtWidgets.QDialog):
    def __init__(self, invoice_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record Payment")
        self.setFixedSize(460, 280)
        self._invoice_id = invoice_id
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        conn = get_db()
        inv = conn.execute(
            """SELECT ai.*, c.first_name, c.last_name, c.company_name
               FROM ar_invoice ai JOIN customer c ON c.id=ai.customer_id
               WHERE ai.id=%s""",
            (self._invoice_id,)
        ).fetchone()
        paid = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ar_payment WHERE invoice_id=%s",
            (self._invoice_id,)
        ).fetchone()[0]
        conn.close()
        self._balance = inv["amount"] - paid
        cust_name = _customer_display(inv)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)

        info = QtWidgets.QLabel(
            f"{inv['invoice_number']}  |  {cust_name}\n"
            f"Invoice: {_money(inv['amount'])}   Paid: {_money(paid)}   Balance: {_money(self._balance)}")
        info.setStyleSheet("color%(white)s;font-size:12px;")
        info.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        def row(lbl_text, widget, lbl_w=120):
            r = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(lbl_text)
            lbl.setFixedWidth(lbl_w)
            lbl.setStyleSheet(LABEL_STYLE)
            r.addWidget(lbl)
            r.addWidget(widget)
            return r

        self.pay_date = QtWidgets.QDateEdit()
        self.pay_date.setStyleSheet(DATE_STYLE)
        self.pay_date.setCalendarPopup(True)
        self.pay_date.setDisplayFormat("MM/dd/yyyy")
        self.pay_date.setDate(QtCore.QDate.currentDate())
        layout.addLayout(row("Payment Date:", self.pay_date))

        self.pay_amount = QtWidgets.QDoubleSpinBox()
        self.pay_amount.setStyleSheet(SPIN_STYLE)
        self.pay_amount.setRange(0.01, self._balance)
        self.pay_amount.setDecimals(2)
        self.pay_amount.setPrefix("$ ")
        self.pay_amount.setValue(self._balance)
        layout.addLayout(row("Amount:", self.pay_amount))

        self.method = QtWidgets.QComboBox()
        self.method.setStyleSheet(COMBO_STYLE)
        self.method.addItems(["Check", "ACH", "Wire Transfer", "Credit Card", "Cash"])
        layout.addLayout(row("Method:", self.method))

        self.ref = QtWidgets.QLineEdit()
        self.ref.setStyleSheet(INPUT_STYLE)
        self.ref.setPlaceholderText("Check # / reference")
        layout.addLayout(row("Reference:", self.ref))

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Record Payment", self._on_save), ("Cancel", self.reject)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

    def _on_save(self):
        amount = self.pay_amount.value()
        if amount <= 0:
            QtWidgets.QMessageBox.warning(self, "Error", "Payment amount must be greater than zero.")
            return
        if amount > self._balance + 0.001:
            QtWidgets.QMessageBox.warning(self, "Error", f"Payment exceeds balance of {_money(self._balance)}.")
            return
        pay_date = self.pay_date.date().toString("yyyy-MM-dd")
        ref_text = self.ref.text().strip() or None
        conn = get_db()
        conn.execute(
            "INSERT INTO ar_payment (invoice_id, payment_date, amount, payment_method, reference) VALUES (%s,%s,%s,%s,%s)",
            (self._invoice_id, pay_date, amount, self.method.currentText(), ref_text))
        new_paid = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ar_payment WHERE invoice_id=%s",
            (self._invoice_id,)
        ).fetchone()[0]
        inv = conn.execute(
            "SELECT ai.amount, ai.invoice_number, c.first_name, c.last_name, c.company_name "
            "FROM ar_invoice ai JOIN customer c ON c.id=ai.customer_id WHERE ai.id=%s",
            (self._invoice_id,)
        ).fetchone()
        new_status = "paid" if abs(new_paid - inv["amount"]) < 0.01 else "partial"
        conn.execute("UPDATE ar_invoice SET status=%s WHERE id=%s", (new_status, self._invoice_id))
        conn.commit()
        conn.close()
        # Post draft GL entry: DR Cash (1000), CR Accounts Receivable (1100)
        ref = ref_text or inv["invoice_number"]
        cust = _customer_display(inv)
        post_gl_entry(
            journal_date=pay_date,
            reference=ref,
            description=f"AR Payment – {cust} ({inv['invoice_number']})",
            lines=[
                ("1000", amount, 0.0, f"Payment on {inv['invoice_number']}"),
                ("1100", 0.0, amount, f"Payment on {inv['invoice_number']}"),
            ],
        )
        self.accept()


# ── Main window ────────────────────────────────────────────────────────────

_TAB_KEYS = {'rcv': 0, 'acct_rcv': 0}


class AccountsReceivableWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, initial_tab=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._cust_row_ids = []
        self._invoice_row_ids = []
        self._build_ui()
        self._load_customers()
        if initial_tab in _TAB_KEYS:
            self.tabs.setCurrentIndex(_TAB_KEYS[initial_tab])
        self._refresh_invoices()
        self._refresh_aging()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        outer.addWidget(self.tabs)
        self.tabs.addTab(self._build_customers_tab(), "Customers")
        self.tabs.addTab(self._build_invoices_tab(), "Invoices")
        self.tabs.addTab(self._build_aging_tab(), "Aging Report")

    # ── Customers tab ──────────────────────────────────────────────────────

    def _build_customers_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.cust_table = QtWidgets.QTableWidget()
        self.cust_table.setColumnCount(7)
        self.cust_table.setHorizontalHeaderLabels(
            ["Company / Name", "Contact", "Phone", "Email", "City", "State", "Zip"])
        hh = self.cust_table.horizontalHeader()
        hh.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5, 6):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.cust_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cust_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.cust_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.cust_table.setAlternatingRowColors(True)
        self.cust_table.verticalHeader().setVisible(False)
        self.cust_table.clicked.connect(self._on_cust_row_clicked)
        layout.addWidget(self.cust_table, stretch=1)

        # Search bar
        sr = QtWidgets.QHBoxLayout()
        sl = QtWidgets.QLabel("Search:")
        sl.setStyleSheet(LABEL_STYLE)
        sr.addWidget(sl)
        self.cust_search = QtWidgets.QLineEdit()
        self.cust_search.setStyleSheet(INPUT_STYLE)
        self.cust_search.setFixedWidth(220)
        self.cust_search.setPlaceholderText("Company or last name")
        self.cust_search.returnPressed.connect(self._on_cust_search)
        sr.addWidget(self.cust_search)
        for t, fn in (("Search", self._on_cust_search), ("Show All", self._load_customers)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            sr.addWidget(b)
        sr.addStretch()
        layout.addLayout(sr)

        # Form
        fg = QtWidgets.QGroupBox("Customer Record")
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

        self.cf_company = inp("Company name")
        self.cf_first = inp("First name")
        self.cf_last = inp("Last name")
        self.cf_phone = inp("Phone")
        self.cf_phone.setFixedWidth(140)
        self.cf_email = inp("Email")
        self.cf_addr = inp("Street address")
        self.cf_city = inp("City")
        self.cf_state = inp("ST")
        self.cf_state.setMaxLength(2)
        self.cf_state.setFixedWidth(44)
        self.cf_zip = inp("Zip")
        self.cf_zip.setFixedWidth(90)

        grid.addWidget(lbl("Company:"), 0, 0)
        grid.addWidget(self.cf_company, 0, 1, 1, 3)
        grid.addWidget(lbl("First Name:"), 0, 4)
        grid.addWidget(self.cf_first, 0, 5)
        grid.addWidget(lbl("Last Name:"), 1, 0)
        grid.addWidget(self.cf_last, 1, 1, 1, 3)
        grid.addWidget(lbl("Phone:"), 1, 4)
        grid.addWidget(self.cf_phone, 1, 5)
        grid.addWidget(lbl("Email:"), 2, 0)
        grid.addWidget(self.cf_email, 2, 1, 1, 5)
        grid.addWidget(lbl("Address:"), 3, 0)
        grid.addWidget(self.cf_addr, 3, 1, 1, 3)
        grid.addWidget(lbl("City:"), 3, 4)
        grid.addWidget(self.cf_city, 3, 5)
        grid.addWidget(lbl("State:"), 4, 0)
        grid.addWidget(self.cf_state, 4, 1)
        grid.addWidget(lbl("Zip:"), 4, 2)
        grid.addWidget(self.cf_zip, 4, 3)
        layout.addWidget(fg)

        br = QtWidgets.QHBoxLayout()
        for t, fn in (("Add New", self._on_cust_add), ("Update Selected", self._on_cust_update),
                      ("Delete Selected", self._on_cust_delete), ("Clear", self._cust_clear)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(34)
            b.clicked.connect(fn)
            br.addWidget(b)
        br.addStretch()
        layout.addLayout(br)
        return w

    # ── Invoices tab ───────────────────────────────────────────────────────

    def _build_invoices_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # Filters
        fr = QtWidgets.QHBoxLayout()
        fr.setSpacing(8)

        def fl(t):
            lbl = QtWidgets.QLabel(t)
            lbl.setStyleSheet(LABEL_STYLE)
            return lbl

        self.inv_cust_filter = QtWidgets.QComboBox()
        self.inv_cust_filter.setStyleSheet(COMBO_STYLE)
        self.inv_cust_filter.setMinimumWidth(200)
        self.inv_status_filter = QtWidgets.QComboBox()
        self.inv_status_filter.setStyleSheet(COMBO_STYLE)
        self.inv_status_filter.addItems(["(all status)", "open", "partial", "paid", "void"])
        self.inv_from = QtWidgets.QDateEdit()
        self.inv_from.setStyleSheet(DATE_STYLE)
        self.inv_from.setCalendarPopup(True)
        self.inv_from.setDisplayFormat("MM/dd/yyyy")
        self.inv_from.setDate(QtCore.QDate.currentDate().addDays(-90))
        self.inv_to = QtWidgets.QDateEdit()
        self.inv_to.setStyleSheet(DATE_STYLE)
        self.inv_to.setCalendarPopup(True)
        self.inv_to.setDisplayFormat("MM/dd/yyyy")
        self.inv_to.setDate(QtCore.QDate.currentDate())

        fr.addWidget(fl("Customer:"))
        fr.addWidget(self.inv_cust_filter)
        fr.addWidget(fl("Status:"))
        fr.addWidget(self.inv_status_filter)
        fr.addWidget(fl("From:"))
        fr.addWidget(self.inv_from)
        fr.addWidget(fl("To:"))
        fr.addWidget(self.inv_to)
        for t, fn in (("Apply", self._refresh_invoices), ("Show All", self._inv_show_all)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            fr.addWidget(b)
        fr.addStretch()
        layout.addLayout(fr)

        # Invoice table
        self.inv_table = QtWidgets.QTableWidget()
        self.inv_table.setColumnCount(8)
        self.inv_table.setHorizontalHeaderLabels(
            ["Invoice #", "Customer", "Date", "Due Date", "Amount", "Paid", "Balance", "Status"])
        hh = self.inv_table.horizontalHeader()
        hh.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (0, 2, 3, 4, 5, 6, 7):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.inv_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inv_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.inv_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.inv_table.verticalHeader().setVisible(False)
        self.inv_table.clicked.connect(self._on_inv_row_clicked)
        layout.addWidget(self.inv_table, stretch=1)

        # Action buttons
        ar = QtWidgets.QHBoxLayout()
        for t, fn in (("New Invoice", self._on_new_invoice),
                      ("Record Payment", self._on_record_payment),
                      ("Void Invoice", self._on_void_invoice)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(fn)
            ar.addWidget(b)
        ar.addStretch()
        layout.addLayout(ar)

        # Detail panel
        self.inv_detail_grp = QtWidgets.QGroupBox("Invoice Detail")
        self.inv_detail_grp.setStyleSheet(
            "QGroupBox{color%(white)s;font-weight%(bold)s;border:1px solid white;margin-top:6px;}"
            "QGroupBox:%(title)s{subcontrol-origin%(margin)s;left:10px;}")
        self.inv_detail_grp.setVisible(False)
        dv = QtWidgets.QVBoxLayout(self.inv_detail_grp)
        self.inv_detail_lbl = QtWidgets.QLabel("")
        self.inv_detail_lbl.setStyleSheet("color%(white)s;font-size:12px;")
        dv.addWidget(self.inv_detail_lbl)
        self.pay_hist_table = QtWidgets.QTableWidget()
        self.pay_hist_table.setColumnCount(5)
        self.pay_hist_table.setHorizontalHeaderLabels(["Date", "Amount", "Method", "Reference", "Notes"])
        ph = self.pay_hist_table.horizontalHeader()
        ph.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        ph.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (0, 1, 2, 3):
            ph.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.pay_hist_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pay_hist_table.setAlternatingRowColors(True)
        self.pay_hist_table.verticalHeader().setVisible(False)
        self.pay_hist_table.setFixedHeight(120)
        dv.addWidget(self.pay_hist_table)
        layout.addWidget(self.inv_detail_grp)
        return w

    # ── Aging tab ──────────────────────────────────────────────────────────

    def _build_aging_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Accounts Receivable Aging Report  (open & partial invoices only)")
        title.setStyleSheet("color%(white)s;font-size:14px;font-weight%(bold)s;")
        hdr.addWidget(title)
        ref_btn = QtWidgets.QPushButton("Refresh")
        ref_btn.setStyleSheet(BUTTON_STYLE)
        ref_btn.setFixedHeight(30)
        ref_btn.clicked.connect(self._refresh_aging)
        hdr.addWidget(ref_btn)
        hdr.addStretch()
        layout.addLayout(hdr)

        self.aging_table = QtWidgets.QTableWidget()
        self.aging_table.setColumnCount(6)
        self.aging_table.setHorizontalHeaderLabels(
            ["Customer", "0-30 Days", "31-60 Days", "61-90 Days", "91+ Days", "Total Outstanding"])
        ah = self.aging_table.horizontalHeader()
        ah.setStyleSheet("color%(black)s;font-weight%(bold)s;")
        ah.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5):
            ah.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.aging_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.aging_table.setAlternatingRowColors(True)
        self.aging_table.verticalHeader().setVisible(False)
        layout.addWidget(self.aging_table, stretch=1)

        self.aging_totals_lbl = QtWidgets.QLabel("")
        self.aging_totals_lbl.setStyleSheet("color%(white)s;font-size:13px;")
        layout.addWidget(self.aging_totals_lbl)
        return w

    # ── Customer data ──────────────────────────────────────────────────────

    def _load_customers(self, search=None):
        self.cust_search.blockSignals(True)
        if not search:
            self.cust_search.clear()
        self.cust_search.blockSignals(False)
        conn = get_db()
        if search:
            rows = conn.execute(
                "SELECT * FROM customer WHERE company_name LIKE %s OR last_name LIKE %s "
                "ORDER BY company_name, last_name, first_name",
                (f"%{search}%", f"%{search}%")
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM customer ORDER BY company_name, last_name, first_name"
            ).fetchall()
        conn.close()

        self.cust_table.setRowCount(0)
        self._cust_row_ids = []
        for row in rows:
            r = self.cust_table.rowCount()
            self.cust_table.insertRow(r)
            self._cust_row_ids.append(row["id"])
            contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
            primary = (row["company_name"] or "").strip() or contact
            for c, v in enumerate([
                primary,
                contact if (row["company_name"] or "").strip() else "",
                row["phone_number"] or "",
                row["email"] or "",
                row["city"] or "",
                row["state"] or "",
                row["zip_code"] or "",
            ]):
                self.cust_table.setItem(r, c, _ro(v))

        self._refresh_customer_filters()

    def _refresh_customer_filters(self):
        conn = get_db()
        customers = conn.execute(
            "SELECT id, first_name, last_name, company_name FROM customer ORDER BY company_name, last_name, first_name"
        ).fetchall()
        conn.close()
        self.inv_cust_filter.blockSignals(True)
        self.inv_cust_filter.clear()
        self.inv_cust_filter.addItem("(all customers)", None)
        for c in customers:
            self.inv_cust_filter.addItem(_customer_display(c), c["id"])
        self.inv_cust_filter.blockSignals(False)

    def _on_cust_search(self):
        self._load_customers(search=self.cust_search.text().strip() or None)

    def _on_cust_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._cust_row_ids):
            return
        conn = get_db()
        c = conn.execute("SELECT * FROM customer WHERE id=%s", (self._cust_row_ids[row],)).fetchone()
        conn.close()
        if not c:
            return
        self.cf_company.setText(c["company_name"] or "")
        self.cf_first.setText(c["first_name"] or "")
        self.cf_last.setText(c["last_name"] or "")
        self.cf_phone.setText(c["phone_number"] or "")
        self.cf_email.setText(c["email"] or "")
        self.cf_addr.setText(c["address"] or "")
        self.cf_city.setText(c["city"] or "")
        self.cf_state.setText(c["state"] or "")
        self.cf_zip.setText(c["zip_code"] or "")

    def _cust_clear(self):
        for w in (self.cf_company, self.cf_first, self.cf_last, self.cf_phone,
                  self.cf_email, self.cf_addr, self.cf_city, self.cf_state, self.cf_zip):
            w.clear()
        self.cust_table.clearSelection()

    def _collect_customer_form(self):
        company = self.cf_company.text().strip()
        first = self.cf_first.text().strip()
        last = self.cf_last.text().strip()
        if not company and not last:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Company name or last name is required.")
            return None
        return {
            "company_name": company or None,
            "first_name": first or None,
            "last_name": last or None,
            "phone_number": self.cf_phone.text().strip() or None,
            "email": self.cf_email.text().strip() or None,
            "address": self.cf_addr.text().strip() or None,
            "city": self.cf_city.text().strip() or None,
            "state": self.cf_state.text().strip().upper() or None,
            "zip_code": self.cf_zip.text().strip() or None,
        }

    def _on_cust_add(self):
        data = self._collect_customer_form()
        if not data:
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO customer (company_name,first_name,last_name,phone_number,email,address,city,state,zip_code) "
            "VALUES (%(company_name)s,%(first_name)s,%(last_name)s,%(phone_number)s,%(email)s,%(address)s,%(city)s,%(state)s,%(zip_code)s)",
            data)
        conn.commit()
        conn.close()
        self._cust_clear()
        self._load_customers()

    def _on_cust_update(self):
        row = self.cust_table.currentRow()
        if row < 0 or row >= len(self._cust_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a customer first.")
            return
        data = self._collect_customer_form()
        if not data:
            return
        data["id"] = self._cust_row_ids[row]
        conn = get_db()
        conn.execute(
            "UPDATE customer SET company_name=%(company_name)s,first_name=%(first_name)s,last_name=%(last_name)s,"
            "phone_number=%(phone_number)s,email=%(email)s,address=%(address)s,city=%(city)s,state=%(state)s,zip_code=%(zip_code)s "
            "WHERE id=%(id)s",
            data)
        conn.commit()
        conn.close()
        self._load_customers()

    def _on_cust_delete(self):
        row = self.cust_table.currentRow()
        if row < 0 or row >= len(self._cust_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a customer first.")
            return
        cid = self._cust_row_ids[row]
        conn = get_db()
        inv_count = conn.execute(
            "SELECT COUNT(*) FROM ar_invoice WHERE customer_id=%s", (cid,)
        ).fetchone()[0]
        conn.close()
        msg = "Delete this customer%s"
        if inv_count:
            msg += f"\n\nWarning: {inv_count} invoice(s) reference this customer. They will also be deleted."
        if (QtWidgets.QMessageBox.question(
                self, "Confirm Delete", msg,
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            conn = get_db()
            inv_ids = [r[0] for r in conn.execute(
                "SELECT id FROM ar_invoice WHERE customer_id=%s", (cid,)).fetchall()]
            for iid in inv_ids:
                conn.execute("DELETE FROM ar_payment WHERE invoice_id=%s", (iid,))
            conn.execute("DELETE FROM ar_invoice WHERE customer_id=%s", (cid,))
            conn.execute("DELETE FROM customer WHERE id=%s", (cid,))
            conn.commit()
            conn.close()
            self._cust_clear()
            self._load_customers()
            self._refresh_invoices()

    # ── Invoice data ───────────────────────────────────────────────────────

    def _refresh_invoices(self):
        cid = self.inv_cust_filter.currentData()
        status = self.inv_status_filter.currentText()
        from_s = self.inv_from.date().toString("yyyy-MM-dd")
        to_s = self.inv_to.date().toString("yyyy-MM-dd")
        conn = get_db()
        q = (
            "SELECT ai.id, ai.invoice_number, c.first_name, c.last_name, c.company_name, "
            "ai.invoice_date, ai.due_date, ai.amount, COALESCE(p.paid,0) as paid, ai.status "
            "FROM ar_invoice ai JOIN customer c ON c.id=ai.customer_id "
            "LEFT JOIN (SELECT invoice_id, SUM(amount) as paid FROM ar_payment GROUP BY invoice_id) p "
            "ON p.invoice_id=ai.id "
            "WHERE ai.invoice_date BETWEEN %s AND %s"
        )
        params = [from_s, to_s]
        if cid:
            q += " AND ai.customer_id=%s"
            params.append(cid)
        if status != "(all status)":
            q += " AND ai.status=%s"
            params.append(status)
        q += " ORDER BY ai.invoice_date DESC"
        rows = conn.execute(q, params).fetchall()
        conn.close()

        self.inv_table.setRowCount(0)
        self._invoice_row_ids = []
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        for row in rows:
            r = self.inv_table.rowCount()
            self.inv_table.insertRow(r)
            self._invoice_row_ids.append(row["id"])
            balance = row["amount"] - row["paid"]
            color = STATUS_COLORS.get(row["status"], QtGui.QColor(255, 255, 255))
            cust_name = _customer_display(row)
            for c, (val, algn) in enumerate([
                (row["invoice_number"], QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (cust_name, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["invoice_date"], QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["due_date"], QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (_money(row["amount"]), right),
                (_money(row["paid"]), right),
                (_money(balance), right),
                (row["status"].upper(), QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter),
            ]):
                item = _ro(val, algn)
                item.setBackground(color)
                self.inv_table.setItem(r, c, item)
        self.inv_detail_grp.setVisible(False)

    def _inv_show_all(self):
        self.inv_cust_filter.setCurrentIndex(0)
        self.inv_status_filter.setCurrentIndex(0)
        self.inv_from.setDate(QtCore.QDate(2000, 1, 1))
        self.inv_to.setDate(QtCore.QDate.currentDate())
        self._refresh_invoices()

    def _on_inv_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._invoice_row_ids):
            return
        inv_id = self._invoice_row_ids[row]
        conn = get_db()
        inv = conn.execute(
            "SELECT ai.*, c.first_name, c.last_name, c.company_name "
            "FROM ar_invoice ai JOIN customer c ON c.id=ai.customer_id WHERE ai.id=%s",
            (inv_id,)
        ).fetchone()
        payments = conn.execute(
            "SELECT * FROM ar_payment WHERE invoice_id=%s ORDER BY payment_date", (inv_id,)
        ).fetchall()
        conn.close()
        paid_total = sum(p["amount"] for p in payments)
        cust_name = _customer_display(inv)
        self.inv_detail_lbl.setText(
            f"{inv['invoice_number']}  |  {cust_name}  |  "
            f"Date: {inv['invoice_date']}  |  Due: {inv['due_date']}  |  "
            f"Amount: {_money(inv['amount'])}  |  Paid: {_money(paid_total)}  |  "
            f"Balance: {_money(inv['amount'] - paid_total)}  |  Status: {inv['status'].upper()}"
            + (f"\nDescription: {inv['description']}" if inv["description"] else ""))
        self.pay_hist_table.setRowCount(0)
        for p in payments:
            r = self.pay_hist_table.rowCount()
            self.pay_hist_table.insertRow(r)
            for c, v in enumerate([p["payment_date"], _money(p["amount"]),
                                   p["payment_method"], p["reference"] or "", p["notes"] or ""]):
                self.pay_hist_table.setItem(r, c, _ro(v))
        self.inv_detail_grp.setVisible(True)

    def _on_new_invoice(self):
        cid = self.inv_cust_filter.currentData()
        dlg = NewInvoiceDialog(self, preselect_customer_id=cid)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_invoices()
            self._refresh_aging()

    def _on_record_payment(self):
        row = self.inv_table.currentRow()
        if row < 0 or row >= len(self._invoice_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select an invoice first.")
            return
        inv_id = self._invoice_row_ids[row]
        conn = get_db()
        status = conn.execute("SELECT status FROM ar_invoice WHERE id=%s", (inv_id,)).fetchone()["status"]
        conn.close()
        if status in ("paid", "void"):
            QtWidgets.QMessageBox.information(self, "Cannot Pay", f"Invoice is already {status}.")
            return
        dlg = RecordPaymentDialog(inv_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_invoices()
            self._refresh_aging()
            self._on_inv_row_clicked(self.inv_table.model().index(row, 0))

    def _on_void_invoice(self):
        row = self.inv_table.currentRow()
        if row < 0 or row >= len(self._invoice_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select an invoice first.")
            return
        inv_id = self._invoice_row_ids[row]
        if (QtWidgets.QMessageBox.question(
                self, "Void Invoice", "Mark this invoice as void%s",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            conn = get_db()
            conn.execute("UPDATE ar_invoice SET status='void' WHERE id=%s", (inv_id,))
            conn.commit()
            conn.close()
            self._refresh_invoices()
            self._refresh_aging()

    # ── Aging data ─────────────────────────────────────────────────────────

    def _refresh_aging(self):
        conn = get_db()
        rows = conn.execute("""
            SELECT c.id, c.first_name, c.last_name, c.company_name,
                SUM(CASE WHEN CAST(julianday('now')-julianday(ai.invoice_date) AS INT) <= 30
                         THEN ai.amount - COALESCE(p.paid,0) ELSE 0 END) b0,
                SUM(CASE WHEN CAST(julianday('now')-julianday(ai.invoice_date) AS INT) BETWEEN 31 AND 60
                         THEN ai.amount - COALESCE(p.paid,0) ELSE 0 END) b31,
                SUM(CASE WHEN CAST(julianday('now')-julianday(ai.invoice_date) AS INT) BETWEEN 61 AND 90
                         THEN ai.amount - COALESCE(p.paid,0) ELSE 0 END) b61,
                SUM(CASE WHEN CAST(julianday('now')-julianday(ai.invoice_date) AS INT) > 90
                         THEN ai.amount - COALESCE(p.paid,0) ELSE 0 END) b91
            FROM ar_invoice ai
            JOIN customer c ON c.id=ai.customer_id
            LEFT JOIN (SELECT invoice_id, SUM(amount) as paid FROM ar_payment GROUP BY invoice_id) p
                ON p.invoice_id=ai.id
            WHERE ai.status IN ('open','partial')
            GROUP BY c.id
            ORDER BY c.company_name, c.last_name, c.first_name
        """).fetchall()
        conn.close()

        self.aging_table.setRowCount(0)
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        totals = [0.0] * 4
        for row in rows:
            b = [row["b0"], row["b31"], row["b61"], row["b91"]]
            total = sum(b)
            if total <= 0:
                continue
            r = self.aging_table.rowCount()
            self.aging_table.insertRow(r)
            self.aging_table.setItem(r, 0, _ro(_customer_display(row)))
            for c, v in enumerate(b):
                self.aging_table.setItem(r, c + 1, _ro(_money(v), right))
                totals[c] += v
            self.aging_table.setItem(r, 5, _ro(_money(total), right))
        self.aging_totals_lbl.setText(
            f"Totals --  0-30: {_money(totals[0])}   31-60: {_money(totals[1])}   "
            f"61-90: {_money(totals[2])}   91+: {_money(totals[3])}   "
            f"Total Outstanding: {_money(sum(totals))}")


class AccountsReceivable(QtWidgets.QMainWindow):
    def __init__(self, initial_tab=None):
        super().__init__()
        self.setWindowTitle("Accounts Receivable")
        self.resize(1150, 700)
        _apply_blue_palette(self)
        self.setCentralWidget(AccountsReceivableWidget(initial_tab=initial_tab))


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = AccountsReceivable(sys.argv[1] if len(sys.argv) > 1 else None)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
