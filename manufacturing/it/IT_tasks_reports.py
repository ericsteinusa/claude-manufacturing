"""
IT_tasks_reports.py — IT Tasks Reports
Tabs: Task Summary | By Technician | By Department | Overdue | Recently
    Completed
"""
import sys
from datetime import date, timedelta
from .db_pg import get_db
from .log_utils import get_logger
from PyQt6 import QtCore, QtGui, QtWidgets
from .qt_theme import apply_blue_palette as _apply_blue_palette

from .button_nav import ButtonNav
log = get_logger(__name__)

BUTTON_STYLE = (
    "QPushButton{background-color:white;border:2px solid "
    "black;border-radius:8px;"
    "padding:4px 12px;font-weight:bold;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)
HDR_STYLE = "font-size:18px;font-weight:bold;color:white;padding:4px;"
TODAY = date.today().isoformat()
THIRTY_DAYS_AGO = (date.today() - timedelta(days=30)).isoformat()
OVERDUE_BG = QtGui.QColor(248, 215, 218)
DONE_BG = QtGui.QColor(212, 237, 218)


def _conn():
    return get_db()


def _ro(text):
    item = QtWidgets.QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable |
                  QtCore.Qt.ItemFlag.ItemIsEnabled)
    return item


def _simple_table(headers, stretch_col=0):
    t = QtWidgets.QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
    t.horizontalHeader().setSectionResizeMode(
        stretch_col, QtWidgets.QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    return t


# ── Task Summary tab ────────────────────────────────────────────────────

class _TaskSummaryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        self._status_tbl: QtWidgets.QTableWidget
        self._pri_tbl: QtWidgets.QTableWidget
        self._type_tbl: QtWidgets.QTableWidget
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        hdr = QtWidgets.QLabel("Task Summary")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        for attr, label, height in [
            ("_status_tbl", "By Status", 160),
            ("_pri_tbl",    "By Priority", 130),
            ("_type_tbl",   "By Task Type", 280),
        ]:
            lbl = QtWidgets.QLabel(label)
            lbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
            v.addWidget(lbl)
            tbl = QtWidgets.QTableWidget(0, 2)
            tbl.setHorizontalHeaderLabels([label.split()[-1], "Count"])
            tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")  # noqa: E501
            tbl.horizontalHeader().setStretchLastSection(True)
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            tbl.setFixedHeight(height)
            v.addWidget(tbl)
            setattr(self, attr, tbl)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)
        v.addStretch()

    def _load(self):
        try:
            conn = _conn()
            s_rows = conn.execute(
                "SELECT status, COUNT(*) FROM it_task GROUP BY status ORDER "
                "BY status"
            ).fetchall()
            p_rows = conn.execute(
                "SELECT priority, COUNT(*) FROM it_task GROUP BY priority "
                "ORDER BY priority"
            ).fetchall()
            t_rows = conn.execute(
                "SELECT COALESCE(task_type,'(none)'), COUNT(*)"
                " FROM it_task GROUP BY task_type ORDER BY COUNT(*) DESC"
            ).fetchall()
            conn.close()
        except Exception:
            log.warning(
                "Report query failed; using empty result",
                exc_info=True)
            s_rows = p_rows = t_rows = []

        for tbl, rows in [(self._status_tbl, s_rows),
                          (self._pri_tbl, p_rows),
                          (self._type_tbl, t_rows)]:
            tbl.setRowCount(len(rows))
            for r, row in enumerate(rows):
                tbl.setItem(
                    r, 0, _ro(str(row[0]).replace("_", " ").capitalize()))
                tbl.setItem(r, 1, _ro(row[1]))


# ── By Technician tab ───────────────────────────────────────────────────

class _ByTechnicianWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hdr = QtWidgets.QLabel("Tasks by Technician")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        self._table = _simple_table(
            ["Assigned To", "Pending", "In Progress", "On Hold", "Completed", "Total"])  # noqa: E501
        self._table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        v.addWidget(self._table, stretch=1)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)

    def _load(self):
        try:
            conn = _conn()
            rows = conn.execute("""
                SELECT
                    COALESCE(assigned_to, '(unassigned)') AS tech,
                    SUM(CASE WHEN status='pending'     THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='on_hold'     THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='completed'   THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_task
                GROUP BY tech
                ORDER BY COUNT(*) DESC
            """).fetchall()
            conn.close()
        except Exception:
            log.warning(
                "Report query failed; using empty result",
                exc_info=True)
            rows = []

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self._table.setItem(r, c, _ro(val))
        self._table.resizeColumnsToContents()


