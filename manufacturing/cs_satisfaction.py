"""
cs_satisfaction.py — Customer Satisfaction
Tabs: CSAT Results | NPS Reports | Satisfaction Trends | Improvement Plans
"""
import sys
import os
import psycopg2
import psycopg2.extras
from .db_connection import get_db_connection
import csv
from datetime import date, datetime
from PyQt6 import QtCore, QtGui, QtWidgets


BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color%(white)s;border:2px solid black;border-radius:8px;"
    "padding:4px 12px;font-weight%(bold)s;}"
    "QPushButton%(hover)s{background-color%(rgb)s(85,255,255);}"
)
TAB_STYLE = (
    "QTabWidget:%(pane)s{border:1px solid #aaa;background%(white)s;}"
    "QTabBar:%(tab)s{background:#cce0ff;padding:6px 18px;font-weight%(bold)s;}"
    "QTabBar:%(tab)s%(selected)s{background%(white)s;border-bottom:2px solid rgb(0,85,255);}"
)
INPUT_STYLE = "QLineEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}"
COMBO_STYLE = "QComboBox{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}QComboBox QAbstractItemView{background-color%(white)s;}"
DATE_STYLE = "QDateEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 4px;}"
TEXT_STYLE = "QTextEdit{background-color%(white)s;border:2px solid black;border-radius:4px;padding:2px 6px;}"
HDR_STYLE = "font-size:20px;font-weight%(bold)s;color%(white)s;padding:4px;"
SECTION_STYLE = "font-size:13px;font-weight%(bold)s;color%(white)s;"
LABEL_STYLE = "color%(white)s;font-size:13px;"


def _conn():
    c = get_db_connection()
    return c


