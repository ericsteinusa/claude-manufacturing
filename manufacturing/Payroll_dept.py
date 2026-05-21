import sys
import sqlite3
import os
from datetime import datetime
from PyQt6 import QtCore, QtGui, QtWidgets
from gl_utils import post_gl_entry

DB_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "company.db")
SS_RATE      = 0.062
MEDICARE_RATE = 0.0145
DT_FMT       = "%Y-%m-%d %H:%M:%S"

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
LABEL_STYLE  = "color: white; font-size: 13px;"
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white; border:2px solid black; padding:6px 18px;"
    " border-bottom:none; border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255); font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)

FREQ_DIVISORS = {"Weekly": 52, "Bi-Weekly": 26, "Semi-Monthly": 24, "Monthly": 12}

# ── DB ─────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employee_pay (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            people_id      INTEGER NOT NULL UNIQUE REFERENCES people(id),
            pay_type       TEXT    NOT NULL DEFAULT 'hourly',
            pay_rate       REAL    NOT NULL DEFAULT 0.0,
            effective_date TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_run (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            period_start     TEXT NOT NULL,
            period_end       TEXT NOT NULL,
            run_date         TEXT NOT NULL,
            pay_frequency    TEXT NOT NULL,
            federal_tax_rate REAL NOT NULL,
            state_tax_rate   REAL NOT NULL,
            status           TEXT NOT NULL DEFAULT 'processed'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_entry (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id         INTEGER NOT NULL REFERENCES payroll_run(id),
            people_id      INTEGER NOT NULL REFERENCES people(id),
            regular_hours  REAL NOT NULL DEFAULT 0.0,
            overtime_hours REAL NOT NULL DEFAULT 0.0,
            gross_pay      REAL NOT NULL DEFAULT 0.0,
            federal_tax    REAL NOT NULL DEFAULT 0.0,
            state_tax      REAL NOT NULL DEFAULT 0.0,
            social_security REAL NOT NULL DEFAULT 0.0,
            medicare       REAL NOT NULL DEFAULT 0.0,
            net_pay        REAL NOT NULL DEFAULT 0.0
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

# ── Pay calculation helpers ────────────────────────────────────────────────

def _hours_from_timeclock(people_id, start_str, end_str):
    """Return (regular_hours, overtime_hours) for the period, OT calculated per ISO week."""
    conn = get_db()
    rows = conn.execute("""
        SELECT clock_in, clock_out FROM time_clock
        WHERE people_id = ? AND clock_in >= ? AND clock_in <= ?
          AND clock_out IS NOT NULL
    """, (people_id, start_str + " 00:00:00", end_str + " 23:59:59")).fetchall()
    conn.close()

    weekly: dict = {}
    for row in rows:
        try:
            t_in  = datetime.strptime(row["clock_in"],  DT_FMT)
            t_out = datetime.strptime(row["clock_out"], DT_FMT)
            hrs   = max(0.0, (t_out - t_in).total_seconds() / 3600)
            week  = t_in.isocalendar()[:2]
            weekly[week] = weekly.get(week, 0.0) + hrs
        except ValueError:
            pass

    reg = ot = 0.0
    for wk_hrs in weekly.values():
        if wk_hrs > 40:
            reg += 40.0
            ot  += wk_hrs - 40.0
        else:
            reg += wk_hrs
    return round(reg, 2), round(ot, 2)


def _calc_pay(pay_type, pay_rate, reg_hrs, ot_hrs, fed_rate, state_rate, pay_freq):
    """Return (gross, fed_tax, state_tax, ss, medicare, net)."""
    if pay_type == "hourly":
        gross = pay_rate * reg_hrs + pay_rate * 1.5 * ot_hrs
    else:
        gross = pay_rate / FREQ_DIVISORS.get(pay_freq, 26)
    fed   = gross * fed_rate
    state = gross * state_rate
    ss    = gross * SS_RATE
    med   = gross * MEDICARE_RATE
    net   = max(0.0, gross - fed - state - ss - med)
    return gross, fed, state, ss, med, net


def _money(v):   return f"${v:,.2f}"
def _pct(v):     return f"{v * 100:.1f}%"

# ── Non-editable / editable table item helpers ────────────────────────────

def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter):
    item = QtWidgets.QTableWidgetItem(text)
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(align)
    return item


def _rw(text):
    item = QtWidgets.QTableWidgetItem(text)
    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return item


# ── Main window ────────────────────────────────────────────────────────────

_TAB_KEYS = {'pay': 0, 'payroll': 0}

class PayrollDept(QtWidgets.QMainWindow):

    # column indices for the run-payroll table
    _C_EMP  = 0; _C_TYPE = 1; _C_RATE = 2; _C_REG  = 3; _C_OT   = 4
    _C_GROSS= 5; _C_FED  = 6; _C_ST   = 7; _C_SS   = 8; _C_MED  = 9; _C_NET  = 10

    def __init__(self, initial_tab=None):
        super().__init__()
        self.setWindowTitle("Payroll Department")
        self.resize(1200, 700)
        _apply_blue_palette(self)
        self._pay_rate_row_ids  = []  # people_id per row in pay-rates tab
        self._run_people_ids    = []  # people_id per row in run-payroll tab
        self._history_run_ids   = []  # run_id per row in history left table
        self._build_ui()
        self._load_pay_rates()
        self._load_history()
        if initial_tab in _TAB_KEYS:
            self.tabs.setCurrentIndex(_TAB_KEYS[initial_tab])

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        outer.addWidget(self.tabs)
        self.tabs.addTab(self._build_pay_rates_tab(),   "Pay Rates")
        self.tabs.addTab(self._build_run_payroll_tab(), "Run Payroll")
        self.tabs.addTab(self._build_history_tab(),     "Payroll History")

    # ── Pay Rates tab ──────────────────────────────────────────────────────

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

        # Form
        form_grp = QtWidgets.QGroupBox("Employee Pay Setup")
        form_grp.setStyleSheet(
            "QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;}")
        fg = QtWidgets.QGridLayout(form_grp)
        fg.setSpacing(8)

        def lbl(t):
            l = QtWidgets.QLabel(t); l.setStyleSheet(LABEL_STYLE); return l

        self.pr_emp_combo = QtWidgets.QComboBox()
        self.pr_emp_combo.setStyleSheet(COMBO_STYLE)
        self.pr_emp_combo.setMinimumWidth(220)

        self.pr_type_combo = QtWidgets.QComboBox()
        self.pr_type_combo.setStyleSheet(COMBO_STYLE)
        self.pr_type_combo.addItems(["hourly", "salary"])
        self.pr_type_combo.currentTextChanged.connect(self._on_pr_type_changed)

        self.pr_rate_spin = QtWidgets.QDoubleSpinBox()
        self.pr_rate_spin.setStyleSheet(SPIN_STYLE)
        self.pr_rate_spin.setRange(0, 9999999)
        self.pr_rate_spin.setDecimals(2)
        self.pr_rate_spin.setPrefix("$ ")

        self.pr_date_edit = QtWidgets.QDateEdit()
        self.pr_date_edit.setStyleSheet(DATE_STYLE)
        self.pr_date_edit.setCalendarPopup(True)
        self.pr_date_edit.setDate(QtCore.QDate.currentDate())
        self.pr_date_edit.setDisplayFormat("MM/dd/yyyy")

        self.pr_rate_lbl = QtWidgets.QLabel("Rate ($/hr):")
        self.pr_rate_lbl.setStyleSheet(LABEL_STYLE)

        fg.addWidget(lbl("Employee:"),       0, 0); fg.addWidget(self.pr_emp_combo,   0, 1)
        fg.addWidget(lbl("Pay Type:"),       0, 2); fg.addWidget(self.pr_type_combo,  0, 3)
        fg.addWidget(self.pr_rate_lbl,       0, 4); fg.addWidget(self.pr_rate_spin,   0, 5)
        fg.addWidget(lbl("Effective Date:"), 0, 6); fg.addWidget(self.pr_date_edit,   0, 7)
        layout.addWidget(form_grp)

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Save / Update", self._on_pr_save),
                           ("Delete Rate",   self._on_pr_delete),
                           ("Clear",         self._pr_clear_form)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE); b.setFixedHeight(34)
            b.clicked.connect(slot); btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    def _on_pr_type_changed(self, t):
        self.pr_rate_lbl.setText("Rate ($/hr):" if t == "hourly" else "Annual Salary ($):")

    # ── Run Payroll tab ────────────────────────────────────────────────────

    def _build_run_payroll_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Config bar
        cfg_grp = QtWidgets.QGroupBox("Payroll Period & Tax Rates")
        cfg_grp.setStyleSheet(
            "QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;}")
        cfg = QtWidgets.QHBoxLayout(cfg_grp)
        cfg.setSpacing(10)

        def lbl(t):
            l = QtWidgets.QLabel(t); l.setStyleSheet(LABEL_STYLE); return l

        self.run_from = QtWidgets.QDateEdit()
        self.run_from.setStyleSheet(DATE_STYLE); self.run_from.setCalendarPopup(True)
        self.run_from.setDate(QtCore.QDate.currentDate().addDays(-13))
        self.run_from.setDisplayFormat("MM/dd/yyyy")

        self.run_to = QtWidgets.QDateEdit()
        self.run_to.setStyleSheet(DATE_STYLE); self.run_to.setCalendarPopup(True)
        self.run_to.setDate(QtCore.QDate.currentDate())
        self.run_to.setDisplayFormat("MM/dd/yyyy")

        self.run_freq = QtWidgets.QComboBox()
        self.run_freq.setStyleSheet(COMBO_STYLE)
        self.run_freq.addItems(list(FREQ_DIVISORS.keys()))
        self.run_freq.setCurrentText("Bi-Weekly")

        self.run_fed_spin = QtWidgets.QDoubleSpinBox()
        self.run_fed_spin.setStyleSheet(SPIN_STYLE)
        self.run_fed_spin.setRange(0, 50); self.run_fed_spin.setDecimals(1)
        self.run_fed_spin.setSuffix(" %"); self.run_fed_spin.setValue(22.0)

        self.run_state_spin = QtWidgets.QDoubleSpinBox()
        self.run_state_spin.setStyleSheet(SPIN_STYLE)
        self.run_state_spin.setRange(0, 20); self.run_state_spin.setDecimals(1)
        self.run_state_spin.setSuffix(" %"); self.run_state_spin.setValue(5.0)

        for widget, label_text in (
            (self.run_from,       "Period From:"),
            (self.run_to,         "To:"),
            (self.run_freq,       "Frequency:"),
            (self.run_fed_spin,   "Federal Tax:"),
            (self.run_state_spin, "State Tax:"),
        ):
            cfg.addWidget(lbl(label_text))
            cfg.addWidget(widget)

        cfg.addSpacing(10)
        load_btn = QtWidgets.QPushButton("Load Employees")
        load_btn.setStyleSheet(BUTTON_STYLE); load_btn.setFixedHeight(30)
        load_btn.clicked.connect(self._on_load_payroll)
        cfg.addWidget(load_btn)
        cfg.addStretch()
        layout.addWidget(cfg_grp)

        # Payroll preview table
        note = QtWidgets.QLabel(
            "Reg Hours and OT Hours are editable — adjust if needed, then click Calculate.")
        note.setStyleSheet("color: rgb(200,220,255); font-size: 11px;")
        layout.addWidget(note)

        self.run_table = QtWidgets.QTableWidget()
        self.run_table.setColumnCount(11)
        self.run_table.setHorizontalHeaderLabels([
            "Employee", "Pay Type", "Rate",
            "Reg Hrs", "OT Hrs",
            "Gross Pay", "Fed Tax", "State Tax", "SS", "Medicare", "Net Pay",
        ])
        hh = self.run_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in range(1, 11):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.run_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.run_table.setAlternatingRowColors(True)
        self.run_table.verticalHeader().setVisible(False)
        layout.addWidget(self.run_table, stretch=1)

        # Bottom bar
        bot = QtWidgets.QHBoxLayout()
        calc_btn = QtWidgets.QPushButton("Calculate")
        calc_btn.setStyleSheet(BUTTON_STYLE); calc_btn.setFixedHeight(34)
        calc_btn.clicked.connect(self._on_calculate_payroll)
        bot.addWidget(calc_btn)

        self.save_run_btn = QtWidgets.QPushButton("Save Payroll Run")
        self.save_run_btn.setStyleSheet(BUTTON_STYLE); self.save_run_btn.setFixedHeight(34)
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

    # ── History tab ────────────────────────────────────────────────────────

    def _build_history_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle{background: white; width: 3px;}")

        # Left — run list
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
        void_btn.setStyleSheet(BUTTON_STYLE); void_btn.setFixedHeight(32)
        void_btn.clicked.connect(self._on_void_run)
        lv.addWidget(void_btn)
        splitter.addWidget(left)

        # Right — entry detail
        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(4, 0, 0, 0)
        self.hist_detail_lbl = QtWidgets.QLabel("Select a run to view detail")
        self.hist_detail_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        rv.addWidget(self.hist_detail_lbl)

        self.hist_detail_table = QtWidgets.QTableWidget()
        self.hist_detail_table.setColumnCount(9)
        self.hist_detail_table.setHorizontalHeaderLabels([
            "Employee", "Reg Hrs", "OT Hrs",
            "Gross", "Fed Tax", "State Tax", "SS", "Medicare", "Net Pay",
        ])
        hd = self.hist_detail_table.horizontalHeader()
        hd.setStyleSheet("color: black; font-weight: bold;")
        hd.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in range(1, 9):
            hd.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.hist_detail_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hist_detail_table.setAlternatingRowColors(True)
        self.hist_detail_table.verticalHeader().setVisible(False)
        rv.addWidget(self.hist_detail_table, stretch=1)

        self.hist_totals_lbl = QtWidgets.QLabel("")
        self.hist_totals_lbl.setStyleSheet("color: white; font-size: 12px;")
        rv.addWidget(self.hist_totals_lbl)
        splitter.addWidget(right)

        splitter.setSizes([300, 800])
        layout.addWidget(splitter)
        return w

    # ── Pay Rates data ─────────────────────────────────────────────────────

    def _load_pay_rates(self):
        conn = get_db()
        employees = conn.execute(
            "SELECT id, first_name, last_name, emp_id FROM people ORDER BY last_name, first_name"
        ).fetchall()
        pay_map = {r["people_id"]: r for r in conn.execute("SELECT * FROM employee_pay").fetchall()}
        conn.close()

        self.pr_emp_combo.blockSignals(True)
        self.pr_emp_combo.clear()
        self.pr_emp_combo.addItem("-- select --", None)
        for e in employees:
            label = f"{e['last_name']}, {e['first_name']}"
            if e["emp_id"]: label += f"  (ID {e['emp_id']})"
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
            emp_id_str = str(e["emp_id"]) if e["emp_id"] else ""
            if pay:
                rate_str = (f"${pay['pay_rate']:.2f}/hr" if pay["pay_type"] == "hourly"
                            else f"${pay['pay_rate']:,.0f}/yr")
                eff_str = pay["effective_date"]
            else:
                rate_str = "(not set)"; eff_str = ""
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
        pay = conn.execute("SELECT * FROM employee_pay WHERE people_id=?", (pid,)).fetchone()
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
            VALUES (?, ?, ?, ?)
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
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", "Remove pay rate for this employee?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM employee_pay WHERE people_id=?", (pid,))
            conn.commit()
            conn.close()
            self._pr_clear_form()
            self._load_pay_rates()

    # ── Run Payroll data ───────────────────────────────────────────────────

    def _on_load_payroll(self):
        start_str = self.run_from.date().toString("yyyy-MM-dd")
        end_str   = self.run_to.date().toString("yyyy-MM-dd")
        if start_str > end_str:
            QtWidgets.QMessageBox.warning(self, "Invalid Range", "From date must be before To date.")
            return

        fed_rate   = self.run_fed_spin.value()   / 100
        state_rate = self.run_state_spin.value() / 100
        freq       = self.run_freq.currentText()

        conn = get_db()
        employees = conn.execute(
            "SELECT p.id, p.first_name, p.last_name, ep.pay_type, ep.pay_rate "
            "FROM people p LEFT JOIN employee_pay ep ON ep.people_id=p.id "
            "ORDER BY p.last_name, p.first_name"
        ).fetchall()
        conn.close()

        self.run_table.setRowCount(0)
        self._run_people_ids = []

        for e in employees:
            pid      = e["id"]
            pay_type = e["pay_type"] or "hourly"
            pay_rate = e["pay_rate"] or 0.0
            reg, ot  = _hours_from_timeclock(pid, start_str, end_str)
            gross, fed, st, ss, med, net = _calc_pay(
                pay_type, pay_rate, reg, ot, fed_rate, state_rate, freq)

            r = self.run_table.rowCount()
            self.run_table.insertRow(r)
            self._run_people_ids.append(pid)

            name     = f"{e['last_name']}, {e['first_name']}"
            rate_str = (f"${pay_rate:.2f}/hr" if pay_type == "hourly"
                        else f"${pay_rate:,.0f}/yr")

            self.run_table.setItem(r, self._C_EMP,  _ro(name, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.run_table.setItem(r, self._C_TYPE, _ro(pay_type,         QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter))
            self.run_table.setItem(r, self._C_RATE, _ro(rate_str))
            self.run_table.setItem(r, self._C_REG,  _rw(f"{reg:.2f}"))
            self.run_table.setItem(r, self._C_OT,   _rw(f"{ot:.2f}"))
            self.run_table.setItem(r, self._C_GROSS, _ro(_money(gross)))
            self.run_table.setItem(r, self._C_FED,   _ro(_money(fed)))
            self.run_table.setItem(r, self._C_ST,    _ro(_money(st)))
            self.run_table.setItem(r, self._C_SS,    _ro(_money(ss)))
            self.run_table.setItem(r, self._C_MED,   _ro(_money(med)))
            self.run_table.setItem(r, self._C_NET,   _ro(_money(net)))

        self._update_run_totals()
        self.save_run_btn.setEnabled(self.run_table.rowCount() > 0)

    def _on_calculate_payroll(self):
        if self.run_table.rowCount() == 0:
            QtWidgets.QMessageBox.warning(self, "No Data", "Load employees first.")
            return
        fed_rate   = self.run_fed_spin.value()   / 100
        state_rate = self.run_state_spin.value() / 100
        freq       = self.run_freq.currentText()

        for r in range(self.run_table.rowCount()):
            type_item = self.run_table.item(r, self._C_TYPE)
            rate_item = self.run_table.item(r, self._C_RATE)
            reg_item  = self.run_table.item(r, self._C_REG)
            ot_item   = self.run_table.item(r, self._C_OT)
            if not all((type_item, rate_item, reg_item, ot_item)):
                continue

            pay_type = type_item.text()
            rate_str = rate_item.text().replace("$", "").replace(",", "").replace("/hr", "").replace("/yr", "")
            try:
                pay_rate = float(rate_str)
                reg_hrs  = float(reg_item.text())
                ot_hrs   = float(ot_item.text())
            except ValueError:
                continue

            if reg_hrs < 0 or ot_hrs < 0:
                QtWidgets.QMessageBox.warning(self, "Invalid", f"Row {r+1}: hours cannot be negative.")
                return

            gross, fed, st, ss, med, net = _calc_pay(
                pay_type, pay_rate, reg_hrs, ot_hrs, fed_rate, state_rate, freq)

            self.run_table.setItem(r, self._C_GROSS, _ro(_money(gross)))
            self.run_table.setItem(r, self._C_FED,   _ro(_money(fed)))
            self.run_table.setItem(r, self._C_ST,    _ro(_money(st)))
            self.run_table.setItem(r, self._C_SS,    _ro(_money(ss)))
            self.run_table.setItem(r, self._C_MED,   _ro(_money(med)))
            self.run_table.setItem(r, self._C_NET,   _ro(_money(net)))

        self._update_run_totals()

    def _update_run_totals(self):
        total_gross = total_net = 0.0
        for r in range(self.run_table.rowCount()):
            g = self.run_table.item(r, self._C_GROSS)
            n = self.run_table.item(r, self._C_NET)
            if g: total_gross += float(g.text().replace("$","").replace(",",""))
            if n: total_net   += float(n.text().replace("$","").replace(",",""))
        self.run_totals_lbl.setText(
            f"Total Gross: {_money(total_gross)}    Total Net: {_money(total_net)}"
            f"    Employees: {self.run_table.rowCount()}"
        )

    def _on_save_payroll_run(self):
        if self.run_table.rowCount() == 0:
            return
        start_str  = self.run_from.date().toString("yyyy-MM-dd")
        end_str    = self.run_to.date().toString("yyyy-MM-dd")
        fed_rate   = self.run_fed_spin.value()   / 100
        state_rate = self.run_state_spin.value() / 100
        freq       = self.run_freq.currentText()

        reply = QtWidgets.QMessageBox.question(
            self, "Save Payroll Run",
            f"Save payroll run for period {start_str} – {end_str}?\n"
            f"({self.run_table.rowCount()} employees)",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        conn = get_db()
        cur = conn.execute("""
            INSERT INTO payroll_run (period_start, period_end, run_date, pay_frequency,
                                     federal_tax_rate, state_tax_rate, status)
            VALUES (?, ?, ?, ?, ?, ?, 'processed')
        """, (start_str, end_str, datetime.now().strftime(DT_FMT), freq, fed_rate, state_rate))
        run_id = cur.lastrowid

        for r, pid in enumerate(self._run_people_ids):
            def _v(col): return float(self.run_table.item(r, col).text().replace("$","").replace(",",""))
            conn.execute("""
                INSERT INTO payroll_entry
                    (run_id, people_id, regular_hours, overtime_hours,
                     gross_pay, federal_tax, state_tax, social_security, medicare, net_pay)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (run_id, pid,
                  float(self.run_table.item(r, self._C_REG).text()),
                  float(self.run_table.item(r, self._C_OT).text()),
                  _v(self._C_GROSS), _v(self._C_FED), _v(self._C_ST),
                  _v(self._C_SS),    _v(self._C_MED), _v(self._C_NET)))

        conn.commit()
        conn.close()

        # Post draft GL entry for the full payroll run
        # DR: Salaries & Wages (6000) — total gross
        # CR: Cash (1000)            — total net pay
        # CR: Payroll Liabilities (2200) — total withholding
        total_gross = total_net = 0.0
        for r in range(self.run_table.rowCount()):
            def _v(col): return float(self.run_table.item(r, col).text().replace("$","").replace(",",""))
            total_gross += _v(self._C_GROSS)
            total_net   += _v(self._C_NET)
        total_withholding = round(total_gross - total_net, 2)
        ref = f"PAYROLL-{start_str}"
        post_gl_entry(
            journal_date=end_str,
            reference=ref,
            description=f"Payroll run {start_str} – {end_str} ({freq})",
            lines=[
                ("6000", round(total_gross, 2), 0.0,                    "Gross wages"),
                ("1000", 0.0, round(total_net, 2),                      "Net pay disbursed"),
                ("2200", 0.0, total_withholding,                        "Taxes & withholding"),
            ],
        )

        self.run_table.setRowCount(0)
        self._run_people_ids = []
        self.save_run_btn.setEnabled(False)
        self.run_totals_lbl.setText("")
        self._load_history()
        QtWidgets.QMessageBox.information(self, "Saved", "Payroll run saved successfully.")

    # ── History data ───────────────────────────────────────────────────────

    def _load_history(self):
        conn = get_db()
        runs = conn.execute("""
            SELECT pr.id, pr.run_date, pr.period_start, pr.period_end,
                   COUNT(pe.id) AS emp_count,
                   COALESCE(SUM(pe.gross_pay), 0) AS total_gross
            FROM payroll_run pr
            LEFT JOIN payroll_entry pe ON pe.run_id = pr.id
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
            for col, val in enumerate([rd, period, str(run["emp_count"]), _money(run["total_gross"])]):
                self.hist_runs_table.setItem(r, col, _ro(val,
                    QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
                    if col == 1 else
                    QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter))

        self.hist_detail_table.setRowCount(0)
        self.hist_detail_lbl.setText("Select a run to view detail")
        self.hist_totals_lbl.setText("")

    def _on_history_run_clicked(self, row, _col):
        if row < 0 or row >= len(self._history_run_ids):
            return
        run_id = self._history_run_ids[row]
        conn = get_db()
        run = conn.execute("SELECT * FROM payroll_run WHERE id=?", (run_id,)).fetchone()
        entries = conn.execute("""
            SELECT p.first_name, p.last_name, pe.*
            FROM payroll_entry pe JOIN people p ON p.id = pe.people_id
            WHERE pe.run_id=?
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
        for entry in entries:
            r = self.hist_detail_table.rowCount()
            self.hist_detail_table.insertRow(r)
            name = f"{entry['last_name']}, {entry['first_name']}"
            for col, val in enumerate([
                name,
                f"{entry['regular_hours']:.2f}",
                f"{entry['overtime_hours']:.2f}",
                _money(entry["gross_pay"]),
                _money(entry["federal_tax"]),
                _money(entry["state_tax"]),
                _money(entry["social_security"]),
                _money(entry["medicare"]),
                _money(entry["net_pay"]),
            ]):
                self.hist_detail_table.setItem(r, col, _ro(val,
                    QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
                    if col == 0 else
                    QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter))
            total_gross += entry["gross_pay"]
            total_net   += entry["net_pay"]

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
        reply = QtWidgets.QMessageBox.question(
            self, "Void Run",
            "Permanently delete this payroll run and all its entries?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM payroll_entry WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM payroll_run   WHERE id=?",     (run_id,))
            conn.commit()
            conn.close()
            self._load_history()


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = PayrollDept(sys.argv[1] if len(sys.argv) > 1 else None)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
