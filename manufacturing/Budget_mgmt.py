import sys
import psycopg2
from .db_pg import get_db_connection
from PyQt6 import QtCore, QtGui, QtWidgets


BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; "
    "border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid "
    "rgb(85, 255, 255);}"
)
INPUT_STYLE = (
    "QLineEdit{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
)
COMBO_STYLE = (
    "QComboBox{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
    "QComboBox QAbstractItemView{background-color: white;}"
)
LABEL_STYLE = "color: white; font-size: 13px;"

BUDGET_COLORS = {
    "draft":    "#ffffff",
    "approved": "#cce5ff",
    "active":   "#d4edda",
    "closed":   "#dcdcdc",
}

CURRENT_YEAR = QtCore.QDate.currentDate().year()


def get_db():
    return get_db_connection()


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budget (
            id SERIAL PRIMARY KEY,
            budget_name TEXT NOT NULL,
            fiscal_year INTEGER NOT NULL,
            dept_id INTEGER,
            status TEXT DEFAULT 'draft',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budget_line (
            id SERIAL PRIMARY KEY,
            budget_id INTEGER NOT NULL REFERENCES budget(id),
            account_id INTEGER,
            category TEXT DEFAULT '',
            description TEXT NOT NULL,
            budgeted_amount REAL DEFAULT 0,
            notes TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


def _apply_blue_palette(widget):
    pal = widget.palette()
    for group in (QtGui.QPalette.ColorGroup.Active,
                  QtGui.QPalette.ColorGroup.Inactive,
                  QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(group, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(group, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _ro(text):
    item = QtWidgets.QTableWidgetItem(text)
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    return item


def _ro_right(text):
    item = _ro(text)
    item.setTextAlignment(
        QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # noqa: E501
    return item


def _load_depts():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT dept_id, dept_name FROM dept ORDER BY dept_name"
        ).fetchall()
    except psycopg2.OperationalError:
        rows = []
    conn.close()
    return rows


def _load_accounts():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, account_number, account_name, account_type"
            " FROM gl_account WHERE is_active = 1 ORDER BY account_number"
        ).fetchall()
    except psycopg2.OperationalError:
        rows = []
    conn.close()
    return rows


def _actual_for_account(account_id, fiscal_year):
    """Sum posted GL journal lines for an account in the given fiscal year."""
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT COALESCE(SUM(jl.debit - jl.credit), 0) AS net
            FROM gl_journal_line jl
            JOIN gl_journal j ON j.id = jl.journal_id
            WHERE jl.account_id = %s
              AND j.posted = 1
              AND EXTRACT(YEAR FROM j.journal_date::date) = %s
        """, (account_id, fiscal_year)).fetchone()
        return abs(row["net"]) if row else 0.0
    except Exception:
        return 0.0
    finally:
        conn.close()


# ── Dialogs ─────────────────────────────────────────────────────────────

class BudgetDialog(QtWidgets.QDialog):
    def __init__(self, budget_id=None, parent=None):
        super().__init__(parent)
        self._budget_id = budget_id
        self.setWindowTitle("Edit Budget" if budget_id else "New Budget")
        self.resize(460, 300)
        _apply_blue_palette(self)
        self.saved_id = None
        self._build_ui()
        if budget_id:
            self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.name = QtWidgets.QLineEdit()
        self.name.setStyleSheet(INPUT_STYLE)
        self.name.setPlaceholderText("e.g. Operations FY2026")
        layout.addRow(lbl("Budget Name:"), self.name)

        self.year = QtWidgets.QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(CURRENT_YEAR)
        self.year.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Fiscal Year:"), self.year)

        self.dept_combo = QtWidgets.QComboBox()
        self.dept_combo.setStyleSheet(COMBO_STYLE)
        self.dept_combo.setMinimumWidth(200)
        self.dept_combo.addItem("(all departments)", None)
        for d in _load_depts():
            self.dept_combo.addItem(d["dept_name"], d["dept_id"])
        layout.addRow(lbl("Department:"), self.dept_combo)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("draft", "approved", "active", "closed"):
            self.status_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Notes:"), self.notes)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _load(self):
        conn = get_db()
        rec = conn.execute("SELECT * FROM budget WHERE id = %s",
                           (self._budget_id,)).fetchone()
        conn.close()
        if not rec:
            return
        self.name.setText(rec["budget_name"] or "")
        self.year.setValue(rec["fiscal_year"] or CURRENT_YEAR)
        for i in range(self.dept_combo.count()):
            if self.dept_combo.itemData(i) == rec["dept_id"]:
                self.dept_combo.setCurrentIndex(i)
                break
        for i in range(self.status_combo.count()):
            if self.status_combo.itemData(i) == rec["status"]:
                self.status_combo.setCurrentIndex(i)
                break
        self.notes.setText(rec["notes"] or "")

    def _on_ok(self):
        name = self.name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Budget name is required.")
            return
        conn = get_db()
        if self._budget_id is None:
            cur = conn.execute(
                "INSERT INTO budget (budget_name, fiscal_year, dept_id, "
                "status, notes)"
                " VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (name, self.year.value(), self.dept_combo.currentData(),
                 self.status_combo.currentData(), self.notes.text().strip())
            )
            self.saved_id = cur.fetchone()['id']
        else:
            conn.execute(
                "UPDATE budget SET budget_name=%s, fiscal_year=%s, dept_id=%s,"
                " status=%s, notes=%s WHERE id=%s",
                (name, self.year.value(), self.dept_combo.currentData(),
                 self.status_combo.currentData(), self.notes.text().strip(),
                 self._budget_id)
            )
            self.saved_id = self._budget_id
        conn.commit()
        conn.close()
        self.accept()


class BudgetLineDialog(QtWidgets.QDialog):
    def __init__(self, budget_id, line_id=None, parent=None):
        super().__init__(parent)
        self._budget_id = budget_id
        self._line_id = line_id
        self.setWindowTitle("Edit Line" if line_id else "Add Budget Line")
        self.resize(460, 300)
        _apply_blue_palette(self)
        self._build_ui()
        if line_id:
            self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.account_combo = QtWidgets.QComboBox()
        self.account_combo.setStyleSheet(COMBO_STYLE)
        self.account_combo.setMinimumWidth(260)
        self.account_combo.currentIndexChanged.connect(
            self._on_account_changed)
        self.account_combo.addItem("(none)", None)
        for a in _load_accounts():
            self.account_combo.addItem(
                f"{a['account_number']} — {a['account_name']}", a["id"])
        layout.addRow(lbl("GL Account:"), self.account_combo)

        self.category = QtWidgets.QLineEdit()
        self.category.setStyleSheet(INPUT_STYLE)
        self.category.setPlaceholderText("e.g. Salaries, Supplies, Travel")
        layout.addRow(lbl("Category:"), self.category)

        self.description = QtWidgets.QLineEdit()
        self.description.setStyleSheet(INPUT_STYLE)
        self.description.setPlaceholderText("Line item description (required)")
        layout.addRow(lbl("Description:"), self.description)

        self.amount = QtWidgets.QDoubleSpinBox()
        self.amount.setRange(0, 99999999)
        self.amount.setDecimals(2)
        self.amount.setPrefix("$ ")
        self.amount.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Budgeted Amount:"), self.amount)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Notes:"), self.notes)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_account_changed(self):
        if not self.description.text():
            self.description.setText(
                self.account_combo.currentText().split("—")[-1].strip())

    def _load(self):
        conn = get_db()
        rec = conn.execute("SELECT * FROM budget_line WHERE id = %s",
                           (self._line_id,)).fetchone()
        conn.close()
        if not rec:
            return
        for i in range(self.account_combo.count()):
            if self.account_combo.itemData(i) == rec["account_id"]:
                self.account_combo.setCurrentIndex(i)
                break
        self.category.setText(rec["category"] or "")
        self.description.setText(rec["description"] or "")
        self.amount.setValue(rec["budgeted_amount"] or 0)
        self.notes.setText(rec["notes"] or "")

    def _on_ok(self):
        desc = self.description.text().strip()
        if not desc:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Description is required.")
            return
        conn = get_db()
        if self._line_id is None:
            conn.execute(
                "INSERT INTO budget_line (budget_id, account_id, category,"
                " description, budgeted_amount, notes)"
                " VALUES (%s,%s,%s,%s,%s,%s)",
                (self._budget_id, self.account_combo.currentData(),
                 self.category.text().strip(), desc,
                 self.amount.value(), self.notes.text().strip())
            )
        else:
            conn.execute(
                "UPDATE budget_line SET account_id=%s, category=%s, "
                "description=%s,"
                " budgeted_amount=%s, notes=%s WHERE id=%s",
                (self.account_combo.currentData(), self.category.text().strip(),  # noqa: E501
                 desc, self.amount.value(), self.notes.text().strip(),
                 self._line_id)
            )
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ─────────────────────────────────────────────────────────

class BudgetManagementWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._budget_row_ids = []
        self._line_row_ids = []
        self._selected_budget_id = None
        self._selected_fiscal_year = CURRENT_YEAR
        self._selected_line_id = None
        self._build_ui()
        init_db()
        self._refresh_budgets()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # filter row
        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.setStyleSheet(COMBO_STYLE)
        self.status_filter.addItem("(all)", None)
        for s in ("draft", "approved", "active", "closed"):
            self.status_filter.addItem(s.capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh_budgets)
        fr.addWidget(self.status_filter)

        fr.addSpacing(10)
        lbl_y = QtWidgets.QLabel("Year:")
        lbl_y.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_y)
        self.year_filter = QtWidgets.QSpinBox()
        self.year_filter.setRange(2000, 2100)
        self.year_filter.setValue(CURRENT_YEAR)
        self.year_filter.setStyleSheet(INPUT_STYLE)
        self.year_filter.setFixedWidth(75)
        self.year_filter.valueChanged.connect(self._refresh_budgets)
        fr.addWidget(self.year_filter)

        fr.addSpacing(10)
        lbl_d = QtWidgets.QLabel("Dept:")
        lbl_d.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_d)
        self.dept_filter = QtWidgets.QComboBox()
        self.dept_filter.setStyleSheet(COMBO_STYLE)
        self.dept_filter.setMinimumWidth(150)
        self.dept_filter.addItem("(all)", None)
        for d in _load_depts():
            self.dept_filter.addItem(d["dept_name"], d["dept_id"])
        self.dept_filter.currentIndexChanged.connect(self._refresh_budgets)
        fr.addWidget(self.dept_filter)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        # Budget list
        self.budget_table = QtWidgets.QTableWidget()
        self.budget_table.setColumnCount(7)
        self.budget_table.setHorizontalHeaderLabels(
            ["Budget Name", "Fiscal Year", "Department",
             "Budgeted", "Actual", "Variance", "Status"]
        )
        hh = self.budget_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    6, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.budget_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.budget_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.budget_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.budget_table.setAlternatingRowColors(True)
        self.budget_table.verticalHeader().setVisible(False)
        self.budget_table.clicked.connect(self._on_budget_clicked)
        self.budget_table.doubleClicked.connect(self._on_edit_budget)
        splitter.addWidget(self.budget_table)

        # Budget lines detail
        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Budget Lines (vs. Actual)")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.line_table = QtWidgets.QTableWidget()
        self.line_table.setColumnCount(6)
        self.line_table.setHorizontalHeaderLabels(
            ["Category", "Description", "GL Account",
             "Budgeted", "Actual", "Variance"]
        )
        lh = self.line_table.horizontalHeader()
        lh.setStyleSheet("color: black; font-weight: bold;")
        lh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        lh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        lh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        lh.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        lh.setSectionResizeMode(
    4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        lh.setSectionResizeMode(
    5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.line_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.line_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.line_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.line_table.verticalHeader().setVisible(False)
        self.line_table.setAlternatingRowColors(True)
        self.line_table.clicked.connect(self._on_line_clicked)
        dv.addWidget(self.line_table)
        splitter.addWidget(detail_w)
        splitter.setSizes([340, 260])
        v.addWidget(splitter, stretch=1)

        # Button rows
        br1 = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Budget",    self._on_new_budget),
            ("Edit Budget",   self._on_edit_budget),
            ("Approve",       lambda: self._set_budget_status("approved")),
            ("Activate",      lambda: self._set_budget_status("active")),
            ("Close Budget",  lambda: self._set_budget_status("closed")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(slot)
            br1.addWidget(b)
        br1.addStretch()
        v.addLayout(br1)

        br2 = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add Line",      self._on_add_line),
            ("Edit Line",     self._on_edit_line),
            ("Delete Line",   self._on_delete_line),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(slot)
            br2.addWidget(b)
        br2.addStretch()
        v.addLayout(br2)

    def _refresh_budgets(self):
        status = self.status_filter.currentData()
        year = self.year_filter.value()
        dept_id = self.dept_filter.currentData()

        conds = ["b.fiscal_year = %s"]
        params = [year]
        if status:
            conds.append("b.status = %s")
            params.append(status)
        if dept_id:
            conds.append("b.dept_id = %s")
            params.append(dept_id)
        where = " AND ".join(conds)

        conn = get_db()
        try:
            rows = conn.execute(f"""
                SELECT b.id, b.budget_name, b.fiscal_year, b.status,
                       d.dept_name,
                       COALESCE(SUM(bl.budgeted_amount), 0) AS total_budgeted
                FROM budget b
                LEFT JOIN dept d ON d.dept_id = b.dept_id
                LEFT JOIN budget_line bl ON bl.budget_id = b.id
                WHERE {where}
                GROUP BY b.id, d.dept_name
                ORDER BY b.fiscal_year DESC, b.budget_name
            """, params).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.budget_table.setRowCount(0)
        self._budget_row_ids = []
        for row in rows:
            r = self.budget_table.rowCount()
            self.budget_table.insertRow(r)
            self._budget_row_ids.append(row["id"])

            budgeted = row["total_budgeted"]
            # Compute actual from GL (sum of all lines)
            actual = self._total_actual_for_budget(
                row["id"], row["fiscal_year"])
            variance = budgeted - actual

            self.budget_table.setItem(r, 0, _ro(row["budget_name"]))
            self.budget_table.setItem(r, 1, _ro(str(row["fiscal_year"])))
            self.budget_table.setItem(r, 2, _ro(row["dept_name"] or "(all)"))
            self.budget_table.setItem(r, 3, _ro_right(f"${budgeted:,.2f}"))
            self.budget_table.setItem(r, 4, _ro_right(f"${actual:,.2f}"))
            var_item = _ro_right(f"${variance:,.2f}")
            if variance < 0:
                var_item.setForeground(QtGui.QColor("#cc0000"))
            self.budget_table.setItem(r, 5, var_item)
            self.budget_table.setItem(r, 6, _ro(row["status"].capitalize()))
            bg = QtGui.QColor(BUDGET_COLORS.get(row["status"], "#ffffff"))
            for col in range(7):
                self.budget_table.item(r, col).setBackground(bg)

        self._selected_budget_id = None
        self._selected_fiscal_year = year
        self.line_table.setRowCount(0)

    def _total_actual_for_budget(self, budget_id, fiscal_year):
        """Sum actuals for all GL accounts referenced in budget lines."""
        conn = get_db()
        try:
            lines = conn.execute(
                "SELECT account_id FROM budget_line WHERE budget_id=%s AND "
                "account_id IS NOT NULL",
                (budget_id,)
            ).fetchall()
            if not lines:
                return 0.0
            account_ids = [line["account_id"] for line in lines]
            placeholders = ",".join(["%s"] * len(account_ids))
            row = conn.execute(f"""
                SELECT COALESCE(SUM(ABS(jl.debit - jl.credit)), 0) AS total
                FROM gl_journal_line jl
                JOIN gl_journal j ON j.id = jl.journal_id
                WHERE jl.account_id IN ({placeholders})
                  AND j.posted = 1
                  AND EXTRACT(YEAR FROM j.journal_date::date) = %s
            """, account_ids + [fiscal_year]).fetchone()
            return row["total"] if row else 0.0
        except Exception:
            return 0.0
        finally:
            conn.close()

    def _on_show_all(self):
        self.status_filter.blockSignals(True)
        self.status_filter.setCurrentIndex(0)
        self.status_filter.blockSignals(False)
        self.dept_filter.blockSignals(True)
        self.dept_filter.setCurrentIndex(0)
        self.dept_filter.blockSignals(False)
        self._refresh_budgets()

    def _on_budget_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._budget_row_ids):
            return
        self._selected_budget_id = self._budget_row_ids[row]
        try:
            self._selected_fiscal_year = int(
                self.budget_table.item(row, 1).text())
        except ValueError:
            self._selected_fiscal_year = CURRENT_YEAR
        self._selected_line_id = None
        self._refresh_lines()

    def _refresh_lines(self):
        self.line_table.setRowCount(0)
        self._line_row_ids = []
        if self._selected_budget_id is None:
            return
        conn = get_db()
        try:
            lines = conn.execute("""
                SELECT bl.id, bl.category, bl.description, bl.budgeted_amount,
                       bl.account_id, a.account_number, a.account_name
                FROM budget_line bl
                LEFT JOIN gl_account a ON a.id = bl.account_id
                WHERE bl.budget_id = %s
                ORDER BY bl.category, bl.description
            """, (self._selected_budget_id,)).fetchall()
        except psycopg2.OperationalError:
            lines = []
        conn.close()

        for line in lines:
            r = self.line_table.rowCount()
            self.line_table.insertRow(r)
            self._line_row_ids.append(line["id"])

            budgeted = line["budgeted_amount"]
            actual = _actual_for_account(
                line["account_id"], self._selected_fiscal_year
            ) if line["account_id"] else 0.0
            variance = budgeted - actual

            acct_display = ""
            if line["account_number"]:
                acct_display = f"{
    line['account_number']} — {
        line['account_name']}"

            self.line_table.setItem(r, 0, _ro(line["category"] or ""))
            self.line_table.setItem(r, 1, _ro(line["description"]))
            self.line_table.setItem(r, 2, _ro(acct_display))
            self.line_table.setItem(r, 3, _ro_right(f"${budgeted:,.2f}"))
            self.line_table.setItem(r, 4, _ro_right(f"${actual:,.2f}"))
            var_item = _ro_right(f"${variance:,.2f}")
            if variance < 0:
                var_item.setForeground(QtGui.QColor("#cc0000"))
            self.line_table.setItem(r, 5, var_item)

    def _on_line_clicked(self, index):
        row = index.row()
        if 0 <= row < len(self._line_row_ids):
            self._selected_line_id = self._line_row_ids[row]

    def _on_new_budget(self):
        dlg = BudgetDialog(parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_budgets()

    def _on_edit_budget(self, _index=None):
        if self._selected_budget_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a budget first.")
            return
        dlg = BudgetDialog(budget_id=self._selected_budget_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_budgets()

    def _set_budget_status(self, new_status):
        if self._selected_budget_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a budget first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", f"Mark budget as {new_status}?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE budget SET status=%s WHERE id=%s",
                         (new_status, self._selected_budget_id))
            conn.commit()
            conn.close()
            self._refresh_budgets()

    def _on_add_line(self):
        if self._selected_budget_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a budget first.")
            return
        dlg = BudgetLineDialog(self._selected_budget_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_budgets()
            self._refresh_lines()

    def _on_edit_line(self):
        if self._selected_line_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection",
                                          "Select a budget line first.")
            return
        dlg = BudgetLineDialog(self._selected_budget_id,
                               line_id=self._selected_line_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_budgets()
            self._refresh_lines()

    def _on_delete_line(self):
        if self._selected_line_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection",
                                          "Select a budget line first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete", "Delete this budget line?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM budget_line WHERE id=%s",
                         (self._selected_line_id,))
            conn.commit()
            conn.close()
            self._selected_line_id = None
            self._refresh_budgets()
            self._refresh_lines()


class BudgetManagementWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Budget Management")
        self.resize(1060, 720)
        _apply_blue_palette(self)
        self.setCentralWidget(BudgetManagementWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = BudgetManagementWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
