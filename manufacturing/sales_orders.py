import sys
import psycopg2
from .db_pg import get_db_connection
from .accounts import get_current_user_email
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

SO_COLORS = {
    "draft":     "#ffffff",
    "confirmed": "#cce5ff",
    "shipped":   "#fff3cd",
    "invoiced":  "#d4edda",
    "cancelled": "#dcdcdc",
}


def get_db():
    return get_db_connection()


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_order (
            id SERIAL PRIMARY KEY,
            so_number TEXT NOT NULL UNIQUE,
            customer_id INTEGER,
            order_date TEXT,
            ship_date TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT,
            created_by TEXT
        )
    """)
    conn.execute("""
        ALTER TABLE sales_order
        ADD COLUMN IF NOT EXISTS created_by TEXT
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS so_item (
            id SERIAL PRIMARY KEY,
            so_id INTEGER NOT NULL REFERENCES sales_order(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty INTEGER DEFAULT 1,
            unit_price REAL DEFAULT 0.0
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


def _next_so_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM sales_order WHERE so_number LIKE %s", (
            f"SO-{yr}-%",)
    ).fetchone()[0]
    conn.close()
    return f"SO-{yr}-{count + 1:04d}"


def _load_customers():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, company_name, first_name, last_name FROM customer "
            "ORDER BY company_name"
        ).fetchall()
    except psycopg2.OperationalError:
        rows = []
    conn.close()
    return rows


def _customer_label(row):
    company = row["company_name"] or ""
    name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    return company if company else name


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

class NewSODialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Sales Order")
        self.resize(500, 320)
        _apply_blue_palette(self)
        self.so_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.so_num = QtWidgets.QLineEdit(_next_so_num())
        self.so_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("SO Number:"), self.so_num)

        created_by_lbl = QtWidgets.QLabel(
            get_current_user_email() or "(unknown)")
        created_by_lbl.setStyleSheet(LABEL_STYLE)
        layout.addRow(lbl("Created by:"), created_by_lbl)

        self.customer_combo = QtWidgets.QComboBox()
        self.customer_combo.setStyleSheet(COMBO_STYLE)
        self.customer_combo.setMinimumWidth(200)
        self.customer_combo.addItem("(none)", None)
        for c in _load_customers():
            self.customer_combo.addItem(_customer_label(c), c["id"])
        layout.addRow(lbl("Customer:"), self.customer_combo)

        self.order_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.order_date.setCalendarPopup(True)
        self.order_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Order Date:"), self.order_date)

        self.ship_date = QtWidgets.QDateEdit(
    QtCore.QDate.currentDate().addDays(7))
        self.ship_date.setCalendarPopup(True)
        self.ship_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Ship Date:"), self.ship_date)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("draft", "confirmed"):
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

    def _on_ok(self):
        so_num = self.so_num.text().strip()
        if not so_num:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "SO number is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO sales_order (so_number, customer_id, order_date,"
                " ship_date, status, notes, created_by)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (so_num, self.customer_combo.currentData(),
                 self.order_date.date().toString("yyyy-MM-dd"),
                 self.ship_date.date().toString("yyyy-MM-dd"),
                 self.status_combo.currentData(),
                 self.notes.text().strip(),
                 get_current_user_email() or None)
            )
            self.so_id = cur.fetchone()['id']
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"SO number '{so_num}' already exists.")  # noqa: E501
            conn.close()
            return
        conn.close()
        self.accept()


