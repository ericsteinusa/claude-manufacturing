"""cs_calls_widget.py — PyQt6 Customer Service Calls widget.

Full add/update/delete/search screen over the ``calls2`` table, replacing the
legacy tkinter ``cs_calls.py``. Embedded as a tab by the CS menus and wrapped
in a window by ``cs_calls.py`` for the desktop menu-leaf launch.
"""
from ..db_pg import get_db
from ..log_utils import get_logger
from ..accounts import get_current_user_email
from ..cs_calls_core import (
    format_customer_label, parse_customer_id, validate_call)
from PyQt6 import QtCore, QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette


log = get_logger(__name__)

BUTTON_STYLE = (
    "QPushButton{background-color:white;border:2px solid "
    "black;border-radius:8px;"
    "padding:4px 12px;font-weight:bold;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
)
HDR_STYLE = "font-size:20px;font-weight:bold;color:white;padding:4px;"
LABEL_STYLE = "color:white;font-size:13px;"
GROUP_STYLE = "QGroupBox{color:white;font-weight:bold;}"
INPUT_STYLE = "background:white;border:1px solid black;border-radius:4px;"

COLS = ["ID", "Customer", "Problem", "Call Date", "Call Time",
        "Completion Date", "Completion Time", "Comments", "Completed",
        "Created By"]


