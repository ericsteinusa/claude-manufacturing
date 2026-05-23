import sys
import sqlite3
import os
import subprocess
from PyQt6 import QtCore, QtGui, QtWidgets

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "company.db")

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
TEXT_STYLE = "QPlainTextEdit{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 6px;}"
LABEL_STYLE = "color: white; font-size: 13px;"

TASK_COLORS = {
    "pending": "#ffffff",
    "in_progress": "#fff3cd",
    "completed": "#d4edda",
    "on_hold": "#f8d7da",
    "cancelled": "#dcdcdc",
}

PRIORITY_COLORS = {
    "critical": QtGui.QColor(248, 215, 218),
    "high": QtGui.QColor(255, 243, 205),
    "medium": QtGui.QColor(220, 235, 255),
}

TASK_TYPES = (
    "Maintenance", "Upgrade", "Installation", "Configuration",
    "Backup / Recovery", "Security", "Network", "Hardware Setup",
    "Software Deployment", "User Setup", "Other",
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS it_task (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            task_number    TEXT NOT NULL UNIQUE,
            task_name      TEXT NOT NULL,
            task_type      TEXT,
            description    TEXT,
            assigned_to    TEXT,
            department     TEXT,
            priority       TEXT DEFAULT 'medium',
            scheduled_date TEXT,
            due_date       TEXT,
            completed_date TEXT,
            status         TEXT DEFAULT 'pending',
            notes          TEXT
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


def _next_task_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM it_task WHERE task_number LIKE ?", (f"TASK-{yr}-%",)
        ).fetchone()[0]
    except sqlite3.OperationalError:
        count = 0
    conn.close()
    return f"TASK-{yr}-{count + 1:04d}"


# ── Dialogs ────────────────────────────────────────────────────────────────────

class NewTaskDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New IT Task")
        self.resize(520, 460)
        _apply_blue_palette(self)
        self.task_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            lbl = QtWidgets.QLabel(t)
            lbl.setStyleSheet(LABEL_STYLE)
            return lbl

        self.task_num = QtWidgets.QLineEdit(_next_task_num())
        self.task_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Task #:"), self.task_num)

        self.task_name = QtWidgets.QLineEdit()
        self.task_name.setStyleSheet(INPUT_STYLE)
        self.task_name.setPlaceholderText("Short task title (required)")
        layout.addRow(lbl("Task Name:"), self.task_name)

        self.task_type = QtWidgets.QComboBox()
        self.task_type.setStyleSheet(COMBO_STYLE)
        for t in TASK_TYPES:
            self.task_type.addItem(t, t)
        layout.addRow(lbl("Task Type:"), self.task_type)

        self.description = QtWidgets.QPlainTextEdit()
        self.description.setStyleSheet(TEXT_STYLE)
        self.description.setPlaceholderText("Describe what needs to be done")
        self.description.setFixedHeight(80)
        layout.addRow(lbl("Description:"), self.description)

        self.priority_combo = QtWidgets.QComboBox()
        self.priority_combo.setStyleSheet(COMBO_STYLE)
        for s in ("low", "medium", "high", "critical"):
            self.priority_combo.addItem(s.capitalize(), s)
        self.priority_combo.setCurrentIndex(1)
        layout.addRow(lbl("Priority:"), self.priority_combo)

        self.assigned_to = QtWidgets.QLineEdit()
        self.assigned_to.setStyleSheet(INPUT_STYLE)
        self.assigned_to.setPlaceholderText("Assigned technician")
        layout.addRow(lbl("Assigned To:"), self.assigned_to)

        self.department = QtWidgets.QLineEdit()
        self.department.setStyleSheet(INPUT_STYLE)
        self.department.setPlaceholderText("Department this task is for")
        layout.addRow(lbl("Department:"), self.department)

        self.scheduled_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.scheduled_date.setCalendarPopup(True)
        self.scheduled_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Scheduled:"), self.scheduled_date)

        self.due_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addDays(7))
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

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
        num = self.task_num.text().strip()
        name = self.task_name.text().strip()
        if not num or not name:
            QtWidgets.QMessageBox.warning(self, "Input Error",
                                          "Task number and task name are required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO it_task (task_number, task_name, task_type, description,"
                " priority, assigned_to, department, scheduled_date, due_date, notes)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (num, name, self.task_type.currentData(),
                 self.description.toPlainText().strip(),
                 self.priority_combo.currentData(),
                 self.assigned_to.text().strip(),
                 self.department.text().strip(),
                 self.scheduled_date.date().toString("yyyy-MM-dd"),
                 self.due_date.date().toString("yyyy-MM-dd"),
                 self.notes.text().strip())
            )
            self.task_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"Task number '{num}' already exists.")
            conn.close()
            return
        conn.close()
        self.accept()


