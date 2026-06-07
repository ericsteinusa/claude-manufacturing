import sys
from .db_pg import get_db
from PyQt6 import QtGui, QtWidgets

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


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dept (
            dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_name TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dept_sub (
            dept_sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_sub_name TEXT NOT NULL
        )
    """)
    for col in ("emp_id INTEGER",
                "dept_id INTEGER REFERENCES dept(dept_id)",
                "dept_Sub_id INTEGER REFERENCES dept_sub(dept_sub_id)"):
        conn.execute(f"ALTER TABLE people ADD COLUMN IF NOT EXISTS {col}")
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


class PersonnelCRM(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Personnel CRM")
        self.resize(1300, 720)
        _apply_blue_palette(self)
        self._selected_row_id = None
        self._row_ids = []
        self._build_ui()
        self._load_depts()
        self._refresh_table()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── Table ──────────────────────────────────────────────────────────
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "First Name", "Last Name", "Emp ID",
            "Address", "City", "State", "Zip", "Email",
            "Department", "Dept Sub",
        ])
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.clicked.connect(self._on_row_clicked)
        layout.addWidget(self.table, stretch=1)

        # ── Search bar ─────────────────────────────────────────────────────
        search_row = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel("Search by last name:")
        lbl.setStyleSheet(LABEL_STYLE)
        search_row.addWidget(lbl)
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setStyleSheet(INPUT_STYLE)
        self.search_input.setFixedWidth(220)
        self.search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self.search_input)

        for text, slot in (("Search", self._on_search),
                           ("Show All", self._on_show_all)):
            btn = QtWidgets.QPushButton(text)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.setFixedHeight(30)
            btn.clicked.connect(slot)
            search_row.addWidget(btn)
        search_row.addStretch()
        layout.addLayout(search_row)

        # ── Entry form ─────────────────────────────────────────────────────
        form_group = QtWidgets.QGroupBox("Employee Record")
        form_group.setStyleSheet(
            "QGroupBox{color: white; font-weight: bold;"
            " border: 1px solid white; margin-top: 8px;}"
            "QGroupBox::title{subcontrol-origin: margin; left: 10px;}"
        )
        fg = QtWidgets.QGridLayout(form_group)
        fg.setSpacing(6)

        def lbl2(text):
            w = QtWidgets.QLabel(text)
            w.setStyleSheet(LABEL_STYLE)
            return w

        def inp(ph=""):
            w = QtWidgets.QLineEdit()
            w.setStyleSheet(INPUT_STYLE)
            if ph:
                w.setPlaceholderText(ph)
            return w

        self.fn_input    = inp("First name")
        self.ln_input    = inp("Last name")
        self.empid_input = inp("Numbers only")
        self.addr_input  = inp("Street address")
        self.city_input  = inp("City")
        self.state_input = inp("ST")
        self.state_input.setMaxLength(2)
        self.state_input.setFixedWidth(44)
        self.zip_input   = inp("Zip")
        self.zip_input.setFixedWidth(90)
        self.email_input = inp("Email address")

        self.dept_combo = QtWidgets.QComboBox()
        self.dept_combo.setStyleSheet(COMBO_STYLE)
        self.dept_combo.setMinimumWidth(160)
        self.dept_combo.currentIndexChanged.connect(self._on_dept_changed)

        self.dept_sub_combo = QtWidgets.QComboBox()
        self.dept_sub_combo.setStyleSheet(COMBO_STYLE)
        self.dept_sub_combo.setMinimumWidth(160)

        # Row 0: name / emp id / email
        fg.addWidget(lbl2("First Name:"),  0, 0)
        fg.addWidget(self.fn_input,         0, 1)
        fg.addWidget(lbl2("Last Name:"),   0, 2)
        fg.addWidget(self.ln_input,         0, 3)
        fg.addWidget(lbl2("Emp ID:"),      0, 4)
        fg.addWidget(self.empid_input,      0, 5)
        fg.addWidget(lbl2("Email:"),        0, 6)
        fg.addWidget(self.email_input,      0, 7)

        # Row 1: address / city / state
        fg.addWidget(lbl2("Address:"),      1, 0)
        fg.addWidget(self.addr_input,       1, 1, 1, 3)
        fg.addWidget(lbl2("City:"),         1, 4)
        fg.addWidget(self.city_input,       1, 5)
        fg.addWidget(lbl2("State:"),        1, 6)
        fg.addWidget(self.state_input,      1, 7)

        # Row 2: zip / dept / dept sub
        fg.addWidget(lbl2("Zip:"),          2, 0)
        fg.addWidget(self.zip_input,        2, 1)
        fg.addWidget(lbl2("Department:"),   2, 2)
        fg.addWidget(self.dept_combo,       2, 3)
        fg.addWidget(lbl2("Dept Sub:"),     2, 4)
        fg.addWidget(self.dept_sub_combo,   2, 5)

        layout.addWidget(form_group)

        # ── Action buttons ─────────────────────────────────────────────────
        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add New",        self._on_add),
            ("Update Selected", self._on_update),
            ("Delete Selected", self._on_delete),
            ("Clear Form",     self._clear_form),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(34)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ── Department helpers ─────────────────────────────────────────────────

    def _load_depts(self):
        conn = get_db()
        depts = conn.execute(
            "SELECT dept_id, dept_name FROM dept ORDER BY dept_name"
        ).fetchall()
        conn.close()
        self.dept_combo.blockSignals(True)
        self.dept_combo.clear()
        self.dept_combo.addItem("(none)", None)
        for row in depts:
            self.dept_combo.addItem(row["dept_name"], row["dept_id"])
        self.dept_combo.blockSignals(False)
        self._populate_dept_sub(None)

    def _on_dept_changed(self):
        self._populate_dept_sub(self.dept_combo.currentData())

    def _populate_dept_sub(self, dept_id):
        conn = get_db()
        subs = conn.execute(
            "SELECT dept_sub_id, dept_sub_name FROM dept_sub ORDER BY "
            "dept_sub_name"
        ).fetchall()
        conn.close()
        self.dept_sub_combo.blockSignals(True)
        self.dept_sub_combo.clear()
        self.dept_sub_combo.addItem("(none)", None)
        for row in subs:
            self.dept_sub_combo.addItem(
    row["dept_sub_name"], row["dept_sub_id"])
        self.dept_sub_combo.blockSignals(False)

    # ── Table data ─────────────────────────────────────────────────────────

    def _refresh_table(self, search_term=None):
        conn = get_db()
        q = """
            SELECT p.id, p.first_name, p.last_name, p.emp_id,
                   p.address, p.city, p.state, p.zip_code, p.email,
                   d.dept_name, ds.dept_sub_name
            FROM people p
            LEFT JOIN dept d    ON d.dept_id     = p.dept_id
            LEFT JOIN dept_sub ds ON ds.dept_sub_id = p.dept_Sub_id
        """
        if search_term:
            rows = conn.execute(
                q + " WHERE p.last_name LIKE ? ORDER BY p.last_name, "
                    "p.first_name",
                (f"%{search_term}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                q + " ORDER BY p.last_name, p.first_name"
            ).fetchall()
        conn.close()

        self.table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._row_ids.append(row["id"])
            for col, val in enumerate([
                row["first_name"], row["last_name"],
                str(row["emp_id"] or ""),
                row["address"] or "", row["city"] or "",
                row["state"] or "", row["zip_code"] or "",
                row["email"] or "",
                row["dept_name"] or "", row["dept_sub_name"] or "",
            ]):
                self.table.setItem(r, col, QtWidgets.QTableWidgetItem(val))

        self._selected_row_id = None

    def _on_search(self):
        term = self.search_input.text().strip()
        self._refresh_table(search_term=term if term else None)

    def _on_show_all(self):
        self.search_input.clear()
        self._refresh_table()

    # ── Row selection → populate form ──────────────────────────────────────

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        self._selected_row_id = self._row_ids[row]
        conn = get_db()
        p = conn.execute("SELECT * FROM people WHERE id = ?",
                         (self._selected_row_id,)).fetchone()
        conn.close()
        if not p:
            return

        keys = p.keys()
        self.fn_input.setText(p["first_name"] or "")
        self.ln_input.setText(p["last_name"] or "")
        self.empid_input.setText(str(p["emp_id"] or ""))
        self.addr_input.setText(p["address"] or "")
        self.city_input.setText(p["city"] or "")
        self.state_input.setText(p["state"] or "")
        self.zip_input.setText(p["zip_code"] or "")
        self.email_input.setText(p["email"] or "")

        dept_id     = p["dept_id"]     if "dept_id"     in keys else None
        dept_sub_id = p["dept_Sub_id"] if "dept_Sub_id" in keys else None

        idx = self.dept_combo.findData(dept_id)
        self.dept_combo.setCurrentIndex(max(0, idx))
        idx2 = self.dept_sub_combo.findData(dept_sub_id)
        self.dept_sub_combo.setCurrentIndex(max(0, idx2))

    # ── Form helpers ───────────────────────────────────────────────────────

    def _collect_form(self):
        emp_id_text = self.empid_input.text().strip()
        if emp_id_text and not emp_id_text.isdigit():
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Employee ID must be a number.")
            return None
        return {
            "first_name":  self.fn_input.text().strip(),
            "last_name":   self.ln_input.text().strip(),
            "emp_id":      int(emp_id_text) if emp_id_text else 0,
            "address":     self.addr_input.text().strip(),
            "city":        self.city_input.text().strip(),
            "state":       self.state_input.text().strip().upper(),
            "zip_code":    self.zip_input.text().strip(),
            "email":       self.email_input.text().strip(),
            "dept_id":     self.dept_combo.currentData(),
            "dept_Sub_id": self.dept_sub_combo.currentData(),
        }

    def _clear_form(self):
        self._selected_row_id = None
        for w in (self.fn_input, self.ln_input, self.empid_input,
                  self.addr_input, self.city_input, self.state_input,
                  self.zip_input, self.email_input):
            w.clear()
        self.dept_combo.setCurrentIndex(0)
        self.dept_sub_combo.setCurrentIndex(0)
        self.table.clearSelection()

    # ── CRUD ───────────────────────────────────────────────────────────────

    def _on_add(self):
        data = self._collect_form()
        if data is None:
            return
        if not data["first_name"] or not data["last_name"]:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "First and last name are required.")
            return
        conn = get_db()
        conn.execute("""
            INSERT INTO people
                (first_name, last_name, emp_id, address, city, state, zip_code,
                    email, dept_id, dept_Sub_id)
            VALUES
                (:first_name, :last_name, :emp_id, :address, :city, :state,
                    :zip_code, :email,
                 :dept_id, :dept_Sub_id)
        """, data)
        conn.commit()
        conn.close()
        self._clear_form()
        self._refresh_table()

    def _on_update(self):
        if self._selected_row_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a row first.")
            return
        data = self._collect_form()
        if data is None:
            return
        data["row_id"] = self._selected_row_id
        conn = get_db()
        conn.execute("""
            UPDATE people SET
                first_name  = :first_name,
                last_name   = :last_name,
                emp_id      = :emp_id,
                address     = :address,
                city        = :city,
                state       = :state,
                zip_code    = :zip_code,
                email       = :email,
                dept_id     = :dept_id,
                dept_Sub_id = :dept_Sub_id
            WHERE id = :row_id
        """, data)
        conn.commit()
        conn.close()
        self._refresh_table()

    def _on_delete(self):
        if self._selected_row_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a row first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete", "Delete this employee record?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM people WHERE id = ?",
                         (self._selected_row_id,))
            conn.commit()
            conn.close()
            self._clear_form()
            self._refresh_table()


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = PersonnelCRM()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
