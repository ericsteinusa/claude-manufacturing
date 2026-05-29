"""
it_calls_reports.py — IT Support Calls Reports
Tabs: Ticket Summary | By Department | By Issue Type | Open Tickets | Asset Summary
"""
import sys
from datetime import date
from .db_pg import get_db
from PyQt6 import QtCore, QtGui, QtWidgets
from .it_calls import _apply_blue_palette

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color:white;border:2px solid black;border-radius:8px;"
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
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
    return item


def _make_count_table(headers, rows, stretch_col=0):
    t = QtWidgets.QTableWidget(len(rows), len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
    t.horizontalHeader().setSectionResizeMode(
        stretch_col, QtWidgets.QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            t.setItem(r, c, _ro(val))
    t.resizeColumnsToContents()
    return t


# ── Ticket Summary tab ────────────────────────────────────────────────────────

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

        hdr = QtWidgets.QLabel("Ticket Summary")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        lbl = QtWidgets.QLabel("By Status")
        lbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        v.addWidget(lbl)
        self._status_tbl = QtWidgets.QTableWidget(0, 2)
        self._status_tbl.setHorizontalHeaderLabels(["Status", "Count"])
        self._status_tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._status_tbl.horizontalHeader().setStretchLastSection(True)
        self._status_tbl.verticalHeader().setVisible(False)
        self._status_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._status_tbl.setFixedHeight(150)
        v.addWidget(self._status_tbl)

        lbl2 = QtWidgets.QLabel("By Priority (open tickets)")
        lbl2.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        v.addWidget(lbl2)
        self._pri_tbl = QtWidgets.QTableWidget(0, 2)
        self._pri_tbl.setHorizontalHeaderLabels(["Priority", "Count"])
        self._pri_tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._pri_tbl.horizontalHeader().setStretchLastSection(True)
        self._pri_tbl.verticalHeader().setVisible(False)
        self._pri_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._pri_tbl.setFixedHeight(130)
        v.addWidget(self._pri_tbl)

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
                "SELECT status, COUNT(*) FROM it_ticket GROUP BY status ORDER BY status"
            ).fetchall()
            p_rows = conn.execute(
                "SELECT priority, COUNT(*) FROM it_ticket"
                " WHERE status IN ('open','in_progress','on_hold')"
                " GROUP BY priority ORDER BY priority"
            ).fetchall()
            conn.close()
        except Exception:
            s_rows, p_rows = [], []

        self._status_tbl.setRowCount(len(s_rows))
        for r, row in enumerate(s_rows):
            self._status_tbl.setItem(r, 0, _ro(row[0].replace("_", " ").capitalize()))
            self._status_tbl.setItem(r, 1, _ro(row[1]))

        self._pri_tbl.setRowCount(len(p_rows))
        for r, row in enumerate(p_rows):
            self._pri_tbl.setItem(r, 0, _ro(row[0].capitalize()))
            self._pri_tbl.setItem(r, 1, _ro(row[1]))


# ── By Department tab ─────────────────────────────────────────────────────────

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

        hdr = QtWidgets.QLabel("Tickets by Department")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        self._table = QtWidgets.QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Department", "Open", "Total"])
        self._table.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
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
            rows = conn.execute("""
                SELECT
                    COALESCE(department, '(none)') AS dept,
                    SUM(CASE WHEN status IN ('open','in_progress','on_hold') THEN 1 ELSE 0 END) AS open_cnt,
                    COUNT(*) AS total
                FROM it_ticket
                GROUP BY dept
                ORDER BY total DESC
            """).fetchall()
            conn.close()
        except Exception:
            rows = []

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self._table.setItem(r, 0, _ro(row[0]))
            self._table.setItem(r, 1, _ro(row[1]))
            self._table.setItem(r, 2, _ro(row[2]))
        self._table.resizeColumnsToContents()


# ── By Issue Type tab ─────────────────────────────────────────────────────────

class _ByIssueTypeWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hdr = QtWidgets.QLabel("Tickets by Issue Type")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        self._table = QtWidgets.QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Issue Type", "Open", "Total"])
        self._table.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
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
            rows = conn.execute("""
                SELECT
                    COALESCE(issue_type, '(none)') AS itype,
                    SUM(CASE WHEN status IN ('open','in_progress','on_hold') THEN 1 ELSE 0 END) AS open_cnt,
                    COUNT(*) AS total
                FROM it_ticket
                GROUP BY itype
                ORDER BY total DESC
            """).fetchall()
            conn.close()
        except Exception:
            rows = []

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self._table.setItem(r, 0, _ro(row[0]))
            self._table.setItem(r, 1, _ro(row[1]))
            self._table.setItem(r, 2, _ro(row[2]))
        self._table.resizeColumnsToContents()


# ── Open Tickets tab ──────────────────────────────────────────────────────────

class _OpenTicketsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hdr = QtWidgets.QLabel("Open Tickets")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        self._table = QtWidgets.QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Ticket #", "Requester", "Department", "Issue Type",
             "Priority", "Assigned To", "Due Date"])
        self._table.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
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
                "SELECT ticket_number, requester, department, issue_type,"
                " priority, assigned_to, due_date"
                " FROM it_ticket"
                " WHERE status IN ('open','in_progress','on_hold')"
                " ORDER BY due_date, priority DESC"
            ).fetchall()
            conn.close()
        except Exception:
            rows = []

        OVERDUE_BG = QtGui.QColor(248, 215, 218)
        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            overdue = row[6] and row[6] < TODAY
            for c, val in enumerate(row):
                item = _ro(str(val or ""))
                if overdue:
                    item.setBackground(OVERDUE_BG)
                self._table.setItem(r, c, item)
        self._table.resizeColumnsToContents()


