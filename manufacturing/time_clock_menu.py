import sys
import psycopg2
from db_pg import get_db
from datetime import datetime, date, timedelta
from PyQt6 import QtCore, QtGui, QtWidgets

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
CLOCK_IN_STYLE = (
    "QPushButton{background-color: #00aa33; color: white; border: 2px solid #007722;"
    " border-radius: 10px; font-size: 18px; font-weight: bold; padding: 12px 36px;}"
    "QPushButton:hover{background-color: #00cc44;}"
    "QPushButton:disabled{background-color: #888; color: #bbb; border-color: #666;}"
)
CLOCK_OUT_STYLE = (
    "QPushButton{background-color: #cc2200; color: white; border: 2px solid #991900;"
    " border-radius: 10px; font-size: 18px; font-weight: bold; padding: 12px 36px;}"
    "QPushButton:hover{background-color: #ee3311;}"
    "QPushButton:disabled{background-color: #888; color: #bbb; border-color: #666;}"
)
COMBO_STYLE = (
    "QComboBox{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 6px;}"
    "QComboBox QAbstractItemView{background-color: white;}"
)
INPUT_STYLE = (
    "QLineEdit{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 6px;}"
)
LABEL_STYLE = "color: white; font-size: 13px;"
DT_FMT = "%Y-%m-%d %H:%M:%S"


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS time_clock (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            people_id INTEGER NOT NULL REFERENCES people(id),
            clock_in  TEXT NOT NULL,
            clock_out TEXT,
            notes     TEXT
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


def _fmt_dt(dt_str):
    if not dt_str:
        return ""
    try:
        return datetime.strptime(dt_str, DT_FMT).strftime("%m/%d/%Y %I:%M %p")
    except ValueError:
        return dt_str


def _hours_str(clock_in_str, clock_out_str):
    if not clock_in_str:
        return ""
    try:
        t_in = datetime.strptime(clock_in_str, DT_FMT)
        t_out = (datetime.strptime(clock_out_str, DT_FMT)
                 if clock_out_str else datetime.now())
        mins = max(0, int((t_out - t_in).total_seconds() / 60))
        suffix = "" if clock_out_str else " *"
        return f"{mins // 60}h {mins % 60:02d}m{suffix}"
    except ValueError:
        return ""


def _to_qdatetime(dt_str):
    try:
        dt = datetime.strptime(dt_str, DT_FMT)
        return QtCore.QDateTime(
            QtCore.QDate(dt.year, dt.month, dt.day),
            QtCore.QTime(dt.hour, dt.minute, dt.second))
    except (ValueError, TypeError):
        return QtCore.QDateTime.currentDateTime()


# ── Edit-record dialog ─────────────────────────────────────────────────────

class EditRecordDialog(QtWidgets.QDialog):
    def __init__(self, record, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Time Record")
        self.setFixedSize(420, 260)
        _apply_blue_palette(self)
        self._record = record
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Edit Time Record")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        def row(label_text, widget):
            r = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(label_text)
            lbl.setFixedWidth(90)
            lbl.setStyleSheet(LABEL_STYLE)
            r.addWidget(lbl)
            r.addWidget(widget)
            return r

        self.in_edit = QtWidgets.QDateTimeEdit()
        self.in_edit.setDisplayFormat("MM/dd/yyyy hh:mm AP")
        self.in_edit.setCalendarPopup(True)
        self.in_edit.setStyleSheet("QDateTimeEdit{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 4px;}")
        self.in_edit.setDateTime(_to_qdatetime(self._record["clock_in"]))
        layout.addLayout(row("Clock In:", self.in_edit))

        self.out_edit = QtWidgets.QDateTimeEdit()
        self.out_edit.setDisplayFormat("MM/dd/yyyy hh:mm AP")
        self.out_edit.setCalendarPopup(True)
        self.out_edit.setStyleSheet("QDateTimeEdit{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 4px;}")
        if self._record["clock_out"]:
            self.out_edit.setDateTime(_to_qdatetime(self._record["clock_out"]))
        else:
            self.out_edit.setDateTime(QtCore.QDateTime.currentDateTime())
        layout.addLayout(row("Clock Out:", self.out_edit))

        self.clear_out_chk = QtWidgets.QCheckBox("Still clocked in (clear clock-out)")
        self.clear_out_chk.setStyleSheet("color: white;")
        self.clear_out_chk.setChecked(not bool(self._record["clock_out"]))
        self.clear_out_chk.toggled.connect(lambda c: self.out_edit.setEnabled(not c))
        self.out_edit.setEnabled(bool(self._record["clock_out"]))
        layout.addWidget(self.clear_out_chk)

        self.notes_input = QtWidgets.QLineEdit()
        self.notes_input.setStyleSheet(INPUT_STYLE)
        self.notes_input.setPlaceholderText("Optional notes")
        self.notes_input.setText(self._record["notes"] or "")
        layout.addLayout(row("Notes:", self.notes_input))

        btn_row = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setStyleSheet(BUTTON_STYLE)
        save_btn.setFixedHeight(34)
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setStyleSheet(BUTTON_STYLE)
        cancel_btn.setFixedHeight(34)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addSpacing(16)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_save(self):
        clock_in  = self.in_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        clock_out = (None if self.clear_out_chk.isChecked()
                     else self.out_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss"))
        if clock_out and clock_out <= clock_in:
            QtWidgets.QMessageBox.warning(self, "Invalid", "Clock-out must be after clock-in.")
            return
        conn = get_db()
        conn.execute(
            "UPDATE time_clock SET clock_in=?, clock_out=?, notes=? WHERE id=?",
            (clock_in, clock_out, self.notes_input.text().strip() or None,
             self._record["id"])
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Main window ────────────────────────────────────────────────────────────

class TimeClock(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Time Clock")
        self.resize(1000, 640)
        _apply_blue_palette(self)
        self._clock_people_id = None  # currently selected employee on tab 1
        self._records_row_ids = []
        self._build_ui()
        self._load_employees()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)

        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane{border:1px solid black;}"
            "QTabBar::tab{background:white; border:2px solid black; padding:6px 18px;"
            " border-bottom:none; border-radius:4px 4px 0 0;}"
            "QTabBar::tab:selected{background:rgb(85,255,255); font-weight:bold;}"
            "QTabBar::tab:hover{background:rgb(85,255,255);}"
        )
        outer.addWidget(tabs)

        tabs.addTab(self._build_clock_tab(), "Clock In / Out")
        tabs.addTab(self._build_records_tab(), "Time Records")

    def _build_clock_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # Live clock
        self.live_clock_lbl = QtWidgets.QLabel()
        self.live_clock_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.live_clock_lbl.setStyleSheet(
            "color: white; font-size: 32px; font-weight: bold; letter-spacing: 2px;"
        )
        layout.addWidget(self.live_clock_lbl)

        # Employee selection
        emp_row = QtWidgets.QHBoxLayout()
        emp_lbl = QtWidgets.QLabel("Employee:")
        emp_lbl.setStyleSheet(LABEL_STYLE)
        emp_lbl.setFixedWidth(80)
        emp_row.addWidget(emp_lbl)
        self.emp_combo = QtWidgets.QComboBox()
        self.emp_combo.setStyleSheet(COMBO_STYLE)
        self.emp_combo.setMinimumWidth(280)
        self.emp_combo.currentIndexChanged.connect(self._on_emp_changed)
        emp_row.addWidget(self.emp_combo)
        emp_row.addStretch()
        layout.addLayout(emp_row)

        # Status panel
        status_frame = QtWidgets.QFrame()
        status_frame.setStyleSheet(
            "QFrame{background-color: rgb(0,60,180); border: 2px solid white; border-radius: 8px;}"
        )
        status_frame.setFixedHeight(70)
        status_inner = QtWidgets.QVBoxLayout(status_frame)
        self.status_lbl = QtWidgets.QLabel("Select an employee")
        self.status_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
        status_inner.addWidget(self.status_lbl)
        layout.addWidget(status_frame)

        # Clock in/out buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self.clock_in_btn = QtWidgets.QPushButton("Clock In")
        self.clock_in_btn.setStyleSheet(CLOCK_IN_STYLE)
        self.clock_in_btn.setEnabled(False)
        self.clock_in_btn.clicked.connect(self._on_clock_in)
        btn_row.addWidget(self.clock_in_btn)
        btn_row.addSpacing(30)
        self.clock_out_btn = QtWidgets.QPushButton("Clock Out")
        self.clock_out_btn.setStyleSheet(CLOCK_OUT_STYLE)
        self.clock_out_btn.setEnabled(False)
        self.clock_out_btn.clicked.connect(self._on_clock_out)
        btn_row.addWidget(self.clock_out_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Today's entries table
        today_lbl = QtWidgets.QLabel("Today's entries:")
        today_lbl.setStyleSheet(LABEL_STYLE)
        layout.addWidget(today_lbl)

        self.today_table = QtWidgets.QTableWidget()
        self.today_table.setColumnCount(4)
        self.today_table.setHorizontalHeaderLabels(["Clock In", "Clock Out", "Hours", "Notes"])
        hh = self.today_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.today_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.today_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.today_table.verticalHeader().setVisible(False)
        self.today_table.setAlternatingRowColors(True)
        layout.addWidget(self.today_table, stretch=1)

        return w

    def _build_records_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Filters
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(8)

        def fl(text):
            l = QtWidgets.QLabel(text)
            l.setStyleSheet(LABEL_STYLE)
            return l

        filter_row.addWidget(fl("Employee:"))
        self.rec_emp_combo = QtWidgets.QComboBox()
        self.rec_emp_combo.setStyleSheet(COMBO_STYLE)
        self.rec_emp_combo.setMinimumWidth(200)
        filter_row.addWidget(self.rec_emp_combo)

        filter_row.addWidget(fl("From:"))
        self.from_date = QtWidgets.QDateEdit()
        self.from_date.setStyleSheet("QDateEdit{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 4px;}")
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QtCore.QDate.currentDate().addDays(-30))
        self.from_date.setDisplayFormat("MM/dd/yyyy")
        filter_row.addWidget(self.from_date)

        filter_row.addWidget(fl("To:"))
        self.to_date = QtWidgets.QDateEdit()
        self.to_date.setStyleSheet("QDateEdit{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 4px;}")
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QtCore.QDate.currentDate())
        self.to_date.setDisplayFormat("MM/dd/yyyy")
        filter_row.addWidget(self.to_date)

        for text, slot in (("Apply", self._refresh_records), ("Show All", self._records_show_all)):
            btn = QtWidgets.QPushButton(text)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.setFixedHeight(30)
            btn.clicked.connect(slot)
            filter_row.addWidget(btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Records table
        self.records_table = QtWidgets.QTableWidget()
        self.records_table.setColumnCount(6)
        self.records_table.setHorizontalHeaderLabels(
            ["Employee", "Date", "Clock In", "Clock Out", "Hours", "Notes"]
        )
        hh = self.records_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.records_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.records_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.records_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.records_table.setAlternatingRowColors(True)
        self.records_table.verticalHeader().setVisible(False)
        layout.addWidget(self.records_table, stretch=1)

        # Action buttons
        act_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Edit Selected", self._on_edit_record),
                           ("Delete Selected", self._on_delete_record)):
            btn = QtWidgets.QPushButton(text)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.setFixedHeight(34)
            btn.clicked.connect(slot)
            act_row.addWidget(btn)
        act_row.addStretch()

        # Total hours label
        self.total_lbl = QtWidgets.QLabel("")
        self.total_lbl.setStyleSheet("color: white; font-size: 13px;")
        act_row.addWidget(self.total_lbl)

        layout.addLayout(act_row)
        return w

    # ── Data helpers ───────────────────────────────────────────────────────

    def _load_employees(self):
        conn = get_db()
        rows = conn.execute(
            "SELECT id, first_name, last_name, ID as emp_id FROM people ORDER BY last_name, first_name"
        ).fetchall()
        conn.close()

        for combo in (self.emp_combo, self.rec_emp_combo):
            combo.blockSignals(True)
            combo.clear()
            if combo is self.rec_emp_combo:
                combo.addItem("(all employees)", None)
            else:
                combo.addItem("-- select employee --", None)
            for r in rows:
                label = f"{r['last_name']}, {r['first_name']}"
                if r["emp_id"]:
                    label += f"  (ID {r['emp_id']})"
                combo.addItem(label, r["id"])
            combo.blockSignals(False)

        self._refresh_records()

    def _get_open_record(self, people_id):
        conn = get_db()
        rec = conn.execute(
            "SELECT * FROM time_clock WHERE people_id=? AND clock_out IS NULL ORDER BY clock_in DESC LIMIT 1",
            (people_id,)
        ).fetchone()
        conn.close()
        return rec

    # ── Tab 1 logic ────────────────────────────────────────────────────────

    def _tick(self):
        self.live_clock_lbl.setText(
            datetime.now().strftime("%A  %B %d, %Y    %I:%M:%S %p")
        )
        if self._clock_people_id:
            self._update_status()

    def _on_emp_changed(self):
        pid = self.emp_combo.currentData()
        self._clock_people_id = pid
        if pid is None:
            self.status_lbl.setText("Select an employee")
            self.clock_in_btn.setEnabled(False)
            self.clock_out_btn.setEnabled(False)
            self.today_table.setRowCount(0)
            return
        self._update_status()
        self._refresh_today()

    def _update_status(self):
        open_rec = self._get_open_record(self._clock_people_id)
        if open_rec:
            since = datetime.strptime(open_rec["clock_in"], DT_FMT).strftime("%I:%M %p")
            mins = max(0, int((datetime.now() -
                               datetime.strptime(open_rec["clock_in"], DT_FMT)
                               ).total_seconds() / 60))
            h, m = mins // 60, mins % 60
            self.status_lbl.setText(
                f"CLOCKED IN  since {since}   ({h}h {m:02d}m elapsed)"
            )
            self.status_lbl.setStyleSheet(
                "color: #88ff88; font-size: 16px; font-weight: bold; border: none;"
            )
            self.clock_in_btn.setEnabled(False)
            self.clock_out_btn.setEnabled(True)
        else:
            self.status_lbl.setText("NOT CLOCKED IN")
            self.status_lbl.setStyleSheet(
                "color: #ffcccc; font-size: 16px; font-weight: bold; border: none;"
            )
            self.clock_in_btn.setEnabled(True)
            self.clock_out_btn.setEnabled(False)

    def _refresh_today(self):
        if not self._clock_people_id:
            return
        today = date.today().strftime("%Y-%m-%d")
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM time_clock WHERE people_id=? AND clock_in LIKE ? ORDER BY clock_in",
            (self._clock_people_id, f"{today}%")
        ).fetchall()
        conn.close()

        self.today_table.setRowCount(0)
        for row in rows:
            r = self.today_table.rowCount()
            self.today_table.insertRow(r)
            for col, val in enumerate([
                _fmt_dt(row["clock_in"]),
                _fmt_dt(row["clock_out"]) if row["clock_out"] else "Active",
                _hours_str(row["clock_in"], row["clock_out"]),
                row["notes"] or "",
            ]):
                self.today_table.setItem(r, col, QtWidgets.QTableWidgetItem(val))

    def _on_clock_in(self):
        pid = self._clock_people_id
        if pid is None:
            return
        if self._get_open_record(pid):
            QtWidgets.QMessageBox.warning(self, "Already Clocked In",
                                          "This employee is already clocked in.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO time_clock (people_id, clock_in) VALUES (?, ?)",
            (pid, datetime.now().strftime(DT_FMT))
        )
        conn.commit()
        conn.close()
        self._update_status()
        self._refresh_today()
        self._refresh_records()

    def _on_clock_out(self):
        pid = self._clock_people_id
        if pid is None:
            return
        open_rec = self._get_open_record(pid)
        if not open_rec:
            QtWidgets.QMessageBox.warning(self, "Not Clocked In",
                                          "This employee is not clocked in.")
            return
        conn = get_db()
        conn.execute(
            "UPDATE time_clock SET clock_out=? WHERE id=?",
            (datetime.now().strftime(DT_FMT), open_rec["id"])
        )
        conn.commit()
        conn.close()
        self._update_status()
        self._refresh_today()
        self._refresh_records()

    # ── Tab 2 logic ────────────────────────────────────────────────────────

    def _refresh_records(self):
        pid = self.rec_emp_combo.currentData()
        from_dt = self.from_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        to_dt   = self.to_date.date().toString("yyyy-MM-dd")   + " 23:59:59"

        conn = get_db()
        q = """
            SELECT tc.id, p.first_name, p.last_name,
                   tc.clock_in, tc.clock_out, tc.notes
            FROM time_clock tc
            JOIN people p ON p.id = tc.people_id
            WHERE tc.clock_in BETWEEN ? AND ?
        """
        params = [from_dt, to_dt]
        if pid is not None:
            q += " AND tc.people_id = ?"
            params.append(pid)
        q += " ORDER BY tc.clock_in DESC"
        rows = conn.execute(q, params).fetchall()
        conn.close()

        self.records_table.setRowCount(0)
        self._records_row_ids = []
        total_mins = 0

        for row in rows:
            r = self.records_table.rowCount()
            self.records_table.insertRow(r)
            self._records_row_ids.append(row["id"])

            try:
                day_str = datetime.strptime(row["clock_in"], DT_FMT).strftime("%m/%d/%Y")
            except ValueError:
                day_str = ""

            hrs = _hours_str(row["clock_in"], row["clock_out"])
            # accumulate completed entries only
            if row["clock_out"]:
                try:
                    t_in  = datetime.strptime(row["clock_in"],  DT_FMT)
                    t_out = datetime.strptime(row["clock_out"], DT_FMT)
                    total_mins += max(0, int((t_out - t_in).total_seconds() / 60))
                except ValueError:
                    pass

            for col, val in enumerate([
                f"{row['last_name']}, {row['first_name']}",
                day_str,
                _fmt_dt(row["clock_in"]),
                _fmt_dt(row["clock_out"]) if row["clock_out"] else "Active",
                hrs,
                row["notes"] or "",
            ]):
                self.records_table.setItem(r, col, QtWidgets.QTableWidgetItem(val))

        h, m = total_mins // 60, total_mins % 60
        self.total_lbl.setText(
            f"Total completed hours: {h}h {m:02d}m  ({len(rows)} records)"
        )

    def _records_show_all(self):
        self.rec_emp_combo.setCurrentIndex(0)
        self.from_date.setDate(QtCore.QDate(2000, 1, 1))
        self.to_date.setDate(QtCore.QDate.currentDate())
        self._refresh_records()

    def _on_edit_record(self):
        row = self.records_table.currentRow()
        if row < 0 or row >= len(self._records_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a record first.")
            return
        rid = self._records_row_ids[row]
        conn = get_db()
        rec = conn.execute("SELECT * FROM time_clock WHERE id=?", (rid,)).fetchone()
        conn.close()
        if not rec:
            return
        dlg = EditRecordDialog(rec, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_records()
            if self._clock_people_id:
                self._update_status()
                self._refresh_today()

    def _on_delete_record(self):
        row = self.records_table.currentRow()
        if row < 0 or row >= len(self._records_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a record first.")
            return
        rid = self._records_row_ids[row]
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete", "Delete this time record?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM time_clock WHERE id=?", (rid,))
            conn.commit()
            conn.close()
            self._refresh_records()
            if self._clock_people_id:
                self._update_status()
                self._refresh_today()


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = TimeClock()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
