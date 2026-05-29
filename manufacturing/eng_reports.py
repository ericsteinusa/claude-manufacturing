import sys
from .db_pg import get_db
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
ECR_STATUSES = ("draft", "pending", "approved", "rejected", "revision_needed")

PROJECT_COLORS = {
    "planning": "#e8f4fd", "in_progress": "#fff3cd",
    "on_hold": "#f8d7da", "completed": "#d4edda", "cancelled": "#dcdcdc",
}
TASK_COLORS = {
    "open": "#ffffff", "in_progress": "#fff3cd",
    "on_hold": "#f8d7da", "completed": "#d4edda", "cancelled": "#dcdcdc",
}
ECR_COLORS = {
    "draft": "#e8f4fd", "pending": "#fff3cd", "approved": "#d4edda",
    "rejected": "#f8d7da", "revision_needed": "#ffe8c0",
}
PRIORITY_COLORS = {
    "critical": QtGui.QColor(248, 215, 218),
    "high": QtGui.QColor(255, 243, 205),
    "medium": QtGui.QColor(220, 235, 255),
}


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


class _StatCard(QtWidgets.QWidget):
    _val_lbl: QtWidgets.QLabel


def _stat_card(title, value) -> _StatCard:
    w = _StatCard()
    w.setStyleSheet("background-color:white;border-radius:6px;border:1px solid black;")
    v = QtWidgets.QVBoxLayout(w)
    v.setContentsMargins(10, 4, 10, 4)
    val_lbl = QtWidgets.QLabel(str(value))
    val_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    val_lbl.setStyleSheet("font-size:22px;font-weight:bold;color:black;border:none;")
    txt_lbl = QtWidgets.QLabel(title)
    txt_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    txt_lbl.setStyleSheet("font-size:11px;color:#333;border:none;")
    v.addWidget(val_lbl)
    v.addWidget(txt_lbl)
    w._val_lbl = val_lbl
    return w


# ── Projects report tab ────────────────────────────────────────────────────────

class ProjectsReportTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        _apply_blue_palette(self)
        self._cards = {}
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        stats = QtWidgets.QHBoxLayout()
        stats.setSpacing(8)
        for key in ("Total", "Planning", "In Progress", "On Hold", "Completed", "Cancelled"):
            card = _stat_card(key, 0)
            self._cards[key] = card
            stats.addWidget(card)
        stats.addStretch()
        v.addLayout(stats)

        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.setStyleSheet(COMBO_STYLE)
        self.status_filter.addItem("All", None)
        for s in PROJECT_STATUSES:
            self.status_filter.addItem(s.replace("_", " ").capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.status_filter)
        fr.addSpacing(10)
        lbl_e = QtWidgets.QLabel("Engineer:")
        lbl_e.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_e)
        self.eng_search = QtWidgets.QLineEdit()
        self.eng_search.setStyleSheet(INPUT_STYLE)
        self.eng_search.setFixedWidth(140)
        self.eng_search.setPlaceholderText("filter by engineer")
        self.eng_search.returnPressed.connect(self._refresh)
        fr.addWidget(self.eng_search)
        fr.addStretch()
        v.addLayout(fr)

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
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table, stretch=1)

    def _refresh(self):
        status_val = self.status_filter.currentData()
        eng = self.eng_search.text().strip()
        conds, params = [], []
        if status_val:
            conds.append("status = %s")
            params.append(status_val)
        if eng:
            conds.append("engineer LIKE %s")
            params.append(f"%{eng}%")
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM eng_project" + where + " ORDER BY due_date, project_number", params
        ).fetchall()
        all_rows = conn.execute("SELECT status FROM eng_project").fetchall()
        conn.close()

        counts = {}
        for r in all_rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        for key, db_key in (
            ("Total", None), ("Planning", "planning"), ("In Progress", "in_progress"),
            ("On Hold", "on_hold"), ("Completed", "completed"), ("Cancelled", "cancelled"),
        ):
            val = len(all_rows) if db_key is None else counts.get(db_key, 0)
            self._cards[key]._val_lbl.setText(str(val))

        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, _ro(row["project_number"]))
            self.table.setItem(r, 1, _ro(row["title"]))
            self.table.setItem(r, 2, _ro(row["engineer"] or ""))
            self.table.setItem(r, 3, _ro(row["start_date"] or ""))
            self.table.setItem(r, 4, _ro(row["due_date"] or ""))
            self.table.setItem(r, 5, _ro(row["status"].replace("_", " ").capitalize()))
            bg = QtGui.QColor(PROJECT_COLORS.get(row["status"], "#ffffff"))
            for col in range(6):
                self.table.item(r, col).setBackground(bg)


# ── Tasks report tab ───────────────────────────────────────────────────────────

class TasksReportTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        _apply_blue_palette(self)
        self._cards = {}
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        stats = QtWidgets.QHBoxLayout()
        stats.setSpacing(8)
        for key in ("Total", "Open", "In Progress", "On Hold", "Completed", "Cancelled"):
            card = _stat_card(key, 0)
            self._cards[key] = card
            stats.addWidget(card)
        stats.addStretch()
        v.addLayout(stats)

        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.setStyleSheet(COMBO_STYLE)
        self.status_filter.addItem("All", None)
        for s in TASK_STATUSES:
            self.status_filter.addItem(s.replace("_", " ").capitalize(), s)
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
        fr.addStretch()
        v.addLayout(fr)

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
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table, stretch=1)

    def _refresh(self):
        status_val = self.status_filter.currentData()
        priority = self.pri_filter.currentData()
        conds, params = [], []
        if status_val:
            conds.append("t.status = %s")
            params.append(status_val)
        if priority:
            conds.append("t.priority = %s")
            params.append(priority)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        conn = get_db()
        rows = conn.execute(
            "SELECT t.*, p.project_number FROM eng_task t"
            " LEFT JOIN eng_project p ON t.project_id = p.id"
            + where + " ORDER BY t.due_date, t.priority", params
        ).fetchall()
        all_rows = conn.execute("SELECT status FROM eng_task").fetchall()
        conn.close()

        counts = {}
        for r in all_rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        for key, db_key in (
            ("Total", None), ("Open", "open"), ("In Progress", "in_progress"),
            ("On Hold", "on_hold"), ("Completed", "completed"), ("Cancelled", "cancelled"),
        ):
            val = len(all_rows) if db_key is None else counts.get(db_key, 0)
            self._cards[key]._val_lbl.setText(str(val))

        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            proj_str = row["project_number"] if row["project_number"] else "—"
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


# ── Design Reviews report tab ──────────────────────────────────────────────────

class DesignReviewReportTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        _apply_blue_palette(self)
        self._cards = {}
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        stats = QtWidgets.QHBoxLayout()
        stats.setSpacing(8)
        for key in ("Total", "Draft", "Pending", "Approved", "Rejected", "Revision Needed"):
            card = _stat_card(key, 0)
            self._cards[key] = card
            stats.addWidget(card)
        stats.addStretch()
        v.addLayout(stats)

        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.setStyleSheet(COMBO_STYLE)
        self.status_filter.addItem("All", None)
        for s in ECR_STATUSES:
            self.status_filter.addItem(s.replace("_", " ").capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.status_filter)
        fr.addStretch()
        v.addLayout(fr)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ECR #", "Title", "Project", "Requested By", "Review Date", "Status"]
        )
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5):
            hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table, stretch=1)

    def _refresh(self):
        status_val = self.status_filter.currentData()
        conds, params = [], []
        if status_val:
            conds.append("d.status = %s")
            params.append(status_val)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        conn = get_db()
        rows = conn.execute(
            "SELECT d.*, p.project_number FROM eng_design_review d"
            " LEFT JOIN eng_project p ON d.project_id = p.id"
            + where + " ORDER BY d.review_date, d.ecr_number", params
        ).fetchall()
        all_rows = conn.execute("SELECT status FROM eng_design_review").fetchall()
        conn.close()

        counts = {}
        for r in all_rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        for key, db_key in (
            ("Total", None), ("Draft", "draft"), ("Pending", "pending"),
            ("Approved", "approved"), ("Rejected", "rejected"),
            ("Revision Needed", "revision_needed"),
        ):
            val = len(all_rows) if db_key is None else counts.get(db_key, 0)
            self._cards[key]._val_lbl.setText(str(val))

        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            proj_str = row["project_number"] if row["project_number"] else "—"
            self.table.setItem(r, 0, _ro(row["ecr_number"]))
            self.table.setItem(r, 1, _ro(row["title"]))
            self.table.setItem(r, 2, _ro(proj_str))
            self.table.setItem(r, 3, _ro(row["requested_by"] or ""))
            self.table.setItem(r, 4, _ro(row["review_date"] or ""))
            self.table.setItem(r, 5, _ro(row["status"].replace("_", " ").capitalize()))
            bg = QtGui.QColor(ECR_COLORS.get(row["status"], "#ffffff"))
            for col in range(6):
                self.table.item(r, col).setBackground(bg)


# ── Embeddable widget (used standalone and embedded in eng_mgr) ────────────────

class EngReportsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(0)
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        self.proj_tab = ProjectsReportTab()
        self.task_tab = TasksReportTab()
        self.ecr_tab = DesignReviewReportTab()
        tabs.addTab(self.proj_tab, "Projects")
        tabs.addTab(self.task_tab, "Tasks")
        tabs.addTab(self.ecr_tab, "Design Reviews")
        v.addWidget(tabs)


# ── Standalone window wrapper ──────────────────────────────────────────────────

class EngReportsMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Engineering Reports")
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self.setCentralWidget(EngReportsWidget())


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = EngReportsMenu()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
