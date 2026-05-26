"""
cs_escalations.py — CS Escalations
Tabs: Active Escalations | Escalation History | Escalation Reports | Resolution Tracking
"""
import sys
import os
import psycopg2
import psycopg2.extras
from .db_connection import get_db_connection
import csv
from datetime import date, datetime
from PyQt6 import QtCore, QtGui, QtWidgets


OVERDUE_DAYS = 7   # calls open this long or more are considered escalated

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color:white;border:2px solid black;border-radius:8px;"
    "padding:4px 12px;font-weight:bold;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid #aaa;background:white;}"
    "QTabBar::tab{background:#cce0ff;padding:6px 18px;font-weight:bold;}"
    "QTabBar::tab:selected{background:white;border-bottom:2px solid rgb(0,85,255);}"
)
DATE_STYLE = "QDateEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 4px;}"
HDR_STYLE = "font-size:20px;font-weight:bold;color:white;padding:4px;"
SECTION_STYLE = "font-size:13px;font-weight:bold;color:white;"
LABEL_STYLE = "color:white;font-size:13px;"

COLOR_CRITICAL = QtGui.QColor(255, 150, 150)   # open ≥ 2× OVERDUE_DAYS
COLOR_OVERDUE  = QtGui.QColor(255, 200, 200)   # open ≥ OVERDUE_DAYS
COLOR_RESOLVED = QtGui.QColor(212, 237, 218)   # completed after being overdue


def _conn():
    c = get_db_connection()
    return c


