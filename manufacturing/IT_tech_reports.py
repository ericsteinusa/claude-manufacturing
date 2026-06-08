"""
IT_tech_reports.py — IT Technician Reports
Tabs: Task Summary | Ticket Summary | Overdue Tasks | Overdue Tickets
"""
import sys
from datetime import date
from .db_pg import get_db
from .log_utils import get_logger
from PyQt6 import QtCore, QtGui, QtWidgets
from .IT_Tasks import _apply_blue_palette

log = get_logger(__name__)

BLUE = QtGui.QColor(0, 85, 255)
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
LABEL_STYLE = "color:white;font-size:13px;"
TODAY = date.today().isoformat()


def _conn():
    return get_db()


def _ro(text):
    item = QtWidgets.QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable |
                  QtCore.Qt.ItemFlag.ItemIsEnabled)
    return item


def _summary_table(headers, rows):
    t = QtWidgets.QTableWidget(len(rows), len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            t.setItem(r, c, _ro(val))
    t.resizeColumnsToContents()
    return t


# ── Task Summary tab ────────────────────────────────────────────────────

class _TaskSummaryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
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

        lbl_s = QtWidgets.QLabel("By Status")
        lbl_s.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        v.addWidget(lbl_s)
        self._status_table = QtWidgets.QTableWidget(0, 2)
        self._status_table.setHorizontalHeaderLabels(["Status", "Count"])
        self._status_table.horizontalHeader().setStyleSheet(
            "color:black;font-weight:bold;")
        self._status_table.horizontalHeader().setStretchLastSection(True)
        self._status_table.verticalHeader().setVisible(False)
        self._status_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._status_table.setFixedHeight(160)
        v.addWidget(self._status_table)

        lbl_p = QtWidgets.QLabel("By Priority (open tasks)")
        lbl_p.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        v.addWidget(lbl_p)
        self._pri_table = QtWidgets.QTableWidget(0, 2)
        self._pri_table.setHorizontalHeaderLabels(["Priority", "Count"])
        self._pri_table.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")  # noqa: E501
        self._pri_table.horizontalHeader().setStretchLastSection(True)
        self._pri_table.verticalHeader().setVisible(False)
        self._pri_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._pri_table.setFixedHeight(130)
        v.addWidget(self._pri_table)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)
        v.addStretch()

    def _load(self):
        try:
            conn = _conn()
            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM it_task GROUP BY status "
                "ORDER BY status"
            ).fetchall()
            pri_rows = conn.execute(
                "SELECT priority, COUNT(*) AS cnt FROM it_task"
                " WHERE status IN ('pending','in_progress','on_hold')"
                " GROUP BY priority ORDER BY priority"
            ).fetchall()
            conn.close()
        except Exception:
            log.warning(
                "Report query failed; using empty result",
                exc_info=True)
            status_rows, pri_rows = [], []

        self._status_table.setRowCount(len(status_rows))
        for r, row in enumerate(status_rows):
            self._status_table.setItem(
    r, 0, _ro(
        row[0].replace(
            "_", " ").capitalize()))
            self._status_table.setItem(r, 1, _ro(row[1]))

        self._pri_table.setRowCount(len(pri_rows))
        for r, row in enumerate(pri_rows):
            self._pri_table.setItem(r, 0, _ro(row[0].capitalize()))
            self._pri_table.setItem(r, 1, _ro(row[1]))


# ── Ticket Summary tab ──────────────────────────────────────────────────

