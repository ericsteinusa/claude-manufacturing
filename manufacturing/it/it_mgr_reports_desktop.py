"""
it_mgr_reports_desktop.py — IT Manager Reports (native PostgreSQL).

Six tabs:
  Overview        — KPI cards + summary tables
  By Technician   — workload pivot for tasks and tickets
  By Department   — activity pivot per requesting department
  Overdue         — overdue tasks and tickets with age
  Asset Inventory — status/type breakdown + full asset list
  SLA & Performance — resolution rates, avg age, ticket throughput
"""
import sys
from datetime import date, timedelta
from typing import Callable, Any
from ..db_pg import get_db_connection
from PyQt6 import QtCore, QtGui, QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..button_nav import ButtonNav
from ..log_utils import get_logger

log = get_logger(__name__)

TODAY = date.today().isoformat()
THIRTY_DAYS_AGO = (date.today() - timedelta(days=30)).isoformat()
NINETY_DAYS_OUT = (date.today() + timedelta(days=90)).isoformat()

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 16px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)
BTN_STYLE = (
    "QPushButton{background-color:white;border:2px solid black;"
    "border-radius:8px;padding:4px 14px;font-weight:bold;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
)
HDR_STYLE = "font-size:17px;font-weight:bold;color:white;padding:4px;"
SEC_STYLE = "color:white;font-weight:bold;font-size:13px;margin-top:6px;"
CARD_STYLE = (
    "QLabel{background:white;border:2px solid black;border-radius:6px;"
    "padding:8px 14px;font-size:13px;font-weight:bold;}"
)
OVERDUE_BG = QtGui.QColor(248, 215, 218)
DONE_BG = QtGui.QColor(212, 237, 218)
WARN_BG = QtGui.QColor(255, 243, 205)


def _db():
    return get_db_connection()


def _ro(val) -> QtWidgets.QTableWidgetItem:
    item = QtWidgets.QTableWidgetItem(
        str(val) if val is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable |
                  QtCore.Qt.ItemFlag.ItemIsEnabled)
    return item


