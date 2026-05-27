import sys
import psycopg2
from db_pg import get_db
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

PROJECT_COLORS = {
    "planning":    "#ffffff",
    "in_progress": "#d4edda",
    "review":      "#fff3cd",
    "complete":    "#d1ecf1",
    "on_hold":     "#dcdcdc",
}

ECR_COLORS = {
    "draft":     "#ffffff",
    "in_review": "#fff3cd",
    "approved":  "#d4edda",
    "rejected":  "#f8d7da",
}

PRIORITY_COLORS = {
    "critical": QtGui.QColor(248, 215, 218),
    "high":     QtGui.QColor(255, 243, 205),
    "medium":   QtGui.QColor(220, 235, 255),
}


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eng_project (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            project_number TEXT NOT NULL UNIQUE,
            title          TEXT NOT NULL,
            product_id     INTEGER,
            engineer       TEXT,
            start_date     TEXT,
            due_date       TEXT,
            status         TEXT DEFAULT 'planning',
            notes          TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eng_design_review (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ecr_number   TEXT NOT NULL UNIQUE,
            title        TEXT NOT NULL,
            product_id   INTEGER,
            project_id   INTEGER REFERENCES eng_project(id),
            requested_by TEXT,
            review_date  TEXT,
            status       TEXT DEFAULT 'draft',
            notes        TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eng_task (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER REFERENCES eng_project(id),
            task_name   TEXT NOT NULL,
            assigned_to TEXT,
            due_date    TEXT,
            priority    TEXT DEFAULT 'medium',
            status      TEXT DEFAULT 'open',
            notes       TEXT
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


def _load_products(combo, include_none=True):
    conn = get_db()
    try:
        prods = conn.execute("SELECT id, name AS product_name FROM product ORDER BY name").fetchall()
    except psycopg2.OperationalError:
        prods = []
    conn.close()
    combo.clear()
    if include_none:
        combo.addItem("(none)", None)
    for p in prods:
        combo.addItem(p["product_name"], p["id"])


def _load_projects(combo, include_none=True):
    conn = get_db()
    try:
        projs = conn.execute(
            "SELECT id, project_number, title FROM eng_project ORDER BY project_number"
        ).fetchall()
    except psycopg2.OperationalError:
        projs = []
    conn.close()
    combo.clear()
    if include_none:
        combo.addItem("(none)", None)
    for p in projs:
        combo.addItem(f"{p['project_number']} — {p['title']}", p["id"])


def _next_num(prefix, table, column):
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    try:
        count = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE ?", (f"{prefix}-{yr}-%",)
        ).fetchone()[0]
    except psycopg2.OperationalError:
        count = 0
    conn.close()
    return f"{prefix}-{yr}-{count + 1:04d}"


# ── Dialogs ────────────────────────────────────────────────────────────────────

class NewProjectDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Engineering Project")
        self.resize(500, 340)
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

        self.proj_num = QtWidgets.QLineEdit(_next_num("ENG", "eng_project", "project_number"))
        self.proj_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Project #:"), self.proj_num)

        self.title = QtWidgets.QLineEdit()
        self.title.setStyleSheet(INPUT_STYLE)
        self.title.setPlaceholderText("Project title (required)")
        layout.addRow(lbl("Title:"), self.title)

        self.product_combo = QtWidgets.QComboBox()
        self.product_combo.setStyleSheet(COMBO_STYLE)
        _load_products(self.product_combo)
        layout.addRow(lbl("Product:"), self.product_combo)

        self.engineer = QtWidgets.QLineEdit()
        self.engineer.setStyleSheet(INPUT_STYLE)
        self.engineer.setPlaceholderText("Lead engineer")
        layout.addRow(lbl("Engineer:"), self.engineer)

        self.start_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        self.start_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Start Date:"), self.start_date)

        self.due_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addDays(30))
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("planning", "in_progress", "review", "complete", "on_hold"):
            self.status_combo.addItem(s.replace("_", " ").capitalize(), s)
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
        num = self.proj_num.text().strip()
        title = self.title.text().strip()
        if not num or not title:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Project number and title are required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO eng_project (project_number, title, product_id, engineer,"
                " start_date, due_date, status, notes) VALUES (?,?,?,?,?,?,?,?)",
                (num, title, self.product_combo.currentData(),
                 self.engineer.text().strip(),
                 self.start_date.date().toString("yyyy-MM-dd"),
                 self.due_date.date().toString("yyyy-MM-dd"),
                 self.status_combo.currentData(),
                 self.notes.text().strip())
            )
            self.project_id = cur.lastrowid
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"Project number '{num}' already exists.")
            conn.close()
            return
        conn.close()
        self.accept()


class NewECRDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Engineering Change Request")
        self.resize(500, 340)
        _apply_blue_palette(self)
        self.ecr_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            l = QtWidgets.QLabel(t)
            l.setStyleSheet(LABEL_STYLE)
            return l

        self.ecr_num = QtWidgets.QLineEdit(_next_num("ECR", "eng_design_review", "ecr_number"))
        self.ecr_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("ECR #:"), self.ecr_num)

        self.title = QtWidgets.QLineEdit()
        self.title.setStyleSheet(INPUT_STYLE)
        self.title.setPlaceholderText("Change description (required)")
        layout.addRow(lbl("Title:"), self.title)

        self.product_combo = QtWidgets.QComboBox()
        self.product_combo.setStyleSheet(COMBO_STYLE)
        _load_products(self.product_combo)
        layout.addRow(lbl("Product:"), self.product_combo)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(COMBO_STYLE)
        _load_projects(self.project_combo)
        layout.addRow(lbl("Project:"), self.project_combo)

        self.requested_by = QtWidgets.QLineEdit()
        self.requested_by.setStyleSheet(INPUT_STYLE)
        self.requested_by.setPlaceholderText("Requester name")
        layout.addRow(lbl("Requested By:"), self.requested_by)

        self.review_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addDays(7))
        self.review_date.setCalendarPopup(True)
        self.review_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Review Date:"), self.review_date)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("draft", "in_review", "approved", "rejected"):
            self.status_combo.addItem(s.replace("_", " ").capitalize(), s)
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
        num = self.ecr_num.text().strip()
        title = self.title.text().strip()
        if not num or not title:
            QtWidgets.QMessageBox.warning(self, "Input Error", "ECR number and title are required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO eng_design_review (ecr_number, title, product_id, project_id,"
                " requested_by, review_date, status, notes) VALUES (?,?,?,?,?,?,?,?)",
                (num, title, self.product_combo.currentData(),
                 self.project_combo.currentData(),
                 self.requested_by.text().strip(),
                 self.review_date.date().toString("yyyy-MM-dd"),
                 self.status_combo.currentData(),
                 self.notes.text().strip())
            )
            self.ecr_id = cur.lastrowid
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"ECR number '{num}' already exists.")
            conn.close()
            return
        conn.close()
        self.accept()


class NewTaskDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Engineering Task")
        self.resize(480, 300)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            l = QtWidgets.QLabel(t)
            l.setStyleSheet(LABEL_STYLE)
            return l

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(COMBO_STYLE)
        _load_projects(self.project_combo)
        layout.addRow(lbl("Project:"), self.project_combo)

        self.task_name = QtWidgets.QLineEdit()
        self.task_name.setStyleSheet(INPUT_STYLE)
        self.task_name.setPlaceholderText("Task description (required)")
        layout.addRow(lbl("Task:"), self.task_name)

        self.assigned_to = QtWidgets.QLineEdit()
        self.assigned_to.setStyleSheet(INPUT_STYLE)
        self.assigned_to.setPlaceholderText("Assigned engineer")
        layout.addRow(lbl("Assigned To:"), self.assigned_to)

        self.due_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addDays(7))
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

        self.priority_combo = QtWidgets.QComboBox()
        self.priority_combo.setStyleSheet(COMBO_STYLE)
        for s in ("low", "medium", "high", "critical"):
            self.priority_combo.addItem(s.capitalize(), s)
        self.priority_combo.setCurrentIndex(1)
        layout.addRow(lbl("Priority:"), self.priority_combo)

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
        name = self.task_name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Task description is required.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO eng_task (project_id, task_name, assigned_to, due_date, priority, notes)"
            " VALUES (?,?,?,?,?,?)",
            (self.project_combo.currentData(),
             name,
             self.assigned_to.text().strip(),
             self.due_date.date().toString("yyyy-MM-dd"),
             self.priority_combo.currentData(),
             self.notes.text().strip())
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ────────────────────────────────────────────────────────────────

class EngineerMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Engineers")
        self.resize(980, 660)
        _apply_blue_palette(self)
        self._proj_row_ids = []
        self._selected_proj_id = None
        self._ecr_row_ids = []
        self._task_row_ids = []
        self._build_ui()
        init_db()
        self._refresh_projects()
        self._refresh_ecrs()
        self._refresh_tasks()

    def _build_ui(self):
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setStyleSheet(
            "QTabBar::tab{background:white; border:1px solid black; padding:4px 10px;}"
            "QTabBar::tab:selected{background:rgb(85,255,255);}"
        )
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)
        self._build_projects_tab()
        self._build_ecr_tab()
        self._build_tasks_tab()

    def _on_tab_changed(self, index):
        if index == 0:
            self._refresh_projects()
        elif index == 1:
            self._refresh_ecrs()
        elif index == 2:
            self._refresh_tasks()

    # ── Projects tab ────────────────────────────────────────────────────────

    def _build_projects_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.proj_status_filter = QtWidgets.QComboBox()
        self.proj_status_filter.setStyleSheet(COMBO_STYLE)
        self.proj_status_filter.addItem("(all)", None)
        for s in ("planning", "in_progress", "review", "complete", "on_hold"):
            self.proj_status_filter.addItem(s.replace("_", " ").capitalize(), s)
        self.proj_status_filter.currentIndexChanged.connect(self._refresh_projects)
        fr.addWidget(self.proj_status_filter)

        fr.addSpacing(10)
        lbl_e = QtWidgets.QLabel("Engineer:")
        lbl_e.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_e)
        self.proj_eng_filter = QtWidgets.QLineEdit()
        self.proj_eng_filter.setStyleSheet(INPUT_STYLE)
        self.proj_eng_filter.setFixedWidth(140)
        self.proj_eng_filter.setPlaceholderText("filter by name...")
        self.proj_eng_filter.returnPressed.connect(self._refresh_projects)
        fr.addWidget(self.proj_eng_filter)
        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_proj_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.proj_table = QtWidgets.QTableWidget()
        self.proj_table.setColumnCount(7)
        self.proj_table.setHorizontalHeaderLabels(
            ["Project #", "Title", "Product", "Engineer", "Start", "Due", "Status"]
        )
        hh = self.proj_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6):
            hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.proj_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.proj_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.proj_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.proj_table.setAlternatingRowColors(True)
        self.proj_table.verticalHeader().setVisible(False)
        self.proj_table.clicked.connect(self._on_proj_clicked)
        splitter.addWidget(self.proj_table)

        task_detail_w = QtWidgets.QWidget()
        _apply_blue_palette(task_detail_w)
        dv = QtWidgets.QVBoxLayout(task_detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Tasks for Selected Project")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.proj_task_table = QtWidgets.QTableWidget()
        self.proj_task_table.setColumnCount(5)
        self.proj_task_table.setHorizontalHeaderLabels(
            ["Task", "Assigned To", "Due Date", "Priority", "Status"]
        )
        dh = self.proj_task_table.horizontalHeader()
        dh.setStyleSheet("color: black; font-weight: bold;")
        dh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            dh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.proj_task_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.proj_task_table.verticalHeader().setVisible(False)
        self.proj_task_table.setAlternatingRowColors(True)
        dv.addWidget(self.proj_task_table)
        splitter.addWidget(task_detail_w)
        splitter.setSizes([380, 200])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Project",      self._on_new_project),
            ("Mark In Progress", lambda: self._set_proj_status("in_progress", "Mark as In Progress?")),
            ("Mark Review",      lambda: self._set_proj_status("review",      "Send to Review?")),
            ("Mark Complete",    lambda: self._set_proj_status("complete",    "Mark as Complete?")),
            ("Mark On Hold",     lambda: self._set_proj_status("on_hold",    "Put On Hold?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Projects")

    def _refresh_projects(self):
        status = self.proj_status_filter.currentData()
        eng = self.proj_eng_filter.text().strip()

        base = """
            SELECT ep.id, ep.project_number, ep.title, ep.engineer,
                   ep.start_date, ep.due_date, ep.status, p.name AS product_name
            FROM eng_project ep
            LEFT JOIN product p ON p.id = ep.product_id
        """
        conds, params = [], []
        if status:
            conds.append("ep.status = ?"); params.append(status)
        if eng:
            conds.append("ep.engineer LIKE ?"); params.append(f"%{eng}%")
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        conn = get_db()
        try:
            rows = conn.execute(base + where + " ORDER BY ep.due_date, ep.project_number", params).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.proj_table.setRowCount(0)
        self._proj_row_ids = []
        for row in rows:
            r = self.proj_table.rowCount()
            self.proj_table.insertRow(r)
            self._proj_row_ids.append(row["id"])
            self.proj_table.setItem(r, 0, _ro(row["project_number"]))
            self.proj_table.setItem(r, 1, _ro(row["title"]))
            self.proj_table.setItem(r, 2, _ro(row["product_name"] or ""))
            self.proj_table.setItem(r, 3, _ro(row["engineer"] or ""))
            self.proj_table.setItem(r, 4, _ro(row["start_date"] or ""))
            self.proj_table.setItem(r, 5, _ro(row["due_date"] or ""))
            self.proj_table.setItem(r, 6, _ro(row["status"].replace("_", " ").capitalize()))
            bg = QtGui.QColor(PROJECT_COLORS.get(row["status"], "#ffffff"))
            for col in range(7):
                self.proj_table.item(r, col).setBackground(bg)

        self._selected_proj_id = None
        self.proj_task_table.setRowCount(0)

    def _on_proj_show_all(self):
        self.proj_eng_filter.clear()
        self.proj_status_filter.blockSignals(True)
        self.proj_status_filter.setCurrentIndex(0)
        self.proj_status_filter.blockSignals(False)
        self._refresh_projects()

    def _on_proj_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._proj_row_ids):
            return
        self._selected_proj_id = self._proj_row_ids[row]
        self._refresh_proj_task_detail()

    def _refresh_proj_task_detail(self):
        self.proj_task_table.setRowCount(0)
        if self._selected_proj_id is None:
            return
        conn = get_db()
        try:
            tasks = conn.execute(
                "SELECT task_name, assigned_to, due_date, priority, status"
                " FROM eng_task WHERE project_id = ? ORDER BY due_date, priority DESC",
                (self._selected_proj_id,)
            ).fetchall()
        except psycopg2.OperationalError:
            tasks = []
        conn.close()
        for t in tasks:
            r = self.proj_task_table.rowCount()
            self.proj_task_table.insertRow(r)
            self.proj_task_table.setItem(r, 0, _ro(t["task_name"]))
            self.proj_task_table.setItem(r, 1, _ro(t["assigned_to"] or ""))
            self.proj_task_table.setItem(r, 2, _ro(t["due_date"] or ""))
            self.proj_task_table.setItem(r, 3, _ro(t["priority"].capitalize()))
            self.proj_task_table.setItem(r, 4, _ro(t["status"].replace("_", " ").capitalize()))
            if t["status"] != "done":
                color = PRIORITY_COLORS.get(t["priority"])
                if color:
                    for col in range(5):
                        self.proj_task_table.item(r, col).setBackground(color)

    def _on_new_project(self):
        dlg = NewProjectDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_projects()

    def _set_proj_status(self, new_status, msg):
        if self._selected_proj_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a project first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE eng_project SET status = ? WHERE id = ?",
                         (new_status, self._selected_proj_id))
            conn.commit()
            conn.close()
            self._refresh_projects()

    # ── Design Reviews (ECR) tab ────────────────────────────────────────────

    def _build_ecr_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.ecr_status_filter = QtWidgets.QComboBox()
        self.ecr_status_filter.setStyleSheet(COMBO_STYLE)
        self.ecr_status_filter.addItem("(all)", None)
        for s in ("draft", "in_review", "approved", "rejected"):
            self.ecr_status_filter.addItem(s.replace("_", " ").capitalize(), s)
        self.ecr_status_filter.currentIndexChanged.connect(self._refresh_ecrs)
        fr.addWidget(self.ecr_status_filter)
        fr.addStretch()
        v.addLayout(fr)

        self.ecr_table = QtWidgets.QTableWidget()
        self.ecr_table.setColumnCount(7)
        self.ecr_table.setHorizontalHeaderLabels(
            ["ECR #", "Title", "Product", "Project", "Requested By", "Review Date", "Status"]
        )
        hh = self.ecr_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6):
            hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.ecr_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ecr_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ecr_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.ecr_table.setAlternatingRowColors(True)
        self.ecr_table.verticalHeader().setVisible(False)
        v.addWidget(self.ecr_table, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New ECR",        self._on_new_ecr),
            ("Submit Review",  lambda: self._set_ecr_status("in_review", "Submit for review?")),
            ("Approve",        lambda: self._set_ecr_status("approved",  "Approve this ECR?")),
            ("Reject",         lambda: self._set_ecr_status("rejected",  "Reject this ECR?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Design Reviews")

    def _refresh_ecrs(self):
        status = self.ecr_status_filter.currentData()
        base = """
            SELECT dr.id, dr.ecr_number, dr.title, dr.requested_by, dr.review_date, dr.status,
                   p.name AS product_name, ep.project_number
            FROM eng_design_review dr
            LEFT JOIN product p ON p.id = dr.product_id
            LEFT JOIN eng_project ep ON ep.id = dr.project_id
        """
        conds, params = [], []
        if status:
            conds.append("dr.status = ?"); params.append(status)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        conn = get_db()
        try:
            rows = conn.execute(
                base + where + " ORDER BY dr.review_date DESC, dr.ecr_number DESC", params
            ).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.ecr_table.setRowCount(0)
        self._ecr_row_ids = []
        for row in rows:
            r = self.ecr_table.rowCount()
            self.ecr_table.insertRow(r)
            self._ecr_row_ids.append(row["id"])
            self.ecr_table.setItem(r, 0, _ro(row["ecr_number"]))
            self.ecr_table.setItem(r, 1, _ro(row["title"]))
            self.ecr_table.setItem(r, 2, _ro(row["product_name"] or ""))
            self.ecr_table.setItem(r, 3, _ro(row["project_number"] or ""))
            self.ecr_table.setItem(r, 4, _ro(row["requested_by"] or ""))
            self.ecr_table.setItem(r, 5, _ro(row["review_date"] or ""))
            self.ecr_table.setItem(r, 6, _ro(row["status"].replace("_", " ").capitalize()))
            bg = QtGui.QColor(ECR_COLORS.get(row["status"], "#ffffff"))
            for col in range(7):
                self.ecr_table.item(r, col).setBackground(bg)

    def _on_new_ecr(self):
        dlg = NewECRDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_ecrs()

    def _set_ecr_status(self, new_status, msg):
        row = self.ecr_table.currentRow()
        if row < 0 or row >= len(self._ecr_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select an ECR first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE eng_design_review SET status = ? WHERE id = ?",
                         (new_status, self._ecr_row_ids[row]))
            conn.commit()
            conn.close()
            self._refresh_ecrs()

    # ── Tasks tab ───────────────────────────────────────────────────────────

    def _build_tasks_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.task_status_filter = QtWidgets.QComboBox()
        self.task_status_filter.setStyleSheet(COMBO_STYLE)
        self.task_status_filter.addItem("Open & In Progress", "open")
        self.task_status_filter.addItem("In Progress only", "in_progress")
        self.task_status_filter.addItem("Done", "done")
        self.task_status_filter.addItem("All", None)
        self.task_status_filter.currentIndexChanged.connect(self._refresh_tasks)
        fr.addWidget(self.task_status_filter)

        fr.addSpacing(10)
        lbl_p = QtWidgets.QLabel("Priority:")
        lbl_p.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_p)
        self.task_pri_filter = QtWidgets.QComboBox()
        self.task_pri_filter.setStyleSheet(COMBO_STYLE)
        self.task_pri_filter.addItem("(all)", None)
        for s in ("low", "medium", "high", "critical"):
            self.task_pri_filter.addItem(s.capitalize(), s)
        self.task_pri_filter.currentIndexChanged.connect(self._refresh_tasks)
        fr.addWidget(self.task_pri_filter)
        fr.addStretch()
        v.addLayout(fr)

        self.task_table = QtWidgets.QTableWidget()
        self.task_table.setColumnCount(6)
        self.task_table.setHorizontalHeaderLabels(
            ["Task", "Project", "Assigned To", "Due Date", "Priority", "Status"]
        )
        hh = self.task_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4, 5):
            hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.task_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.task_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.verticalHeader().setVisible(False)
        v.addWidget(self.task_table, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Task",         self._on_new_task),
            ("Mark In Progress", lambda: self._set_task_status("in_progress", "Mark as In Progress?")),
            ("Mark Done",        lambda: self._set_task_status("done",        "Mark task as Done?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Tasks")

    def _refresh_tasks(self):
        status_val = self.task_status_filter.currentData()
        priority = self.task_pri_filter.currentData()

        base = """
            SELECT t.id, t.task_name, t.assigned_to, t.due_date, t.priority, t.status,
                   ep.project_number
            FROM eng_task t
            LEFT JOIN eng_project ep ON ep.id = t.project_id
        """
        conds, params = [], []
        if status_val == "open":
            conds.append("t.status IN ('open','in_progress')")
        elif status_val:
            conds.append("t.status = ?"); params.append(status_val)
        if priority:
            conds.append("t.priority = ?"); params.append(priority)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        conn = get_db()
        try:
            rows = conn.execute(
                base + where + " ORDER BY t.due_date, t.priority DESC, t.task_name", params
            ).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.task_table.setRowCount(0)
        self._task_row_ids = []
        for row in rows:
            r = self.task_table.rowCount()
            self.task_table.insertRow(r)
            self._task_row_ids.append(row["id"])
            self.task_table.setItem(r, 0, _ro(row["task_name"]))
            self.task_table.setItem(r, 1, _ro(row["project_number"] or ""))
            self.task_table.setItem(r, 2, _ro(row["assigned_to"] or ""))
            self.task_table.setItem(r, 3, _ro(row["due_date"] or ""))
            self.task_table.setItem(r, 4, _ro(row["priority"].capitalize()))
            self.task_table.setItem(r, 5, _ro(row["status"].replace("_", " ").capitalize()))
            if row["status"] != "done":
                color = PRIORITY_COLORS.get(row["priority"])
                if color:
                    for col in range(6):
                        self.task_table.item(r, col).setBackground(color)

    def _on_new_task(self):
        dlg = NewTaskDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_tasks()

    def _set_task_status(self, new_status, msg):
        row = self.task_table.currentRow()
        if row < 0 or row >= len(self._task_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a task first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE eng_task SET status = ? WHERE id = ?",
                         (new_status, self._task_row_ids[row]))
            conn.commit()
            conn.close()
            self._refresh_tasks()


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = EngineerMenu()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
