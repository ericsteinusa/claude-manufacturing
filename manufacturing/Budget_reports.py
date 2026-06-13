"""
Budget_reports.py — Budget Manager oversight report screens

Read-only (and approval) views that aggregate the real budget data managed by
``Budget_mgmt`` (the ``budget`` / ``budget_line`` tables) against GL actuals:

    BudgetDetailWidget      — every budget line for the year, across budgets
    BudgetVsActualWidget    — per-budget budgeted vs. actual vs. variance
    VarianceReportWidget    — per-line variance, ranked worst-overspend first
    DeptSummaryWidget       — budgeted/actual/variance aggregated by department
    ApprovalWorkflowWidget  — approval queue; Approve / Send Back a budget

Variance is ``budgeted - actual``; a negative variance (overspend) is shown in
red, matching the convention in Budget_mgmt. Actuals come from posted GL
journal lines and are 0 when no GL data exists, so the reports still render the
budgeted side on a fresh database.
"""
import sys
from PyQt6 import QtCore, QtGui, QtWidgets
from .Budget_mgmt import (get_db, init_db, _apply_blue_palette, _ro, _ro_right,
                          _actual_for_account, CURRENT_YEAR, BUDGET_COLORS)

BUTTON_STYLE = (
    "QPushButton{background-color:white;border:2px solid black;"
    "border-radius:8px;"
    "padding:4px 10px;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
)
RED = QtGui.QColor("#cc0000")
GREEN = QtGui.QColor("#1a7f37")


def _m(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return ""
    return f"-${abs(v):,.2f}" if round(v, 2) < 0 else f"${abs(v):,.2f}"


def _pct(variance, budgeted):
    if not budgeted:
        return ""
    return f"{variance / budgeted * 100:+.1f}%"


# ── Data helpers ─────────────────────────────────────────────────────────────
def _budgets_for_year(year):
    """One row per budget for the year: department + budgeted total."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT b.id, b.budget_name, b.status, b.dept_id, d.dept_name,
                   COALESCE(SUM(bl.budgeted_amount), 0) AS budgeted
            FROM budget b
            LEFT JOIN dept d ON d.dept_id = b.dept_id
            LEFT JOIN budget_line bl ON bl.budget_id = b.id
            WHERE b.fiscal_year = %s
            GROUP BY b.id, d.dept_name
            ORDER BY d.dept_name, b.budget_name
        """, (year,)).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    return rows


def _budget_lines(year):
    """Every budget line for the year, joined to its budget and department."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT b.budget_name, b.status, d.dept_name,
                   bl.account_id, bl.category, bl.description,
                   bl.budgeted_amount
            FROM budget b
            LEFT JOIN dept d ON d.dept_id = b.dept_id
            JOIN budget_line bl ON bl.budget_id = b.id
            WHERE b.fiscal_year = %s
            ORDER BY d.dept_name, b.budget_name, bl.category
        """, (year,)).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    return rows


