import sys
import psycopg2
from .db_pg import get_db_connection
from PyQt6 import QtCore, QtGui, QtWidgets
from .button_nav import ButtonNav


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

ACCOUNT_TYPES = ["Asset", "Liability", "Equity", "Revenue", "COGS", "Expense"]
# Normal balance: these types have a debit-normal balance (balance =
# debits - credits)
DEBIT_NORMAL = {"Asset", "COGS", "Expense"}


def get_db():
    return get_db_connection()


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gl_account (
            id SERIAL PRIMARY KEY,
            account_number TEXT NOT NULL UNIQUE,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            account_sub TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gl_journal (
            id SERIAL PRIMARY KEY,
            journal_date TEXT NOT NULL,
            reference TEXT,
            description TEXT,
            posted INTEGER DEFAULT 0,
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gl_journal_line (
            id SERIAL PRIMARY KEY,
            journal_id INTEGER NOT NULL REFERENCES gl_journal(id),
            account_id INTEGER NOT NULL REFERENCES gl_account(id),
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            memo TEXT DEFAULT ''
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


def _ro_right(text):
    item = _ro(text)
    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight |
                          QtCore.Qt.AlignmentFlag.AlignVCenter)
    return item


def _account_balance(account_id, account_type, date_to=None):
    conn = get_db()
    q = """
        SELECT COALESCE(SUM(jl.debit),0) AS total_debit,
               COALESCE(SUM(jl.credit),0) AS total_credit
        FROM gl_journal_line jl
        JOIN gl_journal j ON j.id = jl.journal_id
        WHERE jl.account_id = %s AND j.posted = 1
    """
    params = [account_id]
    if date_to:
        q += " AND j.journal_date <= %s"
        params.append(date_to)
    row = conn.execute(q, params).fetchone()
    conn.close()
    d, c = row["total_debit"], row["total_credit"]
    if account_type in DEBIT_NORMAL:
        return d - c
    return c - d


# ── Account Dialogs ─────────────────────────────────────────────────────

class AccountDialog(QtWidgets.QDialog):
    def __init__(self, account_id=None, parent=None):
        super().__init__(parent)
        self._account_id = account_id
        self.setWindowTitle("Edit Account" if account_id else "New Account")
        self.resize(420, 300)
        _apply_blue_palette(self)
        self._build_ui()
        if account_id:
            self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.acct_num = QtWidgets.QLineEdit()
        self.acct_num.setStyleSheet(INPUT_STYLE)
        self.acct_num.setPlaceholderText("e.g. 1000")
        layout.addRow(lbl("Account #:"), self.acct_num)

        self.acct_name = QtWidgets.QLineEdit()
        self.acct_name.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Account Name:"), self.acct_name)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.setStyleSheet(COMBO_STYLE)
        for t in ACCOUNT_TYPES:
            self.type_combo.addItem(t, t)
        layout.addRow(lbl("Type:"), self.type_combo)

        self.sub_edit = QtWidgets.QLineEdit()
        self.sub_edit.setStyleSheet(INPUT_STYLE)
        self.sub_edit.setPlaceholderText("e.g. Current, Fixed, Operating")
        layout.addRow(lbl("Sub-Type:"), self.sub_edit)

        self.active_check = QtWidgets.QCheckBox("Active")
        self.active_check.setStyleSheet("color: white; font-size: 13px;")
        self.active_check.setChecked(True)
        layout.addRow(lbl(""), self.active_check)

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

    def _load(self):
        conn = get_db()
        rec = conn.execute("SELECT * FROM gl_account WHERE id = %s",
                           (self._account_id,)).fetchone()
        conn.close()
        if not rec:
            return
        self.acct_num.setText(rec["account_number"] or "")
        self.acct_name.setText(rec["account_name"] or "")
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == rec["account_type"]:
                self.type_combo.setCurrentIndex(i)
                break
        self.sub_edit.setText(rec["account_sub"] or "")
        self.active_check.setChecked(bool(rec["is_active"]))
        self.notes.setText(rec["notes"] or "")

    def _on_ok(self):
        num = self.acct_num.text().strip()
        name = self.acct_name.text().strip()
        if not num or not name:
            QtWidgets.QMessageBox.warning(self, "Input Error",
                                          "Account number and name are "
                                          "required.")
            return
        conn = get_db()
        try:
            if self._account_id is None:
                conn.execute(
                    "INSERT INTO gl_account (account_number, account_name, "
                    "account_type,"
                    " account_sub, is_active, notes) VALUES "
                    "(%s,%s,%s,%s,%s,%s)",
                    (num, name, self.type_combo.currentData(),
                     self.sub_edit.text().strip(),
                     1 if self.active_check.isChecked() else 0,
                     self.notes.text().strip())
                )
            else:
                conn.execute(
                    "UPDATE gl_account SET account_number=%s, account_name=%s,"
                    " account_type=%s, account_sub=%s, is_active=%s, notes=%s"
                    " WHERE id=%s",
                    (num, name, self.type_combo.currentData(),
                     self.sub_edit.text().strip(),
                     1 if self.active_check.isChecked() else 0,
                     self.notes.text().strip(), self._account_id)
                )
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"Account number '{num}' already exists.")  # noqa: E501
            conn.close()
            return
        conn.close()
        self.accept()


# ── Journal Dialogs ─────────────────────────────────────────────────────

class NewJournalDialog(QtWidgets.QDialog):
    """Create a new journal entry with balanced debit/credit lines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Journal Entry")
        self.resize(700, 520)
        _apply_blue_palette(self)
        self.journal_id = None
        self._lines = []   # list of (account_id, debit, credit, memo)
        self._build_ui()
        self._load_accounts()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)

        # Header fields
        hdr = QtWidgets.QFormLayout()
        hdr.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.jdate = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.jdate.setCalendarPopup(True)
        self.jdate.setStyleSheet(INPUT_STYLE)
        hdr.addRow(lbl("Date:"), self.jdate)

        self.ref = QtWidgets.QLineEdit()
        self.ref.setStyleSheet(INPUT_STYLE)
        self.ref.setPlaceholderText("Reference number")
        hdr.addRow(lbl("Reference:"), self.ref)

        self.desc = QtWidgets.QLineEdit()
        self.desc.setStyleSheet(INPUT_STYLE)
        self.desc.setPlaceholderText("Description")
        hdr.addRow(lbl("Description:"), self.desc)
        v.addLayout(hdr)

        # Line entry row
        line_row = QtWidgets.QHBoxLayout()
        self.line_acct = QtWidgets.QComboBox()
        self.line_acct.setStyleSheet(COMBO_STYLE)
        self.line_acct.setMinimumWidth(220)
        line_row.addWidget(self.line_acct)

        self.line_debit = QtWidgets.QDoubleSpinBox()
        self.line_debit.setRange(0, 99999999)
        self.line_debit.setDecimals(2)
        self.line_debit.setPrefix("Dr $ ")
        self.line_debit.setStyleSheet(INPUT_STYLE)
        self.line_debit.setFixedWidth(130)
        line_row.addWidget(self.line_debit)

        self.line_credit = QtWidgets.QDoubleSpinBox()
        self.line_credit.setRange(0, 99999999)
        self.line_credit.setDecimals(2)
        self.line_credit.setPrefix("Cr $ ")
        self.line_credit.setStyleSheet(INPUT_STYLE)
        self.line_credit.setFixedWidth(130)
        line_row.addWidget(self.line_credit)

        self.line_memo = QtWidgets.QLineEdit()
        self.line_memo.setStyleSheet(INPUT_STYLE)
        self.line_memo.setPlaceholderText("Memo")
        line_row.addWidget(self.line_memo)

        add_btn = QtWidgets.QPushButton("Add Line")
        add_btn.setStyleSheet(BUTTON_STYLE)
        add_btn.setFixedHeight(28)
        add_btn.clicked.connect(self._add_line)
        line_row.addWidget(add_btn)
        v.addLayout(line_row)

        # Lines table
        self.lines_table = QtWidgets.QTableWidget()
        self.lines_table.setColumnCount(4)
        self.lines_table.setHorizontalHeaderLabels(
            ["Account", "Debit", "Credit", "Memo"])
        th = self.lines_table.horizontalHeader()
        th.setStyleSheet("color: black; font-weight: bold;")
        th.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        th.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lines_table.verticalHeader().setVisible(False)
        self.lines_table.setFixedHeight(160)
        v.addWidget(self.lines_table)

        # Totals
        tot_row = QtWidgets.QHBoxLayout()
        self.lbl_totals = QtWidgets.QLabel(
            "Debits: $0.00   Credits: $0.00   Difference: $0.00")
        self.lbl_totals.setStyleSheet("color: white; font-size: 13px;")
        tot_row.addWidget(self.lbl_totals)
        rem_btn = QtWidgets.QPushButton("Remove Selected")
        rem_btn.setStyleSheet(BUTTON_STYLE)
        rem_btn.setFixedHeight(26)
        rem_btn.clicked.connect(self._remove_line)
        tot_row.addWidget(rem_btn)
        tot_row.addStretch()
        v.addLayout(tot_row)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _load_accounts(self):
        conn = get_db()
        accts = conn.execute(
            "SELECT id, account_number, account_name FROM gl_account"
            " WHERE is_active = 1 ORDER BY account_number"
        ).fetchall()
        conn.close()
        self._acct_map = {a["id"]: f"{a['account_number']} — {a['account_name']}"  # noqa: E501
                          for a in accts}
        for a in accts:
            self.line_acct.addItem(
                f"{a['account_number']} — {a['account_name']}", a["id"])

    def _add_line(self):
        acct_id = self.line_acct.currentData()
        dr = self.line_debit.value()
        cr = self.line_credit.value()
        if dr == 0 and cr == 0:
            QtWidgets.QMessageBox.warning(self, "Input Error",
                                          "Enter a debit or credit amount.")
            return
        memo = self.line_memo.text().strip()
        self._lines.append((acct_id, dr, cr, memo))
        r = self.lines_table.rowCount()
        self.lines_table.insertRow(r)
        self.lines_table.setItem(r, 0, _ro(self._acct_map.get(acct_id, "")))
        self.lines_table.setItem(r, 1, _ro_right(f"${dr:,.2f}" if dr else ""))
        self.lines_table.setItem(r, 2, _ro_right(f"${cr:,.2f}" if cr else ""))
        self.lines_table.setItem(r, 3, _ro(memo))
        self.line_debit.setValue(0)
        self.line_credit.setValue(0)
        self.line_memo.clear()
        self._update_totals()

    def _remove_line(self):
        row = self.lines_table.currentRow()
        if row < 0:
            return
        self.lines_table.removeRow(row)
        self._lines.pop(row)
        self._update_totals()

    def _update_totals(self):
        total_dr = sum(ln[1] for ln in self._lines)
        total_cr = sum(ln[2] for ln in self._lines)
        diff = total_dr - total_cr
        color = "color: #90ee90;" if abs(diff) < 0.005 else "color: #ff9999;"
        self.lbl_totals.setStyleSheet(f"{color} font-size: 13px;")
        self.lbl_totals.setText(
            f"Debits: ${total_dr:,.2f}   Credits: ${total_cr:,.2f}"
            f"   Difference: ${diff:,.2f}")

    def _on_ok(self):
        if not self._lines:
            QtWidgets.QMessageBox.warning(
    self, "No Lines", "Add at least one line.")
            return
        total_dr = sum(ln[1] for ln in self._lines)
        total_cr = sum(ln[2] for ln in self._lines)
        if abs(total_dr - total_cr) > 0.005:
            QtWidgets.QMessageBox.warning(
                self, "Not Balanced",
                f"Debits (${total_dr:,.2f}) must equal Credits (${total_cr:,.2f}).")  # noqa: E501
            return
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO gl_journal (journal_date, reference, description, "
            "posted,"
            " created_by, created_at) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (self.jdate.date().toString("yyyy-MM-dd"),
             self.ref.text().strip(), self.desc.text().strip(),
             0, "User",
             QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss"))  # noqa: E501
        )
        self.journal_id = cur.fetchone()['id']
        for acct_id, dr, cr, memo in self._lines:
            conn.execute(
                "INSERT INTO gl_journal_line (journal_id, account_id, debit, "
                "credit, memo)"
                " VALUES (%s,%s,%s,%s,%s)",
                (self.journal_id, acct_id, dr, cr, memo)
            )
        conn.commit()
        conn.close()
        self.accept()


# ── Chart of Accounts Tab ───────────────────────────────────────────────

class ChartOfAccountsTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._row_ids = []
        self._selected_id = None
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_t = QtWidgets.QLabel("Type:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.type_filter = QtWidgets.QComboBox()
        self.type_filter.setStyleSheet(COMBO_STYLE)
        self.type_filter.addItem("(all)", None)
        for t in ACCOUNT_TYPES:
            self.type_filter.addItem(t, t)
        self.type_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.type_filter)

        fr.addSpacing(10)
        self.active_only = QtWidgets.QCheckBox("Active Only")
        self.active_only.setStyleSheet("color: white; font-size: 13px;")
        self.active_only.setChecked(True)
        self.active_only.stateChanged.connect(self._refresh)
        fr.addWidget(self.active_only)
        fr.addStretch()
        v.addLayout(fr)

        self.tbl = QtWidgets.QTableWidget()
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(
            ["Acct #", "Account Name", "Type", "Sub-Type", "Balance", "Active"])  # noqa: E501
        hh = self.tbl.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.clicked.connect(self._on_clicked)
        self.tbl.doubleClicked.connect(self._on_edit)
        v.addWidget(self.tbl, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Account",    self._on_new),
            ("Edit Account",   self._on_edit),
            ("Toggle Active",  self._on_toggle_active),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        acct_type = self.type_filter.currentData()
        active_only = self.active_only.isChecked()
        conn = get_db()
        conds = []
        params = []
        if acct_type:
            conds.append("account_type = %s")
            params.append(acct_type)
        if active_only:
            conds.append("is_active = 1")
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        rows = conn.execute(
            f"SELECT * FROM gl_account {where} ORDER BY account_number",
            params or None
        ).fetchall()
        conn.close()
        self.tbl.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self._row_ids.append(row["id"])
            bal = _account_balance(row["id"], row["account_type"])
            self.tbl.setItem(r, 0, _ro(row["account_number"]))
            self.tbl.setItem(r, 1, _ro(row["account_name"]))
            self.tbl.setItem(r, 2, _ro(row["account_type"]))
            self.tbl.setItem(r, 3, _ro(row["account_sub"] or ""))
            self.tbl.setItem(r, 4, _ro_right(f"${bal:,.2f}"))
            self.tbl.setItem(r, 5, _ro("Yes" if row["is_active"] else "No"))
        self._selected_id = None

    def _on_clicked(self, index):
        row = index.row()
        if 0 <= row < len(self._row_ids):
            self._selected_id = self._row_ids[row]

    def _on_new(self):
        dlg = AccountDialog(parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, _idx=None):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an account first.")
            return
        dlg = AccountDialog(account_id=self._selected_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_toggle_active(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an account first.")
            return
        conn = get_db()
        cur = conn.execute("SELECT is_active FROM gl_account WHERE id=%s",
                           (self._selected_id,)).fetchone()
        new_val = 0 if cur["is_active"] else 1
        conn.execute("UPDATE gl_account SET is_active=%s WHERE id=%s",
                     (new_val, self._selected_id))
        conn.commit()
        conn.close()
        self._refresh()


# ── Journal Entries Tab ─────────────────────────────────────────────────

class JournalEntriesTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._journal_row_ids = []
        self._selected_journal_id = None
        self._build_ui()
        self._refresh_journals()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        self.posted_filter = QtWidgets.QComboBox()
        self.posted_filter.setStyleSheet(COMBO_STYLE)
        self.posted_filter.addItem("All Entries", None)
        self.posted_filter.addItem("Posted Only", 1)
        self.posted_filter.addItem("Unposted Only", 0)
        self.posted_filter.currentIndexChanged.connect(self._refresh_journals)
        fr.addWidget(self.posted_filter)

        fr.addSpacing(10)
        lbl_f = QtWidgets.QLabel("From:")
        lbl_f.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_f)
        self.date_from = QtWidgets.QDateEdit(
            QtCore.QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet(INPUT_STYLE)
        self.date_from.dateChanged.connect(self._refresh_journals)
        fr.addWidget(self.date_from)

        lbl_t = QtWidgets.QLabel("To:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.date_to = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet(INPUT_STYLE)
        self.date_to.dateChanged.connect(self._refresh_journals)
        fr.addWidget(self.date_to)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.journal_tbl = QtWidgets.QTableWidget()
        self.journal_tbl.setColumnCount(6)
        self.journal_tbl.setHorizontalHeaderLabels(
            ["Date", "Reference", "Description", "Lines", "Total Debit", "Posted"])  # noqa: E501
        jh = self.journal_tbl.horizontalHeader()
        jh.setStyleSheet("color: black; font-weight: bold;")
        jh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        jh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        jh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        jh.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        jh.setSectionResizeMode(
    4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        jh.setSectionResizeMode(
    5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.journal_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.journal_tbl.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.journal_tbl.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.journal_tbl.setAlternatingRowColors(True)
        self.journal_tbl.verticalHeader().setVisible(False)
        self.journal_tbl.clicked.connect(self._on_journal_clicked)
        splitter.addWidget(self.journal_tbl)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Journal Lines")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.lines_tbl = QtWidgets.QTableWidget()
        self.lines_tbl.setColumnCount(4)
        self.lines_tbl.setHorizontalHeaderLabels(
            ["Account", "Debit", "Credit", "Memo"])
        lh = self.lines_tbl.horizontalHeader()
        lh.setStyleSheet("color: black; font-weight: bold;")
        lh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        lh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        lh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        lh.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.lines_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lines_tbl.verticalHeader().setVisible(False)
        self.lines_tbl.setAlternatingRowColors(True)
        dv.addWidget(self.lines_tbl)
        splitter.addWidget(detail_w)
        splitter.setSizes([320, 200])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Journal Entry", self._on_new_journal),
            ("Post Entry",        self._on_post),
            ("Void Entry",        self._on_void),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh_journals(self):
        posted = self.posted_filter.currentData()
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")
        conds = ["j.journal_date BETWEEN %s AND %s"]
        params = [d_from, d_to]
        if posted is not None:
            conds.append("j.posted = %s")
            params.append(posted)
        where = " AND ".join(conds)
        conn = get_db()
        rows = conn.execute(f"""
            SELECT j.id, j.journal_date, j.reference, j.description, j.posted,
                   COUNT(jl.id) AS line_count,
                   COALESCE(SUM(jl.debit), 0) AS total_debit
            FROM gl_journal j
            LEFT JOIN gl_journal_line jl ON jl.journal_id = j.id
            WHERE {where}
            GROUP BY j.id ORDER BY j.journal_date DESC, j.id DESC
        """, params).fetchall()
        conn.close()
        self.journal_tbl.setRowCount(0)
        self._journal_row_ids = []
        for row in rows:
            r = self.journal_tbl.rowCount()
            self.journal_tbl.insertRow(r)
            self._journal_row_ids.append(row["id"])
            self.journal_tbl.setItem(r, 0, _ro(row["journal_date"] or ""))
            self.journal_tbl.setItem(r, 1, _ro(row["reference"] or ""))
            self.journal_tbl.setItem(r, 2, _ro(row["description"] or ""))
            self.journal_tbl.setItem(r, 3, _ro(str(row["line_count"])))
            self.journal_tbl.setItem(
                r, 4, _ro_right(f"${row['total_debit']:,.2f}"))
            self.journal_tbl.setItem(
                r, 5, _ro("Yes" if row["posted"] else "No"))
            if row["posted"]:
                bg = QtGui.QColor("#d4edda")
                for col in range(6):
                    self.journal_tbl.item(r, col).setBackground(bg)
        self._selected_journal_id = None
        self.lines_tbl.setRowCount(0)

    def _on_show_all(self):
        self.posted_filter.blockSignals(True)
        self.posted_filter.setCurrentIndex(0)
        self.posted_filter.blockSignals(False)
        self.date_from.blockSignals(True)
        self.date_from.setDate(QtCore.QDate(2000, 1, 1))
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(True)
        self.date_to.setDate(QtCore.QDate.currentDate())
        self.date_to.blockSignals(False)
        self._refresh_journals()

    def _on_journal_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._journal_row_ids):
            return
        self._selected_journal_id = self._journal_row_ids[row]
        self._refresh_lines()

    def _refresh_lines(self):
        self.lines_tbl.setRowCount(0)
        if self._selected_journal_id is None:
            return
        conn = get_db()
        lines = conn.execute("""
            SELECT a.account_number, a.account_name, jl.debit, jl.credit,
                jl.memo
            FROM gl_journal_line jl
            JOIN gl_account a ON a.id = jl.account_id
            WHERE jl.journal_id = %s
            ORDER BY jl.id
        """, (self._selected_journal_id,)).fetchall()
        conn.close()
        for line in lines:
            r = self.lines_tbl.rowCount()
            self.lines_tbl.insertRow(r)
            self.lines_tbl.setItem(r, 0, _ro(
                f"{line['account_number']} — {line['account_name']}"))
            self.lines_tbl.setItem(r, 1, _ro_right(
                f"${line['debit']:,.2f}" if line["debit"] else ""))
            self.lines_tbl.setItem(r, 2, _ro_right(
                f"${line['credit']:,.2f}" if line["credit"] else ""))
            self.lines_tbl.setItem(r, 3, _ro(line["memo"] or ""))

    def _on_new_journal(self):
        dlg = NewJournalDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_journals()

    def _on_post(self):
        if self._selected_journal_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a journal entry first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Post", "Post this journal entry? This cannot be "
                                  "undone.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)  # noqa: E501
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE gl_journal SET posted = 1 WHERE id = %s",
                         (self._selected_journal_id,))
            conn.commit()
            conn.close()
            self._refresh_journals()

    def _on_void(self):
        if self._selected_journal_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a journal entry first.")
            return
        conn = get_db()
        j = conn.execute("SELECT posted FROM gl_journal WHERE id=%s",
                         (self._selected_journal_id,)).fetchone()
        conn.close()
        if j and j["posted"]:
            QtWidgets.QMessageBox.warning(
                self, "Already Posted", "Posted entries cannot be voided.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Void", "Delete this unposted journal entry?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)  # noqa: E501
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM gl_journal_line WHERE journal_id = %s",
                         (self._selected_journal_id,))
            conn.execute("DELETE FROM gl_journal WHERE id = %s",
                         (self._selected_journal_id,))
            conn.commit()
            conn.close()
            self._selected_journal_id = None
            self._refresh_journals()


# ── Trial Balance Tab ───────────────────────────────────────────────────

class TrialBalanceTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_a = QtWidgets.QLabel("As of:")
        lbl_a.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_a)
        self.as_of = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.as_of.setCalendarPopup(True)
        self.as_of.setStyleSheet(INPUT_STYLE)
        fr.addWidget(self.as_of)
        btn = QtWidgets.QPushButton("Run")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(self._refresh)
        fr.addWidget(btn)
        self.zero_check = QtWidgets.QCheckBox("Hide zero balances")
        self.zero_check.setStyleSheet("color: white; font-size: 13px;")
        self.zero_check.setChecked(True)
        fr.addWidget(self.zero_check)
        fr.addStretch()
        v.addLayout(fr)

        self.tbl = QtWidgets.QTableWidget()
        self.tbl.setColumnCount(4)
        self.tbl.setHorizontalHeaderLabels(
            ["Acct #", "Account Name", "Debit", "Credit"])
        hh = self.tbl.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        v.addWidget(self.tbl, stretch=1)

        self.totals_lbl = QtWidgets.QLabel("")
        self.totals_lbl.setStyleSheet(
            "color: white; font-size: 13px; font-weight: bold;")
        v.addWidget(self.totals_lbl)

    def _refresh(self):
        as_of = self.as_of.date().toString("yyyy-MM-dd")
        hide_zero = self.zero_check.isChecked()
        conn = get_db()
        try:
            accounts = conn.execute(
                "SELECT id, account_number, account_name, account_type"
                " FROM gl_account WHERE is_active = 1 ORDER BY account_number"
            ).fetchall()
        except psycopg2.OperationalError:
            accounts = []
        conn.close()

        self.tbl.setRowCount(0)
        total_dr = total_cr = 0.0
        for acct in accounts:
            bal = _account_balance(acct["id"], acct["account_type"], as_of)
            if hide_zero and abs(bal) < 0.005:
                continue
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, _ro(acct["account_number"]))
            self.tbl.setItem(r, 1, _ro(acct["account_name"]))
            if acct["account_type"] in DEBIT_NORMAL:
                self.tbl.setItem(r, 2, _ro_right(
                    f"${bal:,.2f}" if bal >= 0 else ""))
                self.tbl.setItem(r, 3, _ro_right(
                    f"${-bal:,.2f}" if bal < 0 else ""))
                total_dr += max(bal, 0)
                total_cr += max(-bal, 0)
            else:
                self.tbl.setItem(r, 2, _ro_right(
                    f"${-bal:,.2f}" if bal < 0 else ""))
                self.tbl.setItem(r, 3, _ro_right(
                    f"${bal:,.2f}" if bal >= 0 else ""))
                total_cr += max(bal, 0)
                total_dr += max(-bal, 0)

        balanced = abs(total_dr - total_cr) < 0.005
        color = "color: #90ee90;" if balanced else "color: #ff9999;"
        self.totals_lbl.setStyleSheet(
    f"{color} font-size: 13px; font-weight: bold;")
        self.totals_lbl.setText(
            f"Total Debits: ${
    total_dr:,.2f}    Total Credits: ${
        total_cr:,.2f}"
            + ("    BALANCED" if balanced else f"    OUT OF BALANCE by ${abs(total_dr - total_cr):,.2f}")  # noqa: E501
        )


# ── Income Statement Tab ────────────────────────────────────────────────

class IncomeStatementTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_f = QtWidgets.QLabel("From:")
        lbl_f.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_f)
        self.date_from = QtWidgets.QDateEdit(
            QtCore.QDate(QtCore.QDate.currentDate().year(), 1, 1))
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet(INPUT_STYLE)
        fr.addWidget(self.date_from)
        lbl_t = QtWidgets.QLabel("To:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.date_to = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet(INPUT_STYLE)
        fr.addWidget(self.date_to)
        btn = QtWidgets.QPushButton("Run")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(self._refresh)
        fr.addWidget(btn)
        fr.addStretch()
        v.addLayout(fr)

        self.tbl = QtWidgets.QTableWidget()
        self.tbl.setColumnCount(3)
        self.tbl.setHorizontalHeaderLabels(["Account", "Type", "Amount"])
        hh = self.tbl.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        v.addWidget(self.tbl, stretch=1)

        self.summary_lbl = QtWidgets.QLabel("")
        self.summary_lbl.setStyleSheet(
            "color: white; font-size: 13px; font-weight: bold;")
        v.addWidget(self.summary_lbl)

    def _section_total(self, acct_type, date_from, date_to):
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT id, account_type FROM gl_account"
                " WHERE is_active = 1 AND account_type = %s",
                (acct_type,)
            ).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()
        return [(r["id"], r["account_type"]) for r in rows]

    def _period_balance(self, account_id, account_type, date_from, date_to):
        conn = get_db()
        row = conn.execute("""
            SELECT COALESCE(SUM(jl.debit),0) AS d, COALESCE(SUM(jl.credit),0)
                AS c
            FROM gl_journal_line jl
            JOIN gl_journal j ON j.id = jl.journal_id
            WHERE jl.account_id = %s AND j.posted = 1
              AND j.journal_date BETWEEN %s AND %s
        """, (account_id, date_from, date_to)).fetchone()
        conn.close()
        d, c = row["d"], row["c"]
        if account_type in DEBIT_NORMAL:
            return d - c
        return c - d

    def _refresh(self):
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")
        conn = get_db()
        try:
            accounts = conn.execute(
                "SELECT id, account_number, account_name, account_type FROM "
                "gl_account"
                " WHERE is_active = 1 AND account_type IN "
                "('Revenue','COGS','Expense')"
                " ORDER BY account_type, account_number"
            ).fetchall()
        except psycopg2.OperationalError:
            accounts = []
        conn.close()

        self.tbl.setRowCount(0)
        totals = {"Revenue": 0.0, "COGS": 0.0, "Expense": 0.0}
        current_type = None
        for acct in accounts:
            if acct["account_type"] != current_type:
                current_type = acct["account_type"]
                r = self.tbl.rowCount()
                self.tbl.insertRow(r)
                hdr = QtWidgets.QTableWidgetItem(current_type.upper())
                hdr.setFlags(hdr.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                hdr.setBackground(QtGui.QColor("#004499"))
                hdr.setForeground(QtGui.QColor("white"))
                font = hdr.font()
                font.setBold(True)
                hdr.setFont(font)
                self.tbl.setItem(r, 0, hdr)
                self.tbl.setItem(r, 1, _ro(""))
                self.tbl.setItem(r, 2, _ro(""))

            bal = self._period_balance(
    acct["id"], acct["account_type"], d_from, d_to)
            totals[acct["account_type"]] += bal
            if abs(bal) < 0.005:
                continue
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            name = f"  {acct['account_number']} — {acct['account_name']}"
            self.tbl.setItem(r, 0, _ro(name))
            self.tbl.setItem(r, 1, _ro(acct["account_type"]))
            self.tbl.setItem(r, 2, _ro_right(f"${bal:,.2f}"))

        revenue = totals["Revenue"]
        cogs = totals["COGS"]
        expenses = totals["Expense"]
        gross_profit = revenue - cogs
        net_income = gross_profit - expenses

        color = "color: #90ee90;" if net_income >= 0 else "color: #ff9999;"
        self.summary_lbl.setStyleSheet(
    f"{color} font-size: 13px; font-weight: bold;")
        self.summary_lbl.setText(
            f"Revenue: ${revenue:,.2f}    COGS: ${cogs:,.2f}    "
            f"Gross Profit: ${
    gross_profit:,.2f}    Expenses: ${
        expenses:,.2f}    "
            f"Net Income: ${net_income:,.2f}"
        )


# ── Balance Sheet Tab ───────────────────────────────────────────────────

class BalanceSheetTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_a = QtWidgets.QLabel("As of:")
        lbl_a.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_a)
        self.as_of = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.as_of.setCalendarPopup(True)
        self.as_of.setStyleSheet(INPUT_STYLE)
        fr.addWidget(self.as_of)
        btn = QtWidgets.QPushButton("Run")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(self._refresh)
        fr.addWidget(btn)
        fr.addStretch()
        v.addLayout(fr)

        self.tbl = QtWidgets.QTableWidget()
        self.tbl.setColumnCount(3)
        self.tbl.setHorizontalHeaderLabels(["Account", "Type", "Balance"])
        hh = self.tbl.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        v.addWidget(self.tbl, stretch=1)

        self.summary_lbl = QtWidgets.QLabel("")
        self.summary_lbl.setStyleSheet(
            "color: white; font-size: 13px; font-weight: bold;")
        v.addWidget(self.summary_lbl)

    def _refresh(self):
        as_of = self.as_of.date().toString("yyyy-MM-dd")
        conn = get_db()
        try:
            accounts = conn.execute(
                "SELECT id, account_number, account_name, account_type FROM "
                "gl_account"
                " WHERE is_active = 1 AND account_type IN "
                "('Asset','Liability','Equity')"
                " ORDER BY account_type, account_number"
            ).fetchall()
        except psycopg2.OperationalError:
            accounts = []
        conn.close()

        self.tbl.setRowCount(0)
        totals = {"Asset": 0.0, "Liability": 0.0, "Equity": 0.0}
        current_type = None
        for acct in accounts:
            if acct["account_type"] != current_type:
                current_type = acct["account_type"]
                r = self.tbl.rowCount()
                self.tbl.insertRow(r)
                hdr = QtWidgets.QTableWidgetItem(current_type.upper())
                hdr.setFlags(hdr.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                hdr.setBackground(QtGui.QColor("#004499"))
                hdr.setForeground(QtGui.QColor("white"))
                font = hdr.font()
                font.setBold(True)
                hdr.setFont(font)
                self.tbl.setItem(r, 0, hdr)
                self.tbl.setItem(r, 1, _ro(""))
                self.tbl.setItem(r, 2, _ro(""))

            bal = _account_balance(acct["id"], acct["account_type"], as_of)
            totals[acct["account_type"]] += bal
            if abs(bal) < 0.005:
                continue
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            name = f"  {acct['account_number']} — {acct['account_name']}"
            self.tbl.setItem(r, 0, _ro(name))
            self.tbl.setItem(r, 1, _ro(acct["account_type"]))
            self.tbl.setItem(r, 2, _ro_right(f"${bal:,.2f}"))

        assets = totals["Asset"]
        liabilities = totals["Liability"]
        equity = totals["Equity"]
        balanced = abs(assets - (liabilities + equity)) < 0.005
        color = "color: #90ee90;" if balanced else "color: #ff9999;"
        self.summary_lbl.setStyleSheet(
    f"{color} font-size: 13px; font-weight: bold;")
        self.summary_lbl.setText(
            f"Assets: ${assets:,.2f}    Liabilities: ${liabilities:,.2f}    "
            f"Equity: ${equity:,.2f}    "
            + ("BALANCED" if balanced
               else f"OUT OF BALANCE by ${abs(assets - liabilities - equity):,.2f}")  # noqa: E501
        )


# ── Main Window ─────────────────────────────────────────────────────────

class GeneralLedgerWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        init_db()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = ButtonNav()
        tabs.setStyleSheet(
            "QTabWidget::pane{border: none;}"
            "QTabBar::tab{background: white; color: black; padding: 6px 14px;"
            " border: 1px solid #999; border-bottom: none; border-radius: 4px "
            "4px 0 0;}"
            "QTabBar::tab:selected{background: rgb(85,255,255); font-weight: "
            "bold;}"
        )
        tabs.addTab(JournalEntriesTab(), "Journal Entries")
        tabs.addTab(ChartOfAccountsTab(), "Chart of Accounts")
        tabs.addTab(TrialBalanceTab(), "Trial Balance")
        tabs.addTab(IncomeStatementTab(), "Income Statement")
        tabs.addTab(BalanceSheetTab(), "Balance Sheet")
        layout.addWidget(tabs)


class GeneralLedgerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("General Ledger")
        self.resize(1060, 720)
        _apply_blue_palette(self)
        self.setCentralWidget(GeneralLedgerWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = GeneralLedgerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