def _apply_palette(widget):
    pal = QtGui.QPalette()
    for g in (QtGui.QPalette.ColorGroup.Active,
              QtGui.QPalette.ColorGroup.Inactive,
              QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(g, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(g, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter):
    item = QtWidgets.QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
    item.setTextAlignment(align)
    return item


def _ro_c(text):
    return _ro(text, QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)


def _ro_r(text):
    return _ro(text, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)


def _export_table(table, parent, name="export.csv"):
    if table.rowCount() == 0:
        QtWidgets.QMessageBox.information(parent, "Export", "No data to export.")
        return
    path, _ = QtWidgets.QFileDialog.getSaveFileName(parent, "Export CSV", name, "CSV Files (*.csv)")
    if not path:
        return
    headers = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in range(table.rowCount()):
            w.writerow([table.item(r, c).text() if table.item(r, c) else ""
                        for c in range(table.columnCount())])
    QtWidgets.QMessageBox.information(parent, "Export Complete", f"Saved to:\n{path}")


def lbl(text, style=LABEL_STYLE):
    w = QtWidgets.QLabel(text)
    w.setStyleSheet(style)
    return w


def _days_between(d1_str, d2_str):
    try:
        return (date.fromisoformat(d2_str) - date.fromisoformat(d1_str)).days
    except (TypeError, ValueError):
        return None


def _customer_name(row):
    company = (row["company_name"] or "").strip()
    contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    return company if company else (contact if contact else "(no customer)")


class DateRangeBar(QtWidgets.QWidget):
    run_clicked = QtCore.pyqtSignal()

    def __init__(self, default_days_back=365, parent=None):
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.dt_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.dt_from.setStyleSheet(DATE_STYLE)
        self.dt_from.setDisplayFormat("MM/dd/yyyy")
        self.dt_from.setDate(QtCore.QDate.currentDate().addDays(-default_days_back))
        self.dt_to = QtWidgets.QDateEdit(calendarPopup=True)
        self.dt_to.setStyleSheet(DATE_STYLE)
        self.dt_to.setDisplayFormat("MM/dd/yyyy")
        self.dt_to.setDate(QtCore.QDate.currentDate())
        btn = QtWidgets.QPushButton("Run Report")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(self.run_clicked)
        row.addWidget(lbl("From:"))
        row.addWidget(self.dt_from)
        row.addWidget(lbl("To:"))
        row.addWidget(self.dt_to)
        row.addWidget(btn)
        row.addStretch()

    @property
    def from_str(self):
        return self.dt_from.date().toString("yyyy-MM-dd")

    @property
    def to_str(self):
        return self.dt_to.date().toString("yyyy-MM-dd")


class CSEscalationsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_palette(self)
        self._build_ui()
        self._run_all()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        title = QtWidgets.QLabel("CS Escalations")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(HDR_STYLE)
        root.addWidget(title)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_active_tab(), "Active Escalations")
        self.tabs.addTab(self._build_history_tab(), "Escalation History")
        self.tabs.addTab(self._build_reports_tab(), "Escalation Reports")
        self.tabs.addTab(self._build_tracking_tab(), "Resolution Tracking")

    # ── Active Escalations ────────────────────────────────────────────────

    def _build_active_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        self.active_summary_lbl = QtWidgets.QLabel("")
        self.active_summary_lbl.setStyleSheet("color:white;font-size:13px;font-weight:bold;")
        top.addWidget(self.active_summary_lbl)
        top.addStretch()
        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(self._run_active)
        top.addWidget(btn)
        v.addLayout(top)

        self.active_tbl = QtWidgets.QTableWidget(0, 6)
        self.active_tbl.setHorizontalHeaderLabels([
            "Customer", "Problem / Call", "Call Date", "Days Open", "Comments", "Priority"
        ])
        hh = self.active_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (2, 3, 5):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.active_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.active_tbl.setAlternatingRowColors(False)
        self.active_tbl.verticalHeader().setVisible(False)
        self.active_tbl.setSortingEnabled(True)
        v.addWidget(self.active_tbl, stretch=1)

        legend = QtWidgets.QHBoxLayout()
        for color, text in (
            (COLOR_CRITICAL, f"  Critical (≥{OVERDUE_DAYS * 2} days)  "),
            (COLOR_OVERDUE,  f"  Overdue (≥{OVERDUE_DAYS} days)  "),
        ):
            dot = QtWidgets.QLabel("  ")
            dot.setAutoFillBackground(True)
            p = dot.palette()
            p.setColor(QtGui.QPalette.ColorRole.Window, color)
            dot.setPalette(p)
            dot.setFixedSize(18, 18)
            lbl_w = QtWidgets.QLabel(text)
            lbl_w.setStyleSheet("color:white;font-size:12px;")
            legend.addWidget(dot)
            legend.addWidget(lbl_w)
        legend.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BUTTON_STYLE)
        btn_exp.setFixedHeight(28)
        btn_exp.clicked.connect(lambda: _export_table(self.active_tbl, self, "cs_active_escalations.csv"))
        legend.addWidget(btn_exp)
        v.addLayout(legend)
        return w

    def _run_active(self):
        today = date.today().isoformat()
        with _conn() as con:
            rows = con.execute("""
                SELECT c2.id, c2.call, c2.call_date, c2.comments_box,
                       cu.first_name, cu.last_name, cu.company_name
                FROM calls2 c2
                LEFT JOIN customer cu ON cu.id = c2.customer_id
                WHERE c2.completion_box = 0
                ORDER BY c2.call_date ASC
            """).fetchall()

        # Only show rows that are overdue
        escalated = [(r, d) for r in rows
                     if (d := _days_between(r["call_date"], today)) is not None
                     and d >= OVERDUE_DAYS]

        self.active_tbl.setSortingEnabled(False)
        self.active_tbl.setRowCount(0)
        critical_count = 0
        for row, days_open in escalated:
            critical = days_open >= OVERDUE_DAYS * 2
            if critical:
                critical_count += 1
                color = COLOR_CRITICAL
                priority = "Critical"
            else:
                color = COLOR_OVERDUE
                priority = "High"

            r = self.active_tbl.rowCount()
            self.active_tbl.insertRow(r)
            self.active_tbl.setItem(r, 0, _ro(_customer_name(row)))
            self.active_tbl.setItem(r, 1, _ro(row["call"] or ""))
            self.active_tbl.setItem(r, 2, _ro_c(row["call_date"] or ""))
            self.active_tbl.setItem(r, 3, _ro_c(str(days_open)))
            self.active_tbl.setItem(r, 4, _ro(row["comments_box"] or ""))
            self.active_tbl.setItem(r, 5, _ro_c(priority))
            for c in range(6):
                self.active_tbl.item(r, c).setBackground(color)

        self.active_tbl.setSortingEnabled(True)
        total = len(escalated)
        self.active_summary_lbl.setText(
            f"{total} active escalation(s) — {critical_count} critical"
        )
        self.statusBar().showMessage(f"{total} escalations | {critical_count} critical")

    # ── Escalation History ────────────────────────────────────────────────

    def _build_history_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        self.hist_bar = DateRangeBar(default_days_back=365)
        self.hist_bar.run_clicked.connect(self._run_history)
        v.addWidget(self.hist_bar)

        info = QtWidgets.QLabel(
            f"Showing completed calls that were open for ≥{OVERDUE_DAYS} days before resolution.")
        info.setStyleSheet("color:white;font-size:12px;font-style:italic;")
        v.addWidget(info)

        self.hist_tbl = QtWidgets.QTableWidget(0, 6)
        self.hist_tbl.setHorizontalHeaderLabels([
            "Customer", "Problem / Call", "Call Date", "Completed Date",
            "Days to Resolve", "Comments"
        ])
        hh = self.hist_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (2, 3, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.hist_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hist_tbl.setAlternatingRowColors(True)
        self.hist_tbl.verticalHeader().setVisible(False)
        self.hist_tbl.setSortingEnabled(True)
        v.addWidget(self.hist_tbl, stretch=1)

        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: _export_table(self.hist_tbl, self, "cs_escalation_history.csv"))
        exp_row.addWidget(btn)
        v.addLayout(exp_row)
        return w

    def _run_history(self):
        f, t = self.hist_bar.from_str, self.hist_bar.to_str
        with _conn() as con:
            rows = con.execute("""
                SELECT c2.call, c2.call_date, c2.completion_date, c2.comments_box,
                       cu.first_name, cu.last_name, cu.company_name
                FROM calls2 c2
                LEFT JOIN customer cu ON cu.id = c2.customer_id
                WHERE c2.completion_box = 1
                  AND c2.completion_date IS NOT NULL
                  AND c2.call_date BETWEEN %s AND %s
                ORDER BY c2.completion_date DESC
            """, (f, t)).fetchall()

        self.hist_tbl.setSortingEnabled(False)
        self.hist_tbl.setRowCount(0)
        for row in rows:
            days = _days_between(row["call_date"], row["completion_date"])
            if days is None or days < OVERDUE_DAYS:
                continue
            color = COLOR_CRITICAL if days >= OVERDUE_DAYS * 2 else COLOR_RESOLVED
            r = self.hist_tbl.rowCount()
            self.hist_tbl.insertRow(r)
            self.hist_tbl.setItem(r, 0, _ro(_customer_name(row)))
            self.hist_tbl.setItem(r, 1, _ro(row["call"] or ""))
            self.hist_tbl.setItem(r, 2, _ro_c(row["call_date"] or ""))
            self.hist_tbl.setItem(r, 3, _ro_c(row["completion_date"] or ""))
            self.hist_tbl.setItem(r, 4, _ro_c(str(days)))
            self.hist_tbl.setItem(r, 5, _ro(row["comments_box"] or ""))
            for c in range(6):
                self.hist_tbl.item(r, c).setBackground(color)
        self.hist_tbl.setSortingEnabled(True)
        self.statusBar().showMessage(f"{self.hist_tbl.rowCount()} escalation(s) resolved in period")

    # ── Escalation Reports ────────────────────────────────────────────────

    def _build_reports_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        self.rpt_bar = DateRangeBar(default_days_back=365)
        self.rpt_bar.run_clicked.connect(self._run_reports)
        v.addWidget(self.rpt_bar)

        # Summary cards
        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(16)
        self._rpt_cards = {}
        for key, label in (
            ("total_esc",  "Total\nEscalations"),
            ("resolved",   "Resolved"),
            ("active",     "Still Open"),
            ("pct_esc",    "Escalation\nRate"),
            ("avg_resolve","Avg Days\nto Resolve"),
        ):
            card = QtWidgets.QFrame()
            card.setFrameShape(QtWidgets.QFrame.Shape.Box)
            card.setStyleSheet("QFrame{background:white;border:2px solid #0055ff;border-radius:8px;}")
            card.setFixedSize(180, 90)
            cl = QtWidgets.QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            tl = QtWidgets.QLabel(label)
            tl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            tl.setStyleSheet("color:#333;font-size:12px;font-weight:bold;")
            vl = QtWidgets.QLabel("—")
            vl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            vl.setStyleSheet("color:#0055ff;font-size:22px;font-weight:bold;")
            cl.addWidget(tl)
            cl.addWidget(vl)
            self._rpt_cards[key] = vl
            cards.addWidget(card)
        cards.addStretch()
        v.addLayout(cards)

        v.addWidget(lbl("Monthly Escalation Summary", SECTION_STYLE))

        self.rpt_tbl = QtWidgets.QTableWidget(0, 5)
        self.rpt_tbl.setHorizontalHeaderLabels([
            "Month", "Total Calls", "Escalated", "Escalation Rate", "Avg Days Overdue"
        ])
        hh = self.rpt_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rpt_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rpt_tbl.setAlternatingRowColors(True)
        self.rpt_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.rpt_tbl, stretch=1)

        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: _export_table(self.rpt_tbl, self, "cs_escalation_reports.csv"))
        exp_row.addWidget(btn)
        v.addLayout(exp_row)
        return w

    def _run_reports(self):
        f, t = self.rpt_bar.from_str, self.rpt_bar.to_str
        today = date.today().isoformat()
        with _conn() as con:
            all_calls = con.execute("""
                SELECT c2.call_date, c2.completion_date, c2.completion_box
                FROM calls2 c2
                WHERE c2.call_date BETWEEN %s AND %s
            """, (f, t)).fetchall()

        def _resolve_date(row):
            return row["completion_date"] if row["completion_box"] else today

        escalated = [r for r in all_calls
                     if (_days_between(r["call_date"], _resolve_date(r)) or 0) >= OVERDUE_DAYS]
        resolved_esc = [r for r in escalated if r["completion_box"]]
        active_esc = [r for r in escalated if not r["completion_box"]]
        total_calls = len(all_calls)
        pct = len(escalated) / total_calls * 100 if total_calls else 0

        resolve_days = [d for r in resolved_esc
                        if (d := _days_between(r["call_date"], r["completion_date"])) is not None]
        avg_resolve = sum(resolve_days) / len(resolve_days) if resolve_days else None

        self._rpt_cards["total_esc"].setText(str(len(escalated)))
        self._rpt_cards["resolved"].setText(str(len(resolved_esc)))
        self._rpt_cards["active"].setText(str(len(active_esc)))
        self._rpt_cards["pct_esc"].setText(f"{pct:.1f}%")
        self._rpt_cards["avg_resolve"].setText(f"{avg_resolve:.1f}" if avg_resolve is not None else "—")

        # Monthly breakdown
        with _conn() as con:
            monthly = con.execute("""
                SELECT strftime('%Y-%m', call_date) AS month,
                       COUNT(*) AS total,
                       call_date, completion_date, completion_box
                FROM calls2
                WHERE call_date BETWEEN %s AND %s
                GROUP BY month, id
                ORDER BY month DESC
            """, (f, t)).fetchall()

        month_data = {}
        for row in monthly:
            m = row["month"]
            if m not in month_data:
                month_data[m] = {"total": 0, "escalated": 0, "overdue_days": []}
            resolve_d = row["completion_date"] if row["completion_box"] else today
            days = _days_between(row["call_date"], resolve_d) or 0
            month_data[m]["total"] += 1
            if days >= OVERDUE_DAYS:
                month_data[m]["escalated"] += 1
                month_data[m]["overdue_days"].append(days)

        self.rpt_tbl.setRowCount(0)
        for month in sorted(month_data.keys(), reverse=True):
            md = month_data[month]
            total_m = md["total"]
            esc_m = md["escalated"]
            esc_rate = f"{esc_m / total_m * 100:.1f}%" if total_m else "—"
            od = md["overdue_days"]
            avg_od = f"{sum(od) / len(od):.1f}" if od else "—"
            try:
                month_lbl = datetime.strptime(month, "%Y-%m").strftime("%b %Y")
            except (ValueError, TypeError):
                month_lbl = month
            r = self.rpt_tbl.rowCount()
            self.rpt_tbl.insertRow(r)
            self.rpt_tbl.setItem(r, 0, _ro_c(month_lbl))
            self.rpt_tbl.setItem(r, 1, _ro_c(str(total_m)))
            self.rpt_tbl.setItem(r, 2, _ro_c(str(esc_m)))
            self.rpt_tbl.setItem(r, 3, _ro_c(esc_rate))
            self.rpt_tbl.setItem(r, 4, _ro_c(avg_od))
            if esc_m > 0 and total_m > 0 and esc_m / total_m > 0.3:
                for c in range(5):
                    self.rpt_tbl.item(r, c).setBackground(QtGui.QColor(255, 243, 205))

    # ── Resolution Tracking ───────────────────────────────────────────────

    def _build_tracking_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        self.track_bar = DateRangeBar(default_days_back=730)
        self.track_bar.run_clicked.connect(self._run_tracking)
        v.addWidget(self.track_bar)

        self.track_tbl = QtWidgets.QTableWidget(0, 6)
        self.track_tbl.setHorizontalHeaderLabels([
            "Month", "Resolved", "Avg Days", "Min Days", "Max Days", "Trend"
        ])
        hh = self.track_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for c in (1, 2, 3, 4, 5):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.track_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.track_tbl.setAlternatingRowColors(True)
        self.track_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.track_tbl, stretch=1)

        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: _export_table(self.track_tbl, self, "cs_resolution_tracking.csv"))
        exp_row.addWidget(btn)
        v.addLayout(exp_row)
        return w

    def _run_tracking(self):
        f, t = self.track_bar.from_str, self.track_bar.to_str
        with _conn() as con:
            rows = con.execute("""
                SELECT strftime('%Y-%m', call_date) AS month,
                       call_date, completion_date
                FROM calls2
                WHERE completion_box = 1
                  AND completion_date IS NOT NULL
                  AND call_date BETWEEN %s AND %s
                ORDER BY month ASC
            """, (f, t)).fetchall()

        month_data = {}
        for row in rows:
            days = _days_between(row["call_date"], row["completion_date"])
            if days is None or days < OVERDUE_DAYS:
                continue
            m = row["month"]
            if m not in month_data:
                month_data[m] = []
            month_data[m].append(days)

        self.track_tbl.setRowCount(0)
        prev_avg = None
        for month in sorted(month_data.keys()):
            day_list = month_data[month]
            avg = sum(day_list) / len(day_list)
            mn = min(day_list)
            mx = max(day_list)

            if prev_avg is None:
                trend = "—"
            elif avg < prev_avg - 0.5:
                trend = "▲ Improving"
            elif avg > prev_avg + 0.5:
                trend = "▼ Worsening"
            else:
                trend = "→ Stable"

            try:
                month_lbl = datetime.strptime(month, "%Y-%m").strftime("%b %Y")
            except (ValueError, TypeError):
                month_lbl = month

            color = (QtGui.QColor(212, 237, 218) if avg <= OVERDUE_DAYS + 3
                     else QtGui.QColor(255, 243, 205) if avg <= OVERDUE_DAYS * 2
                     else QtGui.QColor(255, 200, 200))

            r = self.track_tbl.rowCount()
            self.track_tbl.insertRow(r)
            self.track_tbl.setItem(r, 0, _ro_c(month_lbl))
            self.track_tbl.setItem(r, 1, _ro_c(str(len(day_list))))
            self.track_tbl.setItem(r, 2, _ro_c(f"{avg:.1f}"))
            self.track_tbl.setItem(r, 3, _ro_c(str(mn)))
            self.track_tbl.setItem(r, 4, _ro_c(str(mx)))
            self.track_tbl.setItem(r, 5, _ro_c(trend))
            for c in range(6):
                self.track_tbl.item(r, c).setBackground(color)
            prev_avg = avg

    # ── Run all ───────────────────────────────────────────────────────────

    def _run_all(self):
        self._run_active()
        self._run_history()
        self._run_reports()
        self._run_tracking()


class CSEscalationsWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CS Escalations")
        self.resize(1100, 720)
        _apply_palette(self)
        self.setCentralWidget(CSEscalationsWidget())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = CSEscalationsWindow()
    win.show()
    sys.exit(app.exec())