class _TicketSummaryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        hdr = QtWidgets.QLabel("Support Ticket Summary")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        lbl_s = QtWidgets.QLabel("By Status")
        lbl_s.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        v.addWidget(lbl_s)
        self._status_table = QtWidgets.QTableWidget(0, 2)
        self._status_table.setHorizontalHeaderLabels(["Status", "Count"])
        self._status_table.horizontalHeader().setStyleSheet(
            "color:black;font-weight:bold;")
        self._status_table.horizontalHeader().setStretchLastSection(True)
        self._status_table.verticalHeader().setVisible(False)
        self._status_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._status_table.setFixedHeight(160)
        v.addWidget(self._status_table)

        lbl_p = QtWidgets.QLabel("By Priority (open tickets)")
        lbl_p.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        v.addWidget(lbl_p)
        self._pri_table = QtWidgets.QTableWidget(0, 2)
        self._pri_table.setHorizontalHeaderLabels(["Priority", "Count"])
        self._pri_table.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")  # noqa: E501
        self._pri_table.horizontalHeader().setStretchLastSection(True)
        self._pri_table.verticalHeader().setVisible(False)
        self._pri_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._pri_table.setFixedHeight(130)
        v.addWidget(self._pri_table)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)
        v.addStretch()

    def _load(self):
        try:
            conn = _conn()
            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM it_ticket GROUP BY "
                "status ORDER BY status"
            ).fetchall()
            pri_rows = conn.execute(
                "SELECT priority, COUNT(*) AS cnt FROM it_ticket"
                " WHERE status IN ('open','in_progress','on_hold')"
                " GROUP BY priority ORDER BY priority"
            ).fetchall()
            conn.close()
        except Exception:
            log.warning(
                "Report query failed; using empty result",
                exc_info=True)
            status_rows, pri_rows = [], []

        self._status_table.setRowCount(len(status_rows))
        for r, row in enumerate(status_rows):
            self._status_table.setItem(
    r, 0, _ro(
        row[0].replace(
            "_", " ").capitalize()))
            self._status_table.setItem(r, 1, _ro(row[1]))

        self._pri_table.setRowCount(len(pri_rows))
        for r, row in enumerate(pri_rows):
            self._pri_table.setItem(r, 0, _ro(row[0].capitalize()))
            self._pri_table.setItem(r, 1, _ro(row[1]))


# ── Overdue Tasks tab ───────────────────────────────────────────────────

class _OverdueTasksWidget(QtWidgets.QWidget):
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

        self._table = QtWidgets.QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Task #", "Task Name", "Priority", "Assigned To", "Due Date", "Status"])  # noqa: E501
        self._table.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")  # noqa: E501
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
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
                "SELECT task_number, task_name, priority, assigned_to, "
                "due_date, status"
                " FROM it_task"
                " WHERE due_date < %s AND status NOT IN "
                "('completed','cancelled')"
                " ORDER BY due_date",
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
                item.setBackground(QtGui.QColor(248, 215, 218))
                self._table.setItem(r, c, item)
        self._table.resizeColumnsToContents()


# ── Overdue Tickets tab ─────────────────────────────────────────────────

class _OverdueTicketsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hdr = QtWidgets.QLabel("Overdue Support Tickets")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        self._table = QtWidgets.QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Ticket #", "Requester", "Department", "Priority", "Due Date", "Status"])  # noqa: E501
        self._table.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")  # noqa: E501
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
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
                "SELECT ticket_number, requester, department, priority, "
                "due_date, status"
                " FROM it_ticket"
                " WHERE due_date < %s AND status NOT IN ('resolved','closed')"
                " ORDER BY due_date",
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
                item.setBackground(QtGui.QColor(248, 215, 218))
                self._table.setItem(r, c, item)
        self._table.resizeColumnsToContents()


# ── Top-level widget ────────────────────────────────────────────────────

class ITTechReportsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(_TaskSummaryWidget(),   "Task Summary")
        tabs.addTab(_TicketSummaryWidget(), "Ticket Summary")
        tabs.addTab(_OverdueTasksWidget(),  "Overdue Tasks")
        tabs.addTab(_OverdueTicketsWidget(), "Overdue Tickets")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = QtWidgets.QMainWindow()
    _apply_blue_palette(w)
    w.setWindowTitle("IT Technician Reports")
    w.resize(900, 600)
    w.setCentralWidget(ITTechReportsWidget())
    w.show()
    sys.exit(app.exec())
