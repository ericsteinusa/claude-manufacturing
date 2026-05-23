"""
General_ledger.py — General Ledger module
Tabs: Chart of Accounts | Journal Entries | Trial Balance | Ledger View
"""
import sys
import os
import sqlite3
import csv
from PyQt6 import QtCore, QtGui, QtWidgets

# ── database ─────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "company.db")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS gl_account (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT    NOT NULL UNIQUE,
            account_name   TEXT    NOT NULL,
            account_type   TEXT    NOT NULL,   -- Asset/Liability/Equity/Revenue/Expense/COGS
            account_sub    TEXT    DEFAULT '',
            is_active      INTEGER DEFAULT 1,
            notes          TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS gl_journal (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_date TEXT    NOT NULL,
            reference    TEXT    DEFAULT '',
            description  TEXT    DEFAULT '',
            posted       INTEGER DEFAULT 0,
            created_by   TEXT    DEFAULT '',
            created_at   TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS gl_journal_line (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_id  INTEGER NOT NULL REFERENCES gl_journal(id) ON DELETE CASCADE,
            account_id  INTEGER NOT NULL REFERENCES gl_account(id),
            debit       REAL    DEFAULT 0.0,
            credit      REAL    DEFAULT 0.0,
            memo        TEXT    DEFAULT ''
        );
        """)
        # Seed a standard manufacturing chart of accounts if empty
        if con.execute("SELECT COUNT(*) FROM gl_account").fetchone()[0] == 0:
            _seed_coa(con)


def _seed_coa(con):
    accounts = [
        # Assets
        ("1000", "Cash", "Asset", "Current"),
        ("1010", "Petty Cash", "Asset", "Current"),
        ("1100", "Accounts Receivable", "Asset", "Current"),
        ("1150", "Allowance for Doubtful Accts", "Asset", "Current"),
        ("1200", "Raw Materials Inventory", "Asset", "Current"),
        ("1210", "Work in Process Inventory", "Asset", "Current"),
        ("1220", "Finished Goods Inventory", "Asset", "Current"),
        ("1300", "Prepaid Expenses", "Asset", "Current"),
        ("1500", "Property, Plant & Equipment", "Asset", "Fixed"),
        ("1510", "Accumulated Depreciation", "Asset", "Fixed"),
        ("1600", "Other Assets", "Asset", "Other"),
        # Liabilities
        ("2000", "Accounts Payable", "Liability", "Current"),
        ("2100", "Accrued Liabilities", "Liability", "Current"),
        ("2200", "Payroll Liabilities", "Liability", "Current"),
        ("2300", "Sales Tax Payable", "Liability", "Current"),
        ("2400", "Notes Payable - Short Term", "Liability", "Current"),
        ("2500", "Notes Payable - Long Term", "Liability", "Long-term"),
        ("2600", "Other Long-Term Liabilities", "Liability", "Long-term"),
        # Equity
        ("3000", "Common Stock", "Equity", ""),
        ("3100", "Retained Earnings", "Equity", ""),
        ("3200", "Dividends Paid", "Equity", ""),
        ("3900", "Current Year Earnings", "Equity", ""),
        # Revenue
        ("4000", "Sales Revenue", "Revenue", "Operating"),
        ("4100", "Service Revenue", "Revenue", "Operating"),
        ("4200", "Shipping & Handling Income", "Revenue", "Operating"),
        ("4900", "Other Income", "Revenue", "Other"),
        # Cost of Goods Sold
        ("5000", "Cost of Goods Sold", "COGS", ""),
        ("5100", "Raw Materials Used", "COGS", ""),
        ("5200", "Direct Labor", "COGS", ""),
        ("5300", "Manufacturing Overhead", "COGS", ""),
        ("5400", "Freight & Shipping", "COGS", ""),
        # Expenses
        ("6000", "Salaries & Wages", "Expense", "Operating"),
        ("6100", "Payroll Taxes", "Expense", "Operating"),
        ("6200", "Rent Expense", "Expense", "Operating"),
        ("6300", "Utilities", "Expense", "Operating"),
        ("6400", "Insurance", "Expense", "Operating"),
        ("6500", "Depreciation Expense", "Expense", "Operating"),
        ("6600", "Office Supplies", "Expense", "Operating"),
        ("6700", "Marketing & Advertising", "Expense", "Operating"),
        ("6800", "Professional Services", "Expense", "Operating"),
        ("6900", "Travel & Entertainment", "Expense", "Operating"),
        ("7000", "Interest Expense", "Expense", "Non-operating"),
        ("7100", "Bank Charges", "Expense", "Non-operating"),
        ("7900", "Other Expense", "Expense", "Other"),
    ]
    con.executemany(
        "INSERT INTO gl_account(account_number,account_name,account_type,account_sub) VALUES(?,?,?,?)",
        accounts
    )


# ── style constants ───────────────────────────────────────────────────────────
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
HDR_STYLE = "background-color:rgb(0,85,255);color:white;font-weight:bold;"
ACCT_TYPE_COLORS = {
    "Asset": QtGui.QColor(220, 240, 255),
    "Liability": QtGui.QColor(255, 235, 220),
    "Equity": QtGui.QColor(220, 255, 220),
    "Revenue": QtGui.QColor(220, 255, 235),
    "COGS": QtGui.QColor(255, 255, 210),
    "Expense": QtGui.QColor(255, 220, 220),
}
ACCT_TYPES = ["Asset", "Liability", "Equity", "Revenue", "COGS", "Expense"]


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
        return f"{float(v):,.2f}"
    except Exception:
        return "0.00"


def _export_table_to_csv(table: QtWidgets.QTableWidget, parent):
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent, "Export to CSV", "", "CSV Files (*.csv)"
    )
    if not path:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        headers = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
        w.writerow(headers)
        for r in range(table.rowCount()):
            row = []
            for c in range(table.columnCount()):
                it = table.item(r, c)
                row.append(it.text() if it else "")
            w.writerow(row)
    QtWidgets.QMessageBox.information(parent, "Export", f"Saved to:\n{path}")

# ══════════════════════════════════════════════════════════════════════════════
# Journal Entry Dialog
# ══════════════════════════════════════════════════════════════════════════════


class JournalDialog(QtWidgets.QDialog):
    """New / Edit Journal Entry dialog with line-item grid."""

    def __init__(self, parent=None, journal_id=None):
        super().__init__(parent)
        self._journal_id = journal_id
        self._accounts = []       # list of (id, number, name, type)
        self.setWindowTitle("New Journal Entry" if journal_id is None else "Edit Journal Entry")
        self.setMinimumSize(820, 580)
        self._build_ui()
        self._load_accounts()
        if journal_id:
            self._load_journal(journal_id)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        # ── header fields ──
        hdr = QtWidgets.QGroupBox("Journal Header")
        hdr.setStyleSheet("QGroupBox{font-weight:bold;}")
        hf = QtWidgets.QFormLayout(hdr)

        self.ef_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.ef_date.setDate(QtCore.QDate.currentDate())
        self.ef_ref = QtWidgets.QLineEdit()
        self.ef_ref.setPlaceholderText("e.g. JE-0001")
        self.ef_desc = QtWidgets.QLineEdit()
        self.ef_desc.setPlaceholderText("Journal description")
        self.ef_by = QtWidgets.QLineEdit()
        self.ef_by.setPlaceholderText("Your name")

        for lbl, w in [("Date*", self.ef_date), ("Reference", self.ef_ref),
                       ("Description", self.ef_desc), ("Created By", self.ef_by)]:
            hf.addRow(lbl, w)
        root.addWidget(hdr)

        # ── line items ──
        lg = QtWidgets.QGroupBox("Journal Lines  (Debits must equal Credits)")
        lg.setStyleSheet("QGroupBox{font-weight:bold;}")
        lv = QtWidgets.QVBoxLayout(lg)

        self.tbl = QtWidgets.QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Account", "Type", "Debit", "Credit", "Memo"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tbl.setColumnWidth(2, 110)
        self.tbl.setColumnWidth(3, 110)
        self.tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setDefaultSectionSize(28)
        lv.addWidget(self.tbl)

        # add/remove line buttons
        lr = QtWidgets.QHBoxLayout()
        b_add = QtWidgets.QPushButton("＋ Add Line")
        b_add.setStyleSheet(BTN_STYLE)
        b_del = QtWidgets.QPushButton("－ Remove Line")
        b_del.setStyleSheet(BTN_STYLE)
        b_add.clicked.connect(self._add_line)
        b_del.clicked.connect(self._remove_line)
        lr.addWidget(b_add)
        lr.addWidget(b_del)
        lr.addStretch()
        lv.addLayout(lr)

        # totals bar
        tot = QtWidgets.QHBoxLayout()
        tot.addStretch()
        self.lbl_debit = QtWidgets.QLabel("Debits: 0.00")
        self.lbl_credit = QtWidgets.QLabel("Credits: 0.00")
        self.lbl_diff = QtWidgets.QLabel("Difference: 0.00")
        for lbl in [self.lbl_debit, self.lbl_credit, self.lbl_diff]:
            lbl.setStyleSheet("font-weight:bold; font-size:13px; padding:0 12px;")
        tot.addWidget(self.lbl_debit)
        tot.addWidget(self.lbl_credit)
        tot.addWidget(self.lbl_diff)
        lv.addLayout(tot)

        root.addWidget(lg)

        # ── buttons ──
        bb = QtWidgets.QDialogButtonBox()
        self.btn_save = bb.addButton("Save Draft", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_post = bb.addButton("Save & Post", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        btn_cancel = bb.addButton("Cancel", QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        for b in [self.btn_save, self.btn_post]:
            b.setStyleSheet(BTN_STYLE)
        btn_cancel.setStyleSheet(BTN_STYLE)
        self.btn_save.clicked.connect(lambda: self._save(post=False))
        self.btn_post.clicked.connect(lambda: self._save(post=True))
        btn_cancel.clicked.connect(self.reject)
        root.addWidget(bb)

        # Start with 2 blank lines
        self._add_line()
        self._add_line()

    def _load_accounts(self):
        with _conn() as con:
            rows = con.execute(
                "SELECT id,account_number,account_name,account_type FROM gl_account "
                "WHERE is_active=1 ORDER BY account_number"
            ).fetchall()
        self._accounts = [(r["id"], r["account_number"], r["account_name"], r["account_type"])
                          for r in rows]

    def _acct_combo(self):
        cb = QtWidgets.QComboBox()
        cb.addItem("-- select --", 0)
        for aid, num, name, _ in self._accounts:
            cb.addItem(f"{num}  {name}", aid)
        cb.currentIndexChanged.connect(self._update_line_type)
        return cb

    def _add_line(self):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        cb = self._acct_combo()
        self.tbl.setCellWidget(r, 0, cb)
        type_item = _ro("")
        type_item.setForeground(QtGui.QColor(80, 80, 80))
        self.tbl.setItem(r, 1, type_item)
        for c in [2, 3]:
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0, 99_999_999)
            spin.setDecimals(2)
            spin.setSingleStep(1.0)
            spin.valueChanged.connect(self._update_totals)
            self.tbl.setCellWidget(r, c, spin)
        self.tbl.setItem(r, 4, QtWidgets.QTableWidgetItem(""))

    def _remove_line(self):
        rows = self.tbl.selectionModel().selectedRows()
        for r in sorted(rows, reverse=True):
            self.tbl.removeRow(r.row())
        if self.tbl.rowCount() == 0:
            self._add_line()
        self._update_totals()

    def _update_line_type(self):
        """Fill type column when an account is chosen."""
        for r in range(self.tbl.rowCount()):
            cb = self.tbl.cellWidget(r, 0)
            if cb:
                aid = cb.currentData()
                acct_type = next((t for i, _, _, t in self._accounts if i == aid), "")
                it = self.tbl.item(r, 1)
                if it:
                    it.setText(acct_type)
        self._update_totals()

    def _update_totals(self):
        dr = cr = 0.0
        for r in range(self.tbl.rowCount()):
            d = self.tbl.cellWidget(r, 2)
            c = self.tbl.cellWidget(r, 3)
            if d:
                dr += d.value()
            if c:
                cr += c.value()
        diff = dr - cr
        self.lbl_debit.setText(f"Debits: {_money(dr)}")
        self.lbl_credit.setText(f"Credits: {_money(cr)}")
        self.lbl_diff.setText(f"Difference: {_money(abs(diff))}")
        color = "green" if abs(diff) < 0.005 else "red"
        self.lbl_diff.setStyleSheet(f"font-weight:bold;font-size:13px;padding:0 12px;color:{color};")

    def _load_journal(self, jid):
        with _conn() as con:
            j = con.execute("SELECT * FROM gl_journal WHERE id=?", (jid,)).fetchone()
            if not j:
                return
            self.ef_date.setDate(QtCore.QDate.fromString(j["journal_date"], "yyyy-MM-dd"))
            self.ef_ref.setText(j["reference"] or "")
            self.ef_desc.setText(j["description"] or "")
            self.ef_by.setText(j["created_by"] or "")
            lines = con.execute(
                "SELECT * FROM gl_journal_line WHERE journal_id=? ORDER BY id", (jid,)
            ).fetchall()
        # clear default lines and reload
        while self.tbl.rowCount():
            self.tbl.removeRow(0)
        for ln in lines:
            self._add_line()
            r = self.tbl.rowCount() - 1
            cb = self.tbl.cellWidget(r, 0)
            idx = cb.findData(ln["account_id"])
            if idx >= 0:
                cb.setCurrentIndex(idx)
            dw = self.tbl.cellWidget(r, 2)
            cw = self.tbl.cellWidget(r, 3)
            if dw:
                dw.setValue(ln["debit"] or 0)
            if cw:
                cw.setValue(ln["credit"] or 0)
            memo_item = self.tbl.item(r, 4)
            if memo_item:
                memo_item.setText(ln["memo"] or "")
        self._update_line_type()

    def _save(self, post=False):
        jdate = self.ef_date.date().toString("yyyy-MM-dd")
        # Validate lines
        lines = []
        for r in range(self.tbl.rowCount()):
            cb = self.tbl.cellWidget(r, 0)
            dw = self.tbl.cellWidget(r, 2)
            cw = self.tbl.cellWidget(r, 3)
            if not cb or not dw or not cw:
                continue
            aid = cb.currentData()
            d = round(dw.value(), 2)
            c = round(cw.value(), 2)
            if aid == 0 and d == 0 and c == 0:
                continue   # blank row
            if aid == 0:
                QtWidgets.QMessageBox.warning(self, "Validation", "Please select an account for every line.")
                return
            memo_item = self.tbl.item(r, 4)
            memo = memo_item.text() if memo_item else ""
            lines.append((aid, d, c, memo))
        if not lines:
            QtWidgets.QMessageBox.warning(self, "Validation", "Add at least one journal line.")
            return
        total_d = sum(ln[1] for ln in lines)
        total_c = sum(ln[2] for ln in lines)
        if post and abs(total_d - total_c) >= 0.005:
            QtWidgets.QMessageBox.warning(
                self, "Unbalanced Entry",
                f"Debits ({_money(total_d)}) ≠ Credits ({_money(total_c)}).\n"
                "An entry must balance before it can be posted."
            )
            return
        with _conn() as con:
            if self._journal_id:
                # update
                con.execute(
                    "UPDATE gl_journal SET journal_date=?,reference=?,description=?,posted=?,created_by=? WHERE id=?",
                    (jdate, self.ef_ref.text().strip(), self.ef_desc.text().strip(),
                     1 if post else 0, self.ef_by.text().strip(), self._journal_id)
                )
                con.execute("DELETE FROM gl_journal_line WHERE journal_id=?", (self._journal_id,))
                jid = self._journal_id
            else:
                cur = con.execute(
                    "INSERT INTO gl_journal(journal_date,reference,description,posted,created_by) VALUES(?,?,?,?,?)",
                    (jdate, self.ef_ref.text().strip(), self.ef_desc.text().strip(),
                     1 if post else 0, self.ef_by.text().strip())
                )
                jid = cur.lastrowid
            con.executemany(
                "INSERT INTO gl_journal_line(journal_id,account_id,debit,credit,memo) VALUES(?,?,?,?,?)",
                [(jid, aid, d, c, memo) for aid, d, c, memo in lines]
            )
        self.accept()


# ══════════════════════════════════════════════════════════════════════════════
# Main GL Window
# ══════════════════════════════════════════════════════════════════════════════
_TAB_KEYS = {
    'gen_ledger': 3,
    'inc_stmt': 4, 'bal_sheet': 4, 'cash_flow': 4, 'cust_rpts': 4,
    'recon_acct': 5, 'pend_items': 5, 'recon_hist': 5, 'bank_rpts': 5,
}

# Inner tab index within the Financial Statements tab (tab 4)
_FS_INNER_KEYS = {
    'inc_stmt': 0,
    'bal_sheet': 1,
}


class GeneralLedgerWindow(QtWidgets.QMainWindow):
    def __init__(self, initial_tab=None):
        super().__init__()
        init_db()
        self.setWindowTitle("General Ledger")
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self._build_ui()
        self._refresh_coa()
        self._refresh_journals()
        self.statusBar().showMessage("Ready")
        if initial_tab in _TAB_KEYS:
            self.tabs.setCurrentIndex(_TAB_KEYS[initial_tab])
            if initial_tab in _FS_INNER_KEYS:
                self.fs_inner.setCurrentIndex(_FS_INNER_KEYS[initial_tab])

    def _build_ui(self):
        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        root = QtWidgets.QVBoxLayout(cw)
        root.setContentsMargins(8, 8, 8, 8)

        # title
        title = QtWidgets.QLabel("General Ledger")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;color:white;padding:4px;")
        root.addWidget(title)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_coa_tab(), "Chart of Accounts")
        self.tabs.addTab(self._build_journals_tab(), "Journal Entries")
        self.tabs.addTab(self._build_trial_tab(), "Trial Balance")
        self.tabs.addTab(self._build_ledger_tab(), "Ledger View")
        self.tabs.addTab(self._build_fs_tab(), "Financial Statements")
        self.tabs.addTab(self._build_recon_tab(), "Bank Reconciliation")

        self.tabs.currentChanged.connect(self._on_tab_change)

    # ── Chart of Accounts tab ─────────────────────────────────────────────────
    def _build_coa_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        # filter bar
        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Filter:"))
        self.coa_search = QtWidgets.QLineEdit()
        self.coa_search.setPlaceholderText("account # or name…")
        self.coa_search.textChanged.connect(self._refresh_coa)
        self.coa_type_filter = QtWidgets.QComboBox()
        self.coa_type_filter.addItem("All Types")
        for t in ACCT_TYPES:
            self.coa_type_filter.addItem(t)
        self.coa_type_filter.currentIndexChanged.connect(self._refresh_coa)
        self.coa_active_filter = QtWidgets.QCheckBox("Active Only")
        self.coa_active_filter.setChecked(True)
        self.coa_active_filter.setStyleSheet("color:white;font-weight:bold;")
        self.coa_active_filter.stateChanged.connect(self._refresh_coa)
        fb.addWidget(self.coa_search)
        fb.addWidget(self.coa_type_filter)
        fb.addWidget(self.coa_active_filter)
        fb.addStretch()
        btn_export = QtWidgets.QPushButton("Export CSV")
        btn_export.setStyleSheet(BTN_STYLE)
        btn_export.clicked.connect(lambda: _export_table_to_csv(self.coa_tbl, self))
        fb.addWidget(btn_export)
        v.addLayout(fb)

        # table
        self.coa_tbl = QtWidgets.QTableWidget(0, 6)
        self.coa_tbl.setHorizontalHeaderLabels(["Acct #", "Account Name", "Type", "Sub-type", "Active", "Notes"])
        self.coa_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.coa_tbl.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.coa_tbl.setColumnWidth(0, 80)
        self.coa_tbl.setColumnWidth(2, 100)
        self.coa_tbl.setColumnWidth(3, 100)
        self.coa_tbl.setColumnWidth(4, 60)
        self.coa_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.coa_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.coa_tbl.setAlternatingRowColors(True)
        self.coa_tbl.verticalHeader().setDefaultSectionSize(24)
        self.coa_tbl.itemSelectionChanged.connect(self._on_coa_select)
        v.addWidget(self.coa_tbl)

        # form
        fg = QtWidgets.QGroupBox("Account Details")
        fg.setStyleSheet("QGroupBox{font-weight:bold;background:white;border:1px solid #aaa;border-radius:6px;}"
                         "QGroupBox::title{padding:2px 8px;}")
        fl = QtWidgets.QFormLayout(fg)
        fl.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)

        self.coa_ef_num = QtWidgets.QLineEdit()
        self.coa_ef_num.setMaxLength(20)
        self.coa_ef_name = QtWidgets.QLineEdit()
        self.coa_ef_type = QtWidgets.QComboBox()
        for t in ACCT_TYPES:
            self.coa_ef_type.addItem(t)
        self.coa_ef_sub = QtWidgets.QLineEdit()
        self.coa_ef_sub.setPlaceholderText("e.g. Current, Fixed…")
        self.coa_ef_act = QtWidgets.QCheckBox("Active")
        self.coa_ef_act.setChecked(True)
        self.coa_ef_notes = QtWidgets.QLineEdit()

        fl.addRow("Acct # *", self.coa_ef_num)
        fl.addRow("Name *", self.coa_ef_name)
        fl.addRow("Type *", self.coa_ef_type)
        fl.addRow("Sub-type", self.coa_ef_sub)
        fl.addRow("", self.coa_ef_act)
        fl.addRow("Notes", self.coa_ef_notes)
        v.addWidget(fg)

        # buttons
        bb = QtWidgets.QHBoxLayout()
        for lbl, slot in [("Add Account", self._on_coa_add),
                          ("Update Account", self._on_coa_update),
                          ("Toggle Active", self._on_coa_toggle),
                          ("Clear", self._on_coa_clear)]:
            b = QtWidgets.QPushButton(lbl)
            b.setStyleSheet(BTN_STYLE)
            b.clicked.connect(slot)
            bb.addWidget(b)
        bb.addStretch()
        v.addLayout(bb)
        return w

    def _refresh_coa(self):
        q = "SELECT * FROM gl_account"
        params = []
        where = []
        txt = self.coa_search.text().strip()
        if txt:
            where.append("(account_number LIKE ? OR account_name LIKE ?)")
            params += [f"%{txt}%", f"%{txt}%"]
        t = self.coa_type_filter.currentText()
        if t != "All Types":
            where.append("account_type=?")
            params.append(t)
        if self.coa_active_filter.isChecked():
            where.append("is_active=1")
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY account_number"
        with _conn() as con:
            rows = con.execute(q, params).fetchall()
        self.coa_tbl.setRowCount(0)
        for row in rows:
            r = self.coa_tbl.rowCount()
            self.coa_tbl.insertRow(r)
            self.coa_tbl.setItem(r, 0, _ro(row["account_number"]))
            self.coa_tbl.setItem(r, 1, _ro(row["account_name"]))
            self.coa_tbl.setItem(r, 2, _ro(row["account_type"]))
            self.coa_tbl.setItem(r, 3, _ro(row["account_sub"]))
            self.coa_tbl.setItem(r, 4, _ro("Yes" if row["is_active"] else "No",
                                           QtCore.Qt.AlignmentFlag.AlignCenter))
            self.coa_tbl.setItem(r, 5, _ro(row["notes"]))
            color = ACCT_TYPE_COLORS.get(row["account_type"], QtGui.QColor(255, 255, 255))
            if not row["is_active"]:
                color = QtGui.QColor(210, 210, 210)
            for c in range(6):
                it = self.coa_tbl.item(r, c)
                if it:
                    it.setBackground(color)
            # store id in col 0
            self.coa_tbl.item(r, 0).setData(QtCore.Qt.ItemDataRole.UserRole, row["id"])

    def _on_coa_select(self):
        rows = self.coa_tbl.selectionModel().selectedRows()
        if not rows:
            return
        r = rows[0].row()
        self.coa_ef_num.setText(self.coa_tbl.item(r, 0).text())
        self.coa_ef_name.setText(self.coa_tbl.item(r, 1).text())
        idx = self.coa_ef_type.findText(self.coa_tbl.item(r, 2).text())
        if idx >= 0:
            self.coa_ef_type.setCurrentIndex(idx)
        self.coa_ef_sub.setText(self.coa_tbl.item(r, 3).text())
        self.coa_ef_act.setChecked(self.coa_tbl.item(r, 4).text() == "Yes")
        self.coa_ef_notes.setText(self.coa_tbl.item(r, 5).text())

    def _coa_form_values(self):
        return (
            self.coa_ef_num.text().strip(),
            self.coa_ef_name.text().strip(),
            self.coa_ef_type.currentText(),
            self.coa_ef_sub.text().strip(),
            1 if self.coa_ef_act.isChecked() else 0,
            self.coa_ef_notes.text().strip(),
        )

    def _on_coa_add(self):
        self.statusBar().showMessage("Add Account clicked")
        num, name, typ, sub, act, notes = self._coa_form_values()
        if not num or not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Account # and Name are required.")
            self.statusBar().showMessage("Validation: Account # and Name are required")
            return
        try:
            with _conn() as con:
                con.execute(
                    "INSERT INTO gl_account(account_number,account_name,account_type,account_sub,is_active,notes) "
                    "VALUES(?,?,?,?,?,?)", (num, name, typ, sub, act, notes)
                )
        except sqlite3.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate", f"Account # {num} already exists.")
            self.statusBar().showMessage(f"Duplicate: Account # {num} already exists")
            return
        self._refresh_coa()
        self._on_coa_clear()
        self.statusBar().showMessage(f"Account {num} added")

    def _selected_coa_id(self):
        rows = self.coa_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Selection", "Select an account first.")
            return None
        return self.coa_tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)

    def _on_coa_update(self):
        self.statusBar().showMessage("Update Account clicked")
        aid = self._selected_coa_id()
        if aid is None:
            return
        num, name, typ, sub, act, notes = self._coa_form_values()
        if not num or not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Account # and Name are required.")
            return
        with _conn() as con:
            con.execute(
                "UPDATE gl_account SET account_number=?,account_name=?,account_type=?,"
                "account_sub=?,is_active=?,notes=? WHERE id=?",
                (num, name, typ, sub, act, notes, aid)
            )
        self._refresh_coa()
        self.statusBar().showMessage(f"Account {num} updated")

    def _on_coa_toggle(self):
        self.statusBar().showMessage("Toggle Active clicked")
        aid = self._selected_coa_id()
        if aid is None:
            return
        with _conn() as con:
            cur = con.execute("SELECT is_active FROM gl_account WHERE id=?", (aid,)).fetchone()
            new_val = 0 if cur["is_active"] else 1
            con.execute("UPDATE gl_account SET is_active=? WHERE id=?", (new_val, aid))
        self._refresh_coa()
        self.statusBar().showMessage("Account active status toggled")

    def _on_coa_clear(self):
        self.coa_ef_num.clear()
        self.coa_ef_name.clear()
        self.coa_ef_sub.clear()
        self.coa_ef_notes.clear()
        self.coa_ef_type.setCurrentIndex(0)
        self.coa_ef_act.setChecked(True)
        self.coa_tbl.clearSelection()
        self.statusBar().showMessage("Form cleared")

    # ── Journal Entries tab ───────────────────────────────────────────────────
    def _build_journals_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        # filter bar
        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("From:"))
        self.je_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.je_from.setDate(QtCore.QDate(QtCore.QDate.currentDate().year(), 1, 1))
        fb.addWidget(self.je_from)
        fb.addWidget(QtWidgets.QLabel("To:"))
        self.je_to = QtWidgets.QDateEdit(calendarPopup=True)
        self.je_to.setDate(QtCore.QDate.currentDate())
        fb.addWidget(self.je_to)
        self.je_status_filter = QtWidgets.QComboBox()
        self.je_status_filter.addItems(["All", "Draft", "Posted"])
        fb.addWidget(self.je_status_filter)
        btn_search = QtWidgets.QPushButton("Search")
        btn_search.setStyleSheet(BTN_STYLE)
        btn_search.clicked.connect(self._refresh_journals)
        fb.addWidget(btn_search)
        fb.addStretch()
        v.addLayout(fb)

        # journal header table
        self.je_tbl = QtWidgets.QTableWidget(0, 6)
        self.je_tbl.setHorizontalHeaderLabels(["ID", "Date", "Reference", "Description", "Status", "Lines"])
        self.je_tbl.setColumnWidth(0, 50)
        self.je_tbl.setColumnWidth(1, 95)
        self.je_tbl.setColumnWidth(2, 110)
        self.je_tbl.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.je_tbl.setColumnWidth(4, 70)
        self.je_tbl.setColumnWidth(5, 55)
        self.je_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.je_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.je_tbl.setAlternatingRowColors(True)
        self.je_tbl.verticalHeader().setDefaultSectionSize(24)
        self.je_tbl.itemSelectionChanged.connect(self._on_je_select)
        v.addWidget(self.je_tbl, 2)

        # line detail table
        self.je_lines_tbl = QtWidgets.QTableWidget(0, 5)
        self.je_lines_tbl.setHorizontalHeaderLabels(["Acct #", "Account Name", "Type", "Debit", "Credit"])
        self.je_lines_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.je_lines_tbl.setColumnWidth(0, 80)
        self.je_lines_tbl.setColumnWidth(2, 90)
        self.je_lines_tbl.setColumnWidth(3, 110)
        self.je_lines_tbl.setColumnWidth(4, 110)
        self.je_lines_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.je_lines_tbl.setAlternatingRowColors(True)
        self.je_lines_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.je_lines_tbl, 1)

        # totals label
        self.je_totals_lbl = QtWidgets.QLabel("")
        self.je_totals_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.je_totals_lbl.setStyleSheet("font-weight:bold;padding:2px 8px;")
        v.addWidget(self.je_totals_lbl)

        # action buttons
        bb = QtWidgets.QHBoxLayout()
        for lbl, slot in [("New Journal", self._on_je_new),
                          ("Edit Journal", self._on_je_edit),
                          ("Post Entry", self._on_je_post),
                          ("Delete Draft", self._on_je_delete)]:
            b = QtWidgets.QPushButton(lbl)
            b.setStyleSheet(BTN_STYLE)
            b.clicked.connect(slot)
            bb.addWidget(b)
        bb.addStretch()
        v.addLayout(bb)
        return w

    def _refresh_journals(self):
        q = ("SELECT j.*, "
             "(SELECT COUNT(*) FROM gl_journal_line WHERE journal_id=j.id) AS line_count "
             "FROM gl_journal j WHERE j.journal_date>=? AND j.journal_date<=?")
        params = [self.je_from.date().toString("yyyy-MM-dd"),
                  self.je_to.date().toString("yyyy-MM-dd")]
        s = self.je_status_filter.currentText()
        if s == "Draft":
            q += " AND j.posted=0"
        elif s == "Posted":
            q += " AND j.posted=1"
        q += " ORDER BY j.journal_date DESC, j.id DESC"
        with _conn() as con:
            rows = con.execute(q, params).fetchall()
        self.je_tbl.setRowCount(0)
        for row in rows:
            r = self.je_tbl.rowCount()
            self.je_tbl.insertRow(r)
            self.je_tbl.setItem(r, 0, _ro(str(row["id"]), QtCore.Qt.AlignmentFlag.AlignRight))
            self.je_tbl.setItem(r, 1, _ro(row["journal_date"]))
            self.je_tbl.setItem(r, 2, _ro(row["reference"]))
            self.je_tbl.setItem(r, 3, _ro(row["description"]))
            posted = row["posted"]
            st_item = _ro("Posted" if posted else "Draft",
                          QtCore.Qt.AlignmentFlag.AlignCenter)
            st_item.setForeground(QtGui.QColor("green") if posted else QtGui.QColor(180, 100, 0))
            self.je_tbl.setItem(r, 4, st_item)
            self.je_tbl.setItem(r, 5, _ro(str(row["line_count"]),
                                          QtCore.Qt.AlignmentFlag.AlignCenter))
            self.je_tbl.item(r, 0).setData(QtCore.Qt.ItemDataRole.UserRole, row["id"])
        self.je_lines_tbl.setRowCount(0)
        self.je_totals_lbl.clear()

    def _on_je_select(self):
        rows = self.je_tbl.selectionModel().selectedRows()
        if not rows:
            return
        jid = self.je_tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        with _conn() as con:
            lines = con.execute(
                "SELECT l.*, a.account_number, a.account_name, a.account_type "
                "FROM gl_journal_line l "
                "JOIN gl_account a ON a.id=l.account_id "
                "WHERE l.journal_id=? ORDER BY l.id", (jid,)
            ).fetchall()
        self.je_lines_tbl.setRowCount(0)
        td = tc = 0.0
        for ln in lines:
            r = self.je_lines_tbl.rowCount()
            self.je_lines_tbl.insertRow(r)
            self.je_lines_tbl.setItem(r, 0, _ro(ln["account_number"]))
            self.je_lines_tbl.setItem(r, 1, _ro(ln["account_name"]))
            self.je_lines_tbl.setItem(r, 2, _ro(ln["account_type"]))
            self.je_lines_tbl.setItem(r, 3, _ro_r(_money(ln["debit"])))
            self.je_lines_tbl.setItem(r, 4, _ro_r(_money(ln["credit"])))
            td += ln["debit"] or 0
            tc += ln["credit"] or 0
        diff = abs(td - tc)
        bal_str = "✓ Balanced" if diff < 0.005 else f"⚠ Difference: {_money(diff)}"
        color = "green" if diff < 0.005 else "red"
        self.je_totals_lbl.setText(
            f"<span style='color:{color};'>  {bal_str}</span>   "
            f"Debits: <b>{_money(td)}</b>   Credits: <b>{_money(tc)}</b>"
        )

    def _selected_je_id(self):
        rows = self.je_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Selection", "Select a journal entry first.")
            return None, None
        r = rows[0].row()
        jid = self.je_tbl.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        posted = self.je_tbl.item(r, 4).text() == "Posted"
        return jid, posted

    def _on_je_new(self):
        dlg = JournalDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_journals()

    def _on_je_edit(self):
        jid, posted = self._selected_je_id()
        if jid is None:
            return
        if posted:
            QtWidgets.QMessageBox.warning(self, "Posted", "Posted entries cannot be edited.")
            return
        dlg = JournalDialog(self, journal_id=jid)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_journals()

    def _on_je_post(self):
        jid, posted = self._selected_je_id()
        if jid is None:
            return
        if posted:
            QtWidgets.QMessageBox.information(self, "Already Posted", "This entry is already posted.")
            return
        # check balance
        with _conn() as con:
            agg = con.execute(
                "SELECT SUM(debit) AS td, SUM(credit) AS tc FROM gl_journal_line WHERE journal_id=?",
                (jid,)
            ).fetchone()
        td = agg["td"] or 0
        tc = agg["tc"] or 0
        if abs(td - tc) >= 0.005:
            QtWidgets.QMessageBox.warning(
                self, "Unbalanced",
                f"Cannot post: Debits ({_money(td)}) ≠ Credits ({_money(tc)})."
            )
            return
        with _conn() as con:
            con.execute("UPDATE gl_journal SET posted=1 WHERE id=?", (jid,))
        self._refresh_journals()

    def _on_je_delete(self):
        jid, posted = self._selected_je_id()
        if jid is None:
            return
        if posted:
            QtWidgets.QMessageBox.warning(self, "Posted", "Posted entries cannot be deleted.")
            return
        if QtWidgets.QMessageBox.question(
            self, "Delete", "Delete this draft journal entry?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute("DELETE FROM gl_journal WHERE id=?", (jid,))
            self._refresh_journals()

    # ── Trial Balance tab ─────────────────────────────────────────────────────
    def _build_trial_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Period From:"))
        self.tb_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.tb_from.setDate(QtCore.QDate(QtCore.QDate.currentDate().year(), 1, 1))
        fb.addWidget(self.tb_from)
        fb.addWidget(QtWidgets.QLabel("To:"))
        self.tb_to = QtWidgets.QDateEdit(calendarPopup=True)
        self.tb_to.setDate(QtCore.QDate.currentDate())
        fb.addWidget(self.tb_to)
        self.tb_posted_only = QtWidgets.QCheckBox("Posted Only")
        self.tb_posted_only.setChecked(False)
        self.tb_posted_only.setStyleSheet("color:white;font-weight:bold;")
        fb.addWidget(self.tb_posted_only)
        btn_run = QtWidgets.QPushButton("Run Trial Balance")
        btn_run.setStyleSheet(BTN_STYLE)
        btn_run.clicked.connect(self._refresh_trial)
        fb.addWidget(btn_run)
        fb.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BTN_STYLE)
        btn_exp.clicked.connect(lambda: _export_table_to_csv(self.tb_tbl, self))
        fb.addWidget(btn_exp)
        v.addLayout(fb)

        self.tb_tbl = QtWidgets.QTableWidget(0, 6)
        self.tb_tbl.setHorizontalHeaderLabels(
            ["Acct #", "Account Name", "Type", "Total Debits", "Total Credits", "Balance"]
        )
        self.tb_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tb_tbl.setColumnWidth(0, 80)
        self.tb_tbl.setColumnWidth(2, 100)
        self.tb_tbl.setColumnWidth(3, 120)
        self.tb_tbl.setColumnWidth(4, 120)
        self.tb_tbl.setColumnWidth(5, 120)
        self.tb_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tb_tbl.setAlternatingRowColors(True)
        self.tb_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.tb_tbl)

        self.tb_totals_lbl = QtWidgets.QLabel("")
        self.tb_totals_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.tb_totals_lbl.setStyleSheet("font-weight:bold;font-size:13px;padding:4px 8px;")
        v.addWidget(self.tb_totals_lbl)
        return w

    def _refresh_trial(self):
        d0 = self.tb_from.date().toString("yyyy-MM-dd")
        d1 = self.tb_to.date().toString("yyyy-MM-dd")
        posted_clause = "AND j.posted=1" if self.tb_posted_only.isChecked() else ""
        sql = f"""
            SELECT a.account_number, a.account_name, a.account_type,
                   COALESCE(SUM(l.debit),0)  AS total_debit,
                   COALESCE(SUM(l.credit),0) AS total_credit
            FROM gl_account a
            LEFT JOIN gl_journal_line l ON l.account_id=a.id
            LEFT JOIN gl_journal j ON j.id=l.journal_id
                AND j.journal_date>=? AND j.journal_date<=?
                {posted_clause}
            WHERE a.is_active=1
            GROUP BY a.id
            ORDER BY a.account_number
        """
        with _conn() as con:
            rows = con.execute(sql, (d0, d1)).fetchall()
        self.tb_tbl.setRowCount(0)
        grand_dr = grand_cr = 0.0
        for row in rows:
            td = row["total_debit"]
            tc = row["total_credit"]
            # natural balance: Asset/Expense/COGS = debit-normal; Liability/Equity/Revenue = credit-normal
            if row["account_type"] in ("Asset", "Expense", "COGS"):
                bal = td - tc
            else:
                bal = tc - td
            if td == 0 and tc == 0:
                continue   # skip zero-activity accounts
            r = self.tb_tbl.rowCount()
            self.tb_tbl.insertRow(r)
            self.tb_tbl.setItem(r, 0, _ro(row["account_number"]))
            self.tb_tbl.setItem(r, 1, _ro(row["account_name"]))
            self.tb_tbl.setItem(r, 2, _ro(row["account_type"]))
            self.tb_tbl.setItem(r, 3, _ro_r(_money(td)))
            self.tb_tbl.setItem(r, 4, _ro_r(_money(tc)))
            bal_item = _ro_r(_money(bal))
            if bal < 0:
                bal_item.setForeground(QtGui.QColor("red"))
            self.tb_tbl.setItem(r, 5, bal_item)
            color = ACCT_TYPE_COLORS.get(row["account_type"], QtGui.QColor(255, 255, 255))
            for c in range(6):
                it = self.tb_tbl.item(r, c)
                if it:
                    it.setBackground(color)
            grand_dr += td
            grand_cr += tc

        diff = abs(grand_dr - grand_cr)
        bal_str = "✓ Trial Balance is balanced" if diff < 0.005 else f"⚠ Out of balance by {_money(diff)}"
        color = "green" if diff < 0.005 else "red"
        self.tb_totals_lbl.setText(
            f"<span style='color:{color};'>{bal_str}</span>   "
            f"Total Debits: <b>{_money(grand_dr)}</b>   "
            f"Total Credits: <b>{_money(grand_cr)}</b>"
        )

    # ── Ledger View tab ───────────────────────────────────────────────────────
    def _build_ledger_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Account:"))
        self.lv_acct = QtWidgets.QComboBox()
        self.lv_acct.setMinimumWidth(300)
        fb.addWidget(self.lv_acct)
        fb.addWidget(QtWidgets.QLabel("From:"))
        self.lv_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.lv_from.setDate(QtCore.QDate(QtCore.QDate.currentDate().year(), 1, 1))
        fb.addWidget(self.lv_from)
        fb.addWidget(QtWidgets.QLabel("To:"))
        self.lv_to = QtWidgets.QDateEdit(calendarPopup=True)
        self.lv_to.setDate(QtCore.QDate.currentDate())
        fb.addWidget(self.lv_to)
        self.lv_posted_only = QtWidgets.QCheckBox("Posted Only")
        self.lv_posted_only.setChecked(False)
        self.lv_posted_only.setStyleSheet("color:white;font-weight:bold;")
        fb.addWidget(self.lv_posted_only)
        btn_run = QtWidgets.QPushButton("View Ledger")
        btn_run.setStyleSheet(BTN_STYLE)
        btn_run.clicked.connect(self._refresh_ledger)
        fb.addWidget(btn_run)
        fb.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BTN_STYLE)
        btn_exp.clicked.connect(lambda: _export_table_to_csv(self.lv_tbl, self))
        fb.addWidget(btn_exp)
        v.addLayout(fb)

        self.lv_tbl = QtWidgets.QTableWidget(0, 7)
        self.lv_tbl.setHorizontalHeaderLabels(
            ["Date", "Journal ID", "Reference", "Description", "Debit", "Credit", "Running Balance"]
        )
        self.lv_tbl.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.lv_tbl.setColumnWidth(0, 95)
        self.lv_tbl.setColumnWidth(1, 75)
        self.lv_tbl.setColumnWidth(2, 110)
        self.lv_tbl.setColumnWidth(4, 110)
        self.lv_tbl.setColumnWidth(5, 110)
        self.lv_tbl.setColumnWidth(6, 130)
        self.lv_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lv_tbl.setAlternatingRowColors(True)
        self.lv_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.lv_tbl)

        self.lv_summary_lbl = QtWidgets.QLabel("")
        self.lv_summary_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.lv_summary_lbl.setStyleSheet("font-weight:bold;font-size:13px;padding:4px 8px;")
        v.addWidget(self.lv_summary_lbl)
        return w

    def _populate_lv_acct_combo(self):
        self.lv_acct.clear()
        with _conn() as con:
            rows = con.execute(
                "SELECT id,account_number,account_name,account_type FROM gl_account "
                "WHERE is_active=1 ORDER BY account_number"
            ).fetchall()
        for row in rows:
            self.lv_acct.addItem(f"{row['account_number']}  {row['account_name']}", row["id"])

    def _refresh_ledger(self):
        aid = self.lv_acct.currentData()
        if not aid:
            return
        d0 = self.lv_from.date().toString("yyyy-MM-dd")
        d1 = self.lv_to.date().toString("yyyy-MM-dd")
        posted_clause = "AND j.posted=1" if self.lv_posted_only.isChecked() else ""
        sql = f"""
            SELECT j.journal_date, j.id AS jid, j.reference, j.description,
                   l.debit, l.credit
            FROM gl_journal_line l
            JOIN gl_journal j ON j.id=l.journal_id
            WHERE l.account_id=?
              AND j.journal_date>=? AND j.journal_date<=?
              {posted_clause}
            ORDER BY j.journal_date, j.id
        """
        with _conn() as con:
            # get account type for natural balance direction
            acct = con.execute("SELECT account_type FROM gl_account WHERE id=?", (aid,)).fetchone()
            rows = con.execute(sql, (aid, d0, d1)).fetchall()

        acct_type = acct["account_type"] if acct else "Asset"
        debit_normal = acct_type in ("Asset", "Expense", "COGS")

        self.lv_tbl.setRowCount(0)
        running = 0.0
        total_d = total_c = 0.0
        for row in rows:
            d = row["debit"] or 0
            c = row["credit"] or 0
            if debit_normal:
                running += d - c
            else:
                running += c - d
            total_d += d
            total_c += c
            r = self.lv_tbl.rowCount()
            self.lv_tbl.insertRow(r)
            self.lv_tbl.setItem(r, 0, _ro(row["journal_date"]))
            self.lv_tbl.setItem(r, 1, _ro(str(row["jid"]), QtCore.Qt.AlignmentFlag.AlignRight))
            self.lv_tbl.setItem(r, 2, _ro(row["reference"]))
            self.lv_tbl.setItem(r, 3, _ro(row["description"]))
            self.lv_tbl.setItem(r, 4, _ro_r(_money(d) if d else ""))
            self.lv_tbl.setItem(r, 5, _ro_r(_money(c) if c else ""))
            bal_item = _ro_r(_money(running))
            if running < 0:
                bal_item.setForeground(QtGui.QColor("red"))
            self.lv_tbl.setItem(r, 6, bal_item)

        self.lv_summary_lbl.setText(
            f"Transactions: <b>{self.lv_tbl.rowCount()}</b>   "
            f"Total Debits: <b>{_money(total_d)}</b>   "
            f"Total Credits: <b>{_money(total_c)}</b>   "
            f"Ending Balance: <b>{_money(running)}</b>"
        )

    # ── Financial Statements tab ──────────────────────────────────────────────
    def _build_fs_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        self.fs_inner = QtWidgets.QTabWidget()
        self.fs_inner.setStyleSheet(TAB_STYLE)
        self.fs_inner.addTab(self._build_income_stmt_tab(), "Income Statement")
        self.fs_inner.addTab(self._build_balance_sheet_tab(), "Balance Sheet")
        v.addWidget(self.fs_inner)
        return w

    def _build_income_stmt_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("From:"))
        self.is_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.is_from.setDate(QtCore.QDate(QtCore.QDate.currentDate().year(), 1, 1))
        fb.addWidget(self.is_from)
        fb.addWidget(QtWidgets.QLabel("To:"))
        self.is_to = QtWidgets.QDateEdit(calendarPopup=True)
        self.is_to.setDate(QtCore.QDate.currentDate())
        fb.addWidget(self.is_to)
        self.is_posted_only = QtWidgets.QCheckBox("Posted Only")
        self.is_posted_only.setChecked(False)
        self.is_posted_only.setStyleSheet("color:white;font-weight:bold;")
        fb.addWidget(self.is_posted_only)
        btn_run = QtWidgets.QPushButton("Run")
        btn_run.setStyleSheet(BTN_STYLE)
        btn_run.clicked.connect(self._refresh_income_stmt)
        fb.addWidget(btn_run)
        fb.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BTN_STYLE)
        btn_exp.clicked.connect(lambda: _export_table_to_csv(self.is_tbl, self))
        fb.addWidget(btn_exp)
        v.addLayout(fb)

        self.is_tbl = QtWidgets.QTableWidget(0, 2)
        self.is_tbl.setHorizontalHeaderLabels(["Description", "Amount"])
        self.is_tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.is_tbl.setColumnWidth(1, 160)
        self.is_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.is_tbl.verticalHeader().setVisible(False)
        self.is_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.is_tbl)
        return w

    def _build_balance_sheet_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("As Of:"))
        self.bs_as_of = QtWidgets.QDateEdit(calendarPopup=True)
        self.bs_as_of.setDate(QtCore.QDate.currentDate())
        fb.addWidget(self.bs_as_of)
        fb.addWidget(QtWidgets.QLabel("Fiscal Year Start:"))
        self.bs_fy_start = QtWidgets.QDateEdit(calendarPopup=True)
        self.bs_fy_start.setDate(QtCore.QDate(QtCore.QDate.currentDate().year(), 1, 1))
        fb.addWidget(self.bs_fy_start)
        self.bs_posted_only = QtWidgets.QCheckBox("Posted Only")
        self.bs_posted_only.setChecked(False)
        self.bs_posted_only.setStyleSheet("color:white;font-weight:bold;")
        fb.addWidget(self.bs_posted_only)
        btn_run = QtWidgets.QPushButton("Run")
        btn_run.setStyleSheet(BTN_STYLE)
        btn_run.clicked.connect(self._refresh_balance_sheet)
        fb.addWidget(btn_run)
        fb.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BTN_STYLE)
        btn_exp.clicked.connect(lambda: _export_table_to_csv(self.bs_tbl, self))
        fb.addWidget(btn_exp)
        v.addLayout(fb)

        self.bs_tbl = QtWidgets.QTableWidget(0, 2)
        self.bs_tbl.setHorizontalHeaderLabels(["Description", "Amount"])
        self.bs_tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.bs_tbl.setColumnWidth(1, 160)
        self.bs_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bs_tbl.verticalHeader().setVisible(False)
        self.bs_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.bs_tbl)

        self.bs_balance_lbl = QtWidgets.QLabel("")
        self.bs_balance_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.bs_balance_lbl.setStyleSheet("font-weight:bold;font-size:13px;padding:4px 8px;")
        v.addWidget(self.bs_balance_lbl)
        return w

    # ── FS row helpers ────────────────────────────────────────────────────────
    def _fs_section_header(self, tbl, label):
        r = tbl.rowCount()
        tbl.insertRow(r)
        item = _ro(label.upper())
        item.setBackground(QtGui.QColor(0, 85, 255))
        item.setForeground(QtGui.QColor(255, 255, 255))
        f = item.font()
        f.setBold(True)
        item.setFont(f)
        tbl.setItem(r, 0, item)
        amt = _ro("")
        amt.setBackground(QtGui.QColor(0, 85, 255))
        tbl.setItem(r, 1, amt)
        tbl.setRowHeight(r, 28)

    def _fs_detail_row(self, tbl, label, amount, color=None):
        r = tbl.rowCount()
        tbl.insertRow(r)
        lbl_item = _ro(f"    {label}")
        amt_item = _ro_r(_money(amount) if amount != 0 else "")
        if color:
            lbl_item.setBackground(color)
            amt_item.setBackground(color)
        tbl.setItem(r, 0, lbl_item)
        tbl.setItem(r, 1, amt_item)

    def _fs_subtotal_row(self, tbl, label, amount, bg=None):
        r = tbl.rowCount()
        tbl.insertRow(r)
        lbl_item = _ro(label)
        amt_item = _ro_r(_money(amount))
        for it in (lbl_item, amt_item):
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            it.setBackground(bg or QtGui.QColor(210, 230, 255))
        tbl.setItem(r, 0, lbl_item)
        tbl.setItem(r, 1, amt_item)
        tbl.setRowHeight(r, 26)

    def _fs_total_row(self, tbl, label, amount, positive_good=True):
        r = tbl.rowCount()
        tbl.insertRow(r)
        lbl_item = _ro(label)
        amt_item = _ro_r(_money(amount))
        fg = QtGui.QColor("green") if (amount >= 0 if positive_good else True) else QtGui.QColor("red")
        bg = QtGui.QColor(0, 85, 255)
        for it in (lbl_item, amt_item):
            f = it.font()
            f.setBold(True)
            it.setFont(f)
            it.setBackground(bg)
            it.setForeground(QtGui.QColor(255, 255, 255))
        amt_item.setForeground(fg)
        tbl.setItem(r, 0, lbl_item)
        tbl.setItem(r, 1, amt_item)
        tbl.setRowHeight(r, 28)

    def _fs_spacer(self, tbl):
        r = tbl.rowCount()
        tbl.insertRow(r)
        tbl.setItem(r, 0, _ro(""))
        tbl.setItem(r, 1, _ro(""))
        tbl.setRowHeight(r, 10)

    # ── Income Statement ──────────────────────────────────────────────────────
    def _refresh_income_stmt(self):
        d0 = self.is_from.date().toString("yyyy-MM-dd")
        d1 = self.is_to.date().toString("yyyy-MM-dd")
        pc = "AND j.posted=1" if self.is_posted_only.isChecked() else ""
        sql = f"""
            SELECT a.account_name, a.account_type,
                   COALESCE(SUM(l.debit),0)  AS td,
                   COALESCE(SUM(l.credit),0) AS tc
            FROM gl_account a
            LEFT JOIN gl_journal_line l ON l.account_id=a.id
            LEFT JOIN gl_journal j ON j.id=l.journal_id
                AND j.journal_date>=? AND j.journal_date<=? {pc}
            WHERE a.is_active=1
              AND a.account_type IN ('Revenue','COGS','Expense')
            GROUP BY a.id ORDER BY a.account_number
        """
        with _conn() as con:
            rows = con.execute(sql, (d0, d1)).fetchall()

        rev_rows = [(r["account_name"], r["tc"] - r["td"]) for r in rows if r["account_type"] == "Revenue"]
        cogs_rows = [(r["account_name"], r["td"] - r["tc"]) for r in rows if r["account_type"] == "COGS"]
        exp_rows = [(r["account_name"], r["td"] - r["tc"]) for r in rows if r["account_type"] == "Expense"]

        total_rev = sum(v for _, v in rev_rows)
        total_cogs = sum(v for _, v in cogs_rows)
        gross = total_rev - total_cogs
        total_exp = sum(v for _, v in exp_rows)
        net_income = gross - total_exp

        tbl = self.is_tbl
        tbl.setRowCount(0)
        c_rev = ACCT_TYPE_COLORS["Revenue"]
        c_cogs = ACCT_TYPE_COLORS["COGS"]
        c_exp = ACCT_TYPE_COLORS["Expense"]

        self._fs_section_header(tbl, "Revenue")
        for name, amt in rev_rows:
            if amt != 0:
                self._fs_detail_row(tbl, name, amt, c_rev)
        self._fs_subtotal_row(tbl, "Total Revenue", total_rev, QtGui.QColor(190, 230, 200))
        self._fs_spacer(tbl)

        self._fs_section_header(tbl, "Cost of Goods Sold")
        for name, amt in cogs_rows:
            if amt != 0:
                self._fs_detail_row(tbl, name, amt, c_cogs)
        self._fs_subtotal_row(tbl, "Total Cost of Goods Sold", total_cogs, QtGui.QColor(240, 240, 180))
        self._fs_spacer(tbl)

        self._fs_total_row(tbl, "Gross Profit", gross)
        self._fs_spacer(tbl)

        self._fs_section_header(tbl, "Operating Expenses")
        for name, amt in exp_rows:
            if amt != 0:
                self._fs_detail_row(tbl, name, amt, c_exp)
        self._fs_subtotal_row(tbl, "Total Operating Expenses", total_exp, QtGui.QColor(255, 200, 200))
        self._fs_spacer(tbl)

        self._fs_total_row(tbl, "Net Income", net_income, positive_good=True)

    # ── Balance Sheet ─────────────────────────────────────────────────────────
    def _refresh_balance_sheet(self):
        d1 = self.bs_as_of.date().toString("yyyy-MM-dd")
        fy0 = self.bs_fy_start.date().toString("yyyy-MM-dd")
        pc = "AND j.posted=1" if self.bs_posted_only.isChecked() else ""

        sql_bal = f"""
            SELECT a.account_number, a.account_name, a.account_type, a.account_sub,
                   COALESCE(SUM(l.debit),0)  AS td,
                   COALESCE(SUM(l.credit),0) AS tc
            FROM gl_account a
            LEFT JOIN gl_journal_line l ON l.account_id=a.id
            LEFT JOIN gl_journal j ON j.id=l.journal_id
                AND j.journal_date<=? {pc}
            WHERE a.is_active=1
              AND a.account_type IN ('Asset','Liability','Equity')
            GROUP BY a.id ORDER BY a.account_number
        """
        sql_nie = f"""
            SELECT a.account_type,
                   COALESCE(SUM(l.debit),0)  AS td,
                   COALESCE(SUM(l.credit),0) AS tc
            FROM gl_account a
            LEFT JOIN gl_journal_line l ON l.account_id=a.id
            LEFT JOIN gl_journal j ON j.id=l.journal_id
                AND j.journal_date>=? AND j.journal_date<=? {pc}
            WHERE a.is_active=1
              AND a.account_type IN ('Revenue','COGS','Expense')
            GROUP BY a.account_type
        """
        with _conn() as con:
            bal_rows = con.execute(sql_bal, (d1,)).fetchall()
            nie_rows = con.execute(sql_nie, (fy0, d1)).fetchall()

        nie = {r["account_type"]: (r["td"], r["tc"]) for r in nie_rows}
        rev_d, rev_c = nie.get("Revenue", (0, 0))
        cogs_d, cogs_c = nie.get("COGS", (0, 0))
        exp_d, exp_c = nie.get("Expense", (0, 0))
        cy_earnings = (rev_c - rev_d) - (cogs_d - cogs_c) - (exp_d - exp_c)

        def net(row):
            return row["td"] - row["tc"] if row["account_type"] == "Asset" else row["tc"] - row["td"]

        asset_rows = [r for r in bal_rows if r["account_type"] == "Asset"]
        liab_rows = [r for r in bal_rows if r["account_type"] == "Liability"]
        eq_rows = [r for r in bal_rows if r["account_type"] == "Equity"]

        tbl = self.bs_tbl
        tbl.setRowCount(0)
        c_asset = ACCT_TYPE_COLORS["Asset"]
        c_liab = ACCT_TYPE_COLORS["Liability"]
        c_eq = ACCT_TYPE_COLORS["Equity"]

        # ── Assets ──
        self._fs_section_header(tbl, "Assets")
        total_assets = 0.0
        for sub, sub_label, hdr_bg, sub_bg in [
            ("Current", "Current Assets", QtGui.QColor(190, 215, 245), QtGui.QColor(210, 230, 255)),
            ("Fixed", "Fixed Assets", QtGui.QColor(190, 215, 245), QtGui.QColor(210, 230, 255)),
            ("Other", "Other Assets", QtGui.QColor(190, 215, 245), QtGui.QColor(210, 230, 255)),
        ]:
            sub_rows = [r for r in asset_rows if (r["account_sub"] or "Other") == sub]
            if not sub_rows:
                continue
            r = tbl.rowCount()
            tbl.insertRow(r)
            lbl = _ro(f"  {sub_label}")
            f = lbl.font()
            f.setItalic(True)
            f.setBold(True)
            lbl.setFont(f)
            lbl.setBackground(hdr_bg)
            tbl.setItem(r, 0, lbl)
            a = _ro("")
            a.setBackground(hdr_bg)
            tbl.setItem(r, 1, a)
            sub_total = 0.0
            for row in sub_rows:
                bal = net(row)
                sub_total += bal
                self._fs_detail_row(tbl, row["account_name"], bal, c_asset)
            total_assets += sub_total
            self._fs_subtotal_row(tbl, f"    Total {sub_label}", sub_total, sub_bg)
        self._fs_spacer(tbl)
        self._fs_total_row(tbl, "Total Assets", total_assets)
        self._fs_spacer(tbl)

        # ── Liabilities ──
        self._fs_section_header(tbl, "Liabilities")
        total_liab = 0.0
        for sub, sub_label, hdr_bg, sub_bg in [
            ("Current", "Current Liabilities", QtGui.QColor(245, 215, 190), QtGui.QColor(255, 225, 200)),
            ("Long-term", "Long-term Liabilities", QtGui.QColor(245, 215, 190), QtGui.QColor(255, 225, 200)),
            ("Other", "Other Liabilities", QtGui.QColor(245, 215, 190), QtGui.QColor(255, 225, 200)),
        ]:
            sub_rows = [r for r in liab_rows if (r["account_sub"] or "Other") == sub]
            if not sub_rows:
                continue
            r = tbl.rowCount()
            tbl.insertRow(r)
            lbl = _ro(f"  {sub_label}")
            f = lbl.font()
            f.setItalic(True)
            f.setBold(True)
            lbl.setFont(f)
            lbl.setBackground(hdr_bg)
            tbl.setItem(r, 0, lbl)
            a = _ro("")
            a.setBackground(hdr_bg)
            tbl.setItem(r, 1, a)
            sub_total = 0.0
            for row in sub_rows:
                bal = net(row)
                sub_total += bal
                self._fs_detail_row(tbl, row["account_name"], bal, c_liab)
            total_liab += sub_total
            self._fs_subtotal_row(tbl, f"    Total {sub_label}", sub_total, sub_bg)
        self._fs_spacer(tbl)
        self._fs_total_row(tbl, "Total Liabilities", total_liab)
        self._fs_spacer(tbl)

        # ── Equity ──
        self._fs_section_header(tbl, "Equity")
        total_eq = 0.0
        for row in eq_rows:
            if row["account_number"] == "3900":
                continue  # replaced by computed current year earnings below
            bal = net(row)
            total_eq += bal
            self._fs_detail_row(tbl, row["account_name"], bal, c_eq)
        self._fs_detail_row(tbl, "Current Year Earnings (computed)", cy_earnings, c_eq)
        total_eq += cy_earnings
        self._fs_spacer(tbl)
        self._fs_total_row(tbl, "Total Equity", total_eq)
        self._fs_spacer(tbl)

        # ── Total Liabilities + Equity ──
        total_l_e = total_liab + total_eq
        self._fs_total_row(tbl, "Total Liabilities + Equity", total_l_e)

        diff = abs(total_assets - total_l_e)
        if diff < 0.005:
            self.bs_balance_lbl.setText(
                "<span style='color:green;'>✓ Balance Sheet is balanced</span>   "
                f"Total Assets: <b>{_money(total_assets)}</b>   "
                f"Total Liabilities + Equity: <b>{_money(total_l_e)}</b>"
            )
        else:
            self.bs_balance_lbl.setText(
                f"<span style='color:red;'>⚠ Out of balance by {_money(diff)}</span>   "
                f"Total Assets: <b>{_money(total_assets)}</b>   "
                f"Total Liabilities + Equity: <b>{_money(total_l_e)}</b>"
            )

    # ── tab change ────────────────────────────────────────────────────────────
    def _on_tab_change(self, idx):
        tab_names = ["Chart of Accounts", "Journal Entries", "Trial Balance",
                     "Ledger View", "Financial Statements"]
        self.statusBar().showMessage(f"Tab: {tab_names[idx]}")
        if idx == 1:   # Journal Entries — always fetch latest from DB
            self._refresh_journals()
        elif idx == 2:  # Trial Balance — auto-run
            self._refresh_trial()
        elif idx == 3:  # Ledger View — repopulate account combo
            self._populate_lv_acct_combo()

    # ── Bank Reconciliation tab ───────────────────────────────────────────────

    def _build_recon_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        hdr = QtWidgets.QLabel("Bank Reconciliation")
        hdr.setStyleSheet("font-size:15px;font-weight:bold;color:white;padding:2px;")
        v.addWidget(hdr)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Account:"))
        self.recon_acct_cb = QtWidgets.QComboBox()
        self.recon_acct_cb.setMinimumWidth(220)
        top.addWidget(self.recon_acct_cb)
        top.addWidget(QtWidgets.QLabel("Statement Date:"))
        self.recon_stmt_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.recon_stmt_date.setDisplayFormat("yyyy-MM-dd")
        self.recon_stmt_date.setDate(QtCore.QDate.currentDate())
        top.addWidget(self.recon_stmt_date)
        top.addWidget(QtWidgets.QLabel("Statement Balance:"))
        self.recon_stmt_bal = QtWidgets.QDoubleSpinBox()
        self.recon_stmt_bal.setRange(-999_999_999, 999_999_999)
        self.recon_stmt_bal.setDecimals(2)
        self.recon_stmt_bal.setGroupSeparatorShown(True)
        top.addWidget(self.recon_stmt_bal)
        btn_load = QtWidgets.QPushButton("Load Transactions")
        btn_load.setStyleSheet(BTN_STYLE)
        btn_load.clicked.connect(self._recon_load)
        top.addWidget(btn_load)
        top.addStretch()
        v.addLayout(top)

        self.recon_tbl = QtWidgets.QTableWidget(0, 5)
        self.recon_tbl.setHorizontalHeaderLabels(["Date", "Reference", "Description", "Amount", "Cleared"])
        self.recon_tbl.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.recon_tbl.setColumnWidth(0, 95)
        self.recon_tbl.setColumnWidth(1, 110)
        self.recon_tbl.setColumnWidth(3, 100)
        self.recon_tbl.setColumnWidth(4, 65)
        self.recon_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.recon_tbl.setAlternatingRowColors(True)
        self.recon_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.recon_tbl)

        self.recon_summary_lbl = QtWidgets.QLabel(
            "Statement Balance: $0.00  |  Cleared Balance: $0.00  |  Difference: $0.00")
        self.recon_summary_lbl.setStyleSheet("font-weight:bold;color:white;padding:4px;")
        v.addWidget(self.recon_summary_lbl)

        bb = QtWidgets.QHBoxLayout()
        btn_clear = QtWidgets.QPushButton("Toggle Cleared")
        btn_clear.setStyleSheet(BTN_STYLE)
        btn_clear.clicked.connect(self._recon_toggle_cleared)
        bb.addWidget(btn_clear)
        bb.addStretch()
        v.addLayout(bb)

        self._recon_populate_accts()
        return w

    def _recon_populate_accts(self):
        with _conn() as con:
            rows = con.execute(
                "SELECT id, account_number, account_name FROM gl_account WHERE account_type='Asset' AND is_active=1 ORDER BY account_number"
            ).fetchall()
        self.recon_acct_cb.clear()
        for row in rows:
            self.recon_acct_cb.addItem(f"{row['account_number']} – {row['account_name']}", userData=row["id"])

    def _recon_load(self):
        acct_id = self.recon_acct_cb.currentData()
        if acct_id is None:
            return
        stmt_date = self.recon_stmt_date.date().toString("yyyy-MM-dd")
        with _conn() as con:
            rows = con.execute("""
                SELECT j.journal_date, j.reference, j.description,
                       l.debit, l.credit, l.id as line_id
                FROM gl_journal_line l
                JOIN gl_journal j ON j.id = l.journal_id
                WHERE l.account_id = ? AND j.journal_date <= ?
                ORDER BY j.journal_date, j.id
            """, (acct_id, stmt_date)).fetchall()
        self.recon_tbl.setRowCount(0)
        self._recon_line_ids = []
        for row in rows:
            r = self.recon_tbl.rowCount()
            self.recon_tbl.insertRow(r)
            amount = row["debit"] - row["credit"]
            self.recon_tbl.setItem(r, 0, _ro(row["journal_date"]))
            self.recon_tbl.setItem(r, 1, _ro(row["reference"] or ""))
            self.recon_tbl.setItem(r, 2, _ro(row["description"] or ""))
            self.recon_tbl.setItem(r, 3, _ro(f"{amount:,.2f}", QtCore.Qt.AlignmentFlag.AlignRight))
            chk = QtWidgets.QTableWidgetItem()
            chk.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.recon_tbl.setItem(r, 4, chk)
            self._recon_line_ids.append(row["line_id"])
        self._recon_update_summary()

    def _recon_toggle_cleared(self):
        rows = self.recon_tbl.selectedItems()
        if not rows:
            return
        r = self.recon_tbl.currentRow()
        chk = self.recon_tbl.item(r, 4)
        if chk:
            chk.setCheckState(
                QtCore.Qt.CheckState.Unchecked if chk.checkState() == QtCore.Qt.CheckState.Checked
                else QtCore.Qt.CheckState.Checked
            )
        self._recon_update_summary()

    def _recon_update_summary(self):
        stmt_bal = self.recon_stmt_bal.value()
        cleared = 0.0
        for r in range(self.recon_tbl.rowCount()):
            chk = self.recon_tbl.item(r, 4)
            if chk and chk.checkState() == QtCore.Qt.CheckState.Checked:
                try:
                    cleared += float(self.recon_tbl.item(r, 3).text().replace(",", ""))
                except Exception:
                    pass
        diff = stmt_bal - cleared
        color = "lime" if abs(diff) < 0.01 else "red"
        self.recon_summary_lbl.setText(
            f"Statement Balance: ${stmt_bal:,.2f}  |  Cleared Balance: ${cleared:,.2f}  |  "
            f"<span style='color:{color};font-weight:bold;'>Difference: ${diff:,.2f}</span>"
        )


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = GeneralLedgerWindow(sys.argv[1] if len(sys.argv) > 1 else None)
    win.show()
    sys.exit(app.exec())
