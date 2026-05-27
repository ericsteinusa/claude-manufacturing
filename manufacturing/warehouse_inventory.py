"""
warehouse_inventory.py — Warehouse & Inventory Management
Tabs: Stock Overview | Receive Stock | Adjustments | Reports
"""
import sys
import os
from db_pg import get_db
import csv
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets


BLUE = QtGui.QColor(0, 85, 255)

BUTTON_STYLE = (
    "QPushButton{background-color:white;border:2px solid black;border-radius:10px;"
    "padding:4px 10px;font-weight:bold;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
)
INPUT_STYLE = "QLineEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
COMBO_STYLE = ("QComboBox{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
               "QComboBox QAbstractItemView{background-color:white;}")
DATE_STYLE = "QDateEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 4px;}"
SPIN_STYLE = "QDoubleSpinBox{background-color:white;border:2px solid black;border-radius:4px;padding:2px 4px;}"
TEXT_STYLE = "QTextEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
LABEL_STYLE = "color:white;font-size:13px;"
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid #aaa;background:white;}"
    "QTabBar::tab{background:#cce0ff;padding:6px 18px;font-weight:bold;}"
    "QTabBar::tab:selected{background:white;border-bottom:2px solid rgb(0,85,255);}"
)
GRP_STYLE = (
    "QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:8px;}"
    "QGroupBox::title{subcontrol-origin:margin;left:10px;}"
)

COLOR_CRITICAL = QtGui.QColor(255, 200, 200)   # red  — at/below reorder point
COLOR_LOW = QtGui.QColor(255, 243, 205)         # amber — within 2× reorder
COLOR_OK = QtGui.QColor(212, 237, 218)          # green — well stocked
COLOR_ZERO = QtGui.QColor(220, 220, 220)        # grey  — zero stock, no reorder set

ADJUST_TYPES = ["Cycle Count", "Damage / Shrinkage", "Return to Vendor", "Transfer", "Other"]


def _conn():
    c = get_db()
    return c


