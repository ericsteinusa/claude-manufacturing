"""
cs_staff_mgmt.py — CS Staff Management
Tabs: Staff Directory | Performance Metrics | Staff Training | Staff Reports
"""
import sys
import os
from db_pg import get_db
import csv
from datetime import date, datetime
from PyQt6 import QtCore, QtGui, QtWidgets

CS_DEPT_ID = 3

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color%(white)s;border:2px solid black;border-radius:8px;"
    "padding:4px 12px;font-weight%(bold)s;}"
    "QPushButton%(hover)s{background-color%(rgb)s(85,255,255);}"
)
TAB_STYLE = (
    "QTabWidget:%(pane)s{border:1px solid #aaa;background%(white)s;}"
    "QTabBar:%(tab)s{background:#cce0ff;padding:6px 18px;font-weight%(bold)s;}"
    "QTabBar:%(tab)s%(selected)s{background%(white)s;border-bottom:2px solid rgb(0,85,255);}"
)
INPUT_STYLE = "QLineEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}"
COMBO_STYLE = "QComboBox{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}QComboBox QAbstractItemView{background-color%(white)s;}"
DATE_STYLE = "QDateEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 4px;}"
TEXT_STYLE = "QTextEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}"
HDR_STYLE = "font-size:20px;font-weight%(bold)s;color%(white)s;padding:4px;"
SECTION_STYLE = "font-size:13px;font-weight%(bold)s;color%(white)s;"
LABEL_STYLE = "color%(white)s;font-size:13px;"


def _conn():
    c = get_db()
    return c


