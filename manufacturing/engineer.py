import sys
import psycopg2
import psycopg2.extras
from .db_connection import get_db_connection
import os
from PyQt6 import QtCore, QtGui, QtWidgets


BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE = "QLineEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
COMBO_STYLE = (
    "QComboBox{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
    "QComboBox QAbstractItemView{background-color:white;}"
)
TEXT_STYLE = "QPlainTextEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
LABEL_STYLE = "color:white;font-size:13px;"
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)

PROJECT_STATUSES = ("planning", "in_progress", "on_hold", "completed", "cancelled")
TASK_STATUSES = ("open", "in_progress", "on_hold", "completed", "cancelled")
PRIORITIES = ("low", "medium", "high", "critical")

PROJECT_COLORS = {
    "planning": "#e8f4fd",
    "in_progress": "#fff3cd",
    "on_hold": "#f8d7da",
    "completed": "#d4edda",
    "cancelled": "#dcdcdc",
}
TASK_COLORS = {
    "open": "#ffffff",
    "in_progress": "#fff3cd",
    "on_hold": "#f8d7da",
    "completed": "#d4edda",
    "cancelled": "#dcdcdc",
}
PRIORITY_COLORS = {
    "critical": QtGui.QColor(248, 215, 218),
    "high": QtGui.QColor(255, 243, 205),
    "medium": QtGui.QColor(220, 235, 255),
}


def get_db():
    conn = get_db_connection()
    return conn


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


def _next_proj_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM eng_project WHERE project_number LIKE %s",
        (f"PROJ-{yr}-%",)
    ).fetchone()[0]
    conn.close()
    return f"PROJ-{yr}-{count + 1:04d}"


# ── Dialogs ────────────────────────────────────────────────────────────────────

class NewProjectDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Engineering Project")
        self.resize(520, 440)
        _apply_blue_palette(self)
        self.project_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            l = QtWidgets.QLabel(t)
            l.setStyleSheet(LABEL_STYLE)
            return l

        self.proj_num = QtWidgets.QLineEdit(_next_proj_num())
        self.proj_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Project #:"), self.proj_num)

        self.title = QtWidgets.QLineEdit()
        self.title.setStyleSheet(INPUT_STYLE)
        self.title.setPlaceholderText("Project title (required)")
        layout.addRow(lbl("Title:"), self.title)

        self.engineer = QtWidgets.QLineEdit()
        self.engineer.setStyleSheet(INPUT_STYLE)
        self.engineer.setPlaceholderText("Lead engineer name")
        layout.addRow(lbl("Engineer:"), self.engineer)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in PROJECT_STATUSES:
            self.status_combo.addItem(s.replace("_", " ").capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

        self.start_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        self.start_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Start Date:"), self.start_date)

        self.due_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addDays(30))
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setStyleSheet(TEXT_STYLE)
        self.notes.setPlaceholderText("Project notes")
        self.notes.setFixedHeight(80)
        layout.addRow(lbl("Notes:"), self.notes)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        num = self.proj_num.text().strip()
        title = self.title.text().strip()
        if not num or not title:
            QtWidgets.QMessageBox.warning(self, "Input Error",
                                          "Project number and title are required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO eng_project"
                " (project_number, title, engineer, start_date, due_date, status, notes)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (num, title,
                 self.engineer.text().strip(),
                 self.start_date.date().toString("yyyy-MM-dd"),
                 self.due_date.date().toString("yyyy-MM-dd"),
                 self.status_combo.currentData(),
                 self.notes.toPlainText().strip())
            )
            self.project_id = cur.fetchone()['id']
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"Project number '{num}' already exists.")
            conn.close()
            return
        conn.close()
        self.accept()


class NewTaskDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Engineering Task")
        self.resize(520, 420)
        _apply_blue_palette(self)
        self.task_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            l = QtWidgets.QLabel(t)
            l.setStyleSheet(LABEL_STYLE)
            return l

        self.task_name = QtWidgets.QLineEdit()
        self.task_name.setStyleSheet(INPUT_STYLE)
        self.task_name.setPlaceholderText("Task name (required)")
        layout.addRow(lbl("Task Name:"), self.task_name)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(COMBO_STYLE)
        self.project_combo.addItem("(no project)", None)
        conn = get_db()
        projects = conn.execute(
            "SELECT id, project_number, title FROM eng_project ORDER BY project_number"
        ).fetchall()
        conn.close()
        for p in projects:
            self.project_combo.addItem(f"{p['project_number']} — {p['title']}", p["id"])
        layout.addRow(lbl("Project:"), self.project_combo)

        self.assigned_to = QtWidgets.QLineEdit()
        self.assigned_to.setStyleSheet(INPUT_STYLE)
        self.assigned_to.setPlaceholderText("Assigned engineer")
        layout.addRow(lbl("Assigned To:"), self.assigned_to)

        self.priority_combo = QtWidgets.QComboBox()
        self.priority_combo.setStyleSheet(COMBO_STYLE)
        for s in PRIORITIES:
            self.priority_combo.addItem(s.capitalize(), s)
        self.priority_combo.setCurrentIndex(1)
        layout.addRow(lbl("Priority:"), self.priority_combo)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in TASK_STATUSES:
            self.status_combo.addItem(s.replace("_", " ").capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

        self.due_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addDays(14))
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setStyleSheet(TEXT_STYLE)
        self.notes.setPlaceholderText("Task notes")
        self.notes.setFixedHeight(80)
        layout.addRow(lbl("Notes:"), self.notes)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        name = self.task_name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Task name is required.")
            return
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO eng_task"
            " (task_name, project_id, assigned_to, priority, status, due_date, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (name,
             self.project_combo.currentData(),
             self.assigned_to.text().strip(),
             self.priority_combo.currentData(),
             self.status_combo.currentData(),
             self.due_date.date().toString("yyyy-MM-dd"),
             self.notes.toPlainText().strip())
        )
        self.task_id = cur.fetchone()['id']
        conn.commit()
        conn.close()
        self.accept()