class AddSOItemDialog(QtWidgets.QDialog):
    def __init__(self, so_id, so_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Item — {so_number}")
        self.resize(460, 250)
        _apply_blue_palette(self)
        self._so_id = so_id
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
        self.product_combo.currentIndexChanged.connect(
            self._on_product_changed)
        self.product_combo.addItem("(none)", None)
        for p in _load_products():
            self.product_combo.addItem(p["product_name"], p["id"])
        layout.addRow(lbl("Product (opt):"), self.product_combo)

        self.desc = QtWidgets.QLineEdit()
        self.desc.setStyleSheet(INPUT_STYLE)
        self.desc.setPlaceholderText("Description (required)")
        layout.addRow(lbl("Description:"), self.desc)

        self.qty = QtWidgets.QSpinBox()
        self.qty.setRange(1, 999999)
        self.qty.setValue(1)
        self.qty.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Quantity:"), self.qty)

        self.unit_price = QtWidgets.QDoubleSpinBox()
        self.unit_price.setRange(0.0, 9999999.99)
        self.unit_price.setDecimals(2)
        self.unit_price.setPrefix("$ ")
        self.unit_price.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Unit Price:"), self.unit_price)

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
        desc = self.desc.text().strip()
        if not desc:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Description is required.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO so_item (so_id, description, product_id, qty, "
            "unit_price)"
            " VALUES (%s,%s,%s,%s,%s)",
            (self._so_id, desc, self.product_combo.currentData(),
             self.qty.value(), self.unit_price.value())
        )
        conn.commit()
        conn.close()
        self.accept()


class UpdateSODialog(QtWidgets.QDialog):
    """Edit customer, dates, and notes on an existing sales order."""

    def __init__(self, so_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Sales Order")
        self.resize(420, 260)
        _apply_blue_palette(self)
        self._so_id = so_id
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.customer_combo = QtWidgets.QComboBox()
        self.customer_combo.setStyleSheet(COMBO_STYLE)
        self.customer_combo.setMinimumWidth(200)
        self.customer_combo.addItem("(none)", None)
        for c in _load_customers():
            self.customer_combo.addItem(_customer_label(c), c["id"])
        layout.addRow(lbl("Customer:"), self.customer_combo)

        self.order_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.order_date.setCalendarPopup(True)
        self.order_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Order Date:"), self.order_date)

        self.ship_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.ship_date.setCalendarPopup(True)
        self.ship_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Ship Date:"), self.ship_date)

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
    "SELECT * FROM sales_order WHERE id = %s",
    (self._so_id,
    )).fetchone()
        conn.close()
        if not rec:
            return
        for i in range(self.customer_combo.count()):
            if self.customer_combo.itemData(i) == rec["customer_id"]:
                self.customer_combo.setCurrentIndex(i)
                break
        if rec["order_date"]:
            self.order_date.setDate(
    QtCore.QDate.fromString(
        rec["order_date"],
         "yyyy-MM-dd"))
        if rec["ship_date"]:
            self.ship_date.setDate(
    QtCore.QDate.fromString(
        rec["ship_date"], "yyyy-MM-dd"))
        self.notes.setText(rec["notes"] or "")

    def _on_ok(self):
        conn = get_db()
        conn.execute(
            "UPDATE sales_order SET customer_id=%s, order_date=%s, "
            "ship_date=%s, notes=%s"
            " WHERE id=%s",
            (self.customer_combo.currentData(),
             self.order_date.date().toString("yyyy-MM-dd"),
             self.ship_date.date().toString("yyyy-MM-dd"),
             self.notes.text().strip(), self._so_id)
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ─────────────────────────────────────────────────────────

class SalesOrdersWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._so_row_ids = []
        self._selected_so_id = None
        self._selected_so_number = None
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
        for s in ("draft", "confirmed", "shipped", "invoiced", "cancelled"):
            self.status_filter.addItem(s.capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh_orders)
        fr.addWidget(self.status_filter)

        fr.addSpacing(10)
        lbl_c = QtWidgets.QLabel("Customer:")
        lbl_c.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_c)
        self.customer_filter = QtWidgets.QComboBox()
        self.customer_filter.setStyleSheet(COMBO_STYLE)
        self.customer_filter.setMinimumWidth(140)
        self.customer_filter.addItem("(all)", None)
        for c in _load_customers():
            self.customer_filter.addItem(_customer_label(c), c["id"])
        self.customer_filter.currentIndexChanged.connect(self._refresh_orders)
        fr.addWidget(self.customer_filter)

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

        lbl_t = QtWidgets.QLabel("To:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.date_to = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
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

        self.so_table = QtWidgets.QTableWidget()
        self.so_table.setColumnCount(9)
        self.so_table.setHorizontalHeaderLabels(
            ["SO #", "Customer", "Order Date", "Ship Date",
             "Items", "Total", "Status", "Notes", "Created By"]
        )
        hh = self.so_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
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
        hh.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    8, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.so_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.so_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.so_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.so_table.setAlternatingRowColors(True)
        self.so_table.verticalHeader().setVisible(False)
        self.so_table.clicked.connect(self._on_order_clicked)
        splitter.addWidget(self.so_table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Line Items")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.item_table = QtWidgets.QTableWidget()
        self.item_table.setColumnCount(4)
        self.item_table.setHorizontalHeaderLabels(
            ["Description", "Product", "Qty", "Unit Price"])
        ih = self.item_table.horizontalHeader()
        ih.setStyleSheet("color: black; font-weight: bold;")
        ih.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        ih.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.item_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.item_table.verticalHeader().setVisible(False)
        self.item_table.setAlternatingRowColors(True)
        dv.addWidget(self.item_table)
        splitter.addWidget(detail_w)
        splitter.setSizes([400, 180])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Order",      self._on_new_order),
            ("Add Item",       self._on_add_item),
            ("Update Order",   self._on_update_order),
            ("Confirm",        lambda: self._set_status(
                "confirmed",  "Confirm this order?")),
            ("Mark Shipped",   lambda: self._set_status(
                "shipped",    "Mark as Shipped?")),
            ("Mark Invoiced",  lambda: self._set_status(
                "invoiced",   "Mark as Invoiced?")),
            ("Cancel",         lambda: self._set_status(
                "cancelled",  "Cancel this order?")),
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
        customer_id = self.customer_filter.currentData()
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")

        base = """
            SELECT so.id, so.so_number, so.order_date, so.ship_date,
                   so.status, so.notes, so.created_by,
                   c.company_name, c.first_name, c.last_name,
                   (SELECT COUNT(*) FROM so_item si WHERE si.so_id = so.id) AS
                       item_count,
                   (SELECT COALESCE(SUM(si.qty * si.unit_price), 0)
                    FROM so_item si WHERE si.so_id = so.id) AS total
            FROM sales_order so
            LEFT JOIN customer c ON c.id = so.customer_id
        """
        conds, params = [], []
        if status:
            conds.append("so.status = %s")
            params.append(status)
        if customer_id:
            conds.append("so.customer_id = %s")
            params.append(customer_id)
        conds.append(
            "(so.order_date IS NULL OR so.order_date BETWEEN %s AND %s)")
        params += [d_from, d_to]
        where = " WHERE " + " AND ".join(conds)

        conn = get_db()
        try:
            rows = conn.execute(
    base + where + " ORDER BY so.order_date DESC",
     params).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.so_table.setRowCount(0)
        self._so_row_ids = []
        for row in rows:
            r = self.so_table.rowCount()
            self.so_table.insertRow(r)
            self._so_row_ids.append(row["id"])
            company = row["company_name"] or ""
            name = f"{
    row['first_name'] or ''} {
        row['last_name'] or ''}".strip()
            customer_display = company if company else name
            self.so_table.setItem(r, 0, _ro(row["so_number"]))
            self.so_table.setItem(r, 1, _ro(customer_display))
            self.so_table.setItem(r, 2, _ro(row["order_date"] or ""))
            self.so_table.setItem(r, 3, _ro(row["ship_date"] or ""))
            self.so_table.setItem(r, 4, _ro(str(row["item_count"])))
            self.so_table.setItem(r, 5, _ro(f"${row['total']:,.2f}"))
            self.so_table.setItem(r, 6, _ro(row["status"].capitalize()))
            self.so_table.setItem(r, 7, _ro(row["notes"] or ""))
            self.so_table.setItem(r, 8, _ro(row["created_by"] or ""))
            bg = QtGui.QColor(SO_COLORS.get(row["status"], "#ffffff"))
            for col in range(9):
                self.so_table.item(r, col).setBackground(bg)

        self._selected_so_id = None
        self._selected_so_number = None
        self.item_table.setRowCount(0)

    def _on_show_all(self):
        for widget in (self.status_filter, self.customer_filter):
            widget.blockSignals(True)
            widget.setCurrentIndex(0)
            widget.blockSignals(False)
        self.date_from.blockSignals(True)
        self.date_from.setDate(QtCore.QDate(2000, 1, 1))
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(True)
        self.date_to.setDate(QtCore.QDate.currentDate())
        self.date_to.blockSignals(False)
        self._refresh_orders()

    def _on_order_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._so_row_ids):
            return
        self._selected_so_id = self._so_row_ids[row]
        self._selected_so_number = self.so_table.item(row, 0).text()
        self._refresh_items()

    def _refresh_items(self):
        self.item_table.setRowCount(0)
        if self._selected_so_id is None:
            return
        conn = get_db()
        try:
            items = conn.execute("""
                SELECT si.description, p.name AS product_name,
                       si.qty, si.unit_price
                FROM so_item si LEFT JOIN product p ON p.id = si.product_id
                WHERE si.so_id = %s
            """, (self._selected_so_id,)).fetchall()
        except psycopg2.OperationalError:
            items = []
        conn.close()
        for item in items:
            r = self.item_table.rowCount()
            self.item_table.insertRow(r)
            self.item_table.setItem(r, 0, _ro(item["description"]))
            self.item_table.setItem(r, 1, _ro(item["product_name"] or ""))
            self.item_table.setItem(r, 2, _ro(str(item["qty"])))
            self.item_table.setItem(r, 3, _ro(f"${item['unit_price']:,.2f}"))

    def _on_new_order(self):
        dlg = NewSODialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_orders()

    def _on_add_item(self):
        if self._selected_so_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an order first.")
            return
        dlg = AddSOItemDialog(
    self._selected_so_id,
    self._selected_so_number,
     self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_orders()
            self._refresh_items()

    def _on_update_order(self):
        if self._selected_so_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an order first.")
            return
        dlg = UpdateSODialog(self._selected_so_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_orders()

    def _set_status(self, new_status, msg):
        if self._selected_so_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an order first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE sales_order SET status = %s WHERE id = %s",
                         (new_status, self._selected_so_id))
            conn.commit()
            conn.close()
            self._refresh_orders()


class SalesOrdersWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = f"Sales Orders — {email}" if email else "Sales Orders"
        self.setWindowTitle(title)
        self.resize(1020, 680)
        _apply_blue_palette(self)
        self.setCentralWidget(SalesOrdersWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = SalesOrdersWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
