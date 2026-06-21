import sys
import psycopg2
from .db_pg import get_db
from .bom import (init_item_master, bom_would_create_cycle,
                  explode_bom_to_wo, ItemSettingsDialog)
from .work_orders_core import next_wo_number
from PyQt6 import QtCore, QtGui, QtWidgets
from .qt_theme import (
    BUTTON_STYLE,
    INPUT_STYLE,
    COMBO_STYLE,
    LABEL_STYLE,
    apply_blue_palette as _apply_blue_palette,
    ro as _ro,
)

from .button_nav import ButtonNav
from .accounts import get_current_user_email

WO_COLORS = {
    "planned":     "#ffffff",
    "in_progress": "#fff3cd",
    "completed":   "#d4edda",
    "on_hold":     "#ffe0b2",
    "cancelled":   "#dcdcdc",
}


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS work_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wo_number TEXT NOT NULL UNIQUE,
            product_id INTEGER,
            description TEXT,
            quantity INTEGER DEFAULT 1,
            start_date TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'planned',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wo_material (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wo_id INTEGER NOT NULL REFERENCES work_order(id),
            product_id INTEGER NOT NULL,
            qty_required REAL DEFAULT 1.0,
            qty_issued REAL DEFAULT 0.0,
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            component_id INTEGER NOT NULL,
            qty_required REAL DEFAULT 1.0,
            unit TEXT,
            notes TEXT
        )
    """)
    try:
        conn.execute(
            "ALTER TABLE work_order ADD COLUMN IF NOT EXISTS created_by TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()
    # Reconcile the item-master (make/buy, lead time, uom) and the bom
    # scrap_pct column. Resilient if product/bom don't exist yet.
    init_item_master()


def _next_wo_num():
    conn = get_db()
    num = next_wo_number(conn)
    conn.close()
    return num


def _load_products(combo, include_none=True):
    conn = get_db()
    try:
        prods = conn.execute(
            "SELECT id, name AS product_name FROM product ORDER BY name"
        ).fetchall()
    except psycopg2.OperationalError:
        prods = []
    conn.close()
    combo.clear()
    if include_none:
        combo.addItem("(none)", None)
    for p in prods:
        combo.addItem(p["product_name"], p["id"])


# ── Dialogs ─────────────────────────────────────────────────────────────

class NewWODialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Work Order")
        self.resize(480, 310)
        _apply_blue_palette(self)
        self.wo_id = None
        self._exploded = 0
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.wo_num = QtWidgets.QLineEdit(_next_wo_num())
        self.wo_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("WO Number:"), self.wo_num)

        self.product_combo = QtWidgets.QComboBox()
        self.product_combo.setStyleSheet(COMBO_STYLE)
        self.product_combo.currentIndexChanged.connect(
            self._on_product_changed)
        _load_products(self.product_combo, include_none=True)
        layout.addRow(lbl("Finished Good:"), self.product_combo)

        self.desc = QtWidgets.QLineEdit()
        self.desc.setStyleSheet(INPUT_STYLE)
        self.desc.setPlaceholderText("What is being produced")
        layout.addRow(lbl("Description:"), self.desc)

        self.qty = QtWidgets.QSpinBox()
        self.qty.setRange(1, 999999)
        self.qty.setValue(1)
        self.qty.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Quantity:"), self.qty)

        self.start_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        self.start_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Start Date:"), self.start_date)

        self.due_date = QtWidgets.QDateEdit(
    QtCore.QDate.currentDate().addDays(7))
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        self.notes.setPlaceholderText("Optional notes")
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

    def _on_product_changed(self):
        pid = self.product_combo.currentData()
        if pid is not None and not self.desc.text():
            self.desc.setText(self.product_combo.currentText())

    def _on_ok(self):
        wo_num = self.wo_num.text().strip()
        if not wo_num:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "WO number is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO work_order (wo_number, product_id, description, "
                "quantity,"
                " start_date, due_date, status, notes, created_by) VALUES "
                "(?,?,?,?,?,?,?,?,?)",
                (wo_num, self.product_combo.currentData(),
                 self.desc.text().strip(), self.qty.value(),
                 self.start_date.date().toString("yyyy-MM-dd"),
                 self.due_date.date().toString("yyyy-MM-dd"),
                 "planned", self.notes.text().strip(),
                 self._created_by)
            )
            self.wo_id = cur.lastrowid
            # Seed the material list from the finished good's BOM, in the same
            # transaction. No-op when the product has no BOM.
            pid = self.product_combo.currentData()
            self._exploded = 0
            if pid is not None and self.wo_id is not None:
                self._exploded = explode_bom_to_wo(
                    conn, self.wo_id, pid, self.qty.value())
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(
    self, "Duplicate", f"WO number '{wo_num}' already exists.")
            conn.close()
            return
        conn.close()
        if self._exploded:
            QtWidgets.QMessageBox.information(
                self, "BOM Applied",
                f"Added {self._exploded} material line(s) from the BOM.")
        self.accept()


class AddMaterialDialog(QtWidgets.QDialog):
    def __init__(self, wo_id, wo_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Add Material — {wo_number}")
        self.resize(420, 200)
        _apply_blue_palette(self)
        self._wo_id = wo_id
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
        _load_products(self.product_combo, include_none=False)
        layout.addRow(lbl("Component:"), self.product_combo)

        self.qty_req = QtWidgets.QDoubleSpinBox()
        self.qty_req.setRange(0.001, 999999.0)
        self.qty_req.setDecimals(3)
        self.qty_req.setValue(1.0)
        self.qty_req.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Qty Required:"), self.qty_req)

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
        prod_id = self.product_combo.currentData()
        if prod_id is None:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Select a component product.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO wo_material (wo_id, product_id, qty_required, notes) "
            "VALUES (?,?,?,?)",
            (self._wo_id, prod_id, self.qty_req.value(), self.notes.text().strip())  # noqa: E501
        )
        conn.commit()
        conn.close()
        self.accept()


class IssueMaterialsDialog(QtWidgets.QDialog):
    def __init__(self, wo_id, wo_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Issue Materials — {wo_number}")
        self.resize(600, 340)
        _apply_blue_palette(self)
        self._wo_id = wo_id
        self._spinboxes = []
        self._mat_ids = []
        self._prod_ids = []
        self._build_ui()
        self._load_materials()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Specify qty to issue from stock for each material:")
        info.setStyleSheet(LABEL_STYLE)
        layout.addWidget(info)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Component", "Qty Required", "Qty Issued", "Issue Now"])
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            hh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load_materials(self):
        conn = get_db()
        try:
            mats = conn.execute("""
                SELECT m.id, p.name AS product_name, p.id AS prod_id, p.amount,
                       m.qty_required, m.qty_issued
                FROM wo_material m JOIN product p ON p.id = m.product_id
                WHERE m.wo_id = ?
            """, (self._wo_id,)).fetchall()
        except psycopg2.OperationalError:
            mats = []
        conn.close()

        self.table.setRowCount(0)
        self._spinboxes = []
        self._mat_ids = []
        self._prod_ids = []
        for mat in mats:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._mat_ids.append(mat["id"])
            self._prod_ids.append(mat["prod_id"])
            remaining = max(0.0, mat["qty_required"] - mat["qty_issued"])
            self.table.setItem(r, 0, _ro(mat["product_name"]))
            self.table.setItem(r, 1, _ro(f"{mat['qty_required']:.3f}"))
            self.table.setItem(r, 2, _ro(f"{mat['qty_issued']:.3f}"))
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.0, remaining)
            spin.setDecimals(3)
            spin.setValue(remaining)
            self.table.setCellWidget(r, 3, spin)
            self._spinboxes.append(spin)

    def _on_ok(self):
        if not self._mat_ids:
            self.accept()
            return
        conn = get_db()
        for mat_id, prod_id, spin in zip(
            self._mat_ids, self._prod_ids, self._spinboxes):
            qty = spin.value()
            if qty <= 0:
                continue
            conn.execute(
                "UPDATE wo_material SET qty_issued = qty_issued + ? WHERE id "
                "= ?", (
                    qty, mat_id)
            )
            conn.execute(
                "UPDATE product SET amount = amount - ? WHERE id = ?", (qty,
                                                                        prod_id)  # noqa: E501
            )
            try:
                conn.execute(
                    "INSERT INTO inventory_transaction (product_id, "
                    "trans_date, trans_type, quantity, reference)"
                    " VALUES (?,?,?,?,?)",
                    (prod_id, QtCore.QDate.currentDate().toString("yyyy-MM-dd"),  # noqa: E501
                     "issue", -qty,
                     conn.execute("SELECT wo_number FROM work_order WHERE id=?",  # noqa: E501
                                  (self._wo_id,)).fetchone()["wo_number"])
                )
            except psycopg2.OperationalError:
                pass
        conn.commit()
        conn.close()
        self.accept()


class AddBOMItemDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add BOM Item")
        self.resize(440, 240)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.finished_combo = QtWidgets.QComboBox()
        self.finished_combo.setStyleSheet(COMBO_STYLE)
        _load_products(self.finished_combo, include_none=False)
        layout.addRow(lbl("Finished Good:"), self.finished_combo)

        self.component_combo = QtWidgets.QComboBox()
        self.component_combo.setStyleSheet(COMBO_STYLE)
        _load_products(self.component_combo, include_none=False)
        layout.addRow(lbl("Component:"), self.component_combo)

        self.qty_req = QtWidgets.QDoubleSpinBox()
        self.qty_req.setRange(0.001, 999999.0)
        self.qty_req.setDecimals(3)
        self.qty_req.setValue(1.0)
        self.qty_req.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Qty Required:"), self.qty_req)

        self.unit = QtWidgets.QLineEdit()
        self.unit.setStyleSheet(INPUT_STYLE)
        self.unit.setPlaceholderText("e.g. each, kg, L")
        layout.addRow(lbl("Unit:"), self.unit)

        self.scrap_pct = QtWidgets.QDoubleSpinBox()
        self.scrap_pct.setRange(0.0, 100.0)
        self.scrap_pct.setDecimals(2)
        self.scrap_pct.setSuffix(" %")
        self.scrap_pct.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Scrap:"), self.scrap_pct)

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
        prod_id = self.finished_combo.currentData()
        comp_id = self.component_combo.currentData()
        if prod_id is None or comp_id is None:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Select both products.")
            return
        if prod_id == comp_id:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Finished good and component must differ.")
            return
        conn = get_db()
        if bom_would_create_cycle(conn, prod_id, comp_id):
            conn.close()
            QtWidgets.QMessageBox.warning(
                self, "Input Error",
                "That component already (directly or indirectly) requires "
                "this finished good — it would create a BOM cycle.")
            return
        conn.execute(
            "INSERT INTO bom (product_id, component_id, qty_required, unit, "
            "scrap_pct, notes) VALUES (?,?,?,?,?,?)",
            (prod_id, comp_id, self.qty_req.value(),
             self.unit.text().strip(), self.scrap_pct.value(),
             self.notes.text().strip())
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ─────────────────────────────────────────────────────────

class WorkOrders(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Production / Work Orders — {email}" if email
                 else "Production / Work Orders")
        self.setWindowTitle(title)
        self.resize(920, 640)
        _apply_blue_palette(self)
        self._wo_row_ids = []
        self._selected_wo_id = None
        self._selected_wo_number = None
        self._bom_row_ids = []
        self._selected_bom_id = None
        self._build_ui()
        init_db()
        self._refresh_wo()
        self._refresh_bom()

    def _build_ui(self):
        self._tabs = ButtonNav()
        self._tabs.setStyleSheet(
            "QTabBar::tab{background:white; border:1px solid black; "
            "padding:4px 10px;}"
            "QTabBar::tab:selected{background:rgb(85,255,255);}"
        )
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)
        self._build_wo_tab()
        self._build_bom_tab()

    def _on_tab_changed(self, index):
        if index == 0:
            self._refresh_wo()
        elif index == 1:
            self._refresh_bom()

    # ── Work Orders tab ─────────────────────────────────────────────────────

    def _build_wo_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.wo_status_filter = QtWidgets.QComboBox()
        self.wo_status_filter.setStyleSheet(COMBO_STYLE)
        self.wo_status_filter.addItem("(all)", None)
        for s in ("planned", "in_progress",
                  "completed", "on_hold", "cancelled"):
            self.wo_status_filter.addItem(s.replace("_", " ").capitalize(), s)
        self.wo_status_filter.currentIndexChanged.connect(self._refresh_wo)
        fr.addWidget(self.wo_status_filter)
        fr.addSpacing(10)

        lbl_p = QtWidgets.QLabel("Search:")
        lbl_p.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_p)
        self.wo_search = QtWidgets.QLineEdit()
        self.wo_search.setStyleSheet(INPUT_STYLE)
        self.wo_search.setFixedWidth(180)
        self.wo_search.returnPressed.connect(self._refresh_wo)
        fr.addWidget(self.wo_search)
        b_search = QtWidgets.QPushButton("Search")
        b_search.setStyleSheet(BUTTON_STYLE)
        b_search.setFixedHeight(28)
        b_search.clicked.connect(self._refresh_wo)
        fr.addWidget(b_search)
        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_wo_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.wo_table = QtWidgets.QTableWidget()
        self.wo_table.setColumnCount(8)
        self.wo_table.setHorizontalHeaderLabels(
            ["WO #", "Description", "Product", "Qty",
                "Start Date", "Due Date", "Status", "Created By"]
        )
        hh = self.wo_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6, 7):
            hh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.wo_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.wo_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.wo_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.wo_table.setAlternatingRowColors(True)
        self.wo_table.verticalHeader().setVisible(False)
        self.wo_table.clicked.connect(self._on_wo_clicked)
        splitter.addWidget(self.wo_table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Materials")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.mat_table = QtWidgets.QTableWidget()
        self.mat_table.setColumnCount(4)
        self.mat_table.setHorizontalHeaderLabels(
            ["Component", "Qty Required", "Qty Issued", "Remaining"])
        mh = self.mat_table.horizontalHeader()
        mh.setStyleSheet("color: black; font-weight: bold;")
        mh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            mh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.mat_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mat_table.verticalHeader().setVisible(False)
        self.mat_table.setAlternatingRowColors(True)
        dv.addWidget(self.mat_table)
        splitter.addWidget(detail_w)
        splitter.setSizes([360, 200])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Work Order",   self._on_new_wo),
            ("Add Material",     self._on_add_material),
            ("Issue Materials",  self._on_issue_materials),
            ("Start (In Progress)", lambda: self._set_wo_status(
                "in_progress", "Mark as In Progress?")),
            ("Complete",         lambda: self._set_wo_status(
                "completed",   "Mark as Completed?")),
            ("On Hold",          lambda: self._set_wo_status(
                "on_hold",     "Put On Hold?")),
            ("Cancel",           lambda: self._set_wo_status(
                "cancelled",   "Cancel this work order?")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Work Orders")

    def _refresh_wo(self):
        status = self.wo_status_filter.currentData()
        term   = self.wo_search.text().strip()
        base = """
            SELECT wo.id, wo.wo_number, wo.description, p.name AS product_name,
                   wo.quantity, wo.start_date, wo.due_date, wo.status,
                   wo.created_by
            FROM work_order wo
            LEFT JOIN product p ON p.id = wo.product_id
        """
        conds, params = [], []
        if status:
            conds.append("wo.status = ?")
            params.append(status)
        if term:
            conds.append("(wo.wo_number LIKE ? OR wo.description LIKE ?)")
            params += [f"%{term}%", f"%{term}%"]
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        conn = get_db()
        try:
            rows = conn.execute(
    base +
    where +
    " ORDER BY wo.due_date, wo.wo_number",
     params).fetchall()
        except psycopg2.OperationalError:
            rows = conn.execute(
                "SELECT id, wo_number, description, NULL AS product_name,"
                " quantity, start_date, due_date, status,"
                " NULL AS created_by FROM work_order"
                + where + " ORDER BY due_date, wo_number", params
            ).fetchall()
        conn.close()

        self.wo_table.setRowCount(0)
        self._wo_row_ids = []
        for row in rows:
            r = self.wo_table.rowCount()
            self.wo_table.insertRow(r)
            self._wo_row_ids.append(row["id"])
            self.wo_table.setItem(r, 0, _ro(row["wo_number"]))
            self.wo_table.setItem(r, 1, _ro(row["description"] or ""))
            self.wo_table.setItem(r, 2, _ro(row["product_name"] or ""))
            self.wo_table.setItem(r, 3, _ro(str(row["quantity"])))
            self.wo_table.setItem(r, 4, _ro(row["start_date"] or ""))
            self.wo_table.setItem(r, 5, _ro(row["due_date"] or ""))
            self.wo_table.setItem(
    r, 6, _ro(
        row["status"].replace(
            "_", " ").capitalize()))
            self.wo_table.setItem(r, 7, _ro(row["created_by"] or ""))
            bg = QtGui.QColor(WO_COLORS.get(row["status"], "#ffffff"))
            for col in range(8):
                self.wo_table.item(r, col).setBackground(bg)

        self._selected_wo_id = None
        self._selected_wo_number = None
        self.mat_table.setRowCount(0)

    def _on_wo_show_all(self):
        self.wo_search.clear()
        self.wo_status_filter.blockSignals(True)
        self.wo_status_filter.setCurrentIndex(0)
        self.wo_status_filter.blockSignals(False)
        self._refresh_wo()

    def _on_wo_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._wo_row_ids):
            return
        self._selected_wo_id = self._wo_row_ids[row]
        self._selected_wo_number = self.wo_table.item(row, 0).text()
        self._refresh_materials()

    def _refresh_materials(self):
        self.mat_table.setRowCount(0)
        if self._selected_wo_id is None:
            return
        conn = get_db()
        try:
            mats = conn.execute("""
                SELECT m.qty_required, m.qty_issued, p.name AS product_name
                FROM wo_material m JOIN product p ON p.id = m.product_id
                WHERE m.wo_id = ?
            """, (self._selected_wo_id,)).fetchall()
        except psycopg2.OperationalError:
            mats = []
        conn.close()
        for mat in mats:
            r = self.mat_table.rowCount()
            self.mat_table.insertRow(r)
            remaining = max(0.0, mat["qty_required"] - mat["qty_issued"])
            self.mat_table.setItem(r, 0, _ro(mat["product_name"]))
            self.mat_table.setItem(r, 1, _ro(f"{mat['qty_required']:.3f}"))
            self.mat_table.setItem(r, 2, _ro(f"{mat['qty_issued']:.3f}"))
            self.mat_table.setItem(r, 3, _ro(f"{remaining:.3f}"))

    def _on_new_wo(self):
        dlg = NewWODialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_wo()

    def _on_add_material(self):
        if self._selected_wo_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a work order first.")
            return
        dlg = AddMaterialDialog(
    self._selected_wo_id,
    self._selected_wo_number,
     self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_materials()

    def _on_issue_materials(self):
        if self._selected_wo_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a work order first.")
            return
        dlg = IssueMaterialsDialog(
    self._selected_wo_id,
    self._selected_wo_number,
     self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_wo()
            self._refresh_materials()

    def _set_wo_status(self, new_status, msg):
        if self._selected_wo_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a work order first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute(
    "UPDATE work_order SET status = ? WHERE id = ?",
    (new_status,
     self._selected_wo_id))
            conn.commit()
            conn.close()
            self._refresh_wo()

    # ── BOM tab ─────────────────────────────────────────────────────────────

    def _build_bom_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_f = QtWidgets.QLabel("Filter by product:")
        lbl_f.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_f)
        self.bom_filter_combo = QtWidgets.QComboBox()
        self.bom_filter_combo.setStyleSheet(COMBO_STYLE)
        self.bom_filter_combo.setMinimumWidth(180)
        self.bom_filter_combo.currentIndexChanged.connect(self._refresh_bom)
        fr.addWidget(self.bom_filter_combo)
        fr.addStretch()
        v.addLayout(fr)

        self.bom_table = QtWidgets.QTableWidget()
        self.bom_table.setColumnCount(6)
        self.bom_table.setHorizontalHeaderLabels(
            ["Finished Good", "Component", "Qty Required", "Unit",
             "Scrap %", "Notes"]
        )
        hh = self.bom_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5):
            hh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.bom_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bom_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.bom_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.bom_table.setAlternatingRowColors(True)
        self.bom_table.verticalHeader().setVisible(False)
        v.addWidget(self.bom_table, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add BOM Item",     self._on_add_bom),
            ("Delete Selected",  self._on_delete_bom),
            ("Item Settings…",   self._on_item_settings),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Bill of Materials")

    def _load_bom_filter(self):
        conn = get_db()
        try:
            prods = conn.execute(
                "SELECT DISTINCT b.product_id, p.name AS product_name FROM "
                "bom b"
                " JOIN product p ON p.id = b.product_id ORDER BY p.name"
            ).fetchall()
        except psycopg2.OperationalError:
            prods = []
        conn.close()
        saved = self.bom_filter_combo.currentData()
        self.bom_filter_combo.blockSignals(True)
        self.bom_filter_combo.clear()
        self.bom_filter_combo.addItem("(all)", None)
        for p in prods:
            self.bom_filter_combo.addItem(p["product_name"], p["product_id"])
        if saved is not None:
            idx = self.bom_filter_combo.findData(saved)
            if idx >= 0:
                self.bom_filter_combo.setCurrentIndex(idx)
        self.bom_filter_combo.blockSignals(False)

    def _refresh_bom(self):
        self._load_bom_filter()
        prod_id = self.bom_filter_combo.currentData()
        conn = get_db()
        try:
            base = """
                SELECT b.id, fg.name AS fg_name, c.name AS comp_name,
                       b.qty_required, b.unit,
                       COALESCE(b.scrap_pct, 0.0) AS scrap_pct, b.notes
                FROM bom b
                JOIN product fg ON fg.id = b.product_id
                JOIN product c  ON c.id  = b.component_id
            """
            if prod_id:
                rows = conn.execute(base + " WHERE b.product_id = ? ORDER BY fg.name, c.name",  # noqa: E501
                                    (prod_id,)).fetchall()
            else:
                rows = conn.execute(
    base + " ORDER BY fg.name, c.name").fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.bom_table.setRowCount(0)
        self._bom_row_ids = []
        for row in rows:
            r = self.bom_table.rowCount()
            self.bom_table.insertRow(r)
            self._bom_row_ids.append(row["id"])
            self.bom_table.setItem(r, 0, _ro(row["fg_name"]))
            self.bom_table.setItem(r, 1, _ro(row["comp_name"]))
            self.bom_table.setItem(r, 2, _ro(f"{row['qty_required']:.3f}"))
            self.bom_table.setItem(r, 3, _ro(row["unit"] or ""))
            self.bom_table.setItem(r, 4, _ro(f"{row['scrap_pct']:g}"))
            self.bom_table.setItem(r, 5, _ro(row["notes"] or ""))
        self._selected_bom_id = None

    def _on_add_bom(self):
        dlg = AddBOMItemDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_bom()

    def _on_item_settings(self):
        ItemSettingsDialog(self).exec()

    def _on_delete_bom(self):
        rows = self.bom_table.selectedItems()
        if not rows:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a BOM row first.")
            return
        row = self.bom_table.currentRow()
        if row < 0 or row >= len(self._bom_row_ids):
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete", "Delete this BOM item?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM bom WHERE id = ?",
                         (self._bom_row_ids[row],))
            conn.commit()
            conn.close()
            self._refresh_bom()


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = WorkOrders()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
