import sys
import psycopg2
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


def get_db():
    return get_db_connection()


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer (
            id SERIAL PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            company_name TEXT,
            phone_number TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            email TEXT
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


def _display_name(row):
    company = row["company_name"] or ""
    name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    return company if company else name


# ── Dialogs ────────────────────────────────────────────────────────────────────

class CustomerDialog(QtWidgets.QDialog):
    """Shared dialog for adding and editing a customer."""

    def __init__(self, customer_id=None, parent=None):
        super().__init__(parent)
        self._customer_id = customer_id
        self.setWindowTitle("Edit Customer" if customer_id else "New Customer")
        self.resize(460, 380)
        _apply_blue_palette(self)
        self.saved_id = None
        self._build_ui()
        if customer_id:
            self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.company = QtWidgets.QLineEdit()
        self.company.setStyleSheet(INPUT_STYLE)
        self.company.setPlaceholderText("Company name (optional)")
        layout.addRow(lbl("Company:"), self.company)

        self.first_name = QtWidgets.QLineEdit()
        self.first_name.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("First Name:"), self.first_name)

        self.last_name = QtWidgets.QLineEdit()
        self.last_name.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Last Name:"), self.last_name)

        self.email = QtWidgets.QLineEdit()
        self.email.setStyleSheet(INPUT_STYLE)
        self.email.setPlaceholderText("email@example.com")
        layout.addRow(lbl("Email:"), self.email)

        self.phone = QtWidgets.QLineEdit()
        self.phone.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Phone:"), self.phone)

        self.address = QtWidgets.QLineEdit()
        self.address.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Address:"), self.address)

        self.city = QtWidgets.QLineEdit()
        self.city.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("City:"), self.city)

        self.state = QtWidgets.QLineEdit()
        self.state.setStyleSheet(INPUT_STYLE)
        self.state.setMaxLength(2)
        self.state.setFixedWidth(50)
        layout.addRow(lbl("State:"), self.state)

        self.zip_code = QtWidgets.QLineEdit()
        self.zip_code.setStyleSheet(INPUT_STYLE)
        self.zip_code.setFixedWidth(90)
        layout.addRow(lbl("Zip:"), self.zip_code)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _load(self):
        conn = get_db()
        rec = conn.execute("SELECT * FROM customer WHERE id = %s",
                           (self._customer_id,)).fetchone()
        conn.close()
        if not rec:
            return
        self.company.setText(rec["company_name"] or "")
        self.first_name.setText(rec["first_name"] or "")
        self.last_name.setText(rec["last_name"] or "")
        self.email.setText(rec["email"] or "")
        self.phone.setText(rec["phone_number"] or "")
        self.address.setText(rec["address"] or "")
        self.city.setText(rec["city"] or "")
        self.state.setText(rec["state"] or "")
        self.zip_code.setText(rec["zip_code"] or "")

    def _on_ok(self):
        company = self.company.text().strip()
        first = self.first_name.text().strip()
        last = self.last_name.text().strip()
        if not company and not (first or last):
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Enter a company name or contact name.")
            return
        conn = get_db()
        if self._customer_id is None:
            cur = conn.execute(
                "INSERT INTO customer (company_name, first_name, last_name, email,"
                " phone_number, address, city, state, zip_code)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (company, first, last,
                 self.email.text().strip(), self.phone.text().strip(),
                 self.address.text().strip(), self.city.text().strip(),
                 self.state.text().strip(), self.zip_code.text().strip())
            )
            self.saved_id = cur.fetchone()['id']
        else:
            conn.execute(
                "UPDATE customer SET company_name=%s, first_name=%s, last_name=%s,"
                " email=%s, phone_number=%s, address=%s, city=%s, state=%s, zip_code=%s"
                " WHERE id=%s",
                (company, first, last,
                 self.email.text().strip(), self.phone.text().strip(),
                 self.address.text().strip(), self.city.text().strip(),
                 self.state.text().strip(), self.zip_code.text().strip(),
                 self._customer_id)
            )
            self.saved_id = self._customer_id
        conn.commit()
        conn.close()
        self.accept()


class CustomerDetailPanel(QtWidgets.QWidget):
    """Read-only detail card shown below the customer list."""

    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(4)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        def val():
            w = QtWidgets.QLabel("")
            w.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
            return w

        self.v_company  = val()
        self.v_name    = val()
        self.v_email    = val()
        self.v_phone   = val()
        self.v_address  = val()
        self.v_orders  = val()

        layout.addWidget(lbl("Company:"),  0, 0)
        layout.addWidget(self.v_company, 0, 1)
        layout.addWidget(lbl("Contact:"),  0, 2)
        layout.addWidget(self.v_name,    0, 3)
        layout.addWidget(lbl("Email:"),    1, 0)
        layout.addWidget(self.v_email,   1, 1)
        layout.addWidget(lbl("Phone:"),    1, 2)
        layout.addWidget(self.v_phone,   1, 3)
        layout.addWidget(lbl("Address:"),  2, 0)
        layout.addWidget(self.v_address, 2, 1, 1, 3)
        layout.addWidget(lbl("Orders:"),   3, 0)
        layout.addWidget(self.v_orders,  3, 1)
        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(3, 2)

    def load(self, customer_id):
        conn = get_db()
        rec = conn.execute("SELECT * FROM customer WHERE id = %s",
                           (customer_id,)).fetchone()
        try:
            order_count = conn.execute(
                "SELECT COUNT(*) FROM sales_order WHERE customer_id = %s",
                (customer_id,)
            ).fetchone()[0]
        except psycopg2.OperationalError:
            order_count = 0
        conn.close()
        if not rec:
            self.clear()
            return
        self.v_company.setText(rec["company_name"] or "")
        name = f"{rec['first_name'] or ''} {rec['last_name'] or ''}".strip()
        self.v_name.setText(name)
        self.v_email.setText(rec["email"] or "")
        self.v_phone.setText(rec["phone_number"] or "")
        parts = [p for p in (rec["address"], rec["city"], rec["state"], rec["zip_code"]) if p]
        self.v_address.setText(", ".join(parts))
        self.v_orders.setText(str(order_count))

    def clear(self):
        for w in (self.v_company, self.v_name, self.v_email,
                  self.v_phone, self.v_address, self.v_orders):
            w.setText("")


