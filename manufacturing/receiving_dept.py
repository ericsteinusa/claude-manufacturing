import sys
import psycopg2
from .db_pg import get_db_connection
from PyQt6 import QtCore, QtGui, QtWidgets


def get_db():
    return get_db_connection()


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

RCV_COLORS = {
    "pending":  "#ffffff",
    "partial":  "#fff3cd",
    "received": "#d4edda",
    "rejected": "#dcdcdc",
}


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS receiving (
            id SERIAL PRIMARY KEY,
            rcv_number TEXT NOT NULL UNIQUE,
            po_id INTEGER,
            rcv_date TEXT,
            supplier TEXT,
            carrier TEXT,
            tracking_number TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS receiving_item (
            id SERIAL PRIMARY KEY,
            receiving_id INTEGER NOT NULL REFERENCES receiving(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty_ordered INTEGER DEFAULT 1,
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


def _next_rcv_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM receiving WHERE rcv_number LIKE %s", (
            f"RCV-{yr}-%",)
    ).fetchone()[0]
    conn.close()
    return f"RCV-{yr}-{count + 1:04d}"


# ── Dialogs ─────────────────────────────────────────────────────────────

class NewReceiptDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Receipt")
        self.resize(480, 330)
        _apply_blue_palette(self)
        self.receiving_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.rcv_num = QtWidgets.QLineEdit(_next_rcv_num())
        self.rcv_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Receipt #:"), self.rcv_num)

        self.po_combo = QtWidgets.QComboBox()
        self.po_combo.setStyleSheet(COMBO_STYLE)
        conn = get_db()
        try:
            pos = conn.execute(
                "SELECT id, po_number FROM purchase_order"
                " WHERE status NOT IN ('cancelled','closed') ORDER BY "
                "po_number"
            ).fetchall()
        except psycopg2.OperationalError:
            pos = []
        conn.close()
        self.po_combo.addItem("(none)", None)
        for p in pos:
            self.po_combo.addItem(p["po_number"], p["id"])
        layout.addRow(lbl("Purchase Order:"), self.po_combo)

        self.rcv_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.rcv_date.setCalendarPopup(True)
        self.rcv_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Receive Date:"), self.rcv_date)

        self.supplier = QtWidgets.QLineEdit()
        self.supplier.setStyleSheet(INPUT_STYLE)
        self.supplier.setPlaceholderText("Supplier name")
        layout.addRow(lbl("Supplier:"), self.supplier)

        self.carrier = QtWidgets.QLineEdit()
        self.carrier.setStyleSheet(INPUT_STYLE)
        self.carrier.setPlaceholderText("e.g. UPS, FedEx, USPS")
        layout.addRow(lbl("Carrier:"), self.carrier)

        self.tracking = QtWidgets.QLineEdit()
        self.tracking.setStyleSheet(INPUT_STYLE)
        self.tracking.setPlaceholderText("Tracking number")
        layout.addRow(lbl("Tracking #:"), self.tracking)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("pending", "partial"):
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
        rcv_num = self.rcv_num.text().strip()
        if not rcv_num:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Receipt number is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO receiving (rcv_number, po_id, rcv_date, "
                "supplier, carrier,"
                " tracking_number, status, notes) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (rcv_num, self.po_combo.currentData(),
                 self.rcv_date.date().toString("yyyy-MM-dd"),
                 self.supplier.text().strip(), self.carrier.text().strip(),
                 self.tracking.text().strip(), self.status_combo.currentData(),
                 self.notes.text().strip())
            )
            self.receiving_id = cur.fetchone()['id']
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"Receipt number '{rcv_num}' already exists.")  # noqa: E501
            conn.close()
            return
        conn.close()
        self.accept()


class AddReceiptItemDialog(QtWidgets.QDialog):
    def __init__(self, receiving_id, rcv_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Item — {rcv_number}")
        self.resize(440, 240)
        _apply_blue_palette(self)
        self._receiving_id = receiving_id
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
        conn = get_db()
        try:
            prods = conn.execute(
                "SELECT id, product_name FROM product ORDER BY product_name"
            ).fetchall()
        except psycopg2.OperationalError:
            prods = []
        conn.close()
        self.product_combo.addItem("(none)", None)
        for p in prods:
            self.product_combo.addItem(p["product_name"], p["id"])
        layout.addRow(lbl("Product (opt):"), self.product_combo)

        self.desc = QtWidgets.QLineEdit()
        self.desc.setStyleSheet(INPUT_STYLE)
        self.desc.setPlaceholderText("Description (required)")
        layout.addRow(lbl("Description:"), self.desc)

        self.qty_ordered = QtWidgets.QSpinBox()
        self.qty_ordered.setRange(1, 999999)
        self.qty_ordered.setValue(1)
        self.qty_ordered.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Qty Ordered:"), self.qty_ordered)

        self.qty_received = QtWidgets.QSpinBox()
        self.qty_received.setRange(0, 999999)
        self.qty_received.setValue(0)
        self.qty_received.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Qty Received:"), self.qty_received)

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
            "INSERT INTO receiving_item"
            " (receiving_id, description, product_id, qty_ordered, "
            "qty_received)"
            " VALUES (%s,%s,%s,%s,%s)",
            (self._receiving_id, desc, self.product_combo.currentData(),
             self.qty_ordered.value(), self.qty_received.value())
        )
        conn.commit()
        conn.close()
        self.accept()


