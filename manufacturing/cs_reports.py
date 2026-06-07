"""
cs_reports.py — Customer Service Reports
Tabs: Summary | Call Volume | By Customer | Open Calls
"""
import sys
from .db_pg import get_db
import csv
from datetime import date, datetime
from PyQt6 import QtCore, QtGui, QtWidgets


BLUE = QtGui.QColor(0, 85, 255)

BUTTON_STYLE = (
    "QPushButton{background-color:white;border:2px solid "
    "black;border-radius:8px;"
    "padding:4px 12px;font-weight:bold;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid #aaa;background:white;}"
    "QTabBar::tab{background:#cce0ff;padding:6px 18px;font-weight:bold;}"
    "QTabBar::tab:selected{background:white;border-bottom:2px solid "
    "rgb(0,85,255);}"
)
HDR_STYLE = "font-size:20px;font-weight:bold;color:white;padding:4px;"
SECTION_STYLE = "font-size:13px;font-weight:bold;color:white;"
DATE_STYLE = (
    "QDateEdit{background-color:white;border:2px solid "
    "black;border-radius:4px;padding:2px 4px;}"
)
COMBO_STYLE = (
    "QComboBox{background-color:white;border:2px solid "
    "black;border-radius:4px;padding:2px 6px;}QComboBox "
    "QAbstractItemView{background-color:white;}"
)

OVERDUE_DAYS = 7   # open calls older than this are highlighted red


def _conn():
    c = get_db()
    return c


def _apply_palette(widget):
    pal = QtGui.QPalette()
    for g in (QtGui.QPalette.ColorGroup.Active,
              QtGui.QPalette.ColorGroup.Inactive,
              QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(g, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(g, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft |
        QtCore.Qt.AlignmentFlag.AlignVCenter):
    item = QtWidgets.QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable |
                  QtCore.Qt.ItemFlag.ItemIsEnabled)
    item.setTextAlignment(align)
    return item


def _ro_c(text):
    return _ro(text, QtCore.Qt.AlignmentFlag.AlignCenter |
               QtCore.Qt.AlignmentFlag.AlignVCenter)


def _ro_r(text):
    return _ro(text, QtCore.Qt.AlignmentFlag.AlignRight |
               QtCore.Qt.AlignmentFlag.AlignVCenter)


def _days_between(d1_str, d2_str):
    """Return integer days between two yyyy-MM-dd strings, or None on failure."""  # noqa: E501
    try:
        d1 = date.fromisoformat(d1_str)
        d2 = date.fromisoformat(d2_str)
        return (d2 - d1).days
    except (TypeError, ValueError):
        return None


def _export_table(table: QtWidgets.QTableWidget, parent,
                  default_name="cs_report.csv"):
    if table.rowCount() == 0:
        QtWidgets.QMessageBox.information(
    parent, "Export", "No data to export.")
        return
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent, "Export to CSV", default_name, "CSV Files (*.csv)"
    )
    if not path:
        return
    headers = [table.horizontalHeaderItem(
        c).text() for c in range(table.columnCount())]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in range(table.rowCount()):
            w.writerow([table.item(r, c).text() if table.item(r, c) else ""
                        for c in range(table.columnCount())])
    QtWidgets.QMessageBox.information(
    parent, "Export Complete", f"Saved to:\n{path}")


# ── Shared date-range widget ────────────────────────────────────────────

class DateRangeBar(QtWidgets.QWidget):
    """Reusable from/to date bar with a Run button."""

    run_clicked = QtCore.pyqtSignal()

    def __init__(self, default_days_back=365, parent=None):
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet("color:white;font-size:13px;")
            return w

        self.dt_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.dt_from.setStyleSheet(DATE_STYLE)
        self.dt_from.setDisplayFormat("MM/dd/yyyy")
        self.dt_from.setDate(
            QtCore.QDate.currentDate().addDays(-default_days_back))

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


# ── Main window ─────────────────────────────────────────────────────────

class CSReportsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_palette(self)
        self._build_ui()
        self._run_all()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        title = QtWidgets.QLabel("Customer Service Reports")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(HDR_STYLE)
        root.addWidget(title)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_summary_tab(), "Summary")
        self.tabs.addTab(self._build_volume_tab(), "Call Volume")
        self.tabs.addTab(self._build_customer_tab(), "By Customer")
        self.tabs.addTab(self._build_open_tab(), "Open Calls")

    # ── Summary tab ───────────────────────────────────────────────────────

    def _build_summary_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(10)

        self.sum_bar = DateRangeBar(default_days_back=365)
        self.sum_bar.run_clicked.connect(self._run_summary)
        v.addWidget(self.sum_bar)

        # Metric cards
        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(16)
        self._sum_cards = {}
        for key, label in (
            ("total",      "Total Calls"),
            ("open",       "Open"),
            ("completed",  "Completed"),
            ("rate",       "Completion Rate"),
            ("avg_res",    "Avg Resolution\n(days)"),
            ("avg_age",    "Avg Age Open\n(days)"),
        ):
            card = QtWidgets.QFrame()
            card.setFrameShape(QtWidgets.QFrame.Shape.Box)
            card.setStyleSheet(
                "QFrame{background:white;border:2px solid "
                "#0055ff;border-radius:8px;}"
            )
            card.setFixedSize(160, 90)
            cl = QtWidgets.QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            title_lbl = QtWidgets.QLabel(label)
            title_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            title_lbl.setStyleSheet(
                "color:#333;font-size:12px;font-weight:bold;")
            val_lbl = QtWidgets.QLabel("—")
            val_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            val_lbl.setStyleSheet(
                "color:#0055ff;font-size:22px;font-weight:bold;")
            cl.addWidget(title_lbl)
            cl.addWidget(val_lbl)
            self._sum_cards[key] = val_lbl
            cards.addWidget(card)
        cards.addStretch()
        v.addLayout(cards)

        # Recent activity table
        lbl = QtWidgets.QLabel("Recent Completed Calls")
        lbl.setStyleSheet(SECTION_STYLE)
        v.addWidget(lbl)

        self.sum_tbl = QtWidgets.QTableWidget(0, 5)
        self.sum_tbl.setHorizontalHeaderLabels(
            ["Customer", "Problem / Call", "Call Date", "Completed Date", "Resolution (days)"])  # noqa: E501
        hh = self.sum_tbl.horizontalHeader()
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (2, 3, 4):
            hh.setSectionResizeMode(
    c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.sum_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sum_tbl.setAlternatingRowColors(True)
        self.sum_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.sum_tbl, stretch=1)

        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(
    lambda: _export_table(
        self.sum_tbl,
        self,
         "cs_summary.csv"))
        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        exp_row.addWidget(btn)
        v.addLayout(exp_row)
        return w

    def _run_summary(self):
        f, t = self.sum_bar.from_str, self.sum_bar.to_str
        today = date.today().isoformat()
        with _conn() as con:
            rows = con.execute("""
                SELECT c2.*, cu.first_name, cu.last_name, cu.company_name
                FROM calls2 c2
                LEFT JOIN customer cu ON cu.id = c2.customer_id
                WHERE c2.call_date BETWEEN %s AND %s
                ORDER BY c2.call_date DESC
            """, (f, t)).fetchall()

        total = len(rows)
        completed = [r for r in rows if r["completion_box"]]
        open_rows = [r for r in rows if not r["completion_box"]]

        res_days = [d for r in completed
                    if (d := _days_between(r["call_date"], r["completion_date"])) is not None and d >= 0]  # noqa: E501
        avg_res = (sum(res_days) / len(res_days)) if res_days else None

        age_days = [d for r in open_rows
                    if (d := _days_between(r["call_date"], today)) is not None]
        avg_age = (sum(age_days) / len(age_days)) if age_days else None

        rate = (len(completed) / total * 100) if total else 0

        self._sum_cards["total"].setText(str(total))
        self._sum_cards["open"].setText(str(len(open_rows)))
        self._sum_cards["completed"].setText(str(len(completed)))
        self._sum_cards["rate"].setText(f"{rate:.1f}%")
        self._sum_cards["avg_res"].setText(
            f"{avg_res:.1f}" if avg_res is not None else "—")
        self._sum_cards["avg_age"].setText(
            f"{avg_age:.1f}" if avg_age is not None else "—")

        # Recent completed table (last 50)
        self.sum_tbl.setRowCount(0)
        for row in completed[:50]:
            company = (row["company_name"] or "").strip()
            contact = f"{
    row['first_name'] or ''} {
        row['last_name'] or ''}".strip()
            cust = company if company else (
    contact if contact else "(no customer)")
            res = _days_between(row["call_date"], row["completion_date"])
            r = self.sum_tbl.rowCount()
            self.sum_tbl.insertRow(r)
            self.sum_tbl.setItem(r, 0, _ro(cust))
            self.sum_tbl.setItem(r, 1, _ro(row["call"] or ""))
            self.sum_tbl.setItem(r, 2, _ro_c(row["call_date"] or ""))
            self.sum_tbl.setItem(r, 3, _ro_c(row["completion_date"] or ""))
            self.sum_tbl.setItem(
    r, 4, _ro_r(
        str(res) if res is not None else "—"))

    # ── Call Volume tab ───────────────────────────────────────────────────

    def _build_volume_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(10)

        self.vol_bar = DateRangeBar(default_days_back=365)
        self.vol_bar.run_clicked.connect(self._run_volume)
        v.addWidget(self.vol_bar)

        self.vol_tbl = QtWidgets.QTableWidget(0, 5)
        self.vol_tbl.setHorizontalHeaderLabels(
            ["Month", "Total Calls", "Open", "Completed", "Completion Rate"])
        hh = self.vol_tbl.horizontalHeader()
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(
    c, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.vol_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.vol_tbl.setAlternatingRowColors(True)
        self.vol_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.vol_tbl, stretch=1)

        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(
    lambda: _export_table(
        self.vol_tbl,
        self,
         "cs_call_volume.csv"))
        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        exp_row.addWidget(btn)
        v.addLayout(exp_row)
        return w

    def _run_volume(self):
        f, t = self.vol_bar.from_str, self.vol_bar.to_str
        with _conn() as con:
            rows = con.execute("""
                SELECT strftime('%Y-%m', call_date) AS month,
                       COUNT(*)                    AS total,
                       SUM(CASE WHEN completion_box=0 THEN 1 ELSE 0 END) AS
                           open_ct,
                       SUM(completion_box)          AS comp_ct
                FROM calls2
                WHERE call_date BETWEEN %s AND %s
                GROUP BY month
                ORDER BY month DESC
            """, (f, t)).fetchall()

        self.vol_tbl.setRowCount(0)
        for row in rows:
            total = row["total"] or 0
            comp = row["comp_ct"] or 0
            open_ct = row["open_ct"] or 0
            rate = f"{comp / total * 100:.1f}%" if total else "—"

            # Format month label: "2025-04" → "Apr 2025"
            try:
                month_lbl = datetime.strptime(
    row["month"], "%Y-%m").strftime("%b %Y")
            except (ValueError, TypeError):
                month_lbl = row["month"] or ""

            r = self.vol_tbl.rowCount()
            self.vol_tbl.insertRow(r)
            self.vol_tbl.setItem(r, 0, _ro_c(month_lbl))
            self.vol_tbl.setItem(r, 1, _ro_c(str(total)))
            self.vol_tbl.setItem(r, 2, _ro_c(str(open_ct)))
            self.vol_tbl.setItem(r, 3, _ro_c(str(comp)))
            self.vol_tbl.setItem(r, 4, _ro_c(rate))

            # Shade rows with high open counts
            if open_ct > 0 and total > 0 and open_ct / total > 0.5:
                color = QtGui.QColor(255, 243, 205)
                for c in range(5):
                    self.vol_tbl.item(r, c).setBackground(color)

    # ── By Customer tab ───────────────────────────────────────────────────

    def _build_customer_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(10)

        self.cust_bar = DateRangeBar(default_days_back=365)
        self.cust_bar.run_clicked.connect(self._run_customer)
        v.addWidget(self.cust_bar)

        self.cust_tbl = QtWidgets.QTableWidget(0, 6)
        self.cust_tbl.setHorizontalHeaderLabels([
            "Customer", "Total Calls", "Open", "Completed",
            "Completion Rate", "Avg Resolution (days)"
        ])
        hh = self.cust_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5):
            hh.setSectionResizeMode(
    c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.cust_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cust_tbl.setAlternatingRowColors(True)
        self.cust_tbl.verticalHeader().setVisible(False)
        self.cust_tbl.setSortingEnabled(True)
        v.addWidget(self.cust_tbl, stretch=1)

        btn = QtWidgets.QPushButton("Export CSV")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(
    lambda: _export_table(
        self.cust_tbl,
        self,
         "cs_by_customer.csv"))
        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        exp_row.addWidget(btn)
        v.addLayout(exp_row)
        return w

    def _run_customer(self):
        f, t = self.cust_bar.from_str, self.cust_bar.to_str
        with _conn() as con:
            rows = con.execute("""
                SELECT cu.id, cu.first_name, cu.last_name, cu.company_name,
                       COUNT(c2.id)
                           AS total,
                       SUM(CASE WHEN c2.completion_box=0 THEN 1 ELSE 0 END)  AS
                           open_ct,
                       SUM(c2.completion_box)
                           AS comp_ct
                FROM calls2 c2
                LEFT JOIN customer cu ON cu.id = c2.customer_id
                WHERE c2.call_date BETWEEN %s AND %s
                GROUP BY cu.id, cu.first_name, cu.last_name, cu.company_name
                ORDER BY total DESC
            """, (f, t)).fetchall()

            # Fetch per-customer resolution averages separately
            res_rows = con.execute("""
                SELECT c2.customer_id,
                       AVG(julianday(c2.completion_date) -
                           julianday(c2.call_date)) AS avg_res
                FROM calls2 c2
                WHERE c2.completion_box = 1
                  AND c2.call_date BETWEEN %s AND %s
                  AND c2.completion_date IS NOT NULL
                GROUP BY c2.customer_id
            """, (f, t)).fetchall()
        avg_res_map = {r["customer_id"]: r["avg_res"] for r in res_rows}

        self.cust_tbl.setSortingEnabled(False)
        self.cust_tbl.setRowCount(0)
        for row in rows:
            company = (row["company_name"] or "").strip()
            contact = f"{
    row['first_name'] or ''} {
        row['last_name'] or ''}".strip()
            cust = company if company else (
    contact if contact else "(no customer)")
            total = row["total"] or 0
            comp = row["comp_ct"] or 0
            open_ct = row["open_ct"] or 0
            rate = f"{comp / total * 100:.1f}%" if total else "—"
            avg = avg_res_map.get(row["id"])
            avg_str = f"{avg:.1f}" if avg is not None else "—"

            r = self.cust_tbl.rowCount()
            self.cust_tbl.insertRow(r)
            self.cust_tbl.setItem(r, 0, _ro(cust))
            self.cust_tbl.setItem(r, 1, _ro_c(str(total)))
            self.cust_tbl.setItem(r, 2, _ro_c(str(open_ct)))
            self.cust_tbl.setItem(r, 3, _ro_c(str(comp)))
            self.cust_tbl.setItem(r, 4, _ro_c(rate))
            self.cust_tbl.setItem(r, 5, _ro_c(avg_str))

            if open_ct > 0:
                for c in range(6):
                    self.cust_tbl.item(
    r, c).setBackground(
        QtGui.QColor(
            255, 243, 205))
        self.cust_tbl.setSortingEnabled(True)

    # ── Open Calls tab ────────────────────────────────────────────────────

    def _build_open_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(10)

        top = QtWidgets.QHBoxLayout()
        self.open_overdue_lbl = QtWidgets.QLabel("")
        self.open_overdue_lbl.setStyleSheet(
            "color:white;font-size:13px;font-weight:bold;")
        top.addWidget(self.open_overdue_lbl)
        top.addStretch()
        btn_run = QtWidgets.QPushButton("Refresh")
        btn_run.setStyleSheet(BUTTON_STYLE)
        btn_run.setFixedHeight(28)
        btn_run.clicked.connect(self._run_open)
        top.addWidget(btn_run)
        v.addLayout(top)

        self.open_tbl = QtWidgets.QTableWidget(0, 6)
        self.open_tbl.setHorizontalHeaderLabels([
            "Customer", "Problem / Call", "Call Date", "Call Time",
            "Days Open", "Comments"
        ])
        hh = self.open_tbl.horizontalHeader()
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (2, 3, 4):
            hh.setSectionResizeMode(
    c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.open_tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.open_tbl.setAlternatingRowColors(True)
        self.open_tbl.verticalHeader().setVisible(False)
        self.open_tbl.setSortingEnabled(True)
        v.addWidget(self.open_tbl, stretch=1)

        legend = QtWidgets.QHBoxLayout()
        for color, text in (
            (QtGui.QColor(255, 243, 205), f"  Open < {OVERDUE_DAYS} days  "),
            (QtGui.QColor(255, 200, 200),
             f"  Overdue ≥ {OVERDUE_DAYS} days  "),
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
        btn_exp.clicked.connect(
    lambda: _export_table(
        self.open_tbl,
        self,
         "cs_open_calls.csv"))
        legend.addWidget(btn_exp)
        v.addLayout(legend)
        return w

    def _run_open(self):
        today = date.today().isoformat()
        with _conn() as con:
            rows = con.execute("""
                SELECT c2.id, c2.call, c2.call_date, c2.call_time,
                    c2.comments_box,
                       cu.first_name, cu.last_name, cu.company_name
                FROM calls2 c2
                LEFT JOIN customer cu ON cu.id = c2.customer_id
                WHERE c2.completion_box = 0
                ORDER BY c2.call_date ASC, c2.call_time ASC
            """).fetchall()

        self.open_tbl.setSortingEnabled(False)
        self.open_tbl.setRowCount(0)
        overdue_count = 0
        for row in rows:
            days_open = _days_between(row["call_date"], today)
            if days_open is None:
                days_open = 0
            overdue = days_open >= OVERDUE_DAYS
            if overdue:
                overdue_count += 1
            color = QtGui.QColor(
    255, 200, 200) if overdue else QtGui.QColor(
        255, 243, 205)

            company = (row["company_name"] or "").strip()
            contact = f"{
    row['first_name'] or ''} {
        row['last_name'] or ''}".strip()
            cust = company if company else (
    contact if contact else "(no customer)")

            r = self.open_tbl.rowCount()
            self.open_tbl.insertRow(r)
            self.open_tbl.setItem(r, 0, _ro(cust))
            self.open_tbl.setItem(r, 1, _ro(row["call"] or ""))
            self.open_tbl.setItem(r, 2, _ro_c(row["call_date"] or ""))
            self.open_tbl.setItem(r, 3, _ro_c(row["call_time"] or ""))
            self.open_tbl.setItem(r, 4, _ro_c(str(days_open)))
            self.open_tbl.setItem(r, 5, _ro(row["comments_box"] or ""))
            for c in range(6):
                self.open_tbl.item(r, c).setBackground(color)

        self.open_tbl.setSortingEnabled(True)
        total_open = len(rows)
        self.open_overdue_lbl.setText(
            f"{total_open} open call(s) — {overdue_count} overdue (≥{OVERDUE_DAYS} days)"  # noqa: E501
        )

    # ── Run all tabs ──────────────────────────────────────────────────────

    def _run_all(self):
        self._run_summary()
        self._run_volume()
        self._run_customer()
        self._run_open()


class CSReportsWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Customer Service Reports")
        self.resize(1100, 720)
        _apply_palette(self)
        self.setCentralWidget(CSReportsWidget())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = CSReportsWindow()
    win.show()
    sys.exit(app.exec())
