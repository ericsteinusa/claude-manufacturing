"""
IT_mgr_reports.py — IT Manager Reports
Tabs: Overview | By Technician | By Department | Overdue | Asset Inventory
"""
import sys
from datetime import date
from db_pg import get_db
from PyQt6 import QtCore, QtGui, QtWidgets
from IT_Tasks import _apply_blue_palette

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
SEC_STYLE = "color:white;font-weight:bold;font-size:13px;"
TODAY = date.today().isoformat()
OVERDUE_BG = QtGui.QColor(248, 215, 218)


def _conn():
    return get_db()


def _ro(text):
    item = QtWidgets.QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
    return item


def _simple_table(headers, stretch_col=0):
    t = QtWidgets.QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
    t.horizontalHeader().setSectionResizeMode(
        stretch_col, QtWidgets.QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    return t


# ── Overview tab ──────────────────────────────────────────────────────────────

class _OverviewWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12); v.setSpacing(10)

        hdr = QtWidgets.QLabel("IT Department Overview")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        row = QtWidgets.QHBoxLayout(); row.setSpacing(16)

        # Tasks by status
        left = QtWidgets.QVBoxLayout()
        lbl = QtWidgets.QLabel("Tasks by Status")
        lbl.setStyleSheet(SEC_STYLE)
        left.addWidget(lbl)
        self._task_status_tbl = QtWidgets.QTableWidget(0, 2)
        self._task_status_tbl.setHorizontalHeaderLabels(["Status", "Count"])
        self._task_status_tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._task_status_tbl.horizontalHeader().setStretchLastSection(True)
        self._task_status_tbl.verticalHeader().setVisible(False)
        self._task_status_tbl.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._task_status_tbl.setFixedHeight(160)
        left.addWidget(self._task_status_tbl)
        row.addLayout(left)

        # Tickets by status
        right = QtWidgets.QVBoxLayout()
        lbl2 = QtWidgets.QLabel("Tickets by Status")
        lbl2.setStyleSheet(SEC_STYLE)
        right.addWidget(lbl2)
        self._ticket_status_tbl = QtWidgets.QTableWidget(0, 2)
        self._ticket_status_tbl.setHorizontalHeaderLabels(["Status", "Count"])
        self._ticket_status_tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._ticket_status_tbl.horizontalHeader().setStretchLastSection(True)
        self._ticket_status_tbl.verticalHeader().setVisible(False)
        self._ticket_status_tbl.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._ticket_status_tbl.setFixedHeight(160)
        right.addWidget(self._ticket_status_tbl)
        row.addLayout(right)

        v.addLayout(row)

        row2 = QtWidgets.QHBoxLayout(); row2.setSpacing(16)

        # Overdue counts
        left2 = QtWidgets.QVBoxLayout()
        lbl3 = QtWidgets.QLabel("Overdue Summary")
        lbl3.setStyleSheet(SEC_STYLE)
        left2.addWidget(lbl3)
        self._overdue_tbl = QtWidgets.QTableWidget(0, 2)
        self._overdue_tbl.setHorizontalHeaderLabels(["Category", "Count"])
        self._overdue_tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._overdue_tbl.horizontalHeader().setStretchLastSection(True)
        self._overdue_tbl.verticalHeader().setVisible(False)
        self._overdue_tbl.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._overdue_tbl.setFixedHeight(90)
        left2.addWidget(self._overdue_tbl)
        row2.addLayout(left2)

        # Asset counts
        right2 = QtWidgets.QVBoxLayout()
        lbl4 = QtWidgets.QLabel("Assets by Status")
        lbl4.setStyleSheet(SEC_STYLE)
        right2.addWidget(lbl4)
        self._asset_tbl = QtWidgets.QTableWidget(0, 2)
        self._asset_tbl.setHorizontalHeaderLabels(["Status", "Count"])
        self._asset_tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._asset_tbl.horizontalHeader().setStretchLastSection(True)
        self._asset_tbl.verticalHeader().setVisible(False)
        self._asset_tbl.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._asset_tbl.setFixedHeight(150)
        right2.addWidget(self._asset_tbl)
        row2.addLayout(right2)

        v.addLayout(row2)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE); btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)
        v.addStretch()

    def _load(self):
        try:
            conn = _conn()
            task_rows = conn.execute(
                "SELECT status, COUNT(*) FROM it_task GROUP BY status ORDER BY status"
            ).fetchall()
            ticket_rows = conn.execute(
                "SELECT status, COUNT(*) FROM it_ticket GROUP BY status ORDER BY status"
            ).fetchall()
            overdue_tasks = conn.execute(
                "SELECT COUNT(*) FROM it_task"
                " WHERE due_date < %s AND status NOT IN ('completed','cancelled')",
                (TODAY,)
            ).fetchone()[0]
            overdue_tickets = conn.execute(
                "SELECT COUNT(*) FROM it_ticket"
                " WHERE due_date < %s AND status NOT IN ('resolved','closed','cancelled')",
                (TODAY,)
            ).fetchone()[0]
            asset_rows = conn.execute(
                "SELECT status, COUNT(*) FROM it_asset GROUP BY status ORDER BY status"
            ).fetchall()
            conn.close()
        except Exception:
            task_rows = ticket_rows = asset_rows = []
            overdue_tasks = overdue_tickets = 0

        self._task_status_tbl.setRowCount(len(task_rows))
        for r, row in enumerate(task_rows):
            self._task_status_tbl.setItem(r, 0, _ro(row[0].replace("_", " ").capitalize()))
            self._task_status_tbl.setItem(r, 1, _ro(row[1]))

        self._ticket_status_tbl.setRowCount(len(ticket_rows))
        for r, row in enumerate(ticket_rows):
            self._ticket_status_tbl.setItem(r, 0, _ro(row[0].replace("_", " ").capitalize()))
            self._ticket_status_tbl.setItem(r, 1, _ro(row[1]))

        overdue_data = [("Overdue Tasks", overdue_tasks), ("Overdue Tickets", overdue_tickets)]
        self._overdue_tbl.setRowCount(2)
        for r, (label, cnt) in enumerate(overdue_data):
            item = _ro(label)
            cnt_item = _ro(cnt)
            if cnt:
                item.setBackground(OVERDUE_BG)
                cnt_item.setBackground(OVERDUE_BG)
            self._overdue_tbl.setItem(r, 0, item)
            self._overdue_tbl.setItem(r, 1, cnt_item)

        self._asset_tbl.setRowCount(len(asset_rows))
        for r, row in enumerate(asset_rows):
            self._asset_tbl.setItem(r, 0, _ro(row[0].capitalize()))
            self._asset_tbl.setItem(r, 1, _ro(row[1]))