# ── By Department tab ───────────────────────────────────────────────────

class _ByDepartmentWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hdr = QtWidgets.QLabel("Tasks by Department")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        self._table = _simple_table(
            ["Department", "Open", "Completed", "Cancelled", "Total"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        v.addWidget(self._table, stretch=1)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)

    def _load(self):
        try:
            conn = _conn()
            rows = conn.execute("""
                SELECT
                    COALESCE(department, '(none)') AS dept,
                    SUM(CASE WHEN status IN ('pending','in_progress','on_hold')
                        THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='completed'  THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='cancelled'  THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_task
                GROUP BY dept
                ORDER BY COUNT(*) DESC
            """).fetchall()
            conn.close()
        except Exception:
            log.warning(
                "Report query failed; using empty result",
                exc_info=True)
            rows = []

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self._table.setItem(r, c, _ro(val))
        self._table.resizeColumnsToContents()


# ── Overdue Tasks tab ───────────────────────────────────────────────────

class _OverdueWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hdr = QtWidgets.QLabel("Overdue Tasks")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        self._table = _simple_table(
            ["Task #",
    "Task Name",
    "Type",
    "Priority",
    "Assigned To",
    "Department",
    "Due Date",
     "Status"],
            stretch_col=1)
        v.addWidget(self._table, stretch=1)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)

    def _load(self):
        try:
            conn = _conn()
            rows = conn.execute(
                "SELECT task_number, task_name, task_type, priority,"
                " assigned_to, department, due_date, status"
                " FROM it_task"
                " WHERE due_date < %s AND status NOT IN "
                "('completed','cancelled')"
                " ORDER BY due_date, priority DESC",
                (TODAY,)
            ).fetchall()
            conn.close()
        except Exception:
            log.warning(
                "Report query failed; using empty result",
                exc_info=True)
            rows = []

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = _ro(str(val or ""))
                item.setBackground(OVERDUE_BG)
                self._table.setItem(r, c, item)
        self._table.resizeColumnsToContents()


# ── Recently Completed tab ──────────────────────────────────────────────

class _RecentlyCompletedWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hdr = QtWidgets.QLabel("Recently Completed  (last 30 days)")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        self._table = _simple_table(
            ["Task #", "Task Name", "Type", "Assigned To",
                "Department", "Completed Date"],
            stretch_col=1)
        v.addWidget(self._table, stretch=1)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)

    def _load(self):
        try:
            conn = _conn()
            rows = conn.execute(
                "SELECT task_number, task_name, task_type,"
                " assigned_to, department, completed_date"
                " FROM it_task"
                " WHERE status='completed' AND completed_date >= %s"
                " ORDER BY completed_date DESC",
                (THIRTY_DAYS_AGO,)
            ).fetchall()
            conn.close()
        except Exception:
            log.warning(
                "Report query failed; using empty result",
                exc_info=True)
            rows = []

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = _ro(str(val or ""))
                item.setBackground(DONE_BG)
                self._table.setItem(r, c, item)
        self._table.resizeColumnsToContents()


# ── Top-level widget ────────────────────────────────────────────────────

class ITTasksReportsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(_TaskSummaryWidget(),        "Task Summary")
        tabs.addTab(_ByTechnicianWidget(),       "By Technician")
        tabs.addTab(_ByDepartmentWidget(),       "By Department")
        tabs.addTab(_OverdueWidget(),            "Overdue")
        tabs.addTab(_RecentlyCompletedWidget(),  "Recently Completed")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = QtWidgets.QMainWindow()
    _apply_blue_palette(w)
    w.setWindowTitle("IT Tasks Reports")
    w.resize(960, 640)
    w.setCentralWidget(ITTasksReportsWidget())
    w.show()
    sys.exit(app.exec())
