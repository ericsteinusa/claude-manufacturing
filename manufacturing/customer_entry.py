import sys
import psycopg2
import psycopg2.extras
from .db_connection import get_db_connection
import os
from PyQt6 import QtCore, QtGui, QtWidgets


BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE = "QLineEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
COMBO_STYLE = "QComboBox{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}QComboBox QAbstractItemView{background-color:white;}"
LABEL_STYLE = "color:white;font-size:13px;"
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white; border:2px solid black; padding:6px 18px;"
    " border-bottom:none; border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255); font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


def get_db():
    conn = get_db_connection()
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer (
            id           SERIAL PRIMARY KEY,
            first_name   TEXT,
            last_name    TEXT,
            company_name TEXT,
            phone_number TEXT,
            address      TEXT,
            city         TEXT,
            state        TEXT,
            zip_code     TEXT,
            email        TEXT
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


def _customer_display(row):
    company = (row["company_name"] or "").strip()
    contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    return company if company else contact


class CustomerEntry(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Customer Entry")
        self.resize(1100, 700)
        _apply_blue_palette(self)
        self._row_ids = []
        self._build_ui()
        self._load_customers()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        outer.addWidget(tabs)
        tabs.addTab(self._build_customers_tab(), "Customers")
        tabs.addTab(self._build_history_tab(), "Service History")
        self._tabs = tabs

    # ── Customers tab ──────────────────────────────────────────────────────

    def _build_customers_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Search bar
        sr = QtWidgets.QHBoxLayout()
        sl = QtWidgets.QLabel("Search:")
        sl.setStyleSheet(LABEL_STYLE)
        sr.addWidget(sl)
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setStyleSheet(INPUT_STYLE)
        self.search_box.setFixedWidth(240)
        self.search_box.setPlaceholderText("Company or last name")
        self.search_box.returnPressed.connect(self._on_search)
        sr.addWidget(self.search_box)
        for t, fn in (("Search", self._on_search), ("Show All", self._load_customers)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            sr.addWidget(b)
        sr.addStretch()
        layout.addLayout(sr)

        # Table
        self.cust_table = QtWidgets.QTableWidget()
        self.cust_table.setColumnCount(8)
        self.cust_table.setHorizontalHeaderLabels(
            ["Company / Name", "Contact", "Phone", "Email", "Address", "City", "State", "Zip"])
        hh = self.cust_table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 5, 6, 7):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.cust_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cust_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.cust_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.cust_table.setAlternatingRowColors(True)
        self.cust_table.verticalHeader().setVisible(False)
        self.cust_table.clicked.connect(self._on_row_clicked)
        layout.addWidget(self.cust_table, stretch=1)

        # Form
        fg = QtWidgets.QGroupBox("Customer Record")
        fg.setStyleSheet(
            "QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;}")
        grid = QtWidgets.QGridLayout(fg)
        grid.setSpacing(6)

        def lbl(t):
            lbl = QtWidgets.QLabel(t)
            lbl.setStyleSheet(LABEL_STYLE)
            return lbl

        def inp(ph=""):
            e = QtWidgets.QLineEdit()
            e.setStyleSheet(INPUT_STYLE)
            e.setPlaceholderText(ph)
            return e

        self.ef_company = inp("Company name")
        self.ef_first = inp("First name")
        self.ef_last = inp("Last name")
        self.ef_phone = inp("Phone")
        self.ef_phone.setFixedWidth(140)
        self.ef_email = inp("Email")
        self.ef_addr = inp("Street address")
        self.ef_city = inp("City")
        self.ef_state = inp("ST")
        self.ef_state.setMaxLength(2)
        self.ef_state.setFixedWidth(44)
        self.ef_zip = inp("Zip")
        self.ef_zip.setFixedWidth(90)

        grid.addWidget(lbl("Company:"), 0, 0)
        grid.addWidget(self.ef_company, 0, 1, 1, 3)
        grid.addWidget(lbl("First Name:"), 0, 4)
        grid.addWidget(self.ef_first, 0, 5)
        grid.addWidget(lbl("Last Name:"), 1, 0)
        grid.addWidget(self.ef_last, 1, 1, 1, 3)
        grid.addWidget(lbl("Phone:"), 1, 4)
        grid.addWidget(self.ef_phone, 1, 5)
        grid.addWidget(lbl("Email:"), 2, 0)
        grid.addWidget(self.ef_email, 2, 1, 1, 5)
        grid.addWidget(lbl("Address:"), 3, 0)
        grid.addWidget(self.ef_addr, 3, 1, 1, 3)
        grid.addWidget(lbl("City:"), 3, 4)
        grid.addWidget(self.ef_city, 3, 5)
        grid.addWidget(lbl("State:"), 4, 0)
        grid.addWidget(self.ef_state, 4, 1)
        grid.addWidget(lbl("Zip:"), 4, 2)
        grid.addWidget(self.ef_zip, 4, 3)
        layout.addWidget(fg)

        br = QtWidgets.QHBoxLayout()
        for t, fn in (("Add New", self._on_add), ("Update Selected", self._on_update),
                      ("Delete Selected", self._on_delete), ("View History", self._on_view_history),
                      ("Clear", self._clear_form)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(34)
            b.clicked.connect(fn)
            br.addWidget(b)
        br.addStretch()
        layout.addLayout(br)
        return w

    # ── Service History tab ────────────────────────────────────────────────

    def _build_history_tab(self):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.hist_cust_lbl = QtWidgets.QLabel("Select a customer on the Customers tab, then click View History.")
        self.hist_cust_lbl.setStyleSheet("color:white;font-size:13px;font-weight:bold;")
        layout.addWidget(self.hist_cust_lbl)

        self.hist_table = QtWidgets.QTableWidget()
        self.hist_table.setColumnCount(7)
        self.hist_table.setHorizontalHeaderLabels([
            "Call Date", "Call Time", "Problem / Call",
            "Completion Date", "Completion Time", "Comments", "Status"
        ])
        hh = self.hist_table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (0, 1, 3, 4, 6):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.hist_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hist_table.setAlternatingRowColors(True)
        self.hist_table.verticalHeader().setVisible(False)
        layout.addWidget(self.hist_table, stretch=1)

        self.hist_summary_lbl = QtWidgets.QLabel("")
        self.hist_summary_lbl.setStyleSheet("color:white;font-size:12px;")
        layout.addWidget(self.hist_summary_lbl)
        return w

    # ── Data ───────────────────────────────────────────────────────────────

    def _load_customers(self, search=None):
        self.search_box.blockSignals(True)
        if not search:
            self.search_box.clear()
        self.search_box.blockSignals(False)

        conn = get_db()
        if search:
            rows = conn.execute(
                "SELECT * FROM customer WHERE company_name LIKE %s OR last_name LIKE %s "
                "ORDER BY company_name, last_name, first_name",
                (f"%{search}%", f"%{search}%")
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM customer ORDER BY company_name, last_name, first_name"
            ).fetchall()
        conn.close()

        self.cust_table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.cust_table.rowCount()
            self.cust_table.insertRow(r)
            self._row_ids.append(row["id"])
            contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
            primary = (row["company_name"] or "").strip() or contact
            for c, v in enumerate([
                primary,
                contact if (row["company_name"] or "").strip() else "",
                row["phone_number"] or "",
                row["email"] or "",
                row["address"] or "",
                row["city"] or "",
                row["state"] or "",
                row["zip_code"] or "",
            ]):
                self.cust_table.setItem(r, c, _ro(v))

    def _on_search(self):
        self._load_customers(search=self.search_box.text().strip() or None)

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        conn = get_db()
        c = conn.execute("SELECT * FROM customer WHERE id=%s", (self._row_ids[row],)).fetchone()
        conn.close()
        if not c:
            return
        self.ef_company.setText(c["company_name"] or "")
        self.ef_first.setText(c["first_name"] or "")
        self.ef_last.setText(c["last_name"] or "")
        self.ef_phone.setText(c["phone_number"] or "")
        self.ef_email.setText(c["email"] or "")
        self.ef_addr.setText(c["address"] or "")
        self.ef_city.setText(c["city"] or "")
        self.ef_state.setText(c["state"] or "")
        self.ef_zip.setText(c["zip_code"] or "")

    def _clear_form(self):
        for w in (self.ef_company, self.ef_first, self.ef_last, self.ef_phone,
                  self.ef_email, self.ef_addr, self.ef_city, self.ef_state, self.ef_zip):
            w.clear()
        self.cust_table.clearSelection()

    def _collect_form(self):
        company = self.ef_company.text().strip()
        last = self.ef_last.text().strip()
        if not company and not last:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Company name or last name is required.")
            return None
        return {
            "company_name": company or None,
            "first_name": self.ef_first.text().strip() or None,
            "last_name": last or None,
            "phone_number": self.ef_phone.text().strip() or None,
            "email": self.ef_email.text().strip() or None,
            "address": self.ef_addr.text().strip() or None,
            "city": self.ef_city.text().strip() or None,
            "state": self.ef_state.text().strip().upper() or None,
            "zip_code": self.ef_zip.text().strip() or None,
        }

    def _on_add(self):
        data = self._collect_form()
        if not data:
            return
        conn = get_db()
        conn.execute("""
            INSERT INTO customer (company_name, first_name, last_name, phone_number,
                                  email, address, city, state, zip_code)
            VALUES (:company_name, :first_name, :last_name, :phone_number,
                    :email, :address, :city, :state, :zip_code)
        """, data)
        conn.commit()
        conn.close()
        self._clear_form()
        self._load_customers()

    def _on_update(self):
        row = self.cust_table.currentRow()
        if row < 0 or row >= len(self._row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a customer first.")
            return
        data = self._collect_form()
        if not data:
            return
        data["id"] = self._row_ids[row]
        conn = get_db()
        conn.execute("""
            UPDATE customer SET company_name=:company_name, first_name=:first_name,
                last_name=:last_name, phone_number=:phone_number, email=:email,
                address=:address, city=:city, state=:state, zip_code=:zip_code
            WHERE id=:id
        """, data)
        conn.commit()
        conn.close()
        self._load_customers()

    def _on_delete(self):
        row = self.cust_table.currentRow()
        if row < 0 or row >= len(self._row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a customer first.")
            return
        cid = self._row_ids[row]
        conn = get_db()
        call_count = conn.execute(
            "SELECT COUNT(*) FROM calls2 WHERE customer_id=%s", (cid,)
        ).fetchone()[0]
        conn.close()
        msg = "Delete this customer%s"
        if call_count:
            msg += f"\n\nWarning: {call_count} service call(s) reference this customer. They will also be deleted."
        if (QtWidgets.QMessageBox.question(
                self, "Confirm Delete", msg,
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            conn = get_db()
            conn.execute("DELETE FROM calls2 WHERE customer_id=%s", (cid,))
            conn.execute("DELETE FROM customer WHERE id=%s", (cid,))
            conn.commit()
            conn.close()
            self._clear_form()
            self._load_customers()

    def _on_view_history(self):
        row = self.cust_table.currentRow()
        if row < 0 or row >= len(self._row_ids):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a customer first.")
            return
        cid = self._row_ids[row]
        conn = get_db()
        cust = conn.execute("SELECT * FROM customer WHERE id=%s", (cid,)).fetchone()
        calls = conn.execute(
            "SELECT * FROM calls2 WHERE customer_id=%s ORDER BY call_date DESC, call_time DESC",
            (cid,)
        ).fetchall()
        conn.close()

        self.hist_cust_lbl.setText(f"Service History — {_customer_display(cust)}")
        self.hist_table.setRowCount(0)
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
        open_count = 0
        for call in calls:
            r = self.hist_table.rowCount()
            self.hist_table.insertRow(r)
            completed = bool(call["completion_box"])
            if not completed:
                open_count += 1
            color = QtGui.QColor(212, 237, 218) if completed else QtGui.QColor(255, 243, 205)
            status_str = "Completed" if completed else "Open"
            for c, (val, algn) in enumerate([
                (call["call_date"] or "", center),
                (call["call_time"] or "", center),
                (call["call"] or "", QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (call["completion_date"] or "", center),
                (call["completion_time"] or "", center),
                (call["comments_box"] or "", QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (status_str, center),
            ]):
                item = _ro(val, algn)
                item.setBackground(color)
                self.hist_table.setItem(r, c, item)

        total = len(calls)
        done = total - open_count
        self.hist_summary_lbl.setText(
            f"Total calls: {total}    Completed: {done}    Open: {open_count}")
        self._tabs.setCurrentIndex(1)


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = CustomerEntry()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
