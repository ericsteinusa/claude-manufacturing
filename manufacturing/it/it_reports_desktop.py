"""
it_reports_desktop.py — Comprehensive IT Reports widget (native PostgreSQL).

Five outer tabs, each with an inner scroll area covering:
  Overview        — live KPI stat cards across all IT tables
  Ticket Reports  — by status / department / issue type / overdue / resolved
  Task Reports    — by status / technician / department / overdue / completed
  Asset Reports   — by status / type / warranty expiring soon
  Infrastructure  — repairs / software / license summaries
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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
SEC_STYLE = "color:white;font-weight:bold;font-size:13px;margin-top:8px;"
CARD_STYLE = (
    "QLabel{background:white;border:2px solid black;border-radius:6px;"
    "padding:8px 14px;font-size:13px;font-weight:bold;}"
)
OVERDUE_BG = QtGui.QColor(248, 215, 218)
DONE_BG = QtGui.QColor(212, 237, 218)
WARN_BG = QtGui.QColor(255, 243, 205)


def _db():
    return get_db_connection()


def _ro(val):
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


# ---------------------------------------------------------------------------
# Helper: 2-column count table (label, count)
# ---------------------------------------------------------------------------

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


# ===========================================================================
# 1. Overview tab
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
        v.setSpacing(12)

        hdr = QtWidgets.QLabel("IT Department Overview")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        # Stat card grid
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        card_defs = [
            ("open_tickets",    "Open Tickets"),
            ("inprog_tickets",  "In Progress Tickets"),
            ("critical_tickets","Critical Tickets"),
            ("overdue_tickets", "Overdue Tickets"),
            ("open_tasks",      "Open Tasks"),
            ("overdue_tasks",   "Overdue Tasks"),
            ("active_assets",   "Active Assets"),
            ("repair_assets",   "Assets in Repair"),
            ("open_repairs",    "Open Repairs"),
            ("active_licenses", "Active Licenses"),
            ("expiring_lic",    "Licenses Expiring (90d)"),
            ("online_devices",  "Network Devices Online"),
        ]
        for i, (key, label) in enumerate(card_defs):
            card = QtWidgets.QLabel(f"{label}\n—")
            card.setStyleSheet(CARD_STYLE)
            card.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(card, i // 3, i % 3)
            self._cards[key] = card
        v.addLayout(grid)

        v.addWidget(_section_lbl("Recent Open Tickets (last 10)"))
        self._tkt_tbl = _tbl(
            ["Ticket #", "Requester", "Department",
             "Issue Type", "Priority", "Due Date"], stretch_col=1)
        self._tkt_tbl.setFixedHeight(200)
        v.addWidget(self._tkt_tbl)

        v.addWidget(_section_lbl("Overdue Tasks"))
        self._task_tbl = _tbl(
            ["Task #", "Task Name", "Priority",
             "Assigned To", "Due Date"], stretch_col=1)
        self._task_tbl.setFixedHeight(180)
        v.addWidget(self._task_tbl)

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
                "critical_tickets": qi(
                    "SELECT COUNT(*) FROM it_ticket "
                    "WHERE priority='critical' AND status NOT IN ('resolved','closed')"),
                "overdue_tickets": qi(
                    "SELECT COUNT(*) FROM it_ticket "
                    "WHERE due_date<%s AND status NOT IN ('resolved','closed')", TODAY),
                "open_tasks": qi(
                    "SELECT COUNT(*) FROM it_task "
                    "WHERE status IN ('pending','in_progress','on_hold')"),
                "overdue_tasks": qi(
                    "SELECT COUNT(*) FROM it_task "
                    "WHERE due_date<%s AND status NOT IN ('completed','cancelled')", TODAY),
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
                "online_devices": qi(
                    "SELECT COUNT(*) FROM it_network_device WHERE status='online'"),
            }
            for key, card in self._cards.items():
                label_text = card.text().split("\n")[0]
                card.setText(f"{label_text}\n{vals.get(key, 0)}")

            tkt_rows = conn.execute(
                "SELECT ticket_number, requester, department, issue_type,"
                " priority, due_date FROM it_ticket "
                "WHERE status IN ('open','in_progress') "
                "ORDER BY submitted_date DESC LIMIT 10"
            ).fetchall()
            _fill(self._tkt_tbl, tkt_rows)

            task_rows = conn.execute(
                "SELECT task_number, task_name, priority, assigned_to, due_date"
                " FROM it_task "
                "WHERE due_date < %s AND status NOT IN ('completed','cancelled')"
                " ORDER BY due_date", (TODAY,)
            ).fetchall()
            _fill(self._task_tbl, task_rows, bg=OVERDUE_BG)
        except Exception:
            log.warning("Overview load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# 2. Ticket Reports tab
# ===========================================================================

class _TicketReportsWidget(QtWidgets.QWidget):
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

        hdr = QtWidgets.QLabel("Ticket Reports")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        # Row 1: By Status | By Priority
        row1 = QtWidgets.QHBoxLayout()
        stat_block = QtWidgets.QVBoxLayout()
        stat_block.addWidget(_section_lbl("By Status"))
        self._by_status = _count_tbl(("Status", "Count"))
        stat_block.addWidget(self._by_status)
        row1.addLayout(stat_block)
        pri_block = QtWidgets.QVBoxLayout()
        pri_block.addWidget(_section_lbl("By Priority (open tickets)"))
        self._by_pri = _count_tbl(("Priority", "Count"))
        pri_block.addWidget(self._by_pri)
        row1.addLayout(pri_block)
        v.addLayout(row1)

        # By Department
        v.addWidget(_section_lbl("By Department"))
        self._by_dept = _tbl(
            ["Department", "Open", "In Progress", "Resolved", "Total"])
        self._by_dept.setFixedHeight(200)
        v.addWidget(self._by_dept)

        # By Issue Type
        v.addWidget(_section_lbl("By Issue Type"))
        self._by_type = _tbl(
            ["Issue Type", "Open", "Total"], stretch_col=0)
        self._by_type.setFixedHeight(200)
        v.addWidget(self._by_type)

        # Overdue Tickets
        v.addWidget(_section_lbl("Overdue Tickets"))
        self._overdue = _tbl(
            ["Ticket #", "Requester", "Department",
             "Priority", "Assigned To", "Due Date"], stretch_col=1)
        self._overdue.setFixedHeight(200)
        v.addWidget(self._overdue)

        # Resolved This Month
        v.addWidget(_section_lbl("Resolved Last 30 Days"))
        self._resolved = _tbl(
            ["Ticket #", "Requester", "Department",
             "Issue Type", "Assigned To", "Resolved Date"], stretch_col=1)
        self._resolved.setFixedHeight(200)
        v.addWidget(self._resolved)

        v.addWidget(_refresh_btn(self._load))
        v.addStretch()
        outer.addWidget(_scrolled(inner))

    def _load(self):
        conn = _db()
        try:
            s_rows = conn.execute(
                "SELECT status, COUNT(*) FROM it_ticket "
                "GROUP BY status ORDER BY status"
            ).fetchall()
            _fill_count(self._by_status, s_rows,
                        fmt0=lambda v: str(v).replace("_", " ").capitalize())

            p_rows = conn.execute(
                "SELECT priority, COUNT(*) FROM it_ticket "
                "WHERE status IN ('open','in_progress') "
                "GROUP BY priority ORDER BY priority"
            ).fetchall()
            _fill_count(self._by_pri, p_rows,
                        fmt0=lambda v: str(v).capitalize())

            dept_rows = conn.execute("""
                SELECT COALESCE(department,'(none)') AS dept,
                    SUM(CASE WHEN status='open'        THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='resolved'    THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_ticket
                GROUP BY dept ORDER BY COUNT(*) DESC
            """).fetchall()
            _fill(self._by_dept, dept_rows)

            type_rows = conn.execute("""
                SELECT COALESCE(issue_type,'(none)') AS itype,
                    SUM(CASE WHEN status IN ('open','in_progress')
                        THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_ticket
                GROUP BY itype ORDER BY COUNT(*) DESC
            """).fetchall()
            _fill(self._by_type, type_rows)

            ov_rows = conn.execute(
                "SELECT ticket_number, requester, department, priority,"
                " assigned_to, due_date FROM it_ticket "
                "WHERE due_date < %s AND status NOT IN ('resolved','closed') "
                "ORDER BY due_date", (TODAY,)
            ).fetchall()
            _fill(self._overdue, ov_rows, bg=OVERDUE_BG)

            res_rows = conn.execute(
                "SELECT ticket_number, requester, department, issue_type,"
                " assigned_to, resolved_date FROM it_ticket "
                "WHERE status='resolved' AND resolved_date >= %s "
                "ORDER BY resolved_date DESC", (THIRTY_DAYS_AGO,)
            ).fetchall()
            _fill(self._resolved, res_rows, bg=DONE_BG)
        except Exception:
            log.warning("Ticket report load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# 3. Task Reports tab
# ===========================================================================

class _TaskReportsWidget(QtWidgets.QWidget):
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

        hdr = QtWidgets.QLabel("Task Reports")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        row1 = QtWidgets.QHBoxLayout()
        blk_s = QtWidgets.QVBoxLayout()
        blk_s.addWidget(_section_lbl("By Status"))
        self._by_status = _count_tbl(("Status", "Count"))
        blk_s.addWidget(self._by_status)
        row1.addLayout(blk_s)
        blk_p = QtWidgets.QVBoxLayout()
        blk_p.addWidget(_section_lbl("By Priority"))
        self._by_pri = _count_tbl(("Priority", "Count"))
        blk_p.addWidget(self._by_pri)
        row1.addLayout(blk_p)
        blk_t = QtWidgets.QVBoxLayout()
        blk_t.addWidget(_section_lbl("By Task Type"))
        self._by_type = _count_tbl(("Task Type", "Count"))
        blk_t.addWidget(self._by_type)
        row1.addLayout(blk_t)
        v.addLayout(row1)

        v.addWidget(_section_lbl("By Technician"))
        self._by_tech = _tbl(
            ["Technician", "Pending", "In Progress",
             "On Hold", "Completed", "Total"])
        self._by_tech.setFixedHeight(200)
        v.addWidget(self._by_tech)

        v.addWidget(_section_lbl("By Department"))
        self._by_dept = _tbl(
            ["Department", "Open", "Completed", "Cancelled", "Total"])
        self._by_dept.setFixedHeight(200)
        v.addWidget(self._by_dept)

        v.addWidget(_section_lbl("Overdue Tasks"))
        self._overdue = _tbl(
            ["Task #", "Task Name", "Priority",
             "Assigned To", "Department", "Due Date"], stretch_col=1)
        self._overdue.setFixedHeight(200)
        v.addWidget(self._overdue)

        v.addWidget(_section_lbl("Recently Completed (last 30 days)"))
        self._completed = _tbl(
            ["Task #", "Task Name", "Type",
             "Assigned To", "Department", "Completed Date"], stretch_col=1)
        self._completed.setFixedHeight(200)
        v.addWidget(self._completed)

        v.addWidget(_refresh_btn(self._load))
        v.addStretch()
        outer.addWidget(_scrolled(inner))

    def _load(self):
        conn = _db()
        try:
            s_rows = conn.execute(
                "SELECT status, COUNT(*) FROM it_task "
                "GROUP BY status ORDER BY status"
            ).fetchall()
            _fill_count(self._by_status, s_rows,
                        fmt0=lambda v: str(v).replace("_", " ").capitalize())

            p_rows = conn.execute(
                "SELECT priority, COUNT(*) FROM it_task "
                "GROUP BY priority ORDER BY priority"
            ).fetchall()
            _fill_count(self._by_pri, p_rows,
                        fmt0=lambda v: str(v).capitalize())

            t_rows = conn.execute(
                "SELECT COALESCE(task_type,'(none)'), COUNT(*) FROM it_task "
                "GROUP BY task_type ORDER BY COUNT(*) DESC"
            ).fetchall()
            _fill_count(self._by_type, t_rows)

            tech_rows = conn.execute("""
                SELECT COALESCE(assigned_to,'(unassigned)'),
                    SUM(CASE WHEN status='pending'     THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='on_hold'     THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='completed'   THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_task GROUP BY 1 ORDER BY COUNT(*) DESC
            """).fetchall()
            _fill(self._by_tech, tech_rows)

            dept_rows = conn.execute("""
                SELECT COALESCE(department,'(none)'),
                    SUM(CASE WHEN status IN ('pending','in_progress','on_hold')
                        THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='completed'  THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='cancelled'  THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_task GROUP BY 1 ORDER BY COUNT(*) DESC
            """).fetchall()
            _fill(self._by_dept, dept_rows)

            ov_rows = conn.execute(
                "SELECT task_number, task_name, priority, assigned_to,"
                " department, due_date FROM it_task "
                "WHERE due_date < %s AND status NOT IN ('completed','cancelled')"
                " ORDER BY due_date", (TODAY,)
            ).fetchall()
            _fill(self._overdue, ov_rows, bg=OVERDUE_BG)

            comp_rows = conn.execute(
                "SELECT task_number, task_name, task_type, assigned_to,"
                " department, completed_date FROM it_task "
                "WHERE status='completed' AND completed_date >= %s "
                "ORDER BY completed_date DESC", (THIRTY_DAYS_AGO,)
            ).fetchall()
            _fill(self._completed, comp_rows, bg=DONE_BG)
        except Exception:
            log.warning("Task report load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# 4. Asset Reports tab
# ===========================================================================

class _AssetReportsWidget(QtWidgets.QWidget):
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

        hdr = QtWidgets.QLabel("Asset Reports")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        row1 = QtWidgets.QHBoxLayout()
        blk_s = QtWidgets.QVBoxLayout()
        blk_s.addWidget(_section_lbl("By Status"))
        self._by_status = _count_tbl(("Status", "Count"))
        blk_s.addWidget(self._by_status)
        row1.addLayout(blk_s)
        blk_t = QtWidgets.QVBoxLayout()
        blk_t.addWidget(_section_lbl("By Asset Type"))
        self._by_type = _count_tbl(("Asset Type", "Count"))
        blk_t.addWidget(self._by_type)
        row1.addLayout(blk_t)
        v.addLayout(row1)

        v.addWidget(_section_lbl("By Department"))
        self._by_dept = _tbl(
            ["Department", "Active", "Spare", "Repair", "Total"],
            stretch_col=0)
        self._by_dept.setFixedHeight(200)
        v.addWidget(self._by_dept)

        v.addWidget(_section_lbl(f"Warranty Expiring Within 90 Days (by {NINETY_DAYS_OUT})"))
        self._warranty = _tbl(
            ["Asset Tag", "Type", "Make", "Model",
             "Assigned To", "Department", "Warranty Exp"], stretch_col=2)
        self._warranty.setFixedHeight(200)
        v.addWidget(self._warranty)

        v.addWidget(_section_lbl("Assets Currently in Repair"))
        self._in_repair = _tbl(
            ["Asset Tag", "Type", "Make", "Model",
             "Assigned To", "Department"], stretch_col=2)
        self._in_repair.setFixedHeight(180)
        v.addWidget(self._in_repair)

        v.addWidget(_refresh_btn(self._load))
        v.addStretch()
        outer.addWidget(_scrolled(inner))

    def _load(self):
        conn = _db()
        try:
            s_rows = conn.execute(
                "SELECT status, COUNT(*) FROM it_asset "
                "GROUP BY status ORDER BY status"
            ).fetchall()
            _fill_count(self._by_status, s_rows,
                        fmt0=lambda v: str(v).capitalize())

            t_rows = conn.execute(
                "SELECT COALESCE(asset_type,'(none)'), COUNT(*) FROM it_asset "
                "GROUP BY asset_type ORDER BY COUNT(*) DESC"
            ).fetchall()
            _fill_count(self._by_type, t_rows)

            dept_rows = conn.execute("""
                SELECT COALESCE(department,'(none)'),
                    SUM(CASE WHEN status='active' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='spare'  THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='repair' THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM it_asset GROUP BY 1 ORDER BY COUNT(*) DESC
            """).fetchall()
            _fill(self._by_dept, dept_rows)

            w_rows = conn.execute(
                "SELECT asset_tag, asset_type, make, model,"
                " assigned_to, department, warranty_exp FROM it_asset "
                "WHERE warranty_exp BETWEEN %s AND %s "
                "AND status='active' ORDER BY warranty_exp",
                (TODAY, NINETY_DAYS_OUT)
            ).fetchall()
            _fill(self._warranty, w_rows, bg=WARN_BG)

            r_rows = conn.execute(
                "SELECT asset_tag, asset_type, make, model,"
                " assigned_to, department FROM it_asset "
                "WHERE status='repair' ORDER BY asset_tag"
            ).fetchall()
            _fill(self._in_repair, r_rows, bg=WARN_BG)
        except Exception:
            log.warning("Asset report load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# 5. Infrastructure Reports tab
# ===========================================================================

class _InfraReportsWidget(QtWidgets.QWidget):
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

        hdr = QtWidgets.QLabel("IT Infrastructure Reports")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        # Repairs row
        row1 = QtWidgets.QHBoxLayout()
        rb = QtWidgets.QVBoxLayout()
        rb.addWidget(_section_lbl("Repairs — By Status"))
        self._rep_status = _count_tbl(("Status", "Count"))
        rb.addWidget(self._rep_status)
        row1.addLayout(rb)
        rp = QtWidgets.QVBoxLayout()
        rp.addWidget(_section_lbl("Repairs — By Priority"))
        self._rep_pri = _count_tbl(("Priority", "Count"))
        rp.addWidget(self._rep_pri)
        row1.addLayout(rp)
        v.addLayout(row1)

        v.addWidget(_section_lbl("Open / In-Progress Repairs"))
        self._open_repairs = _tbl(
            ["Ticket", "Asset Tag", "Problem", "Priority",
             "Assigned To", "Reported Date"], stretch_col=2)
        self._open_repairs.setFixedHeight(180)
        v.addWidget(self._open_repairs)

        # Software / Licenses row
        row2 = QtWidgets.QHBoxLayout()
        sb = QtWidgets.QVBoxLayout()
        sb.addWidget(_section_lbl("Software — By Status"))
        self._sw_status = _count_tbl(("Status", "Count"))
        sb.addWidget(self._sw_status)
        row2.addLayout(sb)
        lb = QtWidgets.QVBoxLayout()
        lb.addWidget(_section_lbl("Licenses — By Status"))
        self._lic_status = _count_tbl(("Status", "Count"))
        lb.addWidget(self._lic_status)
        row2.addLayout(lb)
        lt = QtWidgets.QVBoxLayout()
        lt.addWidget(_section_lbl("Licenses — By Type"))
        self._lic_type = _count_tbl(("Type", "Count"))
        lt.addWidget(self._lic_type)
        row2.addLayout(lt)
        v.addLayout(row2)

        v.addWidget(_section_lbl(f"Licenses Expiring Within 90 Days (by {NINETY_DAYS_OUT})"))
        self._expiring = _tbl(
            ["Software", "Vendor", "Type", "Seats",
             "Expiry Date", "Status"], stretch_col=0)
        self._expiring.setFixedHeight(180)
        v.addWidget(self._expiring)

        # Network
        row3 = QtWidgets.QHBoxLayout()
        nb = QtWidgets.QVBoxLayout()
        nb.addWidget(_section_lbl("Network Devices — By Status"))
        self._net_status = _count_tbl(("Status", "Count"))
        nb.addWidget(self._net_status)
        row3.addLayout(nb)
        nt = QtWidgets.QVBoxLayout()
        nt.addWidget(_section_lbl("Network Devices — By Type"))
        self._net_type = _count_tbl(("Device Type", "Count"))
        nt.addWidget(self._net_type)
        row3.addLayout(nt)
        v.addLayout(row3)

        v.addWidget(_refresh_btn(self._load))
        v.addStretch()
        outer.addWidget(_scrolled(inner))

    def _load(self):
        conn = _db()
        try:
            # Repairs
            r_s = conn.execute(
                "SELECT status, COUNT(*) FROM it_repair "
                "GROUP BY status ORDER BY status"
            ).fetchall()
            _fill_count(self._rep_status, r_s,
                        fmt0=lambda v: str(v).replace("_", " ").capitalize())

            r_p = conn.execute(
                "SELECT priority, COUNT(*) FROM it_repair "
                "WHERE status IN ('open','in_progress') "
                "GROUP BY priority ORDER BY priority"
            ).fetchall()
            _fill_count(self._rep_pri, r_p,
                        fmt0=lambda v: str(v).capitalize())

            or_rows = conn.execute(
                "SELECT id, asset_tag, problem_description, priority,"
                " assigned_to, reported_date FROM it_repair "
                "WHERE status IN ('open','in_progress') "
                "ORDER BY reported_date"
            ).fetchall()
            _fill(self._open_repairs, or_rows)

            # Software
            sw_s = conn.execute(
                "SELECT status, COUNT(*) FROM it_software "
                "GROUP BY status ORDER BY status"
            ).fetchall()
            _fill_count(self._sw_status, sw_s,
                        fmt0=lambda v: str(v).capitalize())

            # Licenses
            lic_s = conn.execute(
                "SELECT status, COUNT(*) FROM it_license "
                "GROUP BY status ORDER BY status"
            ).fetchall()
            _fill_count(self._lic_status, lic_s,
                        fmt0=lambda v: str(v).capitalize())

            lic_t = conn.execute(
                "SELECT COALESCE(license_type,'(none)'), COUNT(*) "
                "FROM it_license GROUP BY license_type ORDER BY COUNT(*) DESC"
            ).fetchall()
            _fill_count(self._lic_type, lic_t,
                        fmt0=lambda v: str(v).replace("_", " ").capitalize())

            exp_rows = conn.execute(
                "SELECT software_name, vendor, license_type, seats,"
                " expiry_date, status FROM it_license "
                "WHERE status='active' AND expiry_date BETWEEN %s AND %s "
                "ORDER BY expiry_date",
                (TODAY, NINETY_DAYS_OUT)
            ).fetchall()
            _fill(self._expiring, exp_rows, bg=WARN_BG)

            # Network
            net_s = conn.execute(
                "SELECT status, COUNT(*) FROM it_network_device "
                "GROUP BY status ORDER BY status"
            ).fetchall()
            _fill_count(self._net_status, net_s,
                        fmt0=lambda v: str(v).capitalize())

            net_t = conn.execute(
                "SELECT COALESCE(device_type,'(none)'), COUNT(*) "
                "FROM it_network_device "
                "GROUP BY device_type ORDER BY COUNT(*) DESC"
            ).fetchall()
            _fill_count(self._net_type, net_t)
        except Exception:
            log.warning("Infra report load failed", exc_info=True)
        finally:
            conn.close()


# ===========================================================================
# Top-level container
# ===========================================================================

class ITReportsDesktopWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(_OverviewWidget(),       "Overview")
        tabs.addTab(_TicketReportsWidget(),  "Ticket Reports")
        tabs.addTab(_TaskReportsWidget(),    "Task Reports")
        tabs.addTab(_AssetReportsWidget(),   "Asset Reports")
        tabs.addTab(_InfraReportsWidget(),   "Infrastructure")
        v.addWidget(tabs)


# ===========================================================================
# Standalone window
# ===========================================================================

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("IT Reports")
    _apply_blue_palette(win)
    win.setCentralWidget(ITReportsDesktopWidget())
    win.showMaximized()
    sys.exit(app.exec())
