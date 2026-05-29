import sys
import psycopg2
from .db_connection import get_db_connection
from PyQt6 import QtCore, QtGui, QtWidgets


BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE = "QLineEdit{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 6px;}"
COMBO_STYLE = (
    "QComboBox{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 6px;}"
    "QComboBox QAbstractItemView{background-color: white;}"
)
LABEL_STYLE = "color: white; font-size: 13px;"

RUN_COLORS = {
    "draft":      "#ffffff",
    "processing": "#cce5ff",
    "completed":  "#d4edda",
    "cancelled":  "#dcdcdc",
}

DEFAULT_DEDUCTIONS = [
    ("Federal Income Tax",  "Federal withholding"),
    ("State Income Tax",    "State withholding"),
    ("Social Security",     "FICA Social Security (6.2%)"),
    ("Medicare",            "FICA Medicare (1.45%)"),
    ("Health Insurance",    "Employee health insurance premium"),
    ("401(k)",              "Retirement contribution"),
]


def get_db():
    return get_db_connection()


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_deduction_type (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_run (
            id SERIAL PRIMARY KEY,
            run_number TEXT NOT NULL UNIQUE,
            pay_period_start TEXT,
            pay_period_end TEXT,
            run_date TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_entry (
            id SERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES payroll_run(id),
            people_id INTEGER NOT NULL,
            hours_worked REAL DEFAULT 0,
            hourly_rate REAL DEFAULT 0,
            gross_pay REAL DEFAULT 0,
            net_pay REAL DEFAULT 0,
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_entry_deduction (
            id SERIAL PRIMARY KEY,
            entry_id INTEGER NOT NULL REFERENCES payroll_entry(id),
            deduction_type_id INTEGER NOT NULL REFERENCES payroll_deduction_type(id),
            amount REAL DEFAULT 0
        )
    """)
    # Seed default deduction types
    for name, desc in DEFAULT_DEDUCTIONS:
        conn.execute(
            "INSERT INTO payroll_deduction_type (name, description)"
            " VALUES (%s,%s) ON CONFLICT (name) DO NOTHING",
            (name, desc)
        )
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


def _next_run_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM payroll_run WHERE run_number LIKE %s", (f"PR-{yr}-%",)
    ).fetchone()[0]
    conn.close()
    return f"PR-{yr}-{count + 1:04d}"


def _load_employees():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, first_name, last_name, email FROM people WHERE id > 0"
            " ORDER BY last_name, first_name"
        ).fetchall()
    except psycopg2.OperationalError:
        rows = []
    conn.close()
    return rows


def _load_deduction_types():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name FROM payroll_deduction_type ORDER BY name"
    ).fetchall()
    conn.close()
    return rows


# ── Dialogs ────────────────────────────────────────────────────────────────────

class NewRunDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Payroll Run")
        self.resize(460, 300)
        _apply_blue_palette(self)
        self.run_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.run_num = QtWidgets.QLineEdit(_next_run_num())
        self.run_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Run Number:"), self.run_num)

        # Default to last two weeks
        today = QtCore.QDate.currentDate()
        self.period_start = QtWidgets.QDateEdit(today.addDays(-13))
        self.period_start.setCalendarPopup(True)
        self.period_start.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Period Start:"), self.period_start)

        self.period_end = QtWidgets.QDateEdit(today)
        self.period_end.setCalendarPopup(True)
        self.period_end.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Period End:"), self.period_end)

        self.run_date = QtWidgets.QDateEdit(today)
        self.run_date.setCalendarPopup(True)
        self.run_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Run Date:"), self.run_date)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("draft", "processing"):
            self.status_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

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

    def _on_ok(self):
        run_num = self.run_num.text().strip()
        if not run_num:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Run number is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO payroll_run (run_number, pay_period_start, pay_period_end,"
                " run_date, status, notes) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (run_num,
                 self.period_start.date().toString("yyyy-MM-dd"),
                 self.period_end.date().toString("yyyy-MM-dd"),
                 self.run_date.date().toString("yyyy-MM-dd"),
                 self.status_combo.currentData(),
                 self.notes.text().strip())
            )
            self.run_id = cur.fetchone()['id']
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"Run number '{run_num}' already exists.")
            conn.close()
            return
        conn.close()
        self.accept()


class AddEntryDialog(QtWidgets.QDialog):
    """Add an employee entry to a payroll run."""

    def __init__(self, run_id, run_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Employee — {run_number}")
        self.resize(480, 340)
        _apply_blue_palette(self)
        self._run_id = run_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.emp_combo = QtWidgets.QComboBox()
        self.emp_combo.setStyleSheet(COMBO_STYLE)
        self.emp_combo.setMinimumWidth(220)
        for e in _load_employees():
            name = f"{e['last_name']}, {e['first_name']}"
            self.emp_combo.addItem(name, e["id"])
        layout.addRow(lbl("Employee:"), self.emp_combo)

        self.hours = QtWidgets.QDoubleSpinBox()
        self.hours.setRange(0, 999)
        self.hours.setDecimals(2)
        self.hours.setValue(80)
        self.hours.setStyleSheet(INPUT_STYLE)
        self.hours.valueChanged.connect(self._recalc)
        layout.addRow(lbl("Hours Worked:"), self.hours)

        self.rate = QtWidgets.QDoubleSpinBox()
        self.rate.setRange(0, 9999)
        self.rate.setDecimals(2)
        self.rate.setPrefix("$ ")
        self.rate.setValue(25.00)
        self.rate.setStyleSheet(INPUT_STYLE)
        self.rate.valueChanged.connect(self._recalc)
        layout.addRow(lbl("Hourly Rate:"), self.rate)

        self.gross = QtWidgets.QLineEdit()
        self.gross.setStyleSheet(INPUT_STYLE)
        self.gross.setReadOnly(True)
        layout.addRow(lbl("Gross Pay:"), self.gross)

        # Deductions table
        ded_lbl = QtWidgets.QLabel("Deductions:")
        ded_lbl.setStyleSheet(LABEL_STYLE)
        self._ded_spins = {}
        ded_widget = QtWidgets.QWidget()
        _apply_blue_palette(ded_widget)
        ded_form = QtWidgets.QFormLayout(ded_widget)
        ded_form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        for dt in _load_deduction_types():
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0, 99999)
            spin.setDecimals(2)
            spin.setPrefix("$ ")
            spin.setStyleSheet(INPUT_STYLE)
            spin.valueChanged.connect(self._recalc)
            self._ded_spins[dt["id"]] = spin
            dl = QtWidgets.QLabel(dt["name"] + ":")
            dl.setStyleSheet(LABEL_STYLE)
            ded_form.addRow(dl, spin)
        layout.addRow(ded_lbl, ded_widget)

        self.net = QtWidgets.QLineEdit()
        self.net.setStyleSheet(INPUT_STYLE)
        self.net.setReadOnly(True)
        layout.addRow(lbl("Net Pay:"), self.net)

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
        self._recalc()

    def _recalc(self):
        gross = self.hours.value() * self.rate.value()
        total_ded = sum(s.value() for s in self._ded_spins.values())
        net = gross - total_ded
        self.gross.setText(f"${gross:,.2f}")
        self.net.setText(f"${net:,.2f}")

    def _on_ok(self):
        if not self.emp_combo.count():
            QtWidgets.QMessageBox.warning(self, "No Employees", "No employees available.")
            return
        gross = self.hours.value() * self.rate.value()
        total_ded = sum(s.value() for s in self._ded_spins.values())
        net = gross - total_ded
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO payroll_entry (run_id, people_id, hours_worked, hourly_rate,"
            " gross_pay, net_pay, notes) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (self._run_id, self.emp_combo.currentData(),
             self.hours.value(), self.rate.value(),
             gross, net, self.notes.text().strip())
        )
        entry_id = cur.fetchone()['id']
        for dt_id, spin in self._ded_spins.items():
            if spin.value() > 0:
                conn.execute(
                    "INSERT INTO payroll_entry_deduction (entry_id, deduction_type_id, amount)"
                    " VALUES (%s,%s,%s)",
                    (entry_id, dt_id, spin.value())
                )
        conn.commit()
        conn.close()
        self.accept()


class EntryDeductionsDialog(QtWidgets.QDialog):
    """Read-only view of deductions for a payroll entry."""

    def __init__(self, entry_id, employee_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Deductions — {employee_name}")
        self.resize(400, 300)
        _apply_blue_palette(self)
        vl = QtWidgets.QVBoxLayout(self)
        tbl = QtWidgets.QTableWidget()
        tbl.setColumnCount(2)
        tbl.setHorizontalHeaderLabels(["Deduction", "Amount"])
        hh = tbl.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.setAlternatingRowColors(True)
        conn = get_db()
        rows = conn.execute("""
            SELECT dt.name, ded.amount FROM payroll_entry_deduction ded
            JOIN payroll_deduction_type dt ON dt.id = ded.deduction_type_id
            WHERE ded.entry_id = %s ORDER BY dt.name
        """, (entry_id,)).fetchall()
        conn.close()
        for row in rows:
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, _ro(row["name"]))
            tbl.setItem(r, 1, _ro(f"${row['amount']:,.2f}"))
        vl.addWidget(tbl)
        close = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        vl.addWidget(close)


# ── Main Window ────────────────────────────────────────────────────────────────

class PayrollWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._run_row_ids = []
        self._entry_row_ids = []
        self._selected_run_id = None
        self._selected_run_number = None
        self._selected_entry_id = None
        self._selected_entry_name = None
        self._build_ui()
        init_db()
        self._refresh_runs()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # filter row
        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.setStyleSheet(COMBO_STYLE)
        self.status_filter.addItem("(all)", None)
        for s in ("draft", "processing", "completed", "cancelled"):
            self.status_filter.addItem(s.capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh_runs)
        fr.addWidget(self.status_filter)

        fr.addSpacing(10)
        lbl_f = QtWidgets.QLabel("From:")
        lbl_f.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_f)
        self.date_from = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet(INPUT_STYLE)
        self.date_from.dateChanged.connect(self._refresh_runs)
        fr.addWidget(self.date_from)

        lbl_t = QtWidgets.QLabel("To:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.date_to = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet(INPUT_STYLE)
        self.date_to.dateChanged.connect(self._refresh_runs)
        fr.addWidget(self.date_to)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        # Payroll runs table
        self.run_table = QtWidgets.QTableWidget()
        self.run_table.setColumnCount(7)
        self.run_table.setHorizontalHeaderLabels(
            ["Run #", "Period Start", "Period End", "Run Date",
             "Employees", "Gross Total", "Status"]
        )
        hh = self.run_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        for i in range(7):
            hh.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.run_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.run_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.run_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.run_table.setAlternatingRowColors(True)
        self.run_table.verticalHeader().setVisible(False)
        self.run_table.clicked.connect(self._on_run_clicked)
        splitter.addWidget(self.run_table)

        # Employee entries detail
        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Employee Entries")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.entry_table = QtWidgets.QTableWidget()
        self.entry_table.setColumnCount(6)
        self.entry_table.setHorizontalHeaderLabels(
            ["Employee", "Hours", "Rate", "Gross", "Deductions", "Net Pay"]
        )
        ih = self.entry_table.horizontalHeader()
        ih.setStyleSheet("color: black; font-weight: bold;")
        ih.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            ih.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.entry_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.entry_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.entry_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.entry_table.verticalHeader().setVisible(False)
        self.entry_table.setAlternatingRowColors(True)
        self.entry_table.clicked.connect(self._on_entry_clicked)
        dv.addWidget(self.entry_table)
        splitter.addWidget(detail_w)
        splitter.setSizes([340, 220])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Run",       self._on_new_run),
            ("Add Employee",  self._on_add_entry),
            ("View Deductions", self._on_view_deductions),
            ("Processing",    lambda: self._set_status("processing", "Mark as Processing?")),
            ("Complete",      lambda: self._set_status("completed",  "Mark run as Completed?")),
            ("Cancel Run",    lambda: self._set_status("cancelled",  "Cancel this payroll run?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh_runs(self):
        status = self.status_filter.currentData()
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")

        conds = ["(pr.run_date IS NULL OR pr.run_date BETWEEN %s AND %s)"]
        params = [d_from, d_to]
        if status:
            conds.append("pr.status = %s")
            params.append(status)
        where = " AND ".join(conds)

        conn = get_db()
        try:
            rows = conn.execute(f"""
                SELECT pr.id, pr.run_number, pr.pay_period_start, pr.pay_period_end,
                       pr.run_date, pr.status,
                       COUNT(pe.id) AS emp_count,
                       COALESCE(SUM(pe.gross_pay), 0) AS gross_total
                FROM payroll_run pr
                LEFT JOIN payroll_entry pe ON pe.run_id = pr.id
                WHERE {where}
                GROUP BY pr.id ORDER BY pr.run_date DESC
            """, params).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.run_table.setRowCount(0)
        self._run_row_ids = []
        for row in rows:
            r = self.run_table.rowCount()
            self.run_table.insertRow(r)
            self._run_row_ids.append(row["id"])
            self.run_table.setItem(r, 0, _ro(row["run_number"]))
            self.run_table.setItem(r, 1, _ro(row["pay_period_start"] or ""))
            self.run_table.setItem(r, 2, _ro(row["pay_period_end"] or ""))
            self.run_table.setItem(r, 3, _ro(row["run_date"] or ""))
            self.run_table.setItem(r, 4, _ro(str(row["emp_count"])))
            self.run_table.setItem(r, 5, _ro(f"${row['gross_total']:,.2f}"))
            self.run_table.setItem(r, 6, _ro(row["status"].capitalize()))
            bg = QtGui.QColor(RUN_COLORS.get(row["status"], "#ffffff"))
            for col in range(7):
                self.run_table.item(r, col).setBackground(bg)

        self._selected_run_id = None
        self._selected_run_number = None
        self.entry_table.setRowCount(0)

    def _on_show_all(self):
        self.status_filter.blockSignals(True)
        self.status_filter.setCurrentIndex(0)
        self.status_filter.blockSignals(False)
        self.date_from.blockSignals(True)
        self.date_from.setDate(QtCore.QDate(2000, 1, 1))
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(True)
        self.date_to.setDate(QtCore.QDate.currentDate())
        self.date_to.blockSignals(False)
        self._refresh_runs()

    def _on_run_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._run_row_ids):
            return
        self._selected_run_id = self._run_row_ids[row]
        self._selected_run_number = self.run_table.item(row, 0).text()
        self._selected_entry_id = None
        self._selected_entry_name = None
        self._refresh_entries()

    def _refresh_entries(self):
        self.entry_table.setRowCount(0)
        self._entry_row_ids = []
        if self._selected_run_id is None:
            return
        conn = get_db()
        try:
            entries = conn.execute("""
                SELECT pe.id, pe.people_id, pe.hours_worked, pe.hourly_rate,
                       pe.gross_pay, pe.net_pay,
                       p.first_name, p.last_name,
                       COALESCE(SUM(ded.amount), 0) AS total_deductions
                FROM payroll_entry pe
                JOIN people p ON p.id = pe.people_id
                LEFT JOIN payroll_entry_deduction ded ON ded.entry_id = pe.id
                WHERE pe.run_id = %s
                GROUP BY pe.id, p.first_name, p.last_name
                ORDER BY p.last_name, p.first_name
            """, (self._selected_run_id,)).fetchall()
        except psycopg2.OperationalError:
            entries = []
        conn.close()
        for entry in entries:
            r = self.entry_table.rowCount()
            self.entry_table.insertRow(r)
            self._entry_row_ids.append(entry["id"])
            name = f"{entry['last_name']}, {entry['first_name']}"
            self.entry_table.setItem(r, 0, _ro(name))
            self.entry_table.setItem(r, 1, _ro(f"{entry['hours_worked']:.2f}"))
            self.entry_table.setItem(r, 2, _ro(f"${entry['hourly_rate']:,.2f}"))
            self.entry_table.setItem(r, 3, _ro(f"${entry['gross_pay']:,.2f}"))
            self.entry_table.setItem(r, 4, _ro(f"${entry['total_deductions']:,.2f}"))
            self.entry_table.setItem(r, 5, _ro(f"${entry['net_pay']:,.2f}"))

    def _on_entry_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._entry_row_ids):
            return
        self._selected_entry_id = self._entry_row_ids[row]
        self._selected_entry_name = self.entry_table.item(row, 0).text()

    def _on_new_run(self):
        dlg = NewRunDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_runs()

    def _on_add_entry(self):
        if self._selected_run_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a payroll run first.")
            return
        dlg = AddEntryDialog(self._selected_run_id, self._selected_run_number, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_runs()
            self._refresh_entries()

    def _on_view_deductions(self):
        if self._selected_entry_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection",
                                          "Select an employee entry first.")
            return
        dlg = EntryDeductionsDialog(
            self._selected_entry_id, self._selected_entry_name, self)
        dlg.exec()

    def _set_status(self, new_status, msg):
        if self._selected_run_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a payroll run first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE payroll_run SET status = %s WHERE id = %s",
                         (new_status, self._selected_run_id))
            conn.commit()
            conn.close()
            self._refresh_runs()


class PayrollWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Payroll")
        self.resize(1060, 700)
        _apply_blue_palette(self)
        self.setCentralWidget(PayrollWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = PayrollWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