def _ensure_schema():
    """Create the customer/calls2 tables if a fresh DB lacks them.

    Mirrors the legacy tkinter setup_database() but with Postgres DDL.
    """
    try:
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customer (
                id SERIAL PRIMARY KEY,
                first_name TEXT, last_name TEXT, company_name TEXT,
                phone_number TEXT, address TEXT, city TEXT, state TEXT,
                zip_code TEXT, email TEXT)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calls2 (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER REFERENCES customer(id),
                call TEXT, call_date TEXT, call_time TEXT,
                completion_date TEXT, completion_time TEXT,
                comments_box TEXT, completion_box INTEGER DEFAULT 0,
                created_by TEXT)
        """)
        conn.execute("""
            ALTER TABLE calls2
            ADD COLUMN IF NOT EXISTS created_by TEXT
        """)
        conn.commit()
        conn.close()
    except Exception:
        log.warning("Could not ensure calls2/customer schema", exc_info=True)


class CustomerServiceCallsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._selected_id = None
        self._build_ui()
        _ensure_schema()
        self._load_customers()
        self._load()

    # -- UI -------------------------------------------------------------
    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)

        hdr = QtWidgets.QLabel("Customer Service Calls")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        # Search row
        search_row = QtWidgets.QHBoxLayout()
        self._search = QtWidgets.QLineEdit()
        self._search.setStyleSheet(INPUT_STYLE)
        self._search.setPlaceholderText("Search customer or problem…")
        self._search.returnPressed.connect(self._load)
        search_btn = QtWidgets.QPushButton("Search")
        search_btn.setStyleSheet(BUTTON_STYLE)
        search_btn.clicked.connect(self._load)
        show_all_btn = QtWidgets.QPushButton("Show All")
        show_all_btn.setStyleSheet(BUTTON_STYLE)
        show_all_btn.clicked.connect(self._show_all)
        search_row.addWidget(self._search, 1)
        search_row.addWidget(search_btn)
        search_row.addWidget(show_all_btn)
        v.addLayout(search_row)

        # Table
        self._table = QtWidgets.QTableWidget(0, len(COLS))
        self._table.setHorizontalHeaderLabels(COLS)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.itemSelectionChanged.connect(self._on_select)
        v.addWidget(self._table, 1)

        # Form
        v.addWidget(self._build_form())

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        for label, slot in (("Add Record", self._add),
                            ("Update Record", self._update),
                            ("Delete Record", self._delete),
                            ("Clear", self._clear),
                            ("Refresh", self._load)):
            b = QtWidgets.QPushButton(label)
            b.setStyleSheet(BUTTON_STYLE)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        v.addLayout(btn_row)

    def _build_form(self):
        box = QtWidgets.QGroupBox("Call Record")
        box.setStyleSheet(GROUP_STYLE)
        grid = QtWidgets.QGridLayout(box)

        def _lbl(text):
            lab = QtWidgets.QLabel(text)
            lab.setStyleSheet(LABEL_STYLE)
            return lab

        self._customer = QtWidgets.QComboBox()
        self._customer.setStyleSheet(INPUT_STYLE)
        self._call = QtWidgets.QPlainTextEdit()
        self._call.setStyleSheet(INPUT_STYLE)
        self._call.setFixedHeight(56)
        self._call_date = QtWidgets.QLineEdit()
        self._call_time = QtWidgets.QLineEdit()
        self._comp_date = QtWidgets.QLineEdit()
        self._comp_time = QtWidgets.QLineEdit()
        self._comments = QtWidgets.QPlainTextEdit()
        self._comments.setStyleSheet(INPUT_STYLE)
        self._comments.setFixedHeight(56)
        for le in (self._call_date, self._call_time,
                   self._comp_date, self._comp_time):
            le.setStyleSheet(INPUT_STYLE)
        self._completed = QtWidgets.QCheckBox("Completed")
        self._completed.setStyleSheet(LABEL_STYLE)

        grid.addWidget(_lbl("Customer:"), 0, 0)
        grid.addWidget(self._customer, 0, 1)
        grid.addWidget(_lbl("Call Date:"), 0, 2)
        grid.addWidget(self._call_date, 0, 3)
        grid.addWidget(_lbl("Call Time:"), 0, 4)
        grid.addWidget(self._call_time, 0, 5)

        grid.addWidget(_lbl("Problem:"), 1, 0)
        grid.addWidget(self._call, 1, 1, 1, 5)

        grid.addWidget(_lbl("Completion Date:"), 2, 0)
        grid.addWidget(self._comp_date, 2, 1)
        grid.addWidget(_lbl("Completion Time:"), 2, 2)
        grid.addWidget(self._comp_time, 2, 3)
        grid.addWidget(self._completed, 2, 4, 1, 2)

        grid.addWidget(_lbl("Comments:"), 3, 0)
        grid.addWidget(self._comments, 3, 1, 1, 5)

        self._created_by_display = QtWidgets.QLabel(
            get_current_user_email() or "(unknown)")
        self._created_by_display.setStyleSheet(LABEL_STYLE)
        grid.addWidget(_lbl("Created by:"), 4, 0)
        grid.addWidget(self._created_by_display, 4, 1, 1, 5)
        return box

    # -- Data -----------------------------------------------------------
    def _load_customers(self):
        self._customer.clear()
        self._customer.addItem("", None)
        try:
            conn = get_db()
            rows = conn.execute(
                "SELECT id, first_name, last_name FROM customer "
                "ORDER BY id").fetchall()
            conn.close()
        except Exception:
            log.warning("Could not load customers", exc_info=True)
            rows = []
        for row in rows:
            label = format_customer_label(
                row["id"], row["first_name"], row["last_name"])
            self._customer.addItem(label, row["id"])

    def _load(self):
        term = self._search.text().strip()
        sql = (
            "SELECT c.id, c.customer_id, cu.first_name, cu.last_name, "
            "c.call, c.call_date, c.call_time, c.completion_date, "
            "c.completion_time, c.comments_box, c.completion_box, "
            "c.created_by "
            "FROM calls2 c LEFT JOIN customer cu ON cu.id = c.customer_id "
        )
        params = ()
        if term:
            sql += ("WHERE cu.first_name ILIKE %s OR cu.last_name ILIKE %s "
                    "OR c.call ILIKE %s ")
            like = f"%{term}%"
            params = (like, like, like)
        sql += "ORDER BY c.id DESC LIMIT 500"
        try:
            conn = get_db()
            rows = conn.execute(sql, params).fetchall()
            conn.close()
        except Exception:
            log.warning("Call list query failed; showing empty", exc_info=True)
            rows = []

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            customer = format_customer_label(
                row["customer_id"], row["first_name"], row["last_name"]) \
                if row["customer_id"] is not None else ""
            completed = "Yes" if row["completion_box"] else "No"
            values = [row["id"], customer, row["call"], row["call_date"],
                      row["call_time"], row["completion_date"],
                      row["completion_time"], row["comments_box"], completed,
                      row["created_by"]]
            for c, val in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(val if val is not None
                                                      else ""))
                if c == 0:
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, row["id"])
                self._table.setItem(r, c, item)
        self._table.resizeColumnsToContents()

    def _show_all(self):
        self._search.clear()
        self._load()

    # -- Selection ------------------------------------------------------
    def _on_select(self):
        items = self._table.selectedItems()
        if not items:
            return
        row_idx = items[0].row()
        call_id = self._table.item(row_idx, 0).data(
            QtCore.Qt.ItemDataRole.UserRole)
        try:
            conn = get_db()
            rec = conn.execute(
                "SELECT customer_id, call, call_date, call_time, "
                "completion_date, completion_time, comments_box, "
                "completion_box FROM calls2 WHERE id = %s",
                (call_id,)).fetchone()
            conn.close()
        except Exception:
            log.warning("Could not load call %s", call_id, exc_info=True)
            return
        if not rec:
            return
        self._selected_id = call_id
        idx = self._customer.findData(rec["customer_id"])
        self._customer.setCurrentIndex(idx if idx >= 0 else 0)
        self._call.setPlainText(rec["call"] or "")
        self._call_date.setText(rec["call_date"] or "")
        self._call_time.setText(rec["call_time"] or "")
        self._comp_date.setText(rec["completion_date"] or "")
        self._comp_time.setText(rec["completion_time"] or "")
        self._comments.setPlainText(rec["comments_box"] or "")
        self._completed.setChecked(bool(rec["completion_box"]))

    def _form_values(self):
        return {
            "customer_id": self._customer.currentData(),
            "call": self._call.toPlainText().strip(),
            "call_date": self._call_date.text().strip(),
            "call_time": self._call_time.text().strip(),
            "completion_date": self._comp_date.text().strip(),
            "completion_time": self._comp_time.text().strip(),
            "comments_box": self._comments.toPlainText().strip(),
            "completion_box": 1 if self._completed.isChecked() else 0,
        }

    # -- CRUD -----------------------------------------------------------
    def _add(self):
        vals = self._form_values()
        errors = validate_call(vals["customer_id"], vals["call"])
        if errors:
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "\n".join(errors))
            return
        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO calls2 (customer_id, call, call_date, call_time, "
                "completion_date, completion_time, comments_box, "
                "completion_box, created_by)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (parse_customer_id(vals["customer_id"]), vals["call"],
                 vals["call_date"], vals["call_time"], vals["completion_date"],
                 vals["completion_time"], vals["comments_box"],
                 vals["completion_box"], get_current_user_email() or None))
            conn.commit()
            conn.close()
        except Exception:
            log.warning("Add call failed", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, "Error", "Could not save the call.")
            return
        self._clear()
        self._load()

    def _update(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.information(
                self, "No Selection", "Select a call to update.")
            return
        vals = self._form_values()
        errors = validate_call(vals["customer_id"], vals["call"])
        if errors:
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "\n".join(errors))
            return
        try:
            conn = get_db()
            conn.execute(
                "UPDATE calls2 SET customer_id=%s, call=%s, call_date=%s, "
                "call_time=%s, completion_date=%s, completion_time=%s, "
                "comments_box=%s, completion_box=%s WHERE id=%s",
                (parse_customer_id(vals["customer_id"]), vals["call"],
                 vals["call_date"], vals["call_time"], vals["completion_date"],
                 vals["completion_time"], vals["comments_box"],
                 vals["completion_box"], self._selected_id))
            conn.commit()
            conn.close()
        except Exception:
            log.warning("Update call failed", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, "Error", "Could not update the call.")
            return
        self._clear()
        self._load()

    def _delete(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.information(
                self, "No Selection", "Select a call to delete.")
            return
        if QtWidgets.QMessageBox.question(
                self, "Delete", "Delete the selected call?") \
                != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            conn = get_db()
            conn.execute("DELETE FROM calls2 WHERE id=%s",
                         (self._selected_id,))
            conn.commit()
            conn.close()
        except Exception:
            log.warning("Delete call failed", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, "Error", "Could not delete the call.")
            return
        self._clear()
        self._load()

    def _clear(self):
        self._selected_id = None
        self._table.clearSelection()
        self._customer.setCurrentIndex(0)
        self._call.clear()
        self._call_date.clear()
        self._call_time.clear()
        self._comp_date.clear()
        self._comp_time.clear()
        self._comments.clear()
        self._completed.setChecked(False)