def _tbl(headers: list[str], stretch_col: int = 0) -> QtWidgets.QTableWidget:
    t = QtWidgets.QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setStyleSheet("color:black;font-weight:bold;")
    t.horizontalHeader().setSectionResizeMode(
        stretch_col, QtWidgets.QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(
        QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(
        QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    return t


def _fill(table: QtWidgets.QTableWidget, rows,
          bg: QtGui.QColor | None = None):
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            item = _ro(str(val or ""))
            if bg:
                item.setBackground(bg)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()


def _count_tbl(headers=("Category", "Count")) -> QtWidgets.QTableWidget:
    t = _tbl(list(headers))
    t.setFixedHeight(160)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def _fill_count(t: QtWidgets.QTableWidget, rows,
                fmt0: Callable[[Any], str] = str):
    t.setRowCount(len(rows))
    for r, row in enumerate(rows):
        t.setItem(r, 0, _ro(fmt0(row[0]) if row[0] is not None else ""))
        t.setItem(r, 1, _ro(row[1]))


def _section_lbl(text: str) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    lbl.setStyleSheet(SEC_STYLE)
    return lbl


def _refresh_btn(slot) -> QtWidgets.QPushButton:
    btn = QtWidgets.QPushButton("Refresh")
    btn.setStyleSheet(BTN_STYLE)
    btn.setFixedWidth(90)
    btn.clicked.connect(slot)
    return btn


def _scrolled(widget: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    sa = QtWidgets.QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    sa.setWidget(widget)
    return sa


# ===========================================================================
# 1. Overview
# ===========================================================================

class _OverviewWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._cards: dict[str, QtWidgets.QLabel] = {}
        self._build_ui()
        self._load()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QtWidgets.QWidget()
        _apply_blue_palette(inner)
        v = QtWidgets.QVBoxLayout(inner)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        hdr = QtWidgets.QLabel("IT Department Overview")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        card_defs = [
            ("open_tickets",     "Open Tickets"),
            ("inprog_tickets",   "In Progress Tickets"),
            ("overdue_tickets",  "Overdue Tickets"),
            ("critical_tickets", "Critical Tickets"),
            ("open_tasks",       "Open Tasks"),
            ("overdue_tasks",    "Overdue Tasks"),
            ("on_hold_tasks",    "On-Hold Tasks"),
            ("active_assets",    "Active Assets"),
            ("repair_assets",    "Assets in Repair"),
            ("open_repairs",     "Open Repairs"),
            ("active_licenses",  "Active Licenses"),
            ("expiring_lic",     "Licenses Expiring (90d)"),
        ]
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        for i, (key, label) in enumerate(card_defs):
            card = QtWidgets.QLabel(f"{label}\n—")
            card.setStyleSheet(CARD_STYLE)
            card.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(card, i // 4, i % 4)
            self._cards[key] = card
        v.addLayout(grid)

        # Recent unassigned tickets
        v.addWidget(_section_lbl("Unassigned Open Tickets"))
        self._unassigned = _tbl(
            ["Ticket #", "Requester", "Department",
             "Issue Type", "Priority", "Submitted"], stretch_col=1)
        self._unassigned.setFixedHeight(180)
        v.addWidget(self._unassigned)

        # Tasks with no assignee
        v.addWidget(_section_lbl("Unassigned Open Tasks"))
        self._unassigned_tasks = _tbl(
            ["Task #", "Task Name", "Type", "Priority",
             "Department", "Due Date"], stretch_col=1)
        self._unassigned_tasks.setFixedHeight(160)
        v.addWidget(self._unassigned_tasks)

        v.addWidget(_refresh_btn(self._load))
        v.addStretch()
        outer.addWidget(_scrolled(inner))

    def _load(self):
        conn = _db()
        try:
            def qi(sql, *p):
                row = conn.execute(sql, p).fetchone()
                return (row[0] or 0) if row else 0

            vals = {
                "open_tickets": qi(
                    "SELECT COUNT(*) FROM it_ticket WHERE status='open'"),
                "inprog_tickets": qi(
                    "SELECT COUNT(*) FROM it_ticket WHERE status='in_progress'"),
                "overdue_tickets": qi(
                    "SELECT COUNT(*) FROM it_ticket "
                    "WHERE due_date<%s AND status NOT IN ('resolved','closed')",
                    TODAY),
                "critical_tickets": qi(
                    "SELECT COUNT(*) FROM it_ticket "
                    "WHERE priority='critical' AND status NOT IN ('resolved','closed')"),
                "open_tasks": qi(
                    "SELECT COUNT(*) FROM it_task "
                    "WHERE status IN ('pending','in_progress','on_hold')"),
                "overdue_tasks": qi(
                    "SELECT COUNT(*) FROM it_task "
                    "WHERE due_date<%s AND status NOT IN ('completed','cancelled')",
                    TODAY),
                "on_hold_tasks": qi(
                    "SELECT COUNT(*) FROM it_task WHERE status='on_hold'"),
                "active_assets": qi(
                    "SELECT COUNT(*) FROM it_asset WHERE status='active'"),
                "repair_assets": qi(
                    "SELECT COUNT(*) FROM it_asset WHERE status='repair'"),
                "open_repairs": qi(
                    "SELECT COUNT(*) FROM it_repair "
                    "WHERE status IN ('open','in_progress')"),
                "active_licenses": qi(
                    "SELECT COUNT(*) FROM it_license WHERE status='active'"),
                "expiring_lic": qi(
                    "SELECT COUNT(*) FROM it_license "
                    "WHERE status='active' AND expiry_date BETWEEN %s AND %s",
                    TODAY, NINETY_DAYS_OUT),
            }
            for key, card in self._cards.items():
                label_text = card.text().split("\n")[0]
                card.setText(f"{label_text}\n{vals.get(key, 0)}")

            ua_rows = conn.execute(
                "SELECT ticket_number, requester, department, issue_type,"
                " priority, submitted_date FROM it_ticket "
                "WHERE status IN ('open','in_progress') "
                "AND (assigned_to IS NULL OR assigned_to='')"
                " ORDER BY submitted_date LIMIT 20"
            ).fetchall()
            _fill(self._unassigned, ua_rows, bg=WARN_BG)

            ut_rows = conn.execute(
                "SELECT task_number, task_name, task_type, priority,"
                " department, due_date FROM it_task "
                "WHERE status IN ('pending','in_progress') "
                "AND (assigned_to IS NULL OR assigned_to='')"
                " ORDER BY due_date LIMIT 20"
            ).fetchall()
            _fill(self._unassigned_tasks, ut_rows, bg=WARN_BG)
        except Exception:
            log.warning("Overview load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# 2. By Technician
# ===========================================================================

class _ByTechnicianWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QtWidgets.QWidget()
        _apply_blue_palette(inner)
        v = QtWidgets.QVBoxLayout(inner)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        hdr = QtWidgets.QLabel("Workload by Technician")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        v.addWidget(_section_lbl("Tasks per Technician"))
        self._task_tbl = _tbl(
            ["Technician", "Pending", "In Progress",
             "On Hold", "Completed", "Overdue", "Total"])
        self._task_tbl.setFixedHeight(220)
        v.addWidget(self._task_tbl)

        v.addWidget(_section_lbl("Tickets per Technician"))
        self._ticket_tbl = _tbl(
            ["Technician", "Open", "In Progress",
             "Resolved", "Overdue", "Avg Age (days)", "Total"])
        self._ticket_tbl.setFixedHeight(220)
        v.addWidget(self._ticket_tbl)

        v.addWidget(_refresh_btn(self._load))
        v.addStretch()
        outer.addWidget(_scrolled(inner))

    def _load(self):
        conn = _db()
        try:
            task_rows = conn.execute(f"""
                SELECT
                    COALESCE(assigned_to,'(unassigned)'),
                    SUM(CASE WHEN status='pending'     THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='on_hold'     THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='completed'   THEN 1 ELSE 0 END),
                    SUM(CASE WHEN due_date < '{TODAY}' AND status NOT IN
                        ('completed','cancelled') THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_task GROUP BY 1 ORDER BY COUNT(*) DESC
            """).fetchall()
            _fill(self._task_tbl, task_rows)

            ticket_rows = conn.execute(f"""
                SELECT
                    COALESCE(assigned_to,'(unassigned)'),
                    SUM(CASE WHEN status='open'        THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='resolved'    THEN 1 ELSE 0 END),
                    SUM(CASE WHEN due_date < '{TODAY}' AND status NOT IN
                        ('resolved','closed') THEN 1 ELSE 0 END),
                    ROUND(AVG(
                        CASE WHEN status NOT IN ('resolved','closed')
                        THEN (CURRENT_DATE - submitted_date::date) END
                    )::numeric, 1),
                    COUNT(*)
                FROM it_ticket GROUP BY 1 ORDER BY COUNT(*) DESC
            """).fetchall()
            _fill(self._ticket_tbl, ticket_rows)
        except Exception:
            log.warning("By Technician load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# 3. By Department
# ===========================================================================

class _ByDepartmentWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QtWidgets.QWidget()
        _apply_blue_palette(inner)
        v = QtWidgets.QVBoxLayout(inner)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        hdr = QtWidgets.QLabel("Activity by Department")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        v.addWidget(_section_lbl("Tasks per Department"))
        self._task_tbl = _tbl(
            ["Department", "Pending", "In Progress",
             "On Hold", "Completed", "Cancelled", "Total"])
        self._task_tbl.setFixedHeight(220)
        v.addWidget(self._task_tbl)

        v.addWidget(_section_lbl("Tickets per Department"))
        self._ticket_tbl = _tbl(
            ["Department", "Open", "In Progress",
             "Resolved", "Closed", "Total"])
        self._ticket_tbl.setFixedHeight(220)
        v.addWidget(self._ticket_tbl)

        v.addWidget(_refresh_btn(self._load))
        v.addStretch()
        outer.addWidget(_scrolled(inner))

    def _load(self):
        conn = _db()
        try:
            task_rows = conn.execute("""
                SELECT COALESCE(department,'(none)'),
                    SUM(CASE WHEN status='pending'     THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='on_hold'     THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='completed'   THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='cancelled'   THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_task GROUP BY 1 ORDER BY COUNT(*) DESC
            """).fetchall()
            _fill(self._task_tbl, task_rows)

            ticket_rows = conn.execute("""
                SELECT COALESCE(department,'(none)'),
                    SUM(CASE WHEN status='open'        THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='resolved'    THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='closed'      THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_ticket GROUP BY 1 ORDER BY COUNT(*) DESC
            """).fetchall()
            _fill(self._ticket_tbl, ticket_rows)
        except Exception:
            log.warning("By Department load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# 4. Overdue
# ===========================================================================

class _OverdueWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QtWidgets.QWidget()
        _apply_blue_palette(inner)
        v = QtWidgets.QVBoxLayout(inner)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        hdr = QtWidgets.QLabel("Overdue Items")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        v.addWidget(_section_lbl("Overdue Tasks"))
        self._task_tbl = _tbl(
            ["Task #", "Task Name", "Priority", "Assigned To",
             "Department", "Due Date", "Days Overdue"], stretch_col=1)
        self._task_tbl.setFixedHeight(240)
        v.addWidget(self._task_tbl)

        v.addWidget(_section_lbl("Overdue Tickets"))
        self._ticket_tbl = _tbl(
            ["Ticket #", "Requester", "Priority", "Assigned To",
             "Department", "Due Date", "Days Overdue"], stretch_col=1)
        self._ticket_tbl.setFixedHeight(240)
        v.addWidget(self._ticket_tbl)

        v.addWidget(_refresh_btn(self._load))
        v.addStretch()
        outer.addWidget(_scrolled(inner))

    def _load(self):
        conn = _db()
        try:
            task_rows = conn.execute(f"""
                SELECT task_number, task_name, priority, assigned_to,
                    department, due_date,
                    (CURRENT_DATE - due_date::date) AS days_over
                FROM it_task
                WHERE due_date < '{TODAY}'
                AND status NOT IN ('completed','cancelled')
                ORDER BY due_date
            """).fetchall()
            self._task_tbl.setRowCount(len(task_rows))
            for r, row in enumerate(task_rows):
                for c, val in enumerate(row):
                    item = _ro(str(val or ""))
                    item.setBackground(OVERDUE_BG)
                    self._task_tbl.setItem(r, c, item)
            self._task_tbl.resizeColumnsToContents()

            ticket_rows = conn.execute(f"""
                SELECT ticket_number, requester, priority, assigned_to,
                    department, due_date,
                    (CURRENT_DATE - due_date::date) AS days_over
                FROM it_ticket
                WHERE due_date < '{TODAY}'
                AND status NOT IN ('resolved','closed')
                ORDER BY due_date
            """).fetchall()
            self._ticket_tbl.setRowCount(len(ticket_rows))
            for r, row in enumerate(ticket_rows):
                for c, val in enumerate(row):
                    item = _ro(str(val or ""))
                    item.setBackground(OVERDUE_BG)
                    self._ticket_tbl.setItem(r, c, item)
            self._ticket_tbl.resizeColumnsToContents()
        except Exception:
            log.warning("Overdue load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# 5. Asset Inventory
# ===========================================================================

class _AssetInventoryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QtWidgets.QWidget()
        _apply_blue_palette(inner)
        v = QtWidgets.QVBoxLayout(inner)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        hdr = QtWidgets.QLabel("Asset Inventory")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        row1 = QtWidgets.QHBoxLayout()
        blk_s = QtWidgets.QVBoxLayout()
        blk_s.addWidget(_section_lbl("By Status"))
        self._status_tbl = _count_tbl(("Status", "Count"))
        blk_s.addWidget(self._status_tbl)
        row1.addLayout(blk_s)
        blk_t = QtWidgets.QVBoxLayout()
        blk_t.addWidget(_section_lbl("By Asset Type"))
        self._type_tbl = _count_tbl(("Asset Type", "Count"))
        blk_t.addWidget(self._type_tbl)
        row1.addLayout(blk_t)
        blk_d = QtWidgets.QVBoxLayout()
        blk_d.addWidget(_section_lbl("By Department"))
        self._dept_tbl = _count_tbl(("Department", "Count"))
        blk_d.addWidget(self._dept_tbl)
        row1.addLayout(blk_d)
        v.addLayout(row1)

        v.addWidget(_section_lbl(
            f"Warranty Expiring Within 90 Days (by {NINETY_DAYS_OUT})"))
        self._warranty_tbl = _tbl(
            ["Asset Tag", "Type", "Make", "Model",
             "Assigned To", "Department", "Warranty Exp"], stretch_col=2)
        self._warranty_tbl.setFixedHeight(180)
        v.addWidget(self._warranty_tbl)

        v.addWidget(_section_lbl("All Assets"))
        self._all_tbl = _tbl(
            ["Asset Tag", "Name", "Type", "Status",
             "Assigned To", "Department", "Purchase Date"], stretch_col=1)
        self._all_tbl.setFixedHeight(280)
        v.addWidget(self._all_tbl)

        v.addWidget(_refresh_btn(self._load))
        v.addStretch()
        outer.addWidget(_scrolled(inner))

    def _load(self):
        conn = _db()
        try:
            _fill_count(self._status_tbl,
                conn.execute(
                    "SELECT status, COUNT(*) FROM it_asset "
                    "GROUP BY status ORDER BY status"
                ).fetchall(),
                fmt0=lambda v: str(v).capitalize())

            _fill_count(self._type_tbl,
                conn.execute(
                    "SELECT COALESCE(asset_type,'(none)'), COUNT(*) "
                    "FROM it_asset GROUP BY asset_type ORDER BY COUNT(*) DESC"
                ).fetchall())

            _fill_count(self._dept_tbl,
                conn.execute(
                    "SELECT COALESCE(department,'(none)'), COUNT(*) "
                    "FROM it_asset GROUP BY department ORDER BY COUNT(*) DESC"
                ).fetchall())

            w_rows = conn.execute(
                "SELECT asset_tag, asset_type, make, model,"
                " assigned_to, department, warranty_exp FROM it_asset "
                "WHERE warranty_exp BETWEEN %s AND %s AND status='active'"
                " ORDER BY warranty_exp",
                (TODAY, NINETY_DAYS_OUT)
            ).fetchall()
            _fill(self._warranty_tbl, w_rows, bg=WARN_BG)

            all_rows = conn.execute(
                "SELECT asset_tag, make || ' ' || COALESCE(model,'') AS asset_name,"
                " asset_type, status, assigned_to, department, purchase_date"
                " FROM it_asset ORDER BY asset_type, make, model"
            ).fetchall()
            _fill(self._all_tbl, all_rows)
        except Exception:
            log.warning("Asset inventory load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# 6. SLA & Performance
# ===========================================================================

class _SLAWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QtWidgets.QWidget()
        _apply_blue_palette(inner)
        v = QtWidgets.QVBoxLayout(inner)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        hdr = QtWidgets.QLabel("SLA & Performance")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        # Ticket resolution stats
        row1 = QtWidgets.QHBoxLayout()
        blk_r = QtWidgets.QVBoxLayout()
        blk_r.addWidget(_section_lbl("Ticket Resolution Rate (all time)"))
        self._res_rate = _count_tbl(("Metric", "Value"))
        self._res_rate.setFixedHeight(130)
        blk_r.addWidget(self._res_rate)
        row1.addLayout(blk_r)

        blk_a = QtWidgets.QVBoxLayout()
        blk_a.addWidget(_section_lbl("Avg Ticket Age by Priority (open)"))
        self._avg_age = _count_tbl(("Priority", "Avg Age (days)"))
        self._avg_age.setFixedHeight(130)
        blk_a.addWidget(self._avg_age)
        row1.addLayout(blk_a)
        v.addLayout(row1)

        # Throughput
        v.addWidget(_section_lbl("Ticket Throughput — Last 30 Days"))
        self._throughput = _tbl(
            ["Technician", "Opened", "Resolved", "Net Change"],
            stretch_col=0)
        self._throughput.setFixedHeight(200)
        v.addWidget(self._throughput)

        # Task completion
        row2 = QtWidgets.QHBoxLayout()
        blk_tc = QtWidgets.QVBoxLayout()
        blk_tc.addWidget(_section_lbl("Task Completion Rate by Technician"))
        self._task_rate = _tbl(
            ["Technician", "Completed", "Total", "Rate %"],
            stretch_col=0)
        self._task_rate.setFixedHeight(200)
        blk_tc.addWidget(self._task_rate)
        row2.addLayout(blk_tc)
        v.addLayout(row2)

        # Top issue types
        v.addWidget(_section_lbl("Top Issue Types (open tickets)"))
        self._issue_types = _tbl(
            ["Issue Type", "Open", "Overdue", "Total"], stretch_col=0)
        self._issue_types.setFixedHeight(180)
        v.addWidget(self._issue_types)

        v.addWidget(_refresh_btn(self._load))
        v.addStretch()
        outer.addWidget(_scrolled(inner))

    def _load(self):
        conn = _db()
        try:
            total = (conn.execute(
                "SELECT COUNT(*) FROM it_ticket").fetchone() or [0])[0]
            resolved = (conn.execute(
                "SELECT COUNT(*) FROM it_ticket "
                "WHERE status IN ('resolved','closed')").fetchone() or [0])[0]
            rate = f"{round(resolved/total*100, 1)}%" if total else "N/A"
            avg_open = (conn.execute(
                "SELECT ROUND(AVG(CURRENT_DATE - submitted_date::date)::numeric,1)"
                " FROM it_ticket WHERE status NOT IN ('resolved','closed')"
            ).fetchone() or [None])[0]

            res_rows = [
                ("Total Tickets", total),
                ("Resolved/Closed", resolved),
                (f"Resolution Rate", rate),
                ("Avg Age Open (days)", avg_open or "N/A"),
            ]
            self._res_rate.setRowCount(len(res_rows))
            for r, (label, val) in enumerate(res_rows):
                self._res_rate.setItem(r, 0, _ro(label))
                self._res_rate.setItem(r, 1, _ro(val))

            age_rows = conn.execute(f"""
                SELECT priority,
                    ROUND(AVG(CURRENT_DATE - submitted_date::date)::numeric, 1)
                FROM it_ticket
                WHERE status NOT IN ('resolved','closed')
                GROUP BY priority ORDER BY priority
            """).fetchall()
            _fill_count(self._avg_age, age_rows,
                        fmt0=lambda v: str(v).capitalize())

            tp_rows = conn.execute(f"""
                SELECT tech,
                    SUM(opened)  AS opened,
                    SUM(resolved) AS resolved,
                    SUM(opened) - SUM(resolved) AS net
                FROM (
                    SELECT COALESCE(assigned_to,'(unassigned)') AS tech,
                        1 AS opened, 0 AS resolved
                    FROM it_ticket WHERE submitted_date >= '{THIRTY_DAYS_AGO}'
                    UNION ALL
                    SELECT COALESCE(assigned_to,'(unassigned)'),
                        0, 1
                    FROM it_ticket
                    WHERE status IN ('resolved','closed')
                    AND resolved_date >= '{THIRTY_DAYS_AGO}'
                ) sub
                GROUP BY tech ORDER BY resolved DESC
            """).fetchall()
            _fill(self._throughput, tp_rows)

            comp_rows = conn.execute("""
                SELECT COALESCE(assigned_to,'(unassigned)'),
                    SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END),
                    COUNT(*),
                    ROUND(
                        SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END)
                        * 100.0 / NULLIF(COUNT(*),0), 1
                    )
                FROM it_task
                GROUP BY 1 ORDER BY 2 DESC
            """).fetchall()
            self._task_rate.setRowCount(len(comp_rows))
            for r, row in enumerate(comp_rows):
                for c, val in enumerate(row):
                    suffix = "%" if c == 3 and val is not None else ""
                    self._task_rate.setItem(r, c, _ro(
                        f"{val}{suffix}" if val is not None else ""))
            self._task_rate.resizeColumnsToContents()

            it_rows = conn.execute(f"""
                SELECT COALESCE(issue_type,'(none)'),
                    SUM(CASE WHEN status IN ('open','in_progress') THEN 1 ELSE 0 END),
                    SUM(CASE WHEN due_date < '{TODAY}' AND status NOT IN
                        ('resolved','closed') THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_ticket GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 15
            """).fetchall()
            _fill(self._issue_types, it_rows)
        except Exception:
            log.warning("SLA load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# Top-level container
# ===========================================================================

class ITMgrReportsDesktopWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(_OverviewWidget(),        "Overview")
        tabs.addTab(_ByTechnicianWidget(),    "By Technician")
        tabs.addTab(_ByDepartmentWidget(),    "By Department")
        tabs.addTab(_OverdueWidget(),         "Overdue")
        tabs.addTab(_AssetInventoryWidget(),  "Asset Inventory")
        tabs.addTab(_SLAWidget(),             "SLA & Performance")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("IT Manager Reports")
    _apply_blue_palette(win)
    win.setCentralWidget(ITMgrReportsDesktopWidget())
    win.showMaximized()
    sys.exit(app.exec())
