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
LABEL_STYLE = "color: white; font-size: 13px;"


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dept_sub (
            dept_sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_sub_name TEXT NOT NULL
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


class DeptSubEntry(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Department Sub Entry")
        self.resize(600, 480)
        _apply_blue_palette(self)
        self._selected_id = None
        self._row_ids = []
        self._build_ui()
        self._refresh_table()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Table ──────────────────────────────────────────────────────────
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Sub-Department Name", "ID"])
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
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

        search_lbl = QtWidgets.QLabel("Search by name:")
        search_lbl.setStyleSheet(LABEL_STYLE)
        search_row.addWidget(search_lbl)

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
        form_group = QtWidgets.QGroupBox("Sub-Department Record")
        form_group.setStyleSheet(
            "QGroupBox{color: white; font-weight: bold;"
            " border: 1px solid white; margin-top: 8px;}"
            "QGroupBox::title{subcontrol-origin: margin; left: 10px;}"
        )
        fg = QtWidgets.QHBoxLayout(form_group)
        fg.setSpacing(8)

        name_lbl = QtWidgets.QLabel("Sub-Dept Name:")
        name_lbl.setStyleSheet(LABEL_STYLE)
        fg.addWidget(name_lbl)

        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setStyleSheet(INPUT_STYLE)
        self.name_input.setPlaceholderText("Enter sub-department name")
        self.name_input.returnPressed.connect(self._on_add)
        fg.addWidget(self.name_input, stretch=1)

        layout.addWidget(form_group)

        # ── Buttons ────────────────────────────────────────────────────────
        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add New",         self._on_add),
            ("Update Selected", self._on_update),
            ("Delete Selected", self._on_delete),
            ("Clear",           self._clear_form),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(34)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ── Table ──────────────────────────────────────────────────────────────

    def _refresh_table(self, search_term=None):
        conn = get_db()
        if search_term:
            rows = conn.execute(
                "SELECT dept_sub_id, dept_sub_name FROM dept_sub"
                " WHERE dept_sub_name LIKE ? ORDER BY dept_sub_name",
                (f"%{search_term}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT dept_sub_id, dept_sub_name FROM dept_sub ORDER BY "
                "dept_sub_name"
            ).fetchall()
        conn.close()

        self.table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._row_ids.append(row["dept_sub_id"])
            self.table.setItem(
    r, 0, QtWidgets.QTableWidgetItem(
        row["dept_sub_name"]))
            self.table.setItem(
                r, 1, QtWidgets.QTableWidgetItem(str(row["dept_sub_id"])))

        self._selected_id = None

    def _on_search(self):
        term = self.search_input.text().strip()
        self._refresh_table(search_term=term if term else None)

    def _on_show_all(self):
        self.search_input.clear()
        self._refresh_table()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        self._selected_id = self._row_ids[row]
        conn = get_db()
        rec = conn.execute(
            "SELECT dept_sub_id, dept_sub_name FROM dept_sub WHERE "
            "dept_sub_id = ?",
            (self._selected_id,)
        ).fetchone()
        conn.close()
        if not rec:
            return
        self.name_input.setText(rec["dept_sub_name"])

    def _clear_form(self):
        self._selected_id = None
        self.name_input.clear()
        self.table.clearSelection()

    # ── CRUD ───────────────────────────────────────────────────────────────

    def _on_add(self):
        name = self.name_input.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Sub-department name is required.")
            return
        conn = get_db()
        conn.execute(
    "INSERT INTO dept_sub (dept_sub_name) VALUES (?)", (name,))
        conn.commit()
        conn.close()
        self._clear_form()
        self._refresh_table()

    def _on_update(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a row first.")
            return
        name = self.name_input.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Sub-department name is required.")
            return
        conn = get_db()
        conn.execute(
            "UPDATE dept_sub SET dept_sub_name = ? WHERE dept_sub_id = ?",
            (name, self._selected_id)
        )
        conn.commit()
        conn.close()
        self._refresh_table()

    def _on_delete(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a row first.")
            return
        conn = get_db()
        emp_count = conn.execute(
            "SELECT COUNT(*) FROM people WHERE dept_Sub_id = ?", (self._selected_id,)  # noqa: E501
        ).fetchone()[0]
        conn.close()

        msg = "Delete this sub-department?"
        if emp_count:
            msg += f"\n\nWarning: {emp_count} employee(s) are assigned to it.\nThose links will be cleared."  # noqa: E501

        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute(
                "UPDATE people SET dept_Sub_id = NULL WHERE dept_Sub_id = ?", (
                    self._selected_id,)
            )
            conn.execute(
                "DELETE FROM dept_sub WHERE dept_sub_id = ?", (
                    self._selected_id,)
            )
            conn.commit()
            conn.close()
            self._clear_form()
            self._refresh_table()


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = DeptSubEntry()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