def init_db():
    import Supplier_entry as _se; _se.init_db()
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS product (
                id             SERIAL PRIMARY KEY,
                supplier_id    INTEGER REFERENCES supplier(id),
                name           TEXT NOT NULL,
                purchase_date  TEXT,
                purchase_price REAL DEFAULT 0.0,
                bin            TEXT DEFAULT '',
                amount         REAL DEFAULT 0.0,
                reorder_point  REAL DEFAULT 0.0
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS inventory_transaction (
                id         SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES product(id),
                trans_date TEXT NOT NULL,
                trans_type TEXT NOT NULL,
                quantity   REAL NOT NULL,
                reference  TEXT DEFAULT '',
                notes      TEXT DEFAULT ''
            )
        """)


def _apply_palette(widget):
    pal = QtGui.QPalette()
    for g in (QtGui.QPalette.ColorGroup.Active,
              QtGui.QPalette.ColorGroup.Inactive,
              QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(g, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(g, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter):
    item = QtWidgets.QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
    item.setTextAlignment(align)
    return item


def _ro_c(text):
    return _ro(text, QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)


def _ro_r(text):
    return _ro(text, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)


def _stock_color(amount, reorder):
    amount = float(amount or 0)
    reorder = float(reorder or 0)
    if amount <= 0 and reorder <= 0:
        return COLOR_ZERO
    if amount <= reorder:
        return COLOR_CRITICAL
    if amount <= reorder * 2:
        return COLOR_LOW
    return COLOR_OK


def _export_table(table, parent, default_name="inventory_export.csv"):
    if table.rowCount() == 0:
        QtWidgets.QMessageBox.information(parent, "Export", "No data to export.")
        return
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent, "Export to CSV", default_name, "CSV Files (*.csv)")
    if not path:
        return
    headers = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in range(table.rowCount()):
            w.writerow([table.item(r, c).text() if table.item(r, c) else ""
                        for c in range(table.columnCount())])
    QtWidgets.QMessageBox.information(parent, "Export Complete", f"Saved to:\n{path}")


# ── Main Window ────────────────────────────────────────────────────────────────

class WarehouseWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_palette(self)
        self._current_product_id = None
        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        title = QtWidgets.QLabel("Warehouse & Inventory Management")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:20px;font-weight:bold;color:white;padding:4px;")
        root.addWidget(title)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        self.tabs.currentChanged.connect(self._on_tab_change)
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_stock_tab(), "Stock Overview")
        self.tabs.addTab(self._build_receive_tab(), "Receive Stock")
        self.tabs.addTab(self._build_adjust_tab(), "Adjustments")
        self.tabs.addTab(self._build_reports_tab(), "Reports")

    # ── Tab 1: Stock Overview ──────────────────────────────────────────────

    def _build_stock_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # Filter row
        fr = QtWidgets.QHBoxLayout()
        fr.setSpacing(8)

        search_lbl = QtWidgets.QLabel("Search:")
        search_lbl.setStyleSheet(LABEL_STYLE)
        self.stock_search = QtWidgets.QLineEdit()
        self.stock_search.setStyleSheet(INPUT_STYLE)
        self.stock_search.setPlaceholderText("Filter by product name or bin...")
        self.stock_search.setMinimumWidth(220)
        self.stock_search.returnPressed.connect(self._load_stock)

        status_lbl = QtWidgets.QLabel("Status:")
        status_lbl.setStyleSheet(LABEL_STYLE)
        self.stock_status_filter = QtWidgets.QComboBox()
        self.stock_status_filter.setStyleSheet(COMBO_STYLE)
        self.stock_status_filter.addItems(["All", "Critical (≤ Reorder)", "Low (≤ 2× Reorder)", "OK"])

        btn_apply = QtWidgets.QPushButton("Apply")
        btn_apply.setStyleSheet(BUTTON_STYLE)
        btn_apply.setFixedHeight(28)
        btn_apply.clicked.connect(self._load_stock)

        btn_all = QtWidgets.QPushButton("Show All")
        btn_all.setStyleSheet(BUTTON_STYLE)
        btn_all.setFixedHeight(28)
        btn_all.clicked.connect(self._stock_show_all)

        fr.addWidget(search_lbl)
        fr.addWidget(self.stock_search)
        fr.addWidget(status_lbl)
        fr.addWidget(self.stock_status_filter)
        fr.addWidget(btn_apply)
        fr.addWidget(btn_all)
        fr.addStretch()

        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BUTTON_STYLE)
        btn_exp.setFixedHeight(28)
        btn_exp.clicked.connect(lambda: _export_table(self.stock_tbl, self, "stock_overview.csv"))
        fr.addWidget(btn_exp)
        v.addLayout(fr)

        # Stock table
        self.stock_tbl = QtWidgets.QTableWidget(0, 7)
        self.stock_tbl.setHorizontalHeaderLabels([
            "Product", "Bin", "On Hand", "Reorder Point", "Status",
            "Unit Cost", "Total Value"
        ])
        hh = self.stock_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5, 6):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.stock_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stock_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.stock_tbl.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.stock_tbl.verticalHeader().setVisible(False)
        self.stock_tbl.setSortingEnabled(True)
        self.stock_tbl.clicked.connect(self._stock_row_clicked)
        v.addWidget(self.stock_tbl, stretch=1)

        # Legend + summary
        bottom = QtWidgets.QHBoxLayout()
        for color, text in (
            (COLOR_CRITICAL, "  Critical (≤ Reorder)  "),
            (COLOR_LOW,      "  Low (≤ 2× Reorder)  "),
            (COLOR_OK,       "  OK  "),
            (COLOR_ZERO,     "  No Stock / No Reorder Set  "),
        ):
            dot = QtWidgets.QLabel("  ")
            dot.setAutoFillBackground(True)
            p = dot.palette()
            p.setColor(QtGui.QPalette.ColorRole.Window, color)
            dot.setPalette(p)
            dot.setFixedSize(16, 16)
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet("color:white;font-size:12px;")
            bottom.addWidget(dot)
            bottom.addWidget(lbl)
        bottom.addStretch()
        self.stock_summary_lbl = QtWidgets.QLabel("")
        self.stock_summary_lbl.setStyleSheet("color:white;font-size:12px;font-weight:bold;")
        bottom.addWidget(self.stock_summary_lbl)
        v.addLayout(bottom)

        # Quick-action buttons
        br = QtWidgets.QHBoxLayout()
        for text, fn in (("Receive Stock →", self._quick_receive),
                         ("Adjust Stock →", self._quick_adjust)):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        return w

    def _load_stock(self):
        keyword = self.stock_search.text().strip()
        status_filter = self.stock_status_filter.currentText()

        with _conn() as con:
            rows = con.execute("""
                SELECT p.id, p.name, p.bin, p.amount, p.reorder_point,
                       p.purchase_price,
                       COALESCE(s.company_name,
                           TRIM(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')),
                           '') AS supplier
                FROM product p
                LEFT JOIN supplier s ON s.id = p.supplier_id
                ORDER BY p.name
            """).fetchall()

        self.stock_tbl.setSortingEnabled(False)
        self.stock_tbl.setRowCount(0)
        self._stock_ids = []
        total_value = 0.0

        for row in rows:
            amount = float(row["amount"] or 0)
            reorder = float(row["reorder_point"] or 0)
            name = row["name"] or ""
            bin_loc = row["bin"] or ""
            unit_cost = float(row["purchase_price"] or 0)
            value = amount * unit_cost

            # Keyword filter
            if keyword and keyword.lower() not in name.lower() and keyword.lower() not in bin_loc.lower():
                continue

            # Status filter
            color = _stock_color(amount, reorder)
            if status_filter == "Critical (≤ Reorder)" and color != COLOR_CRITICAL:
                continue
            if status_filter == "Low (≤ 2× Reorder)" and color != COLOR_LOW:
                continue
            if status_filter == "OK" and color != COLOR_OK:
                continue

            if amount <= reorder:
                status_str = "CRITICAL"
            elif amount <= reorder * 2:
                status_str = "Low"
            else:
                status_str = "OK"

            r = self.stock_tbl.rowCount()
            self.stock_tbl.insertRow(r)
            self._stock_ids.append(row["id"])

            self.stock_tbl.setItem(r, 0, _ro(name))
            self.stock_tbl.setItem(r, 1, _ro_c(bin_loc))
            self.stock_tbl.setItem(r, 2, _ro_r(f"{amount:,.2f}"))
            self.stock_tbl.setItem(r, 3, _ro_r(f"{reorder:,.2f}"))
            self.stock_tbl.setItem(r, 4, _ro_c(status_str))
            self.stock_tbl.setItem(r, 5, _ro_r(f"${unit_cost:,.2f}"))
            self.stock_tbl.setItem(r, 6, _ro_r(f"${value:,.2f}"))

            for c in range(7):
                self.stock_tbl.item(r, c).setBackground(color)
            total_value += value

        self.stock_tbl.setSortingEnabled(True)
        count = self.stock_tbl.rowCount()
        self.stock_summary_lbl.setText(
            f"{count} product(s)   |   Total Value: ${total_value:,.2f}"
        )
        pass  # self.statusBar().showMessage(f"{count} products shown")

    def _stock_show_all(self):
        self.stock_search.clear()
        self.stock_status_filter.setCurrentIndex(0)
        self._load_stock()

    def _stock_row_clicked(self, index):
        r = index.row()
        if 0 <= r < len(self._stock_ids):
            self._current_product_id = self._stock_ids[r]

    def _quick_receive(self):
        if self._current_product_id:
            self._set_receive_product(self._current_product_id)
        self.tabs.setCurrentIndex(1)

    def _quick_adjust(self):
        if self._current_product_id:
            self._set_adjust_product(self._current_product_id)
        self.tabs.setCurrentIndex(2)

    # ── Tab 2: Receive Stock ───────────────────────────────────────────────

    def _build_receive_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)

        grp = QtWidgets.QGroupBox("Receive Inventory")
        grp.setStyleSheet(GRP_STYLE)
        grid = QtWidgets.QGridLayout(grp)
        grid.setSpacing(8)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.rcv_product = QtWidgets.QComboBox()
        self.rcv_product.setStyleSheet(COMBO_STYLE)
        self.rcv_product.setMinimumWidth(240)

        self.rcv_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.rcv_date.setStyleSheet(DATE_STYLE)
        self.rcv_date.setDisplayFormat("MM/dd/yyyy")
        self.rcv_date.setDate(QtCore.QDate.currentDate())

        self.rcv_qty = QtWidgets.QDoubleSpinBox()
        self.rcv_qty.setStyleSheet(SPIN_STYLE)
        self.rcv_qty.setRange(0.01, 999999)
        self.rcv_qty.setDecimals(2)
        self.rcv_qty.setValue(1.0)

        self.rcv_ref = QtWidgets.QLineEdit()
        self.rcv_ref.setStyleSheet(INPUT_STYLE)
        self.rcv_ref.setPlaceholderText("PO number, vendor ref, etc.")

        self.rcv_notes = QtWidgets.QLineEdit()
        self.rcv_notes.setStyleSheet(INPUT_STYLE)
        self.rcv_notes.setPlaceholderText("Optional notes...")

        grid.addWidget(lbl("Product:"), 0, 0)
        grid.addWidget(self.rcv_product, 0, 1)
        grid.addWidget(lbl("Date:"), 0, 2)
        grid.addWidget(self.rcv_date, 0, 3)
        grid.addWidget(lbl("Qty Received:"), 1, 0)
        grid.addWidget(self.rcv_qty, 1, 1)
        grid.addWidget(lbl("Reference:"), 1, 2)
        grid.addWidget(self.rcv_ref, 1, 3)
        grid.addWidget(lbl("Notes:"), 2, 0)
        grid.addWidget(self.rcv_notes, 2, 1, 1, 3)
        v.addWidget(grp)

        br = QtWidgets.QHBoxLayout()
        btn_save = QtWidgets.QPushButton("Post Receipt")
        btn_save.setStyleSheet(BUTTON_STYLE)
        btn_save.setFixedHeight(34)
        btn_save.clicked.connect(self._on_receive)
        btn_clear = QtWidgets.QPushButton("Clear")
        btn_clear.setStyleSheet(BUTTON_STYLE)
        btn_clear.setFixedHeight(34)
        btn_clear.clicked.connect(self._clear_receive)
        br.addWidget(btn_save)
        br.addWidget(btn_clear)
        br.addStretch()
        v.addLayout(br)

        # Recent receipts history
        hist_lbl = QtWidgets.QLabel("Recent Receipts")
        hist_lbl.setStyleSheet("color:white;font-size:13px;font-weight:bold;")
        v.addWidget(hist_lbl)

        self.rcv_hist_tbl = QtWidgets.QTableWidget(0, 5)
        self.rcv_hist_tbl.setHorizontalHeaderLabels(
            ["Date", "Product", "Qty Received", "Reference", "Notes"])
        hh = self.rcv_hist_tbl.horizontalHeader()
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (0, 2, 3):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.rcv_hist_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rcv_hist_tbl.setAlternatingRowColors(True)
        self.rcv_hist_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.rcv_hist_tbl, stretch=1)

        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BUTTON_STYLE)
        btn_exp.setFixedHeight(28)
        btn_exp.clicked.connect(lambda: _export_table(self.rcv_hist_tbl, self, "receipts.csv"))
        exp_row.addWidget(btn_exp)
        v.addLayout(exp_row)
        return w

    def _on_receive(self):
        pid = self.rcv_product.currentData()
        if not pid:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Select a product.")
            return
        qty = self.rcv_qty.value()
        trans_date = self.rcv_date.date().toString("yyyy-MM-dd")
        ref = self.rcv_ref.text().strip()
        notes = self.rcv_notes.text().strip()

        with _conn() as con:
            con.execute("""
                INSERT INTO inventory_transaction
                    (product_id, trans_date, trans_type, quantity, reference, notes)
                VALUES (%s, %s, 'Receive', %s, %s, %s)
            """, (pid, trans_date, qty, ref, notes))
            con.execute("UPDATE product SET amount = amount + %s WHERE id=%s", (qty, pid))

        self._clear_receive()
        self._load_stock()
        self._load_receive_history()
        pass  # self.statusBar().showMessage(f"Receipt posted: +{qty:,.2f} units")

    def _clear_receive(self):
        self.rcv_product.setCurrentIndex(0)
        self.rcv_qty.setValue(1.0)
        self.rcv_date.setDate(QtCore.QDate.currentDate())
        self.rcv_ref.clear()
        self.rcv_notes.clear()

    def _load_receive_history(self):
        with _conn() as con:
            rows = con.execute("""
                SELECT t.trans_date, p.name, t.quantity, t.reference, t.notes
                FROM inventory_transaction t
                JOIN product p ON p.id = t.product_id
                WHERE t.trans_type = 'Receive'
                ORDER BY t.trans_date DESC, t.id DESC
                LIMIT 100
            """).fetchall()
        self.rcv_hist_tbl.setRowCount(0)
        for row in rows:
            r = self.rcv_hist_tbl.rowCount()
            self.rcv_hist_tbl.insertRow(r)
            self.rcv_hist_tbl.setItem(r, 0, _ro_c(row["trans_date"] or ""))
            self.rcv_hist_tbl.setItem(r, 1, _ro(row["name"] or ""))
            self.rcv_hist_tbl.setItem(r, 2, _ro_r(f"{float(row['quantity']):,.2f}"))
            self.rcv_hist_tbl.setItem(r, 3, _ro(row["reference"] or ""))
            self.rcv_hist_tbl.setItem(r, 4, _ro(row["notes"] or ""))

    def _set_receive_product(self, product_id):
        idx = self.rcv_product.findData(product_id)
        if idx >= 0:
            self.rcv_product.setCurrentIndex(idx)

    # ── Tab 3: Adjustments ─────────────────────────────────────────────────

    def _build_adjust_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)

        grp = QtWidgets.QGroupBox("Stock Adjustment")
        grp.setStyleSheet(GRP_STYLE)
        grid = QtWidgets.QGridLayout(grp)
        grid.setSpacing(8)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.adj_product = QtWidgets.QComboBox()
        self.adj_product.setStyleSheet(COMBO_STYLE)
        self.adj_product.setMinimumWidth(240)
        self.adj_product.currentIndexChanged.connect(self._adj_product_changed)

        self.adj_on_hand_lbl = QtWidgets.QLabel("On Hand: —")
        self.adj_on_hand_lbl.setStyleSheet("color:white;font-size:13px;")

        self.adj_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.adj_date.setStyleSheet(DATE_STYLE)
        self.adj_date.setDisplayFormat("MM/dd/yyyy")
        self.adj_date.setDate(QtCore.QDate.currentDate())

        self.adj_type = QtWidgets.QComboBox()
        self.adj_type.setStyleSheet(COMBO_STYLE)
        self.adj_type.addItems(ADJUST_TYPES)

        self.adj_direction = QtWidgets.QComboBox()
        self.adj_direction.setStyleSheet(COMBO_STYLE)
        self.adj_direction.addItems(["+ Add", "− Remove"])

        self.adj_qty = QtWidgets.QDoubleSpinBox()
        self.adj_qty.setStyleSheet(SPIN_STYLE)
        self.adj_qty.setRange(0.01, 999999)
        self.adj_qty.setDecimals(2)
        self.adj_qty.setValue(1.0)

        self.adj_ref = QtWidgets.QLineEdit()
        self.adj_ref.setStyleSheet(INPUT_STYLE)
        self.adj_ref.setPlaceholderText("Reference / count sheet #...")

        self.adj_notes = QtWidgets.QLineEdit()
        self.adj_notes.setStyleSheet(INPUT_STYLE)
        self.adj_notes.setPlaceholderText("Reason / notes...")

        grid.addWidget(lbl("Product:"), 0, 0)
        grid.addWidget(self.adj_product, 0, 1)
        grid.addWidget(self.adj_on_hand_lbl, 0, 2, 1, 2)
        grid.addWidget(lbl("Date:"), 1, 0)
        grid.addWidget(self.adj_date, 1, 1)
        grid.addWidget(lbl("Adj. Type:"), 1, 2)
        grid.addWidget(self.adj_type, 1, 3)
        grid.addWidget(lbl("Direction:"), 2, 0)
        grid.addWidget(self.adj_direction, 2, 1)
        grid.addWidget(lbl("Quantity:"), 2, 2)
        grid.addWidget(self.adj_qty, 2, 3)
        grid.addWidget(lbl("Reference:"), 3, 0)
        grid.addWidget(self.adj_ref, 3, 1)
        grid.addWidget(lbl("Notes:"), 3, 2)
        grid.addWidget(self.adj_notes, 3, 3)
        v.addWidget(grp)

        br = QtWidgets.QHBoxLayout()
        btn_post = QtWidgets.QPushButton("Post Adjustment")
        btn_post.setStyleSheet(BUTTON_STYLE)
        btn_post.setFixedHeight(34)
        btn_post.clicked.connect(self._on_adjust)
        btn_clear = QtWidgets.QPushButton("Clear")
        btn_clear.setStyleSheet(BUTTON_STYLE)
        btn_clear.setFixedHeight(34)
        btn_clear.clicked.connect(self._clear_adjust)
        br.addWidget(btn_post)
        br.addWidget(btn_clear)
        br.addStretch()
        v.addLayout(br)

        hist_lbl = QtWidgets.QLabel("Adjustment History")
        hist_lbl.setStyleSheet("color:white;font-size:13px;font-weight:bold;")
        v.addWidget(hist_lbl)

        self.adj_hist_tbl = QtWidgets.QTableWidget(0, 6)
        self.adj_hist_tbl.setHorizontalHeaderLabels(
            ["Date", "Product", "Type", "Qty Change", "Reference", "Notes"])
        hh = self.adj_hist_tbl.horizontalHeader()
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (0, 2, 3, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.adj_hist_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.adj_hist_tbl.setAlternatingRowColors(True)
        self.adj_hist_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.adj_hist_tbl, stretch=1)

        exp_row = QtWidgets.QHBoxLayout()
        exp_row.addStretch()
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BUTTON_STYLE)
        btn_exp.setFixedHeight(28)
        btn_exp.clicked.connect(lambda: _export_table(self.adj_hist_tbl, self, "adjustments.csv"))
        exp_row.addWidget(btn_exp)
        v.addLayout(exp_row)
        return w

    def _adj_product_changed(self):
        pid = self.adj_product.currentData()
        if not pid:
            self.adj_on_hand_lbl.setText("On Hand: —")
            return
        with _conn() as con:
            row = con.execute("SELECT amount FROM product WHERE id=%s", (pid,)).fetchone()
        if row:
            self.adj_on_hand_lbl.setText(f"On Hand: {float(row['amount']):,.2f}")

    def _on_adjust(self):
        pid = self.adj_product.currentData()
        if not pid:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Select a product.")
            return
        qty = self.adj_qty.value()
        direction = 1 if self.adj_direction.currentIndex() == 0 else -1
        signed_qty = qty * direction
        adj_type = self.adj_type.currentText()
        trans_date = self.adj_date.date().toString("yyyy-MM-dd")
        ref = self.adj_ref.text().strip()
        notes = self.adj_notes.text().strip()

        # Check stock won't go negative
        with _conn() as con:
            row = con.execute("SELECT amount FROM product WHERE id=%s", (pid,)).fetchone()
            current = float(row["amount"] or 0) if row else 0
        if current + signed_qty < 0:
            QtWidgets.QMessageBox.warning(
                self, "Invalid Adjustment",
                f"Cannot remove {qty:,.2f} — only {current:,.2f} on hand.")
            return

        with _conn() as con:
            con.execute("""
                INSERT INTO inventory_transaction
                    (product_id, trans_date, trans_type, quantity, reference, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (pid, trans_date, adj_type, signed_qty, ref, notes))
            con.execute("UPDATE product SET amount = amount + %s WHERE id=%s", (signed_qty, pid))

        self._clear_adjust()
        self._load_stock()
        self._load_adjust_history()
        pass  # self.statusBar().showMessage(f"Adjustment posted: {signed_qty:+,.2f} units")

    def _clear_adjust(self):
        self.adj_product.setCurrentIndex(0)
        self.adj_date.setDate(QtCore.QDate.currentDate())
        self.adj_type.setCurrentIndex(0)
        self.adj_direction.setCurrentIndex(0)
        self.adj_qty.setValue(1.0)
        self.adj_ref.clear()
        self.adj_notes.clear()
        self.adj_on_hand_lbl.setText("On Hand: —")

    def _load_adjust_history(self):
        with _conn() as con:
            rows = con.execute("""
                SELECT t.trans_date, p.name, t.trans_type, t.quantity, t.reference, t.notes
                FROM inventory_transaction t
                JOIN product p ON p.id = t.product_id
                WHERE t.trans_type != 'Receive'
                ORDER BY t.trans_date DESC, t.id DESC
                LIMIT 100
            """).fetchall()
        self.adj_hist_tbl.setRowCount(0)
        for row in rows:
            qty = float(row["quantity"])
            r = self.adj_hist_tbl.rowCount()
            self.adj_hist_tbl.insertRow(r)
            self.adj_hist_tbl.setItem(r, 0, _ro_c(row["trans_date"] or ""))
            self.adj_hist_tbl.setItem(r, 1, _ro(row["name"] or ""))
            self.adj_hist_tbl.setItem(r, 2, _ro_c(row["trans_type"] or ""))
            self.adj_hist_tbl.setItem(r, 3, _ro_r(f"{qty:+,.2f}"))
            self.adj_hist_tbl.setItem(r, 4, _ro(row["reference"] or ""))
            self.adj_hist_tbl.setItem(r, 5, _ro(row["notes"] or ""))
            color = QtGui.QColor(212, 237, 218) if qty >= 0 else QtGui.QColor(255, 200, 200)
            for c in range(6):
                self.adj_hist_tbl.item(r, c).setBackground(color)

    def _set_adjust_product(self, product_id):
        idx = self.adj_product.findData(product_id)
        if idx >= 0:
            self.adj_product.setCurrentIndex(idx)

    # ── Tab 4: Reports ─────────────────────────────────────────────────────

    def _build_reports_tab(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)

        inner_tabs = QtWidgets.QTabWidget()
        inner_tabs.setStyleSheet(TAB_STYLE)
        v.addWidget(inner_tabs)

        inner_tabs.addTab(self._build_low_stock_report(), "Low Stock")
        inner_tabs.addTab(self._build_txn_history_report(), "Transaction History")
        inner_tabs.addTab(self._build_valuation_report(), "Valuation")
        return w

    # Low Stock report
    def _build_low_stock_report(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        top = QtWidgets.QHBoxLayout()
        self.low_stock_lbl = QtWidgets.QLabel("")
        self.low_stock_lbl.setStyleSheet("color:white;font-size:13px;font-weight:bold;")
        top.addWidget(self.low_stock_lbl)
        top.addStretch()
        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(self._load_low_stock)
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BUTTON_STYLE)
        btn_exp.setFixedHeight(28)
        btn_exp.clicked.connect(lambda: _export_table(self.low_stock_tbl, self, "low_stock.csv"))
        top.addWidget(btn)
        top.addWidget(btn_exp)
        v.addLayout(top)

        self.low_stock_tbl = QtWidgets.QTableWidget(0, 6)
        self.low_stock_tbl.setHorizontalHeaderLabels(
            ["Product", "Bin", "On Hand", "Reorder Point", "Shortage", "Status"])
        hh = self.low_stock_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.low_stock_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.low_stock_tbl.setAlternatingRowColors(True)
        self.low_stock_tbl.verticalHeader().setVisible(False)
        self.low_stock_tbl.setSortingEnabled(True)
        v.addWidget(self.low_stock_tbl, stretch=1)
        return w

    def _load_low_stock(self):
        with _conn() as con:
            rows = con.execute("""
                SELECT name, bin, amount, reorder_point
                FROM product
                WHERE amount <= reorder_point * 2 AND reorder_point > 0
                ORDER BY (reorder_point - amount) DESC
            """).fetchall()

        self.low_stock_tbl.setSortingEnabled(False)
        self.low_stock_tbl.setRowCount(0)
        critical = 0
        for row in rows:
            amount = float(row["amount"] or 0)
            reorder = float(row["reorder_point"] or 0)
            shortage = reorder - amount
            status = "CRITICAL" if amount <= reorder else "Low"
            if amount <= reorder:
                critical += 1
            color = COLOR_CRITICAL if amount <= reorder else COLOR_LOW

            r = self.low_stock_tbl.rowCount()
            self.low_stock_tbl.insertRow(r)
            self.low_stock_tbl.setItem(r, 0, _ro(row["name"] or ""))
            self.low_stock_tbl.setItem(r, 1, _ro_c(row["bin"] or ""))
            self.low_stock_tbl.setItem(r, 2, _ro_r(f"{amount:,.2f}"))
            self.low_stock_tbl.setItem(r, 3, _ro_r(f"{reorder:,.2f}"))
            self.low_stock_tbl.setItem(r, 4, _ro_r(f"{shortage:,.2f}" if shortage > 0 else "—"))
            self.low_stock_tbl.setItem(r, 5, _ro_c(status))
            for c in range(6):
                self.low_stock_tbl.item(r, c).setBackground(color)

        self.low_stock_tbl.setSortingEnabled(True)
        total = len(rows)
        self.low_stock_lbl.setText(
            f"{total} product(s) below 2× reorder point — {critical} critical")

    # Transaction history report
    def _build_txn_history_report(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        fr.setSpacing(8)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.txn_product_filter = QtWidgets.QComboBox()
        self.txn_product_filter.setStyleSheet(COMBO_STYLE)
        self.txn_product_filter.setMinimumWidth(180)

        self.txn_type_filter = QtWidgets.QComboBox()
        self.txn_type_filter.setStyleSheet(COMBO_STYLE)
        self.txn_type_filter.addItems(["All Types", "Receive"] + ADJUST_TYPES)

        self.txn_from = QtWidgets.QDateEdit(calendarPopup=True)
        self.txn_from.setStyleSheet(DATE_STYLE)
        self.txn_from.setDisplayFormat("MM/dd/yyyy")
        self.txn_from.setDate(QtCore.QDate.currentDate().addDays(-90))

        self.txn_to = QtWidgets.QDateEdit(calendarPopup=True)
        self.txn_to.setStyleSheet(DATE_STYLE)
        self.txn_to.setDisplayFormat("MM/dd/yyyy")
        self.txn_to.setDate(QtCore.QDate.currentDate())

        btn_run = QtWidgets.QPushButton("Run")
        btn_run.setStyleSheet(BUTTON_STYLE)
        btn_run.setFixedHeight(28)
        btn_run.clicked.connect(self._load_txn_history)

        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BUTTON_STYLE)
        btn_exp.setFixedHeight(28)
        btn_exp.clicked.connect(lambda: _export_table(self.txn_tbl, self, "txn_history.csv"))

        fr.addWidget(lbl("Product:"))
        fr.addWidget(self.txn_product_filter)
        fr.addWidget(lbl("Type:"))
        fr.addWidget(self.txn_type_filter)
        fr.addWidget(lbl("From:"))
        fr.addWidget(self.txn_from)
        fr.addWidget(lbl("To:"))
        fr.addWidget(self.txn_to)
        fr.addWidget(btn_run)
        fr.addStretch()
        fr.addWidget(btn_exp)
        v.addLayout(fr)

        self.txn_tbl = QtWidgets.QTableWidget(0, 6)
        self.txn_tbl.setHorizontalHeaderLabels(
            ["Date", "Product", "Type", "Qty Change", "Reference", "Notes"])
        hh = self.txn_tbl.horizontalHeader()
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (0, 2, 3, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.txn_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.txn_tbl.setAlternatingRowColors(True)
        self.txn_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.txn_tbl, stretch=1)
        return w

    def _load_txn_history(self):
        pid = self.txn_product_filter.currentData()
        txn_type = self.txn_type_filter.currentText()
        from_s = self.txn_from.date().toString("yyyy-MM-dd")
        to_s = self.txn_to.date().toString("yyyy-MM-dd")

        q = """
            SELECT t.trans_date, p.name, t.trans_type, t.quantity, t.reference, t.notes
            FROM inventory_transaction t
            JOIN product p ON p.id = t.product_id
            WHERE t.trans_date BETWEEN %s AND %s
        """
        params = [from_s, to_s]
        if pid:
            q += " AND t.product_id = %s"
            params.append(pid)
        if txn_type != "All Types":
            q += " AND t.trans_type = %s"
            params.append(txn_type)
        q += " ORDER BY t.trans_date DESC, t.id DESC"

        with _conn() as con:
            rows = con.execute(q, params).fetchall()

        self.txn_tbl.setRowCount(0)
        for row in rows:
            qty = float(row["quantity"])
            r = self.txn_tbl.rowCount()
            self.txn_tbl.insertRow(r)
            self.txn_tbl.setItem(r, 0, _ro_c(row["trans_date"] or ""))
            self.txn_tbl.setItem(r, 1, _ro(row["name"] or ""))
            self.txn_tbl.setItem(r, 2, _ro_c(row["trans_type"] or ""))
            self.txn_tbl.setItem(r, 3, _ro_r(f"{qty:+,.2f}"))
            self.txn_tbl.setItem(r, 4, _ro(row["reference"] or ""))
            self.txn_tbl.setItem(r, 5, _ro(row["notes"] or ""))
            color = QtGui.QColor(212, 237, 218) if qty >= 0 else QtGui.QColor(255, 200, 200)
            for c in range(6):
                self.txn_tbl.item(r, c).setBackground(color)

        pass  # self.statusBar().showMessage(f"{len(rows)} transaction(s) shown")

    # Valuation report
    def _build_valuation_report(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)

        top = QtWidgets.QHBoxLayout()
        self.val_total_lbl = QtWidgets.QLabel("")
        self.val_total_lbl.setStyleSheet("color:white;font-size:14px;font-weight:bold;")
        top.addWidget(self.val_total_lbl)
        top.addStretch()
        btn = QtWidgets.QPushButton("Refresh")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.clicked.connect(self._load_valuation)
        btn_exp = QtWidgets.QPushButton("Export CSV")
        btn_exp.setStyleSheet(BUTTON_STYLE)
        btn_exp.setFixedHeight(28)
        btn_exp.clicked.connect(lambda: _export_table(self.val_tbl, self, "inventory_valuation.csv"))
        top.addWidget(btn)
        top.addWidget(btn_exp)
        v.addLayout(top)

        self.val_tbl = QtWidgets.QTableWidget(0, 5)
        self.val_tbl.setHorizontalHeaderLabels(
            ["Product", "Bin", "On Hand", "Unit Cost", "Total Value"])
        hh = self.val_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.val_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.val_tbl.setAlternatingRowColors(True)
        self.val_tbl.verticalHeader().setVisible(False)
        self.val_tbl.setSortingEnabled(True)
        v.addWidget(self.val_tbl, stretch=1)
        return w

    def _load_valuation(self):
        with _conn() as con:
            rows = con.execute("""
                SELECT name, bin, amount, purchase_price
                FROM product
                ORDER BY (amount * purchase_price) DESC
            """).fetchall()

        self.val_tbl.setSortingEnabled(False)
        self.val_tbl.setRowCount(0)
        total = 0.0
        for row in rows:
            amount = float(row["amount"] or 0)
            cost = float(row["purchase_price"] or 0)
            value = amount * cost
            total += value
            r = self.val_tbl.rowCount()
            self.val_tbl.insertRow(r)
            self.val_tbl.setItem(r, 0, _ro(row["name"] or ""))
            self.val_tbl.setItem(r, 1, _ro_c(row["bin"] or ""))
            self.val_tbl.setItem(r, 2, _ro_r(f"{amount:,.2f}"))
            self.val_tbl.setItem(r, 3, _ro_r(f"${cost:,.2f}"))
            self.val_tbl.setItem(r, 4, _ro_r(f"${value:,.2f}"))

        self.val_tbl.setSortingEnabled(True)
        self.val_total_lbl.setText(
            f"{len(rows)} product(s)   |   Total Inventory Value: ${total:,.2f}")

    # ── Shared helpers ─────────────────────────────────────────────────────

    def _refresh_product_combos(self):
        with _conn() as con:
            products = con.execute(
                "SELECT id, name FROM product ORDER BY name").fetchall()

        for combo in (self.rcv_product, self.adj_product, self.txn_product_filter):
            pid = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            placeholder = "(all products)" if combo is self.txn_product_filter else "-- select product --"
            combo.addItem(placeholder, None)
            for p in products:
                combo.addItem(p["name"], p["id"])
            # Restore previous selection
            if pid:
                idx = combo.findData(pid)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def _on_tab_change(self, idx):
        tab_names = ["Stock Overview", "Receive Stock", "Adjustments", "Reports"]
        if idx == 1:
            self._load_receive_history()
        elif idx == 2:
            self._load_adjust_history()

    def _refresh_all(self):
        self._refresh_product_combos()
        self._load_stock()
        self._load_receive_history()
        self._load_adjust_history()
        self._load_low_stock()
        self._load_valuation()
        self._stock_ids = getattr(self, "_stock_ids", [])


class WarehouseWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Warehouse & Inventory")
        self.resize(1200, 780)
        _apply_palette(self)
        self.setCentralWidget(WarehouseWidget())


if __name__ == "__main__":
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    win = WarehouseWindow()
    win.show()
    sys.exit(app.exec())
