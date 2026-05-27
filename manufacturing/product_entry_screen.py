import sys
import psycopg2
from db_pg import get_db
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE = "QLineEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
COMBO_STYLE = "QComboBox{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}QComboBox QAbstractItemView{background-color:white;}"
DATE_STYLE  = "QDateEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 4px;}"
SPIN_STYLE  = "QDoubleSpinBox{background-color:white;border:2px solid black;border-radius:4px;padding:2px 4px;}"
ISPIN_STYLE = "QSpinBox{background-color:white;border:2px solid black;border-radius:4px;padding:2px 4px;}"
LABEL_STYLE = "color:white;font-size:13px;"
TAB_STYLE   = ("QTabWidget::pane{border:1px solid black;}"
               "QTabBar::tab{background:white; border:2px solid black; padding:6px 18px;"
               " border-bottom:none; border-radius:4px 4px 0 0;}"
               "QTabBar::tab:selected{background:rgb(85,255,255); font-weight:bold;}"
               "QTabBar::tab:hover{background:rgb(85,255,255);}")

# Stock level row colors
COLOR_CRITICAL = QtGui.QColor(255, 200, 200)   # red   — at or below reorder point
COLOR_LOW      = QtGui.QColor(255, 243, 205)   # amber — within 2x reorder point
COLOR_OK       = QtGui.QColor(212, 237, 218)   # green — well stocked