def _budget_actual(budget_id, year):
    """Sum posted-GL actuals across a budget's referenced accounts."""
    conn = get_db()
    try:
        lines = conn.execute(
            "SELECT account_id FROM budget_line "
            "WHERE budget_id=%s AND account_id IS NOT NULL",
            (budget_id,)).fetchall()
        ids = [ln["account_id"] for ln in lines]
        if not ids:
            return 0.0
        ph = ",".join(["%s"] * len(ids))
        row = conn.execute(f"""
            SELECT COALESCE(SUM(ABS(jl.debit - jl.credit)), 0) AS total
            FROM gl_journal_line jl
            JOIN gl_journal j ON j.id = jl.journal_id
            WHERE jl.account_id IN ({ph})
              AND j.posted = 1
              AND EXTRACT(YEAR FROM j.journal_date::date) = %s
        """, ids + [year]).fetchone()
        return row["total"] if row else 0.0
    except Exception:
        return 0.0
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# Shared report base — year selector + table + optional summary line
# ═════════════════════════════════════════════════════════════════════════════
class _BudgetReport(QtWidgets.QWidget):
    TITLE = ""
    HEADERS = []            # (label, stretch_bool)
    BUTTONS = []            # (label, method_name) for action subclasses

    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        init_db()
        self._build_ui()
        self._reload()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)

        title = QtWidgets.QLabel(self.TITLE)
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:20px;font-weight:bold;color:white;padding:4px;")
        v.addWidget(title)

        fr = QtWidgets.QHBoxLayout()
        ylbl = QtWidgets.QLabel("Fiscal Year:")
        ylbl.setStyleSheet("color:white;font-weight:bold;")
        fr.addWidget(ylbl)
        self.year = QtWidgets.QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(CURRENT_YEAR)
        self.year.setFixedWidth(85)
        self.year.valueChanged.connect(self._reload)
        fr.addWidget(self.year)
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.setStyleSheet(BUTTON_STYLE)
        refresh.clicked.connect(self._reload)
        fr.addWidget(refresh)
        fr.addStretch()
        self.summary = QtWidgets.QLabel("")
        self.summary.setStyleSheet("color:white;font-weight:bold;")
        fr.addWidget(self.summary)
        v.addLayout(fr)

        self.table = QtWidgets.QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels([h[0] for h in self.HEADERS])
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        for i, (_, stretch) in enumerate(self.HEADERS):
            hh.setSectionResizeMode(
                i, QtWidgets.QHeaderView.ResizeMode.Stretch if stretch
                else QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table, stretch=1)

        if self.BUTTONS:
            br = QtWidgets.QHBoxLayout()
            for label, method in self.BUTTONS:
                b = QtWidgets.QPushButton(label)
                b.setStyleSheet(BUTTON_STYLE)
                b.clicked.connect(getattr(self, method))
                br.addWidget(b)
            br.addStretch()
            v.addLayout(br)

    def _set_row(self, r, values):
        """values: list of (text, kind).

        kind is 'l'eft, 'r'ight, or a QColor for right-aligned + colored.
        """
        self.table.insertRow(r)
        for c, item in enumerate(values):
            text, kind = item
            if kind == "l":
                cell = _ro(text)
            else:
                cell = _ro_right(text)
                if isinstance(kind, QtGui.QColor):
                    cell.setForeground(kind)
            self.table.setItem(r, c, cell)

    def _reload(self):
        self.table.setRowCount(0)
        self._populate()

    def _populate(self):
        raise NotImplementedError


# ═════════════════════════════════════════════════════════════════════════════
# Concrete reports
# ═════════════════════════════════════════════════════════════════════════════
class BudgetDetailWidget(_BudgetReport):
    TITLE = "Budget Detail — All Lines"
    HEADERS = [("Budget", False), ("Department", False), ("Category", False),
               ("Description", True), ("Budgeted", False)]

    def _populate(self):
        total = 0.0
        for ln in _budget_lines(self.year.value()):
            total += ln["budgeted_amount"] or 0
            r = self.table.rowCount()
            self._set_row(r, [
                (ln["budget_name"], "l"),
                (ln["dept_name"] or "(all)", "l"),
                (ln["category"] or "", "l"),
                (ln["description"] or "", "l"),
                (_m(ln["budgeted_amount"]), "r"),
            ])
        self.summary.setText(
            f"{self.table.rowCount()} lines · Budgeted {_m(total)}")


class BudgetVsActualWidget(_BudgetReport):
    TITLE = "Budget vs. Actual — by Budget"
    HEADERS = [("Budget", True), ("Department", False), ("Budgeted", False),
               ("Actual", False), ("Variance", False), ("Var %", False),
               ("Status", False)]

    def _populate(self):
        year = self.year.value()
        tb = ta = 0.0
        for b in _budgets_for_year(year):
            budgeted = b["budgeted"] or 0
            actual = _budget_actual(b["id"], year)
            variance = budgeted - actual
            tb += budgeted
            ta += actual
            r = self.table.rowCount()
            self._set_row(r, [
                (b["budget_name"], "l"),
                (b["dept_name"] or "(all)", "l"),
                (_m(budgeted), "r"),
                (_m(actual), "r"),
                (_m(variance), RED if variance < 0 else "r"),
                (_pct(variance, budgeted), RED if variance < 0 else "r"),
                ((b["status"] or "").capitalize(), "l"),
            ])
            bg = QtGui.QColor(BUDGET_COLORS.get(b["status"], "#ffffff"))
            for c in range(len(self.HEADERS)):
                self.table.item(r, c).setBackground(bg)
        tv = tb - ta
        self.summary.setText(
            f"Budgeted {_m(tb)} · Actual {_m(ta)} · Variance {_m(tv)}")