# ── Main Window ────────────────────────────────────────────────────────────────

class ITTasksMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IT Tasks")
        self.resize(1060, 700)
        _apply_blue_palette(self)
        self._row_ids = []
        self._selected_id = None
        self._build_ui()
        init_db()
        self._refresh()

    def _launch(self, script):
        _dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)

    def _build_ui(self):
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # ── program buttons ──────────────────────────────────────────────────
        prog_row = QtWidgets.QHBoxLayout()
        prog_row.setSpacing(4)
        font16 = QtGui.QFont()
        font16.setPointSize(16)
        for label, script in (
            ("Department Entry", "dept_entry.py"),
            ("Department Sub Entry", "dept_sub_entry.py"),
            ("Department and Sub List", "dept_sub.py"),
            ("People and Dept", "display_people_department.py"),
        ):
            b = QtWidgets.QPushButton(label)
            b.setFont(font16)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(41)
            b.setAutoDefault(False)
            b.clicked.connect(lambda chk, s=script: self._launch(s))
            prog_row.addWidget(b)
        prog_row.addStretch()
        v.addLayout(prog_row)

        # ── filter bar ──────────────────────────────────────────────────────
        fr = QtWidgets.QHBoxLayout()

        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.setStyleSheet(COMBO_STYLE)
        self.status_filter.addItem("Pending & In Progress", "active")
        self.status_filter.addItem("Pending only", "pending")
        self.status_filter.addItem("In Progress", "in_progress")
        self.status_filter.addItem("On Hold", "on_hold")
        self.status_filter.addItem("Completed", "completed")
        self.status_filter.addItem("Cancelled", "cancelled")
        self.status_filter.addItem("All", None)
        self.status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.status_filter)

        fr.addSpacing(10)
        lbl_p = QtWidgets.QLabel("Priority:")
        lbl_p.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_p)
        self.pri_filter = QtWidgets.QComboBox()
        self.pri_filter.setStyleSheet(COMBO_STYLE)
        self.pri_filter.addItem("(all)", None)
        for s in ("low", "medium", "high", "critical"):
            self.pri_filter.addItem(s.capitalize(), s)
        self.pri_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.pri_filter)

        fr.addSpacing(10)
        lbl_t = QtWidgets.QLabel("Type:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.type_filter = QtWidgets.QComboBox()
        self.type_filter.setStyleSheet(COMBO_STYLE)
        self.type_filter.addItem("(all)", None)
        for t in TASK_TYPES:
            self.type_filter.addItem(t, t)
        self.type_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.type_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self.search = QtWidgets.QLineEdit()
        self.search.setStyleSheet(INPUT_STYLE)
        self.search.setFixedWidth(160)
        self.search.returnPressed.connect(self._refresh)
        fr.addWidget(self.search)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        # ── table + detail splitter ──────────────────────────────────────────
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["Task #", "Task Name", "Type", "Priority",
             "Assigned To", "Department", "Due Date", "Status"]
        )
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6, 7):
            hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.clicked.connect(self._on_row_clicked)
        splitter.addWidget(self.table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Description / Notes for Selected Task")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.detail_text = QtWidgets.QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet(
            "QPlainTextEdit{background-color: white; border: 1px solid black;}")
        dv.addWidget(self.detail_text)
        splitter.addWidget(detail_w)
        splitter.setSizes([440, 160])
        v.addWidget(splitter, stretch=1)

        # ── action buttons ──────────────────────────────────────────────────
        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Task", self._on_new_task),
            ("Start Task", lambda: self._set_status("in_progress", "Mark as In Progress?")),
            ("Mark On Hold", lambda: self._set_status("on_hold", "Put On Hold?")),
            ("Mark Complete", lambda: self._set_status("completed", "Mark as Completed?")),
            ("Cancel Task", lambda: self._set_status("cancelled", "Cancel this task?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        status_val = self.status_filter.currentData()
        priority = self.pri_filter.currentData()
        task_type = self.type_filter.currentData()
        term = self.search.text().strip()

        base = "SELECT * FROM it_task"
        conds, params = [], []
        if status_val == "active":
            conds.append("status IN ('pending','in_progress')")
        elif status_val:
            conds.append("status = ?")
            params.append(status_val)
        if priority:
            conds.append("priority = ?")
            params.append(priority)
        if task_type:
            conds.append("task_type = ?")
            params.append(task_type)
        if term:
            conds.append("(task_number LIKE ? OR task_name LIKE ? OR assigned_to LIKE ?"
                         " OR description LIKE ?)")
            params += [f"%{term}%"] * 4
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        conn = get_db()
        try:
            rows = conn.execute(
                base + where + " ORDER BY due_date, task_number", params
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        conn.close()

        self.table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._row_ids.append(row["id"])
            self.table.setItem(r, 0, _ro(row["task_number"]))
            self.table.setItem(r, 1, _ro(row["task_name"]))
            self.table.setItem(r, 2, _ro(row["task_type"] or ""))
            self.table.setItem(r, 3, _ro(row["priority"].capitalize()))
            self.table.setItem(r, 4, _ro(row["assigned_to"] or ""))
            self.table.setItem(r, 5, _ro(row["department"] or ""))
            self.table.setItem(r, 6, _ro(row["due_date"] or ""))
            self.table.setItem(r, 7, _ro(row["status"].replace("_", " ").capitalize()))
            bg = QtGui.QColor(TASK_COLORS.get(row["status"], "#ffffff"))
            for col in range(8):
                self.table.item(r, col).setBackground(bg)
            if row["status"] not in ("completed", "cancelled"):
                pc = PRIORITY_COLORS.get(row["priority"])
                if pc:
                    self.table.item(r, 3).setBackground(pc)

        self._selected_id = None
        self.detail_text.clear()

    def _on_show_all(self):
        self.search.clear()
        for combo in (self.status_filter, self.pri_filter, self.type_filter):
            combo.blockSignals(True)
        self.status_filter.setCurrentIndex(self.status_filter.count() - 1)
        self.pri_filter.setCurrentIndex(0)
        self.type_filter.setCurrentIndex(0)
        for combo in (self.status_filter, self.pri_filter, self.type_filter):
            combo.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        self._selected_id = self._row_ids[row]
        conn = get_db()
        rec = conn.execute(
            "SELECT * FROM it_task WHERE id = ?", (self._selected_id,)
        ).fetchone()
        conn.close()
        if not rec:
            return
        lines = [
            f"Task:        {rec['task_number']}  —  {rec['task_name']}",
            f"Type:        {rec['task_type'] or '—'}  |  Priority: {rec['priority'].capitalize()}",
            f"Assigned To: {rec['assigned_to'] or '—'}  |  Dept: {rec['department'] or '—'}",
            f"Scheduled:   {rec['scheduled_date'] or '—'}  |  Due: {rec['due_date'] or '—'}",
        ]
        if rec["completed_date"]:
            lines.append(f"Completed:   {rec['completed_date']}")
        if rec["description"]:
            lines += ["", "Description:", rec["description"]]
        if rec["notes"]:
            lines += ["", "Notes:", rec["notes"]]
        self.detail_text.setPlainText("\n".join(lines))

    def _on_new_task(self):
        dlg = NewTaskDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status, msg):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a task first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            extra = ""
            params = [new_status]
            if new_status == "completed":
                extra = ", completed_date = ?"
                params.append(QtCore.QDate.currentDate().toString("yyyy-MM-dd"))
            params.append(self._selected_id)
            conn.execute(f"UPDATE it_task SET status = ?{extra} WHERE id = ?", params)
            conn.commit()
            conn.close()
            self._refresh()


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = ITTasksMenu()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