# ── Main Window ────────────────────────────────────────────────────────────────

class CustomersWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._cust_row_ids = []
        self._selected_id = None
        self._build_ui()
        init_db()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # search row
        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Search:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setStyleSheet(INPUT_STYLE)
        self.search_edit.setPlaceholderText("Name, company, email, phone…")
        self.search_edit.setFixedWidth(240)
        self.search_edit.textChanged.connect(self._refresh)
        fr.addWidget(self.search_edit)
        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.cust_table = QtWidgets.QTableWidget()
        self.cust_table.setColumnCount(7)
        self.cust_table.setHorizontalHeaderLabels(
            ["Company", "First Name", "Last Name", "Email", "Phone", "City", "State"]
        )
        hh = self.cust_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.cust_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cust_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.cust_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.cust_table.setAlternatingRowColors(True)
        self.cust_table.verticalHeader().setVisible(False)
        self.cust_table.clicked.connect(self._on_row_clicked)
        self.cust_table.doubleClicked.connect(self._on_edit)
        splitter.addWidget(self.cust_table)

        self.detail = CustomerDetailPanel()
        splitter.addWidget(self.detail)
        splitter.setSizes([480, 120])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Customer",    self._on_new),
            ("Edit Customer",   self._on_edit),
            ("Delete Customer", self._on_delete),
            ("View Orders",     self._on_view_orders),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        search = self.search_edit.text().strip().lower()

        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT id, company_name, first_name, last_name,"
                " email, phone_number, city, state"
                " FROM customer ORDER BY company_name, last_name, first_name"
            ).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.cust_table.setRowCount(0)
        self._cust_row_ids = []
        for row in rows:
            if search:
                haystack = " ".join([
                    row["company_name"] or "",
                    row["first_name"] or "",
                    row["last_name"] or "",
                    row["email"] or "",
                    row["phone_number"] or "",
                    row["city"] or "",
                ]).lower()
                if search not in haystack:
                    continue
            r = self.cust_table.rowCount()
            self.cust_table.insertRow(r)
            self._cust_row_ids.append(row["id"])
            self.cust_table.setItem(r, 0, _ro(row["company_name"] or ""))
            self.cust_table.setItem(r, 1, _ro(row["first_name"] or ""))
            self.cust_table.setItem(r, 2, _ro(row["last_name"] or ""))
            self.cust_table.setItem(r, 3, _ro(row["email"] or ""))
            self.cust_table.setItem(r, 4, _ro(row["phone_number"] or ""))
            self.cust_table.setItem(r, 5, _ro(row["city"] or ""))
            self.cust_table.setItem(r, 6, _ro(row["state"] or ""))

        self._selected_id = None
        self.detail.clear()

    def _on_show_all(self):
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._cust_row_ids):
            return
        self._selected_id = self._cust_row_ids[row]
        self.detail.load(self._selected_id)

    def _on_new(self):
        dlg = CustomerDialog(parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, _index=None):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a customer first.")
            return
        dlg = CustomerDialog(customer_id=self._selected_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()
            self.detail.load(self._selected_id)

    def _on_delete(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a customer first.")
            return
        conn = get_db()
        name_row = conn.execute(
            "SELECT company_name, first_name, last_name FROM customer WHERE id = %s",
            (self._selected_id,)
        ).fetchone()
        conn.close()
        name = _display_name(name_row) if name_row else "this customer"
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{name}'? This cannot be undone.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM customer WHERE id = %s", (self._selected_id,))
            conn.commit()
            conn.close()
            self._selected_id = None
            self._refresh()

    def _on_view_orders(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a customer first.")
            return
        conn = get_db()
        try:
            orders = conn.execute(
                "SELECT so_number, order_date, ship_date, status"
                " FROM sales_order WHERE customer_id = %s ORDER BY order_date DESC",
                (self._selected_id,)
            ).fetchall()
        except psycopg2.OperationalError:
            orders = []
        conn.close()

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Sales Orders")
        dlg.resize(500, 320)
        _apply_blue_palette(dlg)
        vl = QtWidgets.QVBoxLayout(dlg)
        tbl = QtWidgets.QTableWidget()
        tbl.setColumnCount(4)
        tbl.setHorizontalHeaderLabels(["SO #", "Order Date", "Ship Date", "Status"])
        hh = tbl.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        for i in range(4):
            hh.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.setAlternatingRowColors(True)
        for o in orders:
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, _ro(o["so_number"] or ""))
            tbl.setItem(r, 1, _ro(o["order_date"] or ""))
            tbl.setItem(r, 2, _ro(o["ship_date"] or ""))
            tbl.setItem(r, 3, _ro((o["status"] or "").capitalize()))
        vl.addWidget(tbl)
        close_btn = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(dlg.reject)
        vl.addWidget(close_btn)
        dlg.exec()


class CustomersWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Customers")
        self.resize(1000, 660)
        _apply_blue_palette(self)
        self.setCentralWidget(CustomersWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = CustomersWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
