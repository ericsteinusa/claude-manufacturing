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

COLOR_OK       = "#ffffff"
COLOR_LOW      = "#ffe0b2"  # orange tint — at or below reorder point
COLOR_ZERO     = "#ffcccc"  # red tint — zero stock

TRANS_TYPES = ("receive", "issue", "adjust", "return")


def get_db():
    return get_db_connection()


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id SERIAL PRIMARY KEY,
            supplier_id TEXT,
            name TEXT NOT NULL,
            purchase_date TEXT,
            purchase_price REAL DEFAULT 0.0,
            bin TEXT,
            amount INTEGER DEFAULT 0,
            reorder_point INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory_transaction (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES product(id),
            trans_date TEXT,
            trans_type TEXT,
            quantity INTEGER DEFAULT 0,
            reference TEXT,
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


def _row_color(amount, reorder_point):
    amt = amount or 0
    rop = reorder_point or 0
    if amt <= 0:
        return COLOR_ZERO
    if amt <= rop:
        return COLOR_LOW
    return COLOR_OK


# ── Dialogs ────────────────────────────────────────────────────────────────────

class AddProductDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Product / Item")
        self.resize(460, 340)
        _apply_blue_palette(self)
        self.product_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.name = QtWidgets.QLineEdit()
        self.name.setStyleSheet(INPUT_STYLE)
        self.name.setPlaceholderText("Product or part name (required)")
        layout.addRow(lbl("Name:"), self.name)

        self.supplier = QtWidgets.QLineEdit()
        self.supplier.setStyleSheet(INPUT_STYLE)
        self.supplier.setPlaceholderText("Supplier name or ID")
        layout.addRow(lbl("Supplier:"), self.supplier)

        self.bin_loc = QtWidgets.QLineEdit()
        self.bin_loc.setStyleSheet(INPUT_STYLE)
        self.bin_loc.setPlaceholderText("Bin / location")
        layout.addRow(lbl("Bin:"), self.bin_loc)

        self.amount = QtWidgets.QSpinBox()
        self.amount.setRange(0, 9999999)
        self.amount.setValue(0)
        self.amount.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Qty on Hand:"), self.amount)

        self.reorder_point = QtWidgets.QSpinBox()
        self.reorder_point.setRange(0, 9999999)
        self.reorder_point.setValue(0)
        self.reorder_point.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Reorder Point:"), self.reorder_point)

        self.purchase_price = QtWidgets.QDoubleSpinBox()
        self.purchase_price.setRange(0.0, 9999999.99)
        self.purchase_price.setDecimals(2)
        self.purchase_price.setPrefix("$ ")
        self.purchase_price.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Unit Cost:"), self.purchase_price)

        self.purchase_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.purchase_date.setCalendarPopup(True)
        self.purchase_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Purchase Date:"), self.purchase_date)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        name = self.name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Name is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO product (name, supplier_id, bin, amount, reorder_point,"
                " purchase_price, purchase_date) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (name, self.supplier.text().strip(), self.bin_loc.text().strip(),
                 self.amount.value(), self.reorder_point.value(),
                 self.purchase_price.value(),
                 self.purchase_date.date().toString("yyyy-MM-dd"))
            )
            self.product_id = cur.fetchone()['id']
            conn.commit()
        except sqlite3.IntegrityError as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class UpdateProductDialog(QtWidgets.QDialog):
    def __init__(self, product_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Product / Item")
        self.resize(460, 340)
        _apply_blue_palette(self)
        self._product_id = product_id
        self._build_ui()
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
        layout.addRow(lbl("Name:"), self.name)

        self.supplier = QtWidgets.QLineEdit()
        self.supplier.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Supplier:"), self.supplier)

        self.bin_loc = QtWidgets.QLineEdit()
        self.bin_loc.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Bin:"), self.bin_loc)

        self.reorder_point = QtWidgets.QSpinBox()
        self.reorder_point.setRange(0, 9999999)
        self.reorder_point.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Reorder Point:"), self.reorder_point)

        self.purchase_price = QtWidgets.QDoubleSpinBox()
        self.purchase_price.setRange(0.0, 9999999.99)
        self.purchase_price.setDecimals(2)
        self.purchase_price.setPrefix("$ ")
        self.purchase_price.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Unit Cost:"), self.purchase_price)

        self.purchase_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.purchase_date.setCalendarPopup(True)
        self.purchase_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Purchase Date:"), self.purchase_date)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _load(self):
        conn = get_db()
        rec = conn.execute("SELECT * FROM product WHERE id = %s", (self._product_id,)).fetchone()
        conn.close()
        if not rec:
            return
        self.name.setText(rec["name"] or "")
        self.supplier.setText(str(rec["supplier_id"] or ""))
        self.bin_loc.setText(str(rec["bin"] or ""))
        self.reorder_point.setValue(rec["reorder_point"] or 0)
        self.purchase_price.setValue(rec["purchase_price"] or 0.0)
        if rec["purchase_date"]:
            self.purchase_date.setDate(
                QtCore.QDate.fromString(rec["purchase_date"], "yyyy-MM-dd"))

    def _on_ok(self):
        name = self.name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Name is required.")
            return
        conn = get_db()
        conn.execute(
            "UPDATE product SET name=%s, supplier_id=%s, bin=%s, reorder_point=%s,"
            " purchase_price=%s, purchase_date=%s WHERE id=%s",
            (name, self.supplier.text().strip(), self.bin_loc.text().strip(),
             self.reorder_point.value(), self.purchase_price.value(),
             self.purchase_date.date().toString("yyyy-MM-dd"),
             self._product_id)
        )
        conn.commit()
        conn.close()
        self.accept()


class RecordTransactionDialog(QtWidgets.QDialog):
    def __init__(self, product_id, product_name, current_qty, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Record Transaction — {product_name}")
        self.resize(440, 260)
        _apply_blue_palette(self)
        self._product_id = product_id
        self._current_qty = current_qty
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.trans_type = QtWidgets.QComboBox()
        self.trans_type.setStyleSheet(COMBO_STYLE)
        for t in TRANS_TYPES:
            self.trans_type.addItem(t.capitalize(), t)
        layout.addRow(lbl("Type:"), self.trans_type)

        self.quantity = QtWidgets.QSpinBox()
        self.quantity.setRange(1, 9999999)
        self.quantity.setValue(1)
        self.quantity.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Quantity:"), self.quantity)

        self.trans_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.trans_date.setCalendarPopup(True)
        self.trans_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Date:"), self.trans_date)

        self.reference = QtWidgets.QLineEdit()
        self.reference.setStyleSheet(INPUT_STYLE)
        self.reference.setPlaceholderText("PO#, WO#, or other reference")
        layout.addRow(lbl("Reference:"), self.reference)

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
        trans_type = self.trans_type.currentData()
        qty = self.quantity.value()

        # Determine new stock level
        if trans_type in ("receive", "return"):
            new_qty = self._current_qty + qty
        elif trans_type == "issue":
            new_qty = self._current_qty - qty
        else:  # adjust — set absolute value
            new_qty = qty

        conn = get_db()
        conn.execute(
            "INSERT INTO inventory_transaction"
            " (product_id, trans_date, trans_type, quantity, reference, notes)"
            " VALUES (%s,%s,%s,%s,%s,%s)",
            (self._product_id,
             self.trans_date.date().toString("yyyy-MM-dd"),
             trans_type, qty,
             self.reference.text().strip(),
             self.notes.text().strip())
        )
        conn.execute(
            "UPDATE product SET amount = %s WHERE id = %s",
            (new_qty, self._product_id)
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ────────────────────────────────────────────────────────────────

class InventoryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._prod_row_ids = []
        self._selected_product_id = None
        self._selected_product_name = None
        self._selected_qty = 0
        self._build_ui()
        init_db()
        self._refresh_inventory()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # filter row
        fr = QtWidgets.QHBoxLayout()

        lbl_srch = QtWidgets.QLabel("Search:")
        lbl_srch.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_srch)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setStyleSheet(INPUT_STYLE)
        self.search_edit.setPlaceholderText("Name or bin…")
        self.search_edit.setFixedWidth(180)
        self.search_edit.textChanged.connect(self._refresh_inventory)
        fr.addWidget(self.search_edit)

        fr.addSpacing(10)
        self.low_stock_only = QtWidgets.QCheckBox("Low Stock Only")
        self.low_stock_only.setStyleSheet("color: white; font-size: 13px;")
        self.low_stock_only.stateChanged.connect(self._refresh_inventory)
        fr.addWidget(self.low_stock_only)

        fr.addSpacing(10)
        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.inv_table = QtWidgets.QTableWidget()
        self.inv_table.setColumnCount(7)
        self.inv_table.setHorizontalHeaderLabels(
            ["Name", "Bin", "Qty on Hand", "Reorder Point", "Unit Cost", "Supplier", "Status"]
        )
        hh = self.inv_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.inv_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inv_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.inv_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.inv_table.setAlternatingRowColors(True)
        self.inv_table.verticalHeader().setVisible(False)
        self.inv_table.clicked.connect(self._on_product_clicked)
        splitter.addWidget(self.inv_table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Transaction History")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.txn_table = QtWidgets.QTableWidget()
        self.txn_table.setColumnCount(5)
        self.txn_table.setHorizontalHeaderLabels(
            ["Date", "Type", "Quantity", "Reference", "Notes"]
        )
        ih = self.txn_table.horizontalHeader()
        ih.setStyleSheet("color: black; font-weight: bold;")
        ih.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.txn_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.txn_table.verticalHeader().setVisible(False)
        self.txn_table.setAlternatingRowColors(True)
        dv.addWidget(self.txn_table)
        splitter.addWidget(detail_w)
        splitter.setSizes([400, 200])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add Product",        self._on_add_product),
            ("Update Product",     self._on_update_product),
            ("Receive Stock",      lambda: self._quick_trans("receive")),
            ("Issue Stock",        lambda: self._quick_trans("issue")),
            ("Record Transaction", self._on_record_transaction),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh_inventory(self):
        search = self.search_edit.text().strip().lower()
        low_only = self.low_stock_only.isChecked()

        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT id, name, bin, amount, reorder_point, purchase_price, supplier_id"
                " FROM product ORDER BY name"
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        conn.close()

        self.inv_table.setRowCount(0)
        self._prod_row_ids = []
        for row in rows:
            name = row["name"] or ""
            bin_loc = str(row["bin"] or "")
            amt = row["amount"] or 0
            rop = row["reorder_point"] or 0

            if search and search not in name.lower() and search not in bin_loc.lower():
                continue
            if low_only and amt > rop:
                continue

            r = self.inv_table.rowCount()
            self.inv_table.insertRow(r)
            self._prod_row_ids.append(row["id"])

            if amt <= 0:
                status = "Out of Stock"
            elif amt <= rop:
                status = "Low Stock"
            else:
                status = "OK"

            self.inv_table.setItem(r, 0, _ro(name))
            self.inv_table.setItem(r, 1, _ro(bin_loc))
            self.inv_table.setItem(r, 2, _ro(str(amt)))
            self.inv_table.setItem(r, 3, _ro(str(rop)))
            self.inv_table.setItem(r, 4, _ro(f"${row['purchase_price'] or 0:.2f}"))
            self.inv_table.setItem(r, 5, _ro(str(row["supplier_id"] or "")))
            self.inv_table.setItem(r, 6, _ro(status))

            bg = QtGui.QColor(_row_color(amt, rop))
            for col in range(7):
                self.inv_table.item(r, col).setBackground(bg)

        self._selected_product_id = None
        self._selected_product_name = None
        self._selected_qty = 0
        self.txn_table.setRowCount(0)

    def _on_show_all(self):
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self.low_stock_only.blockSignals(True)
        self.low_stock_only.setChecked(False)
        self.low_stock_only.blockSignals(False)
        self._refresh_inventory()

    def _on_product_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._prod_row_ids):
            return
        self._selected_product_id = self._prod_row_ids[row]
        self._selected_product_name = self.inv_table.item(row, 0).text()
        try:
            self._selected_qty = int(self.inv_table.item(row, 2).text())
        except ValueError:
            self._selected_qty = 0
        self._refresh_transactions()

    def _refresh_transactions(self):
        self.txn_table.setRowCount(0)
        if self._selected_product_id is None:
            return
        conn = get_db()
        try:
            txns = conn.execute(
                "SELECT trans_date, trans_type, quantity, reference, notes"
                " FROM inventory_transaction WHERE product_id = %s"
                " ORDER BY trans_date DESC, id DESC",
                (self._selected_product_id,)
            ).fetchall()
        except sqlite3.OperationalError:
            txns = []
        conn.close()
        for txn in txns:
            r = self.txn_table.rowCount()
            self.txn_table.insertRow(r)
            self.txn_table.setItem(r, 0, _ro(txn["trans_date"] or ""))
            self.txn_table.setItem(r, 1, _ro((txn["trans_type"] or "").capitalize()))
            self.txn_table.setItem(r, 2, _ro(str(txn["quantity"])))
            self.txn_table.setItem(r, 3, _ro(txn["reference"] or ""))
            self.txn_table.setItem(r, 4, _ro(txn["notes"] or ""))

    def _on_add_product(self):
        dlg = AddProductDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_inventory()

    def _on_update_product(self):
        if self._selected_product_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a product first.")
            return
        dlg = UpdateProductDialog(self._selected_product_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_inventory()

    def _on_record_transaction(self):
        if self._selected_product_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a product first.")
            return
        dlg = RecordTransactionDialog(
            self._selected_product_id, self._selected_product_name,
            self._selected_qty, self
        )
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_inventory()
            # Re-select to refresh transactions
            for i, pid in enumerate(self._prod_row_ids):
                if pid == self._selected_product_id:
                    self.inv_table.selectRow(i)
                    self._on_product_clicked(self.inv_table.model().index(i, 0))
                    break

    def _quick_trans(self, trans_type):
        """Open transaction dialog pre-set to a specific type."""
        if self._selected_product_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a product first.")
            return
        dlg = RecordTransactionDialog(
            self._selected_product_id, self._selected_product_name,
            self._selected_qty, self
        )
        # Pre-select the transaction type
        for i in range(dlg.trans_type.count()):
            if dlg.trans_type.itemData(i) == trans_type:
                dlg.trans_type.setCurrentIndex(i)
                break
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_inventory()
            for i, pid in enumerate(self._prod_row_ids):
                if pid == self._selected_product_id:
                    self.inv_table.selectRow(i)
                    self._on_product_clicked(self.inv_table.model().index(i, 0))
                    break


class InventoryWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inventory")
        self.resize(1020, 680)
        _apply_blue_palette(self)
        self.setCentralWidget(InventoryWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = InventoryWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
