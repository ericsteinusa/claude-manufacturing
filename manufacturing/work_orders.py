import sys
import psycopg2
from .db_pg import get_db_connection
from .accounts import get_current_user_email
from .work_orders_core import next_wo_number
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

WO_COLORS = {
    "draft":       "#ffffff",
    "open":        "#cce5ff",
    "in_progress": "#fff3cd",
    "completed":   "#d4edda",
    "cancelled":   "#dcdcdc",
}


def get_db():
    return get_db_connection()


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS work_order (
            id SERIAL PRIMARY KEY,
            wo_number TEXT NOT NULL UNIQUE,
            product_id INTEGER,
            description TEXT,
            quantity INTEGER DEFAULT 1,
            start_date TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT,
            created_by TEXT
        )
    """)
    conn.execute("""
        ALTER TABLE work_order
        ADD COLUMN IF NOT EXISTS created_by TEXT
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wo_material (
            id SERIAL PRIMARY KEY,
            wo_id INTEGER NOT NULL REFERENCES work_order(id),
            product_id INTEGER,
            qty_required INTEGER DEFAULT 1,
            qty_issued INTEGER DEFAULT 0,
            notes TEXT
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


def _next_wo_num():
    conn = get_db()
    num = next_wo_number(conn)
    conn.close()
    return num


def _load_products():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, name AS product_name FROM product ORDER BY name"
        ).fetchall()
    except psycopg2.OperationalError:
        rows = []
    conn.close()
    return rows


# ── Dialogs ─────────────────────────────────────────────────────────────

class NewWODialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Work Order")
        self.resize(500, 360)
        _apply_blue_palette(self)
        self.wo_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.wo_num = QtWidgets.QLineEdit(_next_wo_num())
        self.wo_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("WO Number:"), self.wo_num)

        created_by_lbl = QtWidgets.QLabel(
            get_current_user_email() or "(unknown)")
        created_by_lbl.setStyleSheet(LABEL_STYLE)
        layout.addRow(lbl("Created by:"), created_by_lbl)

        self.product_combo = QtWidgets.QComboBox()
        self.product_combo.setStyleSheet(COMBO_STYLE)
        self.product_combo.setMinimumWidth(200)
        self.product_combo.currentIndexChanged.connect(
            self._on_product_changed)
        self.product_combo.addItem("(none)", None)
        for p in _load_products():
            self.product_combo.addItem(p["product_name"], p["id"])
        layout.addRow(lbl("Product:"), self.product_combo)

        self.desc = QtWidgets.QLineEdit()
        self.desc.setStyleSheet(INPUT_STYLE)
        self.desc.setPlaceholderText("Work order description")
        layout.addRow(lbl("Description:"), self.desc)

        self.quantity = QtWidgets.QSpinBox()
        self.quantity.setRange(1, 999999)
        self.quantity.setValue(1)
        self.quantity.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Quantity:"), self.quantity)

        self.start_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        self.start_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Start Date:"), self.start_date)

        self.due_date = QtWidgets.QDateEdit(
    QtCore.QDate.currentDate().addDays(7))
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("draft", "open"):
            self.status_combo.addItem(s.replace("_", " ").capitalize(), s)
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

    def _on_product_changed(self):
        pid = self.product_combo.currentData()
        if pid is not None and not self.desc.text():
            self.desc.setText(self.product_combo.currentText())

    def _on_ok(self):
        wo_num = self.wo_num.text().strip()
        if not wo_num:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "WO number is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO work_order (wo_number, product_id, description, "
                "quantity, start_date, due_date, status, notes, created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (wo_num, self.product_combo.currentData(),
                 self.desc.text().strip(), self.quantity.value(),
                 self.start_date.date().toString("yyyy-MM-dd"),
                 self.due_date.date().toString("yyyy-MM-dd"),
                 self.status_combo.currentData(),
                 self.notes.text().strip(),
                 get_current_user_email() or None)
            )
            self.wo_id = cur.fetchone()['id']
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"WO number '{wo_num}' already exists.")  # noqa: E501
            conn.close()
            return
        conn.close()
        self.accept()


