import sys
import psycopg2
from ..db_pg import get_db
from PyQt6 import QtCore, QtGui, QtWidgets
from ..qt_theme import (
    BUTTON_STYLE,
    INPUT_STYLE,
    COMBO_STYLE,
    LABEL_STYLE,
    apply_blue_palette as _apply_blue_palette,
    ro as _ro,
)

from ..accounts import get_current_user_email

SHIP_COLORS = {
    "pending":   "#ffffff",
    "shipped":   "#fff3cd",
    "delivered": "#d4edda",
    "returned":  "#dcdcdc",
}


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ship_number TEXT NOT NULL UNIQUE,
            so_id INTEGER,
            ship_date TEXT,
            carrier TEXT,
            tracking_number TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shipment_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL REFERENCES shipment(id),
            description TEXT NOT NULL,
            product_id INTEGER,
            qty INTEGER DEFAULT 1
        )
    """)
    try:
        conn.execute(
            "ALTER TABLE shipment ADD COLUMN IF NOT EXISTS created_by TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()


def _next_ship_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM shipment WHERE ship_number LIKE ?", (
            f"SH-{yr}-%",)
    ).fetchone()[0]
    conn.close()
    return f"SH-{yr}-{count + 1:04d}"


# ── Dialogs ─────────────────────────────────────────────────────────────

class NewShipmentDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Shipment")
        self.resize(480, 310)
        _apply_blue_palette(self)
        self.shipment_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.ship_num = QtWidgets.QLineEdit(_next_ship_num())
        self.ship_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Shipment #:"), self.ship_num)

        self.so_combo = QtWidgets.QComboBox()
        self.so_combo.setStyleSheet(COMBO_STYLE)
        conn = get_db()
        try:
            sos = conn.execute(
                "SELECT id, so_number FROM sales_order"
                " WHERE status NOT IN ('cancelled','invoiced') ORDER BY "
                "so_number"
            ).fetchall()
        except psycopg2.OperationalError:
            sos = []
        conn.close()
        self.so_combo.addItem("(none)", None)
        for s in sos:
            self.so_combo.addItem(s["so_number"], s["id"])
        layout.addRow(lbl("Sales Order:"), self.so_combo)

        self.ship_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.ship_date.setCalendarPopup(True)
        self.ship_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Ship Date:"), self.ship_date)

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
        for s in ("pending", "shipped"):
            self.status_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Notes:"), self.notes)

        self._created_by = get_current_user_email() or None
        cb_lbl = QtWidgets.QLabel(self._created_by or "(unknown)")
        cb_lbl.setStyleSheet(LABEL_STYLE)
        layout.addRow(lbl("Created by:"), cb_lbl)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        ship_num = self.ship_num.text().strip()
        if not ship_num:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Shipment number is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO shipment (ship_number, so_id, ship_date, carrier,"
                " tracking_number, status, notes, created_by)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (ship_num, self.so_combo.currentData(),
                 self.ship_date.date().toString("yyyy-MM-dd"),
                 self.carrier.text().strip(), self.tracking.text().strip(),
                 self.status_combo.currentData(), self.notes.text().strip(),
                 self._created_by)
            )
            self.shipment_id = cur.lastrowid
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"Shipment number '{ship_num}' already exists.")  # noqa: E501
            conn.close()
            return
        conn.close()
        self.accept()


class AddShipItemDialog(QtWidgets.QDialog):
    def __init__(self, shipment_id, ship_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Item — {ship_number}")
        self.resize(440, 210)
        _apply_blue_palette(self)
        self._shipment_id = shipment_id
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
        self.product_combo.currentIndexChanged.connect(
            self._on_product_changed)
        conn = get_db()
        try:
            prods = conn.execute(
                "SELECT id, name AS product_name FROM product ORDER BY name"
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

        self.qty = QtWidgets.QSpinBox()
        self.qty.setRange(1, 999999)
        self.qty.setValue(1)
        self.qty.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Quantity:"), self.qty)

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
            "INSERT INTO shipment_item (shipment_id, description, product_id, "
            "qty) VALUES (?,?,?,?)",
            (self._shipment_id, desc, self.product_combo.currentData(), self.qty.value())  # noqa: E501
        )
        conn.commit()
        conn.close()
        self.accept()


class UpdateShipmentDialog(QtWidgets.QDialog):
    """Edit carrier/tracking on an existing shipment."""
    def __init__(self, shipment_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Shipment")
        self.resize(400, 220)
        _apply_blue_palette(self)
        self._shipment_id = shipment_id
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.ship_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.ship_date.setCalendarPopup(True)
        self.ship_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Ship Date:"), self.ship_date)

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
    "SELECT * FROM shipment WHERE id = ?",
    (self._shipment_id,
    )).fetchone()
        conn.close()
        if not rec:
            return
        if rec["ship_date"]:
            self.ship_date.setDate(
    QtCore.QDate.fromString(
        rec["ship_date"], "yyyy-MM-dd"))
        self.carrier.setText(rec["carrier"] or "")
        self.tracking.setText(rec["tracking_number"] or "")
        self.notes.setText(rec["notes"] or "")

    def _on_ok(self):
        conn = get_db()
        conn.execute(
            "UPDATE shipment SET ship_date=?, carrier=?, tracking_number=?, "
            "notes=? WHERE id=?",
            (self.ship_date.date().toString("yyyy-MM-dd"),
             self.carrier.text().strip(), self.tracking.text().strip(),
             self.notes.text().strip(), self._shipment_id)
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ─────────────────────────────────────────────────────────

class ShippingDept(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Shipping Department — {email}" if email
                 else "Shipping Department")
        self.setWindowTitle(title)
        self.resize(920, 640)
        _apply_blue_palette(self)
        self._ship_row_ids = []
        self._selected_ship_id = None
        self._selected_ship_number = None
        self._build_ui()
        init_db()
        self._refresh_shipments()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
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
        for s in ("pending", "shipped", "delivered", "returned"):
            self.status_filter.addItem(s.capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh_shipments)
        fr.addWidget(self.status_filter)

        fr.addSpacing(10)
        lbl_f = QtWidgets.QLabel("From:")
        lbl_f.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_f)
        self.date_from = QtWidgets.QDateEdit(
            QtCore.QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet(INPUT_STYLE)
        self.date_from.dateChanged.connect(self._refresh_shipments)
        fr.addWidget(self.date_from)

        lbl_t = QtWidgets.QLabel("To:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.date_to = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet(INPUT_STYLE)
        self.date_to.dateChanged.connect(self._refresh_shipments)
        fr.addWidget(self.date_to)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.ship_table = QtWidgets.QTableWidget()
        self.ship_table.setColumnCount(8)
        self.ship_table.setHorizontalHeaderLabels(
            ["Ship #", "Sales Order", "Ship Date",
                "Carrier", "Tracking #", "Items", "Status", "Created By"]
        )
        hh = self.ship_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
    5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    6, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
    7, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.ship_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ship_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ship_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.ship_table.setAlternatingRowColors(True)
        self.ship_table.verticalHeader().setVisible(False)
        self.ship_table.clicked.connect(self._on_shipment_clicked)
        splitter.addWidget(self.ship_table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Shipment Items")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.item_table = QtWidgets.QTableWidget()
        self.item_table.setColumnCount(3)
        self.item_table.setHorizontalHeaderLabels(
            ["Description", "Product", "Qty"])
        ih = self.item_table.horizontalHeader()
        ih.setStyleSheet("color: black; font-weight: bold;")
        ih.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        ih.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ih.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
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
            ("New Shipment",    self._on_new_shipment),
            ("Add Item",        self._on_add_item),
            ("Update Details",  self._on_update_shipment),
            ("Mark Shipped",    lambda: self._set_status(
                "shipped",   "Mark as Shipped?")),
            ("Mark Delivered",  lambda: self._set_status(
                "delivered", "Mark as Delivered?")),
            ("Mark Returned",   lambda: self._set_status(
                "returned",  "Mark as Returned?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh_shipments(self):
        status = self.status_filter.currentData()
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to   = self.date_to.date().toString("yyyy-MM-dd")

        base = """
            SELECT s.id, s.ship_number, s.ship_date, s.carrier,
                s.tracking_number, s.status, s.created_by,
                   so.so_number,
                   (SELECT COUNT(*) FROM shipment_item si WHERE si.shipment_id
                       = s.id) AS item_count
            FROM shipment s
            LEFT JOIN sales_order so ON so.id = s.so_id
        """
        conds, params = [], []
        if status:
            conds.append("s.status = ?")
            params.append(status)
        conds.append("(s.ship_date IS NULL OR s.ship_date BETWEEN ? AND ?)")
        params += [d_from, d_to]
        where = " WHERE " + " AND ".join(conds)

        conn = get_db()
        try:
            rows = conn.execute(
    base + where + " ORDER BY s.ship_date DESC",
     params).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.ship_table.setRowCount(0)
        self._ship_row_ids = []
        for row in rows:
            r = self.ship_table.rowCount()
            self.ship_table.insertRow(r)
            self._ship_row_ids.append(row["id"])
            self.ship_table.setItem(r, 0, _ro(row["ship_number"]))
            self.ship_table.setItem(r, 1, _ro(row["so_number"] or ""))
            self.ship_table.setItem(r, 2, _ro(row["ship_date"] or ""))
            self.ship_table.setItem(r, 3, _ro(row["carrier"] or ""))
            self.ship_table.setItem(r, 4, _ro(row["tracking_number"] or ""))
            self.ship_table.setItem(r, 5, _ro(str(row["item_count"])))
            self.ship_table.setItem(r, 6, _ro(row["status"].capitalize()))
            self.ship_table.setItem(r, 7, _ro(row["created_by"] or ""))
            bg = QtGui.QColor(SHIP_COLORS.get(row["status"], "#ffffff"))
            for col in range(8):
                self.ship_table.item(r, col).setBackground(bg)

        self._selected_ship_id = None
        self._selected_ship_number = None
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
        self._refresh_shipments()

    def _on_shipment_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._ship_row_ids):
            return
        self._selected_ship_id = self._ship_row_ids[row]
        self._selected_ship_number = self.ship_table.item(row, 0).text()
        self._refresh_items()

    def _refresh_items(self):
        self.item_table.setRowCount(0)
        if self._selected_ship_id is None:
            return
        conn = get_db()
        try:
            items = conn.execute("""
                SELECT si.description, p.name AS product_name, si.qty
                FROM shipment_item si LEFT JOIN product p ON p.id =
                    si.product_id
                WHERE si.shipment_id = ?
            """, (self._selected_ship_id,)).fetchall()
        except psycopg2.OperationalError:
            items = conn.execute(
                "SELECT description, NULL AS product_name, qty FROM "
                "shipment_item WHERE shipment_id = ?",
                (self._selected_ship_id,)
            ).fetchall()
        conn.close()
        for item in items:
            r = self.item_table.rowCount()
            self.item_table.insertRow(r)
            self.item_table.setItem(r, 0, _ro(item["description"]))
            self.item_table.setItem(r, 1, _ro(item["product_name"] or ""))
            self.item_table.setItem(r, 2, _ro(str(item["qty"])))

    def _on_new_shipment(self):
        dlg = NewShipmentDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_shipments()

    def _on_add_item(self):
        if self._selected_ship_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a shipment first.")
            return
        dlg = AddShipItemDialog(
    self._selected_ship_id,
    self._selected_ship_number,
     self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_shipments()
            self._refresh_items()

    def _on_update_shipment(self):
        if self._selected_ship_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a shipment first.")
            return
        dlg = UpdateShipmentDialog(self._selected_ship_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_shipments()

    def _set_status(self, new_status, msg):
        if self._selected_ship_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a shipment first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE shipment SET status = ? WHERE id = ?",
                         (new_status, self._selected_ship_id))
            conn.commit()
            conn.close()
            self._refresh_shipments()


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = ShippingDept()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
