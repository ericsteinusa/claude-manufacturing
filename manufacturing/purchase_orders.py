import sys
import sqlite3
from .db_connection import get_db_connection
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

PO_COLORS = {
    "draft":     "#ffffff",
    "sent":      "#cce5ff",
    "partial":   "#fff3cd",
    "received":  "#d4edda",
    "cancelled": "#dcdcdc",
}


def get_db():
    return get_db_connection()


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase_order (
            id SERIAL PRIMARY KEY,
            po_number TEXT NOT NULL UNIQUE,
            supplier_id INTEGER,
            order_date TEXT,
            expected_date TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS po_item (
            id SERIAL PRIMARY KEY,
            po_id INTEGER NOT NULL REFERENCES purchase_order(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty_ordered INTEGER DEFAULT 1,
            unit_price REAL DEFAULT 0.0,
            qty_received INTEGER DEFAULT 0
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


def _next_po_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM purchase_order WHERE po_number LIKE %s", (f"PO-{yr}-%",)
    ).fetchone()[0]
    conn.close()
    return f"PO-{yr}-{count + 1:04d}"


def _load_suppliers():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, company_name FROM supplier ORDER BY company_name"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return rows


def _load_products():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, product_name FROM product ORDER BY product_name"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return rows


# ── Dialogs ────────────────────────────────────────────────────────────────────

class NewPODialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Purchase Order")
        self.resize(500, 340)
        _apply_blue_palette(self)
        self.po_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.po_num = QtWidgets.QLineEdit(_next_po_num())
        self.po_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("PO Number:"), self.po_num)

        self.supplier_combo = QtWidgets.QComboBox()
        self.supplier_combo.setStyleSheet(COMBO_STYLE)
        self.supplier_combo.addItem("(none)", None)
        for s in _load_suppliers():
            self.supplier_combo.addItem(s["company_name"], s["id"])
        layout.addRow(lbl("Supplier:"), self.supplier_combo)

        self.order_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.order_date.setCalendarPopup(True)
        self.order_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Order Date:"), self.order_date)

        self.expected_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addDays(14))
        self.expected_date.setCalendarPopup(True)
        self.expected_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Expected Date:"), self.expected_date)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("draft", "sent"):
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
        po_num = self.po_num.text().strip()
        if not po_num:
            QtWidgets.QMessageBox.warning(self, "Input Error", "PO number is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO purchase_order (po_number, supplier_id, order_date,"
                " expected_date, status, notes) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (po_num, self.supplier_combo.currentData(),
                 self.order_date.date().toString("yyyy-MM-dd"),
                 self.expected_date.date().toString("yyyy-MM-dd"),
                 self.status_combo.currentData(),
                 self.notes.text().strip())
            )
            self.po_id = cur.fetchone()['id']
            conn.commit()
        except sqlite3.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"PO number '{po_num}' already exists.")
            conn.close()
            return
        conn.close()
        self.accept()


