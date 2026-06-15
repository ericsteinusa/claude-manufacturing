"""
Bank_reconciliation.py — Bank Reconciliation module
Tabs: Bank Accounts | Statement Entry | Reconciliation | History
"""
import sys
from .db_pg import get_db
import csv
from PyQt6 import QtCore, QtGui, QtWidgets
from .button_nav import ButtonNav



def _conn():
    c = get_db()
    return c


def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS bank_account (
            id             SERIAL PRIMARY KEY,
            account_name   TEXT    NOT NULL,
            bank_name      TEXT    DEFAULT '',
            account_number TEXT    DEFAULT '',
            routing_number TEXT    DEFAULT '',
            gl_account_id  INTEGER REFERENCES gl_account(id),
            is_active      INTEGER DEFAULT 1,
            notes          TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS bank_statement (
            id                SERIAL PRIMARY KEY,
            bank_account_id   INTEGER NOT NULL REFERENCES bank_account(id) ON
                DELETE CASCADE,
            statement_date    TEXT    NOT NULL,
            beginning_balance REAL    DEFAULT 0.0,
            ending_balance    REAL    DEFAULT 0.0,
            status            TEXT    DEFAULT 'Open',
                -- Open / In Progress / Reconciled
            reconciled_by     TEXT    DEFAULT '',
            reconciled_at     TEXT    DEFAULT '',
            notes             TEXT    DEFAULT '',
            created_at        TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bank_statement_item (
            id                     SERIAL PRIMARY KEY,
            statement_id           INTEGER NOT NULL REFERENCES
                bank_statement(id) ON DELETE CASCADE,
            item_date              TEXT    NOT NULL,
            description            TEXT    DEFAULT '',
            amount                 REAL    NOT NULL,
            item_type              TEXT    DEFAULT 'Credit',  -- Credit / Debit
            is_matched             INTEGER DEFAULT 0,
            matched_journal_line_id INTEGER DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS bank_reconciliation (
            id                    SERIAL PRIMARY KEY,
            statement_id          INTEGER NOT NULL REFERENCES
                bank_statement(id) ON DELETE CASCADE,
            journal_line_id       INTEGER REFERENCES gl_journal_line(id),
            statement_item_id     INTEGER REFERENCES bank_statement_item(id),
            matched_at            TEXT    DEFAULT (datetime('now')),
            matched_by            TEXT    DEFAULT ''
        );
        """)


STATUSES = ["Open", "In Progress", "Reconciled"]
ITEM_TYPES = ["Credit", "Debit"]

BLUE = QtGui.QColor(0, 85, 255)

BTN_STYLE = (
    "QPushButton{background-color:white;border:2px solid "
    "black;border-radius:8px;"
    "padding:4px 10px;font-weight:bold;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
    "QPushButton:disabled{background-color:#cccccc;color:#888888;}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid #aaa;background:white;}"
    "QTabBar::tab{background:#cce0ff;padding:6px 14px;font-weight:bold;}"
    "QTabBar::tab:selected{background:white;border-bottom:2px solid "
    "rgb(0,85,255);}"
)
HDR_STYLE = "font-size:22px;font-weight:bold;color:white;padding:4px;"


def _apply_palette(widget):
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.ColorRole.Window, BLUE)
    pal.setColor(QtGui.QPalette.ColorRole.Button, BLUE)
    pal.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(255, 255, 255))
    pal.setColor(
    QtGui.QPalette.ColorRole.WindowText,
    QtGui.QColor(
        255,
        255,
         255))
    pal.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(0, 0, 0))
    pal.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(0, 0, 0))
    widget.setPalette(pal)


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft):
    item = QtWidgets.QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable |
                  QtCore.Qt.ItemFlag.ItemIsEnabled)
    item.setTextAlignment(align | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return item


def _ro_r(text):
    return _ro(text, QtCore.Qt.AlignmentFlag.AlignRight)


def _ro_c(text):
    return _ro(text, QtCore.Qt.AlignmentFlag.AlignCenter)


def _money(v):
    try:
        return f"{float(v):,.2f}" if v is not None else "0.00"
    except (ValueError, TypeError):
        return "0.00"


def _export_csv(table: QtWidgets.QTableWidget, parent):
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent, "Export to CSV", "", "CSV Files (*.csv)"
    )
    if not path:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        headers = [table.horizontalHeaderItem(
            c).text() for c in range(table.columnCount())]
        w.writerow(headers)
        for r in range(table.rowCount()):
            row = [
    table.item(
        r,
        c).text() if table.item(
            r,
            c) else "" for c in range(
                table.columnCount())]
            w.writerow(row)
    QtWidgets.QMessageBox.information(parent, "Export", f"Saved to:\n{path}")


# ═════════════════════════════════════════════════════════════════════════════
# Main Window
# ═════════════════════════════════════════════════════════════════════════════
class BankReconciliationWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        init_db()
        _apply_palette(self)
        self._current_stmt_id = None
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        title = QtWidgets.QLabel("Bank Reconciliation")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(HDR_STYLE)
        root.addWidget(title)

        self.tabs = ButtonNav()
        self.tabs.setStyleSheet(TAB_STYLE)
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_accounts_tab(), "Bank Accounts")
        self.tabs.addTab(self._build_statements_tab(), "Statement Entry")
        self.tabs.addTab(self._build_reconcile_tab(), "Reconciliation")
        self.tabs.addTab(self._build_history_tab(), "History")

        self.tabs.currentChanged.connect(self._on_tab_change)

    # ── Bank Accounts tab ───────────────────────────────────────────────────
    def _build_accounts_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        self.ba_tbl = QtWidgets.QTableWidget(0, 7)
        self.ba_tbl.setHorizontalHeaderLabels(
            ["ID",
    "Account Name",
    "Bank Name",
    "Account #",
    "GL Account",
    "Active",
     "Notes"]
        )
        self.ba_tbl.setColumnWidth(0, 40)
        self.ba_tbl.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ba_tbl.setColumnWidth(2, 140)
        self.ba_tbl.setColumnWidth(3, 120)
        self.ba_tbl.setColumnWidth(4, 160)
        self.ba_tbl.setColumnWidth(5, 55)
        self.ba_tbl.setColumnWidth(6, 160)
        self.ba_tbl.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ba_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ba_tbl.setAlternatingRowColors(True)
        self.ba_tbl.verticalHeader().setDefaultSectionSize(24)
        self.ba_tbl.itemSelectionChanged.connect(self._on_ba_select)
        v.addWidget(self.ba_tbl)

        fg = QtWidgets.QGroupBox("Account Details")
        fg.setStyleSheet("QGroupBox{font-weight:bold;background:white;border:1px solid #aaa;"  # noqa: E501
                         "border-radius:6px;}QGroupBox::title{padding:2px "
                         "8px;}")
        fl = QtWidgets.QFormLayout(fg)
        fl.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)

        self.ba_ef_name = QtWidgets.QLineEdit()
        self.ba_ef_bank = QtWidgets.QLineEdit()
        self.ba_ef_acctno = QtWidgets.QLineEdit()
        self.ba_ef_routing = QtWidgets.QLineEdit()
        self.ba_ef_gl = QtWidgets.QComboBox()
        self.ba_ef_gl.setMinimumWidth(200)
        self.ba_ef_active = QtWidgets.QCheckBox("Active")
        self.ba_ef_active.setChecked(True)
        self.ba_ef_notes = QtWidgets.QLineEdit()

        fl.addRow("Account Name *", self.ba_ef_name)
        fl.addRow("Bank Name", self.ba_ef_bank)
        fl.addRow("Account Number", self.ba_ef_acctno)
        fl.addRow("Routing Number", self.ba_ef_routing)
        fl.addRow("GL Account", self.ba_ef_gl)
        fl.addRow("", self.ba_ef_active)
        fl.addRow("Notes", self.ba_ef_notes)
        v.addWidget(fg)

        bb = QtWidgets.QHBoxLayout()
        for lbl, slot in [("Add Account", self._on_ba_add),
                          ("Update Account", self._on_ba_update),
                          ("Delete Account", self._on_ba_delete),
                          ("Clear", self._on_ba_clear)]:
            b = QtWidgets.QPushButton(lbl)
            b.setStyleSheet(BTN_STYLE)
            b.clicked.connect(slot)
            bb.addWidget(b)
        bb.addStretch()
        v.addLayout(bb)

        self._refresh_ba_gl_combo()
        self._refresh_accounts()
        return w

    def _refresh_ba_gl_combo(self):
        self.ba_ef_gl.clear()
        self.ba_ef_gl.addItem("-- none --", None)
        with _conn() as con:
            rows = con.execute(
                "SELECT id, account_number, account_name FROM gl_account "
                "WHERE is_active=1 AND account_type='Asset' ORDER BY "
                "account_number"
            ).fetchall()
        for r in rows:
            self.ba_ef_gl.addItem(
                f"{r['account_number']} – {r['account_name']}", r["id"])

    def _refresh_accounts(self):
        with _conn() as con:
            rows = con.execute(
                "SELECT ba.*, ga.account_number, ga.account_name "
                "FROM bank_account ba "
                "LEFT JOIN gl_account ga ON ga.id=ba.gl_account_id "
                "ORDER BY ba.account_name"
            ).fetchall()
        self.ba_tbl.setRowCount(0)
        for row in rows:
            r = self.ba_tbl.rowCount()
            self.ba_tbl.insertRow(r)
            gl_text = f"{
    row['account_number']} – {
        row['account_name']}" if row["account_number"] else ""
            self.ba_tbl.setItem(r, 0, _ro_c(str(row["id"])))
            self.ba_tbl.setItem(r, 1, _ro(row["account_name"]))
            self.ba_tbl.setItem(r, 2, _ro(row["bank_name"]))
            self.ba_tbl.setItem(r, 3, _ro(row["account_number"] or ""))
            self.ba_tbl.setItem(r, 4, _ro(gl_text))
            self.ba_tbl.setItem(
    r, 5, _ro_c(
        "Yes" if row["is_active"] else "No"))
            self.ba_tbl.setItem(r, 6, _ro(row["notes"]))
            self.ba_tbl.item(
    r,
    0).setData(
        QtCore.Qt.ItemDataRole.UserRole,
         row["id"])
            if not row["is_active"]:
                for c in range(7):
                    it = self.ba_tbl.item(r, c)
                    if it:
                        it.setForeground(QtGui.QColor(160, 160, 160))

    def _on_ba_select(self):
        rows = self.ba_tbl.selectionModel().selectedRows()
        if not rows:
            return
        r = rows[0].row()
        bid = self.ba_tbl.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        with _conn() as con:
            row = con.execute(
    "SELECT * FROM bank_account WHERE id=%s", (bid,)).fetchone()
        if not row:
            return
        self.ba_ef_name.setText(row["account_name"])
        self.ba_ef_bank.setText(row["bank_name"] or "")
        self.ba_ef_acctno.setText(row["account_number"] or "")
        self.ba_ef_routing.setText(row["routing_number"] or "")
        self.ba_ef_active.setChecked(bool(row["is_active"]))
        self.ba_ef_notes.setText(row["notes"] or "")
        if row["gl_account_id"]:
            idx = self.ba_ef_gl.findData(row["gl_account_id"])
            if idx >= 0:
                self.ba_ef_gl.setCurrentIndex(idx)
        else:
            self.ba_ef_gl.setCurrentIndex(0)

    def _ba_form_values(self):
        return (
            self.ba_ef_name.text().strip(),
            self.ba_ef_bank.text().strip(),
            self.ba_ef_acctno.text().strip(),
            self.ba_ef_routing.text().strip(),
            self.ba_ef_gl.currentData(),
            1 if self.ba_ef_active.isChecked() else 0,
            self.ba_ef_notes.text().strip(),
        )

    def _on_ba_add(self):
        name, bank, acctno, routing, gl_id, active, notes = self._ba_form_values()  # noqa: E501
        if not name:
            QtWidgets.QMessageBox.warning(
    self, "Validation", "Account Name is required.")
            return
        with _conn() as con:
            con.execute(
                "INSERT INTO bank_account(account_name,bank_name,account_number,routing_number,"  # noqa: E501
                "gl_account_id,is_active,notes) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (name, bank, acctno, routing, gl_id, active, notes)
            )
        self._refresh_accounts()
        self._on_ba_clear()

    def _selected_ba_id(self):
        rows = self.ba_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(
    self, "Selection", "Select a bank account first.")
            return None
        return self.ba_tbl.item(rows[0].row(), 0).data(
            QtCore.Qt.ItemDataRole.UserRole)

    def _on_ba_update(self):
        bid = self._selected_ba_id()
        if bid is None:
            return
        name, bank, acctno, routing, gl_id, active, notes = self._ba_form_values()  # noqa: E501
        if not name:
            QtWidgets.QMessageBox.warning(
    self, "Validation", "Account Name is required.")
            return
        with _conn() as con:
            con.execute(
                "UPDATE bank_account SET "
                "account_name=%s,bank_name=%s,account_number=%s,"
                "routing_number=%s,gl_account_id=%s,is_active=%s,notes=%s "
                "WHERE id=%s",
                (name, bank, acctno, routing, gl_id, active, notes, bid)
            )
        self._refresh_accounts()

    def _on_ba_delete(self):
        bid = self._selected_ba_id()
        if bid is None:
            return
        if QtWidgets.QMessageBox.question(
            self, "Delete", "Delete this bank account and all its statements%s",  # noqa: E501
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute("DELETE FROM bank_account WHERE id=%s", (bid,))
            self._refresh_accounts()
            self._on_ba_clear()

    def _on_ba_clear(self):
        self.ba_ef_name.clear()
        self.ba_ef_bank.clear()
        self.ba_ef_acctno.clear()
        self.ba_ef_routing.clear()
        self.ba_ef_notes.clear()
        self.ba_ef_active.setChecked(True)
        self.ba_ef_gl.setCurrentIndex(0)
        self.ba_tbl.clearSelection()

    # ── Statement Entry tab ─────────────────────────────────────────────────
    def _build_statements_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        # Statement list header
        hdr = QtWidgets.QHBoxLayout()
        hdr.addWidget(QtWidgets.QLabel("Bank Account:"))
        self.st_ba_filter = QtWidgets.QComboBox()
        self.st_ba_filter.setMinimumWidth(220)
        self.st_ba_filter.currentIndexChanged.connect(self._refresh_statements)
        hdr.addWidget(self.st_ba_filter)
        hdr.addWidget(QtWidgets.QLabel("Status:"))
        self.st_status_filter = QtWidgets.QComboBox()
        self.st_status_filter.addItem("All Statuses")
        for s in STATUSES:
            self.st_status_filter.addItem(s)
        self.st_status_filter.currentIndexChanged.connect(
            self._refresh_statements)
        hdr.addWidget(self.st_status_filter)
        hdr.addStretch()
        v.addLayout(hdr)

        # Statement list (top)
        self.st_tbl = QtWidgets.QTableWidget(0, 7)
        self.st_tbl.setHorizontalHeaderLabels(
            ["ID",
    "Bank Account",
    "Statement Date",
    "Beg. Balance",
    "End Balance",
    "Status",
     "Reconciled By"]
        )
        self.st_tbl.setColumnWidth(0, 40)
        self.st_tbl.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.st_tbl.setColumnWidth(2, 120)
        self.st_tbl.setColumnWidth(3, 110)
        self.st_tbl.setColumnWidth(4, 110)
        self.st_tbl.setColumnWidth(5, 100)
        self.st_tbl.setColumnWidth(6, 120)
        self.st_tbl.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.st_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.st_tbl.setAlternatingRowColors(True)
        self.st_tbl.verticalHeader().setDefaultSectionSize(24)
        self.st_tbl.setMaximumHeight(180)
        self.st_tbl.itemSelectionChanged.connect(self._on_stmt_select)
        v.addWidget(self.st_tbl)

        # Statement form
        fg = QtWidgets.QGroupBox("Statement Details")
        fg.setStyleSheet("QGroupBox{font-weight:bold;background:white;border:1px solid #aaa;"  # noqa: E501
                         "border-radius:6px;}QGroupBox::title{padding:2px "
                         "8px;}")
        fl = QtWidgets.QFormLayout(fg)
        fl.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)

        self.st_ef_ba = QtWidgets.QComboBox()
        self.st_ef_ba.setMinimumWidth(200)
        self.st_ef_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.st_ef_date.setDate(QtCore.QDate.currentDate())
        self.st_ef_beg_bal = QtWidgets.QDoubleSpinBox()
        self.st_ef_beg_bal.setRange(-99_999_999, 99_999_999)
        self.st_ef_beg_bal.setDecimals(2)
        self.st_ef_end_bal = QtWidgets.QDoubleSpinBox()
        self.st_ef_end_bal.setRange(-99_999_999, 99_999_999)
        self.st_ef_end_bal.setDecimals(2)
        self.st_ef_status = QtWidgets.QComboBox()
        for s in STATUSES:
            self.st_ef_status.addItem(s)
        self.st_ef_by = QtWidgets.QLineEdit()
        self.st_ef_notes = QtWidgets.QLineEdit()

        fl.addRow("Bank Account *", self.st_ef_ba)
        fl.addRow("Statement Date *", self.st_ef_date)
        fl.addRow("Beginning Balance", self.st_ef_beg_bal)
        fl.addRow("Ending Balance", self.st_ef_end_bal)
        fl.addRow("Status", self.st_ef_status)
        fl.addRow("Reconciled By", self.st_ef_by)
        fl.addRow("Notes", self.st_ef_notes)
        v.addWidget(fg)

        sb = QtWidgets.QHBoxLayout()
        for lbl, slot in [("Add Statement", self._on_st_add),
                          ("Update Statement", self._on_st_update),
                          ("Delete Statement", self._on_st_delete),
                          ("Clear", self._on_st_clear),
                          ("Open Items →", self._on_st_open_items)]:
            b = QtWidgets.QPushButton(lbl)
            b.setStyleSheet(BTN_STYLE)
            b.clicked.connect(slot)
            sb.addWidget(b)
        sb.addStretch()
        v.addLayout(sb)

        # Statement items
        items_lbl = QtWidgets.QLabel("Statement Line Items:")
        items_lbl.setStyleSheet("font-weight:bold;color:white;margin-top:6px;")
        v.addWidget(items_lbl)

        self.si_tbl = QtWidgets.QTableWidget(0, 6)
        self.si_tbl.setHorizontalHeaderLabels(
            ["ID", "Date", "Description", "Type", "Amount", "Matched"]
        )
        self.si_tbl.setColumnWidth(0, 40)
        self.si_tbl.setColumnWidth(1, 100)
        self.si_tbl.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.si_tbl.setColumnWidth(3, 70)
        self.si_tbl.setColumnWidth(4, 110)
        self.si_tbl.setColumnWidth(5, 70)
        self.si_tbl.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.si_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.si_tbl.setAlternatingRowColors(True)
        self.si_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.si_tbl)

        # Item entry form
        item_fg = QtWidgets.QGroupBox("Add / Edit Line Item")
        item_fg.setStyleSheet("QGroupBox{font-weight:bold;background:white;border:1px solid #aaa;"  # noqa: E501
                              "border-radius:6px;}QGroupBox::title{padding:2px 8px;}")  # noqa: E501
        item_fl = QtWidgets.QFormLayout(item_fg)
        item_fl.setRowWrapPolicy(
    QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)

        self.si_ef_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.si_ef_date.setDate(QtCore.QDate.currentDate())
        self.si_ef_desc = QtWidgets.QLineEdit()
        self.si_ef_type = QtWidgets.QComboBox()
        for t in ITEM_TYPES:
            self.si_ef_type.addItem(t)
        self.si_ef_amt = QtWidgets.QDoubleSpinBox()
        self.si_ef_amt.setRange(0, 99_999_999)
        self.si_ef_amt.setDecimals(2)

        item_fl.addRow("Date *", self.si_ef_date)
        item_fl.addRow("Description", self.si_ef_desc)
        item_fl.addRow("Type", self.si_ef_type)
        item_fl.addRow("Amount *", self.si_ef_amt)
        v.addWidget(item_fg)

        ib = QtWidgets.QHBoxLayout()
        for lbl, slot in [("Add Item", self._on_si_add),
                          ("Delete Item", self._on_si_delete),
                          ("Clear Item", self._on_si_clear),
                          ("Export CSV", lambda: _export_csv(self.si_tbl, self))]:  # noqa: E501
            b = QtWidgets.QPushButton(lbl)
            b.setStyleSheet(BTN_STYLE)
            b.clicked.connect(slot)
            ib.addWidget(b)
        self.si_tbl.itemSelectionChanged.connect(self._on_si_select)
        ib.addStretch()
        v.addLayout(ib)
        return w

    def _refresh_ba_combos(self):
        for combo in [self.st_ba_filter, self.st_ef_ba]:
            combo.blockSignals(True)
            combo.clear()
        self.st_ba_filter.addItem("All Accounts", None)
        self.st_ef_ba.addItem("-- select --", None)
        with _conn() as con:
            rows = con.execute(
                "SELECT id, account_name, bank_name FROM bank_account WHERE "
                "is_active=1 ORDER BY account_name"
            ).fetchall()
        for row in rows:
            label = f"{
    row['account_name']} ({
        row['bank_name']})" if row["bank_name"] else row["account_name"]
            self.st_ba_filter.addItem(label, row["id"])
            self.st_ef_ba.addItem(label, row["id"])
        for combo in [self.st_ba_filter, self.st_ef_ba]:
            combo.blockSignals(False)

    def _refresh_statements(self):
        ba_id = self.st_ba_filter.currentData()
        status = self.st_status_filter.currentText()
        q = """
            SELECT bs.*, ba.account_name
            FROM bank_statement bs
            JOIN bank_account ba ON ba.id=bs.bank_account_id
        """
        params, where = [], []
        if ba_id:
            where.append("bs.bank_account_id=%s")
            params.append(ba_id)
        if status != "All Statuses":
            where.append("bs.status=%s")
            params.append(status)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY bs.statement_date DESC"
        with _conn() as con:
            rows = con.execute(q, params).fetchall()
        self.st_tbl.setRowCount(0)
        STATUS_COLORS = {
            "Open": QtGui.QColor(240, 240, 240),
            "In Progress": QtGui.QColor(200, 230, 255),
            "Reconciled": QtGui.QColor(200, 255, 210),
        }
        for row in rows:
            r = self.st_tbl.rowCount()
            self.st_tbl.insertRow(r)
            self.st_tbl.setItem(r, 0, _ro_c(str(row["id"])))
            self.st_tbl.setItem(r, 1, _ro(row["account_name"]))
            self.st_tbl.setItem(r, 2, _ro_c(row["statement_date"]))
            self.st_tbl.setItem(r, 3, _ro_r(_money(row["beginning_balance"])))
            self.st_tbl.setItem(r, 4, _ro_r(_money(row["ending_balance"])))
            self.st_tbl.setItem(r, 5, _ro_c(row["status"]))
            self.st_tbl.setItem(r, 6, _ro(row["reconciled_by"] or ""))
            self.st_tbl.item(
    r,
    0).setData(
        QtCore.Qt.ItemDataRole.UserRole,
         row["id"])
            color = STATUS_COLORS.get(
    row["status"], QtGui.QColor(
        255, 255, 255))
            for c in range(7):
                it = self.st_tbl.item(r, c)
                if it:
                    it.setBackground(color)

    def _on_stmt_select(self):
        rows = self.st_tbl.selectionModel().selectedRows()
        if not rows:
            return
        r = rows[0].row()
        sid = self.st_tbl.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        self._current_stmt_id = sid
        with _conn() as con:
            row = con.execute(
    "SELECT * FROM bank_statement WHERE id=%s", (sid,)).fetchone()
        if not row:
            return
        idx = self.st_ef_ba.findData(row["bank_account_id"])
        if idx >= 0:
            self.st_ef_ba.setCurrentIndex(idx)
        self.st_ef_date.setDate(
    QtCore.QDate.fromString(
        row["statement_date"],
         "yyyy-MM-dd"))
        self.st_ef_beg_bal.setValue(row["beginning_balance"] or 0.0)
        self.st_ef_end_bal.setValue(row["ending_balance"] or 0.0)
        sidx = self.st_ef_status.findText(row["status"])
        if sidx >= 0:
            self.st_ef_status.setCurrentIndex(sidx)
        self.st_ef_by.setText(row["reconciled_by"] or "")
        self.st_ef_notes.setText(row["notes"] or "")
        self._refresh_stmt_items()

    def _refresh_stmt_items(self):
        if not self._current_stmt_id:
            self.si_tbl.setRowCount(0)
            return
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM bank_statement_item WHERE statement_id=%s "
                "ORDER BY item_date, id",
                (self._current_stmt_id,)
            ).fetchall()
        self.si_tbl.setRowCount(0)
        for row in rows:
            r = self.si_tbl.rowCount()
            self.si_tbl.insertRow(r)
            self.si_tbl.setItem(r, 0, _ro_c(str(row["id"])))
            self.si_tbl.setItem(r, 1, _ro_c(row["item_date"]))
            self.si_tbl.setItem(r, 2, _ro(row["description"]))
            self.si_tbl.setItem(r, 3, _ro_c(row["item_type"]))
            self.si_tbl.setItem(r, 4, _ro_r(_money(row["amount"])))
            matched = "Yes" if row["is_matched"] else "No"
            self.si_tbl.setItem(r, 5, _ro_c(matched))
            self.si_tbl.item(
    r,
    0).setData(
        QtCore.Qt.ItemDataRole.UserRole,
         row["id"])
            if row["is_matched"]:
                for c in range(6):
                    it = self.si_tbl.item(r, c)
                    if it:
                        it.setBackground(QtGui.QColor(200, 255, 210))

    def _st_form_values(self):
        return (
            self.st_ef_ba.currentData(),
            self.st_ef_date.date().toString("yyyy-MM-dd"),
            self.st_ef_beg_bal.value(),
            self.st_ef_end_bal.value(),
            self.st_ef_status.currentText(),
            self.st_ef_by.text().strip(),
            self.st_ef_notes.text().strip(),
        )

    def _on_st_add(self):
        ba_id, dt, beg, end, status, by, notes = self._st_form_values()
        if not ba_id:
            QtWidgets.QMessageBox.warning(
    self, "Validation", "Select a bank account.")
            return
        with _conn() as con:
            con.execute(
                "INSERT INTO bank_statement(bank_account_id,statement_date,beginning_balance,"  # noqa: E501
                "ending_balance,status,reconciled_by,notes) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (ba_id, dt, beg, end, status, by, notes)
            )
        self._refresh_statements()
        self._on_st_clear()

    def _selected_stmt_id(self):
        rows = self.st_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(
    self, "Selection", "Select a statement first.")
            return None
        return self.st_tbl.item(rows[0].row(), 0).data(
            QtCore.Qt.ItemDataRole.UserRole)

    def _on_st_update(self):
        sid = self._selected_stmt_id()
        if sid is None:
            return
        ba_id, dt, beg, end, status, by, notes = self._st_form_values()
        if not ba_id:
            QtWidgets.QMessageBox.warning(
    self, "Validation", "Select a bank account.")
            return
        with _conn() as con:
            con.execute(
                "UPDATE bank_statement SET "
                "bank_account_id=%s,statement_date=%s,beginning_balance=%s,"
                "ending_balance=%s,status=%s,reconciled_by=%s,notes=%s WHERE "
                "id=%s",
                (ba_id, dt, beg, end, status, by, notes, sid)
            )
        self._refresh_statements()

    def _on_st_delete(self):
        sid = self._selected_stmt_id()
        if sid is None:
            return
        if QtWidgets.QMessageBox.question(
            self, "Delete", "Delete this statement and all its line items%s",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute("DELETE FROM bank_statement WHERE id=%s", (sid,))
            if self._current_stmt_id == sid:
                self._current_stmt_id = None
            self._refresh_statements()
            self.si_tbl.setRowCount(0)
            self._on_st_clear()

    def _on_st_clear(self):
        self.st_ef_ba.setCurrentIndex(0)
        self.st_ef_date.setDate(QtCore.QDate.currentDate())
        self.st_ef_beg_bal.setValue(0.0)
        self.st_ef_end_bal.setValue(0.0)
        self.st_ef_status.setCurrentIndex(0)
        self.st_ef_by.clear()
        self.st_ef_notes.clear()
        self.st_tbl.clearSelection()
        self._current_stmt_id = None
        self.si_tbl.setRowCount(0)

    def _on_st_open_items(self):
        sid = self._selected_stmt_id()
        if sid is None:
            return
        self._current_stmt_id = sid
        self.tabs.setCurrentIndex(2)
        self._refresh_reconcile_tab()

    # Statement items
    def _on_si_select(self):
        rows = self.si_tbl.selectionModel().selectedRows()
        if not rows:
            return
        r = rows[0].row()
        iid = self.si_tbl.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        with _conn() as con:
            row = con.execute(
    "SELECT * FROM bank_statement_item WHERE id=%s", (iid,)).fetchone()
        if not row:
            return
        self.si_ef_date.setDate(
    QtCore.QDate.fromString(
        row["item_date"],
         "yyyy-MM-dd"))
        self.si_ef_desc.setText(row["description"] or "")
        idx = self.si_ef_type.findText(row["item_type"])
        if idx >= 0:
            self.si_ef_type.setCurrentIndex(idx)
        self.si_ef_amt.setValue(row["amount"] or 0.0)

    def _on_si_add(self):
        if not self._current_stmt_id:
            QtWidgets.QMessageBox.warning(
    self, "No Statement", "Select a statement first.")
            return
        dt = self.si_ef_date.date().toString("yyyy-MM-dd")
        desc = self.si_ef_desc.text().strip()
        typ = self.si_ef_type.currentText()
        amt = self.si_ef_amt.value()
        if amt <= 0:
            QtWidgets.QMessageBox.warning(
    self, "Validation", "Amount must be greater than zero.")
            return
        with _conn() as con:
            con.execute(
                "INSERT INTO bank_statement_item(statement_id,item_date,description,amount,item_type) "  # noqa: E501
                "VALUES(%s,%s,%s,%s,%s)",
                (self._current_stmt_id, dt, desc, amt, typ)
            )
        self._refresh_stmt_items()
        self._on_si_clear()

    def _on_si_delete(self):
        rows = self.si_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(
    self, "Selection", "Select a line item first.")
            return
        iid = self.si_tbl.item(
    rows[0].row(), 0).data(
        QtCore.Qt.ItemDataRole.UserRole)
        with _conn() as con:
            matched = con.execute(
                "SELECT is_matched FROM bank_statement_item WHERE id=%s", (
                    iid,)
            ).fetchone()
        if matched and matched["is_matched"]:
            QtWidgets.QMessageBox.warning(
    self, "Matched", "Unmatch this item in Reconciliation before deleting.")
            return
        with _conn() as con:
            con.execute("DELETE FROM bank_statement_item WHERE id=%s", (iid,))
        self._refresh_stmt_items()

    def _on_si_clear(self):
        self.si_ef_date.setDate(QtCore.QDate.currentDate())
        self.si_ef_desc.clear()
        self.si_ef_type.setCurrentIndex(0)
        self.si_ef_amt.setValue(0.0)
        self.si_tbl.clearSelection()

    # ── Reconciliation tab ──────────────────────────────────────────────────
    def _build_reconcile_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        # Statement selector
        sel = QtWidgets.QHBoxLayout()
        sel.addWidget(QtWidgets.QLabel("Statement:"))
        self.rec_stmt_combo = QtWidgets.QComboBox()
        self.rec_stmt_combo.setMinimumWidth(340)
        self.rec_stmt_combo.currentIndexChanged.connect(
            self._on_rec_stmt_change)
        sel.addWidget(self.rec_stmt_combo)
        btn_load = QtWidgets.QPushButton("Load")
        btn_load.setStyleSheet(BTN_STYLE)
        btn_load.clicked.connect(self._refresh_reconcile_tab)
        sel.addWidget(btn_load)
        sel.addStretch()
        btn_mark = QtWidgets.QPushButton("Mark Reconciled")
        btn_mark.setStyleSheet(BTN_STYLE)
        btn_mark.clicked.connect(self._on_mark_reconciled)
        sel.addWidget(btn_mark)
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BTN_STYLE)
        btn_exp.clicked.connect(lambda: _export_csv(self.rec_match_tbl, self))
        sel.addWidget(btn_exp)
        v.addLayout(sel)

        # Summary bar
        self.rec_summary = QtWidgets.QLabel("")
        self.rec_summary.setStyleSheet(
            "background:rgba(255,255,255,30);border-radius:6px;padding:6px "
            "12px;"
            "color:white;font-weight:bold;font-size:13px;"
        )
        self.rec_summary.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.rec_summary)

        # Two-panel: GL transactions | Bank statement items
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # Left: GL Transactions
        gl_frame = QtWidgets.QGroupBox("GL Transactions (Book Side)")
        gl_frame.setStyleSheet("QGroupBox{font-weight:bold;background:white;border:1px solid #aaa;"  # noqa: E501
                               "border-radius:6px;}QGroupBox::title{padding:2px 8px;}")  # noqa: E501
        gl_v = QtWidgets.QVBoxLayout(gl_frame)
        self.rec_gl_tbl = QtWidgets.QTableWidget(0, 5)
        self.rec_gl_tbl.setHorizontalHeaderLabels(
            ["Line ID", "Date", "Description", "Debit", "Credit"])
        self.rec_gl_tbl.setColumnWidth(0, 60)
        self.rec_gl_tbl.setColumnWidth(1, 90)
        self.rec_gl_tbl.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rec_gl_tbl.setColumnWidth(3, 90)
        self.rec_gl_tbl.setColumnWidth(4, 90)
        self.rec_gl_tbl.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.rec_gl_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rec_gl_tbl.setAlternatingRowColors(True)
        self.rec_gl_tbl.verticalHeader().setDefaultSectionSize(22)
        gl_v.addWidget(self.rec_gl_tbl)
        splitter.addWidget(gl_frame)

        # Right: Bank Statement Items
        st_frame = QtWidgets.QGroupBox("Bank Statement Items")
        st_frame.setStyleSheet("QGroupBox{font-weight:bold;background:white;border:1px solid #aaa;"  # noqa: E501
                               "border-radius:6px;}QGroupBox::title{padding:2px 8px;}")  # noqa: E501
        st_v = QtWidgets.QVBoxLayout(st_frame)
        self.rec_st_tbl = QtWidgets.QTableWidget(0, 4)
        self.rec_st_tbl.setHorizontalHeaderLabels(
            ["Item ID", "Date", "Description", "Amount"])
        self.rec_st_tbl.setColumnWidth(0, 60)
        self.rec_st_tbl.setColumnWidth(1, 90)
        self.rec_st_tbl.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rec_st_tbl.setColumnWidth(3, 90)
        self.rec_st_tbl.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.rec_st_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rec_st_tbl.setAlternatingRowColors(True)
        self.rec_st_tbl.verticalHeader().setDefaultSectionSize(22)
        st_v.addWidget(self.rec_st_tbl)
        splitter.addWidget(st_frame)

        splitter.setSizes([600, 400])
        v.addWidget(splitter, stretch=2)

        # Match controls
        mc = QtWidgets.QHBoxLayout()
        btn_match = QtWidgets.QPushButton("Match Selected Pair")
        btn_match.setStyleSheet(BTN_STYLE)
        btn_match.clicked.connect(self._on_match_pair)
        mc.addWidget(btn_match)
        btn_auto = QtWidgets.QPushButton("Auto-Match by Amount & Date")
        btn_auto.setStyleSheet(BTN_STYLE)
        btn_auto.clicked.connect(self._on_auto_match)
        mc.addWidget(btn_auto)
        mc.addStretch()
        v.addLayout(mc)

        # Matched pairs table
        matched_lbl = QtWidgets.QLabel("Matched Pairs:")
        matched_lbl.setStyleSheet(
            "font-weight:bold;color:white;margin-top:4px;")
        v.addWidget(matched_lbl)

        self.rec_match_tbl = QtWidgets.QTableWidget(0, 7)
        self.rec_match_tbl.setHorizontalHeaderLabels(
            ["Match ID", "GL Date", "GL Description", "GL Amount",
                "Stmt Date", "Stmt Description", "Stmt Amount"]
        )
        self.rec_match_tbl.setColumnWidth(0, 70)
        self.rec_match_tbl.setColumnWidth(1, 90)
        self.rec_match_tbl.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rec_match_tbl.setColumnWidth(3, 100)
        self.rec_match_tbl.setColumnWidth(4, 90)
        self.rec_match_tbl.horizontalHeader().setSectionResizeMode(
            5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rec_match_tbl.setColumnWidth(6, 100)
        self.rec_match_tbl.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.rec_match_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rec_match_tbl.setAlternatingRowColors(True)
        self.rec_match_tbl.verticalHeader().setDefaultSectionSize(22)
        self.rec_match_tbl.setMaximumHeight(160)
        v.addWidget(self.rec_match_tbl)

        ub = QtWidgets.QHBoxLayout()
        btn_unmatch = QtWidgets.QPushButton("Unmatch Selected")
        btn_unmatch.setStyleSheet(BTN_STYLE)
        btn_unmatch.clicked.connect(self._on_unmatch)
        ub.addWidget(btn_unmatch)
        ub.addStretch()
        v.addLayout(ub)
        return w

    def _populate_rec_stmt_combo(self):
        self.rec_stmt_combo.blockSignals(True)
        self.rec_stmt_combo.clear()
        self.rec_stmt_combo.addItem("-- select statement --", None)
        with _conn() as con:
            rows = con.execute(
                "SELECT bs.id, bs.statement_date, bs.ending_balance, "
                "bs.status, ba.account_name "
                "FROM bank_statement bs "
                "JOIN bank_account ba ON ba.id=bs.bank_account_id "
                "ORDER BY bs.statement_date DESC"
            ).fetchall()
        for row in rows:
            label = (f"{row['account_name']} — {row['statement_date']} "
                     f"(Bal: {_money(row['ending_balance'])}) [{row['status']}]")  # noqa: E501
            self.rec_stmt_combo.addItem(label, row["id"])
        if self._current_stmt_id:
            idx = self.rec_stmt_combo.findData(self._current_stmt_id)
            if idx >= 0:
                self.rec_stmt_combo.setCurrentIndex(idx)
        self.rec_stmt_combo.blockSignals(False)

    def _on_rec_stmt_change(self):
        self._current_stmt_id = self.rec_stmt_combo.currentData()

    def _refresh_reconcile_tab(self):
        sid = self.rec_stmt_combo.currentData() or self._current_stmt_id
        if not sid:
            self.rec_summary.setText("Select a statement and click Load.")
            return
        self._current_stmt_id = sid

        with _conn() as con:
            stmt = con.execute(
                "SELECT bs.*, ba.gl_account_id, ba.account_name "
                "FROM bank_statement bs "
                "JOIN bank_account ba ON ba.id=bs.bank_account_id "
                "WHERE bs.id=%s", (sid,)
            ).fetchone()
            if not stmt:
                return
            gl_acct_id = stmt["gl_account_id"]

            # Unmatched GL lines for this account
            gl_rows = []
            if gl_acct_id:
                gl_rows = con.execute("""
                    SELECT l.id, j.journal_date, j.description, l.debit,
                        l.credit
                    FROM gl_journal_line l
                    JOIN gl_journal j ON j.id=l.journal_id
                    WHERE l.account_id=%s
                      AND l.id NOT IN (
                          SELECT journal_line_id FROM bank_reconciliation
                          WHERE statement_id=%s AND journal_line_id IS NOT NULL
                      )
                    ORDER BY j.journal_date
                """, (gl_acct_id, sid)).fetchall()

            # Unmatched statement items
            st_rows = con.execute(
                "SELECT * FROM bank_statement_item "
                "WHERE statement_id=%s AND is_matched=0 ORDER BY item_date",
                (sid,)
            ).fetchall()

            # Matched pairs
            matches = con.execute("""
                SELECT br.id,
                       j.journal_date, j.description,
                       l.debit, l.credit,
                       si.item_date, si.description AS st_desc, si.amount AS
                           st_amount,
                       si.item_type
                FROM bank_reconciliation br
                LEFT JOIN gl_journal_line l  ON l.id=br.journal_line_id
                LEFT JOIN gl_journal j        ON j.id=l.journal_id
                LEFT JOIN bank_statement_item si ON si.id=br.statement_item_id
                WHERE br.statement_id=%s
                ORDER BY j.journal_date
            """, (sid,)).fetchall()

            # Book balance (net movement on the GL account)
            book_bal = 0.0
            if gl_acct_id:
                res = con.execute(
                    "SELECT COALESCE(SUM(l.debit - l.credit),0) AS net "
                    "FROM gl_journal_line l "
                    "JOIN gl_journal j ON j.id=l.journal_id "
                    "WHERE l.account_id=%s",
                    (gl_acct_id,)
                ).fetchone()
                book_bal = res["net"] if res else 0.0

        # Populate GL table
        self.rec_gl_tbl.setRowCount(0)
        for row in gl_rows:
            r = self.rec_gl_tbl.rowCount()
            self.rec_gl_tbl.insertRow(r)
            self.rec_gl_tbl.setItem(r, 0, _ro_c(str(row["id"])))
            self.rec_gl_tbl.setItem(r, 1, _ro_c(row["journal_date"] or ""))
            self.rec_gl_tbl.setItem(r, 2, _ro(row["description"] or ""))
            self.rec_gl_tbl.setItem(
    r, 3, _ro_r(
        _money(
            row["debit"]) if row["debit"] else ""))
            self.rec_gl_tbl.setItem(
    r, 4, _ro_r(
        _money(
            row["credit"]) if row["credit"] else ""))
            self.rec_gl_tbl.item(
    r,
    0).setData(
        QtCore.Qt.ItemDataRole.UserRole,
         row["id"])

        # Populate statement items table
        self.rec_st_tbl.setRowCount(0)
        for row in st_rows:
            r = self.rec_st_tbl.rowCount()
            self.rec_st_tbl.insertRow(r)
            signed = row["amount"] if row["item_type"] == "Credit" else -row["amount"]  # noqa: E501
            self.rec_st_tbl.setItem(r, 0, _ro_c(str(row["id"])))
            self.rec_st_tbl.setItem(r, 1, _ro_c(row["item_date"]))
            self.rec_st_tbl.setItem(r, 2, _ro(row["description"]))
            self.rec_st_tbl.setItem(r, 3, _ro_r(_money(signed)))
            self.rec_st_tbl.item(
    r,
    0).setData(
        QtCore.Qt.ItemDataRole.UserRole,
         row["id"])
            color = QtGui.QColor(
    220,
    255,
    220) if row["item_type"] == "Credit" else QtGui.QColor(
        255,
        220,
         220)
            for c in range(4):
                it = self.rec_st_tbl.item(r, c)
                if it:
                    it.setBackground(color)

        # Populate matched pairs table
        self.rec_match_tbl.setRowCount(0)
        for row in matches:
            r = self.rec_match_tbl.rowCount()
            self.rec_match_tbl.insertRow(r)
            gl_amt = (row["debit"] or 0) - (row["credit"] or 0)
            st_amt = row["st_amount"] if row["item_type"] == "Credit" else - \
                (row["st_amount"] or 0)
            self.rec_match_tbl.setItem(r, 0, _ro_c(str(row["id"])))
            self.rec_match_tbl.setItem(r, 1, _ro_c(row["journal_date"] or ""))
            self.rec_match_tbl.setItem(r, 2, _ro(row["description"] or ""))
            self.rec_match_tbl.setItem(r, 3, _ro_r(_money(gl_amt)))
            self.rec_match_tbl.setItem(r, 4, _ro_c(row["item_date"] or ""))
            self.rec_match_tbl.setItem(r, 5, _ro(row["st_desc"] or ""))
            self.rec_match_tbl.setItem(r, 6, _ro_r(_money(st_amt)))
            self.rec_match_tbl.item(
    r, 0).setData(
        QtCore.Qt.ItemDataRole.UserRole, row["id"])

        # Summary
        bank_bal = stmt["ending_balance"] or 0.0
        diff = bank_bal - book_bal
        color = "lime" if abs(diff) < 0.005 else "yellow"
        self.rec_summary.setText(
            f"Bank Account: <b>{stmt['account_name']}</b>  |  "
            f"Statement Date: <b>{stmt['statement_date']}</b>  |  "
            f"Book Balance (GL): <b>${_money(book_bal)}</b>  |  "
            f"Bank Ending Balance: <b>${_money(bank_bal)}</b>  |  "
            f"Difference: <b style='color:{color};'>${_money(diff)}</b>  |  "
            f"Matched: <b>{len(matches)}</b>  |  "
            f"Unmatched GL: <b>{len(gl_rows)}</b>  |  "
            f"Unmatched Stmt: <b>{len(st_rows)}</b>"
        )

    def _on_match_pair(self):
        gl_rows = self.rec_gl_tbl.selectionModel().selectedRows()
        st_rows = self.rec_st_tbl.selectionModel().selectedRows()
        if not gl_rows or not st_rows:
            QtWidgets.QMessageBox.warning(
                self, "Selection",
                "Select one GL transaction (left) and one bank statement item "
                "(right) to match."
            )
            return
        gl_id = self.rec_gl_tbl.item(
    gl_rows[0].row(), 0).data(
        QtCore.Qt.ItemDataRole.UserRole)
        si_id = self.rec_st_tbl.item(
    st_rows[0].row(), 0).data(
        QtCore.Qt.ItemDataRole.UserRole)
        sid = self._current_stmt_id
        with _conn() as con:
            con.execute(
                "INSERT INTO bank_reconciliation(statement_id,journal_line_id,statement_item_id) "  # noqa: E501
                "VALUES(%s,%s,%s)",
                (sid, gl_id, si_id)
            )
            con.execute(
    "UPDATE bank_statement_item SET is_matched=1 WHERE id=%s", (si_id,))
        self._refresh_reconcile_tab()

    def _on_auto_match(self):
        sid = self._current_stmt_id
        if not sid:
            QtWidgets.QMessageBox.warning(
    self, "No Statement", "Load a statement first.")
            return
        with _conn() as con:
            stmt = con.execute(
                "SELECT ba.gl_account_id FROM bank_statement bs "
                "JOIN bank_account ba ON ba.id=bs.bank_account_id WHERE "
                "bs.id=%s", (
                    sid,)
            ).fetchone()
            if not stmt or not stmt["gl_account_id"]:
                QtWidgets.QMessageBox.warning(
    self, "No GL Account", "No GL account linked to this bank account.")
                return
            gl_acct_id = stmt["gl_account_id"]
            gl_rows = con.execute("""
                SELECT l.id, j.journal_date, (l.debit - l.credit) AS net
                FROM gl_journal_line l
                JOIN gl_journal j ON j.id=l.journal_id
                WHERE l.account_id=%s
                  AND l.id NOT IN (
                      SELECT journal_line_id FROM bank_reconciliation
                      WHERE statement_id=%s AND journal_line_id IS NOT NULL
                  )
            """, (gl_acct_id, sid)).fetchall()
            st_rows = con.execute(
                "SELECT id, item_date, amount, item_type FROM "
                "bank_statement_item "
                "WHERE statement_id=%s AND is_matched=0", (sid,)
            ).fetchall()

        matched_count = 0
        used_si = set()
        for gl in gl_rows:
            gl_net = gl["net"]
            gl_date = gl["journal_date"]
            for si in st_rows:
                if si["id"] in used_si:
                    continue
                si_signed = si["amount"] if si["item_type"] == "Credit" else -si["amount"]  # noqa: E501
                if abs(si_signed - \
                       gl_net) < 0.005 and si["item_date"] == gl_date:
                    with _conn() as con:
                        con.execute(
                            "INSERT INTO bank_reconciliation(statement_id,journal_line_id,statement_item_id) "  # noqa: E501
                            "VALUES(%s,%s,%s)", (sid, gl["id"], si["id"])
                        )
                        con.execute(
    "UPDATE bank_statement_item SET is_matched=1 WHERE id=%s", (si["id"],))
                    used_si.add(si["id"])
                    matched_count += 1
                    break

        QtWidgets.QMessageBox.information(
    self, "Auto-Match", f"Matched {matched_count} pair(s).")
        self._refresh_reconcile_tab()

    def _on_unmatch(self):
        rows = self.rec_match_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(
    self, "Selection", "Select a matched pair to unmatch.")
            return
        match_id = self.rec_match_tbl.item(
    rows[0].row(), 0).data(
        QtCore.Qt.ItemDataRole.UserRole)
        with _conn() as con:
            match = con.execute(
                "SELECT statement_item_id FROM bank_reconciliation WHERE id=%s", (  # noqa: E501
                    match_id,)
            ).fetchone()
            con.execute(
    "DELETE FROM bank_reconciliation WHERE id=%s", (match_id,))
            if match and match["statement_item_id"]:
                con.execute(
                    "UPDATE bank_statement_item SET is_matched=0 WHERE id=%s",
                    (match["statement_item_id"],)
                )
        self._refresh_reconcile_tab()

    def _on_mark_reconciled(self):
        sid = self._current_stmt_id
        if not sid:
            QtWidgets.QMessageBox.warning(
    self, "No Statement", "Load a statement first.")
            return
        with _conn() as con:
            unmatched = con.execute(
                "SELECT COUNT(*) FROM bank_statement_item WHERE "
                "statement_id=%s AND is_matched=0", (sid,)
            ).fetchone()[0]
        msg = (
            f"There are {unmatched} unmatched statement item(s).\n\n"
            "Mark this statement as Reconciled anyway%s"
            if unmatched else
            "Mark this statement as Reconciled%s"
        )
        if QtWidgets.QMessageBox.question(
            self, "Mark Reconciled", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute(
                    "UPDATE bank_statement SET status='Reconciled', "
                    "reconciled_at=datetime('now') WHERE id=%s",
                    (sid,)
                )
            QtWidgets.QMessageBox.information(
    self, "Done", "Statement marked as Reconciled.")
            self._refresh_reconcile_tab()
            self._refresh_statements()

    # ── History tab ─────────────────────────────────────────────────────────
    def _build_history_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Bank Account:"))
        self.hist_ba_filter = QtWidgets.QComboBox()
        self.hist_ba_filter.setMinimumWidth(220)
        fb.addWidget(self.hist_ba_filter)
        btn_run = QtWidgets.QPushButton("Refresh")
        btn_run.setStyleSheet(BTN_STYLE)
        btn_run.clicked.connect(self._refresh_history)
        fb.addWidget(btn_run)
        fb.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BTN_STYLE)
        btn_exp.clicked.connect(lambda: _export_csv(self.hist_tbl, self))
        fb.addWidget(btn_exp)
        v.addLayout(fb)

        self.hist_tbl = QtWidgets.QTableWidget(0, 8)
        self.hist_tbl.setHorizontalHeaderLabels(
            ["ID", "Bank Account", "Statement Date", "Beg. Balance", "End "
                                                                     "Balance",
             "Status", "Matches", "Reconciled By"]
        )
        self.hist_tbl.setColumnWidth(0, 40)
        self.hist_tbl.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.hist_tbl.setColumnWidth(2, 120)
        self.hist_tbl.setColumnWidth(3, 110)
        self.hist_tbl.setColumnWidth(4, 110)
        self.hist_tbl.setColumnWidth(5, 100)
        self.hist_tbl.setColumnWidth(6, 70)
        self.hist_tbl.setColumnWidth(7, 120)
        self.hist_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hist_tbl.setAlternatingRowColors(True)
        self.hist_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.hist_tbl)
        return w

    def _populate_hist_ba_filter(self):
        self.hist_ba_filter.blockSignals(True)
        self.hist_ba_filter.clear()
        self.hist_ba_filter.addItem("All Accounts", None)
        with _conn() as con:
            rows = con.execute(
                "SELECT id, account_name FROM bank_account ORDER BY "
                "account_name"
            ).fetchall()
        for row in rows:
            self.hist_ba_filter.addItem(row["account_name"], row["id"])
        self.hist_ba_filter.blockSignals(False)

    def _refresh_history(self):
        ba_id = self.hist_ba_filter.currentData()
        q = """
            SELECT bs.id, ba.account_name, bs.statement_date,
                   bs.beginning_balance, bs.ending_balance, bs.status,
                   bs.reconciled_by,
                   (SELECT COUNT(*) FROM bank_reconciliation br WHERE
                       br.statement_id=bs.id) AS match_count
            FROM bank_statement bs
            JOIN bank_account ba ON ba.id=bs.bank_account_id
        """
        params = []
        if ba_id:
            q += " WHERE bs.bank_account_id=%s"
            params.append(ba_id)
        q += " ORDER BY bs.statement_date DESC"
        with _conn() as con:
            rows = con.execute(q, params).fetchall()
        self.hist_tbl.setRowCount(0)
        STATUS_COLORS = {
            "Open": QtGui.QColor(240, 240, 240),
            "In Progress": QtGui.QColor(200, 230, 255),
            "Reconciled": QtGui.QColor(200, 255, 210),
        }
        for row in rows:
            r = self.hist_tbl.rowCount()
            self.hist_tbl.insertRow(r)
            self.hist_tbl.setItem(r, 0, _ro_c(str(row["id"])))
            self.hist_tbl.setItem(r, 1, _ro(row["account_name"]))
            self.hist_tbl.setItem(r, 2, _ro_c(row["statement_date"]))
            self.hist_tbl.setItem(
    r, 3, _ro_r(
        _money(
            row["beginning_balance"])))
            self.hist_tbl.setItem(r, 4, _ro_r(_money(row["ending_balance"])))
            self.hist_tbl.setItem(r, 5, _ro_c(row["status"]))
            self.hist_tbl.setItem(r, 6, _ro_c(str(row["match_count"])))
            self.hist_tbl.setItem(r, 7, _ro(row["reconciled_by"] or ""))
            color = STATUS_COLORS.get(
    row["status"], QtGui.QColor(
        255, 255, 255))
            for c in range(8):
                it = self.hist_tbl.item(r, c)
                if it:
                    it.setBackground(color)

    # ── Tab change ──────────────────────────────────────────────────────────
    def _on_tab_change(self, idx):
        if idx == 1:
            self._refresh_ba_combos()
            self._refresh_statements()
        elif idx == 2:
            self._populate_rec_stmt_combo()
            if self._current_stmt_id:
                self._refresh_reconcile_tab()
        elif idx == 3:
            self._populate_hist_ba_filter()
            self._refresh_history()


class BankReconciliationWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bank Reconciliation")
        self.resize(1200, 780)
        _apply_palette(self)
        self.setCentralWidget(BankReconciliationWidget())


# ── Entry point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = BankReconciliationWindow()
    win.show()
    sys.exit(app.exec())