# ── By Technician tab ─────────────────────────────────────────────────────────

class _ByTechnicianWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12); v.setSpacing(8)

        hdr = QtWidgets.QLabel("Workload by Technician")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        lbl = QtWidgets.QLabel("Tasks per Technician")
        lbl.setStyleSheet(SEC_STYLE)
        v.addWidget(lbl)
        self._task_tbl = _simple_table(
            ["Assigned To", "Pending", "In Progress", "On Hold", "Completed", "Total"])
        self._task_tbl.setFixedHeight(200)
        v.addWidget(self._task_tbl)

        lbl2 = QtWidgets.QLabel("Tickets per Technician")
        lbl2.setStyleSheet(SEC_STYLE)
        v.addWidget(lbl2)
        self._ticket_tbl = _simple_table(
            ["Assigned To", "Open", "In Progress", "On Hold", "Resolved", "Total"])
        v.addWidget(self._ticket_tbl, stretch=1)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE); btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)

    def _load(self):
        try:
            conn = _conn()
            task_rows = conn.execute("""
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
            ticket_rows = conn.execute("""
                SELECT
                    COALESCE(assigned_to, '(unassigned)') AS tech,
                    SUM(CASE WHEN status='open'        THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='on_hold'     THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='resolved'    THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_ticket
                GROUP BY tech
                ORDER BY COUNT(*) DESC
            """).fetchall()
            conn.close()
        except Exception:
            task_rows = ticket_rows = []

        self._task_tbl.setRowCount(len(task_rows))
        for r, row in enumerate(task_rows):
            for c, val in enumerate(row):
                self._task_tbl.setItem(r, c, _ro(val))
        self._task_tbl.resizeColumnsToContents()

        self._ticket_tbl.setRowCount(len(ticket_rows))
        for r, row in enumerate(ticket_rows):
            for c, val in enumerate(row):
                self._ticket_tbl.setItem(r, c, _ro(val))
        self._ticket_tbl.resizeColumnsToContents()


# ── By Department tab ─────────────────────────────────────────────────────────

class _ByDepartmentWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12); v.setSpacing(8)

        hdr = QtWidgets.QLabel("Activity by Department")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        lbl = QtWidgets.QLabel("Tasks per Department")
        lbl.setStyleSheet(SEC_STYLE)
        v.addWidget(lbl)
        self._task_tbl = _simple_table(
            ["Department", "Open", "Completed", "Cancelled", "Total"])
        self._task_tbl.setFixedHeight(200)
        v.addWidget(self._task_tbl)

        lbl2 = QtWidgets.QLabel("Tickets per Department")
        lbl2.setStyleSheet(SEC_STYLE)
        v.addWidget(lbl2)
        self._ticket_tbl = _simple_table(
            ["Department", "Open", "Resolved", "Cancelled", "Total"])
        v.addWidget(self._ticket_tbl, stretch=1)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE); btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)

    def _load(self):
        try:
            conn = _conn()
            task_rows = conn.execute("""
                SELECT
                    COALESCE(department, '(none)') AS dept,
                    SUM(CASE WHEN status IN ('pending','in_progress','on_hold') THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='completed'  THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='cancelled'  THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_task
                GROUP BY dept
                ORDER BY COUNT(*) DESC
            """).fetchall()
            ticket_rows = conn.execute("""
                SELECT
                    COALESCE(department, '(none)') AS dept,
                    SUM(CASE WHEN status IN ('open','in_progress','on_hold') THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='resolved'   THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='cancelled'  THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_ticket
                GROUP BY dept
                ORDER BY COUNT(*) DESC
            """).fetchall()
            conn.close()
        except Exception:
            task_rows = ticket_rows = []

        self._task_tbl.setRowCount(len(task_rows))
        for r, row in enumerate(task_rows):
            for c, val in enumerate(row):
                self._task_tbl.setItem(r, c, _ro(val))
        self._task_tbl.resizeColumnsToContents()

        self._ticket_tbl.setRowCount(len(ticket_rows))
        for r, row in enumerate(ticket_rows):
            for c, val in enumerate(row):
                self._ticket_tbl.setItem(r, c, _ro(val))
        self._ticket_tbl.resizeColumnsToContents()


# ── Overdue tab ───────────────────────────────────────────────────────────────

class _OverdueWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12); v.setSpacing(8)

        hdr = QtWidgets.QLabel("Overdue Items")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        lbl = QtWidgets.QLabel("Overdue Tasks")
        lbl.setStyleSheet(SEC_STYLE)
        v.addWidget(lbl)
        self._task_tbl = _simple_table(
            ["Task #", "Task Name", "Priority", "Assigned To", "Department", "Due Date"],
            stretch_col=1)
        self._task_tbl.setFixedHeight(220)
        v.addWidget(self._task_tbl)

        lbl2 = QtWidgets.QLabel("Overdue Tickets")
        lbl2.setStyleSheet(SEC_STYLE)
        v.addWidget(lbl2)
        self._ticket_tbl = _simple_table(
            ["Ticket #", "Requester", "Priority", "Assigned To", "Department", "Due Date"],
            stretch_col=1)
        v.addWidget(self._ticket_tbl, stretch=1)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE); btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)

    def _load(self):
        try:
            conn = _conn()
            task_rows = conn.execute(
                "SELECT task_number, task_name, priority, assigned_to, department, due_date"
                " FROM it_task"
                " WHERE due_date < %s AND status NOT IN ('completed','cancelled')"
                " ORDER BY due_date, priority DESC",
                (TODAY,)
            ).fetchall()
            ticket_rows = conn.execute(
                "SELECT ticket_number, requester, priority, assigned_to, department, due_date"
                " FROM it_ticket"
                " WHERE due_date < %s AND status NOT IN ('resolved','closed','cancelled')"
                " ORDER BY due_date, priority DESC",
                (TODAY,)
            ).fetchall()
            conn.close()
        except Exception:
            task_rows = ticket_rows = []

        self._task_tbl.setRowCount(len(task_rows))
        for r, row in enumerate(task_rows):
            for c, val in enumerate(row):
                item = _ro(str(val or ""))
                item.setBackground(OVERDUE_BG)
                self._task_tbl.setItem(r, c, item)
        self._task_tbl.resizeColumnsToContents()

        self._ticket_tbl.setRowCount(len(ticket_rows))
        for r, row in enumerate(ticket_rows):
            for c, val in enumerate(row):
                item = _ro(str(val or ""))
                item.setBackground(OVERDUE_BG)
                self._ticket_tbl.setItem(r, c, item)
        self._ticket_tbl.resizeColumnsToContents()


# ── Asset Inventory tab ───────────────────────────────────────────────────────

class _AssetInventoryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12); v.setSpacing(8)

        hdr = QtWidgets.QLabel("Asset Inventory")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        row = QtWidgets.QHBoxLayout(); row.setSpacing(16)

        left = QtWidgets.QVBoxLayout()
        lbl = QtWidgets.QLabel("By Status")
        lbl.setStyleSheet(SEC_STYLE)
        left.addWidget(lbl)
        self._status_tbl = QtWidgets.QTableWidget(0, 2)
        self._status_tbl.setHorizontalHeaderLabels(["Status", "Count"])
        self._status_tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._status_tbl.horizontalHeader().setStretchLastSection(True)
        self._status_tbl.verticalHeader().setVisible(False)
        self._status_tbl.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._status_tbl.setFixedHeight(170)
        left.addWidget(self._status_tbl)
        row.addLayout(left)

        right = QtWidgets.QVBoxLayout()
        lbl2 = QtWidgets.QLabel("By Asset Type")
        lbl2.setStyleSheet(SEC_STYLE)
        right.addWidget(lbl2)
        self._type_tbl = QtWidgets.QTableWidget(0, 2)
        self._type_tbl.setHorizontalHeaderLabels(["Asset Type", "Count"])
        self._type_tbl.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
        self._type_tbl.horizontalHeader().setStretchLastSection(True)
        self._type_tbl.verticalHeader().setVisible(False)
        self._type_tbl.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._type_tbl.setFixedHeight(170)
        right.addWidget(self._type_tbl)
        row.addLayout(right)

        v.addLayout(row)

        lbl3 = QtWidgets.QLabel("All Assets")
        lbl3.setStyleSheet(SEC_STYLE)
        v.addWidget(lbl3)
        self._all_tbl = _simple_table(
            ["Asset Tag", "Asset Name", "Type", "Status", "Assigned To", "Department",
             "Purchase Date"],
            stretch_col=1)
        v.addWidget(self._all_tbl, stretch=1)

        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE); btn.setFixedWidth(100)
        btn.clicked.connect(self._load)
        v.addWidget(btn)

    def _load(self):
        try:
            conn = _conn()
            status_rows = conn.execute(
                "SELECT status, COUNT(*) FROM it_asset GROUP BY status ORDER BY status"
            ).fetchall()
            type_rows = conn.execute(
                "SELECT COALESCE(asset_type,'(none)'), COUNT(*)"
                " FROM it_asset GROUP BY asset_type ORDER BY COUNT(*) DESC"
            ).fetchall()
            all_rows = conn.execute(
                "SELECT asset_tag, asset_name, asset_type, status,"
                " assigned_to, department, purchase_date"
                " FROM it_asset ORDER BY asset_type, asset_name"
            ).fetchall()
            conn.close()
        except Exception:
            status_rows = type_rows = all_rows = []

        self._status_tbl.setRowCount(len(status_rows))
        for r, row in enumerate(status_rows):
            self._status_tbl.setItem(r, 0, _ro(row[0].capitalize()))
            self._status_tbl.setItem(r, 1, _ro(row[1]))

        self._type_tbl.setRowCount(len(type_rows))
        for r, row in enumerate(type_rows):
            self._type_tbl.setItem(r, 0, _ro(row[0]))
            self._type_tbl.setItem(r, 1, _ro(row[1]))

        self._all_tbl.setRowCount(len(all_rows))
        for r, row in enumerate(all_rows):
            for c, val in enumerate(row):
                self._all_tbl.setItem(r, c, _ro(str(val or "")))
        self._all_tbl.resizeColumnsToContents()


# ── Top-level widget ──────────────────────────────────────────────────────────

class ITMgrReportsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(_OverviewWidget(),        "Overview")
        tabs.addTab(_ByTechnicianWidget(),    "By Technician")
        tabs.addTab(_ByDepartmentWidget(),    "By Department")
        tabs.addTab(_OverdueWidget(),         "Overdue")
        tabs.addTab(_AssetInventoryWidget(),  "Asset Inventory")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = QtWidgets.QMainWindow()
    _apply_blue_palette(w)
    w.setWindowTitle("IT Manager Reports")
    w.resize(1000, 680)
    w.setCentralWidget(ITMgrReportsWidget())
    w.show()
    sys.exit(app.exec())