class AddPOItemDialog(QtWidgets.QDialog):
    def __init__(self, po_id, po_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Item — {po_number}")
        self.resize(460, 260)
        _apply_blue_palette(self)
        self._po_id = po_id
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
        self.product_combo.currentIndexChanged.connect(self._on_product_changed)
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
        layout.addRow(lbl("Qty Ordered:"), self.qty)

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
            QtWidgets.QMessageBox.warning(self, "Input Error", "Description is required.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO po_item (po_id, description, product_id, qty_ordered, unit_price)"
            " VALUES (%s,%s,%s,%s,%s)",
            (self._po_id, desc, self.product_combo.currentData(),
             self.qty.value(), self.unit_price.value())
        )
        conn.commit()
        conn.close()
        self.accept()


class UpdatePODialog(QtWidgets.QDialog):
    """Edit supplier, dates, and notes on an existing PO."""

    def __init__(self, po_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Purchase Order")
        self.resize(420, 280)
        _apply_blue_palette(self)
        self._po_id = po_id
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.supplier_combo = QtWidgets.QComboBox()
        self.supplier_combo.setStyleSheet(COMBO_STYLE)
        self.supplier_combo.addItem("(none)", None)
        for s in _load_suppliers():
            self.supplier_combo.addItem(s["company_name"], s["id"])
        layout.addRow(lbl("Supplier:"), self.supplier_combo)

        self.order_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.order_date.setCalendarPopup(True)
        self.order_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Order Date:"), self.order_date)

        self.expected_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.expected_date.setCalendarPopup(True)
        self.expected_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Expected Date:"), self.expected_date)

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
        rec = conn.execute("SELECT * FROM purchase_order WHERE id = %s", (self._po_id,)).fetchone()
        conn.close()
        if not rec:
            return
        # Set supplier
        for i in range(self.supplier_combo.count()):
            if self.supplier_combo.itemData(i) == rec["supplier_id"]:
                self.supplier_combo.setCurrentIndex(i)
                break
        if rec["order_date"]:
            self.order_date.setDate(QtCore.QDate.fromString(rec["order_date"], "yyyy-MM-dd"))
        if rec["expected_date"]:
            self.expected_date.setDate(QtCore.QDate.fromString(rec["expected_date"], "yyyy-MM-dd"))
        self.notes.setText(rec["notes"] or "")

    def _on_ok(self):
        conn = get_db()
        conn.execute(
            "UPDATE purchase_order SET supplier_id=%s, order_date=%s,"
            " expected_date=%s, notes=%s WHERE id=%s",
            (self.supplier_combo.currentData(),
             self.order_date.date().toString("yyyy-MM-dd"),
             self.expected_date.date().toString("yyyy-MM-dd"),
             self.notes.text().strip(), self._po_id)
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ────────────────────────────────────────────────────────────────

class PurchaseOrdersWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._po_row_ids = []
        self._selected_po_id = None
        self._selected_po_number = None
        self._build_ui()
        init_db()
        self._refresh_pos()

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
        for s in ("draft", "sent", "partial", "received", "cancelled"):
            self.status_filter.addItem(s.capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh_pos)
        fr.addWidget(self.status_filter)

        fr.addSpacing(10)
        lbl_sup = QtWidgets.QLabel("Supplier:")
        lbl_sup.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_sup)
        self.supplier_filter = QtWidgets.QComboBox()
        self.supplier_filter.setStyleSheet(COMBO_STYLE)
        self.supplier_filter.setMinimumWidth(140)
        self.supplier_filter.addItem("(all)", None)
        for s in _load_suppliers():
            self.supplier_filter.addItem(s["company_name"], s["id"])
        self.supplier_filter.currentIndexChanged.connect(self._refresh_pos)
        fr.addWidget(self.supplier_filter)

        fr.addSpacing(10)
        lbl_f = QtWidgets.QLabel("From:")
        lbl_f.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_f)
        self.date_from = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet(INPUT_STYLE)
        self.date_from.dateChanged.connect(self._refresh_pos)
        fr.addWidget(self.date_from)

        lbl_t = QtWidgets.QLabel("To:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.date_to = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet(INPUT_STYLE)
        self.date_to.dateChanged.connect(self._refresh_pos)
        fr.addWidget(self.date_to)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.po_table = QtWidgets.QTableWidget()
        self.po_table.setColumnCount(8)
        self.po_table.setHorizontalHeaderLabels(
            ["PO #", "Supplier", "Order Date", "Expected Date", "Items", "Total", "Status", "Notes"]
        )
        hh = self.po_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.po_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.po_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.po_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.po_table.setAlternatingRowColors(True)
        self.po_table.verticalHeader().setVisible(False)
        self.po_table.clicked.connect(self._on_po_clicked)
        splitter.addWidget(self.po_table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Line Items")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.item_table = QtWidgets.QTableWidget()
        self.item_table.setColumnCount(5)
        self.item_table.setHorizontalHeaderLabels(
            ["Description", "Product", "Qty Ordered", "Unit Price", "Qty Received"]
        )
        ih = self.item_table.horizontalHeader()
        ih.setStyleSheet("color: black; font-weight: bold;")
        ih.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        ih.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.item_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.item_table.verticalHeader().setVisible(False)
        self.item_table.setAlternatingRowColors(True)
        dv.addWidget(self.item_table)
        splitter.addWidget(detail_w)
        splitter.setSizes([400, 180])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New PO",        self._on_new_po),
            ("Add Item",      self._on_add_item),
            ("Update PO",     self._on_update_po),
            ("Mark Sent",     lambda: self._set_status("sent",      "Mark PO as Sent?")),
            ("Mark Partial",  lambda: self._set_status("partial",   "Mark as Partial Receipt?")),
            ("Mark Received", lambda: self._set_status("received",  "Mark as Fully Received?")),
            ("Cancel PO",     lambda: self._set_status("cancelled", "Cancel this PO?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh_pos(self):
        status = self.status_filter.currentData()
        supplier_id = self.supplier_filter.currentData()
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")

        base = """
            SELECT po.id, po.po_number, po.order_date, po.expected_date,
                   po.status, po.notes, s.company_name,
                   (SELECT COUNT(*) FROM po_item pi WHERE pi.po_id = po.id) AS item_count,
                   (SELECT COALESCE(SUM(pi.qty_ordered * pi.unit_price),0)
                    FROM po_item pi WHERE pi.po_id = po.id) AS total
            FROM purchase_order po
            LEFT JOIN supplier s ON s.id = po.supplier_id
        """
        conds, params = [], []
        if status:
            conds.append("po.status = %s")
            params.append(status)
        if supplier_id:
            conds.append("po.supplier_id = %s")
            params.append(supplier_id)
        conds.append("(po.order_date IS NULL OR po.order_date BETWEEN %s AND %s)")
        params += [d_from, d_to]
        where = " WHERE " + " AND ".join(conds)

        conn = get_db()
        try:
            rows = conn.execute(base + where + " ORDER BY po.order_date DESC", params).fetchall()
        except sqlite3.OperationalError:
            rows = []
        conn.close()

        self.po_table.setRowCount(0)
        self._po_row_ids = []
        for row in rows:
            r = self.po_table.rowCount()
            self.po_table.insertRow(r)
            self._po_row_ids.append(row["id"])
            self.po_table.setItem(r, 0, _ro(row["po_number"]))
            self.po_table.setItem(r, 1, _ro(row["company_name"] or ""))
            self.po_table.setItem(r, 2, _ro(row["order_date"] or ""))
            self.po_table.setItem(r, 3, _ro(row["expected_date"] or ""))
            self.po_table.setItem(r, 4, _ro(str(row["item_count"])))
            self.po_table.setItem(r, 5, _ro(f"${row['total']:,.2f}"))
            self.po_table.setItem(r, 6, _ro(row["status"].capitalize()))
            self.po_table.setItem(r, 7, _ro(row["notes"] or ""))
            bg = QtGui.QColor(PO_COLORS.get(row["status"], "#ffffff"))
            for col in range(8):
                self.po_table.item(r, col).setBackground(bg)

        self._selected_po_id = None
        self._selected_po_number = None
        self.item_table.setRowCount(0)

    def _on_show_all(self):
        for widget, val in (
            (self.status_filter,   0),
            (self.supplier_filter, 0),
        ):
            widget.blockSignals(True)
            widget.setCurrentIndex(val)
            widget.blockSignals(False)
        self.date_from.blockSignals(True)
        self.date_from.setDate(QtCore.QDate(2000, 1, 1))
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(True)
        self.date_to.setDate(QtCore.QDate.currentDate())
        self.date_to.blockSignals(False)
        self._refresh_pos()

    def _on_po_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._po_row_ids):
            return
        self._selected_po_id = self._po_row_ids[row]
        self._selected_po_number = self.po_table.item(row, 0).text()
        self._refresh_items()

    def _refresh_items(self):
        self.item_table.setRowCount(0)
        if self._selected_po_id is None:
            return
        conn = get_db()
        try:
            items = conn.execute("""
                SELECT pi.description, p.product_name, pi.qty_ordered,
                       pi.unit_price, pi.qty_received
                FROM po_item pi LEFT JOIN product p ON p.id = pi.product_id
                WHERE pi.po_id = %s
            """, (self._selected_po_id,)).fetchall()
        except sqlite3.OperationalError:
            items = []
        conn.close()
        for item in items:
            r = self.item_table.rowCount()
            self.item_table.insertRow(r)
            self.item_table.setItem(r, 0, _ro(item["description"]))
            self.item_table.setItem(r, 1, _ro(item["product_name"] or ""))
            self.item_table.setItem(r, 2, _ro(str(item["qty_ordered"])))
            self.item_table.setItem(r, 3, _ro(f"${item['unit_price']:,.2f}"))
            self.item_table.setItem(r, 4, _ro(str(item["qty_received"])))

    def _on_new_po(self):
        dlg = NewPODialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_pos()

    def _on_add_item(self):
        if self._selected_po_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a PO first.")
            return
        dlg = AddPOItemDialog(self._selected_po_id, self._selected_po_number, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_pos()
            self._refresh_items()

    def _on_update_po(self):
        if self._selected_po_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a PO first.")
            return
        dlg = UpdatePODialog(self._selected_po_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_pos()

    def _set_status(self, new_status, msg):
        if self._selected_po_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a PO first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE purchase_order SET status = %s WHERE id = %s",
                         (new_status, self._selected_po_id))
            conn.commit()
            conn.close()
            self._refresh_pos()


class PurchaseOrdersWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Purchase Orders")
        self.resize(1020, 680)
        _apply_blue_palette(self)
        self.setCentralWidget(PurchaseOrdersWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = PurchaseOrdersWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
