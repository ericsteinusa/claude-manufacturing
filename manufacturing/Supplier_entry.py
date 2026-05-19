import sys
import sqlite3
import os
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "company.db")

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

PO_COLORS = {
    "open":      QtGui.QColor(255, 255, 255),
    "partial":   QtGui.QColor(255, 243, 205),
    "received":  QtGui.QColor(212, 237, 218),
    "cancelled": QtGui.QColor(220, 220, 220),
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
        CREATE TABLE IF NOT EXISTS purchase_order (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number     TEXT NOT NULL UNIQUE,
            supplier_id   INTEGER NOT NULL REFERENCES supplier(id),
            order_date    TEXT NOT NULL,
            expected_date TEXT,
            status        TEXT NOT NULL DEFAULT 'open',
            notes         TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS po_item (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id        INTEGER NOT NULL REFERENCES purchase_order(id),
            description  TEXT NOT NULL,
            product_id   INTEGER,
            qty_ordered  INTEGER NOT NULL,
            unit_price   REAL NOT NULL,
            qty_received INTEGER NOT NULL DEFAULT 0
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


def _money(v):
    return f"${v:,.2f}"


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter):
    item = QtWidgets.QTableWidgetItem(str(text))
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(align)
    return item


def _supplier_display(row):
    company = (row["company_name"] or "").strip()
    contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    return company if company else contact


def _next_po_num():
    yr = date.today().year
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM purchase_order WHERE po_number LIKE ?",
                     (f"PO-{yr}-%",)).fetchone()[0]
    conn.close()
    return f"PO-{yr}-{n+1:04d}"


# ── Dialogs ────────────────────────────────────────────────────────────────

class NewPODialog(QtWidgets.QDialog):
    def __init__(self, parent=None, preselect_supplier_id=None):
        super().__init__(parent)
        self.setWindowTitle("New Purchase Order")
        self.setFixedSize(460, 280)
        _apply_blue_palette(self)
        self._preselect = preselect_supplier_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("New Purchase Order")
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

        self.supp_combo = QtWidgets.QComboBox()
        self.supp_combo.setStyleSheet(COMBO_STYLE)
        conn = get_db()
        suppliers = conn.execute(
            "SELECT id, first_name, last_name, company_name FROM supplier "
            "ORDER BY company_name, last_name, first_name"
        ).fetchall()
        conn.close()
        for s in suppliers:
            self.supp_combo.addItem(_supplier_display(s), s["id"])
        if self._preselect:
            idx = self.supp_combo.findData(self._preselect)
            if idx >= 0:
                self.supp_combo.setCurrentIndex(idx)
        layout.addLayout(row("Supplier:", self.supp_combo))

        self.po_num = QtWidgets.QLineEdit(_next_po_num())
        self.po_num.setStyleSheet(INPUT_STYLE)
        layout.addLayout(row("PO Number:", self.po_num))

        self.order_date = QtWidgets.QDateEdit()
        self.order_date.setStyleSheet(DATE_STYLE)
        self.order_date.setCalendarPopup(True)
        self.order_date.setDisplayFormat("MM/dd/yyyy")
        self.order_date.setDate(QtCore.QDate.currentDate())
        layout.addLayout(row("Order Date:", self.order_date))

        self.exp_date = QtWidgets.QDateEdit()
        self.exp_date.setStyleSheet(DATE_STYLE)
        self.exp_date.setCalendarPopup(True)
        self.exp_date.setDisplayFormat("MM/dd/yyyy")
        self.exp_date.setDate(QtCore.QDate.currentDate().addDays(14))
        layout.addLayout(row("Expected Date:", self.exp_date))

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        self.notes.setPlaceholderText("Notes / reference")
        layout.addLayout(row("Notes:", self.notes))

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Save", self._on_save), ("Cancel", self.reject)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

    def _on_save(self):
        if self.supp_combo.count() == 0 or self.supp_combo.currentData() is None:
            QtWidgets.QMessageBox.warning(self, "Error", "Select a supplier.")
            return
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO purchase_order
                    (po_number, supplier_id, order_date, expected_date, status, notes)
                VALUES (?,?,?,?,?,?)
            """, (self.po_num.text().strip(),
                  self.supp_combo.currentData(),
                  self.order_date.date().toString("yyyy-MM-dd"),
                  self.exp_date.date().toString("yyyy-MM-dd"),
                  "open",
                  self.notes.text().strip() or None))
            conn.commit()
        except sqlite3.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate", "PO number already exists.")
            conn.close()
            return
        conn.close()
        self.accept()


class AddLineItemDialog(QtWidgets.QDialog):
    def __init__(self, po_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Line Item")
        self.setFixedSize(460, 260)
        self._po_id = po_id
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)

        title = QtWidgets.QLabel("Add Line Item")
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

        self.desc = QtWidgets.QLineEdit()
        self.desc.setStyleSheet(INPUT_STYLE)
        self.desc.setPlaceholderText("Item description")
        layout.addLayout(row("Description:", self.desc))

        self.prod_combo = QtWidgets.QComboBox()
        self.prod_combo.setStyleSheet(COMBO_STYLE)
        self.prod_combo.addItem("(none — new item)", None)
        conn = get_db()
        try:
            products = conn.execute("SELECT id, name FROM product ORDER BY name").fetchall()
            for p in products:
                self.prod_combo.addItem(p["name"], p["id"])
        except sqlite3.OperationalError:
            pass
        conn.close()
        self.prod_combo.currentIndexChanged.connect(self._on_product_changed)
        layout.addLayout(row("Product (opt.):", self.prod_combo))

        self.qty = QtWidgets.QSpinBox()
        self.qty.setStyleSheet(ISPIN_STYLE)
        self.qty.setRange(1, 999999)
        self.qty.setValue(1)
        layout.addLayout(row("Quantity:", self.qty))

        self.price = QtWidgets.QDoubleSpinBox()
        self.price.setStyleSheet(SPIN_STYLE)
        self.price.setRange(0, 9999999)
        self.price.setDecimals(2)
        self.price.setPrefix("$ ")
        layout.addLayout(row("Unit Price:", self.price))

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Add Item", self._on_save), ("Cancel", self.reject)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

    def _on_product_changed(self):
        pid = self.prod_combo.currentData()
        if pid is None:
            return
        conn = get_db()
        try:
            p = conn.execute("SELECT name, purchase_price FROM product WHERE id=?", (pid,)).fetchone()
            if p:
                if not self.desc.text().strip():
                    self.desc.setText(p["name"])
                if p["purchase_price"]:
                    self.price.setValue(float(p["purchase_price"]))
        except sqlite3.OperationalError:
            pass
        conn.close()

    def _on_save(self):
        desc = self.desc.text().strip()
        if not desc:
            QtWidgets.QMessageBox.warning(self, "Error", "Description is required.")
            return
        conn = get_db()
        conn.execute("""
            INSERT INTO po_item (po_id, description, product_id, qty_ordered, unit_price)
            VALUES (?,?,?,?,?)
        """, (self._po_id, desc, self.prod_combo.currentData(),
              self.qty.value(), self.price.value()))
        conn.commit()
        conn.close()
        self.accept()


class ReceivePODialog(QtWidgets.QDialog):
    def __init__(self, po_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Receive Purchase Order")
        self.resize(680, 380)
        self._po_id = po_id
        _apply_blue_palette(self)
        self._spins = []
        self._build_ui()

    def _build_ui(self):
        conn = get_db()
        po = conn.execute(
            "SELECT po.*, s.first_name, s.last_name, s.company_name "
            "FROM purchase_order po JOIN supplier s ON s.id=po.supplier_id WHERE po.id=?",
            (self._po_id,)
        ).fetchone()
        items = conn.execute(
            "SELECT * FROM po_item WHERE po_id=? ORDER BY id", (self._po_id,)
        ).fetchall()
        conn.close()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(8)

        info = QtWidgets.QLabel(
            f"PO: {po['po_number']}  |  Supplier: {_supplier_display(po)}")
        info.setStyleSheet("color:white;font-size:13px;font-weight:bold;")
        layout.addWidget(info)

        lbl = QtWidgets.QLabel("Enter quantity to receive for each open item:")
        lbl.setStyleSheet("color:white;font-size:12px;")
        layout.addWidget(lbl)

        tbl = QtWidgets.QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(
            ["Description", "Ordered", "Already Received", "Remaining", "Receive Now"])
        hh = tbl.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        layout.addWidget(tbl, stretch=1)

        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        for item in items:
            remaining = item["qty_ordered"] - item["qty_received"]
            if remaining <= 0:
                continue
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, _ro(item["description"]))
            tbl.setItem(r, 1, _ro(str(item["qty_ordered"]), center))
            tbl.setItem(r, 2, _ro(str(item["qty_received"]), center))
            tbl.setItem(r, 3, _ro(str(remaining), center))
            spin = QtWidgets.QSpinBox()
            spin.setStyleSheet(ISPIN_STYLE)
            spin.setRange(0, remaining)
            spin.setValue(remaining)
            tbl.setCellWidget(r, 4, spin)
            self._spins.append((item["id"], item["product_id"], spin))

        btn_row = QtWidgets.QHBoxLayout()
        for text, slot in (("Receive", self._on_receive), ("Cancel", self.reject)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _on_receive(self):
        today = date.today().isoformat()
        conn = get_db()
        po_num = conn.execute(
            "SELECT po_number FROM purchase_order WHERE id=?", (self._po_id,)
        ).fetchone()["po_number"]

        for item_id, product_id, spin in self._spins:
            qty = spin.value()
            if qty <= 0:
                continue
            conn.execute(
                "UPDATE po_item SET qty_received = qty_received + ? WHERE id=?",
                (qty, item_id))
            if product_id:
                conn.execute(
                    "UPDATE product SET amount = amount + ? WHERE id=?",
                    (qty, product_id))
                try:
                    conn.execute("""
                        INSERT INTO inventory_transaction
                            (product_id, trans_date, trans_type, quantity, reference, notes)
                        VALUES (?,?,?,?,?,?)
                    """, (product_id, today, "receipt", qty, po_num,
                          f"Received from PO {po_num}"))
                except sqlite3.OperationalError:
                    pass

        all_items = conn.execute(
            "SELECT qty_ordered, qty_received FROM po_item WHERE po_id=?",
            (self._po_id,)
        ).fetchall()
        if all_items:
            all_recv = all(i["qty_received"] >= i["qty_ordered"] for i in all_items)
            any_recv = any(i["qty_received"] > 0 for i in all_items)
            new_status = "received" if all_recv else ("partial" if any_recv else "open")
            conn.execute("UPDATE purchase_order SET status=? WHERE id=?",
                         (new_status, self._po_id))
        conn.commit()
        conn.close()
        self.accept()


# ── Main window ────────────────────────────────────────────────────────────

class Purchasing(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Purchasing")
        self.resize(1150, 700)
        _apply_blue_palette(self)
        self._supp_row_ids = []
        self._po_row_ids   = []
        self._build_ui()
        self._load_suppliers()
        self._refresh_pos()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        outer.addWidget(tabs)
        tabs.addTab(self._build_suppliers_tab(), "Suppliers")
        tabs.addTab(self._build_po_tab(),        "Purchase Orders")

    # ── Suppliers tab ──────────────────────────────────────────────────────

    def _build_suppliers_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.supp_table = QtWidgets.QTableWidget()
        self.supp_table.setColumnCount(7)
        self.supp_table.setHorizontalHeaderLabels(
            ["Company / Name", "Contact", "Phone", "Email", "City", "State", "Zip"])
        hh = self.supp_table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5, 6):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.supp_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.supp_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.supp_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.supp_table.setAlternatingRowColors(True)
        self.supp_table.verticalHeader().setVisible(False)
        self.supp_table.clicked.connect(self._on_supp_row_clicked)
        layout.addWidget(self.supp_table, stretch=1)

        sr = QtWidgets.QHBoxLayout()
        sl = QtWidgets.QLabel("Search:")
        sl.setStyleSheet(LABEL_STYLE)
        sr.addWidget(sl)
        self.supp_search = QtWidgets.QLineEdit()
        self.supp_search.setStyleSheet(INPUT_STYLE)
        self.supp_search.setFixedWidth(220)
        self.supp_search.setPlaceholderText("Company or last name")
        self.supp_search.returnPressed.connect(self._on_supp_search)
        sr.addWidget(self.supp_search)
        for t, fn in (("Search", self._on_supp_search), ("Show All", self._load_suppliers)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            sr.addWidget(b)
        sr.addStretch()
        layout.addLayout(sr)

        fg = QtWidgets.QGroupBox("Supplier Record")
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

        self.sf_company = inp("Company name")
        self.sf_first   = inp("First name")
        self.sf_last    = inp("Last name")
        self.sf_phone   = inp("Phone")
        self.sf_phone.setFixedWidth(140)
        self.sf_email   = inp("Email")
        self.sf_addr    = inp("Street address")
        self.sf_city    = inp("City")
        self.sf_state   = inp("ST")
        self.sf_state.setMaxLength(2)
        self.sf_state.setFixedWidth(44)
        self.sf_zip     = inp("Zip")
        self.sf_zip.setFixedWidth(90)

        grid.addWidget(lbl("Company:"),    0, 0); grid.addWidget(self.sf_company, 0, 1, 1, 3)
        grid.addWidget(lbl("First Name:"), 0, 4); grid.addWidget(self.sf_first,   0, 5)
        grid.addWidget(lbl("Last Name:"),  1, 0); grid.addWidget(self.sf_last,    1, 1, 1, 3)
        grid.addWidget(lbl("Phone:"),      1, 4); grid.addWidget(self.sf_phone,   1, 5)
        grid.addWidget(lbl("Email:"),      2, 0); grid.addWidget(self.sf_email,   2, 1, 1, 5)
        grid.addWidget(lbl("Address:"),    3, 0); grid.addWidget(self.sf_addr,    3, 1, 1, 3)
        grid.addWidget(lbl("City:"),       3, 4); grid.addWidget(self.sf_city,    3, 5)
        grid.addWidget(lbl("State:"),      4, 0); grid.addWidget(self.sf_state,   4, 1)
        grid.addWidget(lbl("Zip:"),        4, 2); grid.addWidget(self.sf_zip,     4, 3)
        layout.addWidget(fg)

        br = QtWidgets.QHBoxLayout()
        for t, fn in (("Add New", self._on_supp_add), ("Update Selected", self._on_supp_update),
                      ("Delete Selected", self._on_supp_delete), ("Clear", self._supp_clear)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(34)
            b.clicked.connect(fn)
            br.addWidget(b)
        br.addStretch()
        layout.addLayout(br)
        return w

    # ── Purchase Orders tab ────────────────────────────────────────────────

    def _build_po_tab(self):
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

        self.po_supp_filter = QtWidgets.QComboBox()
        self.po_supp_filter.setStyleSheet(COMBO_STYLE)
        self.po_supp_filter.setMinimumWidth(200)
        self.po_status_filter = QtWidgets.QComboBox()
        self.po_status_filter.setStyleSheet(COMBO_STYLE)
        self.po_status_filter.addItems(["(all status)", "open", "partial", "received", "cancelled"])
        self.po_from = QtWidgets.QDateEdit()
        self.po_from.setStyleSheet(DATE_STYLE)
        self.po_from.setCalendarPopup(True)
        self.po_from.setDisplayFormat("MM/dd/yyyy")
        self.po_from.setDate(QtCore.QDate.currentDate().addDays(-90))
        self.po_to = QtWidgets.QDateEdit()
        self.po_to.setStyleSheet(DATE_STYLE)
        self.po_to.setCalendarPopup(True)
        self.po_to.setDisplayFormat("MM/dd/yyyy")
        self.po_to.setDate(QtCore.QDate.currentDate())

        fr.addWidget(fl("Supplier:")); fr.addWidget(self.po_supp_filter)
        fr.addWidget(fl("Status:"));   fr.addWidget(self.po_status_filter)
        fr.addWidget(fl("From:"));     fr.addWidget(self.po_from)
        fr.addWidget(fl("To:"));       fr.addWidget(self.po_to)
        for t, fn in (("Apply", self._refresh_pos), ("Show All", self._po_show_all)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            fr.addWidget(b)
        fr.addStretch()
        layout.addLayout(fr)

        self.po_table = QtWidgets.QTableWidget()
        self.po_table.setColumnCount(7)
        self.po_table.setHorizontalHeaderLabels(
            ["PO Number", "Supplier", "Order Date", "Expected Date", "Items", "Total", "Status"])
        hh = self.po_table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (0, 2, 3, 4, 5, 6):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.po_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.po_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.po_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.po_table.verticalHeader().setVisible(False)
        self.po_table.clicked.connect(self._on_po_row_clicked)
        layout.addWidget(self.po_table, stretch=1)

        ar = QtWidgets.QHBoxLayout()
        for t, fn in (("New PO", self._on_new_po),
                      ("Add Line Item", self._on_add_line),
                      ("Receive PO", self._on_receive_po),
                      ("Cancel PO", self._on_cancel_po)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(fn)
            ar.addWidget(b)
        ar.addStretch()
        layout.addLayout(ar)

        self.po_detail_grp = QtWidgets.QGroupBox("PO Line Items")
        self.po_detail_grp.setStyleSheet(
            "QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:6px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;}")
        self.po_detail_grp.setVisible(False)
        dv = QtWidgets.QVBoxLayout(self.po_detail_grp)
        self.po_items_table = QtWidgets.QTableWidget()
        self.po_items_table.setColumnCount(6)
        self.po_items_table.setHorizontalHeaderLabels(
            ["Description", "Product", "Qty Ordered", "Qty Received", "Remaining", "Line Total"])
        ph = self.po_items_table.horizontalHeader()
        ph.setStyleSheet("color:black;font-weight:bold;")
        ph.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5):
            ph.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.po_items_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.po_items_table.setAlternatingRowColors(True)
        self.po_items_table.verticalHeader().setVisible(False)
        self.po_items_table.setFixedHeight(150)
        dv.addWidget(self.po_items_table)
        layout.addWidget(self.po_detail_grp)
        return w

    # ── Supplier data ──────────────────────────────────────────────────────

    def _load_suppliers(self, search=None):
        self.supp_search.blockSignals(True)
        if not search:
            self.supp_search.clear()
        self.supp_search.blockSignals(False)
        conn = get_db()
        if search:
            rows = conn.execute(
                "SELECT * FROM supplier WHERE company_name LIKE ? OR last_name LIKE ? "
                "ORDER BY company_name, last_name, first_name",
                (f"%{search}%", f"%{search}%")
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM supplier ORDER BY company_name, last_name, first_name"
            ).fetchall()
        conn.close()

        self.supp_table.setRowCount(0)
        self._supp_row_ids = []
        for row in rows:
            r = self.supp_table.rowCount()
            self.supp_table.insertRow(r)
            self._supp_row_ids.append(row["id"])
            contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
            primary = (row["company_name"] or "").strip() or contact
            for c, v in enumerate([
                primary,
                contact if (row["company_name"] or "").strip() else "",
                row["phone_number"] or "",
                row["email"] or "",
                row["city"] or "",
                row["state"] or "",
                row["zip_code"] or "",
            ]):
                self.supp_table.setItem(r, c, _ro(v))
        self._refresh_supplier_filters()

    def _refresh_supplier_filters(self):
        conn = get_db()
        suppliers = conn.execute(
            "SELECT id, first_name, last_name, company_name FROM supplier "
            "ORDER BY company_name, last_name, first_name"
        ).fetchall()
        conn.close()
        self.po_supp_filter.blockSignals(True)
        self.po_supp_filter.clear()
        self.po_supp_filter.addItem("(all suppliers)", None)
        for s in suppliers:
            self.po_supp_filter.addItem(_supplier_display(s), s["id"])
        self.po_supp_filter.blockSignals(False)

    def _on_supp_search(self):
        self._load_suppliers(search=self.supp_search.text().strip() or None)

    def _on_supp_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._supp_row_ids):
            return
        conn = get_db()
        s = conn.execute("SELECT * FROM supplier WHERE id=?",
                         (self._supp_row_ids[row],)).fetchone()
        conn.close()
        if not s:
            return
        self.sf_company.setText(s["company_name"] or "")
        self.sf_first.setText(s["first_name"] or "")
        self.sf_last.setText(s["last_name"] or "")
        self.sf_phone.setText(s["phone_number"] or "")
        self.sf_email.setText(s["email"] or "")
        self.sf_addr.setText(s["address"] or "")
        self.sf_city.setText(s["city"] or "")
        self.sf_state.setText(s["state"] or "")
        self.sf_zip.setText(s["zip_code"] or "")

    def _supp_clear(self):
        for w in (self.sf_company, self.sf_first, self.sf_last, self.sf_phone,
                  self.sf_email, self.sf_addr, self.sf_city, self.sf_state, self.sf_zip):
            w.clear()
        self.supp_table.clearSelection()

    def _collect_supplier_form(self):
        company = self.sf_company.text().strip()
        last    = self.sf_last.text().strip()
        if not company and not last:
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Company name or last name is required.")
            return None
        return {
            "company_name": company or "",
            "first_name":   self.sf_first.text().strip() or "",
            "last_name":    last or "",
            "phone_number": self.sf_phone.text().strip() or "",
            "email":        self.sf_email.text().strip() or "",
            "address":      self.sf_addr.text().strip() or "",
            "city":         self.sf_city.text().strip() or "",
            "state":        self.sf_state.text().strip().upper() or "",
            "zip_code":     self.sf_zip.text().strip() or "",
        }

    def _on_supp_add(self):
        data = self._collect_supplier_form()
        if not data:
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO supplier "
            "(company_name,first_name,last_name,phone_number,email,address,city,state,zip_code) "
            "VALUES (:company_name,:first_name,:last_name,:phone_number,"
            ":email,:address,:city,:state,:zip_code)",
            data)
        conn.commit()
        conn.close()
        self._supp_clear()
        self._load_suppliers()

    def _on_supp_update(self):
        row = self.supp_table.currentRow()
        if row < 0 or row >= len(self._supp_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a supplier first.")
            return
        data = self._collect_supplier_form()
        if not data:
            return
        data["id"] = self._supp_row_ids[row]
        conn = get_db()
        conn.execute(
            "UPDATE supplier SET company_name=:company_name,first_name=:first_name,"
            "last_name=:last_name,phone_number=:phone_number,email=:email,"
            "address=:address,city=:city,state=:state,zip_code=:zip_code WHERE id=:id",
            data)
        conn.commit()
        conn.close()
        self._load_suppliers()

    def _on_supp_delete(self):
        row = self.supp_table.currentRow()
        if row < 0 or row >= len(self._supp_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a supplier first.")
            return
        sid = self._supp_row_ids[row]
        conn = get_db()
        po_count = conn.execute(
            "SELECT COUNT(*) FROM purchase_order WHERE supplier_id=?", (sid,)
        ).fetchone()[0]
        conn.close()
        msg = "Delete this supplier?"
        if po_count:
            msg += (f"\n\nWarning: {po_count} purchase order(s) reference this supplier."
                    " They will also be deleted.")
        if (QtWidgets.QMessageBox.question(
                self, "Confirm Delete", msg,
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            conn = get_db()
            po_ids = [r[0] for r in conn.execute(
                "SELECT id FROM purchase_order WHERE supplier_id=?", (sid,)).fetchall()]
            for pid in po_ids:
                conn.execute("DELETE FROM po_item WHERE po_id=?", (pid,))
            conn.execute("DELETE FROM purchase_order WHERE supplier_id=?", (sid,))
            conn.execute("DELETE FROM supplier WHERE id=?", (sid,))
            conn.commit()
            conn.close()
            self._supp_clear()
            self._load_suppliers()
            self._refresh_pos()

    # ── PO data ────────────────────────────────────────────────────────────

    def _refresh_pos(self):
        sid    = self.po_supp_filter.currentData()
        status = self.po_status_filter.currentText()
        from_s = self.po_from.date().toString("yyyy-MM-dd")
        to_s   = self.po_to.date().toString("yyyy-MM-dd")
        conn   = get_db()
        q = (
            "SELECT po.id, po.po_number, po.order_date, po.expected_date, po.status, "
            "s.first_name, s.last_name, s.company_name, "
            "COUNT(pi.id) as item_count, "
            "COALESCE(SUM(pi.qty_ordered * pi.unit_price), 0) as total "
            "FROM purchase_order po "
            "JOIN supplier s ON s.id=po.supplier_id "
            "LEFT JOIN po_item pi ON pi.po_id=po.id "
            "WHERE po.order_date BETWEEN ? AND ?"
        )
        params = [from_s, to_s]
        if sid:
            q += " AND po.supplier_id=?"
            params.append(sid)
        if status != "(all status)":
            q += " AND po.status=?"
            params.append(status)
        q += " GROUP BY po.id ORDER BY po.order_date DESC"
        rows = conn.execute(q, params).fetchall()
        conn.close()

        self.po_table.setRowCount(0)
        self._po_row_ids = []
        right  = QtCore.Qt.AlignmentFlag.AlignRight  | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        left   = QtCore.Qt.AlignmentFlag.AlignLeft   | QtCore.Qt.AlignmentFlag.AlignVCenter
        for row in rows:
            r = self.po_table.rowCount()
            self.po_table.insertRow(r)
            self._po_row_ids.append(row["id"])
            color = PO_COLORS.get(row["status"], QtGui.QColor(255, 255, 255))
            for c, (val, algn) in enumerate([
                (row["po_number"],          left),
                (_supplier_display(row),    left),
                (row["order_date"],         center),
                (row["expected_date"] or "", center),
                (str(row["item_count"]),    center),
                (_money(row["total"]),      right),
                (row["status"].upper(),     center),
            ]):
                item = _ro(val, algn)
                item.setBackground(color)
                self.po_table.setItem(r, c, item)
        self.po_detail_grp.setVisible(False)

    def _po_show_all(self):
        self.po_supp_filter.setCurrentIndex(0)
        self.po_status_filter.setCurrentIndex(0)
        self.po_from.setDate(QtCore.QDate(2000, 1, 1))
        self.po_to.setDate(QtCore.QDate.currentDate())
        self._refresh_pos()

    def _on_po_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._po_row_ids):
            return
        po_id = self._po_row_ids[row]
        conn = get_db()
        items = conn.execute("""
            SELECT pi.*, p.name AS product_name
            FROM po_item pi
            LEFT JOIN product p ON p.id = pi.product_id
            WHERE pi.po_id=? ORDER BY pi.id
        """, (po_id,)).fetchall()
        conn.close()

        self.po_items_table.setRowCount(0)
        right  = QtCore.Qt.AlignmentFlag.AlignRight  | QtCore.Qt.AlignmentFlag.AlignVCenter
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        for item in items:
            r = self.po_items_table.rowCount()
            self.po_items_table.insertRow(r)
            remaining = item["qty_ordered"] - item["qty_received"]
            self.po_items_table.setItem(r, 0, _ro(item["description"]))
            self.po_items_table.setItem(r, 1, _ro(item["product_name"] or ""))
            self.po_items_table.setItem(r, 2, _ro(str(item["qty_ordered"]), center))
            self.po_items_table.setItem(r, 3, _ro(str(item["qty_received"]), center))
            self.po_items_table.setItem(r, 4, _ro(str(remaining), center))
            self.po_items_table.setItem(r, 5, _ro(
                _money(item["qty_ordered"] * item["unit_price"]), right))
        self.po_detail_grp.setVisible(True)

    def _on_new_po(self):
        sid = self.po_supp_filter.currentData()
        dlg = NewPODialog(self, preselect_supplier_id=sid)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_pos()

    def _on_add_line(self):
        row = self.po_table.currentRow()
        if row < 0 or row >= len(self._po_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a PO first.")
            return
        po_id = self._po_row_ids[row]
        conn = get_db()
        status = conn.execute(
            "SELECT status FROM purchase_order WHERE id=?", (po_id,)
        ).fetchone()["status"]
        conn.close()
        if status in ("received", "cancelled"):
            QtWidgets.QMessageBox.information(
                self, "Cannot Edit", f"PO is already {status}.")
            return
        dlg = AddLineItemDialog(po_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_pos()
            for i, pid in enumerate(self._po_row_ids):
                if pid == po_id:
                    self._on_po_row_clicked(self.po_table.model().index(i, 0))
                    break

    def _on_receive_po(self):
        row = self.po_table.currentRow()
        if row < 0 or row >= len(self._po_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a PO first.")
            return
        po_id = self._po_row_ids[row]
        conn = get_db()
        po = conn.execute(
            "SELECT status FROM purchase_order WHERE id=?", (po_id,)
        ).fetchone()
        item_count = conn.execute(
            "SELECT COUNT(*) FROM po_item WHERE po_id=?", (po_id,)
        ).fetchone()[0]
        conn.close()
        if po["status"] in ("received", "cancelled"):
            QtWidgets.QMessageBox.information(
                self, "Cannot Receive", f"PO is already {po['status']}.")
            return
        if item_count == 0:
            QtWidgets.QMessageBox.warning(
                self, "No Items", "Add line items to this PO before receiving.")
            return
        dlg = ReceivePODialog(po_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_pos()
            for i, pid in enumerate(self._po_row_ids):
                if pid == po_id:
                    self._on_po_row_clicked(self.po_table.model().index(i, 0))
                    break

    def _on_cancel_po(self):
        row = self.po_table.currentRow()
        if row < 0 or row >= len(self._po_row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a PO first.")
            return
        po_id = self._po_row_ids[row]
        conn = get_db()
        status = conn.execute(
            "SELECT status FROM purchase_order WHERE id=?", (po_id,)
        ).fetchone()["status"]
        conn.close()
        if status == "cancelled":
            QtWidgets.QMessageBox.information(self, "Already Cancelled", "PO is already cancelled.")
            return
        if (QtWidgets.QMessageBox.question(
                self, "Cancel PO", "Mark this PO as cancelled?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            conn = get_db()
            conn.execute("UPDATE purchase_order SET status='cancelled' WHERE id=?", (po_id,))
            conn.commit()
            conn.close()
            self._refresh_pos()


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = Purchasing()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
