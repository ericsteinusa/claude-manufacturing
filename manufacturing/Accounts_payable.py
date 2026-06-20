import sys
import psycopg2
from .db_pg import get_db_connection
from .accounts import get_current_user_email
from PyQt6 import QtCore, QtGui, QtWidgets
from .qt_theme import (
    BLUE,
    BUTTON_STYLE,
    INPUT_STYLE,
    COMBO_STYLE,
    LABEL_STYLE,
    apply_blue_palette as _apply_blue_palette,
    ro as _ro,
)


INV_COLORS = {
    "open":        "#ffffff",
    "partial":     "#fff3cd",
    "paid":        "#d4edda",
    "overdue":     "#f8d7da",
    "cancelled":   "#dcdcdc",
}

PAYMENT_METHODS = ["Check", "ACH", "Wire", "Credit Card", "Cash", "Other"]


def get_db():
    return get_db_connection()


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ap_invoice (
            id SERIAL PRIMARY KEY,
            vendor_id INTEGER,
            invoice_number TEXT NOT NULL,
            invoice_date TEXT,
            due_date TEXT,
            amount REAL DEFAULT 0,
            description TEXT,
            status TEXT DEFAULT 'open',
            created_by TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ap_payment (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER NOT NULL REFERENCES ap_invoice(id),
            payment_date TEXT,
            amount REAL DEFAULT 0,
            payment_method TEXT DEFAULT 'Check',
            reference TEXT,
            notes TEXT
        )
    """)
    try:
        conn.execute(
            "ALTER TABLE ap_invoice ADD COLUMN IF NOT EXISTS created_by TEXT")
    except Exception:
        pass
    # Backfill: an older DB may have ap_invoice.vendor_id pointing to a
    # separate `vendors` table (not `supplier`) with a NOT NULL constraint.
    # The code reads vendors from `supplier`, so that FK is wrong and blocks
    # every insert. Drop it and make vendor_id nullable to match the DDL above.
    try:
        conn.execute(
            "ALTER TABLE ap_invoice"
            " DROP CONSTRAINT IF EXISTS ap_invoice_vendor_id_fkey")
    except Exception:
        pass
    try:
        conn.execute(
            "ALTER TABLE ap_invoice ALTER COLUMN vendor_id DROP NOT NULL")
    except Exception:
        pass
    conn.commit()
    conn.close()


def _ro_right(text):
    item = _ro(text)
    item.setTextAlignment(
        QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)  # noqa: E501
    return item


def _load_vendors():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, company_name, first_name, last_name FROM supplier"
            " ORDER BY company_name, last_name"
        ).fetchall()
    except psycopg2.OperationalError:
        rows = []
    conn.close()
    return rows


def _vendor_label(row):
    company = row["company_name"] or ""
    name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    return company if company else name


def _invoice_status(amount, paid):
    """Compute status based on amounts."""
    if paid <= 0:
        return "open"
    if paid >= amount:
        return "paid"
    return "partial"


# ── Dialogs ─────────────────────────────────────────────────────────────

class InvoiceDialog(QtWidgets.QDialog):
    def __init__(self, invoice_id=None, parent=None):
        super().__init__(parent)
        self._invoice_id = invoice_id
        self.setWindowTitle("Edit Invoice" if invoice_id else "New Invoice")
        self.resize(480, 340)
        _apply_blue_palette(self)
        self.saved_id = None
        self._build_ui()
        if invoice_id:
            self._load()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.vendor_combo = QtWidgets.QComboBox()
        self.vendor_combo.setStyleSheet(COMBO_STYLE)
        self.vendor_combo.setMinimumWidth(220)
        self.vendor_combo.addItem("(none)", None)
        for v in _load_vendors():
            self.vendor_combo.addItem(_vendor_label(v), v["id"])
        layout.addRow(lbl("Vendor:"), self.vendor_combo)

        self.inv_num = QtWidgets.QLineEdit()
        self.inv_num.setStyleSheet(INPUT_STYLE)
        self.inv_num.setPlaceholderText("Vendor invoice number")
        layout.addRow(lbl("Invoice #:"), self.inv_num)

        self.inv_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.inv_date.setCalendarPopup(True)
        self.inv_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Invoice Date:"), self.inv_date)

        self.due_date = QtWidgets.QDateEdit(
    QtCore.QDate.currentDate().addDays(30))
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

        self.amount = QtWidgets.QDoubleSpinBox()
        self.amount.setRange(0, 99999999)
        self.amount.setDecimals(2)
        self.amount.setPrefix("$ ")
        self.amount.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Amount:"), self.amount)

        self.description = QtWidgets.QLineEdit()
        self.description.setStyleSheet(INPUT_STYLE)
        self.description.setPlaceholderText("Invoice description")
        layout.addRow(lbl("Description:"), self.description)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ("open", "partial", "paid", "overdue", "cancelled"):
            self.status_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

        created_by_lbl = QtWidgets.QLabel(
            get_current_user_email() or "(unknown)")
        created_by_lbl.setStyleSheet(LABEL_STYLE)
        layout.addRow(lbl("Created by:"), created_by_lbl)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _load(self):
        conn = get_db()
        rec = conn.execute("SELECT * FROM ap_invoice WHERE id = %s",
                           (self._invoice_id,)).fetchone()
        conn.close()
        if not rec:
            return
        for i in range(self.vendor_combo.count()):
            if self.vendor_combo.itemData(i) == rec["vendor_id"]:
                self.vendor_combo.setCurrentIndex(i)
                break
        self.inv_num.setText(rec["invoice_number"] or "")
        if rec["invoice_date"]:
            self.inv_date.setDate(
                QtCore.QDate.fromString(rec["invoice_date"], "yyyy-MM-dd"))
        if rec["due_date"]:
            self.due_date.setDate(
                QtCore.QDate.fromString(rec["due_date"], "yyyy-MM-dd"))
        self.amount.setValue(rec["amount"] or 0)
        self.description.setText(rec["description"] or "")
        for i in range(self.status_combo.count()):
            if self.status_combo.itemData(i) == rec["status"]:
                self.status_combo.setCurrentIndex(i)
                break

    def _on_ok(self):
        inv_num = self.inv_num.text().strip()
        if not inv_num:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Invoice number is required.")
            return
        conn = get_db()
        try:
            if self._invoice_id is None:
                cur = conn.execute(
                    "INSERT INTO ap_invoice (vendor_id, invoice_number, "
                    "invoice_date,"
                    " due_date, amount, description, status, created_by)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (self.vendor_combo.currentData(), inv_num,
                     self.inv_date.date().toString("yyyy-MM-dd"),
                     self.due_date.date().toString("yyyy-MM-dd"),
                     self.amount.value(), self.description.text().strip(),
                     self.status_combo.currentData(),
                     get_current_user_email() or None)
                )
                self.saved_id = cur.fetchone()['id']
            else:
                conn.execute(
                    "UPDATE ap_invoice SET vendor_id=%s, invoice_number=%s,"
                    " invoice_date=%s, due_date=%s, amount=%s, description=%s,"
                    " status=%s WHERE id=%s",
                    (self.vendor_combo.currentData(), inv_num,
                     self.inv_date.date().toString("yyyy-MM-dd"),
                     self.due_date.date().toString("yyyy-MM-dd"),
                     self.amount.value(), self.description.text().strip(),
                     self.status_combo.currentData(), self._invoice_id)
                )
                self.saved_id = self._invoice_id
            conn.commit()
        except psycopg2.IntegrityError as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class RecordPaymentDialog(QtWidgets.QDialog):
    def __init__(self, invoice_id, invoice_number, balance, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Record Payment — {invoice_number}")
        self.resize(420, 280)
        _apply_blue_palette(self)
        self._invoice_id = invoice_id
        self._balance = balance
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        bal_lbl = QtWidgets.QLabel(f"${self._balance:,.2f}")
        bal_lbl.setStyleSheet(
            "color: white; font-size: 13px; font-weight: bold;")
        layout.addRow(lbl("Balance Due:"), bal_lbl)

        self.pay_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.pay_date.setCalendarPopup(True)
        self.pay_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Payment Date:"), self.pay_date)

        self.pay_amount = QtWidgets.QDoubleSpinBox()
        self.pay_amount.setRange(0.01, 99999999)
        self.pay_amount.setDecimals(2)
        self.pay_amount.setPrefix("$ ")
        self.pay_amount.setValue(self._balance)
        self.pay_amount.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Amount:"), self.pay_amount)

        self.method_combo = QtWidgets.QComboBox()
        self.method_combo.setStyleSheet(COMBO_STYLE)
        for m in PAYMENT_METHODS:
            self.method_combo.addItem(m, m)
        layout.addRow(lbl("Method:"), self.method_combo)

        self.reference = QtWidgets.QLineEdit()
        self.reference.setStyleSheet(INPUT_STYLE)
        self.reference.setPlaceholderText("Check #, ACH ref, etc.")
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
        conn = get_db()
        conn.execute(
            "INSERT INTO ap_payment (invoice_id, payment_date, amount,"
            " payment_method, reference, notes) VALUES (%s,%s,%s,%s,%s,%s)",
            (self._invoice_id,
             self.pay_date.date().toString("yyyy-MM-dd"),
             self.pay_amount.value(),
             self.method_combo.currentData(),
             self.reference.text().strip(),
             self.notes.text().strip())
        )
        # Update invoice status
        paid = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ap_payment WHERE "
            "invoice_id=%s",
            (self._invoice_id,)
        ).fetchone()[0]
        inv = conn.execute(
            "SELECT amount FROM ap_invoice WHERE id=%s", (self._invoice_id,)
        ).fetchone()
        if inv:
            new_status = _invoice_status(inv["amount"], paid)
            conn.execute("UPDATE ap_invoice SET status=%s WHERE id=%s",
                         (new_status, self._invoice_id))
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ─────────────────────────────────────────────────────────

class AccountsPayableWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._inv_row_ids = []
        self._selected_inv_id = None
        self._selected_inv_number = None
        self._selected_balance = 0.0
        self._build_ui()
        init_db()
        self._refresh_invoices()

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
        for s in ("open", "partial", "paid", "overdue", "cancelled"):
            self.status_filter.addItem(s.capitalize(), s)
        self.status_filter.currentIndexChanged.connect(self._refresh_invoices)
        fr.addWidget(self.status_filter)

        fr.addSpacing(10)
        lbl_v = QtWidgets.QLabel("Vendor:")
        lbl_v.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_v)
        self.vendor_filter = QtWidgets.QComboBox()
        self.vendor_filter.setStyleSheet(COMBO_STYLE)
        self.vendor_filter.setMinimumWidth(150)
        self.vendor_filter.addItem("(all)", None)
        for vendor in _load_vendors():
            self.vendor_filter.addItem(_vendor_label(vendor), vendor["id"])
        self.vendor_filter.currentIndexChanged.connect(self._refresh_invoices)
        fr.addWidget(self.vendor_filter)

        fr.addSpacing(10)
        lbl_f = QtWidgets.QLabel("Due From:")
        lbl_f.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_f)
        self.date_from = QtWidgets.QDateEdit(
            QtCore.QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet(INPUT_STYLE)
        self.date_from.dateChanged.connect(self._refresh_invoices)
        fr.addWidget(self.date_from)

        lbl_t = QtWidgets.QLabel("To:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self.date_to = QtWidgets.QDateEdit(
    QtCore.QDate.currentDate().addMonths(3))
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet(INPUT_STYLE)
        self.date_to.dateChanged.connect(self._refresh_invoices)
        fr.addWidget(self.date_to)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        # Invoice table
        self.inv_table = QtWidgets.QTableWidget()
        self.inv_table.setColumnCount(9)
        self.inv_table.setHorizontalHeaderLabels(
            ["Invoice #", "Vendor", "Invoice Date", "Due Date",
             "Amount", "Paid", "Balance", "Status", "Created By"]
        )
        hh = self.inv_table.horizontalHeader()
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
        hh.setSectionResizeMode(
    7, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(8, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.inv_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inv_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.inv_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.inv_table.setAlternatingRowColors(True)
        self.inv_table.verticalHeader().setVisible(False)
        self.inv_table.clicked.connect(self._on_invoice_clicked)
        self.inv_table.doubleClicked.connect(self._on_edit_invoice)
        splitter.addWidget(self.inv_table)

        # Payment detail
        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Payment History")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.pay_table = QtWidgets.QTableWidget()
        self.pay_table.setColumnCount(5)
        self.pay_table.setHorizontalHeaderLabels(
            ["Date", "Amount", "Method", "Reference", "Notes"])
        ph = self.pay_table.horizontalHeader()
        ph.setStyleSheet("color: black; font-weight: bold;")
        ph.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(
    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(
    2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(
    3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.pay_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pay_table.verticalHeader().setVisible(False)
        self.pay_table.setAlternatingRowColors(True)
        dv.addWidget(self.pay_table)
        splitter.addWidget(detail_w)
        splitter.setSizes([400, 180])
        v.addWidget(splitter, stretch=1)

        # Summary bar
        self.summary_lbl = QtWidgets.QLabel("")
        self.summary_lbl.setStyleSheet("color: white; font-size: 13px;")
        v.addWidget(self.summary_lbl)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Invoice",     self._on_new_invoice),
            ("Edit Invoice",    self._on_edit_invoice),
            ("Record Payment",  self._on_record_payment),
            ("Mark Overdue",    lambda: self._set_status("overdue")),
            ("Cancel Invoice",  lambda: self._set_status("cancelled")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh_invoices(self):
        status = self.status_filter.currentData()
        vendor_id = self.vendor_filter.currentData()
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")

        conds = ["(inv.due_date IS NULL OR inv.due_date BETWEEN %s AND %s)"]
        params = [d_from, d_to]
        if status:
            conds.append("inv.status = %s")
            params.append(status)
        if vendor_id:
            conds.append("inv.vendor_id = %s")
            params.append(vendor_id)
        where = " AND ".join(conds)

        conn = get_db()
        try:
            rows = conn.execute(f"""
                SELECT inv.id, inv.invoice_number, inv.invoice_date,
                    inv.due_date,
                       inv.amount, inv.description, inv.status,
                       inv.created_by,
                       s.company_name, s.first_name, s.last_name,
                       COALESCE(SUM(p.amount), 0) AS paid
                FROM ap_invoice inv
                LEFT JOIN supplier s ON s.id = inv.vendor_id
                LEFT JOIN ap_payment p ON p.invoice_id = inv.id
                WHERE {where}
                GROUP BY inv.id, inv.created_by,
                         s.company_name, s.first_name, s.last_name
                ORDER BY inv.due_date ASC, inv.id DESC
            """, params).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.inv_table.setRowCount(0)
        self._inv_row_ids = []
        total_amount = total_paid = 0.0
        for row in rows:
            r = self.inv_table.rowCount()
            self.inv_table.insertRow(r)
            self._inv_row_ids.append(row["id"])
            company = row["company_name"] or ""
            name = f"{
    row['first_name'] or ''} {
        row['last_name'] or ''}".strip()
            vendor_display = company if company else name
            paid = row["paid"]
            balance = row["amount"] - paid
            total_amount += row["amount"]
            total_paid += paid
            self.inv_table.setItem(r, 0, _ro(row["invoice_number"]))
            self.inv_table.setItem(r, 1, _ro(vendor_display))
            self.inv_table.setItem(r, 2, _ro(row["invoice_date"] or ""))
            self.inv_table.setItem(r, 3, _ro(row["due_date"] or ""))
            self.inv_table.setItem(r, 4, _ro_right(f"${row['amount']:,.2f}"))
            self.inv_table.setItem(r, 5, _ro_right(f"${paid:,.2f}"))
            self.inv_table.setItem(r, 6, _ro_right(f"${balance:,.2f}"))
            self.inv_table.setItem(r, 7, _ro(row["status"].capitalize()))
            self.inv_table.setItem(r, 8, _ro(row["created_by"] or ""))
            bg = QtGui.QColor(INV_COLORS.get(row["status"], "#ffffff"))
            for col in range(9):
                self.inv_table.item(r, col).setBackground(bg)

        total_balance = total_amount - total_paid
        self.summary_lbl.setText(
            f"Showing {len(rows)} invoices  |  "
            f"Total: ${total_amount:,.2f}  |  "
            f"Paid: ${total_paid:,.2f}  |  "
            f"Outstanding: ${total_balance:,.2f}"
        )
        self._selected_inv_id = None
        self._selected_inv_number = None
        self._selected_balance = 0.0
        self.pay_table.setRowCount(0)

    def _on_show_all(self):
        self.status_filter.blockSignals(True)
        self.status_filter.setCurrentIndex(0)
        self.status_filter.blockSignals(False)
        self.vendor_filter.blockSignals(True)
        self.vendor_filter.setCurrentIndex(0)
        self.vendor_filter.blockSignals(False)
        self.date_from.blockSignals(True)
        self.date_from.setDate(QtCore.QDate(2000, 1, 1))
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(True)
        self.date_to.setDate(QtCore.QDate(2099, 12, 31))
        self.date_to.blockSignals(False)
        self._refresh_invoices()

    def _on_invoice_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._inv_row_ids):
            return
        self._selected_inv_id = self._inv_row_ids[row]
        self._selected_inv_number = self.inv_table.item(row, 0).text()
        try:
            self._selected_balance = float(
                self.inv_table.item(row, 6).text().replace("$", "").replace(",", ""))  # noqa: E501
        except ValueError:
            self._selected_balance = 0.0
        self._refresh_payments()

    def _refresh_payments(self):
        self.pay_table.setRowCount(0)
        if self._selected_inv_id is None:
            return
        conn = get_db()
        try:
            payments = conn.execute(
                "SELECT payment_date, amount, payment_method, reference, notes"
                " FROM ap_payment WHERE invoice_id = %s ORDER BY payment_date "
                "DESC",
                (self._selected_inv_id,)
            ).fetchall()
        except psycopg2.OperationalError:
            payments = []
        conn.close()
        for p in payments:
            r = self.pay_table.rowCount()
            self.pay_table.insertRow(r)
            self.pay_table.setItem(r, 0, _ro(p["payment_date"] or ""))
            self.pay_table.setItem(r, 1, _ro_right(f"${p['amount']:,.2f}"))
            self.pay_table.setItem(r, 2, _ro(p["payment_method"] or ""))
            self.pay_table.setItem(r, 3, _ro(p["reference"] or ""))
            self.pay_table.setItem(r, 4, _ro(p["notes"] or ""))

    def _on_new_invoice(self):
        dlg = InvoiceDialog(parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_invoices()

    def _on_edit_invoice(self, _index=None):
        if self._selected_inv_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an invoice first.")
            return
        dlg = InvoiceDialog(invoice_id=self._selected_inv_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_invoices()

    def _on_record_payment(self):
        if self._selected_inv_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an invoice first.")
            return
        if self._selected_balance <= 0:
            QtWidgets.QMessageBox.information(self, "Fully Paid",
                                              "This invoice is already fully "
                                              "paid.")
            return
        dlg = RecordPaymentDialog(
            self._selected_inv_id, self._selected_inv_number,
            self._selected_balance, self
        )
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_invoices()
            self._refresh_payments()

    def _set_status(self, new_status):
        if self._selected_inv_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an invoice first.")
            return
        msg = f"Mark invoice as {new_status}?"
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE ap_invoice SET status = %s WHERE id = %s",
                         (new_status, self._selected_inv_id))
            conn.commit()
            conn.close()
            self._refresh_invoices()


class AccountsPayableWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = f"Accounts Payable — {email}" if email else "Accounts Payable"
        self.setWindowTitle(title)
        self.resize(1060, 700)
        _apply_blue_palette(self)
        self.setCentralWidget(AccountsPayableWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = AccountsPayableWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
