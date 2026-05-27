"""
Payroll_dept.py — Payroll Department
Tabs: Pay Rates | Deductions & Benefits | Run Payroll | Pay Stubs | YTD Report | Payroll History
"""
import sys
import psycopg2
from db_pg import get_db
import os
import csv
from datetime import datetime
from PyQt6 import QtCore, QtGui, QtWidgets
SS_RATE      = 0.062
MEDICARE_RATE = 0.0145
DT_FMT = "%Y-%m-%d %H:%M:%S"

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE = (
    "QLineEdit{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 6px;}"
)
COMBO_STYLE = (
    "QComboBox{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 6px;}"
    "QComboBox QAbstractItemView{background-color: white;}"
)
DATE_STYLE = (
    "QDateEdit{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 4px;}"
)
SPIN_STYLE = (
    "QDoubleSpinBox{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 4px;}"
)
LABEL_STYLE = "color: white; font-size: 13px;"
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white; border:2px solid black; padding:6px 18px;"
    " border-bottom:none; border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255); font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)
GRP_STYLE = (
    "QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:8px;}"
    "QGroupBox::title{subcontrol-origin:margin;left:10px;}"
)

FREQ_DIVISORS = {"Weekly": 52, "Bi-Weekly": 26, "Semi-Monthly": 24, "Monthly": 12}
DED_CATEGORIES = ["Benefits", "Retirement", "Garnishment", "Other"]