def _init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS cs_improvement_plan (
                id          SERIAL PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT,
                owner       TEXT,
                target_date TEXT,
                status      TEXT NOT NULL DEFAULT 'Open',
                created_date TEXT NOT NULL
            )
        """)


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


class CSSatisfactionWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_palette(self)
        self._plan_current_id = None
        self._build_ui()
        self._run_all()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        title = QtWidgets.QLabel("Customer Satisfaction")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(HDR_STYLE)
        root.addWidget(title)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_csat_tab(), "CSAT Results")
        self.tabs.addTab(self._build_nps_tab(), "NPS Reports")
        self.tabs.addTab(self._build_trends_tab(), "Satisfaction Trends")
        self.tabs.addTab(self._build_plans_tab(), "Improvement Plans")

    # ── CSAT Results ──────────────────────────────────────────────────────
    # Derived metric: completion rate per customer (higher = more satisfied)

    def _build_csat_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        info = QtWidgets.QLabel(
            "CSAT score derived from call completion rate and average resolution time per customer.")
        info.setStyleSheet("color%(white)s;font-size:12px;font-style%(italic)s;")
        info.setWordWrap(True)
        v.addWidget(info)

        self.csat_bar = DateRangeBar(default_days_back=365)
        self.csat_bar.run_clicked.connect(self._run_csat)
        v.addWidget(self.csat_bar)

        self.csat_tbl = QtWidgets.QTableWidget(0, 6)
        self.csat_tbl.setHorizontalHeaderLabels([
            "Customer", "Total Calls", "Completed", "Completion Rate",
            "Avg Resolution (days)", "CSAT Score"
        ])
        hh = self.csat_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.csat_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.csat_tbl.setAlternatingRowColors(True)
        self.csat_tbl.verticalHeader().setVisible(False)
        self.csat_tbl.setSortingEnabled(True)
        v.addWidget(self.csat_tbl, stretch=1)

        legend = QtWidgets.QHBoxLayout()
        for color, text in (
            (QtGui.QColor(212, 237, 218), "  CSAT ≥ 80%  "),
            (QtGui.QColor(255, 243, 205), "  CSAT 50–79%  "),
            (QtGui.QColor(255, 200, 200), "  CSAT < 50%  "),
        ):
            dot = QtWidgets.QLabel("  ")
            dot.setAutoFillBackground(True)
            p = dot.palette()
            p.setColor(QtGui.QPalette.ColorRole.Window, color)
            dot.setPalette(p)
            dot.setFixedSize(18, 18)
            legend.addWidget(dot)
            legend.addWidget(QtWidgets.QLabel(text) if False else _mk_lbl(text))
        legend.addStretch()
        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: _export_table(self.csat_tbl, self, "cs_csat.csv"))
        legend.addWidget(btn)
        v.addLayout(legend)
        return w

    def _run_csat(self):
        f, t = self.csat_bar.from_str, self.csat_bar.to_str
        with _conn() as con:
            rows = con.execute("""
                SELECT cu.id, cu.first_name, cu.last_name, cu.company_name,
                       COUNT(c2.id) AS total,
                       SUM(c2.completion_box) AS comp_ct,
                       AVG(CASE WHEN c2.completion_box=1 AND c2.completion_date IS NOT NULL
                                THEN julianday(c2.completion_date) - julianday(c2.call_date)
                                END) AS avg_res
                FROM calls2 c2
                LEFT JOIN customer cu ON cu.id = c2.customer_id
                WHERE c2.call_date BETWEEN %s AND %s
                GROUP BY c2.customer_id
                ORDER BY comp_ct * 1.0 / COUNT(c2.id) DESC
            """, (f, t)).fetchall()

        self.csat_tbl.setSortingEnabled(False)
        self.csat_tbl.setRowCount(0)
        for row in rows:
            company = (row["company_name"] or "").strip()
            contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
            cust = company if company else (contact if contact else "(no customer)")
            total = row["total"] or 0
            comp = row["comp_ct"] or 0
            rate = comp / total if total else 0
            rate_pct = f"{rate * 100:.1f}%"
            avg_res = row["avg_res"]
            avg_str = f"{avg_res:.1f}" if avg_res is not None else "—"

            # CSAT score: 70% weight on completion rate, 30% weight on speed
            # Resolution speed bonus: 0 if avg > 14 days, 100 if avg <= 1 day, linear in between
            if avg_res is not None:
                speed = max(0.0, min(1.0, (14 - avg_res) / 13))
            else:
                speed = 0.5
            csat = rate * 70 + speed * 30
            csat_str = f"{csat:.0f}"

            if rate >= 0.80:
                color = QtGui.QColor(212, 237, 218)
            elif rate >= 0.50:
                color = QtGui.QColor(255, 243, 205)
            else:
                color = QtGui.QColor(255, 200, 200)

            r = self.csat_tbl.rowCount()
            self.csat_tbl.insertRow(r)
            self.csat_tbl.setItem(r, 0, _ro(cust))
            self.csat_tbl.setItem(r, 1, _ro_c(str(total)))
            self.csat_tbl.setItem(r, 2, _ro_c(str(comp)))
            self.csat_tbl.setItem(r, 3, _ro_c(rate_pct))
            self.csat_tbl.setItem(r, 4, _ro_c(avg_str))
            self.csat_tbl.setItem(r, 5, _ro_c(csat_str))
            for c in range(6):
                self.csat_tbl.item(r, c).setBackground(color)
        self.csat_tbl.setSortingEnabled(True)

    # ── NPS Reports ───────────────────────────────────────────────────────
    # Proxy NPS: promoters = customers with ≥80% completion rate in period

    def _build_nps_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        info = QtWidgets.QLabel(
            "NPS proxy: customers with ≥80% completion rate = Promoters, "
            "50–79% = Passives, <50% = Detractors. "
            "Net Promoter Score = %Promoters − %Detractors.")
        info.setStyleSheet("color%(white)s;font-size:12px;font-style%(italic)s;")
        info.setWordWrap(True)
        v.addWidget(info)

        self.nps_bar = DateRangeBar(default_days_back=365)
        self.nps_bar.run_clicked.connect(self._run_nps)
        v.addWidget(self.nps_bar)

        # Score cards
        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(16)
        self._nps_cards = {}
        for key, label in (
            ("promoters",  "Promoters\n(≥80%)"),
            ("passives",   "Passives\n(50–79%)"),
            ("detractors", "Detractors\n(<50%)"),
            ("nps",        "NPS Score"),
        ):
            card = QtWidgets.QFrame()
            card.setFrameShape(QtWidgets.QFrame.Shape.Box)
            card.setStyleSheet("QFrame{background%(white)s;border:2px solid #0055ff;border-radius:8px;}")
            card.setFixedSize(180, 90)
            cl = QtWidgets.QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            tl = QtWidgets.QLabel(label)
            tl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            tl.setStyleSheet("color:#333;font-size:12px;font-weight%(bold)s;")
            vl = QtWidgets.QLabel("—")
            vl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            vl.setStyleSheet("color:#0055ff;font-size:22px;font-weight%(bold)s;")
            cl.addWidget(tl)
            cl.addWidget(vl)
            self._nps_cards[key] = vl
            cards.addWidget(card)
        cards.addStretch()
        v.addLayout(cards)

        v.addWidget(lbl("Customer Breakdown", SECTION_STYLE))

        self.nps_tbl = QtWidgets.QTableWidget(0, 4)
        self.nps_tbl.setHorizontalHeaderLabels(
            ["Customer", "Total Calls", "Completion Rate", "Category"])
        hh = self.nps_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.nps_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.nps_tbl.setAlternatingRowColors(True)
        self.nps_tbl.verticalHeader().setVisible(False)
        self.nps_tbl.setSortingEnabled(True)
        v.addWidget(self.nps_tbl, stretch=1)

        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: _export_table(self.nps_tbl, self, "cs_nps.csv"))
        exp_row.addWidget(btn)
        v.addLayout(exp_row)
        return w

    def _run_nps(self):
        f, t = self.nps_bar.from_str, self.nps_bar.to_str
        with _conn() as con:
            rows = con.execute("""
                SELECT cu.first_name, cu.last_name, cu.company_name,
                       COUNT(c2.id) AS total,
                       SUM(c2.completion_box) AS comp_ct
                FROM calls2 c2
                LEFT JOIN customer cu ON cu.id = c2.customer_id
                WHERE c2.call_date BETWEEN %s AND %s
                GROUP BY c2.customer_id
                HAVING COUNT(c2.id) > 0
            """, (f, t)).fetchall()

        promoters = passives = detractors = 0
        self.nps_tbl.setSortingEnabled(False)
        self.nps_tbl.setRowCount(0)
        for row in rows:
            company = (row["company_name"] or "").strip()
            contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
            cust = company if company else (contact if contact else "(no customer)")
            total = row["total"] or 0
            comp = row["comp_ct"] or 0
            rate = comp / total if total else 0
            rate_pct = f"{rate * 100:.1f}%"
            if rate >= 0.80:
                cat = "Promoter"
                color = QtGui.QColor(212, 237, 218)
                promoters += 1
            elif rate >= 0.50:
                cat = "Passive"
                color = QtGui.QColor(255, 243, 205)
                passives += 1
            else:
                cat = "Detractor"
                color = QtGui.QColor(255, 200, 200)
                detractors += 1
            r = self.nps_tbl.rowCount()
            self.nps_tbl.insertRow(r)
            self.nps_tbl.setItem(r, 0, _ro(cust))
            self.nps_tbl.setItem(r, 1, _ro_c(str(total)))
            self.nps_tbl.setItem(r, 2, _ro_c(rate_pct))
            self.nps_tbl.setItem(r, 3, _ro_c(cat))
            for c in range(4):
                self.nps_tbl.item(r, c).setBackground(color)
        self.nps_tbl.setSortingEnabled(True)

        n = promoters + passives + detractors
        nps = int((promoters - detractors) / n * 100) if n else 0
        self._nps_cards["promoters"].setText(str(promoters))
        self._nps_cards["passives"].setText(str(passives))
        self._nps_cards["detractors"].setText(str(detractors))
        self._nps_cards["nps"].setText(str(nps))

    # ── Satisfaction Trends ───────────────────────────────────────────────

    def _build_trends_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        self.trend_bar = DateRangeBar(default_days_back=730)
        self.trend_bar.run_clicked.connect(self._run_trends)
        v.addWidget(self.trend_bar)

        self.trend_tbl = QtWidgets.QTableWidget(0, 6)
        self.trend_tbl.setHorizontalHeaderLabels([
            "Month", "Total Calls", "Completed", "Completion Rate",
            "Avg Resolution (days)", "Trend"
        ])
        hh = self.trend_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for c in (1, 2, 3, 4, 5):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.trend_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.trend_tbl.setAlternatingRowColors(True)
        self.trend_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.trend_tbl, stretch=1)

        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: _export_table(self.trend_tbl, self, "cs_trends.csv"))
        exp_row.addWidget(btn)
        v.addLayout(exp_row)
        return w

    def _run_trends(self):
        f, t = self.trend_bar.from_str, self.trend_bar.to_str
        with _conn() as con:
            rows = con.execute("""
                SELECT strftime('%Y-%m', call_date) AS month,
                       COUNT(*) AS total,
                       SUM(completion_box) AS comp_ct,
                       AVG(CASE WHEN completion_box=1 AND completion_date IS NOT NULL
                                THEN julianday(completion_date) - julianday(call_date)
                                END) AS avg_res
                FROM calls2
                WHERE call_date BETWEEN %s AND %s
                GROUP BY month
                ORDER BY month ASC
            """, (f, t)).fetchall()

        self.trend_tbl.setRowCount(0)
        prev_rate = None
        for row in rows:
            total = row["total"] or 0
            comp = row["comp_ct"] or 0
            rate = comp / total if total else 0
            rate_pct = f"{rate * 100:.1f}%"
            avg_res = row["avg_res"]
            avg_str = f"{avg_res:.1f}" if avg_res is not None else "—"

            if prev_rate is None:
                trend = "—"
            elif rate > prev_rate + 0.02:
                trend = "▲ Improving"
            elif rate < prev_rate - 0.02:
                trend = "▼ Declining"
            else:
                trend = "→ Stable"

            try:
                month_lbl = datetime.strptime(row["month"], "%Y-%m").strftime("%b %Y")
            except (ValueError, TypeError):
                month_lbl = row["month"] or ""

            color = (QtGui.QColor(212, 237, 218) if rate >= 0.80
                     else QtGui.QColor(255, 243, 205) if rate >= 0.50
                     else QtGui.QColor(255, 200, 200))

            r = self.trend_tbl.rowCount()
            self.trend_tbl.insertRow(r)
            self.trend_tbl.setItem(r, 0, _ro_c(month_lbl))
            self.trend_tbl.setItem(r, 1, _ro_c(str(total)))
            self.trend_tbl.setItem(r, 2, _ro_c(str(comp)))
            self.trend_tbl.setItem(r, 3, _ro_c(rate_pct))
            self.trend_tbl.setItem(r, 4, _ro_c(avg_str))
            self.trend_tbl.setItem(r, 5, _ro_c(trend))
            for c in range(6):
                self.trend_tbl.item(r, c).setBackground(color)
            prev_rate = rate

    # ── Improvement Plans ─────────────────────────────────────────────────

    def _build_plans_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        self.plan_status_filter = QtWidgets.QComboBox()
        self.plan_status_filter.setStyleSheet(COMBO_STYLE)
        self.plan_status_filter.addItems(["(all)", "Open", "In Progress", "Completed", "Cancelled"])
        btn_filter = QtWidgets.QPushButton("Apply Filter")
        btn_filter.setStyleSheet(BUTTON_STYLE)
        btn_filter.setFixedHeight(28)
        btn_filter.clicked.connect(self._run_plans)
        top.addWidget(lbl("Status:"))
        top.addWidget(self.plan_status_filter)
        top.addWidget(btn_filter)
        top.addStretch()
        v.addLayout(top)

        self.plan_tbl = QtWidgets.QTableWidget(0, 5)
        self.plan_tbl.setHorizontalHeaderLabels(
            ["Title", "Owner", "Target Date", "Created", "Status"])
        hh = self.plan_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.plan_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.plan_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.plan_tbl.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.plan_tbl.setAlternatingRowColors(True)
        self.plan_tbl.verticalHeader().setVisible(False)
        self.plan_tbl.clicked.connect(self._on_plan_row_clicked)
        v.addWidget(self.plan_tbl, stretch=1)

        # Entry form
        form = QtWidgets.QGroupBox("Improvement Plan")
        form.setStyleSheet(
            "QGroupBox{color%(white)s;font-weight%(bold)s;border:1px solid white;margin-top:8px;}"
            "QGroupBox:%(title)s{subcontrol-origin%(margin)s;left:10px;}")
        grid = QtWidgets.QGridLayout(form)
        grid.setSpacing(6)

        self.pl_title = QtWidgets.QLineEdit()
        self.pl_title.setStyleSheet(INPUT_STYLE)
        self.pl_title.setPlaceholderText("Plan title")

        self.pl_owner = QtWidgets.QLineEdit()
        self.pl_owner.setStyleSheet(INPUT_STYLE)
        self.pl_owner.setPlaceholderText("Responsible owner")

        self.pl_target = QtWidgets.QDateEdit(calendarPopup=True)
        self.pl_target.setStyleSheet(DATE_STYLE)
        self.pl_target.setDisplayFormat("MM/dd/yyyy")
        self.pl_target.setDate(QtCore.QDate.currentDate().addDays(30))

        self.pl_status = QtWidgets.QComboBox()
        self.pl_status.setStyleSheet(COMBO_STYLE)
        self.pl_status.addItems(["Open", "In Progress", "Completed", "Cancelled"])

        self.pl_desc = QtWidgets.QTextEdit()
        self.pl_desc.setStyleSheet(TEXT_STYLE)
        self.pl_desc.setFixedHeight(60)
        self.pl_desc.setPlaceholderText("Description / action items...")

        grid.addWidget(lbl("Title:"), 0, 0)
        grid.addWidget(self.pl_title, 0, 1, 1, 2)
        grid.addWidget(lbl("Owner:"), 0, 3)
        grid.addWidget(self.pl_owner, 0, 4)
        grid.addWidget(lbl("Target Date:"), 1, 0)
        grid.addWidget(self.pl_target, 1, 1)
        grid.addWidget(lbl("Status:"), 1, 2)
        grid.addWidget(self.pl_status, 1, 3)
        grid.addWidget(lbl("Description:"), 2, 0)
        grid.addWidget(self.pl_desc, 2, 1, 1, 4)
        v.addWidget(form)

        br = QtWidgets.QHBoxLayout()
        for text, fn in (("Add", self._plan_add), ("Update Selected", self._plan_update),
                         ("Delete Selected", self._plan_delete),
                         ("Export CSV", lambda: _export_table(self.plan_tbl, self, "cs_improvement_plans.csv")),
                         ("Clear", self._plan_clear)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        return w

    def _run_plans(self):
        status_filter = self.plan_status_filter.currentText()
        with _conn() as con:
            if status_filter == "(all)":
                rows = con.execute(
                    "SELECT * FROM cs_improvement_plan ORDER BY target_date ASC"
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM cs_improvement_plan WHERE status=%s ORDER BY target_date ASC",
                    (status_filter,)
                ).fetchall()

        self._plan_ids = []
        self.plan_tbl.setRowCount(0)
        today = date.today().isoformat()
        for row in rows:
            overdue = (row["status"] not in ("Completed", "Cancelled")
                       and row["target_date"] and row["target_date"] < today)
            if row["status"] == "Completed":
                color = QtGui.QColor(212, 237, 218)
            elif row["status"] == "Cancelled":
                color = QtGui.QColor(220, 220, 220)
            elif overdue:
                color = QtGui.QColor(255, 200, 200)
            elif row["status"] == "In Progress":
                color = QtGui.QColor(255, 243, 205)
            else:
                color = QtGui.QColor(255, 255, 255)

            r = self.plan_tbl.rowCount()
            self.plan_tbl.insertRow(r)
            self._plan_ids.append(row["id"])
            for c, val in enumerate([
                row["title"] or "",
                row["owner"] or "",
                row["target_date"] or "",
                row["created_date"] or "",
                row["status"] or "",
            ]):
                item = _ro_c(val) if c in (2, 3, 4) else _ro(val)
                item.setBackground(color)
                self.plan_tbl.setItem(r, c, item)

    def _on_plan_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._plan_ids):
            return
        self._plan_current_id = self._plan_ids[row]
        with _conn() as con:
            rec = con.execute("SELECT * FROM cs_improvement_plan WHERE id=%s",
                              (self._plan_current_id,)).fetchone()
        if not rec:
            return
        self.pl_title.setText(rec["title"] or "")
        self.pl_owner.setText(rec["owner"] or "")
        self.pl_desc.setPlainText(rec["description"] or "")
        idx = self.pl_status.findText(rec["status"] or "Open")
        self.pl_status.setCurrentIndex(idx if idx >= 0 else 0)
        if rec["target_date"]:
            try:
                parts = rec["target_date"].split("-")
                self.pl_target.setDate(QtCore.QDate(int(parts[0]), int(parts[1]), int(parts[2])))
            except (ValueError, IndexError):
                pass

    def _plan_collect(self):
        title = self.pl_title.text().strip()
        if not title:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Title is required.")
            return None
        return {
            "title": title,
            "description": self.pl_desc.toPlainText().strip() or None,
            "owner": self.pl_owner.text().strip() or None,
            "target_date": self.pl_target.date().toString("yyyy-MM-dd"),
            "status": self.pl_status.currentText(),
            "created_date": date.today().isoformat(),
        }

    def _plan_add(self):
        data = self._plan_collect()
        if not data:
            return
        with _conn() as con:
            con.execute("""
                INSERT INTO cs_improvement_plan
                    (title, description, owner, target_date, status, created_date)
                VALUES (%(title)s, %(description)s, %(owner)s, %(target_date)s, %(status)s, %(created_date)s)
            """, data)
        self._plan_clear()
        self._run_plans()

    def _plan_update(self):
        if self._plan_current_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a plan first.")
            return
        data = self._plan_collect()
        if not data:
            return
        data["id"] = self._plan_current_id
        with _conn() as con:
            con.execute("""
                UPDATE cs_improvement_plan
                SET title=%(title)s, description=%(description)s, owner=%(owner)s,
                    target_date=%(target_date)s, status=%(status)s
                WHERE id=%(id)s
            """, data)
        self._run_plans()

    def _plan_delete(self):
        if self._plan_current_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a plan first.")
            return
        if (QtWidgets.QMessageBox.question(
                self, "Confirm Delete", "Delete this improvement plan%s",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            with _conn() as con:
                con.execute("DELETE FROM cs_improvement_plan WHERE id=%s", (self._plan_current_id,))
            self._plan_clear()
            self._run_plans()

    def _plan_clear(self):
        self._plan_current_id = None
        self.pl_title.clear()
        self.pl_owner.clear()
        self.pl_desc.clear()
        self.pl_status.setCurrentIndex(0)
        self.pl_target.setDate(QtCore.QDate.currentDate().addDays(30))
        self.plan_tbl.clearSelection()

    # ── Run all ───────────────────────────────────────────────────────────

    def _run_all(self):
        self._plan_ids = []
        self._run_csat()
        self._run_nps()
        self._run_trends()
        self._run_plans()


def _mk_lbl(text):
    w = QtWidgets.QLabel(text)
    w.setStyleSheet("color%(white)s;font-size:12px;")
    return w


class CSSatisfactionWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Customer Satisfaction")
        self.resize(1100, 720)
        _apply_palette(self)
        self.setCentralWidget(CSSatisfactionWidget())


if __name__ == "__main__":
    _init_db()
    app = QtWidgets.QApplication(sys.argv)
    win = CSSatisfactionWindow()
    win.show()
    sys.exit(app.exec())
