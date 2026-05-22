import sys
import sqlite3
import os
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets
from gl_utils import post_gl_entry, gl_accounts_by_type

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "company.db")

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE  = "QLineEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
COMBO_STYLE  = "QComboBox{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}QComboBox QAbstractItemView{background-color:white;}"
DATE_STYLE   = "QDateEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 4px;}"
SPIN_STYLE   = "QDoubleSpinBox{background-color:white;border:2px solid black;border-radius:4px;padding:2px 4px;}"
LABEL_STYLE  = "color:white;font-size:13px;"
TAB_STYLE    = ("QTabWidget::pane{border:1px solid black;}"
                "QTabBar::tab{background:white; border:2px solid black; padding:6px 18px;"
                " border-bottom:none; border-radius:4px 4px 0 0;}"
                "QTabBar::tab:selected{background:rgb(85,255,255); font-weight:bold;}"
                "QTabBar::tab:hover{background:rgb(85,255,255);}")

STATUS_COLORS = {
    "open":    QtGui.QColor(255, 255, 255),
    "partial": QtGui.QColor(255, 243, 205),
    "paid":    QtGui.QColor(212, 237, 218),
    "void":    QtGui.QColor(220, 220, 220),
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vendors (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name  TEXT NOT NULL,
            contact_name TEXT,
            phone        TEXT,
            email        TEXT,
            address      TEXT,
            city         TEXT,
            state        TEXT,
            zip_code     TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ap_invoice (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id      INTEGER NOT NULL REFERENCES vendors(id),
            invoice_number TEXT NOT NULL UNIQUE,
            invoice_date   TEXT NOT NULL,
            due_date       TEXT NOT NULL,
            amount         REAL NOT NULL,
            description    TEXT,
            status         TEXT NOT NULL DEFAULT 'open'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ap_payment (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id     INTEGER NOT NULL REFERENCES ap_invoice(id),
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


def _invoice_balance(invoice_id):
    conn = get_db()
    inv  = conn.execute("SELECT amount FROM ap_invoice WHERE id=?", (invoice_id,)).fetchone()
    paid = conn.execute("SELECT COALESCE(SUM(amount),0) FROM ap_payment WHERE invoice_id=?",
                        (invoice_id,)).fetchone()[0]
    conn.close()
    return (inv["amount"] - paid) if inv else 0.0


def _next_inv_num():
    yr = date.today().year
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM ap_invoice WHERE invoice_number LIKE ?",
                     (f"AP-{yr}-%",)).fetchone()[0]
    conn.close()
    return f"AP-{yr}-{n+1:04d}"


# ── Dialogs ────────────────────────────────────────────────────────────────

class NewInvoiceDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, preselect_vendor_id=None):
        super().__init__(parent)
        self.setWindowTitle("New Bill / Invoice")
        self.setFixedSize(480, 360)
        _apply_blue_palette(self)
        self._preselect = preselect_vendor_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("New Accounts Payable Invoice")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:white;font-size:15px;font-weight:bold;")
        layout.addWidget(title)

        def row(lbl_text, widget, lbl_w=110):
            r = QtWidgets.QHBoxLayout()
            l = QtWidgets.QLabel(lbl_text); l.setFixedWidth(lbl_w); l.setStyleSheet(LABEL_STYLE)
            r.addWidget(l); r.addWidget(widget)
            return r

        self.vendor_combo = QtWidgets.QComboBox(); self.vendor_combo.setStyleSheet(COMBO_STYLE)
        conn = get_db()
        vendors = conn.execute("SELECT id, vendor_name FROM vendors ORDER BY vendor_name").fetchall()
        conn.close()
        for v in vendors:
            self.vendor_combo.addItem(v["vendor_name"], v["id"])
        if self._preselect:
            idx = self.vendor_combo.findData(self._preselect)
            if idx >= 0: self.vendor_combo.setCurrentIndex(idx)
        layout.addLayout(row("Vendor:", self.vendor_combo))

        self.inv_num = QtWidgets.QLineEdit(_next_inv_num()); self.inv_num.setStyleSheet(INPUT_STYLE)
        layout.addLayout(row("Invoice #:", self.inv_num))

        self.inv_date = QtWidgets.QDateEdit(); self.inv_date.setStyleSheet(DATE_STYLE)
        self.inv_date.setCalendarPopup(True); self.inv_date.setDisplayFormat("MM/dd/yyyy")
        self.inv_date.setDate(QtCore.QDate.currentDate())
        layout.addLayout(row("Invoice Date:", self.inv_date))

        self.due_date = QtWidgets.QDateEdit(); self.due_date.setStyleSheet(DATE_STYLE)
        self.due_date.setCalendarPopup(True); self.due_date.setDisplayFormat("MM/dd/yyyy")
        self.due_date.setDate(QtCore.QDate.currentDate().addDays(30))
        layout.addLayout(row("Due Date:", self.due_date))

        self.amount = QtWidgets.QDoubleSpinBox(); self.amount.setStyleSheet(SPIN_STYLE)
        self.amount.setRange(0, 99999999); self.amount.setDecimals(2); self.amount.setPrefix("$ ")
        layout.addLayout(row("Amount:", self.amount))

        self.desc = QtWidgets.QLineEdit(); self.desc.setStyleSheet(INPUT_STYLE)
        self.desc.setPlaceholderText("Description / PO reference")
        layout.addLayout(row("Description:", self.desc))

        self.gl_acct_combo = QtWidgets.QComboBox(); self.gl_acct_combo.setStyleSheet(COMBO_STYLE)
        for num, name in gl_accounts_by_type("Expense", "COGS", "Asset"):
            self.gl_acct_combo.addItem(f"{num}  {name}", num)
        # Default to "Other Expense" 7900 if present
        idx = self.gl_acct_combo.findData("7900")
        if idx >= 0:
            self.gl_acct_combo.setCurrentIndex(idx)
        layout.addLayout(row("GL Expense Acct:", self.gl_acct_combo))

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Save", self._on_save), ("Cancel", self.reject)):
            b = QtWidgets.QPushButton(text); b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32); b.clicked.connect(slot); btn_row.addWidget(b)
        layout.addLayout(btn_row)

    def _on_save(self):
        if self.vendor_combo.currentData() is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Select a vendor."); return
        if self.amount.value() <= 0:
            QtWidgets.QMessageBox.warning(self, "Error", "Amount must be greater than zero."); return
        inv_num  = self.inv_num.text().strip()
        inv_date = self.inv_date.date().toString("yyyy-MM-dd")
        amount   = self.amount.value()
        desc     = self.desc.text().strip() or None
        vendor   = self.vendor_combo.currentText()
        gl_acct  = self.gl_acct_combo.currentData()
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO ap_invoice (vendor_id, invoice_number, invoice_date, due_date, amount, description)
                VALUES (?,?,?,?,?,?)
            """, (self.vendor_combo.currentData(), inv_num, inv_date,
                  self.due_date.date().toString("yyyy-MM-dd"), amount, desc))
            conn.commit()
        except sqlite3.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate", "Invoice number already exists."); conn.close(); return
        conn.close()
        # Post draft GL entry: DR expense account, CR Accounts Payable (2000)
        jid = post_gl_entry(
            journal_date=inv_date,
            reference=inv_num,
            description=f"AP Invoice – {vendor}",
            lines=[
                (gl_acct, amount, 0.0,   f"AP Invoice {inv_num}"),
                ("2000",  0.0,  amount,  f"AP Invoice {inv_num}"),
            ],
        )
        if jid is None:
            QtWidgets.QMessageBox.warning(
                self, "GL Warning",
                "Invoice saved, but the GL journal entry could not be created.\n"
                "Check that accounts 2000 and the selected expense account exist in the Chart of Accounts.")
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
            "SELECT ai.*, v.vendor_name FROM ap_invoice ai JOIN vendors v ON v.id=ai.vendor_id WHERE ai.id=?",
            (self._invoice_id,)).fetchone()
        paid = conn.execute("SELECT COALESCE(SUM(amount),0) FROM ap_payment WHERE invoice_id=?",
                            (self._invoice_id,)).fetchone()[0]
        conn.close()
        self._balance = inv["amount"] - paid

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20); layout.setSpacing(10)

        info = QtWidgets.QLabel(
            f"{inv['invoice_number']}  |  {inv['vendor_name']}\n"
            f"Invoice: {_money(inv['amount'])}   Paid: {_money(paid)}   Balance: {_money(self._balance)}")
        info.setStyleSheet("color:white;font-size:12px;")
        info.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        def row(lbl_text, widget, lbl_w=120):
            r = QtWidgets.QHBoxLayout()
            l = QtWidgets.QLabel(lbl_text); l.setFixedWidth(lbl_w); l.setStyleSheet(LABEL_STYLE)
            r.addWidget(l); r.addWidget(widget); return r

        self.pay_date = QtWidgets.QDateEdit(); self.pay_date.setStyleSheet(DATE_STYLE)
        self.pay_date.setCalendarPopup(True); self.pay_date.setDisplayFormat("MM/dd/yyyy")
        self.pay_date.setDate(QtCore.QDate.currentDate())
        layout.addLayout(row("Payment Date:", self.pay_date))

        self.pay_amount = QtWidgets.QDoubleSpinBox(); self.pay_amount.setStyleSheet(SPIN_STYLE)
        self.pay_amount.setRange(0.01, self._balance); self.pay_amount.setDecimals(2)
        self.pay_amount.setPrefix("$ "); self.pay_amount.setValue(self._balance)
        layout.addLayout(row("Amount:", self.pay_amount))

        self.method = QtWidgets.QComboBox(); self.method.setStyleSheet(COMBO_STYLE)
        self.method.addItems(["Check", "ACH", "Wire Transfer", "Credit Card", "Cash"])
        layout.addLayout(row("Method:", self.method))

        self.ref = QtWidgets.QLineEdit(); self.ref.setStyleSheet(INPUT_STYLE)
        self.ref.setPlaceholderText("Check # / reference")
        layout.addLayout(row("Reference:", self.ref))

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Record Payment", self._on_save), ("Cancel", self.reject)):
            b = QtWidgets.QPushButton(text); b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32); b.clicked.connect(slot); btn_row.addWidget(b)
        layout.addLayout(btn_row)

    def _on_save(self):
        amount = self.pay_amount.value()
        if amount <= 0:
            QtWidgets.QMessageBox.warning(self, "Error", "Payment amount must be greater than zero."); return
        if amount > self._balance + 0.001:
            QtWidgets.QMessageBox.warning(self, "Error", f"Payment exceeds balance of {_money(self._balance)}."); return
        pay_date = self.pay_date.date().toString("yyyy-MM-dd")
        ref_text = self.ref.text().strip() or None
        conn = get_db()
        conn.execute("INSERT INTO ap_payment (invoice_id, payment_date, amount, payment_method, reference) VALUES (?,?,?,?,?)",
                     (self._invoice_id, pay_date, amount, self.method.currentText(), ref_text))
        new_paid = conn.execute("SELECT COALESCE(SUM(amount),0) FROM ap_payment WHERE invoice_id=?",
                                (self._invoice_id,)).fetchone()[0]
        inv      = conn.execute(
            "SELECT ai.amount, ai.invoice_number, v.vendor_name "
            "FROM ap_invoice ai JOIN vendors v ON v.id=ai.vendor_id WHERE ai.id=?",
            (self._invoice_id,)
        ).fetchone()
        new_status = "paid" if abs(new_paid - inv["amount"]) < 0.01 else "partial"
        conn.execute("UPDATE ap_invoice SET status=? WHERE id=?", (new_status, self._invoice_id))
        conn.commit(); conn.close()
        # Post draft GL entry: DR Accounts Payable (2000), CR Cash (1000)
        ref = ref_text or inv["invoice_number"]
        post_gl_entry(
            journal_date=pay_date,
            reference=ref,
            description=f"AP Payment – {inv['vendor_name']} ({inv['invoice_number']})",
            lines=[
                ("2000", amount, 0.0,   f"Payment on {inv['invoice_number']}"),
                ("1000", 0.0,  amount,  f"Payment on {inv['invoice_number']}"),
            ],
        )
        self.accept()


# ── Main window ────────────────────────────────────────────────────────────

_TAB_KEYS = {
    'acct_pay': 0, 'ap': 0,
    'sub_exp': 1, 'pend_appr': 1, 'appr_exp': 1, 'exp_sum': 1,
}

class AccountsPayable(QtWidgets.QMainWindow):
    def __init__(self, initial_tab=None):
        super().__init__()
        self.setWindowTitle("Accounts Payable")
        self.resize(1150, 700)
        _apply_blue_palette(self)
        self._vendor_row_ids  = []
        self._invoice_row_ids = []
        self._build_ui()
        self._load_vendors()
        self._refresh_invoices()
        self._refresh_aging()
        if initial_tab in _TAB_KEYS:
            self.tabs.setCurrentIndex(_TAB_KEYS[initial_tab])

    def _build_ui(self):
        central = QtWidgets.QWidget(); self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central); outer.setContentsMargins(10,10,10,10)
        self.tabs = QtWidgets.QTabWidget(); self.tabs.setStyleSheet(TAB_STYLE); outer.addWidget(self.tabs)
        self.tabs.addTab(self._build_vendors_tab(),  "Vendors")
        self.tabs.addTab(self._build_invoices_tab(), "Bills / Invoices")
        self.tabs.addTab(self._build_aging_tab(),    "Aging Report")

    # ── Vendors tab ────────────────────────────────────────────────────────

    def _build_vendors_tab(self):
        w = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12,12,12,12); layout.setSpacing(8)

        self.vend_table = QtWidgets.QTableWidget()
        self.vend_table.setColumnCount(6)
        self.vend_table.setHorizontalHeaderLabels(["Vendor Name","Contact","Phone","Email","City","State"])
        hh = self.vend_table.horizontalHeader(); hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1,2,3,4,5): hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.vend_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.vend_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.vend_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.vend_table.setAlternatingRowColors(True); self.vend_table.verticalHeader().setVisible(False)
        self.vend_table.clicked.connect(self._on_vend_row_clicked); layout.addWidget(self.vend_table, stretch=1)

        # Search
        sr = QtWidgets.QHBoxLayout()
        sl = QtWidgets.QLabel("Search:"); sl.setStyleSheet(LABEL_STYLE); sr.addWidget(sl)
        self.vend_search = QtWidgets.QLineEdit(); self.vend_search.setStyleSheet(INPUT_STYLE)
        self.vend_search.setFixedWidth(200); self.vend_search.returnPressed.connect(self._on_vend_search); sr.addWidget(self.vend_search)
        for t, fn in (("Search", self._on_vend_search), ("Show All", self._load_vendors)):
            b = QtWidgets.QPushButton(t); b.setStyleSheet(BUTTON_STYLE); b.setFixedHeight(30)
            b.clicked.connect(fn); sr.addWidget(b)
        sr.addStretch(); layout.addLayout(sr)

        # Form
        fg = QtWidgets.QGroupBox("Vendor Record")
        fg.setStyleSheet("QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:8px;}QGroupBox::title{subcontrol-origin:margin;left:10px;}")
        grid = QtWidgets.QGridLayout(fg); grid.setSpacing(6)

        def lbl(t): l=QtWidgets.QLabel(t); l.setStyleSheet(LABEL_STYLE); return l
        def inp(ph=""): e=QtWidgets.QLineEdit(); e.setStyleSheet(INPUT_STYLE); e.setPlaceholderText(ph); return e

        self.vf_name    = inp("Company/vendor name")
        self.vf_contact = inp("Contact person")
        self.vf_phone   = inp("Phone"); self.vf_phone.setFixedWidth(130)
        self.vf_email   = inp("Email")
        self.vf_addr    = inp("Street address")
        self.vf_city    = inp("City")
        self.vf_state   = inp("ST"); self.vf_state.setMaxLength(2); self.vf_state.setFixedWidth(44)
        self.vf_zip     = inp("Zip"); self.vf_zip.setFixedWidth(90)

        grid.addWidget(lbl("Vendor Name:"),  0,0); grid.addWidget(self.vf_name,    0,1,1,3)
        grid.addWidget(lbl("Contact:"),      0,4); grid.addWidget(self.vf_contact, 0,5)
        grid.addWidget(lbl("Phone:"),        1,0); grid.addWidget(self.vf_phone,   1,1)
        grid.addWidget(lbl("Email:"),        1,2); grid.addWidget(self.vf_email,   1,3,1,3)
        grid.addWidget(lbl("Address:"),      2,0); grid.addWidget(self.vf_addr,    2,1,1,3)
        grid.addWidget(lbl("City:"),         2,4); grid.addWidget(self.vf_city,    2,5)
        grid.addWidget(lbl("State:"),        3,0); grid.addWidget(self.vf_state,   3,1)
        grid.addWidget(lbl("Zip:"),          3,2); grid.addWidget(self.vf_zip,     3,3)
        layout.addWidget(fg)

        br = QtWidgets.QHBoxLayout()
        for t, fn in (("Add New",self._on_vend_add),("Update Selected",self._on_vend_update),
                      ("Delete Selected",self._on_vend_delete),("Clear",self._vend_clear)):
            b = QtWidgets.QPushButton(t); b.setStyleSheet(BUTTON_STYLE); b.setFixedHeight(34)
            b.clicked.connect(fn); br.addWidget(b)
        br.addStretch(); layout.addLayout(br)
        return w

    # ── Invoices tab ───────────────────────────────────────────────────────

    def _build_invoices_tab(self):
        w = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12,12,12,12); layout.setSpacing(6)

        # Filters
        fr = QtWidgets.QHBoxLayout(); fr.setSpacing(8)
        def fl(t): l=QtWidgets.QLabel(t); l.setStyleSheet(LABEL_STYLE); return l
        self.inv_vend_filter = QtWidgets.QComboBox(); self.inv_vend_filter.setStyleSheet(COMBO_STYLE); self.inv_vend_filter.setMinimumWidth(180)
        self.inv_status_filter = QtWidgets.QComboBox(); self.inv_status_filter.setStyleSheet(COMBO_STYLE)
        self.inv_status_filter.addItems(["(all status)", "open", "partial", "paid", "void"])
        self.inv_from = QtWidgets.QDateEdit(); self.inv_from.setStyleSheet(DATE_STYLE)
        self.inv_from.setCalendarPopup(True); self.inv_from.setDisplayFormat("MM/dd/yyyy")
        self.inv_from.setDate(QtCore.QDate.currentDate().addDays(-90))
        self.inv_to = QtWidgets.QDateEdit(); self.inv_to.setStyleSheet(DATE_STYLE)
        self.inv_to.setCalendarPopup(True); self.inv_to.setDisplayFormat("MM/dd/yyyy")
        self.inv_to.setDate(QtCore.QDate.currentDate())
        for lbl_t, widget in (("Vendor:",fl("Vendor:")),): pass  # placeholder
        fr.addWidget(fl("Vendor:")); fr.addWidget(self.inv_vend_filter)
        fr.addWidget(fl("Status:")); fr.addWidget(self.inv_status_filter)
        fr.addWidget(fl("From:"));   fr.addWidget(self.inv_from)
        fr.addWidget(fl("To:"));     fr.addWidget(self.inv_to)
        for t, fn in (("Apply", self._refresh_invoices), ("Show All", self._inv_show_all)):
            b = QtWidgets.QPushButton(t); b.setStyleSheet(BUTTON_STYLE); b.setFixedHeight(30)
            b.clicked.connect(fn); fr.addWidget(b)
        fr.addStretch(); layout.addLayout(fr)

        # Invoice table
        self.inv_table = QtWidgets.QTableWidget()
        self.inv_table.setColumnCount(8)
        self.inv_table.setHorizontalHeaderLabels(["Invoice #","Vendor","Date","Due Date","Amount","Paid","Balance","Status"])
        hh = self.inv_table.horizontalHeader(); hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (0,2,3,4,5,6,7): hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.inv_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inv_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.inv_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.inv_table.verticalHeader().setVisible(False)
        self.inv_table.clicked.connect(self._on_inv_row_clicked); layout.addWidget(self.inv_table, stretch=1)

        # Action buttons
        ar = QtWidgets.QHBoxLayout()
        for t, fn in (("New Invoice",self._on_new_invoice),("Record Payment",self._on_record_payment),
                      ("Void Invoice",self._on_void_invoice)):
            b = QtWidgets.QPushButton(t); b.setStyleSheet(BUTTON_STYLE); b.setFixedHeight(32)
            b.clicked.connect(fn); ar.addWidget(b)
        ar.addStretch(); layout.addLayout(ar)

        # Detail panel
        self.inv_detail_grp = QtWidgets.QGroupBox("Invoice Detail")
        self.inv_detail_grp.setStyleSheet("QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:6px;}QGroupBox::title{subcontrol-origin:margin;left:10px;}")
        self.inv_detail_grp.setVisible(False)
        dv = QtWidgets.QVBoxLayout(self.inv_detail_grp)
        self.inv_detail_lbl = QtWidgets.QLabel("")
        self.inv_detail_lbl.setStyleSheet("color:white;font-size:12px;")
        dv.addWidget(self.inv_detail_lbl)
        self.pay_hist_table = QtWidgets.QTableWidget()
        self.pay_hist_table.setColumnCount(5)
        self.pay_hist_table.setHorizontalHeaderLabels(["Date","Amount","Method","Reference","Notes"])
        ph = self.pay_hist_table.horizontalHeader(); ph.setStyleSheet("color:black;font-weight:bold;")
        ph.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (0,1,2,3): ph.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.pay_hist_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pay_hist_table.setAlternatingRowColors(True); self.pay_hist_table.verticalHeader().setVisible(False)
        self.pay_hist_table.setFixedHeight(120); dv.addWidget(self.pay_hist_table)
        layout.addWidget(self.inv_detail_grp)
        return w

    # ── Aging tab ──────────────────────────────────────────────────────────

    def _build_aging_tab(self):
        w = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12,12,12,12); layout.setSpacing(8)
        hdr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Accounts Payable Aging Report  (open & partial invoices only)")
        title.setStyleSheet("color:white;font-size:14px;font-weight:bold;"); hdr.addWidget(title)
        ref_btn = QtWidgets.QPushButton("Refresh"); ref_btn.setStyleSheet(BUTTON_STYLE)
        ref_btn.setFixedHeight(30); ref_btn.clicked.connect(self._refresh_aging); hdr.addWidget(ref_btn)
        hdr.addStretch(); layout.addLayout(hdr)
        self.aging_table = QtWidgets.QTableWidget()
        self.aging_table.setColumnCount(6)
        self.aging_table.setHorizontalHeaderLabels(["Vendor","0–30 Days","31–60 Days","61–90 Days","91+ Days","Total Outstanding"])
        ah = self.aging_table.horizontalHeader(); ah.setStyleSheet("color:black;font-weight:bold;")
        ah.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1,2,3,4,5): ah.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.aging_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.aging_table.setAlternatingRowColors(True); self.aging_table.verticalHeader().setVisible(False)
        layout.addWidget(self.aging_table, stretch=1)
        self.aging_totals_lbl = QtWidgets.QLabel("")
        self.aging_totals_lbl.setStyleSheet("color:white;font-size:13px;"); layout.addWidget(self.aging_totals_lbl)
        return w

    # ── Vendor data ────────────────────────────────────────────────────────

    def _load_vendors(self, search=None):
        self.vend_search.blockSignals(True)
        if not search: self.vend_search.clear()
        self.vend_search.blockSignals(False)
        conn = get_db()
        if search:
            rows = conn.execute("SELECT * FROM vendors WHERE vendor_name LIKE ? ORDER BY vendor_name", (f"%{search}%",)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM vendors ORDER BY vendor_name").fetchall()
        conn.close()
        self.vend_table.setRowCount(0); self._vendor_row_ids = []
        for row in rows:
            r = self.vend_table.rowCount(); self.vend_table.insertRow(r)
            self._vendor_row_ids.append(row["id"])
            for c, v in enumerate([row["vendor_name"],row["contact_name"] or "",row["phone"] or "",
                                    row["email"] or "",row["city"] or "",row["state"] or ""]):
                self.vend_table.setItem(r, c, _ro(v))
        self._refresh_vendor_filters()

    def _refresh_vendor_filters(self):
        conn = get_db(); vendors = conn.execute("SELECT id, vendor_name FROM vendors ORDER BY vendor_name").fetchall(); conn.close()
        for combo in (self.inv_vend_filter,):
            combo.blockSignals(True); combo.clear(); combo.addItem("(all vendors)", None)
            for v in vendors: combo.addItem(v["vendor_name"], v["id"])
            combo.blockSignals(False)

    def _on_vend_search(self):
        self._load_vendors(search=self.vend_search.text().strip() or None)

    def _on_vend_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._vendor_row_ids): return
        conn = get_db(); v = conn.execute("SELECT * FROM vendors WHERE id=?", (self._vendor_row_ids[row],)).fetchone(); conn.close()
        if not v: return
        for widget, key in ((self.vf_name,"vendor_name"),(self.vf_contact,"contact_name"),
                            (self.vf_phone,"phone"),(self.vf_email,"email"),(self.vf_addr,"address"),
                            (self.vf_city,"city"),(self.vf_state,"state"),(self.vf_zip,"zip_code")):
            widget.setText(v[key] or "")

    def _vend_clear(self):
        for w in (self.vf_name,self.vf_contact,self.vf_phone,self.vf_email,
                  self.vf_addr,self.vf_city,self.vf_state,self.vf_zip): w.clear()
        self.vend_table.clearSelection()

    def _collect_vendor_form(self):
        name = self.vf_name.text().strip()
        if not name: QtWidgets.QMessageBox.warning(self,"Input Error","Vendor name is required."); return None
        return {"vendor_name":name,"contact_name":self.vf_contact.text().strip() or None,
                "phone":self.vf_phone.text().strip() or None,"email":self.vf_email.text().strip() or None,
                "address":self.vf_addr.text().strip() or None,"city":self.vf_city.text().strip() or None,
                "state":self.vf_state.text().strip().upper() or None,"zip_code":self.vf_zip.text().strip() or None}

    def _on_vend_add(self):
        data = self._collect_vendor_form()
        if not data: return
        conn = get_db()
        conn.execute("INSERT INTO vendors (vendor_name,contact_name,phone,email,address,city,state,zip_code) VALUES (:vendor_name,:contact_name,:phone,:email,:address,:city,:state,:zip_code)", data)
        conn.commit(); conn.close(); self._vend_clear(); self._load_vendors()

    def _on_vend_update(self):
        rows = self.vend_table.selectedItems()
        if not rows: QtWidgets.QMessageBox.warning(self,"No Selection","Select a vendor first."); return
        row = self.vend_table.currentRow()
        if row < 0 or row >= len(self._vendor_row_ids): return
        data = self._collect_vendor_form()
        if not data: return
        data["id"] = self._vendor_row_ids[row]
        conn = get_db()
        conn.execute("UPDATE vendors SET vendor_name=:vendor_name,contact_name=:contact_name,phone=:phone,email=:email,address=:address,city=:city,state=:state,zip_code=:zip_code WHERE id=:id", data)
        conn.commit(); conn.close(); self._load_vendors()

    def _on_vend_delete(self):
        row = self.vend_table.currentRow()
        if row < 0 or row >= len(self._vendor_row_ids): QtWidgets.QMessageBox.warning(self,"No Selection","Select a vendor first."); return
        vid = self._vendor_row_ids[row]
        conn = get_db()
        inv_count = conn.execute("SELECT COUNT(*) FROM ap_invoice WHERE vendor_id=?", (vid,)).fetchone()[0]; conn.close()
        msg = "Delete this vendor?"
        if inv_count: msg += f"\n\nWarning: {inv_count} invoice(s) reference this vendor. They will also be deleted."
        if QtWidgets.QMessageBox.question(self,"Confirm Delete",msg,QtWidgets.QMessageBox.StandardButton.Yes|QtWidgets.QMessageBox.StandardButton.No) == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            inv_ids = [r[0] for r in conn.execute("SELECT id FROM ap_invoice WHERE vendor_id=?", (vid,)).fetchall()]
            for iid in inv_ids: conn.execute("DELETE FROM ap_payment WHERE invoice_id=?", (iid,))
            conn.execute("DELETE FROM ap_invoice WHERE vendor_id=?", (vid,))
            conn.execute("DELETE FROM vendors WHERE id=?", (vid,))
            conn.commit(); conn.close(); self._vend_clear(); self._load_vendors(); self._refresh_invoices()

    # ── Invoice data ───────────────────────────────────────────────────────

    def _refresh_invoices(self):
        vid    = self.inv_vend_filter.currentData()
        status = self.inv_status_filter.currentText()
        from_s = self.inv_from.date().toString("yyyy-MM-dd")
        to_s   = self.inv_to.date().toString("yyyy-MM-dd")
        conn   = get_db()
        q = ("SELECT ai.id, ai.invoice_number, v.vendor_name, ai.invoice_date, ai.due_date, "
             "ai.amount, COALESCE(p.paid,0) as paid, ai.status "
             "FROM ap_invoice ai JOIN vendors v ON v.id=ai.vendor_id "
             "LEFT JOIN (SELECT invoice_id, SUM(amount) as paid FROM ap_payment GROUP BY invoice_id) p ON p.invoice_id=ai.id "
             "WHERE ai.invoice_date BETWEEN ? AND ?")
        params = [from_s, to_s]
        if vid:    q += " AND ai.vendor_id=?";  params.append(vid)
        if status != "(all status)": q += " AND ai.status=?"; params.append(status)
        q += " ORDER BY ai.invoice_date DESC"
        rows = conn.execute(q, params).fetchall(); conn.close()

        self.inv_table.setRowCount(0); self._invoice_row_ids = []
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        for row in rows:
            r = self.inv_table.rowCount(); self.inv_table.insertRow(r)
            self._invoice_row_ids.append(row["id"])
            balance = row["amount"] - row["paid"]
            color = STATUS_COLORS.get(row["status"], QtGui.QColor(255,255,255))
            for c, (val, algn) in enumerate([
                (row["invoice_number"], QtCore.Qt.AlignmentFlag.AlignLeft|QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["vendor_name"],    QtCore.Qt.AlignmentFlag.AlignLeft|QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["invoice_date"],   QtCore.Qt.AlignmentFlag.AlignCenter|QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["due_date"],       QtCore.Qt.AlignmentFlag.AlignCenter|QtCore.Qt.AlignmentFlag.AlignVCenter),
                (_money(row["amount"]), right), (_money(row["paid"]), right),
                (_money(balance),       right),
                (row["status"].upper(), QtCore.Qt.AlignmentFlag.AlignCenter|QtCore.Qt.AlignmentFlag.AlignVCenter),
            ]):
                item = _ro(val, algn); item.setBackground(color); self.inv_table.setItem(r, c, item)
        self.inv_detail_grp.setVisible(False)

    def _inv_show_all(self):
        self.inv_vend_filter.setCurrentIndex(0); self.inv_status_filter.setCurrentIndex(0)
        self.inv_from.setDate(QtCore.QDate(2000,1,1)); self.inv_to.setDate(QtCore.QDate.currentDate())
        self._refresh_invoices()

    def _on_inv_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._invoice_row_ids): return
        inv_id = self._invoice_row_ids[row]
        conn = get_db()
        inv = conn.execute("SELECT ai.*, v.vendor_name FROM ap_invoice ai JOIN vendors v ON v.id=ai.vendor_id WHERE ai.id=?", (inv_id,)).fetchone()
        payments = conn.execute("SELECT * FROM ap_payment WHERE invoice_id=? ORDER BY payment_date", (inv_id,)).fetchall()
        conn.close()
        paid_total = sum(p["amount"] for p in payments)
        self.inv_detail_lbl.setText(
            f"{inv['invoice_number']}  |  {inv['vendor_name']}  |  "
            f"Date: {inv['invoice_date']}  |  Due: {inv['due_date']}  |  "
            f"Amount: {_money(inv['amount'])}  |  Paid: {_money(paid_total)}  |  "
            f"Balance: {_money(inv['amount']-paid_total)}  |  Status: {inv['status'].upper()}"
            + (f"\nDescription: {inv['description']}" if inv["description"] else ""))
        self.pay_hist_table.setRowCount(0)
        for p in payments:
            r = self.pay_hist_table.rowCount(); self.pay_hist_table.insertRow(r)
            for c, v in enumerate([p["payment_date"],_money(p["amount"]),p["payment_method"],p["reference"] or "",p["notes"] or ""]):
                self.pay_hist_table.setItem(r, c, _ro(v))
        self.inv_detail_grp.setVisible(True)

    def _on_new_invoice(self):
        vid = self.inv_vend_filter.currentData()
        dlg = NewInvoiceDialog(self, preselect_vendor_id=vid)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_invoices(); self._refresh_aging()

    def _on_record_payment(self):
        row = self.inv_table.currentRow()
        if row < 0 or row >= len(self._invoice_row_ids): QtWidgets.QMessageBox.warning(self,"No Selection","Select an invoice first."); return
        inv_id = self._invoice_row_ids[row]
        conn = get_db(); status = conn.execute("SELECT status FROM ap_invoice WHERE id=?", (inv_id,)).fetchone()["status"]; conn.close()
        if status in ("paid","void"): QtWidgets.QMessageBox.information(self,"Cannot Pay",f"Invoice is already {status}."); return
        dlg = RecordPaymentDialog(inv_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_invoices(); self._refresh_aging()
            self._on_inv_row_clicked(self.inv_table.model().index(row, 0))

    def _on_void_invoice(self):
        row = self.inv_table.currentRow()
        if row < 0 or row >= len(self._invoice_row_ids): QtWidgets.QMessageBox.warning(self,"No Selection","Select an invoice first."); return
        inv_id = self._invoice_row_ids[row]
        if QtWidgets.QMessageBox.question(self,"Void Invoice","Mark this invoice as void?",
                QtWidgets.QMessageBox.StandardButton.Yes|QtWidgets.QMessageBox.StandardButton.No) == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db(); conn.execute("UPDATE ap_invoice SET status='void' WHERE id=?", (inv_id,)); conn.commit(); conn.close()
            self._refresh_invoices(); self._refresh_aging()

    # ── Aging data ─────────────────────────────────────────────────────────

    def _refresh_aging(self):
        conn = get_db()
        rows = conn.execute("""
            SELECT v.vendor_name,
                SUM(CASE WHEN CAST(julianday('now')-julianday(ai.invoice_date) AS INT) <= 30
                         THEN ai.amount - COALESCE(p.paid,0) ELSE 0 END) b0,
                SUM(CASE WHEN CAST(julianday('now')-julianday(ai.invoice_date) AS INT) BETWEEN 31 AND 60
                         THEN ai.amount - COALESCE(p.paid,0) ELSE 0 END) b31,
                SUM(CASE WHEN CAST(julianday('now')-julianday(ai.invoice_date) AS INT) BETWEEN 61 AND 90
                         THEN ai.amount - COALESCE(p.paid,0) ELSE 0 END) b61,
                SUM(CASE WHEN CAST(julianday('now')-julianday(ai.invoice_date) AS INT) > 90
                         THEN ai.amount - COALESCE(p.paid,0) ELSE 0 END) b91
            FROM ap_invoice ai
            JOIN vendors v ON v.id=ai.vendor_id
            LEFT JOIN (SELECT invoice_id, SUM(amount) as paid FROM ap_payment GROUP BY invoice_id) p ON p.invoice_id=ai.id
            WHERE ai.status IN ('open','partial')
            GROUP BY v.id, v.vendor_name
            ORDER BY v.vendor_name
        """).fetchall(); conn.close()
        self.aging_table.setRowCount(0)
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        totals = [0.0]*4
        for row in rows:
            b = [row["b0"],row["b31"],row["b61"],row["b91"]]
            total = sum(b)
            if total <= 0: continue
            r = self.aging_table.rowCount(); self.aging_table.insertRow(r)
            self.aging_table.setItem(r, 0, _ro(row["vendor_name"]))
            for c, (v, t) in enumerate(zip(b, totals)):
                self.aging_table.setItem(r, c+1, _ro(_money(v), right))
                totals[c] += v
            self.aging_table.setItem(r, 5, _ro(_money(total), right))
        self.aging_totals_lbl.setText(
            f"Totals —  0–30: {_money(totals[0])}   31–60: {_money(totals[1])}   "
            f"61–90: {_money(totals[2])}   91+: {_money(totals[3])}   "
            f"Total Outstanding: {_money(sum(totals))}")


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = AccountsPayable(sys.argv[1] if len(sys.argv) > 1 else None)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
