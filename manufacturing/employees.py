import sys
import psycopg2
from .db_pg import get_db_connection
from .schema import init_schema
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


def get_db():
    return get_db_connection()


def init_db():
    init_schema()


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


def _load_dept_subs(dept_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT dept_sub_id, dept_sub_name FROM dept_sub WHERE dept_id = "
            "%s"
            " ORDER BY dept_sub_name", (dept_id,)
        ).fetchall()
    except psycopg2.OperationalError:
        rows = []
    conn.close()
    return rows


def _load_roles():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, role_name FROM roles ORDER BY role_name").fetchall()
    except psycopg2.OperationalError:
        rows = []
    conn.close()
    return rows


# ── Dialogs ─────────────────────────────────────────────────────────────

class EmployeeDialog(QtWidgets.QDialog):
    """Shared dialog for adding and editing an employee."""

    def __init__(self, people_id=None, parent=None):
        super().__init__(parent)
        self._people_id = people_id
        self.setWindowTitle("Edit Employee" if people_id else "New Employee")
        self.resize(500, 500)
        _apply_blue_palette(self)
        self.saved_id = None
        self._build_ui()
        if people_id:
            self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.first_name = QtWidgets.QLineEdit()
        self.first_name.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("First Name:"), self.first_name)

        self.last_name = QtWidgets.QLineEdit()
        self.last_name.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Last Name:"), self.last_name)

        self.email = QtWidgets.QLineEdit()
        self.email.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Email:"), self.email)

        self.employee_id = QtWidgets.QLineEdit()
        self.employee_id.setStyleSheet(INPUT_STYLE)
        self.employee_id.setPlaceholderText("Employee number")
        layout.addRow(lbl("Employee ID:"), self.employee_id)

        self.job_title = QtWidgets.QLineEdit()
        self.job_title.setStyleSheet(INPUT_STYLE)
        self.job_title.setPlaceholderText("Job title")
        layout.addRow(lbl("Job Title:"), self.job_title)

        self.dept_combo = QtWidgets.QComboBox()
        self.dept_combo.setStyleSheet(COMBO_STYLE)
        self.dept_combo.setMinimumWidth(200)
        self.dept_combo.addItem("(none)", None)
        for d in _load_depts():
            self.dept_combo.addItem(d["dept_name"], d["dept_id"])
        self.dept_combo.currentIndexChanged.connect(self._on_dept_changed)
        layout.addRow(lbl("Department:"), self.dept_combo)

        self.sub_combo = QtWidgets.QComboBox()
        self.sub_combo.setStyleSheet(COMBO_STYLE)
        layout.addRow(lbl("Sub-Dept:"), self.sub_combo)

        self.role_combo = QtWidgets.QComboBox()
        self.role_combo.setStyleSheet(COMBO_STYLE)
        self.role_combo.addItem("(none)", None)
        for r in _load_roles():
            self.role_combo.addItem(r["role_name"], r["id"])
        layout.addRow(lbl("Role:"), self.role_combo)

        self.address = QtWidgets.QLineEdit()
        self.address.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Address:"), self.address)

        self.city = QtWidgets.QLineEdit()
        self.city.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("City:"), self.city)

        self.state = QtWidgets.QLineEdit()
        self.state.setStyleSheet(INPUT_STYLE)
        self.state.setMaxLength(2)
        self.state.setFixedWidth(50)
        layout.addRow(lbl("State:"), self.state)

        self.zip_code = QtWidgets.QLineEdit()
        self.zip_code.setStyleSheet(INPUT_STYLE)
        self.zip_code.setFixedWidth(90)
        layout.addRow(lbl("Zip:"), self.zip_code)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_dept_changed(self):
        self.sub_combo.clear()
        self.sub_combo.addItem("(none)", None)
        dept_id = self.dept_combo.currentData()
        if dept_id is not None:
            for s in _load_dept_subs(dept_id):
                self.sub_combo.addItem(s["dept_sub_name"], s["dept_sub_id"])

    def _load(self):
        conn = get_db()
        rec = conn.execute("SELECT * FROM people WHERE id = %s",
                           (self._people_id,)).fetchone()
        pos = conn.execute("SELECT job_title FROM position WHERE people_id = %s",  # noqa: E501
                           (self._people_id,)).fetchone()
        role = conn.execute(
            "SELECT role_id FROM user_roles WHERE people_id = %s",
            (self._people_id,)
        ).fetchone()
        conn.close()
        if not rec:
            return
        self.first_name.setText(rec["first_name"] or "")
        self.last_name.setText(rec["last_name"] or "")
        self.email.setText(rec["email"] or "")
        self.employee_id.setText(str(rec["employee_id"] or ""))
        self.job_title.setText(pos["job_title"] if pos else "")
        self.address.setText(rec["address"] or "")
        self.city.setText(rec["city"] or "")
        self.state.setText(rec["state"] or "")
        self.zip_code.setText(rec["zip_code"] or "")

        # Set department
        if rec["dept_id"] is not None:
            for i in range(self.dept_combo.count()):
                if self.dept_combo.itemData(i) == rec["dept_id"]:
                    self.dept_combo.setCurrentIndex(i)
                    break
            # Set sub-dept after dept is set (populates sub_combo)
            if rec["dept_sub_id"] is not None:
                for i in range(self.sub_combo.count()):
                    if self.sub_combo.itemData(i) == rec["dept_sub_id"]:
                        self.sub_combo.setCurrentIndex(i)
                        break

        # Set role
        if role:
            for i in range(self.role_combo.count()):
                if self.role_combo.itemData(i) == role["role_id"]:
                    self.role_combo.setCurrentIndex(i)
                    break

    def _on_ok(self):
        first = self.first_name.text().strip()
        last = self.last_name.text().strip()
        if not (first or last):
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "First or last name is required.")
            return
        try:
            emp_id = int(self.employee_id.text().strip()
                         ) if self.employee_id.text().strip() else 0
        except ValueError:
            emp_id = 0

        conn = get_db()
        try:
            if self._people_id is None:
                cur = conn.execute(
                    "INSERT INTO people (first_name, last_name, email, "
                    "employee_id,"
                    " address, city, state, zip_code, dept_id, dept_sub_id)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (first, last, self.email.text().strip(), emp_id,
                     self.address.text().strip(), self.city.text().strip(),
                     self.state.text().strip(), self.zip_code.text().strip(),
                     self.dept_combo.currentData(), self.sub_combo.currentData())  # noqa: E501
                )
                self.saved_id = cur.fetchone()['id']
            else:
                conn.execute(
                    "UPDATE people SET first_name=%s, last_name=%s, email=%s,"
                    " employee_id=%s, address=%s, city=%s, state=%s, "
                    "zip_code=%s,"
                    " dept_id=%s, dept_sub_id=%s WHERE id=%s",
                    (first, last, self.email.text().strip(), emp_id,
                     self.address.text().strip(), self.city.text().strip(),
                     self.state.text().strip(), self.zip_code.text().strip(),
                     self.dept_combo.currentData(), self.sub_combo.currentData(),  # noqa: E501
                     self._people_id)
                )
                self.saved_id = self._people_id

            pid = self.saved_id
            # Upsert job title
            title = self.job_title.text().strip()
            conn.execute(
                "INSERT INTO position (people_id, job_title) VALUES (%s,%s)"
                " ON CONFLICT (people_id) DO UPDATE SET job_title = "
                "EXCLUDED.job_title",
                (pid, title)
            )
            # Upsert role
            role_id = self.role_combo.currentData()
            if role_id is not None:
                conn.execute(
                    "INSERT INTO user_roles (people_id, role_id) VALUES "
                    "(%s,%s)"
                    " ON CONFLICT (people_id) DO UPDATE SET role_id = "
                    "EXCLUDED.role_id",
                    (pid, role_id)
                )
            conn.commit()
        except psycopg2.IntegrityError as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class EmployeeDetailPanel(QtWidgets.QWidget):
    """Read-only detail card shown below the employee list."""

    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(4)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        def val():
            w = QtWidgets.QLabel("")
            w.setStyleSheet(
                "color: white; font-size: 13px; font-weight: bold;")
            return w

        self.v_name    = val()
        self.v_email   = val()
        self.v_dept    = val()
        self.v_title   = val()
        self.v_role    = val()
        self.v_address = val()

        layout.addWidget(lbl("Name:"),    0, 0)
        layout.addWidget(self.v_name,    0, 1)
        layout.addWidget(lbl("Email:"),   0, 2)
        layout.addWidget(self.v_email,   0, 3)
        layout.addWidget(lbl("Dept:"),    1, 0)
        layout.addWidget(self.v_dept,    1, 1)
        layout.addWidget(lbl("Title:"),   1, 2)
        layout.addWidget(self.v_title,   1, 3)
        layout.addWidget(lbl("Role:"),    2, 0)
        layout.addWidget(self.v_role,    2, 1)
        layout.addWidget(lbl("Address:"), 3, 0)
        layout.addWidget(self.v_address, 3, 1, 1, 3)
        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(3, 2)

    def load(self, people_id):
        conn = get_db()
        rec = conn.execute(
    "SELECT * FROM people WHERE id = %s", (people_id,)).fetchone()
        pos = conn.execute("SELECT job_title FROM position WHERE people_id = %s",  # noqa: E501
                           (people_id,)).fetchone()
        role = conn.execute(
            "SELECT r.role_name FROM user_roles ur JOIN roles r ON r.id = "
            "ur.role_id"
            " WHERE ur.people_id = %s", (people_id,)
        ).fetchone()
        dept = conn.execute(
            "SELECT d.dept_name, ds.dept_sub_name FROM people p"
            " LEFT JOIN dept d ON d.dept_id = p.dept_id"
            " LEFT JOIN dept_sub ds ON ds.dept_sub_id = p.dept_sub_id"
            " WHERE p.id = %s", (people_id,)
        ).fetchone()
        conn.close()
        if not rec:
            self.clear()
            return
        self.v_name.setText(
            f"{rec['first_name'] or ''} {rec['last_name'] or ''}".strip())
        self.v_email.setText(rec["email"] or "")
        dept_str = dept["dept_name"] or "" if dept else ""
        if dept and dept["dept_sub_name"]:
            dept_str += f" / {dept['dept_sub_name']}"
        self.v_dept.setText(dept_str)
        self.v_title.setText(pos["job_title"] if pos else "")
        self.v_role.setText(role["role_name"] if role else "")
        parts = [
    p for p in (
        rec["address"],
        rec["city"],
        rec["state"],
         rec["zip_code"]) if p]
        self.v_address.setText(", ".join(parts))

    def clear(self):
        for w in (self.v_name, self.v_email, self.v_dept,
                  self.v_title, self.v_role, self.v_address):
            w.setText("")


