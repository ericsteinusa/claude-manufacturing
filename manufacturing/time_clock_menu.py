import sys
import psycopg2
from .db_pg import get_db_connection
from PyQt6 import QtCore, QtGui, QtWidgets


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

TIME_OFF_TYPES = ["Vacation", "Sick", "Personal", "Bereavement", "Other"]
TIME_OFF_COLORS = {
    "pending":  "#fff3cd",
    "approved": "#d4edda",
    "denied":   "#f8d7da",
}


def get_db():
    return get_db_connection()


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS time_clock (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL,
            clock_in TEXT NOT NULL,
            clock_out TEXT,
            hours_worked REAL,
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS time_off_request (
            id SERIAL PRIMARY KEY,
            people_id INTEGER NOT NULL,
            request_date TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            request_type TEXT DEFAULT 'Vacation',
            status TEXT DEFAULT 'pending',
            notes TEXT DEFAULT ''
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
    item.setTextAlignment(
        QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # noqa: E501
    return item


def _load_employees():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, first_name, last_name FROM people"
            " WHERE id > 0 ORDER BY last_name, first_name"
        ).fetchall()
    except psycopg2.OperationalError:
        rows = []
    conn.close()
    return rows


def _emp_label(row):
    return f"{row['last_name']}, {row['first_name']}"


def _now_str():
    return QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")


def _hours_between(clock_in_str, clock_out_str):
    """Return decimal hours between two datetime strings."""
    try:
        fmt = "yyyy-MM-dd hh:mm:ss"
        t_in = QtCore.QDateTime.fromString(clock_in_str, fmt)
        t_out = QtCore.QDateTime.fromString(clock_out_str, fmt)
        if t_in.isValid() and t_out.isValid():
            return t_in.secsTo(t_out) / 3600.0
    except Exception:
        pass
    return 0.0


# ── Dialogs ─────────────────────────────────────────────────────────────

class ClockInDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clock In")
        self.resize(400, 200)
        _apply_blue_palette(self)
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
            self.emp_combo.addItem(_emp_label(e), e["id"])
        layout.addRow(lbl("Employee:"), self.emp_combo)

        self.dt_edit = QtWidgets.QDateTimeEdit(
            QtCore.QDateTime.currentDateTime())
        self.dt_edit.setDisplayFormat("yyyy-MM-dd hh:mm:ss")
        self.dt_edit.setCalendarPopup(True)
        self.dt_edit.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Clock In Time:"), self.dt_edit)

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
        if not self.emp_combo.count():
            QtWidgets.QMessageBox.warning(
    self, "No Employees", "No employees found.")
            return
        people_id = self.emp_combo.currentData()
        clock_in = self.dt_edit.dateTime().toString("yyyy-MM-dd hh:mm:ss")

        # Warn if already clocked in
        conn = get_db()
        open_entry = conn.execute(
            "SELECT id FROM time_clock WHERE people_id=%s AND clock_out IS "
            "NULL",
            (people_id,)
        ).fetchone()
        if open_entry:
            reply = QtWidgets.QMessageBox.question(
                self, "Already Clocked In",
                "This employee has an open clock-in. Clock in again anyway?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                conn.close()
                return

        conn.execute(
            "INSERT INTO time_clock (people_id, clock_in, notes) VALUES "
            "(%s,%s,%s)",
            (people_id, clock_in, self.notes.text().strip())
        )
        conn.commit()
        conn.close()
        self.accept()


class ClockOutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clock Out")
        self.resize(400, 200)
        _apply_blue_palette(self)
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
        # Only show employees with open entries
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT DISTINCT p.id, p.first_name, p.last_name
                FROM people p
                JOIN time_clock tc ON tc.people_id = p.id
                WHERE tc.clock_out IS NULL
                ORDER BY p.last_name, p.first_name
            """).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()
        if not rows:
            rows = _load_employees()
        for e in rows:
            self.emp_combo.addItem(_emp_label(e), e["id"])
        layout.addRow(lbl("Employee:"), self.emp_combo)

        self.dt_edit = QtWidgets.QDateTimeEdit(
            QtCore.QDateTime.currentDateTime())
        self.dt_edit.setDisplayFormat("yyyy-MM-dd hh:mm:ss")
        self.dt_edit.setCalendarPopup(True)
        self.dt_edit.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Clock Out Time:"), self.dt_edit)

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
        if not self.emp_combo.count():
            return
        people_id = self.emp_combo.currentData()
        clock_out = self.dt_edit.dateTime().toString("yyyy-MM-dd hh:mm:ss")
        conn = get_db()
        # Find the most recent open entry
        entry = conn.execute(
            "SELECT id, clock_in FROM time_clock"
            " WHERE people_id=%s AND clock_out IS NULL"
            " ORDER BY clock_in DESC LIMIT 1",
            (people_id,)
        ).fetchone()
        if not entry:
            QtWidgets.QMessageBox.warning(self, "Not Clocked In",
                                          "No open clock-in found for this "
                                          "employee.")
            conn.close()
            return
        hours = _hours_between(entry["clock_in"], clock_out)
        conn.execute(
            "UPDATE time_clock SET clock_out=%s, hours_worked=%s, notes=%s"
            " WHERE id=%s",
            (clock_out, round(hours, 4),
             self.notes.text().strip(), entry["id"])
        )
        conn.commit()
        conn.close()
        self.accept()


class TimeOffDialog(QtWidgets.QDialog):
    def __init__(self, request_id=None, parent=None):
        super().__init__(parent)
        self._request_id = request_id
        self.setWindowTitle(
    "Edit Request" if request_id else "New Time Off Request")
        self.resize(440, 320)
        _apply_blue_palette(self)
        self._build_ui()
        if request_id:
            self._load()

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
            self.emp_combo.addItem(_emp_label(e), e["id"])
        layout.addRow(lbl("Employee:"), self.emp_combo)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.setStyleSheet(COMBO_STYLE)
        for t in TIME_OFF_TYPES:
            self.type_combo.addItem(t, t)
        layout.addRow(lbl("Type:"), self.type_combo)

        self.start_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        self.start_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Start Date:"), self.start_date)

        self.end_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("End Date:"), self.end_date)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("pending", "approved", "denied"):
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

    def _load(self):
        conn = get_db()
        rec = conn.execute("SELECT * FROM time_off_request WHERE id=%s",
                           (self._request_id,)).fetchone()
        conn.close()
        if not rec:
            return
        for i in range(self.emp_combo.count()):
            if self.emp_combo.itemData(i) == rec["people_id"]:
                self.emp_combo.setCurrentIndex(i)
                break
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == rec["request_type"]:
                self.type_combo.setCurrentIndex(i)
                break
        self.start_date.setDate(
    QtCore.QDate.fromString(
        rec["start_date"],
         "yyyy-MM-dd"))
        self.end_date.setDate(
    QtCore.QDate.fromString(
        rec["end_date"],
         "yyyy-MM-dd"))
        for i in range(self.status_combo.count()):
            if self.status_combo.itemData(i) == rec["status"]:
                self.status_combo.setCurrentIndex(i)
                break
        self.notes.setText(rec["notes"] or "")

    def _on_ok(self):
        if not self.emp_combo.count():
            return
        conn = get_db()
        today = QtCore.QDate.currentDate().toString("yyyy-MM-dd")
        if self._request_id is None:
            conn.execute(
                "INSERT INTO time_off_request"
                " (people_id, request_date, start_date, end_date, "
                "request_type, status, notes)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (self.emp_combo.currentData(), today,
                 self.start_date.date().toString("yyyy-MM-dd"),
                 self.end_date.date().toString("yyyy-MM-dd"),
                 self.type_combo.currentData(),
                 self.status_combo.currentData(),
                 self.notes.text().strip())
            )
        else:
            conn.execute(
                "UPDATE time_off_request SET people_id=%s, start_date=%s, "
                "end_date=%s,"
                " request_type=%s, status=%s, notes=%s WHERE id=%s",
                (self.emp_combo.currentData(),
                 self.start_date.date().toString("yyyy-MM-dd"),
                 self.end_date.date().toString("yyyy-MM-dd"),
                 self.type_combo.currentData(),
                 self.status_combo.currentData(),
                 self.notes.text().strip(), self._request_id)
            )
        conn.commit()
        conn.close()
        self.accept()


# ── Time Entries Tab ────────────────────────────────────────────────────

class TimeEntriesTab(QtWidgets.QWidget):
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

        # Clock in/out quick buttons + status
        top = QtWidgets.QHBoxLayout()
        btn_in = QtWidgets.QPushButton("⏵  Clock In")
        btn_in.setStyleSheet(BUTTON_STYLE)
        btn_in.setFixedHeight(36)
        btn_in.clicked.connect(self._on_clock_in)
        top.addWidget(btn_in)

        btn_out = QtWidgets.QPushButton("⏹  Clock Out")
        btn_out.setStyleSheet(BUTTON_STYLE)
        btn_out.setFixedHeight(36)
        btn_out.clicked.connect(self._on_clock_out)
        top.addWidget(btn_out)

        top.addSpacing(20)
        self.clocked_in_lbl = QtWidgets.QLabel("")
        self.clocked_in_lbl.setStyleSheet("color: white; font-size: 13px;")
        top.addWidget(self.clocked_in_lbl)
        top.addStretch()
        v.addLayout(top)

        # Filters
        fr = QtWidgets.QHBoxLayout()
        lbl_e = QtWidgets.QLabel("Employee:")
        lbl_e.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_e)
        self.emp_filter = QtWidgets.QComboBox()
        self.emp_filter.setStyleSheet(COMBO_STYLE)
        self.emp_filter.setMinimumWidth(180)
        self.emp_filter.addItem("(all)", None)
        for e in _load_employees():
            self.emp_filter.addItem(_emp_label(e), e["id"])
        self.emp_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.emp_filter)

        fr.addSpacing(10)
        lbl_f = QtWidgets.QLabel("From:")
        lbl_f.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_f)
        self.date_from = QtWidgets.QDateEdit(
            QtCore.QDate.currentDate().addDays(-6))
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet(INPUT_STYLE)
        self.date_from.dateChanged.connect(self._refresh)
        fr.addWidget(self.date_from)

        lbl_t = QtWidgets.QLabel("To:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.date_to = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet(INPUT_STYLE)
        self.date_to.dateChanged.connect(self._refresh)
        fr.addWidget(self.date_to)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        self.tbl = QtWidgets.QTableWidget()
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(
            ["Employee", "Clock In", "Clock Out", "Hours", "Status", "Notes"])
        hh = self.tbl.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.clicked.connect(self._on_clicked)
        v.addWidget(self.tbl, stretch=1)

        self.summary_lbl = QtWidgets.QLabel("")
        self.summary_lbl.setStyleSheet("color: white; font-size: 13px;")
        v.addWidget(self.summary_lbl)

        br = QtWidgets.QHBoxLayout()
        btn_del = QtWidgets.QPushButton("Delete Entry")
        btn_del.setStyleSheet(BUTTON_STYLE)
        btn_del.setFixedHeight(30)
        btn_del.clicked.connect(self._on_delete)
        br.addWidget(btn_del)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        emp_id = self.emp_filter.currentData()
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")

        conds = ["DATE(tc.clock_in) BETWEEN %s AND %s"]
        params = [d_from, d_to]
        if emp_id:
            conds.append("tc.people_id = %s")
            params.append(emp_id)
        where = " AND ".join(conds)

        conn = get_db()
        try:
            rows = conn.execute(f"""
                SELECT tc.id, tc.clock_in, tc.clock_out, tc.hours_worked,
                    tc.notes,
                       p.first_name, p.last_name
                FROM time_clock tc
                JOIN people p ON p.id = tc.people_id
                WHERE {where}
                ORDER BY tc.clock_in DESC
            """, params).fetchall()
        except psycopg2.OperationalError:
            rows = []

        # Count currently clocked-in employees
        try:
            open_count = conn.execute(
                "SELECT COUNT(*) FROM time_clock WHERE clock_out IS NULL"
            ).fetchone()[0]
        except Exception:
            open_count = 0
        conn.close()

        self.tbl.setRowCount(0)
        self._row_ids = []
        total_hours = 0.0
        for row in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self._row_ids.append(row["id"])
            is_open = row["clock_out"] is None
            hours = row["hours_worked"] or 0
            total_hours += hours
            name = f"{row['last_name']}, {row['first_name']}"
            self.tbl.setItem(r, 0, _ro(name))
            self.tbl.setItem(r, 1, _ro(row["clock_in"] or ""))
            self.tbl.setItem(r, 2, _ro(row["clock_out"] or ""))
            self.tbl.setItem(r, 3, _ro_right(
                f"{hours:.2f}" if not is_open else "open"))
            self.tbl.setItem(
    r, 4, _ro(
        "Clocked In" if is_open else "Complete"))
            self.tbl.setItem(r, 5, _ro(row["notes"] or ""))
            if is_open:
                bg = QtGui.QColor("#cce5ff")
                for col in range(6):
                    self.tbl.item(r, col).setBackground(bg)

        self.summary_lbl.setText(
            f"Showing {len(rows)} entries  |  "
            f"Total hours: {total_hours:.2f}  |  "
            f"Currently clocked in: {open_count}"
        )
        self.clocked_in_lbl.setText(
    f"Currently clocked in: {open_count} employee(s)")
        self._selected_id = None

    def _on_show_all(self):
        self.emp_filter.blockSignals(True)
        self.emp_filter.setCurrentIndex(0)
        self.emp_filter.blockSignals(False)
        self.date_from.blockSignals(True)
        self.date_from.setDate(QtCore.QDate(2000, 1, 1))
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(True)
        self.date_to.setDate(QtCore.QDate.currentDate())
        self.date_to.blockSignals(False)
        self._refresh()

    def _on_clicked(self, index):
        row = index.row()
        if 0 <= row < len(self._row_ids):
            self._selected_id = self._row_ids[row]

    def _on_clock_in(self):
        dlg = ClockInDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_clock_out(self):
        dlg = ClockOutDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_delete(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an entry first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete", "Delete this time entry?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM time_clock WHERE id=%s",
                         (self._selected_id,))
            conn.commit()
            conn.close()
            self._selected_id = None
            self._refresh()


# ── Time Off Tab ────────────────────────────────────────────────────────

class TimeOffTab(QtWidgets.QWidget):
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
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.setStyleSheet(COMBO_STYLE)
        self.status_filter.addItem("(all)", None)
        for s in ("pending", "approved", "denied"):
            self.status_filter.addItem(s.capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.status_filter)

        fr.addSpacing(10)
        lbl_e = QtWidgets.QLabel("Employee:")
        lbl_e.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_e)
        self.emp_filter = QtWidgets.QComboBox()
        self.emp_filter.setStyleSheet(COMBO_STYLE)
        self.emp_filter.setMinimumWidth(180)
        self.emp_filter.addItem("(all)", None)
        for e in _load_employees():
            self.emp_filter.addItem(_emp_label(e), e["id"])
        self.emp_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.emp_filter)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        self.tbl = QtWidgets.QTableWidget()
        self.tbl.setColumnCount(7)
        self.tbl.setHorizontalHeaderLabels(
            ["Employee", "Type", "Start", "End", "Days", "Status", "Notes"])
        hh = self.tbl.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Stretch)
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
            ("New Request", self._on_new),
            ("Edit Request", self._on_edit),
            ("Approve",  lambda: self._set_status("approved")),
            ("Deny",     lambda: self._set_status("denied")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        status = self.status_filter.currentData()
        emp_id = self.emp_filter.currentData()
        conds, params = [], []
        if status:
            conds.append("r.status=%s")
            params.append(status)
        if emp_id:
            conds.append("r.people_id=%s")
            params.append(emp_id)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""

        conn = get_db()
        try:
            rows = conn.execute(f"""
                SELECT r.id, r.start_date, r.end_date, r.request_type,
                    r.status, r.notes,
                       p.first_name, p.last_name
                FROM time_off_request r
                JOIN people p ON p.id = r.people_id
                {where}
                ORDER BY r.start_date DESC
            """, params or None).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.tbl.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self._row_ids.append(row["id"])
            # Calculate days
            try:
                d1 = QtCore.QDate.fromString(row["start_date"], "yyyy-MM-dd")
                d2 = QtCore.QDate.fromString(row["end_date"], "yyyy-MM-dd")
                days = str(d1.daysTo(d2) + 1)
            except Exception:
                days = ""
            name = f"{row['last_name']}, {row['first_name']}"
            self.tbl.setItem(r, 0, _ro(name))
            self.tbl.setItem(r, 1, _ro(row["request_type"] or ""))
            self.tbl.setItem(r, 2, _ro(row["start_date"] or ""))
            self.tbl.setItem(r, 3, _ro(row["end_date"] or ""))
            self.tbl.setItem(r, 4, _ro_right(days))
            self.tbl.setItem(r, 5, _ro((row["status"] or "").capitalize()))
            self.tbl.setItem(r, 6, _ro(row["notes"] or ""))
            bg = QtGui.QColor(TIME_OFF_COLORS.get(row["status"], "#ffffff"))
            for col in range(7):
                self.tbl.item(r, col).setBackground(bg)
        self._selected_id = None

    def _on_show_all(self):
        self.status_filter.blockSignals(True)
        self.status_filter.setCurrentIndex(0)
        self.status_filter.blockSignals(False)
        self.emp_filter.blockSignals(True)
        self.emp_filter.setCurrentIndex(0)
        self.emp_filter.blockSignals(False)
        self._refresh()

    def _on_clicked(self, index):
        row = index.row()
        if 0 <= row < len(self._row_ids):
            self._selected_id = self._row_ids[row]

    def _on_new(self):
        dlg = TimeOffDialog(parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, _index=None):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a request first.")
            return
        dlg = TimeOffDialog(request_id=self._selected_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a request first.")
            return
        conn = get_db()
        conn.execute("UPDATE time_off_request SET status=%s WHERE id=%s",
                     (new_status, self._selected_id))
        conn.commit()
        conn.close()
        self._refresh()


# ── Main Window ─────────────────────────────────────────────────────────

class TimeClockWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        init_db()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane{border: none;}"
            "QTabBar::tab{background: white; color: black; padding: 6px 14px;"
            " border: 1px solid #999; border-bottom: none;"
            " border-radius: 4px 4px 0 0;}"
            "QTabBar::tab:selected{background: rgb(85,255,255); font-weight: "
            "bold;}"
        )
        tabs.addTab(TimeEntriesTab(), "Time Entries")
        tabs.addTab(TimeOffTab(), "Time Off Requests")
        layout.addWidget(tabs)


class TimeClockWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Time Clock")
        self.resize(1020, 680)
        _apply_blue_palette(self)
        self.setCentralWidget(TimeClockWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = TimeClockWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