# ── DB ─────────────────────────────────────────────────────────────────────────


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS employee_pay (
            id             SERIAL PRIMARY KEY,
            people_id      INTEGER NOT NULL UNIQUE REFERENCES people(id),
            pay_type       TEXT    NOT NULL DEFAULT 'hourly',
            pay_rate       REAL    NOT NULL DEFAULT 0.0,
            effective_date TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payroll_run (
            id               SERIAL PRIMARY KEY,
            period_start     TEXT NOT NULL,
            period_end       TEXT NOT NULL,
            run_date         TEXT NOT NULL,
            pay_frequency    TEXT NOT NULL,
            federal_tax_rate REAL NOT NULL,
            state_tax_rate   REAL NOT NULL,
            status           TEXT NOT NULL DEFAULT 'processed'
        );

        CREATE TABLE IF NOT EXISTS payroll_entry (
            id                  SERIAL PRIMARY KEY,
            run_id              INTEGER NOT NULL REFERENCES payroll_run(id),
            people_id           INTEGER NOT NULL REFERENCES people(id),
            regular_hours       REAL NOT NULL DEFAULT 0.0,
            overtime_hours      REAL NOT NULL DEFAULT 0.0,
            gross_pay           REAL NOT NULL DEFAULT 0.0,
            federal_tax         REAL NOT NULL DEFAULT 0.0,
            state_tax           REAL NOT NULL DEFAULT 0.0,
            social_security     REAL NOT NULL DEFAULT 0.0,
            medicare            REAL NOT NULL DEFAULT 0.0,
            net_pay             REAL NOT NULL DEFAULT 0.0,
            pre_tax_deductions  REAL NOT NULL DEFAULT 0.0,
            post_tax_deductions REAL NOT NULL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS payroll_deduction_type (
            id         SERIAL PRIMARY KEY,
            name       TEXT    NOT NULL,
            category   TEXT    DEFAULT 'Other',
            is_pre_tax INTEGER DEFAULT 1,
            is_active  INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS employee_deduction (
            id                SERIAL PRIMARY KEY,
            people_id         INTEGER NOT NULL REFERENCES people(id),
            deduction_type_id INTEGER NOT NULL REFERENCES payroll_deduction_type(id),
            calc_method       TEXT    DEFAULT 'flat',
            amount            REAL    DEFAULT 0.0,
            is_active         INTEGER DEFAULT 1,
            effective_date    TEXT    DEFAULT (date('now')),
            end_date          TEXT    DEFAULT NULL,
            notes             TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS payroll_entry_deduction (
            id             SERIAL PRIMARY KEY,
            entry_id       INTEGER NOT NULL REFERENCES payroll_entry(id) ON DELETE CASCADE,
            deduction_name TEXT    NOT NULL,
            is_pre_tax     INTEGER DEFAULT 1,
            amount         REAL    NOT NULL DEFAULT 0.0
        );
    """)
    # Add columns to payroll_entry for existing databases that predate this version
    for col, defn in [
        ("pre_tax_deductions", "REAL NOT NULL DEFAULT 0.0"),
        ("post_tax_deductions", "REAL NOT NULL DEFAULT 0.0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE payroll_entry ADD COLUMN {col} {defn}")
        except Exception:
            pass
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


# ── Pay calculation ─────────────────────────────────────────────────────────────

def _hours_from_timeclock(people_id, start_str, end_str):
    conn = get_db()
    rows = conn.execute("""
        SELECT clock_in, clock_out FROM time_clock
        WHERE people_id=%s AND clock_in>=%s AND clock_in<=%s
          AND clock_out IS NOT NULL
    """, (people_id, start_str + " 00:00:00", end_str + " 23:59:59")).fetchall()
    conn.close()
    weekly: dict = {}
    for row in rows:
        try:
            t_in = datetime.strptime(row["clock_in"], DT_FMT)
            t_out = datetime.strptime(row["clock_out"], DT_FMT)
            hrs = max(0.0, (t_out - t_in).total_seconds() / 3600)
            week = t_in.isocalendar()[:2]
            weekly[week] = weekly.get(week, 0.0) + hrs
        except ValueError:
            pass
    reg = ot = 0.0
    for wk_hrs in weekly.values():
        if wk_hrs > 40:
            reg += 40.0
            ot += wk_hrs - 40.0
        else:
            reg += wk_hrs
    return round(reg, 2), round(ot, 2)


def _calc_pay(pay_type, pay_rate, reg_hrs, ot_hrs, fed_rate, state_rate, pay_freq,
              pre_tax_deds=0.0, post_tax_deds=0.0):
    """Return (gross, fed_tax, state_tax, ss, medicare, net)."""
    if pay_type == "hourly":
        gross = pay_rate * reg_hrs + pay_rate * 1.5 * ot_hrs
    else:
        gross = pay_rate / FREQ_DIVISORS.get(pay_freq, 26)
    taxable = max(0.0, gross - pre_tax_deds)
    fed = taxable * fed_rate
    state = taxable * state_rate
    ss = taxable * SS_RATE
    med = taxable * MEDICARE_RATE
    net = max(0.0, taxable - fed - state - ss - med - post_tax_deds)
    return gross, fed, state, ss, med, net


def _money(v): return f"${v:,.2f}"
def _pct(v): return f"{v * 100:.1f}%"


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter):
    item = QtWidgets.QTableWidgetItem(text)
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(align)
    return item


def _rw(text):
    item = QtWidgets.QTableWidgetItem(text)
    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return item


def _lbl(text, style=LABEL_STYLE):
    lbl = QtWidgets.QLabel(text)
    lbl.setStyleSheet(style)
    return lbl


def _export_csv(table: QtWidgets.QTableWidget, parent):
    path, _ = QtWidgets.QFileDialog.getSaveFileName(parent, "Export CSV", "", "CSV Files (*.csv)")
    if not path:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([table.horizontalHeaderItem(c).text() for c in range(table.columnCount())])
        for r in range(table.rowCount()):
            w.writerow([table.item(r, c).text() if table.item(r, c) else "" for c in range(table.columnCount())])
    QtWidgets.QMessageBox.information(parent, "Export", f"Saved to:\n{path}")


# ── Main window ─────────────────────────────────────────────────────────────────

_TAB_KEYS = {'pay': 0, 'payroll': 2, 'deductions': 1, 'paystub': 3, 'ytd': 4, 'history': 5}


class PayrollDeptWidget(QtWidgets.QWidget):

    # Column indices for the run-payroll table
    _C_EMP = 0
    _C_TYPE = 1
    _C_RATE = 2
    _C_REG = 3
    _C_OT = 4
    _C_DEDS = 5
    _C_GROSS = 6
    _C_FED = 7
    _C_ST = 8
    _C_SS = 9
    _C_MED = 10
    _C_NET = 11

    def __init__(self, parent=None, initial_tab=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._pay_rate_row_ids = []
        self._run_people_ids = []
        self._run_deductions = {}
        self._history_run_ids = []
        import personnel_crm as _pcrm; _pcrm.init_db()
        init_db()
        self._build_ui()
        self._load_pay_rates()
        self._load_history()
        if initial_tab in _TAB_KEYS:
            self.tabs.setCurrentIndex(_TAB_KEYS[initial_tab])

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        outer.addWidget(self.tabs)
        self.tabs.addTab(self._build_pay_rates_tab(), "Pay Rates")
        self.tabs.addTab(self._build_deductions_tab(), "Deductions & Benefits")
        self.tabs.addTab(self._build_run_payroll_tab(), "Run Payroll")
        self.tabs.addTab(self._build_paystubs_tab(), "Pay Stubs")
        self.tabs.addTab(self._build_ytd_tab(), "YTD Report")
        self.tabs.addTab(self._build_history_tab(), "Payroll History")
        self.tabs.currentChanged.connect(self._on_tab_change)

    # ── Pay Rates tab ────────────────────────────────────────────────────────

    def _build_pay_rates_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.pr_table = QtWidgets.QTableWidget()
        self.pr_table.setColumnCount(5)
        self.pr_table.setHorizontalHeaderLabels(
            ["Employee", "Emp ID", "Pay Type", "Pay Rate", "Effective Date"])
        hh = self.pr_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.pr_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pr_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.pr_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.pr_table.setAlternatingRowColors(True)
        self.pr_table.verticalHeader().setVisible(False)
        self.pr_table.clicked.connect(self._on_pr_row_clicked)
        layout.addWidget(self.pr_table, stretch=1)

        form_grp = QtWidgets.QGroupBox("Employee Pay Setup")
        form_grp.setStyleSheet(GRP_STYLE)
        fg = QtWidgets.QGridLayout(form_grp)
        fg.setSpacing(8)

        self.pr_emp_combo = QtWidgets.QComboBox()
        self.pr_emp_combo.setStyleSheet(COMBO_STYLE)
        self.pr_emp_combo.setMinimumWidth(220)

        self.pr_type_combo = QtWidgets.QComboBox()
        self.pr_type_combo.setStyleSheet(COMBO_STYLE)
        self.pr_type_combo.addItems(["hourly", "salary"])
        self.pr_type_combo.currentTextChanged.connect(self._on_pr_type_changed)

        self.pr_rate_spin = QtWidgets.QDoubleSpinBox()
        self.pr_rate_spin.setStyleSheet(SPIN_STYLE)
        self.pr_rate_spin.setRange(0, 9_999_999)
        self.pr_rate_spin.setDecimals(2)
        self.pr_rate_spin.setPrefix("$ ")

        self.pr_date_edit = QtWidgets.QDateEdit()
        self.pr_date_edit.setStyleSheet(DATE_STYLE)
        self.pr_date_edit.setCalendarPopup(True)
        self.pr_date_edit.setDate(QtCore.QDate.currentDate())
        self.pr_date_edit.setDisplayFormat("MM/dd/yyyy")

        self.pr_rate_lbl = QtWidgets.QLabel("Rate ($/hr):")
        self.pr_rate_lbl.setStyleSheet(LABEL_STYLE)

        fg.addWidget(_lbl("Employee:"), 0, 0)
        fg.addWidget(self.pr_emp_combo, 0, 1)
        fg.addWidget(_lbl("Pay Type:"), 0, 2)
        fg.addWidget(self.pr_type_combo, 0, 3)
        fg.addWidget(self.pr_rate_lbl, 0, 4)
        fg.addWidget(self.pr_rate_spin, 0, 5)
        fg.addWidget(_lbl("Effective Date:"), 0, 6)
        fg.addWidget(self.pr_date_edit, 0, 7)
        layout.addWidget(form_grp)

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Save / Update", self._on_pr_save),
                           ("Delete Rate", self._on_pr_delete),
                           ("Clear", self._pr_clear_form)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(34)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    def _on_pr_type_changed(self, t):
        self.pr_rate_lbl.setText("Rate ($/hr):" if t == "hourly" else "Annual Salary ($):")

    # ── Deductions & Benefits tab ────────────────────────────────────────────

    def _build_deductions_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # ── Left: Deduction Types ──
        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 6, 0)

        lv.addWidget(_lbl("Deduction Types (Company-Wide)"))

        self.ded_type_tbl = QtWidgets.QTableWidget(0, 4)
        self.ded_type_tbl.setHorizontalHeaderLabels(["ID", "Name", "Category", "Pre-Tax"])
        self.ded_type_tbl.horizontalHeader().setStyleSheet("color: black; font-weight: bold;")
        self.ded_type_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ded_type_tbl.setColumnWidth(0, 40)
        self.ded_type_tbl.setColumnWidth(2, 100)
        self.ded_type_tbl.setColumnWidth(3, 65)
        self.ded_type_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ded_type_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ded_type_tbl.setAlternatingRowColors(True)
        self.ded_type_tbl.verticalHeader().setVisible(False)
        self.ded_type_tbl.itemSelectionChanged.connect(self._on_ded_type_select)
        lv.addWidget(self.ded_type_tbl, stretch=1)

        type_fg = QtWidgets.QGroupBox("Deduction Type Details")
        type_fg.setStyleSheet(GRP_STYLE)
        type_fl = QtWidgets.QFormLayout(type_fg)
        self.dt_ef_name = QtWidgets.QLineEdit()
        self.dt_ef_name.setStyleSheet(INPUT_STYLE)
        self.dt_ef_cat = QtWidgets.QComboBox()
        self.dt_ef_cat.setStyleSheet(COMBO_STYLE)
        for c in DED_CATEGORIES:
            self.dt_ef_cat.addItem(c)
        self.dt_ef_pretax = QtWidgets.QCheckBox("Pre-Tax Deduction")
        self.dt_ef_pretax.setChecked(True)
        self.dt_ef_pretax.setStyleSheet("color:white;")
        type_fl.addRow(_lbl("Name *:"), self.dt_ef_name)
        type_fl.addRow(_lbl("Category:"), self.dt_ef_cat)
        type_fl.addRow("", self.dt_ef_pretax)
        lv.addWidget(type_fg)

        type_btns = QtWidgets.QHBoxLayout()
        for txt, slot in [("Add Type", self._on_dt_add),
                          ("Update Type", self._on_dt_update),
                          ("Delete Type", self._on_dt_delete),
                          ("Clear", self._on_dt_clear)]:
            b = QtWidgets.QPushButton(txt)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(slot)
            type_btns.addWidget(b)
        type_btns.addStretch()
        lv.addLayout(type_btns)
        splitter.addWidget(left)

        # ── Right: Employee Deductions ──
        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(6, 0, 0, 0)

        rv.addWidget(_lbl("Employee Deduction Assignments"))

        ed_filter_row = QtWidgets.QHBoxLayout()
        ed_filter_row.addWidget(_lbl("Filter by Employee:"))
        self.ed_emp_filter = QtWidgets.QComboBox()
        self.ed_emp_filter.setStyleSheet(COMBO_STYLE)
        self.ed_emp_filter.setMinimumWidth(200)
        self.ed_emp_filter.currentIndexChanged.connect(self._refresh_emp_deductions)
        ed_filter_row.addWidget(self.ed_emp_filter)
        ed_filter_row.addStretch()
        rv.addLayout(ed_filter_row)

        self.ed_tbl = QtWidgets.QTableWidget(0, 7)
        self.ed_tbl.setHorizontalHeaderLabels(
            ["ID", "Employee", "Deduction", "Method", "Amount", "Pre-Tax", "Active"])
        self.ed_tbl.horizontalHeader().setStyleSheet("color: black; font-weight: bold;")
        self.ed_tbl.setColumnWidth(0, 40)
        self.ed_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ed_tbl.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ed_tbl.setColumnWidth(3, 65)
        self.ed_tbl.setColumnWidth(4, 90)
        self.ed_tbl.setColumnWidth(5, 65)
        self.ed_tbl.setColumnWidth(6, 55)
        self.ed_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ed_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ed_tbl.setAlternatingRowColors(True)
        self.ed_tbl.verticalHeader().setVisible(False)
        self.ed_tbl.itemSelectionChanged.connect(self._on_ed_select)
        rv.addWidget(self.ed_tbl, stretch=1)

        ed_fg = QtWidgets.QGroupBox("Assign Deduction to Employee")
        ed_fg.setStyleSheet(GRP_STYLE)
        ed_fl = QtWidgets.QFormLayout(ed_fg)
        self.ed_ef_emp = QtWidgets.QComboBox()
        self.ed_ef_emp.setStyleSheet(COMBO_STYLE)
        self.ed_ef_type = QtWidgets.QComboBox()
        self.ed_ef_type.setStyleSheet(COMBO_STYLE)
        self.ed_ef_method = QtWidgets.QComboBox()
        self.ed_ef_method.setStyleSheet(COMBO_STYLE)
        self.ed_ef_method.addItems(["flat", "percent"])
        self.ed_ef_method.currentTextChanged.connect(self._on_ed_method_changed)
        self.ed_ef_amount = QtWidgets.QDoubleSpinBox()
        self.ed_ef_amount.setStyleSheet(SPIN_STYLE)
        self.ed_ef_amount.setRange(0, 99_999)
        self.ed_ef_amount.setDecimals(2)
        self.ed_ef_amount.setPrefix("$ ")
        self.ed_ef_active = QtWidgets.QCheckBox("Active")
        self.ed_ef_active.setChecked(True)
        self.ed_ef_active.setStyleSheet("color:white;")
        self.ed_ef_notes = QtWidgets.QLineEdit()
        self.ed_ef_notes.setStyleSheet(INPUT_STYLE)
        ed_fl.addRow(_lbl("Employee *:"), self.ed_ef_emp)
        ed_fl.addRow(_lbl("Deduction *:"), self.ed_ef_type)
        ed_fl.addRow(_lbl("Method:"), self.ed_ef_method)
        self.ed_amount_lbl = _lbl("Amount ($):")
        ed_fl.addRow(self.ed_amount_lbl, self.ed_ef_amount)
        ed_fl.addRow("", self.ed_ef_active)
        ed_fl.addRow(_lbl("Notes:"), self.ed_ef_notes)
        rv.addWidget(ed_fg)

        ed_btns = QtWidgets.QHBoxLayout()
        for txt, slot in [("Assign Deduction", self._on_ed_add),
                          ("Update", self._on_ed_update),
                          ("Remove", self._on_ed_delete),
                          ("Clear", self._on_ed_clear)]:
            b = QtWidgets.QPushButton(txt)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(slot)
            ed_btns.addWidget(b)
        ed_btns.addStretch()
        rv.addLayout(ed_btns)
        splitter.addWidget(right)

        splitter.setSizes([420, 700])
        v.addWidget(splitter)
        return w

    def _on_ed_method_changed(self, m):
        if m == "percent":
            self.ed_ef_amount.setPrefix("  ")
            self.ed_ef_amount.setSuffix(" %")
            self.ed_ef_amount.setRange(0, 100)
            self.ed_amount_lbl.setText("Amount (%):")
        else:
            self.ed_ef_amount.setPrefix("$ ")
            self.ed_ef_amount.setSuffix("")
            self.ed_ef_amount.setRange(0, 99_999)
            self.ed_amount_lbl.setText("Amount ($):")

    # ── Run Payroll tab ──────────────────────────────────────────────────────

    def _build_run_payroll_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        cfg_grp = QtWidgets.QGroupBox("Payroll Period & Tax Rates")
        cfg_grp.setStyleSheet(GRP_STYLE)
        cfg = QtWidgets.QHBoxLayout(cfg_grp)
        cfg.setSpacing(10)

        self.run_from = QtWidgets.QDateEdit()
        self.run_from.setStyleSheet(DATE_STYLE)
        self.run_from.setCalendarPopup(True)
        self.run_from.setDate(QtCore.QDate.currentDate().addDays(-13))
        self.run_from.setDisplayFormat("MM/dd/yyyy")

        self.run_to = QtWidgets.QDateEdit()
        self.run_to.setStyleSheet(DATE_STYLE)
        self.run_to.setCalendarPopup(True)
        self.run_to.setDate(QtCore.QDate.currentDate())
        self.run_to.setDisplayFormat("MM/dd/yyyy")

        self.run_freq = QtWidgets.QComboBox()
        self.run_freq.setStyleSheet(COMBO_STYLE)
        self.run_freq.addItems(list(FREQ_DIVISORS.keys()))
        self.run_freq.setCurrentText("Bi-Weekly")

        self.run_fed_spin = QtWidgets.QDoubleSpinBox()
        self.run_fed_spin.setStyleSheet(SPIN_STYLE)
        self.run_fed_spin.setRange(0, 50)
        self.run_fed_spin.setDecimals(1)
        self.run_fed_spin.setSuffix(" %")
        self.run_fed_spin.setValue(22.0)

        self.run_state_spin = QtWidgets.QDoubleSpinBox()
        self.run_state_spin.setStyleSheet(SPIN_STYLE)
        self.run_state_spin.setRange(0, 20)
        self.run_state_spin.setDecimals(1)
        self.run_state_spin.setSuffix(" %")
        self.run_state_spin.setValue(5.0)

        for widget, label_text in (
            (self.run_from, "Period From:"),
            (self.run_to, "To:"),
            (self.run_freq, "Frequency:"),
            (self.run_fed_spin, "Federal Tax:"),
            (self.run_state_spin, "State Tax:"),
        ):
            cfg.addWidget(_lbl(label_text))
            cfg.addWidget(widget)

        cfg.addSpacing(10)
        load_btn = QtWidgets.QPushButton("Load Employees")
        load_btn.setStyleSheet(BUTTON_STYLE)
        load_btn.setFixedHeight(30)
        load_btn.clicked.connect(self._on_load_payroll)
        cfg.addWidget(load_btn)
        cfg.addStretch()
        layout.addWidget(cfg_grp)

        note = QtWidgets.QLabel(
            "Reg Hours and OT Hours are editable. Active deductions are applied automatically.")
        note.setStyleSheet("color: rgb(200,220,255); font-size: 11px;")
        layout.addWidget(note)

        self.run_table = QtWidgets.QTableWidget()
        self.run_table.setColumnCount(12)
        self.run_table.setHorizontalHeaderLabels([
            "Employee", "Pay Type", "Rate",
            "Reg Hrs", "OT Hrs", "Deductions",
            "Gross Pay", "Fed Tax", "State Tax", "SS", "Medicare", "Net Pay",
        ])
        hh = self.run_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in range(1, 12):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.run_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.run_table.setAlternatingRowColors(True)
        self.run_table.verticalHeader().setVisible(False)
        layout.addWidget(self.run_table, stretch=1)

        bot = QtWidgets.QHBoxLayout()
        calc_btn = QtWidgets.QPushButton("Calculate")
        calc_btn.setStyleSheet(BUTTON_STYLE)
        calc_btn.setFixedHeight(34)
        calc_btn.clicked.connect(self._on_calculate_payroll)
        bot.addWidget(calc_btn)

        self.save_run_btn = QtWidgets.QPushButton("Save Payroll Run")
        self.save_run_btn.setStyleSheet(BUTTON_STYLE)
        self.save_run_btn.setFixedHeight(34)
        self.save_run_btn.setEnabled(False)
        self.save_run_btn.clicked.connect(self._on_save_payroll_run)
        bot.addWidget(self.save_run_btn)

        bot.addSpacing(20)
        self.run_totals_lbl = QtWidgets.QLabel("")
        self.run_totals_lbl.setStyleSheet("color: white; font-size: 13px;")
        bot.addWidget(self.run_totals_lbl)
        bot.addStretch()
        layout.addLayout(bot)
        return w

    # ── Pay Stubs tab ────────────────────────────────────────────────────────

    def _build_paystubs_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        sel = QtWidgets.QHBoxLayout()
        sel.addWidget(_lbl("Payroll Run:"))
        self.stub_run_combo = QtWidgets.QComboBox()
        self.stub_run_combo.setStyleSheet(COMBO_STYLE)
        self.stub_run_combo.setMinimumWidth(300)
        self.stub_run_combo.currentIndexChanged.connect(self._on_stub_run_change)
        sel.addWidget(self.stub_run_combo)
        sel.addWidget(_lbl("Employee:"))
        self.stub_emp_combo = QtWidgets.QComboBox()
        self.stub_emp_combo.setStyleSheet(COMBO_STYLE)
        self.stub_emp_combo.setMinimumWidth(200)
        sel.addWidget(self.stub_emp_combo)
        view_btn = QtWidgets.QPushButton("View Pay Stub")
        view_btn.setStyleSheet(BUTTON_STYLE)
        view_btn.setFixedHeight(30)
        view_btn.clicked.connect(self._on_view_stub)
        sel.addWidget(view_btn)
        sel.addStretch()
        v.addLayout(sel)

        self.stub_display = QtWidgets.QTextEdit()
        self.stub_display.setReadOnly(True)
        self.stub_display.setStyleSheet(
            "QTextEdit{background-color:white;border:2px solid black;"
            "border-radius:6px;font-family:Courier New,monospace;font-size:13px;}"
        )
        v.addWidget(self.stub_display, stretch=1)
        return w

    # ── YTD Report tab ───────────────────────────────────────────────────────

    def _build_ytd_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(_lbl("Fiscal Year:"))
        self.ytd_year = QtWidgets.QComboBox()
        self.ytd_year.setStyleSheet(COMBO_STYLE)
        cur_year = QtCore.QDate.currentDate().year()
        for yr in range(cur_year, cur_year - 6, -1):
            self.ytd_year.addItem(str(yr))
        fb.addWidget(self.ytd_year)
        fb.addWidget(_lbl("Employee:"))
        self.ytd_emp_filter = QtWidgets.QComboBox()
        self.ytd_emp_filter.setStyleSheet(COMBO_STYLE)
        self.ytd_emp_filter.setMinimumWidth(200)
        fb.addWidget(self.ytd_emp_filter)
        run_btn = QtWidgets.QPushButton("Run Report")
        run_btn.setStyleSheet(BUTTON_STYLE)
        run_btn.setFixedHeight(30)
        run_btn.clicked.connect(self._refresh_ytd)
        fb.addWidget(run_btn)
        fb.addStretch()
        exp_btn = QtWidgets.QPushButton("Export CSV")
        exp_btn.setStyleSheet(BUTTON_STYLE)
        exp_btn.setFixedHeight(30)
        exp_btn.clicked.connect(lambda: _export_csv(self.ytd_tbl, self))
        fb.addWidget(exp_btn)
        v.addLayout(fb)

        self.ytd_tbl = QtWidgets.QTableWidget(0, 11)
        self.ytd_tbl.setHorizontalHeaderLabels([
            "Employee", "Runs", "Reg Hours", "OT Hours",
            "Gross Pay", "Pre-Tax Deds", "Fed Tax", "State Tax", "SS", "Medicare", "Net Pay"
        ])
        hh = self.ytd_tbl.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in range(1, 11):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.ytd_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ytd_tbl.setAlternatingRowColors(True)
        self.ytd_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.ytd_tbl, stretch=1)

        self.ytd_totals_lbl = QtWidgets.QLabel("")
        self.ytd_totals_lbl.setStyleSheet("color: white; font-size: 13px;")
        self.ytd_totals_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        v.addWidget(self.ytd_totals_lbl)
        return w

    # ── History tab ──────────────────────────────────────────────────────────

    def _build_history_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle{background: white; width: 3px;}")

        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 4, 0)
        runs_lbl = QtWidgets.QLabel("Payroll Runs")
        runs_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        lv.addWidget(runs_lbl)

        self.hist_runs_table = QtWidgets.QTableWidget()
        self.hist_runs_table.setColumnCount(4)
        self.hist_runs_table.setHorizontalHeaderLabels(["Run Date", "Period", "Employees", "Total Gross"])
        hl = self.hist_runs_table.horizontalHeader()
        hl.setStyleSheet("color: black; font-weight: bold;")
        hl.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hl.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hl.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hl.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.hist_runs_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hist_runs_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.hist_runs_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.hist_runs_table.setAlternatingRowColors(True)
        self.hist_runs_table.verticalHeader().setVisible(False)
        self.hist_runs_table.cellClicked.connect(self._on_history_run_clicked)
        lv.addWidget(self.hist_runs_table, stretch=1)

        void_btn = QtWidgets.QPushButton("Void Selected Run")
        void_btn.setStyleSheet(BUTTON_STYLE)
        void_btn.setFixedHeight(32)
        void_btn.clicked.connect(self._on_void_run)
        lv.addWidget(void_btn)
        splitter.addWidget(left)

        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(4, 0, 0, 0)
        self.hist_detail_lbl = QtWidgets.QLabel("Select a run to view detail")
        self.hist_detail_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        rv.addWidget(self.hist_detail_lbl)

        self.hist_detail_table = QtWidgets.QTableWidget()
        self.hist_detail_table.setColumnCount(11)
        self.hist_detail_table.setHorizontalHeaderLabels([
            "Employee", "Reg Hrs", "OT Hrs",
            "Gross", "Pre-Tax Deds", "Fed Tax", "State Tax", "SS", "Medicare",
            "Post-Tax Deds", "Net Pay",
        ])
        hd = self.hist_detail_table.horizontalHeader()
        hd.setStyleSheet("color: black; font-weight: bold;")
        hd.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in range(1, 11):
            hd.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.hist_detail_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hist_detail_table.setAlternatingRowColors(True)
        self.hist_detail_table.verticalHeader().setVisible(False)
        rv.addWidget(self.hist_detail_table, stretch=1)

        self.hist_totals_lbl = QtWidgets.QLabel("")
        self.hist_totals_lbl.setStyleSheet("color: white; font-size: 12px;")
        rv.addWidget(self.hist_totals_lbl)
        splitter.addWidget(right)

        splitter.setSizes([300, 900])
        layout.addWidget(splitter)
        return w

    # ── Pay Rates data ───────────────────────────────────────────────────────

    def _load_pay_rates(self):
        conn = get_db()
        employees = conn.execute(
            "SELECT id, first_name, last_name, employee_id FROM people ORDER BY last_name, first_name"
        ).fetchall()
        pay_map = {r["people_id"]: r for r in conn.execute("SELECT * FROM employee_pay").fetchall()}
        conn.close()

        self.pr_emp_combo.blockSignals(True)
        self.pr_emp_combo.clear()
        self.pr_emp_combo.addItem("-- select --", None)
        for e in employees:
            label = f"{e['last_name']}, {e['first_name']}"
            if e["employee_id"]:
                label += f"  (ID {e['employee_id']})"
            self.pr_emp_combo.addItem(label, e["id"])
        self.pr_emp_combo.blockSignals(False)

        self.pr_table.setRowCount(0)
        self._pay_rate_row_ids = []
        for e in employees:
            pay = pay_map.get(e["id"])
            r = self.pr_table.rowCount()
            self.pr_table.insertRow(r)
            self._pay_rate_row_ids.append(e["id"])
            name = f"{e['last_name']}, {e['first_name']}"
            emp_id_str = str(e["employee_id"]) if e["employee_id"] else ""
            if pay:
                rate_str = (f"${pay['pay_rate']:.2f}/hr" if pay["pay_type"] == "hourly"
                            else f"${pay['pay_rate']:,.0f}/yr")
                eff_str = pay["effective_date"]
            else:
                rate_str = "(not set)"
                eff_str = ""
            for col, val in enumerate([name, emp_id_str,
                                       pay["pay_type"] if pay else "", rate_str, eff_str]):
                self.pr_table.setItem(r, col, _ro(val,
                                                  QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
                                                  if col == 0 else
                                                  QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter))

    def _on_pr_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._pay_rate_row_ids):
            return
        pid = self._pay_rate_row_ids[row]
        idx = self.pr_emp_combo.findData(pid)
        if idx >= 0:
            self.pr_emp_combo.setCurrentIndex(idx)
        conn = get_db()
        pay = conn.execute("SELECT * FROM employee_pay WHERE people_id=%s", (pid,)).fetchone()
        conn.close()
        if pay:
            self.pr_type_combo.setCurrentText(pay["pay_type"])
            self.pr_rate_spin.setValue(pay["pay_rate"])
            try:
                d = datetime.strptime(pay["effective_date"], "%Y-%m-%d")
                self.pr_date_edit.setDate(QtCore.QDate(d.year, d.month, d.day))
            except ValueError:
                pass
        else:
            self.pr_rate_spin.setValue(0.0)

    def _pr_clear_form(self):
        self.pr_emp_combo.setCurrentIndex(0)
        self.pr_type_combo.setCurrentIndex(0)
        self.pr_rate_spin.setValue(0.0)
        self.pr_date_edit.setDate(QtCore.QDate.currentDate())
        self.pr_table.clearSelection()

    def _on_pr_save(self):
        pid = self.pr_emp_combo.currentData()
        if pid is None:
            QtWidgets.QMessageBox.warning(self, "No Employee", "Select an employee first.")
            return
        pay_type = self.pr_type_combo.currentText()
        pay_rate = self.pr_rate_spin.value()
        eff_date = self.pr_date_edit.date().toString("yyyy-MM-dd")
        conn = get_db()
        conn.execute("""
            INSERT INTO employee_pay (people_id, pay_type, pay_rate, effective_date)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(people_id) DO UPDATE SET
                pay_type=excluded.pay_type,
                pay_rate=excluded.pay_rate,
                effective_date=excluded.effective_date
        """, (pid, pay_type, pay_rate, eff_date))
        conn.commit()
        conn.close()
        self._load_pay_rates()

    def _on_pr_delete(self):
        pid = self.pr_emp_combo.currentData()
        if pid is None:
            QtWidgets.QMessageBox.warning(self, "No Employee", "Select an employee first.")
            return
        if QtWidgets.QMessageBox.question(
            self, "Confirm", "Remove pay rate for this employee%s",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM employee_pay WHERE people_id=%s", (pid,))
            conn.commit()
            conn.close()
            self._pr_clear_form()
            self._load_pay_rates()

    # ── Deductions data ──────────────────────────────────────────────────────

    def _refresh_ded_types(self):
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM payroll_deduction_type ORDER BY category, name"
        ).fetchall()
        conn.close()
        self.ded_type_tbl.setRowCount(0)
        for row in rows:
            r = self.ded_type_tbl.rowCount()
            self.ded_type_tbl.insertRow(r)
            self.ded_type_tbl.setItem(
                r, 0, _ro(str(row["id"]), QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.ded_type_tbl.setItem(
                r, 1, _ro(row["name"], QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.ded_type_tbl.setItem(
                r, 2, _ro(row["category"], QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.ded_type_tbl.setItem(r, 3, _ro(
                "Yes" if row["is_pre_tax"] else "No", QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.ded_type_tbl.item(r, 0).setData(QtCore.Qt.ItemDataRole.UserRole, row["id"])
        self._refresh_ded_type_combo()

    def _refresh_ded_type_combo(self):
        conn = get_db()
        types = conn.execute(
            "SELECT id, name FROM payroll_deduction_type WHERE is_active=1 ORDER BY name"
        ).fetchall()
        conn.close()
        self.ed_ef_type.clear()
        self.ed_ef_type.addItem("-- select --", None)
        for t in types:
            self.ed_ef_type.addItem(t["name"], t["id"])

    def _refresh_emp_filter_combo(self):
        conn = get_db()
        emps = conn.execute(
            "SELECT id, first_name, last_name FROM people ORDER BY last_name, first_name"
        ).fetchall()
        conn.close()
        for combo in [self.ed_emp_filter, self.ed_ef_emp, self.ytd_emp_filter]:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("All Employees", None)
            for e in emps:
                combo.addItem(f"{e['last_name']}, {e['first_name']}", e["id"])
            combo.blockSignals(False)

    def _refresh_emp_deductions(self):
        pid = self.ed_emp_filter.currentData()
        conn = get_db()
        q = """
            SELECT ed.id, p.first_name, p.last_name,
                   dt.name AS ded_name, dt.is_pre_tax,
                   ed.calc_method, ed.amount, ed.is_active
            FROM employee_deduction ed
            JOIN people p ON p.id=ed.people_id
            JOIN payroll_deduction_type dt ON dt.id=ed.deduction_type_id
        """
        params = []
        if pid:
            q += " WHERE ed.people_id=%s"
            params.append(pid)
        q += " ORDER BY p.last_name, p.first_name, dt.name"
        rows = conn.execute(q, params).fetchall()
        conn.close()
        self.ed_tbl.setRowCount(0)
        for row in rows:
            r = self.ed_tbl.rowCount()
            self.ed_tbl.insertRow(r)
            amt_str = (f"${row['amount']:.2f}" if row["calc_method"] == "flat"
                       else f"{row['amount']:.1f}%")
            self.ed_tbl.setItem(
                r, 0, _ro(str(row["id"]), QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.ed_tbl.setItem(r, 1, _ro(f"{row['last_name']}, {row['first_name']}",
                                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.ed_tbl.setItem(
                r, 2, _ro(row["ded_name"], QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.ed_tbl.setItem(
                r, 3, _ro(row["calc_method"], QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.ed_tbl.setItem(r, 4, _ro(amt_str))
            self.ed_tbl.setItem(r, 5, _ro(
                "Yes" if row["is_pre_tax"] else "No", QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.ed_tbl.setItem(r, 6, _ro(
                "Yes" if row["is_active"] else "No", QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.ed_tbl.item(r, 0).setData(QtCore.Qt.ItemDataRole.UserRole, row["id"])
            if not row["is_active"]:
                for c in range(7):
                    it = self.ed_tbl.item(r, c)
                    if it:
                        it.setForeground(QtGui.QColor(160, 160, 160))

    def _on_ded_type_select(self):
        rows = self.ded_type_tbl.selectionModel().selectedRows()
        if not rows:
            return
        r = rows[0].row()
        tid = self.ded_type_tbl.item(r, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        conn = get_db()
        row = conn.execute("SELECT * FROM payroll_deduction_type WHERE id=%s", (tid,)).fetchone()
        conn.close()
        if row:
            self.dt_ef_name.setText(row["name"])
            idx = self.dt_ef_cat.findText(row["category"])
            if idx >= 0:
                self.dt_ef_cat.setCurrentIndex(idx)
            self.dt_ef_pretax.setChecked(bool(row["is_pre_tax"]))

    def _on_dt_add(self):
        name = self.dt_ef_name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Name is required.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO payroll_deduction_type(name,category,is_pre_tax) VALUES(%s,%s,%s)",
            (name, self.dt_ef_cat.currentText(), 1 if self.dt_ef_pretax.isChecked() else 0)
        )
        conn.commit()
        conn.close()
        self._refresh_ded_types()
        self._on_dt_clear()

    def _on_dt_update(self):
        rows = self.ded_type_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Selection", "Select a deduction type first.")
            return
        tid = self.ded_type_tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        name = self.dt_ef_name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Name is required.")
            return
        conn = get_db()
        conn.execute(
            "UPDATE payroll_deduction_type SET name=%s,category=%s,is_pre_tax=%s WHERE id=%s",
            (name, self.dt_ef_cat.currentText(), 1 if self.dt_ef_pretax.isChecked() else 0, tid)
        )
        conn.commit()
        conn.close()
        self._refresh_ded_types()

    def _on_dt_delete(self):
        rows = self.ded_type_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Selection", "Select a deduction type first.")
            return
        tid = self.ded_type_tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if QtWidgets.QMessageBox.question(
            self, "Delete", "Delete this deduction type%s This will remove all employee assignments.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM payroll_deduction_type WHERE id=%s", (tid,))
            conn.commit()
            conn.close()
            self._refresh_ded_types()
            self._on_dt_clear()

    def _on_dt_clear(self):
        self.dt_ef_name.clear()
        self.dt_ef_cat.setCurrentIndex(0)
        self.dt_ef_pretax.setChecked(True)
        self.ded_type_tbl.clearSelection()

    def _on_ed_select(self):
        rows = self.ed_tbl.selectionModel().selectedRows()
        if not rows:
            return
        eid = self.ed_tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        conn = get_db()
        row = conn.execute("SELECT * FROM employee_deduction WHERE id=%s", (eid,)).fetchone()
        conn.close()
        if not row:
            return
        idx = self.ed_ef_emp.findData(row["people_id"])
        if idx >= 0:
            self.ed_ef_emp.setCurrentIndex(idx)
        idx = self.ed_ef_type.findData(row["deduction_type_id"])
        if idx >= 0:
            self.ed_ef_type.setCurrentIndex(idx)
        self.ed_ef_method.setCurrentText(row["calc_method"])
        self.ed_ef_amount.setValue(row["amount"])
        self.ed_ef_active.setChecked(bool(row["is_active"]))
        self.ed_ef_notes.setText(row["notes"] or "")

    def _on_ed_add(self):
        pid = self.ed_ef_emp.currentData()
        tid = self.ed_ef_type.currentData()
        if not pid or not tid:
            QtWidgets.QMessageBox.warning(self, "Validation", "Select employee and deduction type.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO employee_deduction(people_id,deduction_type_id,calc_method,amount,is_active,notes) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (pid, tid, self.ed_ef_method.currentText(), self.ed_ef_amount.value(),
             1 if self.ed_ef_active.isChecked() else 0, self.ed_ef_notes.text().strip())
        )
        conn.commit()
        conn.close()
        self._refresh_emp_deductions()
        self._on_ed_clear()

    def _on_ed_update(self):
        rows = self.ed_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Selection", "Select an assignment first.")
            return
        eid = self.ed_tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        conn = get_db()
        conn.execute(
            "UPDATE employee_deduction SET people_id=%s,deduction_type_id=%s,calc_method=%s,"
            "amount=%s,is_active=%s,notes=%s WHERE id=%s",
            (self.ed_ef_emp.currentData(), self.ed_ef_type.currentData(),
             self.ed_ef_method.currentText(), self.ed_ef_amount.value(),
             1 if self.ed_ef_active.isChecked() else 0,
             self.ed_ef_notes.text().strip(), eid)
        )
        conn.commit()
        conn.close()
        self._refresh_emp_deductions()

    def _on_ed_delete(self):
        rows = self.ed_tbl.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Selection", "Select an assignment first.")
            return
        eid = self.ed_tbl.item(rows[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if QtWidgets.QMessageBox.question(
            self, "Remove", "Remove this deduction assignment%s",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM employee_deduction WHERE id=%s", (eid,))
            conn.commit()
            conn.close()
            self._refresh_emp_deductions()
            self._on_ed_clear()

    def _on_ed_clear(self):
        self.ed_ef_emp.setCurrentIndex(0)
        self.ed_ef_type.setCurrentIndex(0)
        self.ed_ef_method.setCurrentIndex(0)
        self.ed_ef_amount.setValue(0.0)
        self.ed_ef_active.setChecked(True)
        self.ed_ef_notes.clear()
        self.ed_tbl.clearSelection()

    def _get_employee_deductions(self, people_id, gross):
        """Return (pre_tax_total, post_tax_total, items_list) for an employee."""
        conn = get_db()
        rows = conn.execute("""
            SELECT ed.calc_method, ed.amount, dt.name, dt.is_pre_tax
            FROM employee_deduction ed
            JOIN payroll_deduction_type dt ON dt.id=ed.deduction_type_id
            WHERE ed.people_id=%s AND ed.is_active=1
        """, (people_id,)).fetchall()
        conn.close()
        pre_total = post_total = 0.0
        items = []
        for row in rows:
            if row["calc_method"] == "percent":
                amt = gross * (row["amount"] / 100.0)
            else:
                amt = row["amount"]
            amt = round(amt, 2)
            items.append({"name": row["name"], "is_pre_tax": row["is_pre_tax"], "amount": amt})
            if row["is_pre_tax"]:
                pre_total += amt
            else:
                post_total += amt
        return round(pre_total, 2), round(post_total, 2), items

    # ── Run Payroll data ─────────────────────────────────────────────────────

    def _on_load_payroll(self):
        start_str = self.run_from.date().toString("yyyy-MM-dd")
        end_str = self.run_to.date().toString("yyyy-MM-dd")
        if start_str > end_str:
            QtWidgets.QMessageBox.warning(self, "Invalid Range", "From date must be before To date.")
            return
        fed_rate = self.run_fed_spin.value() / 100
        state_rate = self.run_state_spin.value() / 100
        freq = self.run_freq.currentText()

        conn = get_db()
        employees = conn.execute(
            "SELECT p.id, p.first_name, p.last_name, ep.pay_type, ep.pay_rate "
            "FROM people p LEFT JOIN employee_pay ep ON ep.people_id=p.id "
            "ORDER BY p.last_name, p.first_name"
        ).fetchall()
        conn.close()

        self.run_table.setRowCount(0)
        self._run_people_ids = []
        self._run_deductions = {}

        for e in employees:
            pid = e["id"]
            pay_type = e["pay_type"] or "hourly"
            pay_rate = e["pay_rate"] or 0.0
            reg, ot = _hours_from_timeclock(pid, start_str, end_str)

            # get raw gross to compute percent-based deductions
            if pay_type == "hourly":
                raw_gross = pay_rate * reg + pay_rate * 1.5 * ot
            else:
                raw_gross = pay_rate / FREQ_DIVISORS.get(freq, 26)

            pre_deds, post_deds, ded_items = self._get_employee_deductions(pid, raw_gross)
            self._run_deductions[pid] = {'pre': pre_deds, 'post': post_deds, 'items': ded_items}

            gross, fed, st, ss, med, net = _calc_pay(
                pay_type, pay_rate, reg, ot, fed_rate, state_rate, freq, pre_deds, post_deds)
            total_deds = pre_deds + post_deds

            r = self.run_table.rowCount()
            self.run_table.insertRow(r)
            self._run_people_ids.append(pid)

            name = f"{e['last_name']}, {e['first_name']}"
            rate_str = (f"${pay_rate:.2f}/hr" if pay_type == "hourly" else f"${pay_rate:,.0f}/yr")

            al = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            ac = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
            self.run_table.setItem(r, self._C_EMP, _ro(name, al))
            self.run_table.setItem(r, self._C_TYPE, _ro(pay_type, ac))
            self.run_table.setItem(r, self._C_RATE, _ro(rate_str))
            self.run_table.setItem(r, self._C_REG, _rw(f"{reg:.2f}"))
            self.run_table.setItem(r, self._C_OT, _rw(f"{ot:.2f}"))
            self.run_table.setItem(r, self._C_DEDS, _ro(_money(total_deds)))
            self.run_table.setItem(r, self._C_GROSS, _ro(_money(gross)))
            self.run_table.setItem(r, self._C_FED, _ro(_money(fed)))
            self.run_table.setItem(r, self._C_ST, _ro(_money(st)))
            self.run_table.setItem(r, self._C_SS, _ro(_money(ss)))
            self.run_table.setItem(r, self._C_MED, _ro(_money(med)))
            self.run_table.setItem(r, self._C_NET, _ro(_money(net)))

        self._update_run_totals()
        self.save_run_btn.setEnabled(self.run_table.rowCount() > 0)

    def _on_calculate_payroll(self):
        if self.run_table.rowCount() == 0:
            QtWidgets.QMessageBox.warning(self, "No Data", "Load employees first.")
            return
        fed_rate = self.run_fed_spin.value() / 100
        state_rate = self.run_state_spin.value() / 100
        freq = self.run_freq.currentText()

        for r, pid in enumerate(self._run_people_ids):
            type_item = self.run_table.item(r, self._C_TYPE)
            rate_item = self.run_table.item(r, self._C_RATE)
            reg_item = self.run_table.item(r, self._C_REG)
            ot_item = self.run_table.item(r, self._C_OT)
            if not all((type_item, rate_item, reg_item, ot_item)):
                continue
            pay_type = type_item.text()
            rate_str = rate_item.text().replace("$", "").replace(",", "").replace("/hr", "").replace("/yr", "")
            try:
                pay_rate = float(rate_str)
                reg_hrs = float(reg_item.text())
                ot_hrs = float(ot_item.text())
            except ValueError:
                continue
            if reg_hrs < 0 or ot_hrs < 0:
                QtWidgets.QMessageBox.warning(self, "Invalid", f"Row {r + 1}: hours cannot be negative.")
                return

            raw_gross = (pay_rate * reg_hrs + pay_rate * 1.5 * ot_hrs
                         if pay_type == "hourly" else pay_rate / FREQ_DIVISORS.get(freq, 26))
            pre_deds, post_deds, ded_items = self._get_employee_deductions(pid, raw_gross)
            self._run_deductions[pid] = {'pre': pre_deds, 'post': post_deds, 'items': ded_items}

            gross, fed, st, ss, med, net = _calc_pay(
                pay_type, pay_rate, reg_hrs, ot_hrs, fed_rate, state_rate, freq, pre_deds, post_deds)
            total_deds = pre_deds + post_deds

            self.run_table.setItem(r, self._C_DEDS, _ro(_money(total_deds)))
            self.run_table.setItem(r, self._C_GROSS, _ro(_money(gross)))
            self.run_table.setItem(r, self._C_FED, _ro(_money(fed)))
            self.run_table.setItem(r, self._C_ST, _ro(_money(st)))
            self.run_table.setItem(r, self._C_SS, _ro(_money(ss)))
            self.run_table.setItem(r, self._C_MED, _ro(_money(med)))
            self.run_table.setItem(r, self._C_NET, _ro(_money(net)))

        self._update_run_totals()

    def _update_run_totals(self):
        total_gross = total_net = total_deds = 0.0
        for r in range(self.run_table.rowCount()):
            def _v(col):
                it = self.run_table.item(r, col)
                return float(it.text().replace("$", "").replace(",", "")) if it else 0.0
            total_gross += _v(self._C_GROSS)
            total_net += _v(self._C_NET)
            total_deds += _v(self._C_DEDS)
        self.run_totals_lbl.setText(
            f"Total Gross: {_money(total_gross)}    "
            f"Total Deductions: {_money(total_deds)}    "
            f"Total Net: {_money(total_net)}    "
            f"Employees: {self.run_table.rowCount()}"
        )

    def _on_save_payroll_run(self):
        if self.run_table.rowCount() == 0:
            return
        start_str = self.run_from.date().toString("yyyy-MM-dd")
        end_str = self.run_to.date().toString("yyyy-MM-dd")
        fed_rate = self.run_fed_spin.value() / 100
        state_rate = self.run_state_spin.value() / 100
        freq = self.run_freq.currentText()

        if QtWidgets.QMessageBox.question(
            self, "Save Payroll Run",
            f"Save payroll run for period {start_str} – {end_str}?\n"
            f"({self.run_table.rowCount()} employees)",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        ) != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        conn = get_db()
        cur = conn.execute("""
            INSERT INTO payroll_run (period_start, period_end, run_date, pay_frequency,
                                     federal_tax_rate, state_tax_rate, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'processed') RETURNING id
        """, (start_str, end_str, datetime.now().strftime(DT_FMT), freq, fed_rate, state_rate))
        run_id = cur.fetchone()['id']

        def _v(r, col):
            it = self.run_table.item(r, col)
            return float(it.text().replace("$", "").replace(",", "")) if it else 0.0

        total_gross = total_net = 0.0
        for r, pid in enumerate(self._run_people_ids):
            deds = self._run_deductions.get(pid, {'pre': 0.0, 'post': 0.0, 'items': []})
            entry_cur = conn.execute("""
                INSERT INTO payroll_entry
                    (run_id, people_id, regular_hours, overtime_hours,
                     gross_pay, federal_tax, state_tax, social_security, medicare, net_pay,
                     pre_tax_deductions, post_tax_deductions)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, (run_id, pid,
                  float(self.run_table.item(r, self._C_REG).text()),
                  float(self.run_table.item(r, self._C_OT).text()),
                  _v(r, self._C_GROSS), _v(r, self._C_FED), _v(r, self._C_ST),
                  _v(r, self._C_SS), _v(r, self._C_MED), _v(r, self._C_NET),
                  deds['pre'], deds['post']))
            entry_id = entry_cur.fetchone()['id']

            for item in deds['items']:
                conn.execute(
                    "INSERT INTO payroll_entry_deduction(entry_id,deduction_name,is_pre_tax,amount) "
                    "VALUES(%s,%s,%s,%s)",
                    (entry_id, item["name"], item["is_pre_tax"], item["amount"])
                )
            total_gross += _v(r, self._C_GROSS)
            total_net += _v(r, self._C_NET)

        conn.commit()
        conn.close()

        total_withholding = round(total_gross - total_net, 2)
        post_gl_entry(
            journal_date=end_str,
            reference=f"PAYROLL-{start_str}",
            description=f"Payroll run {start_str} – {end_str} ({freq})",
            lines=[
                ("6000", round(total_gross, 2), 0.0, "Gross wages"),
                ("1000", 0.0, round(total_net, 2), "Net pay disbursed"),
                ("2200", 0.0, total_withholding, "Taxes & withholding"),
            ],
        )

        self.run_table.setRowCount(0)
        self._run_people_ids = []
        self._run_deductions = {}
        self.save_run_btn.setEnabled(False)
        self.run_totals_lbl.setText("")
        self._load_history()
        QtWidgets.QMessageBox.information(self, "Saved", "Payroll run saved successfully.")

    # ── Pay Stubs data ───────────────────────────────────────────────────────

    def _refresh_stub_run_combo(self):
        self.stub_run_combo.blockSignals(True)
        self.stub_run_combo.clear()
        self.stub_run_combo.addItem("-- select run --", None)
        conn = get_db()
        runs = conn.execute(
            "SELECT id, period_start, period_end, run_date, pay_frequency "
            "FROM payroll_run ORDER BY run_date DESC"
        ).fetchall()
        conn.close()
        for run in runs:
            try:
                rd = datetime.strptime(run["run_date"], DT_FMT).strftime("%m/%d/%Y")
            except ValueError:
                rd = run["run_date"]
            label = f"{rd}  ({run['period_start']} – {run['period_end']})  [{run['pay_frequency']}]"
            self.stub_run_combo.addItem(label, run["id"])
        self.stub_run_combo.blockSignals(False)

    def _on_stub_run_change(self):
        run_id = self.stub_run_combo.currentData()
        self.stub_emp_combo.clear()
        self.stub_emp_combo.addItem("-- select employee --", None)
        if not run_id:
            return
        conn = get_db()
        emps = conn.execute("""
            SELECT pe.id AS entry_id, p.first_name, p.last_name
            FROM payroll_entry pe JOIN people p ON p.id=pe.people_id
            WHERE pe.run_id=%s ORDER BY p.last_name, p.first_name
        """, (run_id,)).fetchall()
        conn.close()
        for e in emps:
            self.stub_emp_combo.addItem(f"{e['last_name']}, {e['first_name']}", e["entry_id"])

    def _on_view_stub(self):
        entry_id = self.stub_emp_combo.currentData()
        if not entry_id:
            QtWidgets.QMessageBox.warning(self, "Selection", "Select a payroll run and employee.")
            return
        conn = get_db()
        entry = conn.execute("""
            SELECT pe.*, p.first_name, p.last_name, p.emp_id,
                   pr.period_start, pr.period_end, pr.run_date, pr.pay_frequency,
                   pr.federal_tax_rate, pr.state_tax_rate,
                   ep.pay_type, ep.pay_rate
            FROM payroll_entry pe
            JOIN people p      ON p.id=pe.people_id
            JOIN payroll_run pr ON pr.id=pe.run_id
            LEFT JOIN employee_pay ep ON ep.people_id=pe.people_id
            WHERE pe.id=%s
        """, (entry_id,)).fetchone()
        ded_rows = conn.execute(
            "SELECT * FROM payroll_entry_deduction WHERE entry_id=%s ORDER BY is_pre_tax DESC, deduction_name",
            (entry_id,)
        ).fetchall()
        conn.close()
        if not entry:
            return
        self._render_pay_stub(entry, ded_rows)

    def _render_pay_stub(self, e, deds):
        try:
            rd = datetime.strptime(e["run_date"], DT_FMT).strftime("%B %d, %Y")
        except ValueError:
            rd = e["run_date"]
        pay_type = e["pay_type"] or "hourly"
        pay_rate = e["pay_rate"] or 0.0
        rate_str = (f"${pay_rate:.2f}/hr" if pay_type == "hourly" else f"${pay_rate:,.2f}/yr (salary)")

        W = 60

        def line(label, value, width=W):
            return f"{label:<30}{str(value):>{width - 30}}"

        def divider(ch="-"):
            return ch * W

        def section(title):
            return f"\n{title}\n{divider()}"

        stub = "\n".join([
            divider("="),
            "PAY STUB".center(W),
            divider("="),
            line("Employee:", f"{e['last_name']}, {e['first_name']}"),
            line("Employee ID:", e["employee_id"] or "—"),
            line("Pay Period:", f"{e['period_start']}  to  {e['period_end']}"),
            line("Payment Date:", rd),
            line("Pay Frequency:", e["pay_frequency"]),
            line("Pay Type / Rate:", rate_str),
            divider(),
            section("EARNINGS"),
            line("Regular Hours:", f"{e['regular_hours']:.2f} hrs"),
            line("Overtime Hours:", f"{e['overtime_hours']:.2f} hrs"),
            line("GROSS PAY:", _money(e["gross_pay"])),
        ])

        pre_tax = [d for d in deds if d["is_pre_tax"]]
        post_tax = [d for d in deds if not d["is_pre_tax"]]

        if pre_tax:
            stub += section("PRE-TAX DEDUCTIONS")
            for d in pre_tax:
                stub += "\n" + line(f"  {d['deduction_name']}:", f"-{_money(d['amount'])}")
            stub += "\n" + line("  Total Pre-Tax Deductions:",
                                f"-{_money(sum(d['amount'] for d in pre_tax))}")

        taxable = e["gross_pay"] - (e["pre_tax_deductions"] or 0.0)
        stub += section("TAXES  (on taxable wages: " + _money(taxable) + ")")
        stub += "\n" + line(f"  Federal Income Tax ({_pct(e['federal_tax_rate'])}):".replace("  ", " ", 1) if False else
                            "  Federal Income Tax:", f"-{_money(e['federal_tax'])}")
        stub += "\n" + line("  State Income Tax:", f"-{_money(e['state_tax'])}")
        stub += "\n" + line(f"  Social Security ({_pct(SS_RATE)}):", f"-{_money(e['social_security'])}")
        stub += "\n" + line(f"  Medicare ({_pct(MEDICARE_RATE)}):", f"-{_money(e['medicare'])}")
        total_tax = e["federal_tax"] + e["state_tax"] + e["social_security"] + e["medicare"]
        stub += "\n" + line("  Total Taxes:", f"-{_money(total_tax)}")

        if post_tax:
            stub += section("POST-TAX DEDUCTIONS")
            for d in post_tax:
                stub += "\n" + line(f"  {d['deduction_name']}:", f"-{_money(d['amount'])}")
            stub += "\n" + line("  Total Post-Tax Deductions:",
                                f"-{_money(sum(d['amount'] for d in post_tax))}")

        stub += "\n" + divider("=")
        stub += "\n" + line("NET PAY:", _money(e["net_pay"]))
        stub += "\n" + divider("=")

        self.stub_display.setPlainText(stub)

    # ── YTD Report data ──────────────────────────────────────────────────────

    def _refresh_ytd_emp_combo(self):
        conn = get_db()
        emps = conn.execute(
            "SELECT id, first_name, last_name FROM people ORDER BY last_name, first_name"
        ).fetchall()
        conn.close()
        self.ytd_emp_filter.blockSignals(True)
        self.ytd_emp_filter.clear()
        self.ytd_emp_filter.addItem("All Employees", None)
        for e in emps:
            self.ytd_emp_filter.addItem(f"{e['last_name']}, {e['first_name']}", e["id"])
        self.ytd_emp_filter.blockSignals(False)

    def _refresh_ytd(self):
        year = int(self.ytd_year.currentText())
        pid = self.ytd_emp_filter.currentData()

        q = """
            SELECT p.first_name, p.last_name,
                   COUNT(DISTINCT pe.run_id) AS run_count,
                   SUM(pe.regular_hours)       AS reg_hrs,
                   SUM(pe.overtime_hours)       AS ot_hrs,
                   SUM(pe.gross_pay)            AS gross,
                   SUM(pe.pre_tax_deductions)   AS pre_deds,
                   SUM(pe.federal_tax)          AS fed,
                   SUM(pe.state_tax)            AS state,
                   SUM(pe.social_security)      AS ss,
                   SUM(pe.medicare)             AS med,
                   SUM(pe.net_pay)              AS net
            FROM payroll_entry pe
            JOIN people p      ON p.id=pe.people_id
            JOIN payroll_run pr ON pr.id=pe.run_id
            WHERE strftime('%Y', pr.period_start)=%s
        """
        params = [str(year)]
        if pid:
            q += " AND pe.people_id=%s"
            params.append(pid)
        q += " GROUP BY pe.people_id ORDER BY p.last_name, p.first_name"

        conn = get_db()
        rows = conn.execute(q, params).fetchall()
        conn.close()

        self.ytd_tbl.setRowCount(0)
        totals = {k: 0.0 for k in ["reg_hrs", "ot_hrs", "gross", "pre_deds", "fed", "state", "ss", "med", "net"]}
        run_count_total = 0

        for row in rows:
            r = self.ytd_tbl.rowCount()
            self.ytd_tbl.insertRow(r)
            al = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            ac = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
            self.ytd_tbl.setItem(r, 0, _ro(f"{row['last_name']}, {row['first_name']}", al))
            self.ytd_tbl.setItem(r, 1, _ro(str(row["run_count"]), ac))
            self.ytd_tbl.setItem(r, 2, _ro(f"{(row['reg_hrs'] or 0):.2f}"))
            self.ytd_tbl.setItem(r, 3, _ro(f"{(row['ot_hrs'] or 0):.2f}"))
            self.ytd_tbl.setItem(r, 4, _ro(_money(row["gross"] or 0)))
            self.ytd_tbl.setItem(r, 5, _ro(_money(row["pre_deds"] or 0)))
            self.ytd_tbl.setItem(r, 6, _ro(_money(row["fed"] or 0)))
            self.ytd_tbl.setItem(r, 7, _ro(_money(row["state"] or 0)))
            self.ytd_tbl.setItem(r, 8, _ro(_money(row["ss"] or 0)))
            self.ytd_tbl.setItem(r, 9, _ro(_money(row["med"] or 0)))
            self.ytd_tbl.setItem(r, 10, _ro(_money(row["net"] or 0)))
            for key in totals:
                totals[key] += row[key] or 0.0
            run_count_total += row["run_count"]

        # Totals row
        if self.ytd_tbl.rowCount():
            r = self.ytd_tbl.rowCount()
            self.ytd_tbl.insertRow(r)
            bold = QtGui.QFont()
            bold.setBold(True)
            totals_row = [
                ("TOTALS", QtCore.Qt.AlignmentFlag.AlignLeft),
                (str(run_count_total), QtCore.Qt.AlignmentFlag.AlignCenter),
                (f"{totals['reg_hrs']:.2f}", QtCore.Qt.AlignmentFlag.AlignRight),
                (f"{totals['ot_hrs']:.2f}", QtCore.Qt.AlignmentFlag.AlignRight),
                (_money(totals["gross"]), QtCore.Qt.AlignmentFlag.AlignRight),
                (_money(totals["pre_deds"]), QtCore.Qt.AlignmentFlag.AlignRight),
                (_money(totals["fed"]), QtCore.Qt.AlignmentFlag.AlignRight),
                (_money(totals["state"]), QtCore.Qt.AlignmentFlag.AlignRight),
                (_money(totals["ss"]), QtCore.Qt.AlignmentFlag.AlignRight),
                (_money(totals["med"]), QtCore.Qt.AlignmentFlag.AlignRight),
                (_money(totals["net"]), QtCore.Qt.AlignmentFlag.AlignRight),
            ]
            for c, (val, align) in enumerate(totals_row):
                it = _ro(val, align | QtCore.Qt.AlignmentFlag.AlignVCenter)
                it.setFont(bold)
                it.setBackground(QtGui.QColor(200, 230, 255))
                self.ytd_tbl.setItem(r, c, it)

        self.ytd_totals_lbl.setText(
            f"Year: {year}  |  Employees: {self.ytd_tbl.rowCount() - (1 if self.ytd_tbl.rowCount() else 0)}  |  "
            f"Total Gross: {_money(totals['gross'])}  |  "
            f"Total Deductions: {_money(totals['pre_deds'])}  |  "
            f"Total Net: {_money(totals['net'])}"
        )

    # ── History data ─────────────────────────────────────────────────────────

    def _load_history(self):
        conn = get_db()
        runs = conn.execute("""
            SELECT pr.id, pr.run_date, pr.period_start, pr.period_end,
                   COUNT(pe.id) AS emp_count,
                   COALESCE(SUM(pe.gross_pay), 0) AS total_gross
            FROM payroll_run pr
            LEFT JOIN payroll_entry pe ON pe.run_id=pr.id
            GROUP BY pr.id
            ORDER BY pr.run_date DESC
        """).fetchall()
        conn.close()

        self.hist_runs_table.setRowCount(0)
        self._history_run_ids = []
        for run in runs:
            r = self.hist_runs_table.rowCount()
            self.hist_runs_table.insertRow(r)
            self._history_run_ids.append(run["id"])
            try:
                rd = datetime.strptime(run["run_date"], DT_FMT).strftime("%m/%d/%Y")
            except ValueError:
                rd = run["run_date"]
            period = f"{run['period_start']}  –  {run['period_end']}"
            al = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            ac = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
            for col, (val, align) in enumerate([(rd, ac), (period, al),
                                                (str(run["emp_count"]), ac),
                                                (_money(run["total_gross"]), QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)]):
                self.hist_runs_table.setItem(r, col, _ro(val, align))

        self.hist_detail_table.setRowCount(0)
        self.hist_detail_lbl.setText("Select a run to view detail")
        self.hist_totals_lbl.setText("")

    def _on_history_run_clicked(self, row, _col):
        if row < 0 or row >= len(self._history_run_ids):
            return
        run_id = self._history_run_ids[row]
        conn = get_db()
        run = conn.execute("SELECT * FROM payroll_run WHERE id=%s", (run_id,)).fetchone()
        entries = conn.execute("""
            SELECT p.first_name, p.last_name, pe.*
            FROM payroll_entry pe JOIN people p ON p.id=pe.people_id
            WHERE pe.run_id=%s
            ORDER BY p.last_name, p.first_name
        """, (run_id,)).fetchall()
        conn.close()

        self.hist_detail_lbl.setText(
            f"Run: {run['period_start']} – {run['period_end']}   "
            f"({run['pay_frequency']}, Fed {_pct(run['federal_tax_rate'])}, "
            f"State {_pct(run['state_tax_rate'])})"
        )
        self.hist_detail_table.setRowCount(0)
        total_gross = total_net = 0.0
        al = QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        ar = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        for entry in entries:
            r = self.hist_detail_table.rowCount()
            self.hist_detail_table.insertRow(r)
            name = f"{entry['last_name']}, {entry['first_name']}"
            pre = entry["pre_tax_deductions"] if "pre_tax_deductions" in entry.keys() else 0.0
            post = entry["post_tax_deductions"] if "post_tax_deductions" in entry.keys() else 0.0
            for col, (val, align) in enumerate([
                (name, al),
                (f"{entry['regular_hours']:.2f}", ar),
                (f"{entry['overtime_hours']:.2f}", ar),
                (_money(entry["gross_pay"]), ar),
                (_money(pre or 0.0), ar),
                (_money(entry["federal_tax"]), ar),
                (_money(entry["state_tax"]), ar),
                (_money(entry["social_security"]), ar),
                (_money(entry["medicare"]), ar),
                (_money(post or 0.0), ar),
                (_money(entry["net_pay"]), ar),
            ]):
                self.hist_detail_table.setItem(r, col, _ro(val, align))
            total_gross += entry["gross_pay"]
            total_net += entry["net_pay"]

        self.hist_totals_lbl.setText(
            f"Total Gross: {_money(total_gross)}    Total Net: {_money(total_net)}"
            f"    Employees: {len(entries)}"
        )

    def _on_void_run(self):
        row = self.hist_runs_table.currentRow()
        if row < 0 or row >= len(self._history_run_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a payroll run first.")
            return
        run_id = self._history_run_ids[row]
        if QtWidgets.QMessageBox.question(
            self, "Void Run", "Permanently delete this payroll run and all its entries%s",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        ) == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM payroll_entry WHERE run_id=%s", (run_id,))
            conn.execute("DELETE FROM payroll_run   WHERE id=%s", (run_id,))
            conn.commit()
            conn.close()
            self._load_history()

    # ── Tab change ───────────────────────────────────────────────────────────

    def _on_tab_change(self, idx):
        if idx == 1:   # Deductions
            self._refresh_ded_types()
            self._refresh_emp_filter_combo()
            self._refresh_emp_deductions()
        elif idx == 3:  # Pay Stubs
            self._refresh_stub_run_combo()
        elif idx == 4:  # YTD
            self._refresh_ytd_emp_combo()
            self._refresh_ytd()


class PayrollDept(QtWidgets.QMainWindow):
    def __init__(self, initial_tab=None):
        super().__init__()
        self.setWindowTitle("Payroll Department")
        self.resize(1280, 740)
        _apply_blue_palette(self)
        self.setCentralWidget(PayrollDeptWidget(initial_tab=initial_tab))


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = PayrollDept(sys.argv[1] if len(sys.argv) > 1 else None)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
