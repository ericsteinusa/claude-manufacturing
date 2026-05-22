"""
Budget_mgmt.py — Budget Management module
Tabs: Budgets | Budget Detail | Budget vs. Actual | Variance Report | Department Summary
"""
import sys, os, sqlite3, csv
from datetime import date
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
        CREATE TABLE IF NOT EXISTS budget (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_name  TEXT    NOT NULL,
            fiscal_year  INTEGER NOT NULL,
            department   TEXT    DEFAULT 'All',
            description  TEXT    DEFAULT '',
            status       TEXT    DEFAULT 'Draft',   -- Draft / Approved / Active / Closed
            created_by   TEXT    DEFAULT '',
            created_at   TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS budget_line (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_id  INTEGER NOT NULL REFERENCES budget(id) ON DELETE CASCADE,
            account_id INTEGER NOT NULL REFERENCES gl_account(id),
            month      INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
            amount     REAL    DEFAULT 0.0,
            UNIQUE(budget_id, account_id, month)
        );
        """)

# ── constants ─────────────────────────────────────────────────────────────────
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
STATUSES = ["Draft", "Approved", "Active", "Closed"]
ACCT_TYPES = ["Asset","Liability","Equity","Revenue","COGS","Expense"]
DEPARTMENTS = [
    "All",
    "Accounting",
    "Customer Service",
    "Engineering",
    "Information Technology",
    "Maintenance",
    "Marketing",
    "Personnel",
    "Production",
    "Purchasing",
    "Quality Assurance",
    "Sales",
    "Budget Management",
]

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

STATUS_COLORS = {
    "Draft":    QtGui.QColor(230, 230, 230),
    "Approved": QtGui.QColor(200, 230, 255),
    "Active":   QtGui.QColor(200, 255, 210),
    "Closed":   QtGui.QColor(255, 220, 200),
}
ACCT_TYPE_COLORS = {
    "Asset":     QtGui.QColor(220, 240, 255),
    "Liability": QtGui.QColor(255, 235, 220),
    "Equity":    QtGui.QColor(220, 255, 220),
    "Revenue":   QtGui.QColor(220, 255, 235),
    "COGS":      QtGui.QColor(255, 255, 210),
    "Expense":   QtGui.QColor(255, 220, 220),
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
# Copy Budget Dialog
# ══════════════════════════════════════════════════════════════════════════════
class CopyBudgetDialog(QtWidgets.QDialog):
    def __init__(self, source_id, source_name, parent=None):
        super().__init__(parent)
        self.source_id = source_id
        self.setWindowTitle("Copy Budget")
        self.setMinimumWidth(380)
        v = QtWidgets.QVBoxLayout(self)
        v.addWidget(QtWidgets.QLabel(f"Copying: <b>{source_name}</b>"))
        fl = QtWidgets.QFormLayout()
        self.ef_name = QtWidgets.QLineEdit(f"Copy of {source_name}")
        self.ef_year = QtWidgets.QSpinBox()
        self.ef_year.setRange(2000, 2100)
        self.ef_year.setValue(date.today().year)
        fl.addRow("New Budget Name:", self.ef_name)
        fl.addRow("Fiscal Year:",     self.ef_year)
        v.addLayout(fl)
        bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def values(self):
        return self.ef_name.text().strip(), self.ef_year.value()


# ══════════════════════════════════════════════════════════════════════════════
# Main Budget Window
# ══════════════════════════════════════════════════════════════════════════════
_TAB_KEYS = {
    # Tab 0 – Budgets
    'budgets': 0, 'budg_plan': 0, 'budg_over': 0, 'budg_camp': 0,
    'eng_budg': 0, 'it_budg': 0, 'maint_budg': 0, 'prod_budg': 0,
    'purch_budg': 0, 'hw_proc': 0, 'sw_lic': 0, 'budg_req': 0,
    # Tab 1 – Budget Detail
    'bud_detail': 1, 'budg_amend': 1,
    # Tab 2 – Budget vs. Actual
    'bva': 2, 'budg_act': 2, 'cost_analy': 2, 'spend_analy': 2,
    # Tab 3 – Variance Report
    'variance': 3, 'budg_rpts': 3, 'cost_rpts': 3, 'proc_rpts': 3,
}

class BudgetWindow(QtWidgets.QMainWindow):
    def __init__(self, initial_tab=None):
        super().__init__()
        init_db()
        self.setWindowTitle("Budget Management")
        self.resize(1200, 740)
        _apply_blue_palette(self)
        self._current_budget_id = None
        self._build_ui()
        self._refresh_budgets()
        if initial_tab in _TAB_KEYS:
            self.tabs.setCurrentIndex(_TAB_KEYS[initial_tab])

    def _build_ui(self):
        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        root = QtWidgets.QVBoxLayout(cw)
        root.setContentsMargins(8, 8, 8, 8)

        title = QtWidgets.QLabel("Budget Management")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;color:white;padding:4px;")
        root.addWidget(title)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_budgets_tab(),    "Budgets")
        self.tabs.addTab(self._build_detail_tab(),    "Budget Detail")
        self.tabs.addTab(self._build_bva_tab(),       "Budget vs. Actual")
        self.tabs.addTab(self._build_variance_tab(),  "Variance Report")
        self.tabs.addTab(self._build_dept_summary_tab(), "Department Summary")

        self.tabs.currentChanged.connect(self._on_tab_change)

    # ── Budgets tab ───────────────────────────────────────────────────────────
    def _build_budgets_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        # filter bar
        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Year:"))
        self.bud_year_filter = QtWidgets.QComboBox()
        self.bud_year_filter.addItem("All Years")
        for yr in range(date.today().year + 1, date.today().year - 6, -1):
            self.bud_year_filter.addItem(str(yr))
        self.bud_year_filter.currentIndexChanged.connect(self._refresh_budgets)
        fb.addWidget(self.bud_year_filter)
        fb.addWidget(QtWidgets.QLabel("Status:"))
        self.bud_status_filter = QtWidgets.QComboBox()
        self.bud_status_filter.addItem("All Statuses")
        for s in STATUSES:
            self.bud_status_filter.addItem(s)
        self.bud_status_filter.currentIndexChanged.connect(self._refresh_budgets)
        fb.addWidget(self.bud_status_filter)
        fb.addWidget(QtWidgets.QLabel("Department:"))
        self.bud_dept_filter = QtWidgets.QComboBox()
        self.bud_dept_filter.addItem("All Departments")
        for d in DEPARTMENTS[1:]:
            self.bud_dept_filter.addItem(d)
        self.bud_dept_filter.currentIndexChanged.connect(self._refresh_budgets)
        fb.addWidget(self.bud_dept_filter)
        fb.addStretch()
        v.addLayout(fb)

        # table
        self.bud_tbl = QtWidgets.QTableWidget(0, 7)
        self.bud_tbl.setHorizontalHeaderLabels(
            ["ID", "Budget Name", "Year", "Department", "Status", "Created By", "Created"]
        )
        self.bud_tbl.setColumnWidth(0, 45)
        self.bud_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.bud_tbl.setColumnWidth(2, 55)
        self.bud_tbl.setColumnWidth(3, 120)
        self.bud_tbl.setColumnWidth(4, 80)
        self.bud_tbl.setColumnWidth(5, 110)
        self.bud_tbl.setColumnWidth(6, 140)
        self.bud_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.bud_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bud_tbl.setAlternatingRowColors(True)
        self.bud_tbl.verticalHeader().setDefaultSectionSize(24)
        self.bud_tbl.itemSelectionChanged.connect(self._on_budget_select)
        v.addWidget(self.bud_tbl)

        # form
        fg = QtWidgets.QGroupBox("Budget Details")
        fg.setStyleSheet("QGroupBox{font-weight:bold;background:white;border:1px solid #aaa;"
                         "border-radius:6px;}QGroupBox::title{padding:2px 8px;}")
        fl = QtWidgets.QFormLayout(fg)
        fl.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)

        self.bud_ef_name = QtWidgets.QLineEdit()
        self.bud_ef_year = QtWidgets.QSpinBox()
        self.bud_ef_year.setRange(2000, 2100)
        self.bud_ef_year.setValue(date.today().year)
        self.bud_ef_dept = QtWidgets.QComboBox()
        for d in DEPARTMENTS:
            self.bud_ef_dept.addItem(d)
        self.bud_ef_status = QtWidgets.QComboBox()
        for s in STATUSES:
            self.bud_ef_status.addItem(s)
        self.bud_ef_desc = QtWidgets.QLineEdit()
        self.bud_ef_by = QtWidgets.QLineEdit()

        fl.addRow("Budget Name *", self.bud_ef_name)
        fl.addRow("Fiscal Year *", self.bud_ef_year)
        fl.addRow("Department",    self.bud_ef_dept)
        fl.addRow("Status",        self.bud_ef_status)
        fl.addRow("Description",   self.bud_ef_desc)
        fl.addRow("Created By",    self.bud_ef_by)
        v.addWidget(fg)

        # buttons
        bb = QtWidgets.QHBoxLayout()
        for lbl, slot in [("Add Budget",     self._on_bud_add),
                           ("Update Budget",  self._on_bud_update),
                           ("Copy Budget",    self._on_bud_copy),
                           ("Delete Budget",  self._on_bud_delete),
                           ("Open Detail →",  self._on_open_detail),
                           ("Clear",          self._on_bud_clear)]:
            b = QtWidgets.QPushButton(lbl); b.setStyleSheet(BTN_STYLE)
            b.clicked.connect(slot)
            bb.addWidget(b)
        bb.addStretch()
        v.addLayout(bb)
        return w

    def _refresh_budgets(self):
        q = "SELECT * FROM budget"
        params = []
        where = []
        yr = self.bud_year_filter.currentText()
        if yr != "All Years":
            where.append("fiscal_year=?"); params.append(int(yr))
        st = self.bud_status_filter.currentText()
        if st != "All Statuses":
            where.append("status=?"); params.append(st)
        dept = self.bud_dept_filter.currentText()
        if dept != "All Departments":
            where.append("department=?"); params.append(dept)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY fiscal_year DESC, department, budget_name"
        with _conn() as con:
            rows = con.execute(q, params).fetchall()
        self.bud_tbl.setRowCount(0)
        for row in rows:
            r = self.bud_tbl.rowCount()
            self.bud_tbl.insertRow(r)
            self.bud_tbl.setItem(r, 0, _ro(str(row["id"]), QtCore.Qt.AlignmentFlag.AlignRight))
            self.bud_tbl.setItem(r, 1, _ro(row["budget_name"]))
            self.bud_tbl.setItem(r, 2, _ro(str(row["fiscal_year"]), QtCore.Qt.AlignmentFlag.AlignCenter))
            self.bud_tbl.setItem(r, 3, _ro(row["department"]))
            st_item = _ro(row["status"], QtCore.Qt.AlignmentFlag.AlignCenter)
            self.bud_tbl.setItem(r, 4, st_item)
            self.bud_tbl.setItem(r, 5, _ro(row["created_by"]))
            self.bud_tbl.setItem(r, 6, _ro(row["created_at"][:16] if row["created_at"] else ""))
            color = STATUS_COLORS.get(row["status"], QtGui.QColor(255, 255, 255))
            for c in range(7):
                it = self.bud_tbl.item(r, c)
                if it:
                    it.setBackground(color)
            self.bud_tbl.item(r, 0).setData(QtCore.Qt.ItemDataRole.UserRole, row["id"])

    def _on_budget_select(self):
        rows = self.bud_tbl.selectionModel().selectedRows()
        if not rows:
            return
        r = rows[0].row()
        bid = self.bud_tbl.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        self._current_budget_id = bid
        self.bud_ef_name.setText(self.bud_tbl.item(r, 1).text())
        self.bud_ef_year.setValue(int(self.bud_tbl.item(r, 2).text()))
        didx = self.bud_ef_dept.findText(self.bud_tbl.item(r, 3).text())
        if didx >= 0:
            self.bud_ef_dept.setCurrentIndex(didx)
        idx = self.bud_ef_status.findText(self.bud_tbl.item(r, 4).text())
        if idx >= 0:
            self.bud_ef_status.setCurrentIndex(idx)
        with _conn() as con:
            full = con.execute("SELECT * FROM budget WHERE id=?", (bid,)).fetchone()
        if full:
            self.bud_ef_desc.setText(full["description"] or "")
            self.bud_ef_by.setText(full["created_by"] or "")

    def _form_values(self):
        return (
            self.bud_ef_name.text().strip(),
            self.bud_ef_year.value(),
            self.bud_ef_dept.currentText(),
            self.bud_ef_status.currentText(),
            self.bud_ef_desc.text().strip(),
            self.bud_ef_by.text().strip(),
        )

    def _on_bud_add(self):
        name, yr, dept, status, desc, by = self._form_values()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Budget Name is required.")
            return
        with _conn() as con:
            con.execute(
                "INSERT INTO budget(budget_name,fiscal_year,department,status,description,created_by) "
                "VALUES(?,?,?,?,?,?)", (name, yr, dept, status, desc, by)
            )
        self._refresh_budgets()
        self._on_bud_clear()

    def _selected_budget_id(self):
        rows = self.bud_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Selection", "Select a budget first.")
            return None
        return self.bud_tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)

    def _on_bud_update(self):
        bid = self._selected_budget_id()
        if bid is None:
            return
        name, yr, dept, status, desc, by = self._form_values()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Budget Name is required.")
            return
        with _conn() as con:
            con.execute(
                "UPDATE budget SET budget_name=?,fiscal_year=?,department=?,status=?,"
                "description=?,created_by=? WHERE id=?",
                (name, yr, dept, status, desc, by, bid)
            )
        self._refresh_budgets()

    def _on_bud_copy(self):
        bid = self._selected_budget_id()
        if bid is None:
            return
        with _conn() as con:
            src = con.execute("SELECT * FROM budget WHERE id=?", (bid,)).fetchone()
        dlg = CopyBudgetDialog(bid, src["budget_name"], self)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        new_name, new_year = dlg.values()
        if not new_name:
            QtWidgets.QMessageBox.warning(self, "Validation", "New budget name is required.")
            return
        with _conn() as con:
            cur = con.execute(
                "INSERT INTO budget(budget_name,fiscal_year,department,status,description,created_by) "
                "VALUES(?,?,?,?,?,?)",
                (new_name, new_year, src["department"], "Draft", src["description"], src["created_by"])
            )
            new_id = cur.lastrowid
            # copy lines
            lines = con.execute(
                "SELECT account_id, month, amount FROM budget_line WHERE budget_id=?", (bid,)
            ).fetchall()
            con.executemany(
                "INSERT INTO budget_line(budget_id,account_id,month,amount) VALUES(?,?,?,?)",
                [(new_id, ln["account_id"], ln["month"], ln["amount"]) for ln in lines]
            )
        QtWidgets.QMessageBox.information(self, "Copied", f"Budget copied as '{new_name}'.")
        self._refresh_budgets()

    def _on_bud_delete(self):
        bid = self._selected_budget_id()
        if bid is None:
            return
        if QtWidgets.QMessageBox.question(
            self, "Delete", "Delete this budget and all its line items?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute("DELETE FROM budget WHERE id=?", (bid,))
            if self._current_budget_id == bid:
                self._current_budget_id = None
            self._refresh_budgets()

    def _on_open_detail(self):
        bid = self._selected_budget_id()
        if bid is None:
            return
        self._current_budget_id = bid
        self.tabs.setCurrentIndex(1)

    def _on_bud_clear(self):
        self.bud_ef_name.clear()
        self.bud_ef_dept.setCurrentIndex(0)
        self.bud_ef_desc.clear(); self.bud_ef_by.clear()
        self.bud_ef_year.setValue(date.today().year)
        self.bud_ef_status.setCurrentIndex(0)
        self.bud_tbl.clearSelection()
        self._current_budget_id = None

    # ── Budget Detail tab ─────────────────────────────────────────────────────
    def _build_detail_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        # selector bar
        sb = QtWidgets.QHBoxLayout()
        sb.addWidget(QtWidgets.QLabel("Budget:"))
        self.det_budget_combo = QtWidgets.QComboBox()
        self.det_budget_combo.setMinimumWidth(300)
        self.det_budget_combo.currentIndexChanged.connect(self._on_detail_budget_change)
        sb.addWidget(self.det_budget_combo)
        sb.addWidget(QtWidgets.QLabel("Show Types:"))
        self.det_type_filter = QtWidgets.QComboBox()
        self.det_type_filter.addItem("All Types")
        for t in ACCT_TYPES:
            self.det_type_filter.addItem(t)
        self.det_type_filter.currentIndexChanged.connect(self._refresh_detail)
        sb.addWidget(self.det_type_filter)
        btn_load = QtWidgets.QPushButton("Load"); btn_load.setStyleSheet(BTN_STYLE)
        btn_load.clicked.connect(self._refresh_detail)
        sb.addWidget(btn_load)
        sb.addStretch()
        btn_save_all = QtWidgets.QPushButton("💾 Save All Changes"); btn_save_all.setStyleSheet(BTN_STYLE)
        btn_save_all.clicked.connect(self._save_detail)
        sb.addWidget(btn_save_all)
        btn_exp = QtWidgets.QPushButton("Export CSV"); btn_exp.setStyleSheet(BTN_STYLE)
        btn_exp.clicked.connect(lambda: _export_table_to_csv(self.det_tbl, self))
        sb.addWidget(btn_exp)
        v.addLayout(sb)

        self.det_label = QtWidgets.QLabel("Select a budget and click Load.")
        self.det_label.setStyleSheet("color:white;font-weight:bold;padding:2px;")
        v.addWidget(self.det_label)

        # spreadsheet grid: rows = accounts, cols = Acct#, Name, Type, Jan..Dec, Total
        col_headers = ["Acct #", "Account Name", "Type"] + MONTHS + ["Annual Total"]
        self.det_tbl = QtWidgets.QTableWidget(0, len(col_headers))
        self.det_tbl.setHorizontalHeaderLabels(col_headers)
        self.det_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.det_tbl.setColumnWidth(0, 70)
        self.det_tbl.setColumnWidth(2, 80)
        for c in range(3, 15):
            self.det_tbl.setColumnWidth(c, 80)
        self.det_tbl.setColumnWidth(15, 100)
        self.det_tbl.setAlternatingRowColors(True)
        self.det_tbl.verticalHeader().setDefaultSectionSize(26)
        self.det_tbl.cellChanged.connect(self._on_detail_cell_changed)
        v.addWidget(self.det_tbl)

        self.det_totals_lbl = QtWidgets.QLabel("")
        self.det_totals_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.det_totals_lbl.setStyleSheet("font-weight:bold;font-size:13px;padding:4px 8px;color:white;")
        v.addWidget(self.det_totals_lbl)

        # quick-fill helper
        qf = QtWidgets.QHBoxLayout()
        qf.addWidget(QtWidgets.QLabel("Quick Fill — set monthly amount for selected row:"))
        self.qf_amount = QtWidgets.QDoubleSpinBox()
        self.qf_amount.setRange(0, 99_999_999); self.qf_amount.setDecimals(2)
        qf.addWidget(self.qf_amount)
        btn_fill_monthly = QtWidgets.QPushButton("Fill All 12 Months"); btn_fill_monthly.setStyleSheet(BTN_STYLE)
        btn_fill_monthly.clicked.connect(self._quick_fill_monthly)
        btn_fill_equal = QtWidgets.QPushButton("Spread Annual Total"); btn_fill_equal.setStyleSheet(BTN_STYLE)
        btn_fill_equal.clicked.connect(self._quick_fill_spread)
        qf.addWidget(btn_fill_monthly); qf.addWidget(btn_fill_equal); qf.addStretch()
        v.addLayout(qf)

        return w

    def _populate_det_budget_combo(self):
        self.det_budget_combo.blockSignals(True)
        self.det_budget_combo.clear()
        self.det_budget_combo.addItem("-- select budget --", 0)
        with _conn() as con:
            rows = con.execute(
                "SELECT id, budget_name, fiscal_year FROM budget ORDER BY fiscal_year DESC, budget_name"
            ).fetchall()
        for row in rows:
            self.det_budget_combo.addItem(f"{row['fiscal_year']} — {row['budget_name']}", row["id"])
        # restore current selection
        if self._current_budget_id:
            idx = self.det_budget_combo.findData(self._current_budget_id)
            if idx >= 0:
                self.det_budget_combo.setCurrentIndex(idx)
        self.det_budget_combo.blockSignals(False)

    def _on_detail_budget_change(self):
        self._current_budget_id = self.det_budget_combo.currentData() or None

    def _refresh_detail(self):
        bid = self.det_budget_combo.currentData()
        if not bid:
            self.det_label.setText("Select a budget and click Load.")
            return
        self._current_budget_id = bid
        with _conn() as con:
            bud = con.execute("SELECT * FROM budget WHERE id=?", (bid,)).fetchone()
            acct_filter = self.det_type_filter.currentText()
            acct_q = "SELECT id,account_number,account_name,account_type FROM gl_account WHERE is_active=1"
            if acct_filter != "All Types":
                acct_q += f" AND account_type='{acct_filter}'"
            acct_q += " ORDER BY account_number"
            accounts = con.execute(acct_q).fetchall()
            # load existing budget lines into dict
            lines = con.execute(
                "SELECT account_id, month, amount FROM budget_line WHERE budget_id=?", (bid,)
            ).fetchall()
        line_map = {}   # (account_id, month) -> amount
        for ln in lines:
            line_map[(ln["account_id"], ln["month"])] = ln["amount"]

        self.det_label.setText(
            f"  Budget: {bud['budget_name']}  |  Year: {bud['fiscal_year']}  |  "
            f"Dept: {bud['department']}  |  Status: {bud['status']}"
        )
        # block signals while filling
        self.det_tbl.blockSignals(True)
        self.det_tbl.setRowCount(0)
        for acct in accounts:
            r = self.det_tbl.rowCount()
            self.det_tbl.insertRow(r)
            self.det_tbl.setItem(r, 0, _ro(acct["account_number"]))
            self.det_tbl.setItem(r, 1, _ro(acct["account_name"]))
            self.det_tbl.setItem(r, 2, _ro(acct["account_type"]))
            # store account_id in col 0
            self.det_tbl.item(r, 0).setData(QtCore.Qt.ItemDataRole.UserRole, acct["id"])
            row_total = 0.0
            for m in range(1, 13):
                amt = line_map.get((acct["id"], m), 0.0)
                row_total += amt
                cell = QtWidgets.QTableWidgetItem(f"{amt:.2f}" if amt else "")
                cell.setTextAlignment(
                    QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
                self.det_tbl.setItem(r, 2 + m, cell)
            # total col (read-only)
            tot_item = _ro_r(_money(row_total) if row_total else "")
            tot_item.setBackground(QtGui.QColor(240, 240, 240))
            tot_item.setFont(QtGui.QFont("", -1, QtGui.QFont.Weight.Bold))
            self.det_tbl.setItem(r, 15, tot_item)
            # row color
            color = ACCT_TYPE_COLORS.get(acct["account_type"], QtGui.QColor(255, 255, 255))
            for c in [0, 1, 2]:
                it = self.det_tbl.item(r, c)
                if it:
                    it.setBackground(color)
        self.det_tbl.blockSignals(False)
        self._update_detail_totals()

    def _on_detail_cell_changed(self, row, col):
        if col < 3 or col > 14:
            return
        self._update_row_total(row)
        self._update_detail_totals()

    def _update_row_total(self, row):
        total = 0.0
        for m in range(3, 15):
            it = self.det_tbl.item(row, m)
            if it and it.text().strip():
                try:
                    total += float(it.text().replace(",", ""))
                except ValueError:
                    pass
        self.det_tbl.blockSignals(True)
        tot_item = self.det_tbl.item(row, 15)
        if tot_item:
            tot_item.setText(_money(total) if total else "")
        self.det_tbl.blockSignals(False)

    def _update_detail_totals(self):
        grand = 0.0
        for r in range(self.det_tbl.rowCount()):
            it = self.det_tbl.item(r, 15)
            if it and it.text().strip():
                try:
                    grand += float(it.text().replace(",", ""))
                except ValueError:
                    pass
        self.det_totals_lbl.setText(f"Grand Annual Total: <b>{_money(grand)}</b>")

    def _save_detail(self):
        bid = self.det_budget_combo.currentData()
        if not bid:
            QtWidgets.QMessageBox.warning(self, "No Budget", "Load a budget first.")
            return
        to_upsert = []
        for r in range(self.det_tbl.rowCount()):
            aid = self.det_tbl.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
            for m in range(1, 13):
                it = self.det_tbl.item(r, 2 + m)
                txt = it.text().strip().replace(",", "") if it else ""
                try:
                    amt = float(txt)
                except ValueError:
                    amt = 0.0
                to_upsert.append((bid, aid, m, amt, amt))
        with _conn() as con:
            con.executemany(
                "INSERT INTO budget_line(budget_id,account_id,month,amount) VALUES(?,?,?,?) "
                "ON CONFLICT(budget_id,account_id,month) DO UPDATE SET amount=?",
                to_upsert
            )
        QtWidgets.QMessageBox.information(self, "Saved", "Budget lines saved.")

    def _quick_fill_monthly(self):
        rows = self.det_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Selection", "Select a row first.")
            return
        amt = self.qf_amount.value()
        self.det_tbl.blockSignals(True)
        for idx in rows:
            r = idx.row()
            for m in range(3, 15):
                self.det_tbl.item(r, m).setText(f"{amt:.2f}" if amt else "")
            self._update_row_total(r)
        self.det_tbl.blockSignals(False)
        self._update_detail_totals()

    def _quick_fill_spread(self):
        """Spread the entered annual total evenly across 12 months."""
        rows = self.det_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Selection", "Select a row first.")
            return
        annual = self.qf_amount.value()
        monthly = round(annual / 12, 2)
        # last month gets remainder
        remainder = round(annual - monthly * 11, 2)
        self.det_tbl.blockSignals(True)
        for idx in rows:
            r = idx.row()
            for m in range(3, 14):
                self.det_tbl.item(r, m).setText(f"{monthly:.2f}" if monthly else "")
            self.det_tbl.item(r, 14).setText(f"{remainder:.2f}" if remainder else "")
            self._update_row_total(r)
        self.det_tbl.blockSignals(False)
        self._update_detail_totals()

    # ── Budget vs. Actual tab ─────────────────────────────────────────────────
    def _build_bva_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Budget:"))
        self.bva_combo = QtWidgets.QComboBox(); self.bva_combo.setMinimumWidth(280)
        fb.addWidget(self.bva_combo)
        fb.addWidget(QtWidgets.QLabel("From:"))
        self.bva_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.bva_from.setDate(QtCore.QDate(QtCore.QDate.currentDate().year(), 1, 1))
        fb.addWidget(self.bva_from)
        fb.addWidget(QtWidgets.QLabel("To:"))
        self.bva_to = QtWidgets.QDateEdit(calendarPopup=True)
        self.bva_to.setDate(QtCore.QDate.currentDate())
        fb.addWidget(self.bva_to)
        self.bva_posted = QtWidgets.QCheckBox("Posted GL Only")
        self.bva_posted.setChecked(True)
        self.bva_posted.setStyleSheet("color:white;font-weight:bold;")
        fb.addWidget(self.bva_posted)
        btn_run = QtWidgets.QPushButton("Run Report"); btn_run.setStyleSheet(BTN_STYLE)
        btn_run.clicked.connect(self._refresh_bva)
        fb.addWidget(btn_run); fb.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV"); btn_exp.setStyleSheet(BTN_STYLE)
        btn_exp.clicked.connect(lambda: _export_table_to_csv(self.bva_tbl, self))
        fb.addWidget(btn_exp)
        v.addLayout(fb)

        self.bva_tbl = QtWidgets.QTableWidget(0, 8)
        self.bva_tbl.setHorizontalHeaderLabels(
            ["Acct #", "Account Name", "Type", "Budget", "Actual", "Variance $", "Variance %", "Status"]
        )
        self.bva_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.bva_tbl.setColumnWidth(0, 70)
        self.bva_tbl.setColumnWidth(2, 90)
        self.bva_tbl.setColumnWidth(3, 110)
        self.bva_tbl.setColumnWidth(4, 110)
        self.bva_tbl.setColumnWidth(5, 110)
        self.bva_tbl.setColumnWidth(6, 90)
        self.bva_tbl.setColumnWidth(7, 90)
        self.bva_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bva_tbl.setAlternatingRowColors(True)
        self.bva_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.bva_tbl)

        self.bva_totals = QtWidgets.QLabel("")
        self.bva_totals.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.bva_totals.setStyleSheet("font-weight:bold;font-size:13px;padding:4px 8px;")
        v.addWidget(self.bva_totals)
        return w

    def _populate_bva_combo(self):
        self.bva_combo.clear()
        self.bva_combo.addItem("-- select budget --", 0)
        with _conn() as con:
            rows = con.execute(
                "SELECT id, budget_name, fiscal_year FROM budget ORDER BY fiscal_year DESC, budget_name"
            ).fetchall()
        for row in rows:
            self.bva_combo.addItem(f"{row['fiscal_year']} — {row['budget_name']}", row["id"])
        if self._current_budget_id:
            idx = self.bva_combo.findData(self._current_budget_id)
            if idx >= 0:
                self.bva_combo.setCurrentIndex(idx)

    def _refresh_bva(self):
        bid = self.bva_combo.currentData()
        if not bid:
            QtWidgets.QMessageBox.warning(self, "No Budget", "Select a budget first.")
            return
        d0 = self.bva_from.date().toString("yyyy-MM-dd")
        d1 = self.bva_to.date().toString("yyyy-MM-dd")
        # derive month range from date filter
        m0 = self.bva_from.date().month()
        m1 = self.bva_to.date().month()

        posted_clause = "AND j.posted=1" if self.bva_posted.isChecked() else ""

        # get budget amounts (sum months in range)
        with _conn() as con:
            bud_lines = con.execute(
                "SELECT bl.account_id, SUM(bl.amount) AS budgeted "
                "FROM budget_line bl "
                "WHERE bl.budget_id=? AND bl.month>=? AND bl.month<=? "
                "GROUP BY bl.account_id",
                (bid, m0, m1)
            ).fetchall()

            # get actual GL amounts
            act_sql = f"""
                SELECT l.account_id,
                       SUM(CASE WHEN a.account_type IN ('Asset','Expense','COGS')
                                THEN l.debit - l.credit
                                ELSE l.credit - l.debit END) AS actual
                FROM gl_journal_line l
                JOIN gl_journal j ON j.id=l.journal_id
                JOIN gl_account  a ON a.id=l.account_id
                WHERE j.journal_date>=? AND j.journal_date<=?
                  {posted_clause}
                GROUP BY l.account_id
            """
            actuals = con.execute(act_sql, (d0, d1)).fetchall()

            accounts = con.execute(
                "SELECT id, account_number, account_name, account_type "
                "FROM gl_account WHERE is_active=1 ORDER BY account_number"
            ).fetchall()

        bud_map = {r["account_id"]: r["budgeted"] for r in bud_lines}
        act_map = {r["account_id"]: r["actual"]   for r in actuals}

        self.bva_tbl.setRowCount(0)
        tot_bud = tot_act = 0.0
        for acct in accounts:
            aid = acct["id"]
            budgeted = bud_map.get(aid, 0.0) or 0.0
            actual   = act_map.get(aid, 0.0) or 0.0
            if budgeted == 0 and actual == 0:
                continue
            variance = actual - budgeted
            pct      = (variance / budgeted * 100) if budgeted else 0.0
            # favorable = under budget for expense/COGS, over for revenue
            if acct["account_type"] in ("Revenue",):
                favorable = actual >= budgeted
            else:
                favorable = actual <= budgeted
            status = "✓ On Budget" if abs(pct) < 5 else ("▲ Over" if variance > 0 else "▼ Under")

            r = self.bva_tbl.rowCount()
            self.bva_tbl.insertRow(r)
            self.bva_tbl.setItem(r, 0, _ro(acct["account_number"]))
            self.bva_tbl.setItem(r, 1, _ro(acct["account_name"]))
            self.bva_tbl.setItem(r, 2, _ro(acct["account_type"]))
            self.bva_tbl.setItem(r, 3, _ro_r(_money(budgeted)))
            self.bva_tbl.setItem(r, 4, _ro_r(_money(actual)))
            var_item = _ro_r(_money(abs(variance)))
            pct_item = _ro_r(f"{pct:+.1f}%" if budgeted else "N/A")
            st_item  = _ro(status, QtCore.Qt.AlignmentFlag.AlignCenter)

            var_color = QtGui.QColor("green") if favorable else QtGui.QColor("red")
            for it in [var_item, pct_item, st_item]:
                it.setForeground(var_color)
            self.bva_tbl.setItem(r, 5, var_item)
            self.bva_tbl.setItem(r, 6, pct_item)
            self.bva_tbl.setItem(r, 7, st_item)

            bg = ACCT_TYPE_COLORS.get(acct["account_type"], QtGui.QColor(255, 255, 255))
            for c in range(8):
                it = self.bva_tbl.item(r, c)
                if it:
                    it.setBackground(bg)
            tot_bud += budgeted; tot_act += actual

        grand_var = tot_act - tot_bud
        self.bva_totals.setText(
            f"Total Budget: <b>{_money(tot_bud)}</b>   "
            f"Total Actual: <b>{_money(tot_act)}</b>   "
            f"<span style='color:{'green' if grand_var <= 0 else 'red'};'>"
            f"Net Variance: <b>{_money(grand_var):}</b></span>"
        )

    # ── Variance Report tab ───────────────────────────────────────────────────
    def _build_variance_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Budget:"))
        self.var_combo = QtWidgets.QComboBox(); self.var_combo.setMinimumWidth(280)
        fb.addWidget(self.var_combo)
        fb.addWidget(QtWidgets.QLabel("Period:"))
        self.var_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.var_from.setDate(QtCore.QDate(QtCore.QDate.currentDate().year(), 1, 1))
        fb.addWidget(self.var_from)
        fb.addWidget(QtWidgets.QLabel("to"))
        self.var_to = QtWidgets.QDateEdit(calendarPopup=True)
        self.var_to.setDate(QtCore.QDate.currentDate())
        fb.addWidget(self.var_to)
        fb.addWidget(QtWidgets.QLabel("Threshold %:"))
        self.var_threshold = QtWidgets.QSpinBox()
        self.var_threshold.setRange(0, 100); self.var_threshold.setValue(10)
        self.var_threshold.setSuffix("%")
        fb.addWidget(self.var_threshold)
        self.var_posted = QtWidgets.QCheckBox("Posted GL Only")
        self.var_posted.setChecked(True)
        self.var_posted.setStyleSheet("color:white;font-weight:bold;")
        fb.addWidget(self.var_posted)
        btn_run = QtWidgets.QPushButton("Run Variance"); btn_run.setStyleSheet(BTN_STYLE)
        btn_run.clicked.connect(self._refresh_variance)
        fb.addWidget(btn_run); fb.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV"); btn_exp.setStyleSheet(BTN_STYLE)
        btn_exp.clicked.connect(lambda: _export_table_to_csv(self.var_tbl, self))
        fb.addWidget(btn_exp)
        v.addLayout(fb)

        # summary cards row
        self.var_cards = QtWidgets.QHBoxLayout()
        self.card_over   = self._make_card("Over Budget",  "#ffcccc")
        self.card_under  = self._make_card("Under Budget", "#ccffcc")
        self.card_ok     = self._make_card("On Target",    "#cce0ff")
        self.card_noact  = self._make_card("No Activity",  "#eeeeee")
        for card in [self.card_over, self.card_under, self.card_ok, self.card_noact]:
            self.var_cards.addWidget(card)
        v.addLayout(self.var_cards)

        self.var_tbl = QtWidgets.QTableWidget(0, 7)
        self.var_tbl.setHorizontalHeaderLabels(
            ["Acct #", "Account Name", "Type", "Budget", "Actual", "Variance $", "Variance %"]
        )
        self.var_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.var_tbl.setColumnWidth(0, 70)
        self.var_tbl.setColumnWidth(2, 90)
        self.var_tbl.setColumnWidth(3, 110)
        self.var_tbl.setColumnWidth(4, 110)
        self.var_tbl.setColumnWidth(5, 110)
        self.var_tbl.setColumnWidth(6, 100)
        self.var_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.var_tbl.setAlternatingRowColors(True)
        self.var_tbl.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self.var_tbl)
        return w

    def _make_card(self, label, bg):
        card = QtWidgets.QFrame()
        card.setStyleSheet(f"background:{bg};border-radius:8px;border:1px solid #aaa;")
        card.setMinimumHeight(70)
        cl = QtWidgets.QVBoxLayout(card)
        lbl = QtWidgets.QLabel(label)
        lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-weight:bold;font-size:12px;")
        val = QtWidgets.QLabel("—")
        val.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet("font-size:20px;font-weight:bold;")
        cl.addWidget(lbl); cl.addWidget(val)
        card._value_label = val
        return card

    def _populate_var_combo(self):
        self.var_combo.clear()
        self.var_combo.addItem("-- select budget --", 0)
        with _conn() as con:
            rows = con.execute(
                "SELECT id, budget_name, fiscal_year FROM budget ORDER BY fiscal_year DESC, budget_name"
            ).fetchall()
        for row in rows:
            self.var_combo.addItem(f"{row['fiscal_year']} — {row['budget_name']}", row["id"])
        if self._current_budget_id:
            idx = self.var_combo.findData(self._current_budget_id)
            if idx >= 0:
                self.var_combo.setCurrentIndex(idx)

    def _refresh_variance(self):
        bid = self.var_combo.currentData()
        if not bid:
            QtWidgets.QMessageBox.warning(self, "No Budget", "Select a budget first.")
            return
        d0 = self.var_from.date().toString("yyyy-MM-dd")
        d1 = self.var_to.date().toString("yyyy-MM-dd")
        m0 = self.var_from.date().month()
        m1 = self.var_to.date().month()
        threshold = self.var_threshold.value()
        posted_clause = "AND j.posted=1" if self.var_posted.isChecked() else ""

        with _conn() as con:
            bud_lines = con.execute(
                "SELECT bl.account_id, SUM(bl.amount) AS budgeted "
                "FROM budget_line bl WHERE bl.budget_id=? AND bl.month>=? AND bl.month<=? "
                "GROUP BY bl.account_id", (bid, m0, m1)
            ).fetchall()
            act_sql = f"""
                SELECT l.account_id,
                       SUM(CASE WHEN a.account_type IN ('Asset','Expense','COGS')
                                THEN l.debit - l.credit
                                ELSE l.credit - l.debit END) AS actual
                FROM gl_journal_line l
                JOIN gl_journal j ON j.id=l.journal_id
                JOIN gl_account  a ON a.id=l.account_id
                WHERE j.journal_date>=? AND j.journal_date<=?
                  {posted_clause}
                GROUP BY l.account_id
            """
            actuals = con.execute(act_sql, (d0, d1)).fetchall()
            accounts = con.execute(
                "SELECT id, account_number, account_name, account_type "
                "FROM gl_account WHERE is_active=1 ORDER BY account_number"
            ).fetchall()

        bud_map = {r["account_id"]: r["budgeted"] for r in bud_lines}
        act_map = {r["account_id"]: r["actual"]   for r in actuals}

        self.var_tbl.setRowCount(0)
        cnt_over = cnt_under = cnt_ok = cnt_noact = 0

        for acct in accounts:
            aid = acct["id"]
            budgeted = bud_map.get(aid, 0.0) or 0.0
            actual   = act_map.get(aid, 0.0) or 0.0
            if budgeted == 0 and actual == 0:
                continue
            variance = actual - budgeted
            pct      = (variance / budgeted * 100) if budgeted else 0.0
            is_revenue = acct["account_type"] in ("Revenue",)

            if actual == 0 and budgeted > 0:
                cnt_noact += 1
                row_color = QtGui.QColor(230, 230, 230)
            elif abs(pct) <= threshold:
                cnt_ok += 1
                row_color = QtGui.QColor(200, 255, 210)
            elif (variance > 0 and not is_revenue) or (variance < 0 and is_revenue):
                cnt_over += 1
                row_color = QtGui.QColor(255, 200, 200)
            else:
                cnt_under += 1
                row_color = QtGui.QColor(255, 255, 190)

            r = self.var_tbl.rowCount()
            self.var_tbl.insertRow(r)
            self.var_tbl.setItem(r, 0, _ro(acct["account_number"]))
            self.var_tbl.setItem(r, 1, _ro(acct["account_name"]))
            self.var_tbl.setItem(r, 2, _ro(acct["account_type"]))
            self.var_tbl.setItem(r, 3, _ro_r(_money(budgeted)))
            self.var_tbl.setItem(r, 4, _ro_r(_money(actual)))
            self.var_tbl.setItem(r, 5, _ro_r(f"{'-' if variance < 0 else ''}{_money(abs(variance))}"))
            self.var_tbl.setItem(r, 6, _ro_r(f"{pct:+.1f}%" if budgeted else "N/A"))
            for c in range(7):
                it = self.var_tbl.item(r, c)
                if it:
                    it.setBackground(row_color)

        # update summary cards
        self.card_over._value_label.setText(str(cnt_over))
        self.card_under._value_label.setText(str(cnt_under))
        self.card_ok._value_label.setText(str(cnt_ok))
        self.card_noact._value_label.setText(str(cnt_noact))

    # ── tab change ────────────────────────────────────────────────────────────
    def _on_tab_change(self, idx):
        if idx == 1:
            self._populate_det_budget_combo()
        elif idx == 2:
            self._populate_bva_combo()
        elif idx == 3:
            self._populate_var_combo()
        elif idx == 4:
            self._refresh_dept_summary()


    # ── Department Summary tab ────────────────────────────────────────────────
    def _build_dept_summary_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Fiscal Year:"))
        self.ds_year = QtWidgets.QComboBox()
        self.ds_year.addItem("All Years")
        for yr in range(date.today().year + 1, date.today().year - 6, -1):
            self.ds_year.addItem(str(yr))
        self.ds_year.setCurrentText(str(date.today().year))
        fb.addWidget(self.ds_year)
        fb.addWidget(QtWidgets.QLabel("Status:"))
        self.ds_status = QtWidgets.QComboBox()
        self.ds_status.addItem("All Statuses")
        for s in STATUSES:
            self.ds_status.addItem(s)
        fb.addWidget(self.ds_status)
        btn_run = QtWidgets.QPushButton("Refresh"); btn_run.setStyleSheet(BTN_STYLE)
        btn_run.clicked.connect(self._refresh_dept_summary)
        fb.addWidget(btn_run); fb.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV"); btn_exp.setStyleSheet(BTN_STYLE)
        btn_exp.clicked.connect(lambda: _export_table_to_csv(self.ds_tbl, self))
        fb.addWidget(btn_exp)
        v.addLayout(fb)

        self.ds_tbl = QtWidgets.QTableWidget(0, 5)
        self.ds_tbl.setHorizontalHeaderLabels(
            ["Department", "Budgets", "Active", "Total Budgeted", "Avg per Budget"]
        )
        self.ds_tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ds_tbl.setColumnWidth(1, 80)
        self.ds_tbl.setColumnWidth(2, 80)
        self.ds_tbl.setColumnWidth(3, 130)
        self.ds_tbl.setColumnWidth(4, 130)
        self.ds_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ds_tbl.setAlternatingRowColors(True)
        self.ds_tbl.verticalHeader().setDefaultSectionSize(28)
        self.ds_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ds_tbl.itemSelectionChanged.connect(self._on_ds_select)
        v.addWidget(self.ds_tbl)

        self.ds_totals = QtWidgets.QLabel("")
        self.ds_totals.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.ds_totals.setStyleSheet("font-weight:bold;font-size:13px;padding:4px 8px;color:white;")
        v.addWidget(self.ds_totals)

        lbl = QtWidgets.QLabel("Select a department row to filter the Budgets tab to that department.")
        lbl.setStyleSheet("color:white;font-size:11px;padding:2px 4px;")
        v.addWidget(lbl)
        return w

    def _refresh_dept_summary(self):
        yr = self.ds_year.currentText()
        st = self.ds_status.currentText()

        q = "SELECT department, status, COUNT(*) as cnt, SUM(total) as total FROM (" \
            "SELECT b.department, b.status, COALESCE(SUM(bl.amount),0) as total " \
            "FROM budget b LEFT JOIN budget_line bl ON bl.budget_id=b.id"
        params = []
        where = []
        if yr != "All Years":
            where.append("b.fiscal_year=?"); params.append(int(yr))
        if st != "All Statuses":
            where.append("b.status=?"); params.append(st)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " GROUP BY b.id, b.department, b.status) GROUP BY department, status ORDER BY department, status"

        with _conn() as con:
            rows = con.execute(q, params).fetchall()

        # aggregate by department
        dept_map: dict = {}
        for row in rows:
            d = row["department"] or "All"
            if d not in dept_map:
                dept_map[d] = {"budgets": 0, "active": 0, "total": 0.0}
            dept_map[d]["budgets"] += row["cnt"]
            if row["status"] == "Active":
                dept_map[d]["active"] += row["cnt"]
            dept_map[d]["total"] += row["total"] or 0.0

        DEPT_COLORS = {
            "Accounting":           QtGui.QColor(220, 240, 255),
            "Customer Service":     QtGui.QColor(220, 255, 235),
            "Engineering":          QtGui.QColor(255, 245, 220),
            "Information Technology": QtGui.QColor(240, 220, 255),
            "Maintenance":          QtGui.QColor(255, 235, 220),
            "Marketing":            QtGui.QColor(220, 255, 255),
            "Personnel":            QtGui.QColor(255, 220, 240),
            "Production":           QtGui.QColor(230, 255, 220),
            "Purchasing":           QtGui.QColor(255, 255, 220),
            "Quality Assurance":    QtGui.QColor(220, 230, 255),
            "Sales":                QtGui.QColor(255, 240, 220),
            "Budget Management":    QtGui.QColor(200, 230, 255),
        }

        self.ds_tbl.setRowCount(0)
        grand_total = 0.0
        for dept in sorted(dept_map.keys()):
            info = dept_map[dept]
            r = self.ds_tbl.rowCount()
            self.ds_tbl.insertRow(r)
            self.ds_tbl.setItem(r, 0, _ro(dept))
            self.ds_tbl.setItem(r, 1, _ro(str(info["budgets"]), QtCore.Qt.AlignmentFlag.AlignCenter))
            self.ds_tbl.setItem(r, 2, _ro(str(info["active"]), QtCore.Qt.AlignmentFlag.AlignCenter))
            self.ds_tbl.setItem(r, 3, _ro_r(_money(info["total"])))
            avg = info["total"] / info["budgets"] if info["budgets"] else 0.0
            self.ds_tbl.setItem(r, 4, _ro_r(_money(avg)))
            color = DEPT_COLORS.get(dept, QtGui.QColor(245, 245, 245))
            for c in range(5):
                it = self.ds_tbl.item(r, c)
                if it:
                    it.setBackground(color)
            grand_total += info["total"]

        total_budgets = sum(v["budgets"] for v in dept_map.values())
        self.ds_totals.setText(
            f"Departments: <b>{len(dept_map)}</b>   "
            f"Total Budgets: <b>{total_budgets}</b>   "
            f"Grand Total Budgeted: <b>{_money(grand_total)}</b>"
        )

    def _on_ds_select(self):
        rows = self.ds_tbl.selectionModel().selectedRows()
        if not rows:
            return
        dept = self.ds_tbl.item(rows[0].row(), 0).text()
        idx = self.bud_dept_filter.findText(dept)
        if idx >= 0:
            self.bud_dept_filter.setCurrentIndex(idx)
        self.tabs.setCurrentIndex(0)


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = BudgetWindow(sys.argv[1] if len(sys.argv) > 1 else None)
    win.show()
    sys.exit(app.exec())