# Transaction type colors
TRANS_COLORS = {
    "receipt":    QtGui.QColor(212, 237, 218),
    "issue":      QtGui.QColor(255, 200, 200),
    "adjustment": QtGui.QColor(220, 235, 255),
}


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS supplier (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name   TEXT NOT NULL,
            last_name    TEXT NOT NULL,
            company_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            address      TEXT NOT NULL,
            city         TEXT NOT NULL,
            state        TEXT NOT NULL,
            zip_code     TEXT NOT NULL,
            email        TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id    INTEGER REFERENCES supplier(id),
            name           TEXT,
            purchase_date  TEXT,
            purchase_price INTEGER,
            bin            INTEGER,
            amount         INTEGER,
            reorder_point  INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory_transaction (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES product(id),
            trans_date TEXT NOT NULL,
            trans_type TEXT NOT NULL,
            quantity   INTEGER NOT NULL,
            reference  TEXT,
            notes      TEXT
        )
    """)
    conn.commit()
    conn.close()


def _apply_blue_palette(widget):
    pal = widget.palette()
    for g in (QtGui.QPalette.ColorGroup.Active,
              QtGui.QPalette.ColorGroup.Inactive,
              QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(g, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(g, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter):
    item = QtWidgets.QTableWidgetItem(str(text))
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(align)
    return item


def _supplier_display(row):
    company = (row["company_name"] or "").strip()
    contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    return company if company else contact


# ── Transaction dialog ─────────────────────────────────────────────────────

class TransactionDialog(QtWidgets.QDialog):
    """Handles receipt, issue, and adjustment transactions."""

    def __init__(self, trans_type, parent=None, preselect_product_id=None):
        super().__init__(parent)
        self._trans_type = trans_type
        titles = {"receipt": "Receive Stock", "issue": "Issue Stock",
                  "adjustment": "Inventory Adjustment"}
        self.setWindowTitle(titles[trans_type])
        self.setFixedSize(460, 280)
        _apply_blue_palette(self)
        self._preselect = preselect_product_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)

        title_text = {
            "receipt":    "Receive Stock",
            "issue":      "Issue / Use Stock",
            "adjustment": "Inventory Adjustment",
        }[self._trans_type]
        title = QtWidgets.QLabel(title_text)
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:white;font-size:15px;font-weight:bold;")
        layout.addWidget(title)

        def row(lbl_text, widget, lbl_w=120):
            r = QtWidgets.QHBoxLayout()
            l = QtWidgets.QLabel(lbl_text)
            l.setFixedWidth(lbl_w)
            l.setStyleSheet(LABEL_STYLE)
            r.addWidget(l)
            r.addWidget(widget)
            return r

        self.prod_combo = QtWidgets.QComboBox()
        self.prod_combo.setStyleSheet(COMBO_STYLE)
        conn = get_db()
        products = conn.execute("SELECT id, name FROM product ORDER BY name").fetchall()
        conn.close()
        for p in products:
            self.prod_combo.addItem(p["name"], p["id"])
        if self._preselect:
            idx = self.prod_combo.findData(self._preselect)
            if idx >= 0:
                self.prod_combo.setCurrentIndex(idx)
        self.prod_combo.currentIndexChanged.connect(self._update_max)
        layout.addLayout(row("Product:", self.prod_combo))

        self.trans_date = QtWidgets.QDateEdit()
        self.trans_date.setStyleSheet(DATE_STYLE)
        self.trans_date.setCalendarPopup(True)
        self.trans_date.setDisplayFormat("MM/dd/yyyy")
        self.trans_date.setDate(QtCore.QDate.currentDate())
        layout.addLayout(row("Date:", self.trans_date))

        if self._trans_type == "adjustment":
            self.qty = QtWidgets.QSpinBox()
            self.qty.setStyleSheet(ISPIN_STYLE)
            self.qty.setRange(-999999, 999999)
            self.qty.setValue(0)
            layout.addLayout(row("Qty Change (+/-):", self.qty))
        else:
            self.qty = QtWidgets.QSpinBox()
            self.qty.setStyleSheet(ISPIN_STYLE)
            self.qty.setRange(1, 999999)
            self.qty.setValue(1)
            qty_label = "Qty to Receive:" if self._trans_type == "receipt" else "Qty to Issue:"
            layout.addLayout(row(qty_label, self.qty))

        self.reference = QtWidgets.QLineEdit()
        self.reference.setStyleSheet(INPUT_STYLE)
        self.reference.setPlaceholderText("PO #, work order, etc.")
        layout.addLayout(row("Reference:", self.reference))

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        self.notes.setPlaceholderText("Optional notes")
        layout.addLayout(row("Notes:", self.notes))

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Save", self._on_save), ("Cancel", self.reject)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

    def _update_max(self):
        if self._trans_type != "issue":
            return
        pid = self.prod_combo.currentData()
        if pid is None:
            return
        conn = get_db()
        p = conn.execute("SELECT amount FROM product WHERE id=?", (pid,)).fetchone()
        conn.close()
        if p:
            self.qty.setRange(1, max(1, p["amount"]))

    def _on_save(self):
        pid = self.prod_combo.currentData()
        if pid is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Select a product.")
            return
        qty_val = self.qty.value()
        if self._trans_type == "adjustment" and qty_val == 0:
            QtWidgets.QMessageBox.warning(self, "Error", "Adjustment quantity cannot be zero.")
            return

        stored_qty = qty_val if self._trans_type != "issue" else -qty_val
        today = self.trans_date.date().toString("yyyy-MM-dd")

        conn = get_db()
        conn.execute("""
            INSERT INTO inventory_transaction
                (product_id, trans_date, trans_type, quantity, reference, notes)
            VALUES (?,?,?,?,?,?)
        """, (pid, today, self._trans_type, stored_qty,
              self.reference.text().strip() or None,
              self.notes.text().strip() or None))
        conn.execute(
            "UPDATE product SET amount = amount + ? WHERE id=?",
            (stored_qty, pid))
        if self._trans_type == "receipt":
            conn.execute(
                "UPDATE product SET purchase_date=? WHERE id=?", (today, pid))
        conn.commit()
        conn.close()
        self.accept()


# ── Main window ────────────────────────────────────────────────────────────

class Inventory(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inventory")
        self.resize(1100, 680)
        _apply_blue_palette(self)
        self._prod_row_ids  = []
        self._trans_row_ids = []
        self._build_ui()
        self._load_products()
        self._refresh_stock_report()
        self._refresh_transactions()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        outer.addWidget(tabs)
        tabs.addTab(self._build_products_tab(),     "Products")
        tabs.addTab(self._build_stock_report_tab(), "Stock Report")
        tabs.addTab(self._build_transactions_tab(), "Transactions")
        tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs = tabs

    # ── Products tab ───────────────────────────────────────────────────────

    def _build_products_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.prod_table = QtWidgets.QTableWidget()
        self.prod_table.setColumnCount(7)
        self.prod_table.setHorizontalHeaderLabels(
            ["Name", "Supplier", "Bin", "Unit Cost", "Qty on Hand",
             "Reorder Point", "Last Received"])
        hh = self.prod_table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5, 6):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.prod_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.prod_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.prod_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.prod_table.setAlternatingRowColors(True)
        self.prod_table.verticalHeader().setVisible(False)
        self.prod_table.clicked.connect(self._on_prod_row_clicked)
        layout.addWidget(self.prod_table, stretch=1)

        sr = QtWidgets.QHBoxLayout()
        sl = QtWidgets.QLabel("Search:")
        sl.setStyleSheet(LABEL_STYLE)
        sr.addWidget(sl)
        self.prod_search = QtWidgets.QLineEdit()
        self.prod_search.setStyleSheet(INPUT_STYLE)
        self.prod_search.setFixedWidth(220)
        self.prod_search.setPlaceholderText("Product name")
        self.prod_search.returnPressed.connect(self._on_prod_search)
        sr.addWidget(self.prod_search)
        for t, fn in (("Search", self._on_prod_search), ("Show All", self._load_products)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            sr.addWidget(b)
        sr.addStretch()
        layout.addLayout(sr)

        fg = QtWidgets.QGroupBox("Product Record")
        fg.setStyleSheet(
            "QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;}")
        grid = QtWidgets.QGridLayout(fg)
        grid.setSpacing(6)

        def lbl(t):
            l = QtWidgets.QLabel(t)
            l.setStyleSheet(LABEL_STYLE)
            return l

        def inp(ph=""):
            e = QtWidgets.QLineEdit()
            e.setStyleSheet(INPUT_STYLE)
            e.setPlaceholderText(ph)
            return e

        self.pf_name = inp("Product / item name")

        self.pf_supplier = QtWidgets.QComboBox()
        self.pf_supplier.setStyleSheet(COMBO_STYLE)
        self.pf_supplier.setMinimumWidth(180)

        self.pf_bin = inp("Bin / location")
        self.pf_bin.setFixedWidth(100)

        self.pf_cost = QtWidgets.QDoubleSpinBox()
        self.pf_cost.setStyleSheet(SPIN_STYLE)
        self.pf_cost.setRange(0, 9999999)
        self.pf_cost.setDecimals(2)
        self.pf_cost.setPrefix("$ ")
        self.pf_cost.setFixedWidth(110)

        self.pf_qty = QtWidgets.QSpinBox()
        self.pf_qty.setStyleSheet(ISPIN_STYLE)
        self.pf_qty.setRange(0, 999999)
        self.pf_qty.setFixedWidth(80)

        self.pf_reorder = QtWidgets.QSpinBox()
        self.pf_reorder.setStyleSheet(ISPIN_STYLE)
        self.pf_reorder.setRange(0, 999999)
        self.pf_reorder.setFixedWidth(80)

        grid.addWidget(lbl("Name:"),         0, 0); grid.addWidget(self.pf_name,     0, 1, 1, 5)
        grid.addWidget(lbl("Supplier:"),     1, 0); grid.addWidget(self.pf_supplier, 1, 1, 1, 2)
        grid.addWidget(lbl("Bin:"),          1, 3); grid.addWidget(self.pf_bin,      1, 4)
        grid.addWidget(lbl("Unit Cost:"),    2, 0); grid.addWidget(self.pf_cost,     2, 1)
        grid.addWidget(lbl("Qty on Hand:"),  2, 2); grid.addWidget(self.pf_qty,      2, 3)
        grid.addWidget(lbl("Reorder Pt:"),   2, 4); grid.addWidget(self.pf_reorder,  2, 5)
        layout.addWidget(fg)

        br = QtWidgets.QHBoxLayout()
        for t, fn in (("Add New", self._on_prod_add), ("Update Selected", self._on_prod_update),
                      ("Delete Selected", self._on_prod_delete), ("Clear", self._prod_clear)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(34)
            b.clicked.connect(fn)
            br.addWidget(b)
        br.addStretch()
        layout.addLayout(br)
        self._load_supplier_combo()
        return w

    # ── Stock Report tab ───────────────────────────────────────────────────

    def _build_stock_report_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Stock Levels  —  sorted by quantity on hand")
        title.setStyleSheet("color:white;font-size:14px;font-weight:bold;")
        hdr.addWidget(title)
        ref_btn = QtWidgets.QPushButton("Refresh")
        ref_btn.setStyleSheet(BUTTON_STYLE)
        ref_btn.setFixedHeight(30)
        ref_btn.clicked.connect(self._refresh_stock_report)
        hdr.addWidget(ref_btn)
        hdr.addStretch()
        layout.addLayout(hdr)

        legend = QtWidgets.QHBoxLayout()
        for color, label in (
            (COLOR_CRITICAL, "At/Below Reorder Point"),
            (COLOR_LOW,      "Within 2x Reorder Point"),
            (COLOR_OK,       "Well Stocked"),
        ):
            swatch = QtWidgets.QLabel("   ")
            pal = swatch.palette()
            pal.setColor(QtGui.QPalette.ColorRole.Window, color)
            swatch.setAutoFillBackground(True)
            swatch.setPalette(pal)
            swatch.setFixedSize(24, 16)
            legend.addWidget(swatch)
            lbl = QtWidgets.QLabel(label)
            lbl.setStyleSheet("color:white;font-size:12px;")
            legend.addWidget(lbl)
            legend.addSpacing(16)
        legend.addStretch()
        layout.addLayout(legend)

        self.stock_table = QtWidgets.QTableWidget()
        self.stock_table.setColumnCount(6)
        self.stock_table.setHorizontalHeaderLabels(
            ["Name", "Supplier", "Bin", "Qty on Hand", "Reorder Point", "Unit Cost"])
        sh = self.stock_table.horizontalHeader()
        sh.setStyleSheet("color:black;font-weight:bold;")
        sh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5):
            sh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.stock_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stock_table.setAlternatingRowColors(False)
        self.stock_table.verticalHeader().setVisible(False)
        layout.addWidget(self.stock_table, stretch=1)
        return w

    # ── Transactions tab ───────────────────────────────────────────────────

    def _build_transactions_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        fr.setSpacing(8)

        def fl(t):
            l = QtWidgets.QLabel(t)
            l.setStyleSheet(LABEL_STYLE)
            return l

        self.tr_prod_filter = QtWidgets.QComboBox()
        self.tr_prod_filter.setStyleSheet(COMBO_STYLE)
        self.tr_prod_filter.setMinimumWidth(200)
        self.tr_type_filter = QtWidgets.QComboBox()
        self.tr_type_filter.setStyleSheet(COMBO_STYLE)
        self.tr_type_filter.addItems(["(all types)", "receipt", "issue", "adjustment"])
        self.tr_from = QtWidgets.QDateEdit()
        self.tr_from.setStyleSheet(DATE_STYLE)
        self.tr_from.setCalendarPopup(True)
        self.tr_from.setDisplayFormat("MM/dd/yyyy")
        self.tr_from.setDate(QtCore.QDate.currentDate().addDays(-30))
        self.tr_to = QtWidgets.QDateEdit()
        self.tr_to.setStyleSheet(DATE_STYLE)
        self.tr_to.setCalendarPopup(True)
        self.tr_to.setDisplayFormat("MM/dd/yyyy")
        self.tr_to.setDate(QtCore.QDate.currentDate())

        fr.addWidget(fl("Product:")); fr.addWidget(self.tr_prod_filter)
        fr.addWidget(fl("Type:"));    fr.addWidget(self.tr_type_filter)
        fr.addWidget(fl("From:"));    fr.addWidget(self.tr_from)
        fr.addWidget(fl("To:"));      fr.addWidget(self.tr_to)
        for t, fn in (("Apply", self._refresh_transactions), ("Show All", self._tr_show_all)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            fr.addWidget(b)
        fr.addStretch()
        layout.addLayout(fr)

        self.trans_table = QtWidgets.QTableWidget()
        self.trans_table.setColumnCount(6)
        self.trans_table.setHorizontalHeaderLabels(
            ["Date", "Product", "Type", "Qty", "Reference", "Notes"])
        th = self.trans_table.horizontalHeader()
        th.setStyleSheet("color:black;font-weight:bold;")
        th.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (0, 2, 3, 4, 5):
            th.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.trans_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.trans_table.verticalHeader().setVisible(False)
        layout.addWidget(self.trans_table, stretch=1)

        ar = QtWidgets.QHBoxLayout()
        for t, fn in (("Receive Stock", self._on_receive),
                      ("Issue Stock",   self._on_issue),
                      ("Adjustment",    self._on_adjust)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(fn)
            ar.addWidget(b)
        ar.addStretch()
        layout.addLayout(ar)
        return w

    # ── Products data ──────────────────────────────────────────────────────

    def _load_supplier_combo(self):
        conn = get_db()
        suppliers = conn.execute(
            "SELECT id, first_name, last_name, company_name FROM supplier "
            "ORDER BY company_name, last_name, first_name"
        ).fetchall()
        conn.close()
        self.pf_supplier.blockSignals(True)
        self.pf_supplier.clear()
        self.pf_supplier.addItem("(none)", None)
        for s in suppliers:
            self.pf_supplier.addItem(_supplier_display(s), s["id"])
        self.pf_supplier.blockSignals(False)

    def _load_products(self, search=None):
        self.prod_search.blockSignals(True)
        if not search:
            self.prod_search.clear()
        self.prod_search.blockSignals(False)

        conn = get_db()
        if search:
            rows = conn.execute(
                "SELECT p.*, s.first_name, s.last_name, s.company_name "
                "FROM product p LEFT JOIN supplier s ON s.id=p.supplier_id "
                "WHERE p.name LIKE ? ORDER BY p.name",
                (f"%{search}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT p.*, s.first_name, s.last_name, s.company_name "
                "FROM product p LEFT JOIN supplier s ON s.id=p.supplier_id "
                "ORDER BY p.name"
            ).fetchall()
        conn.close()

        self.prod_table.setRowCount(0)
        self._prod_row_ids = []
        right  = QtCore.Qt.AlignmentFlag.AlignRight  | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        for row in rows:
            r = self.prod_table.rowCount()
            self.prod_table.insertRow(r)
            self._prod_row_ids.append(row["id"])
            supp = _supplier_display(row) if row["company_name"] or row["last_name"] else ""
            rp   = row["reorder_point"] if "reorder_point" in row.keys() else 0
            qty  = row["amount"] or 0
            for c, (val, algn) in enumerate([
                (row["name"],              QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (supp,                     QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["bin"] or "",         center),
                (f"${row['purchase_price'] or 0:,.2f}", right),
                (str(qty),                 center),
                (str(rp),                  center),
                (row["purchase_date"] or "", center),
            ]):
                self.prod_table.setItem(r, c, _ro(val, algn))
        self._refresh_product_filter()

    def _refresh_product_filter(self):
        conn = get_db()
        products = conn.execute("SELECT id, name FROM product ORDER BY name").fetchall()
        conn.close()
        self.tr_prod_filter.blockSignals(True)
        self.tr_prod_filter.clear()
        self.tr_prod_filter.addItem("(all products)", None)
        for p in products:
            self.tr_prod_filter.addItem(p["name"], p["id"])
        self.tr_prod_filter.blockSignals(False)

    def _on_prod_search(self):
        self._load_products(search=self.prod_search.text().strip() or None)

    def _on_prod_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._prod_row_ids):
            return
        conn = get_db()
        p = conn.execute("SELECT * FROM product WHERE id=?",
                         (self._prod_row_ids[row],)).fetchone()
        conn.close()
        if not p:
            return
        self.pf_name.setText(p["name"] or "")
        idx = self.pf_supplier.findData(p["supplier_id"])
        self.pf_supplier.setCurrentIndex(max(0, idx))
        self.pf_bin.setText(p["bin"] or "")
        self.pf_cost.setValue(float(p["purchase_price"] or 0))
        self.pf_qty.setValue(int(p["amount"] or 0))
        rp = p["reorder_point"] if "reorder_point" in p.keys() else 0
        self.pf_reorder.setValue(int(rp or 0))

    def _prod_clear(self):
        self.pf_name.clear()
        self.pf_supplier.setCurrentIndex(0)
        self.pf_bin.clear()
        self.pf_cost.setValue(0)
        self.pf_qty.setValue(0)
        self.pf_reorder.setValue(0)
        self.prod_table.clearSelection()

    def _collect_product_form(self):
        name = self.pf_name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Product name is required.")
            return None
        return {
            "name":           name,
            "supplier_id":    self.pf_supplier.currentData(),
            "bin":            self.pf_bin.text().strip() or None,
            "purchase_price": self.pf_cost.value(),
            "amount":         self.pf_qty.value(),
            "reorder_point":  self.pf_reorder.value(),
        }

    def _on_prod_add(self):
        data = self._collect_product_form()
        if not data:
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO product (name,supplier_id,bin,purchase_price,amount,reorder_point) "
            "VALUES (:name,:supplier_id,:bin,:purchase_price,:amount,:reorder_point)",
            data)
        conn.commit()
        conn.close()
        self._prod_clear()
        self._load_products()

    def _on_prod_update(self):
        row = self.prod_table.currentRow()
        if row < 0 or row >= len(self._prod_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a product first.")
            return
        data = self._collect_product_form()
        if not data:
            return
        data["id"] = self._prod_row_ids[row]
        conn = get_db()
        conn.execute(
            "UPDATE product SET name=:name,supplier_id=:supplier_id,bin=:bin,"
            "purchase_price=:purchase_price,amount=:amount,reorder_point=:reorder_point "
            "WHERE id=:id",
            data)
        conn.commit()
        conn.close()
        self._load_products()

    def _on_prod_delete(self):
        row = self.prod_table.currentRow()
        if row < 0 or row >= len(self._prod_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a product first.")
            return
        pid = self._prod_row_ids[row]
        conn = get_db()
        tr_count = conn.execute(
            "SELECT COUNT(*) FROM inventory_transaction WHERE product_id=?", (pid,)
        ).fetchone()[0]
        conn.close()
        msg = "Delete this product?"
        if tr_count:
            msg += f"\n\nWarning: {tr_count} transaction record(s) will also be deleted."
        if (QtWidgets.QMessageBox.question(
                self, "Confirm Delete", msg,
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            conn = get_db()
            conn.execute(
                "DELETE FROM inventory_transaction WHERE product_id=?", (pid,))
            conn.execute("DELETE FROM product WHERE id=?", (pid,))
            conn.commit()
            conn.close()
            self._prod_clear()
            self._load_products()
            self._refresh_transactions()

    # ── Stock report data ──────────────────────────────────────────────────

    def _refresh_stock_report(self):
        conn = get_db()
        rows = conn.execute(
            "SELECT p.*, s.first_name, s.last_name, s.company_name "
            "FROM product p LEFT JOIN supplier s ON s.id=p.supplier_id "
            "ORDER BY p.amount ASC, p.name"
        ).fetchall()
        conn.close()

        self.stock_table.setRowCount(0)
        right  = QtCore.Qt.AlignmentFlag.AlignRight  | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        for row in rows:
            r = self.stock_table.rowCount()
            self.stock_table.insertRow(r)
            qty = int(row["amount"] or 0)
            rp  = int(row["reorder_point"] if "reorder_point" in row.keys() else 0) or 0
            supp = _supplier_display(row) if row["company_name"] or row["last_name"] else ""
            if rp > 0 and qty <= rp:
                color = COLOR_CRITICAL
            elif rp > 0 and qty <= rp * 2:
                color = COLOR_LOW
            else:
                color = COLOR_OK
            for c, (val, algn) in enumerate([
                (row["name"],   QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (supp,          QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["bin"] or "", center),
                (str(qty),      center),
                (str(rp),       center),
                (f"${row['purchase_price'] or 0:,.2f}", right),
            ]):
                item = _ro(val, algn)
                item.setBackground(color)
                self.stock_table.setItem(r, c, item)

    # ── Transaction data ───────────────────────────────────────────────────

    def _refresh_transactions(self):
        pid    = self.tr_prod_filter.currentData()
        ttype  = self.tr_type_filter.currentText()
        from_s = self.tr_from.date().toString("yyyy-MM-dd")
        to_s   = self.tr_to.date().toString("yyyy-MM-dd")
        conn   = get_db()
        q = (
            "SELECT t.*, p.name AS product_name "
            "FROM inventory_transaction t JOIN product p ON p.id=t.product_id "
            "WHERE t.trans_date BETWEEN ? AND ?"
        )
        params = [from_s, to_s]
        if pid:
            q += " AND t.product_id=?"
            params.append(pid)
        if ttype != "(all types)":
            q += " AND t.trans_type=?"
            params.append(ttype)
        q += " ORDER BY t.trans_date DESC, t.id DESC"
        rows = conn.execute(q, params).fetchall()
        conn.close()

        self.trans_table.setRowCount(0)
        self._trans_row_ids = []
        right  = QtCore.Qt.AlignmentFlag.AlignRight  | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        for row in rows:
            r = self.trans_table.rowCount()
            self.trans_table.insertRow(r)
            self._trans_row_ids.append(row["id"])
            qty     = row["quantity"]
            qty_str = f"+{qty}" if qty > 0 else str(qty)
            color   = TRANS_COLORS.get(row["trans_type"], QtGui.QColor(255, 255, 255))
            for c, (val, algn) in enumerate([
                (row["trans_date"],    center),
                (row["product_name"],  QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["trans_type"],    center),
                (qty_str,              right),
                (row["reference"] or "", QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["notes"] or "",     QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
            ]):
                item = _ro(val, algn)
                item.setBackground(color)
                self.trans_table.setItem(r, c, item)

    def _tr_show_all(self):
        self.tr_prod_filter.setCurrentIndex(0)
        self.tr_type_filter.setCurrentIndex(0)
        self.tr_from.setDate(QtCore.QDate(2000, 1, 1))
        self.tr_to.setDate(QtCore.QDate.currentDate())
        self._refresh_transactions()

    def _on_receive(self):
        pid = self._selected_product_id()
        dlg = TransactionDialog("receipt", self, preselect_product_id=pid)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._load_products()
            self._refresh_stock_report()
            self._refresh_transactions()

    def _on_issue(self):
        pid = self._selected_product_id()
        dlg = TransactionDialog("issue", self, preselect_product_id=pid)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._load_products()
            self._refresh_stock_report()
            self._refresh_transactions()

    def _on_adjust(self):
        pid = self._selected_product_id()
        dlg = TransactionDialog("adjustment", self, preselect_product_id=pid)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._load_products()
            self._refresh_stock_report()
            self._refresh_transactions()

    def _selected_product_id(self):
        row = self.prod_table.currentRow()
        if 0 <= row < len(self._prod_row_ids):
            return self._prod_row_ids[row]
        return None

    def _on_tab_changed(self, index):
        if index == 1:
            self._refresh_stock_report()
        elif index == 2:
            self._refresh_product_filter()
            self._refresh_transactions()


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = Inventory()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