class VarianceReportWidget(_BudgetReport):
    TITLE = "Variance Report — by Line (worst overspend first)"
    HEADERS = [("Budget", False), ("Category", False), ("Description", True),
               ("Budgeted", False), ("Actual", False), ("Variance", False),
               ("Var %", False)]

    def _populate(self):
        year = self.year.value()
        rows = []
        for ln in _budget_lines(year):
            budgeted = ln["budgeted_amount"] or 0
            actual = (_actual_for_account(ln["account_id"], year)
                      if ln["account_id"] else 0.0)
            rows.append((ln, budgeted, actual, budgeted - actual))
        rows.sort(key=lambda t: t[3])  # most negative (overspent) first
        for ln, budgeted, actual, variance in rows:
            r = self.table.rowCount()
            color = RED if variance < 0 else (GREEN if variance > 0 else "r")
            self._set_row(r, [
                (ln["budget_name"], "l"),
                (ln["category"] or "", "l"),
                (ln["description"] or "", "l"),
                (_m(budgeted), "r"),
                (_m(actual), "r"),
                (_m(variance), color),
                (_pct(variance, budgeted), color),
            ])
        over = sum(1 for _, _, _, v in rows if v < 0)
        self.summary.setText(f"{len(rows)} lines · {over} over budget")


class DeptSummaryWidget(_BudgetReport):
    TITLE = "Department Summaries"
    HEADERS = [("Department", True), ("Budgets", False), ("Budgeted", False),
               ("Actual", False), ("Variance", False), ("Var %", False)]

    def _populate(self):
        year = self.year.value()
        agg = {}  # dept_name -> [count, budgeted, actual]
        for b in _budgets_for_year(year):
            dept = b["dept_name"] or "(unassigned)"
            slot = agg.setdefault(dept, [0, 0.0, 0.0])
            slot[0] += 1
            slot[1] += b["budgeted"] or 0
            slot[2] += _budget_actual(b["id"], year)
        tb = ta = 0.0
        for dept in sorted(agg):
            count, budgeted, actual = agg[dept]
            variance = budgeted - actual
            tb += budgeted
            ta += actual
            r = self.table.rowCount()
            self._set_row(r, [
                (dept, "l"),
                (str(count), "r"),
                (_m(budgeted), "r"),
                (_m(actual), "r"),
                (_m(variance), RED if variance < 0 else "r"),
                (_pct(variance, budgeted), RED if variance < 0 else "r"),
            ])
        self.summary.setText(
            f"{len(agg)} departments · Budgeted {_m(tb)} "
            f"· Actual {_m(ta)}")


class ApprovalWorkflowWidget(_BudgetReport):
    TITLE = "Approval Workflow"
    HEADERS = [("Budget", True), ("Department", False), ("Budgeted", False),
               ("Status", False)]
    BUTTONS = [("Approve", "_approve"), ("Send Back to Draft", "_send_back")]

    def _populate(self):
        self._row_ids = []
        year = self.year.value()
        pending = 0
        for b in _budgets_for_year(year):
            r = self.table.rowCount()
            self._row_ids.append(b["id"])
            status = (b["status"] or "").capitalize()
            self._set_row(r, [
                (b["budget_name"], "l"),
                (b["dept_name"] or "(all)", "l"),
                (_m(b["budgeted"]), "r"),
                (status, "l"),
            ])
            bg = QtGui.QColor(BUDGET_COLORS.get(b["status"], "#ffffff"))
            for c in range(len(self.HEADERS)):
                self.table.item(r, c).setBackground(bg)
            if b["status"] == "draft":
                pending += 1
        self.summary.setText(
            f"{self.table.rowCount()} budgets · "
            f"{pending} awaiting approval")

    def _selected_budget_id(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self._row_ids):
            return None
        return self._row_ids[r]

    def _set_status(self, status):
        bid = self._selected_budget_id()
        if bid is None:
            QtWidgets.QMessageBox.information(
                self, "No selection", "Select a budget first.")
            return
        conn = get_db()
        try:
            conn.execute(
                "UPDATE budget SET status=%s WHERE id=%s", (status, bid))
            conn.commit()
        finally:
            conn.close()
        self._reload()

    def _approve(self):
        self._set_status("approved")

    def _send_back(self):
        self._set_status("draft")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("Budget Reports")
    win.resize(1150, 740)
    _apply_blue_palette(win)
    tabs = QtWidgets.QTabWidget()
    tabs.addTab(BudgetDetailWidget(), "Budget Detail")
    tabs.addTab(BudgetVsActualWidget(), "Budget vs. Actual")
    tabs.addTab(VarianceReportWidget(), "Variance Report")
    tabs.addTab(DeptSummaryWidget(), "Department Summaries")
    tabs.addTab(ApprovalWorkflowWidget(), "Approval Workflow")
    win.setCentralWidget(tabs)
    win.show()
    sys.exit(app.exec())