class UpdateReceiptDialog(QtWidgets.QDialog):
    """Edit carrier/tracking/notes on an existing receipt."""

    def __init__(self, receiving_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Receipt")
        self.resize(400, 240)
        _apply_blue_palette(self)
        self._receiving_id = receiving_id
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.rcv_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.rcv_date.setCalendarPopup(True)
        self.rcv_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Receive Date:"), self.rcv_date)

        self.supplier = QtWidgets.QLineEdit()
        self.supplier.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Supplier:"), self.supplier)

        self.carrier = QtWidgets.QLineEdit()
        self.carrier.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Carrier:"), self.carrier)

        self.tracking = QtWidgets.QLineEdit()
        self.tracking.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Tracking #:"), self.tracking)

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
    "SELECT * FROM receiving WHERE id = %s",
    (self._receiving_id,
    )).fetchone()
        conn.close()
        if not rec:
            return
        if rec["rcv_date"]:
            self.rcv_date.setDate(
    QtCore.QDate.fromString(
        rec["rcv_date"], "yyyy-MM-dd"))
        self.supplier.setText(rec["supplier"] or "")
        self.carrier.setText(rec["carrier"] or "")
        self.tracking.setText(rec["tracking_number"] or "")
        self.notes.setText(rec["notes"] or "")

    def _on_ok(self):
        conn = get_db()
        conn.execute(
            "UPDATE receiving SET rcv_date=%s, supplier=%s, carrier=%s,"
            " tracking_number=%s, notes=%s WHERE id=%s",
            (self.rcv_date.date().toString("yyyy-MM-dd"),
             self.supplier.text().strip(), self.carrier.text().strip(),
             self.tracking.text().strip(), self.notes.text().strip(),
             self._receiving_id)
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ─────────────────────────────────────────────────────────

class ReceivingDeptWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._rcv_row_ids = []
        self._selected_rcv_id = None
        self._selected_rcv_number = None
        self._build_ui()
        init_db()
        self._refresh_receipts()

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
        for s in ("pending", "partial", "received", "rejected"):
            self.status_filter.addItem(s.capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh_receipts)
        fr.addWidget(self.status_filter)

        fr.addSpacing(10)
        lbl_f = QtWidgets.QLabel("From:")
        lbl_f.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_f)
        self.date_from = QtWidgets.QDateEdit(
            QtCore.QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet(INPUT_STYLE)
        self.date_from.dateChanged.connect(self._refresh_receipts)
        fr.addWidget(self.date_from)

        lbl_t = QtWidgets.QLabel("To:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.date_to = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet(INPUT_STYLE)
        self.date_to.dateChanged.connect(self._refresh_receipts)
        fr.addWidget(self.date_to)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.rcv_table = QtWidgets.QTableWidget()
        self.rcv_table.setColumnCount(8)
        self.rcv_table.setHorizontalHeaderLabels(
            ["Receipt #", "PO #", "Receive Date", "Supplier",
                "Carrier", "Tracking #", "Items", "Status"]
        )
        hh = self.rcv_table.horizontalHeader()
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
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    6, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    7, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.rcv_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rcv_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.rcv_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.rcv_table.setAlternatingRowColors(True)
        self.rcv_table.verticalHeader().setVisible(False)
        self.rcv_table.clicked.connect(self._on_receipt_clicked)
        splitter.addWidget(self.rcv_table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Receipt Items")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.item_table = QtWidgets.QTableWidget()
        self.item_table.setColumnCount(4)
        self.item_table.setHorizontalHeaderLabels(
            ["Description", "Product", "Qty Ordered", "Qty Received"])
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
        splitter.setSizes([380, 180])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Receipt", self._on_new_receipt),
            ("Add Item", self._on_add_item),
            ("Update Details", self._on_update_receipt),
            ("Mark Partial", lambda: self._set_status(
                "partial", "Mark as Partial Receipt?")),
            ("Mark Received", lambda: self._set_status(
                "received", "Mark as Fully Received?")),
            ("Mark Rejected", lambda: self._set_status(
                "rejected", "Mark as Rejected?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh_receipts(self):
        status = self.status_filter.currentData()
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")

        base = """
            SELECT r.id, r.rcv_number, r.rcv_date, r.supplier, r.carrier,
                   r.tracking_number, r.status, po.po_number,
                   (SELECT COUNT(*) FROM receiving_item ri WHERE
                       ri.receiving_id = r.id) AS item_count
            FROM receiving r
            LEFT JOIN purchase_order po ON po.id = r.po_id
        """
        conds, params = [], []
        if status:
            conds.append("r.status = %s")
            params.append(status)
        conds.append("(r.rcv_date IS NULL OR r.rcv_date BETWEEN %s AND %s)")
        params += [d_from, d_to]
        where = " WHERE " + " AND ".join(conds)

        conn = get_db()
        try:
            rows = conn.execute(
    base + where + " ORDER BY r.rcv_date DESC",
     params).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.rcv_table.setRowCount(0)
        self._rcv_row_ids = []
        for row in rows:
            r = self.rcv_table.rowCount()
            self.rcv_table.insertRow(r)
            self._rcv_row_ids.append(row["id"])
            self.rcv_table.setItem(r, 0, _ro(row["rcv_number"]))
            self.rcv_table.setItem(r, 1, _ro(row["po_number"] or ""))
            self.rcv_table.setItem(r, 2, _ro(row["rcv_date"] or ""))
            self.rcv_table.setItem(r, 3, _ro(row["supplier"] or ""))
            self.rcv_table.setItem(r, 4, _ro(row["carrier"] or ""))
            self.rcv_table.setItem(r, 5, _ro(row["tracking_number"] or ""))
            self.rcv_table.setItem(r, 6, _ro(str(row["item_count"])))
            self.rcv_table.setItem(r, 7, _ro(row["status"].capitalize()))
            bg = QtGui.QColor(RCV_COLORS.get(row["status"], "#ffffff"))
            for col in range(8):
                self.rcv_table.item(r, col).setBackground(bg)

        self._selected_rcv_id = None
        self._selected_rcv_number = None
        self.item_table.setRowCount(0)

    def _on_show_all(self):
        self.status_filter.blockSignals(True)
        self.status_filter.setCurrentIndex(0)
        self.status_filter.blockSignals(False)
        self.date_from.blockSignals(True)
        self.date_from.setDate(QtCore.QDate(2000, 1, 1))
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(True)
        self.date_to.setDate(QtCore.QDate.currentDate())
        self.date_to.blockSignals(False)
        self._refresh_receipts()

    def _on_receipt_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._rcv_row_ids):
            return
        self._selected_rcv_id = self._rcv_row_ids[row]
        self._selected_rcv_number = self.rcv_table.item(row, 0).text()
        self._refresh_items()

    def _refresh_items(self):
        self.item_table.setRowCount(0)
        if self._selected_rcv_id is None:
            return
        conn = get_db()
        try:
            items = conn.execute("""
                SELECT ri.description, p.product_name, ri.qty_ordered,
                    ri.qty_received
                FROM receiving_item ri LEFT JOIN product p ON p.id =
                    ri.product_id
                WHERE ri.receiving_id = %s
            """, (self._selected_rcv_id,)).fetchall()
        except psycopg2.OperationalError:
            items = conn.execute(
                "SELECT description, NULL AS product_name, qty_ordered, "
                "qty_received"
                " FROM receiving_item WHERE receiving_id = %s",
                (self._selected_rcv_id,)
            ).fetchall()
        conn.close()
        for item in items:
            r = self.item_table.rowCount()
            self.item_table.insertRow(r)
            self.item_table.setItem(r, 0, _ro(item["description"]))
            self.item_table.setItem(r, 1, _ro(item["product_name"] or ""))
            self.item_table.setItem(r, 2, _ro(str(item["qty_ordered"])))
            self.item_table.setItem(r, 3, _ro(str(item["qty_received"])))

    def _on_new_receipt(self):
        dlg = NewReceiptDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_receipts()

    def _on_add_item(self):
        if self._selected_rcv_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a receipt first.")
            return
        dlg = AddReceiptItemDialog(
    self._selected_rcv_id,
    self._selected_rcv_number,
     self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_receipts()
            self._refresh_items()

    def _on_update_receipt(self):
        if self._selected_rcv_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a receipt first.")
            return
        dlg = UpdateReceiptDialog(self._selected_rcv_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_receipts()

    def _set_status(self, new_status, msg):
        if self._selected_rcv_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a receipt first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE receiving SET status = %s WHERE id = %s",
                         (new_status, self._selected_rcv_id))
            conn.commit()
            conn.close()
            self._refresh_receipts()


class ReceivingDept(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Receiving Department")
        self.resize(980, 660)
        _apply_blue_palette(self)
        self.setCentralWidget(ReceivingDeptWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = ReceivingDept()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
