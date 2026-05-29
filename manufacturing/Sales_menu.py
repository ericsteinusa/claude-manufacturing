import sys
import psycopg2
from .db_pg import get_db
from PyQt6 import QtCore, QtGui, QtWidgets

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE = "QLineEdit{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 6px;}"
COMBO_STYLE = (
    "QComboBox{background-color: white; border: 2px solid black; border-radius: 4px; padding: 2px 6px;}"
    "QComboBox QAbstractItemView{background-color: white;}"
)
LABEL_STYLE = "color: white; font-size: 13px;"
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)

SO_COLORS = {
    "quote":      "#ffffff",
    "order":      "#e8f4fd",
    "processing": "#fff3cd",
    "shipped":    "#d4edda",
    "invoiced":   "#d1ecf1",
    "cancelled":  "#dcdcdc",
}


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT, last_name TEXT, company_name TEXT,
            phone_number TEXT, address TEXT, city TEXT, state TEXT,
            zip_code TEXT, email TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            so_number TEXT NOT NULL UNIQUE,
            customer_id INTEGER REFERENCES customer(id),
            order_date TEXT,
            ship_date TEXT,
            status TEXT DEFAULT 'quote',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS so_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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


def _customer_display(row):
    if row["company_name"]:
        return row["company_name"]
    return f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()


def _next_so_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM sales_order WHERE so_number LIKE ?", (f"SO-{yr}-%",)
    ).fetchone()[0]
    conn.close()
    return f"SO-{yr}-{count + 1:04d}"


# ── Dialogs ────────────────────────────────────────────────────────────────────

class NewOrderDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Sales Order / Quote")
        self.resize(480, 290)
        _apply_blue_palette(self)
        self.so_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.so_num = QtWidgets.QLineEdit(_next_so_num())
        self.so_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("SO Number:"), self.so_num)

        self.customer_combo = QtWidgets.QComboBox()
        self.customer_combo.setStyleSheet(COMBO_STYLE)
        conn = get_db()
        rows = conn.execute("SELECT * FROM customer ORDER BY company_name, last_name").fetchall()
        conn.close()
        self.customer_combo.addItem("(none)", None)
        for r in rows:
            self.customer_combo.addItem(_customer_display(r), r["id"])
        layout.addRow(lbl("Customer:"), self.customer_combo)

        self.order_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.order_date.setCalendarPopup(True)
        self.order_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Order Date:"), self.order_date)

        self.ship_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addDays(14))
        self.ship_date.setCalendarPopup(True)
        self.ship_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Est. Ship Date:"), self.ship_date)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("quote", "order"):
            self.status_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        self.notes.setPlaceholderText("Optional notes")
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
            QtWidgets.QMessageBox.warning(self, "Input Error", "SO number is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO sales_order (so_number, customer_id, order_date, ship_date, status, notes)"
                " VALUES (?,?,?,?,?,?)",
                (so_num, self.customer_combo.currentData(),
                 self.order_date.date().toString("yyyy-MM-dd"),
                 self.ship_date.date().toString("yyyy-MM-dd"),
                 self.status_combo.currentData(),
                 self.notes.text().strip())
            )
            self.so_id = cur.lastrowid
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate", f"SO number '{so_num}' already exists.")
            conn.close()
            return
        conn.close()
        self.accept()