def _init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS cs_training (
                id          SERIAL PRIMARY KEY,
                people_id   INTEGER,
                topic       TEXT NOT NULL,
                trainer     TEXT,
                train_date  TEXT NOT NULL,
                notes       TEXT,
                completed   INTEGER NOT NULL DEFAULT 0
            )
        """)


def _apply_palette(widget):
    pal = QtGui.QPalette()
    for g in (QtGui.QPalette.ColorGroup.Active,
              QtGui.QPalette.ColorGroup.Inactive,
              QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(g, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(g, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter):
    item = QtWidgets.QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
    item.setTextAlignment(align)
    return item


def _ro_c(text):
    return _ro(text, QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)


def _export_table(table, parent, name="export.csv"):
    if table.rowCount() == 0:
        QtWidgets.QMessageBox.information(parent, "Export", "No data to export.")
        return
    path, _ = QtWidgets.QFileDialog.getSaveFileName(parent, "Export CSV", name, "CSV Files (*.csv)")
    if not path:
        return
    headers = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in range(table.rowCount()):
            w.writerow([table.item(r, c).text() if table.item(r, c) else ""
                        for c in range(table.columnCount())])
    QtWidgets.QMessageBox.information(parent, "Export Complete", f"Saved to:\n{path}")


def lbl(text, style=LABEL_STYLE):
    w = QtWidgets.QLabel(text)
    w.setStyleSheet(style)
    return w


class DateRangeBar(QtWidgets.QWidget):
    run_clicked = QtCore.pyqtSignal()

    def __init__(self, default_days_back=365, parent=None):
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.dt_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.dt_from.setStyleSheet(DATE_STYLE)
        self.dt_from.setDisplayFormat("MM/dd/yyyy")
        self.dt_from.setDate(QtCore.QDate.currentDate().addDays(-default_days_back))
        self.dt_to = QtWidgets.QDateEdit(calendarPopup=True)
        self.dt_to.setStyleSheet(DATE_STYLE)
        self.dt_to.setDisplayFormat("MM/dd/yyyy")
        self.dt_to.setDate(QtCore.QDate.currentDate())
        btn = QtWidgets.QPushButton("Run Report")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(self.run_clicked)
        row.addWidget(lbl("From:"))
        row.addWidget(self.dt_from)
        row.addWidget(lbl("To:"))
        row.addWidget(self.dt_to)
        row.addWidget(btn)
        row.addStretch()

    @property
    def from_str(self):
        return self.dt_from.date().toString("yyyy-MM-dd")

    @property
    def to_str(self):
        return self.dt_to.date().toString("yyyy-MM-dd")


class CSStaffMgmtWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_palette(self)
        self._training_current_id = None
        self._build_ui()
        self._run_all()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        title = QtWidgets.QLabel("CS Staff Management")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(HDR_STYLE)
        root.addWidget(title)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_directory_tab(), "Staff Directory")
        self.tabs.addTab(self._build_metrics_tab(), "Performance Metrics")
        self.tabs.addTab(self._build_training_tab(), "Staff Training")
        self.tabs.addTab(self._build_reports_tab(), "Staff Reports")

    # ── Staff Directory ───────────────────────────────────────────────────

    def _build_directory_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(lbl("Customer Service Staff", SECTION_STYLE))
        top.addStretch()
        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(self._run_directory)
        top.addWidget(btn)
        v.addLayout(top)

        self.dir_tbl = QtWidgets.QTableWidget(0, 6)
        self.dir_tbl.setHorizontalHeaderLabels(
            ["Name", "Email", "City", "State", "Zip", "Employee ID"])
        hh = self.dir_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (2, 3, 4, 5):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.dir_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dir_tbl.setAlternatingRowColors(True)
        self.dir_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.dir_tbl, stretch=1)

        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BUTTON_STYLE)
        btn_exp.setFixedHeight(28)
        btn_exp.clicked.connect(lambda: _export_table(self.dir_tbl, self, "cs_staff_directory.csv"))
        exp_row.addWidget(btn_exp)
        v.addLayout(exp_row)
        return w

    def _run_directory(self):
        with _conn() as con:
            rows = con.execute("""
                SELECT p.first_name, p.last_name, p.email, p.city, p.state, p.zip_code, p.emp_id
                FROM people p
                WHERE p.dept_id = %s
                ORDER BY p.last_name, p.first_name
            """, (CS_DEPT_ID,)).fetchall()

        self.dir_tbl.setRowCount(0)
        for row in rows:
            name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
            r = self.dir_tbl.rowCount()
            self.dir_tbl.insertRow(r)
            self.dir_tbl.setItem(r, 0, _ro(name))
            self.dir_tbl.setItem(r, 1, _ro(row["email"] or ""))
            self.dir_tbl.setItem(r, 2, _ro_c(row["city"] or ""))
            self.dir_tbl.setItem(r, 3, _ro_c(row["state"] or ""))
            self.dir_tbl.setItem(r, 4, _ro_c(row["zip_code"] or ""))
            self.dir_tbl.setItem(r, 5, _ro_c(str(row["emp_id"] or "")))


    # ── Performance Metrics ───────────────────────────────────────────────

    def _build_metrics_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        self.met_bar = DateRangeBar(default_days_back=365)
        self.met_bar.run_clicked.connect(self._run_metrics)
        v.addWidget(self.met_bar)

        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(16)
        self._met_cards = {}
        for key, label in (
            ("total",    "Total Calls"),
            ("open",     "Open"),
            ("completed","Completed"),
            ("rate",     "Completion\nRate"),
            ("avg_res",  "Avg Resolution\n(days)"),
            ("avg_age",  "Avg Age Open\n(days)"),
        ):
            card = QtWidgets.QFrame()
            card.setFrameShape(QtWidgets.QFrame.Shape.Box)
            card.setStyleSheet("QFrame{background%(white)s;border:2px solid #0055ff;border-radius:8px;}")
            card.setFixedSize(160, 90)
            cl = QtWidgets.QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            tl = QtWidgets.QLabel(label)
            tl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            tl.setStyleSheet("color:#333;font-size:12px;font-weight%(bold)s;")
            vl = QtWidgets.QLabel("—")
            vl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            vl.setStyleSheet("color:#0055ff;font-size:22px;font-weight%(bold)s;")
            cl.addWidget(tl)
            cl.addWidget(vl)
            self._met_cards[key] = vl
            cards.addWidget(card)
        cards.addStretch()
        v.addLayout(cards)

        v.addWidget(lbl("Monthly Call Activity", SECTION_STYLE))

        self.met_tbl = QtWidgets.QTableWidget(0, 5)
        self.met_tbl.setHorizontalHeaderLabels(
            ["Month", "Total Calls", "Open", "Completed", "Completion Rate"])
        hh = self.met_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.met_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.met_tbl.setAlternatingRowColors(True)
        self.met_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.met_tbl, stretch=1)

        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: _export_table(self.met_tbl, self, "cs_performance.csv"))
        exp_row.addWidget(btn)
        v.addLayout(exp_row)
        return w

    def _run_metrics(self):
        f, t = self.met_bar.from_str, self.met_bar.to_str
        today = date.today().isoformat()
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM calls2 WHERE call_date BETWEEN %s AND %s", (f, t)
            ).fetchall()
            monthly = con.execute("""
                SELECT strftime('%Y-%m', call_date) AS month,
                       COUNT(*) AS total,
                       SUM(CASE WHEN completion_box=0 THEN 1 ELSE 0 END) AS open_ct,
                       SUM(completion_box) AS comp_ct
                FROM calls2
                WHERE call_date BETWEEN %s AND %s
                GROUP BY month ORDER BY month DESC
            """, (f, t)).fetchall()

        total = len(rows)
        completed = [r for r in rows if r["completion_box"]]
        open_rows = [r for r in rows if not r["completion_box"]]

        def _days(d1, d2):
            try:
                return (date.fromisoformat(d2) - date.fromisoformat(d1)).days
            except Exception:
                return None

        res_days = [d for r in completed
                    if (d := _days(r["call_date"], r["completion_date"])) is not None and d >= 0]
        age_days = [d for r in open_rows
                    if (d := _days(r["call_date"], today)) is not None]
        avg_res = sum(res_days) / len(res_days) if res_days else None
        avg_age = sum(age_days) / len(age_days) if age_days else None
        rate = len(completed) / total * 100 if total else 0

        self._met_cards["total"].setText(str(total))
        self._met_cards["open"].setText(str(len(open_rows)))
        self._met_cards["completed"].setText(str(len(completed)))
        self._met_cards["rate"].setText(f"{rate:.1f}%")
        self._met_cards["avg_res"].setText(f"{avg_res:.1f}" if avg_res is not None else "—")
        self._met_cards["avg_age"].setText(f"{avg_age:.1f}" if avg_age is not None else "—")

        self.met_tbl.setRowCount(0)
        for row in monthly:
            total_m = row["total"] or 0
            comp_m = row["comp_ct"] or 0
            open_m = row["open_ct"] or 0
            rate_m = f"{comp_m / total_m * 100:.1f}%" if total_m else "—"
            try:
                month_lbl = datetime.strptime(row["month"], "%Y-%m").strftime("%b %Y")
            except (ValueError, TypeError):
                month_lbl = row["month"] or ""
            r = self.met_tbl.rowCount()
            self.met_tbl.insertRow(r)
            self.met_tbl.setItem(r, 0, _ro_c(month_lbl))
            self.met_tbl.setItem(r, 1, _ro_c(str(total_m)))
            self.met_tbl.setItem(r, 2, _ro_c(str(open_m)))
            self.met_tbl.setItem(r, 3, _ro_c(str(comp_m)))
            self.met_tbl.setItem(r, 4, _ro_c(rate_m))

    # ── Staff Training ────────────────────────────────────────────────────

    def _build_training_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        self.train_tbl = QtWidgets.QTableWidget(0, 6)
        self.train_tbl.setHorizontalHeaderLabels(
            ["Staff Member", "Topic", "Trainer", "Date", "Notes", "Completed"])
        hh = self.train_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.train_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.train_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.train_tbl.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.train_tbl.setAlternatingRowColors(True)
        self.train_tbl.verticalHeader().setVisible(False)
        self.train_tbl.clicked.connect(self._on_training_row_clicked)
        v.addWidget(self.train_tbl, stretch=1)

        # Entry form
        form = QtWidgets.QGroupBox("Training Record")
        form.setStyleSheet(
            "QGroupBox{color%(white)s;font-weight%(bold)s;border:1px solid white;margin-top:8px;}"
            "QGroupBox:%(title)s{subcontrol-origin%(margin)s;left:10px;}")
        grid = QtWidgets.QGridLayout(form)
        grid.setSpacing(6)

        self.tr_staff = QtWidgets.QComboBox()
        self.tr_staff.setStyleSheet(COMBO_STYLE)

        self.tr_topic = QtWidgets.QLineEdit()
        self.tr_topic.setStyleSheet(INPUT_STYLE)
        self.tr_topic.setPlaceholderText("Training topic / course name")

        self.tr_trainer = QtWidgets.QLineEdit()
        self.tr_trainer.setStyleSheet(INPUT_STYLE)
        self.tr_trainer.setPlaceholderText("Trainer name")

        self.tr_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.tr_date.setStyleSheet(DATE_STYLE)
        self.tr_date.setDisplayFormat("MM/dd/yyyy")
        self.tr_date.setDate(QtCore.QDate.currentDate())

        self.tr_notes = QtWidgets.QLineEdit()
        self.tr_notes.setStyleSheet(INPUT_STYLE)
        self.tr_notes.setPlaceholderText("Notes")

        self.tr_completed = QtWidgets.QCheckBox("Completed")
        self.tr_completed.setStyleSheet("color%(white)s;font-size:13px;")

        grid.addWidget(lbl("Staff Member:"), 0, 0)
        grid.addWidget(self.tr_staff, 0, 1)
        grid.addWidget(lbl("Date:"), 0, 2)
        grid.addWidget(self.tr_date, 0, 3)
        grid.addWidget(self.tr_completed, 0, 4)
        grid.addWidget(lbl("Topic:"), 1, 0)
        grid.addWidget(self.tr_topic, 1, 1, 1, 2)
        grid.addWidget(lbl("Trainer:"), 1, 3)
        grid.addWidget(self.tr_trainer, 1, 4)
        grid.addWidget(lbl("Notes:"), 2, 0)
        grid.addWidget(self.tr_notes, 2, 1, 1, 4)
        v.addWidget(form)

        br = QtWidgets.QHBoxLayout()
        for text, fn in (("Add", self._tr_add), ("Update Selected", self._tr_update),
                         ("Delete Selected", self._tr_delete),
                         ("Export CSV", lambda: _export_table(self.train_tbl, self, "cs_training.csv")),
                         ("Clear", self._tr_clear)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        return w

    def _load_staff_combo(self):
        with _conn() as con:
            staff = con.execute(
                "SELECT id, first_name, last_name FROM people WHERE dept_id=%s ORDER BY last_name, first_name",
                (CS_DEPT_ID,)
            ).fetchall()
        self.tr_staff.blockSignals(True)
        self.tr_staff.clear()
        self.tr_staff.addItem("-- select --", None)
        for s in staff:
            name = f"{s['first_name'] or ''} {s['last_name'] or ''}".strip()
            self.tr_staff.addItem(name, s["id"])
        self.tr_staff.blockSignals(False)

    def _run_training(self):
        with _conn() as con:
            rows = con.execute("""
                SELECT t.id, t.people_id, t.topic, t.trainer, t.train_date, t.notes, t.completed,
                       p.first_name, p.last_name
                FROM cs_training t
                LEFT JOIN people p ON p.id = t.people_id
                ORDER BY t.train_date DESC
            """).fetchall()

        self._training_ids = []
        self.train_tbl.setRowCount(0)
        for row in rows:
            name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or "(unassigned)"
            comp = "Yes" if row["completed"] else "No"
            color = QtGui.QColor(212, 237, 218) if row["completed"] else QtGui.QColor(255, 243, 205)
            r = self.train_tbl.rowCount()
            self.train_tbl.insertRow(r)
            self._training_ids.append(row["id"])
            for c, val in enumerate([name, row["topic"] or "", row["trainer"] or "",
                                     row["train_date"] or "", row["notes"] or "", comp]):
                item = _ro_c(val) if c in (3, 5) else _ro(val)
                item.setBackground(color)
                self.train_tbl.setItem(r, c, item)

    def _on_training_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._training_ids):
            return
        self._training_current_id = self._training_ids[row]
        with _conn() as con:
            rec = con.execute("SELECT * FROM cs_training WHERE id=%s",
                              (self._training_current_id,)).fetchone()
        if not rec:
            return
        idx = self.tr_staff.findData(rec["people_id"])
        self.tr_staff.setCurrentIndex(idx if idx >= 0 else 0)
        self.tr_topic.setText(rec["topic"] or "")
        self.tr_trainer.setText(rec["trainer"] or "")
        self.tr_notes.setText(rec["notes"] or "")
        self.tr_completed.setChecked(bool(rec["completed"]))
        if rec["train_date"]:
            try:
                parts = rec["train_date"].split("-")
                self.tr_date.setDate(QtCore.QDate(int(parts[0]), int(parts[1]), int(parts[2])))
            except (ValueError, IndexError):
                pass

    def _tr_collect(self):
        topic = self.tr_topic.text().strip()
        if not topic:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Topic is required.")
            return None
        return {
            "people_id": self.tr_staff.currentData(),
            "topic": topic,
            "trainer": self.tr_trainer.text().strip() or None,
            "train_date": self.tr_date.date().toString("yyyy-MM-dd"),
            "notes": self.tr_notes.text().strip() or None,
            "completed": 1 if self.tr_completed.isChecked() else 0,
        }

    def _tr_add(self):
        data = self._tr_collect()
        if not data:
            return
        with _conn() as con:
            con.execute("""
                INSERT INTO cs_training (people_id, topic, trainer, train_date, notes, completed)
                VALUES (%(people_id)s, %(topic)s, %(trainer)s, %(train_date)s, %(notes)s, %(completed)s)
            """, data)
        self._tr_clear()
        self._run_training()

    def _tr_update(self):
        if self._training_current_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a record first.")
            return
        data = self._tr_collect()
        if not data:
            return
        data["id"] = self._training_current_id
        with _conn() as con:
            con.execute("""
                UPDATE cs_training SET people_id=%(people_id)s, topic=%(topic)s, trainer=%(trainer)s,
                    train_date=%(train_date)s, notes=%(notes)s, completed=%(completed)s
                WHERE id=%(id)s
            """, data)
        self._run_training()

    def _tr_delete(self):
        if self._training_current_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a record first.")
            return
        if (QtWidgets.QMessageBox.question(
                self, "Confirm Delete", "Delete this training record%s",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            with _conn() as con:
                con.execute("DELETE FROM cs_training WHERE id=%s", (self._training_current_id,))
            self._tr_clear()
            self._run_training()

    def _tr_clear(self):
        self._training_current_id = None
        self.tr_staff.setCurrentIndex(0)
        self.tr_topic.clear()
        self.tr_trainer.clear()
        self.tr_notes.clear()
        self.tr_completed.setChecked(False)
        self.tr_date.setDate(QtCore.QDate.currentDate())
        self.train_tbl.clearSelection()

    # ── Staff Reports ─────────────────────────────────────────────────────

    def _build_reports_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        self.rpt_bar = DateRangeBar(default_days_back=365)
        self.rpt_bar.run_clicked.connect(self._run_reports)
        v.addWidget(self.rpt_bar)

        v.addWidget(lbl("Call Activity by Customer", SECTION_STYLE))

        self.rpt_tbl = QtWidgets.QTableWidget(0, 5)
        self.rpt_tbl.setHorizontalHeaderLabels(
            ["Customer", "Total Calls", "Open", "Completed", "Completion Rate"])
        hh = self.rpt_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.rpt_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rpt_tbl.setAlternatingRowColors(True)
        self.rpt_tbl.verticalHeader().setVisible(False)
        self.rpt_tbl.setSortingEnabled(True)
        v.addWidget(self.rpt_tbl, stretch=1)

        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: _export_table(self.rpt_tbl, self, "cs_staff_report.csv"))
        exp_row.addWidget(btn)
        v.addLayout(exp_row)
        return w

    def _run_reports(self):
        f, t = self.rpt_bar.from_str, self.rpt_bar.to_str
        with _conn() as con:
            rows = con.execute("""
                SELECT cu.first_name, cu.last_name, cu.company_name,
                       COUNT(c2.id) AS total,
                       SUM(CASE WHEN c2.completion_box=0 THEN 1 ELSE 0 END) AS open_ct,
                       SUM(c2.completion_box) AS comp_ct
                FROM calls2 c2
                LEFT JOIN customer cu ON cu.id = c2.customer_id
                WHERE c2.call_date BETWEEN %s AND %s
                GROUP BY c2.customer_id, cu.first_name, cu.last_name, cu.company_name
                ORDER BY total DESC
            """, (f, t)).fetchall()

        self.rpt_tbl.setSortingEnabled(False)
        self.rpt_tbl.setRowCount(0)
        for row in rows:
            company = (row["company_name"] or "").strip()
            contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
            cust = company if company else (contact if contact else "(no customer)")
            total = row["total"] or 0
            comp = row["comp_ct"] or 0
            open_ct = row["open_ct"] or 0
            rate = f"{comp / total * 100:.1f}%" if total else "—"
            r = self.rpt_tbl.rowCount()
            self.rpt_tbl.insertRow(r)
            self.rpt_tbl.setItem(r, 0, _ro(cust))
            self.rpt_tbl.setItem(r, 1, _ro_c(str(total)))
            self.rpt_tbl.setItem(r, 2, _ro_c(str(open_ct)))
            self.rpt_tbl.setItem(r, 3, _ro_c(str(comp)))
            self.rpt_tbl.setItem(r, 4, _ro_c(rate))
            if open_ct > 0:
                for c in range(5):
                    self.rpt_tbl.item(r, c).setBackground(QtGui.QColor(255, 243, 205))
        self.rpt_tbl.setSortingEnabled(True)

    # ── Run all ───────────────────────────────────────────────────────────

    def _run_all(self):
        self._load_staff_combo()
        self._training_ids = []
        self._run_directory()
        self._run_metrics()
        self._run_training()
        self._run_reports()


class CSStaffMgmtWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CS Staff Management")
        self.resize(1100, 720)
        _apply_palette(self)
        self.setCentralWidget(CSStaffMgmtWidget())


if __name__ == "__main__":
    _init_db()
    app = QtWidgets.QApplication(sys.argv)
    win = CSStaffMgmtWindow()
    win.show()
    sys.exit(app.exec())