class AddMaterialDialog(QtWidgets.QDialog):
    def __init__(self, wo_id, wo_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Material — {wo_number}")
        self.resize(440, 240)
        _apply_blue_palette(self)
        self._wo_id = wo_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.product_combo = QtWidgets.QComboBox()
        self.product_combo.setStyleSheet(COMBO_STYLE)
        self.product_combo.addItem("(none)", None)
        for p in _load_products():
            self.product_combo.addItem(p["product_name"], p["id"])
        layout.addRow(lbl("Material/Product:"), self.product_combo)

        self.qty_required = QtWidgets.QSpinBox()
        self.qty_required.setRange(1, 999999)
        self.qty_required.setValue(1)
        self.qty_required.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Qty Required:"), self.qty_required)

        self.qty_issued = QtWidgets.QSpinBox()
        self.qty_issued.setRange(0, 999999)
        self.qty_issued.setValue(0)
        self.qty_issued.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Qty Issued:"), self.qty_issued)

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

    def _on_ok(self):
        if self.product_combo.currentData() is None:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Select a material/product.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO wo_material (wo_id, product_id, qty_required, "
            "qty_issued, notes)"
            " VALUES (%s,%s,%s,%s,%s)",
            (self._wo_id, self.product_combo.currentData(),
             self.qty_required.value(), self.qty_issued.value(),
             self.notes.text().strip())
        )
        conn.commit()
        conn.close()
        self.accept()


class UpdateWODialog(QtWidgets.QDialog):
    """Edit product, description, dates, and notes on an existing work order."""  # noqa: E501

    def __init__(self, wo_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Work Order")
        self.resize(420, 300)
        _apply_blue_palette(self)
        self._wo_id = wo_id
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.product_combo = QtWidgets.QComboBox()
        self.product_combo.setStyleSheet(COMBO_STYLE)
        self.product_combo.setMinimumWidth(200)
        self.product_combo.addItem("(none)", None)
        for p in _load_products():
            self.product_combo.addItem(p["product_name"], p["id"])
        layout.addRow(lbl("Product:"), self.product_combo)

        self.desc = QtWidgets.QLineEdit()
        self.desc.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Description:"), self.desc)

        self.quantity = QtWidgets.QSpinBox()
        self.quantity.setRange(1, 999999)
        self.quantity.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Quantity:"), self.quantity)

        self.start_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        self.start_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Start Date:"), self.start_date)

        self.due_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

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
        rec = conn.execute(
    "SELECT * FROM work_order WHERE id = %s",
    (self._wo_id,
    )).fetchone()
        conn.close()
        if not rec:
            return
        for i in range(self.product_combo.count()):
            if self.product_combo.itemData(i) == rec["product_id"]:
                self.product_combo.setCurrentIndex(i)
                break
        self.desc.setText(rec["description"] or "")
        self.quantity.setValue(rec["quantity"] or 1)
        if rec["start_date"]:
            self.start_date.setDate(
    QtCore.QDate.fromString(
        rec["start_date"],
         "yyyy-MM-dd"))
        if rec["due_date"]:
            self.due_date.setDate(
    QtCore.QDate.fromString(
        rec["due_date"], "yyyy-MM-dd"))
        self.notes.setText(rec["notes"] or "")

    def _on_ok(self):
        conn = get_db()
        conn.execute(
            "UPDATE work_order SET product_id=%s, description=%s, quantity=%s,"
            " start_date=%s, due_date=%s, notes=%s WHERE id=%s",
            (self.product_combo.currentData(), self.desc.text().strip(),
             self.quantity.value(),
             self.start_date.date().toString("yyyy-MM-dd"),
             self.due_date.date().toString("yyyy-MM-dd"),
             self.notes.text().strip(), self._wo_id)
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ─────────────────────────────────────────────────────────

class WorkOrdersWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._wo_row_ids = []
        self._selected_wo_id = None
        self._selected_wo_number = None
        self._build_ui()
        init_db()
        self._refresh_orders()

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
        for s in ("draft", "open", "in_progress", "completed", "cancelled"):
            self.status_filter.addItem(s.replace("_", " ").capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh_orders)
        fr.addWidget(self.status_filter)

        fr.addSpacing(10)
        lbl_f = QtWidgets.QLabel("From:")
        lbl_f.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_f)
        self.date_from = QtWidgets.QDateEdit(
            QtCore.QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet(INPUT_STYLE)
        self.date_from.dateChanged.connect(self._refresh_orders)
        fr.addWidget(self.date_from)

        lbl_t = QtWidgets.QLabel("Due by:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.date_to = QtWidgets.QDateEdit(
    QtCore.QDate.currentDate().addMonths(3))
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet(INPUT_STYLE)
        self.date_to.dateChanged.connect(self._refresh_orders)
        fr.addWidget(self.date_to)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.wo_table = QtWidgets.QTableWidget()
        self.wo_table.setColumnCount(9)
        self.wo_table.setHorizontalHeaderLabels(
            ["WO #", "Product", "Description", "Qty",
             "Start Date", "Due Date", "Materials", "Status", "Created By"]
        )
        hh = self.wo_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    6, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    7, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    8, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.wo_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.wo_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.wo_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.wo_table.setAlternatingRowColors(True)
        self.wo_table.verticalHeader().setVisible(False)
        self.wo_table.clicked.connect(self._on_wo_clicked)
        splitter.addWidget(self.wo_table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Materials")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.mat_table = QtWidgets.QTableWidget()
        self.mat_table.setColumnCount(4)
        self.mat_table.setHorizontalHeaderLabels(
            ["Material / Product", "Qty Required", "Qty Issued", "Notes"]
        )
        ih = self.mat_table.horizontalHeader()
        ih.setStyleSheet("color: black; font-weight: bold;")
        ih.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        ih.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.mat_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mat_table.verticalHeader().setVisible(False)
        self.mat_table.setAlternatingRowColors(True)
        dv.addWidget(self.mat_table)
        splitter.addWidget(detail_w)
        splitter.setSizes([400, 180])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New WO",          self._on_new_wo),
            ("Add Material",    self._on_add_material),
            ("Update WO",       self._on_update_wo),
            ("Open",            lambda: self._set_status(
                "open",        "Open this work order?")),
            ("Start",           lambda: self._set_status(
                "in_progress", "Mark as In Progress?")),
            ("Complete",        lambda: self._set_status(
                "completed",   "Mark as Completed?")),
            ("Cancel",          lambda: self._set_status(
                "cancelled",   "Cancel this work order?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh_orders(self):
        status = self.status_filter.currentData()
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")

        base = """
            SELECT wo.id, wo.wo_number, wo.description, wo.quantity,
                   wo.start_date, wo.due_date, wo.status, wo.created_by,
                   p.name AS product_name,
                   (SELECT COUNT(*) FROM wo_material m WHERE m.wo_id = wo.id)
                       AS mat_count
            FROM work_order wo
            LEFT JOIN product p ON p.id = wo.product_id
        """
        conds, params = [], []
        if status:
            conds.append("wo.status = %s")
            params.append(status)
        conds.append("(wo.due_date IS NULL OR wo.due_date BETWEEN %s AND %s)")
        params += [d_from, d_to]
        where = " WHERE " + " AND ".join(conds)

        conn = get_db()
        try:
            rows = conn.execute(
    base + where + " ORDER BY wo.due_date ASC",
     params).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.wo_table.setRowCount(0)
        self._wo_row_ids = []
        for row in rows:
            r = self.wo_table.rowCount()
            self.wo_table.insertRow(r)
            self._wo_row_ids.append(row["id"])
            self.wo_table.setItem(r, 0, _ro(row["wo_number"]))
            self.wo_table.setItem(r, 1, _ro(row["product_name"] or ""))
            self.wo_table.setItem(r, 2, _ro(row["description"] or ""))
            self.wo_table.setItem(r, 3, _ro(str(row["quantity"])))
            self.wo_table.setItem(r, 4, _ro(row["start_date"] or ""))
            self.wo_table.setItem(r, 5, _ro(row["due_date"] or ""))
            self.wo_table.setItem(r, 6, _ro(str(row["mat_count"])))
            status_val = row["status"]
            self.wo_table.setItem(
    r, 7, _ro(
        status_val.replace(
            "_", " ").capitalize()))
            self.wo_table.setItem(r, 8, _ro(row["created_by"] or ""))
            bg = QtGui.QColor(WO_COLORS.get(status_val, "#ffffff"))
            for col in range(9):
                self.wo_table.item(r, col).setBackground(bg)

        self._selected_wo_id = None
        self._selected_wo_number = None
        self.mat_table.setRowCount(0)

    def _on_show_all(self):
        self.status_filter.blockSignals(True)
        self.status_filter.setCurrentIndex(0)
        self.status_filter.blockSignals(False)
        self.date_from.blockSignals(True)
        self.date_from.setDate(QtCore.QDate(2000, 1, 1))
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(True)
        self.date_to.setDate(QtCore.QDate(2099, 12, 31))
        self.date_to.blockSignals(False)
        self._refresh_orders()

    def _on_wo_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._wo_row_ids):
            return
        self._selected_wo_id = self._wo_row_ids[row]
        self._selected_wo_number = self.wo_table.item(row, 0).text()
        self._refresh_materials()

    def _refresh_materials(self):
        self.mat_table.setRowCount(0)
        if self._selected_wo_id is None:
            return
        conn = get_db()
        try:
            mats = conn.execute("""
                SELECT p.name AS product_name, m.qty_required, m.qty_issued,
                    m.notes
                FROM wo_material m LEFT JOIN product p ON p.id = m.product_id
                WHERE m.wo_id = %s
            """, (self._selected_wo_id,)).fetchall()
        except psycopg2.OperationalError:
            mats = []
        conn.close()
        for mat in mats:
            r = self.mat_table.rowCount()
            self.mat_table.insertRow(r)
            self.mat_table.setItem(r, 0, _ro(mat["product_name"] or ""))
            self.mat_table.setItem(r, 1, _ro(str(mat["qty_required"])))
            self.mat_table.setItem(r, 2, _ro(str(mat["qty_issued"])))
            self.mat_table.setItem(r, 3, _ro(mat["notes"] or ""))

    def _on_new_wo(self):
        dlg = NewWODialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_orders()

    def _on_add_material(self):
        if self._selected_wo_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a work order first.")
            return
        dlg = AddMaterialDialog(
    self._selected_wo_id,
    self._selected_wo_number,
     self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_orders()
            self._refresh_materials()

    def _on_update_wo(self):
        if self._selected_wo_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a work order first.")
            return
        dlg = UpdateWODialog(self._selected_wo_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_orders()

    def _set_status(self, new_status, msg):
        if self._selected_wo_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a work order first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE work_order SET status = %s WHERE id = %s",
                         (new_status, self._selected_wo_id))
            conn.commit()
            conn.close()
            self._refresh_orders()


class WorkOrdersWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = f"Work Orders — {email}" if email else "Work Orders"
        self.setWindowTitle(title)
        self.resize(1020, 680)
        _apply_blue_palette(self)
        self.setCentralWidget(WorkOrdersWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = WorkOrdersWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