# ── Tab widgets ────────────────────────────────────────────────────────────────

class ProjectsTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
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
        self.status_filter.addItem("Active (Planning & In Progress)", "active")
        self.status_filter.addItem("Planning", "planning")
        self.status_filter.addItem("In Progress", "in_progress")
        self.status_filter.addItem("On Hold", "on_hold")
        self.status_filter.addItem("Completed", "completed")
        self.status_filter.addItem("Cancelled", "cancelled")
        self.status_filter.addItem("All", None)
        self.status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.status_filter)
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

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Project #", "Title", "Engineer", "Start Date", "Due Date", "Status"]
        )
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5):
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
        dlbl = QtWidgets.QLabel("Notes for Selected Project")
        dlbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        dv.addWidget(dlbl)
        self.detail_text = QtWidgets.QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet(
            "QPlainTextEdit{background-color:white;border:1px solid black;}")
        dv.addWidget(self.detail_text)
        splitter.addWidget(detail_w)
        splitter.setSizes([380, 120])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Project", self._on_new),
            ("Start Project", lambda: self._set_status("in_progress", "Mark as In Progress%s")),
            ("Mark On Hold", lambda: self._set_status("on_hold", "Put On Hold%s")),
            ("Mark Complete", lambda: self._set_status("completed", "Mark as Completed%s")),
            ("Cancel Project", lambda: self._set_status("cancelled", "Cancel this project%s")),
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
        term = self.search.text().strip()
        conds, params = [], []
        if status_val == "active":
            conds.append("status IN ('planning','in_progress')")
        elif status_val:
            conds.append("status = %s")
            params.append(status_val)
        if term:
            conds.append("(project_number LIKE %s OR title LIKE %s OR engineer LIKE %s)")
            params += [f"%{term}%"] * 3
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM eng_project" + where + " ORDER BY due_date, project_number", params
        ).fetchall()
        conn.close()
        self.table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._row_ids.append(row["id"])
            self.table.setItem(r, 0, _ro(row["project_number"]))
            self.table.setItem(r, 1, _ro(row["title"]))
            self.table.setItem(r, 2, _ro(row["engineer"] or ""))
            self.table.setItem(r, 3, _ro(row["start_date"] or ""))
            self.table.setItem(r, 4, _ro(row["due_date"] or ""))
            self.table.setItem(r, 5, _ro(row["status"].replace("_", " ").capitalize()))
            bg = QtGui.QColor(PROJECT_COLORS.get(row["status"], "#ffffff"))
            for col in range(6):
                self.table.item(r, col).setBackground(bg)
        self._selected_id = None
        self.detail_text.clear()

    def _on_show_all(self):
        self.search.clear()
        self.status_filter.blockSignals(True)
        self.status_filter.setCurrentIndex(self.status_filter.count() - 1)
        self.status_filter.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        self._selected_id = self._row_ids[row]
        conn = get_db()
        rec = conn.execute(
            "SELECT * FROM eng_project WHERE id = %s", (self._selected_id,)
        ).fetchone()
        conn.close()
        if not rec:
            return
        lines = [
            f"Project:  {rec['project_number']}  —  {rec['title']}",
            f"Engineer: {rec['engineer'] or '—'}",
            f"Start:    {rec['start_date'] or '—'}  |  Due: {rec['due_date'] or '—'}",
            f"Status:   {rec['status'].replace('_', ' ').capitalize()}",
        ]
        if rec["notes"]:
            lines += ["", "Notes:", rec["notes"]]
        self.detail_text.setPlainText("\n".join(lines))

    def _on_new(self):
        dlg = NewProjectDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status, msg):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a project first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE eng_project SET status = %s WHERE id = %s",
                         (new_status, self._selected_id))
            conn.commit()
            conn.close()
            self._refresh()


class TasksTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
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
        self.status_filter.addItem("Open & In Progress", "active")
        self.status_filter.addItem("Open", "open")
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
        for s in PRIORITIES:
            self.pri_filter.addItem(s.capitalize(), s)
        self.pri_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.pri_filter)
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

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Task Name", "Project", "Assigned To", "Priority", "Due Date", "Status"]
        )
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for col in (2, 3, 4, 5):
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
        dlbl = QtWidgets.QLabel("Notes for Selected Task")
        dlbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        dv.addWidget(dlbl)
        self.detail_text = QtWidgets.QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet(
            "QPlainTextEdit{background-color:white;border:1px solid black;}")
        dv.addWidget(self.detail_text)
        splitter.addWidget(detail_w)
        splitter.setSizes([380, 120])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Task", self._on_new),
            ("Start Task", lambda: self._set_status("in_progress", "Mark as In Progress%s")),
            ("Mark On Hold", lambda: self._set_status("on_hold", "Put On Hold%s")),
            ("Mark Complete", lambda: self._set_status("completed", "Mark as Completed%s")),
            ("Cancel Task", lambda: self._set_status("cancelled", "Cancel this task%s")),
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
        term = self.search.text().strip()
        conds, params = [], []
        if status_val == "active":
            conds.append("t.status IN ('open','in_progress')")
        elif status_val:
            conds.append("t.status = %s")
            params.append(status_val)
        if priority:
            conds.append("t.priority = %s")
            params.append(priority)
        if term:
            conds.append("(t.task_name LIKE %s OR t.assigned_to LIKE %s OR p.title LIKE %s)")
            params += [f"%{term}%"] * 3
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        conn = get_db()
        rows = conn.execute(
            "SELECT t.*, p.project_number, p.title as proj_title"
            " FROM eng_task t LEFT JOIN eng_project p ON t.project_id = p.id"
            + where + " ORDER BY t.due_date, t.priority", params
        ).fetchall()
        conn.close()
        self.table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._row_ids.append(row["id"])
            proj_str = (f"{row['project_number']} — {row['proj_title']}"
                        if row["project_number"] else "—")
            self.table.setItem(r, 0, _ro(row["task_name"]))
            self.table.setItem(r, 1, _ro(proj_str))
            self.table.setItem(r, 2, _ro(row["assigned_to"] or ""))
            self.table.setItem(r, 3, _ro(row["priority"].capitalize()))
            self.table.setItem(r, 4, _ro(row["due_date"] or ""))
            self.table.setItem(r, 5, _ro(row["status"].replace("_", " ").capitalize()))
            bg = QtGui.QColor(TASK_COLORS.get(row["status"], "#ffffff"))
            for col in range(6):
                self.table.item(r, col).setBackground(bg)
            if row["status"] not in ("completed", "cancelled"):
                pc = PRIORITY_COLORS.get(row["priority"])
                if pc:
                    self.table.item(r, 3).setBackground(pc)
        self._selected_id = None
        self.detail_text.clear()

    def _on_show_all(self):
        self.search.clear()
        for combo in (self.status_filter, self.pri_filter):
            combo.blockSignals(True)
        self.status_filter.setCurrentIndex(self.status_filter.count() - 1)
        self.pri_filter.setCurrentIndex(0)
        for combo in (self.status_filter, self.pri_filter):
            combo.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        self._selected_id = self._row_ids[row]
        conn = get_db()
        rec = conn.execute(
            "SELECT t.*, p.project_number, p.title as proj_title"
            " FROM eng_task t LEFT JOIN eng_project p ON t.project_id = p.id"
            " WHERE t.id = %s", (self._selected_id,)
        ).fetchone()
        conn.close()
        if not rec:
            return
        proj_str = (f"{rec['project_number']} — {rec['proj_title']}"
                    if rec["project_number"] else "—")
        lines = [
            f"Task:     {rec['task_name']}",
            f"Project:  {proj_str}",
            f"Assigned: {rec['assigned_to'] or '—'}  |  Priority: {rec['priority'].capitalize()}",
            f"Due:      {rec['due_date'] or '—'}  |  Status: {rec['status'].replace('_',' ').capitalize()}",
        ]
        if rec["notes"]:
            lines += ["", "Notes:", rec["notes"]]
        self.detail_text.setPlainText("\n".join(lines))

    def _on_new(self):
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
            conn.execute("UPDATE eng_task SET status = %s WHERE id = %s",
                         (new_status, self._selected_id))
            conn.commit()
            conn.close()
            self._refresh()


# ── Main Window ────────────────────────────────────────────────────────────────

class EngineerMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Engineers")
        self.resize(1060, 700)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(ProjectsTab(), "Engineering Projects")
        tabs.addTab(TasksTab(), "Engineering Tasks")
        v.addWidget(tabs, stretch=1)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = EngineerMenu()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