class AddSOLineItemDialog(QtWidgets.QDialog):
    def __init__(self, so_id, so_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Line Item — {so_number}")
        self.resize(440, 230)
        _apply_blue_palette(self)
        self._so_id = so_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.product_combo = QtWidgets.QComboBox()
        self.product_combo.setStyleSheet(COMBO_STYLE)
        self.product_combo.currentIndexChanged.connect(self._on_product_changed)
        conn = get_db()
        try:
            prods = conn.execute(
                "SELECT id, name AS product_name, purchase_price FROM product ORDER BY name"
            ).fetchall()
        except psycopg2.OperationalError:
            prods = []
        conn.close()
        self.product_combo.addItem("(none)", None)
        for p in prods:
            self.product_combo.addItem(p["product_name"], {"id": p["id"], "price": p["purchase_price"] or 0.0})
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

        self.price = QtWidgets.QDoubleSpinBox()
        self.price.setRange(0.0, 9999999.99)
        self.price.setDecimals(2)
        self.price.setPrefix("$")
        self.price.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Unit Price:"), self.price)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_product_changed(self):
        data = self.product_combo.currentData()
        if data and isinstance(data, dict):
            if not self.desc.text():
                self.desc.setText(self.product_combo.currentText())
            self.price.setValue(data["price"])

    def _on_ok(self):
        desc = self.desc.text().strip()
        if not desc:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Description is required.")
            return
        data = self.product_combo.currentData()
        product_id = data["id"] if data and isinstance(data, dict) else None
        conn = get_db()
        conn.execute(
            "INSERT INTO so_item (so_id, description, product_id, qty, unit_price) VALUES (?,?,?,?,?)",
            (self._so_id, desc, product_id, self.qty.value(), self.price.value())
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Embeddable Widget ──────────────────────────────────────────────────────────

class SalesOrdersWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._ord_row_ids = []
        self._selected_so_id = None
        self._selected_so_number = None
        self._cust_row_ids = []
        self._selected_cust_id = None
        self._build_ui()
        init_db()
        self._load_ord_customer_filter()
        self._refresh_orders()
        self._refresh_customers()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setStyleSheet(TAB_STYLE)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        v.addWidget(self._tabs)
        self._build_orders_tab()
        self._build_customers_tab()

    def _on_tab_changed(self, index):
        if index == 0:
            self._load_ord_customer_filter()
            self._refresh_orders()
        elif index == 1:
            self._refresh_customers()

    # ── Orders tab ─────────────────────────────────────────────────────────

    def _build_orders_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_c = QtWidgets.QLabel("Customer:")
        lbl_c.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_c)
        self.ord_cust_filter = QtWidgets.QComboBox()
        self.ord_cust_filter.setStyleSheet(COMBO_STYLE)
        self.ord_cust_filter.setMinimumWidth(160)
        self.ord_cust_filter.currentIndexChanged.connect(self._refresh_orders)
        fr.addWidget(self.ord_cust_filter)
        fr.addSpacing(10)
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.ord_status_filter = QtWidgets.QComboBox()
        self.ord_status_filter.setStyleSheet(COMBO_STYLE)
        self.ord_status_filter.addItem("(all)", None)
        for s in ("quote", "order", "processing", "shipped", "invoiced", "cancelled"):
            self.ord_status_filter.addItem(s.capitalize(), s)
        self.ord_status_filter.currentIndexChanged.connect(self._refresh_orders)
        fr.addWidget(self.ord_status_filter)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.ord_table = QtWidgets.QTableWidget()
        self.ord_table.setColumnCount(6)
        self.ord_table.setHorizontalHeaderLabels(["SO #", "Customer", "Order Date", "Ship Date", "Total", "Status"])
        hh = self.ord_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5):
            hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.ord_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ord_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ord_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.ord_table.setAlternatingRowColors(True)
        self.ord_table.verticalHeader().setVisible(False)
        self.ord_table.clicked.connect(self._on_order_clicked)
        splitter.addWidget(self.ord_table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Line Items")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.item_table = QtWidgets.QTableWidget()
        self.item_table.setColumnCount(5)
        self.item_table.setHorizontalHeaderLabels(["Description", "Product", "Qty", "Unit Price", "Line Total"])
        ih = self.item_table.horizontalHeader()
        ih.setStyleSheet("color: black; font-weight: bold;")
        ih.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            ih.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.item_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.item_table.verticalHeader().setVisible(False)
        self.item_table.setAlternatingRowColors(True)
        dv.addWidget(self.item_table)
        splitter.addWidget(detail_w)
        splitter.setSizes([360, 200])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Order",       self._on_new_order),
            ("Add Line Item",   self._on_add_line_item),
            ("Mark as Order",   lambda: self._set_status("order",      "Mark this as a confirmed order?")),
            ("Mark Processing", lambda: self._set_status("processing", "Mark as in processing?")),
            ("Mark Shipped",    lambda: self._set_status("shipped",    "Mark as shipped?")),
            ("Cancel Order",    lambda: self._set_status("cancelled",  "Cancel this order?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Sales Orders")

    def _load_ord_customer_filter(self):
        conn = get_db()
        rows = conn.execute(
            "SELECT id, first_name, last_name, company_name FROM customer ORDER BY company_name, last_name"
        ).fetchall()
        conn.close()
        saved = self.ord_cust_filter.currentData()
        self.ord_cust_filter.blockSignals(True)
        self.ord_cust_filter.clear()
        self.ord_cust_filter.addItem("(all)", None)
        for r in rows:
            self.ord_cust_filter.addItem(_customer_display(r), r["id"])
        if saved is not None:
            idx = self.ord_cust_filter.findData(saved)
            if idx >= 0:
                self.ord_cust_filter.setCurrentIndex(idx)
        self.ord_cust_filter.blockSignals(False)

    def _refresh_orders(self):
        cust_id = self.ord_cust_filter.currentData()
        status  = self.ord_status_filter.currentData()
        base = """
            SELECT so.id, so.so_number, so.order_date, so.ship_date, so.status,
                   c.first_name, c.last_name, c.company_name,
                   COALESCE(SUM(i.qty * i.unit_price), 0.0) AS total
            FROM sales_order so
            LEFT JOIN customer c ON c.id = so.customer_id
            LEFT JOIN so_item i ON i.so_id = so.id
        """
        conds, params = [], []
        if cust_id:
            conds.append("so.customer_id = ?")
            params.append(cust_id)
        if status:
            conds.append("so.status = ?")
            params.append(status)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        conn = get_db()
        rows = conn.execute(base + where + " GROUP BY so.id, so.so_number, so.order_date, so.ship_date, so.status, c.first_name, c.last_name, c.company_name ORDER BY so.order_date DESC", params).fetchall()
        conn.close()

        self.ord_table.setRowCount(0)
        self._ord_row_ids = []
        for row in rows:
            r = self.ord_table.rowCount()
            self.ord_table.insertRow(r)
            self._ord_row_ids.append(row["id"])
            cname = _customer_display(row) if (row["company_name"] or row["first_name"]) else ""
            self.ord_table.setItem(r, 0, _ro(row["so_number"]))
            self.ord_table.setItem(r, 1, _ro(cname))
            self.ord_table.setItem(r, 2, _ro(row["order_date"] or ""))
            self.ord_table.setItem(r, 3, _ro(row["ship_date"] or ""))
            self.ord_table.setItem(r, 4, _ro(f"${row['total']:,.2f}"))
            self.ord_table.setItem(r, 5, _ro(row["status"].capitalize()))
            bg = QtGui.QColor(SO_COLORS.get(row["status"], "#ffffff"))
            for col in range(6):
                self.ord_table.item(r, col).setBackground(bg)
        self._selected_so_id = None
        self._selected_so_number = None
        self.item_table.setRowCount(0)

    def _on_order_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._ord_row_ids):
            return
        self._selected_so_id = self._ord_row_ids[row]
        self._selected_so_number = self.ord_table.item(row, 0).text()
        self._refresh_items()

    def _refresh_items(self):
        self.item_table.setRowCount(0)
        if self._selected_so_id is None:
            return
        conn = get_db()
        try:
            items = conn.execute("""
                SELECT i.description, p.name AS product_name, i.qty, i.unit_price
                FROM so_item i LEFT JOIN product p ON p.id = i.product_id
                WHERE i.so_id = ?
            """, (self._selected_so_id,)).fetchall()
        except psycopg2.OperationalError:
            items = conn.execute(
                "SELECT description, NULL AS product_name, qty, unit_price FROM so_item WHERE so_id = ?",
                (self._selected_so_id,)
            ).fetchall()
        conn.close()
        for item in items:
            r = self.item_table.rowCount()
            self.item_table.insertRow(r)
            self.item_table.setItem(r, 0, _ro(item["description"]))
            self.item_table.setItem(r, 1, _ro(item["product_name"] or ""))
            self.item_table.setItem(r, 2, _ro(str(item["qty"])))
            self.item_table.setItem(r, 3, _ro(f"${item['unit_price']:,.2f}"))
            self.item_table.setItem(r, 4, _ro(f"${item['qty'] * item['unit_price']:,.2f}"))

    def _on_new_order(self):
        dlg = NewOrderDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_orders()

    def _on_add_line_item(self):
        if self._selected_so_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a sales order first.")
            return
        dlg = AddSOLineItemDialog(self._selected_so_id, self._selected_so_number, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_orders()
            self._refresh_items()

    def _set_status(self, new_status, msg):
        if self._selected_so_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a sales order first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE sales_order SET status = ? WHERE id = ?", (new_status, self._selected_so_id))
            conn.commit()
            conn.close()
            self._refresh_orders()

    # ── Customers tab ───────────────────────────────────────────────────────

    def _build_customers_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        sr = QtWidgets.QHBoxLayout()
        sl = QtWidgets.QLabel("Search:")
        sl.setStyleSheet(LABEL_STYLE)
        sr.addWidget(sl)
        self.cust_search = QtWidgets.QLineEdit()
        self.cust_search.setStyleSheet(INPUT_STYLE)
        self.cust_search.setFixedWidth(200)
        self.cust_search.returnPressed.connect(self._on_cust_search)
        sr.addWidget(self.cust_search)
        for text, slot in (("Search", self._on_cust_search), ("Show All", self._on_cust_show_all)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(28)
            b.clicked.connect(slot)
            sr.addWidget(b)
        sr.addStretch()
        v.addLayout(sr)

        self.cust_table = QtWidgets.QTableWidget()
        self.cust_table.setColumnCount(6)
        self.cust_table.setHorizontalHeaderLabels(["Company", "First Name", "Last Name", "Phone", "Email", "City/State"])
        hh = self.cust_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in range(1, 6):
            hh.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.cust_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cust_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.cust_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.cust_table.setAlternatingRowColors(True)
        self.cust_table.verticalHeader().setVisible(False)
        self.cust_table.clicked.connect(self._on_cust_clicked)
        v.addWidget(self.cust_table, stretch=1)

        fg = QtWidgets.QGroupBox("Customer Record")
        fg.setStyleSheet(
            "QGroupBox{color:white; font-weight:bold; border:1px solid white; margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin; left:10px;}"
        )
        fl = QtWidgets.QGridLayout(fg)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        fields = [
            ("Company:", "cust_company"), ("First Name:", "cust_first"), ("Last Name:", "cust_last"),
            ("Phone:", "cust_phone"),     ("Email:", "cust_email"),       ("Address:", "cust_address"),
            ("City:", "cust_city"),       ("State:", "cust_state"),       ("Zip:", "cust_zip"),
        ]
        for i, (label, attr) in enumerate(fields):
            row, col = divmod(i, 3)
            fl.addWidget(lbl(label), row * 2, col * 2)
            edit = QtWidgets.QLineEdit()
            edit.setStyleSheet(INPUT_STYLE)
            setattr(self, attr, edit)
            fl.addWidget(edit, row * 2 + 1, col * 2)
        v.addWidget(fg)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add New",         self._on_cust_add),
            ("Update Selected", self._on_cust_update),
            ("Delete Selected", self._on_cust_delete),
            ("Clear",           self._clear_cust_form),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Customers")

    def _refresh_customers(self, search=None):
        conn = get_db()
        if search:
            rows = conn.execute("""
                SELECT * FROM customer
                WHERE company_name LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email LIKE ?
                ORDER BY company_name, last_name
            """, (f"%{search}%",) * 4).fetchall()
        else:
            rows = conn.execute("SELECT * FROM customer ORDER BY company_name, last_name").fetchall()
        conn.close()
        self.cust_table.setRowCount(0)
        self._cust_row_ids = []
        for row in rows:
            r = self.cust_table.rowCount()
            self.cust_table.insertRow(r)
            self._cust_row_ids.append(row["id"])
            cs = f"{row['city'] or ''}, {row['state'] or ''}".strip(", ")
            self.cust_table.setItem(r, 0, _ro(row["company_name"] or ""))
            self.cust_table.setItem(r, 1, _ro(row["first_name"] or ""))
            self.cust_table.setItem(r, 2, _ro(row["last_name"] or ""))
            self.cust_table.setItem(r, 3, _ro(row["phone_number"] or ""))
            self.cust_table.setItem(r, 4, _ro(row["email"] or ""))
            self.cust_table.setItem(r, 5, _ro(cs))
        self._selected_cust_id = None

    def _on_cust_search(self):
        term = self.cust_search.text().strip()
        self._refresh_customers(search=term if term else None)

    def _on_cust_show_all(self):
        self.cust_search.clear()
        self._refresh_customers()

    def _on_cust_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._cust_row_ids):
            return
        self._selected_cust_id = self._cust_row_ids[row]
        conn = get_db()
        rec = conn.execute("SELECT * FROM customer WHERE id = ?", (self._selected_cust_id,)).fetchone()
        conn.close()
        if not rec:
            return
        self.cust_company.setText(rec["company_name"] or "")
        self.cust_first.setText(rec["first_name"] or "")
        self.cust_last.setText(rec["last_name"] or "")
        self.cust_phone.setText(rec["phone_number"] or "")
        self.cust_email.setText(rec["email"] or "")
        self.cust_address.setText(rec["address"] or "")
        self.cust_city.setText(rec["city"] or "")
        self.cust_state.setText(rec["state"] or "")
        self.cust_zip.setText(rec["zip_code"] or "")

    def _clear_cust_form(self):
        self._selected_cust_id = None
        for attr in ("cust_company", "cust_first", "cust_last", "cust_phone",
                     "cust_email", "cust_address", "cust_city", "cust_state", "cust_zip"):
            getattr(self, attr).clear()
        self.cust_table.clearSelection()

    def _on_cust_add(self):
        conn = get_db()
        conn.execute(
            "INSERT INTO customer (company_name, first_name, last_name, phone_number, email,"
            " address, city, state, zip_code) VALUES (?,?,?,?,?,?,?,?,?)",
            (self.cust_company.text().strip(), self.cust_first.text().strip(),
             self.cust_last.text().strip(), self.cust_phone.text().strip(),
             self.cust_email.text().strip(), self.cust_address.text().strip(),
             self.cust_city.text().strip(), self.cust_state.text().strip(),
             self.cust_zip.text().strip())
        )
        conn.commit()
        conn.close()
        self._clear_cust_form()
        self._refresh_customers()
        self._load_ord_customer_filter()

    def _on_cust_update(self):
        if self._selected_cust_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a customer first.")
            return
        conn = get_db()
        conn.execute(
            "UPDATE customer SET company_name=?, first_name=?, last_name=?, phone_number=?,"
            " email=?, address=?, city=?, state=?, zip_code=? WHERE id=?",
            (self.cust_company.text().strip(), self.cust_first.text().strip(),
             self.cust_last.text().strip(), self.cust_phone.text().strip(),
             self.cust_email.text().strip(), self.cust_address.text().strip(),
             self.cust_city.text().strip(), self.cust_state.text().strip(),
             self.cust_zip.text().strip(), self._selected_cust_id)
        )
        conn.commit()
        conn.close()
        self._refresh_customers()
        self._load_ord_customer_filter()

    def _on_cust_delete(self):
        if self._selected_cust_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a customer first.")
            return
        conn = get_db()
        so_count = conn.execute(
            "SELECT COUNT(*) FROM sales_order WHERE customer_id = ?", (self._selected_cust_id,)
        ).fetchone()[0]
        conn.close()
        msg = "Delete this customer?"
        if so_count:
            msg += f"\n\nWarning: {so_count} sales order(s) will be unlinked."
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE sales_order SET customer_id = NULL WHERE customer_id = ?", (self._selected_cust_id,))
            conn.execute("DELETE FROM customer WHERE id = ?", (self._selected_cust_id,))
            conn.commit()
            conn.close()
            self._clear_cust_form()
            self._refresh_customers()
            self._load_ord_customer_filter()


class SalesOrders(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sales")
        self.resize(920, 640)
        _apply_blue_palette(self)
        self.setCentralWidget(SalesOrdersWidget())


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = SalesOrders()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