# ── Asset Summary tab ─────────────────────────────────────────────────────────

class _AssetSummaryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        hdr = QtWidgets.QLabel("Asset Summary")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        lbl = QtWidgets.QLabel("By Status")
        lbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        v.addWidget(lbl)
        self._status_tbl = QtWidgets.QTableWidget(0, 2)
        self._status_tbl.setHorizontalHeaderLabels(["Status", "Count"])
        self._status_tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._status_tbl.horizontalHeader().setStretchLastSection(True)
        self._status_tbl.verticalHeader().setVisible(False)
        self._status_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._status_tbl.setFixedHeight(150)
        v.addWidget(self._status_tbl)

        lbl2 = QtWidgets.QLabel("By Asset Type")
        lbl2.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        v.addWidget(lbl2)
        self._type_tbl = QtWidgets.QTableWidget(0, 2)
        self._type_tbl.setHorizontalHeaderLabels(["Asset Type", "Count"])
        self._type_tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._type_tbl.horizontalHeader().setStretchLastSection(True)
        self._type_tbl.verticalHeader().setVisible(False)
        self._type_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._type_tbl.setFixedHeight(150)
        v.addWidget(self._type_tbl)

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
                "SELECT status, COUNT(*) FROM it_asset GROUP BY status ORDER BY status"
            ).fetchall()
            t_rows = conn.execute(
                "SELECT COALESCE(asset_type,'(none)'), COUNT(*)"
                " FROM it_asset GROUP BY asset_type ORDER BY COUNT(*) DESC"
            ).fetchall()
            conn.close()
        except Exception:
            s_rows, t_rows = [], []

        self._status_tbl.setRowCount(len(s_rows))
        for r, row in enumerate(s_rows):
            self._status_tbl.setItem(r, 0, _ro(row[0].capitalize()))
            self._status_tbl.setItem(r, 1, _ro(row[1]))

        self._type_tbl.setRowCount(len(t_rows))
        for r, row in enumerate(t_rows):
            self._type_tbl.setItem(r, 0, _ro(row[0]))
            self._type_tbl.setItem(r, 1, _ro(row[1]))


# ── Top-level widget ──────────────────────────────────────────────────────────

class ITSupportReportsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(_TicketSummaryWidget(),  "Ticket Summary")
        tabs.addTab(_ByDepartmentWidget(),   "By Department")
        tabs.addTab(_ByIssueTypeWidget(),    "By Issue Type")
        tabs.addTab(_OpenTicketsWidget(),    "Open Tickets")
        tabs.addTab(_AssetSummaryWidget(),   "Asset Summary")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = QtWidgets.QMainWindow()
    _apply_blue_palette(w)
    w.setWindowTitle("IT Support Reports")
    w.resize(960, 640)
    w.setCentralWidget(ITSupportReportsWidget())
    w.show()
    sys.exit(app.exec())