# ── Main Window ─────────────────────────────────────────────────────────

class EmployeesWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._row_ids = []
        self._selected_id = None
        self._build_ui()
        init_db()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # filter row
        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Search:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setStyleSheet(INPUT_STYLE)
        self.search_edit.setPlaceholderText("Name, email, title…")
        self.search_edit.setFixedWidth(200)
        self.search_edit.textChanged.connect(self._refresh)
        fr.addWidget(self.search_edit)

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
        self.dept_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.dept_filter)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.emp_table = QtWidgets.QTableWidget()
        self.emp_table.setColumnCount(7)
        self.emp_table.setHorizontalHeaderLabels(
            ["Emp ID", "First Name", "Last Name", "Email",
                "Department", "Job Title", "Role"]
        )
        hh = self.emp_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    6, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.emp_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.emp_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.emp_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.emp_table.setAlternatingRowColors(True)
        self.emp_table.verticalHeader().setVisible(False)
        self.emp_table.clicked.connect(self._on_row_clicked)
        self.emp_table.doubleClicked.connect(self._on_edit)
        splitter.addWidget(self.emp_table)

        self.detail = EmployeeDetailPanel()
        splitter.addWidget(self.detail)
        splitter.setSizes([480, 120])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Employee",    self._on_new),
            ("Edit Employee",   self._on_edit),
            ("Delete Employee", self._on_delete),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        search = self.search_edit.text().strip().lower()
        dept_id = self.dept_filter.currentData()

        conn = get_db()
        try:
            conds = ["p.id > 0"]
            params = []
            if dept_id:
                conds.append("p.dept_id = %s")
                params.append(dept_id)
            where = " AND ".join(conds)
            rows = conn.execute(f"""
                SELECT p.id, p.employee_id, p.first_name, p.last_name, p.email,
                       d.dept_name, pos.job_title, r.role_name
                FROM people p
                LEFT JOIN dept d ON d.dept_id = p.dept_id
                LEFT JOIN position pos ON pos.people_id = p.id
                LEFT JOIN user_roles ur ON ur.people_id = p.id
                LEFT JOIN roles r ON r.id = ur.role_id
                WHERE {where}
                ORDER BY p.last_name, p.first_name
            """, params or None).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.emp_table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            if search:
                haystack = " ".join([
                    row["first_name"] or "", row["last_name"] or "",
                    row["email"] or "", row["job_title"] or "",
                    row["dept_name"] or "", row["role_name"] or "",
                ]).lower()
                if search not in haystack:
                    continue
            r = self.emp_table.rowCount()
            self.emp_table.insertRow(r)
            self._row_ids.append(row["id"])
            self.emp_table.setItem(r, 0, _ro(str(row["employee_id"] or "")))
            self.emp_table.setItem(r, 1, _ro(row["first_name"] or ""))
            self.emp_table.setItem(r, 2, _ro(row["last_name"] or ""))
            self.emp_table.setItem(r, 3, _ro(row["email"] or ""))
            self.emp_table.setItem(r, 4, _ro(row["dept_name"] or ""))
            self.emp_table.setItem(r, 5, _ro(row["job_title"] or ""))
            self.emp_table.setItem(r, 6, _ro(row["role_name"] or ""))

        self._selected_id = None
        self.detail.clear()

    def _on_show_all(self):
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self.dept_filter.blockSignals(True)
        self.dept_filter.setCurrentIndex(0)
        self.dept_filter.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        self._selected_id = self._row_ids[row]
        self.detail.load(self._selected_id)

    def _on_new(self):
        dlg = EmployeeDialog(parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, _index=None):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an employee first.")
            return
        dlg = EmployeeDialog(people_id=self._selected_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()
            self.detail.load(self._selected_id)

    def _on_delete(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an employee first.")
            return
        conn = get_db()
        rec = conn.execute(
            "SELECT first_name, last_name FROM people WHERE id = %s",
            (self._selected_id,)
        ).fetchone()
        conn.close()
        name = f"{
    rec['first_name'] or ''} {
        rec['last_name'] or ''}".strip() if rec else "this employee"
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{name}'? This cannot be undone.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute(
    "DELETE FROM user_roles WHERE people_id = %s", (self._selected_id,))
            conn.execute(
    "DELETE FROM position WHERE people_id = %s", (self._selected_id,))
            conn.execute(
    "DELETE FROM passwd WHERE people_id = %s", (self._selected_id,))
            conn.execute("DELETE FROM people WHERE id = %s",
                         (self._selected_id,))
            conn.commit()
            conn.close()
            self._selected_id = None
            self._refresh()


class EmployeesWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Employees")
        self.resize(1020, 680)
        _apply_blue_palette(self)
        self.setCentralWidget(EmployeesWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = EmployeesWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
