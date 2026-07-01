import sys
import psycopg2
from ..db_pg import get_db
from ..accounts import get_current_user_email
from PyQt6 import QtCore, QtGui, QtWidgets
from ..qt_theme import (
    BUTTON_STYLE,
    INPUT_STYLE,
    COMBO_STYLE,
    LABEL_STYLE,
    apply_blue_palette as _apply_blue_palette,
    ro as _ro,
)

from ..button_nav import ButtonNav

INSP_COLORS = {
    "pending": "#ffffff",
    "passed":  "#d4edda",
    "failed":  "#f8d7da",
    "on_hold": "#fff3cd",
}

SEVERITY_COLORS = {
    "critical": QtGui.QColor(248, 215, 218),
    "major":    QtGui.QColor(255, 243, 205),
    "minor":    QtGui.QColor(220, 235, 255),
}


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_inspection (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            insp_number   TEXT NOT NULL UNIQUE,
            product_id    INTEGER,
            wo_id         INTEGER,
            insp_date     TEXT,
            inspector     TEXT,
            result        TEXT DEFAULT 'pending',
            notes         TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_defect (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            insp_id      INTEGER NOT NULL REFERENCES qa_inspection(id),
            defect_type  TEXT,
            severity     TEXT DEFAULT 'minor',
            description  TEXT,
            resolved     INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qa_spec (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            spec_name  TEXT NOT NULL,
            min_value  REAL,
            max_value  REAL,
            unit       TEXT,
            notes      TEXT
        )
    """)
    conn.commit()
    conn.close()
    try:
        conn = get_db()
        conn.execute(
            "ALTER TABLE qa_inspection"
            " ADD COLUMN IF NOT EXISTS created_by TEXT")
        conn.execute(
            "ALTER TABLE qa_defect"
            " ADD COLUMN IF NOT EXISTS created_by TEXT")
        conn.execute(
            "ALTER TABLE qa_spec"
            " ADD COLUMN IF NOT EXISTS created_by TEXT")
        conn.commit()
        conn.close()
    except Exception:
        pass


def _next_insp_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM qa_inspection WHERE insp_number LIKE ?", (
            f"QA-{yr}-%",)
    ).fetchone()[0]
    conn.close()
    return f"QA-{yr}-{count + 1:04d}"


def _load_products(combo, include_none=True):
    conn = get_db()
    try:
        prods = conn.execute(
            "SELECT id, name AS product_name FROM product ORDER BY name").fetchall()  # noqa: E501
    except psycopg2.OperationalError:
        prods = []
    conn.close()
    combo.clear()
    if include_none:
        combo.addItem("(none)", None)
    for p in prods:
        combo.addItem(p["product_name"], p["id"])


# ── Dialogs ─────────────────────────────────────────────────────────────

class NewInspectionDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Inspection")
        self.resize(480, 300)
        _apply_blue_palette(self)
        self.insp_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.insp_num = QtWidgets.QLineEdit(_next_insp_num())
        self.insp_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Inspection #:"), self.insp_num)

        self.product_combo = QtWidgets.QComboBox()
        self.product_combo.setStyleSheet(COMBO_STYLE)
        _load_products(self.product_combo, include_none=True)
        layout.addRow(lbl("Product:"), self.product_combo)

        self.wo_combo = QtWidgets.QComboBox()
        self.wo_combo.setStyleSheet(COMBO_STYLE)
        conn = get_db()
        try:
            wos = conn.execute(
                "SELECT id, wo_number FROM work_order ORDER BY wo_number DESC "
                "LIMIT 100"
            ).fetchall()
        except psycopg2.OperationalError:
            wos = []
        conn.close()
        self.wo_combo.addItem("(none)", None)
        for w in wos:
            self.wo_combo.addItem(w["wo_number"], w["id"])
        layout.addRow(lbl("Work Order:"), self.wo_combo)

        self.insp_date = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.insp_date.setCalendarPopup(True)
        self.insp_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Inspection Date:"), self.insp_date)

        self.inspector = QtWidgets.QLineEdit()
        self.inspector.setStyleSheet(INPUT_STYLE)
        self.inspector.setPlaceholderText("Inspector name")
        layout.addRow(lbl("Inspector:"), self.inspector)

        self.result_combo = QtWidgets.QComboBox()
        self.result_combo.setStyleSheet(COMBO_STYLE)
        for s in ("pending", "passed", "failed", "on_hold"):
            self.result_combo.addItem(s.replace("_", " ").capitalize(), s)
        layout.addRow(lbl("Result:"), self.result_combo)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Notes:"), self.notes)

        created_by_lbl = QtWidgets.QLabel(get_current_user_email() or "(unknown)")  # noqa: E501
        created_by_lbl.setStyleSheet(LABEL_STYLE)
        layout.addRow(lbl("Created by:"), created_by_lbl)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        num = self.insp_num.text().strip()
        if not num:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Inspection number is required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO qa_inspection (insp_number, product_id, wo_id, "
                "insp_date,"
                " inspector, result, notes, created_by)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (num, self.product_combo.currentData(), self.wo_combo.currentData(),  # noqa: E501
                 self.insp_date.date().toString("yyyy-MM-dd"),
                 self.inspector.text().strip(), self.result_combo.currentData(),  # noqa: E501
                 self.notes.text().strip(),
                 get_current_user_email() or None)
            )
            self.insp_id = cur.lastrowid
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"Inspection number '{num}' already exists.")  # noqa: E501
            conn.close()
            return
        conn.close()
        self.accept()


class LogDefectDialog(QtWidgets.QDialog):
    def __init__(self, insp_id, insp_number, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Log Defect — {insp_number}")
        self.resize(440, 240)
        _apply_blue_palette(self)
        self._insp_id = insp_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.defect_type = QtWidgets.QLineEdit()
        self.defect_type.setStyleSheet(INPUT_STYLE)
        self.defect_type.setPlaceholderText(
            "e.g. Dimensional, Surface, Contamination")
        layout.addRow(lbl("Defect Type:"), self.defect_type)

        self.severity_combo = QtWidgets.QComboBox()
        self.severity_combo.setStyleSheet(COMBO_STYLE)
        for s in ("minor", "major", "critical"):
            self.severity_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Severity:"), self.severity_combo)

        self.description = QtWidgets.QLineEdit()
        self.description.setStyleSheet(INPUT_STYLE)
        self.description.setPlaceholderText("Describe the defect (required)")
        layout.addRow(lbl("Description:"), self.description)

        created_by_lbl = QtWidgets.QLabel(get_current_user_email() or "(unknown)")  # noqa: E501
        created_by_lbl.setStyleSheet(LABEL_STYLE)
        layout.addRow(lbl("Created by:"), created_by_lbl)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        desc = self.description.text().strip()
        if not desc:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Description is required.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO qa_defect (insp_id, defect_type, severity, "
            "description, created_by) VALUES (?,?,?,?,?)",
            (self._insp_id, self.defect_type.text().strip(),
             self.severity_combo.currentData(), desc,
             get_current_user_email() or None)
        )
        conn.commit()
        conn.close()
        self.accept()


class AddSpecDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Product Specification")
        self.resize(440, 260)
        _apply_blue_palette(self)
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
        layout.addRow(lbl("Product:"), self.product_combo)

        self.spec_name = QtWidgets.QLineEdit()
        self.spec_name.setStyleSheet(INPUT_STYLE)
        self.spec_name.setPlaceholderText("e.g. Weight, pH, Particle Size")
        layout.addRow(lbl("Spec Name:"), self.spec_name)

        self.min_val = QtWidgets.QDoubleSpinBox()
        self.min_val.setRange(-999999.0, 999999.0)
        self.min_val.setDecimals(4)
        self.min_val.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Min Value:"), self.min_val)

        self.max_val = QtWidgets.QDoubleSpinBox()
        self.max_val.setRange(-999999.0, 999999.0)
        self.max_val.setDecimals(4)
        self.max_val.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Max Value:"), self.max_val)

        self.unit = QtWidgets.QLineEdit()
        self.unit.setStyleSheet(INPUT_STYLE)
        self.unit.setPlaceholderText("e.g. g, mg/L, µm")
        layout.addRow(lbl("Unit:"), self.unit)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Notes:"), self.notes)

        created_by_lbl = QtWidgets.QLabel(get_current_user_email() or "(unknown)")  # noqa: E501
        created_by_lbl.setStyleSheet(LABEL_STYLE)
        layout.addRow(lbl("Created by:"), created_by_lbl)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        prod_id = self.product_combo.currentData()
        name = self.spec_name.text().strip()
        if prod_id is None or not name:
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Product and spec name are required.")
            return
        if self.min_val.value() > self.max_val.value():
            QtWidgets.QMessageBox.warning(
    self, "Input Error", "Min value must be ≤ max value.")
            return
        conn = get_db()
        conn.execute(
            "INSERT INTO qa_spec (product_id, spec_name, min_value, "
            "max_value, unit, notes, created_by)"
            " VALUES (?,?,?,?,?,?,?)",
            (prod_id, name, self.min_val.value(), self.max_val.value(),
             self.unit.text().strip(), self.notes.text().strip(),
             get_current_user_email() or None)
        )
        conn.commit()
        conn.close()
        self.accept()


# ── Main Window ─────────────────────────────────────────────────────────

class QALab(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = f"QA Laboratory — {email}" if email else "QA Laboratory"
        self.setWindowTitle(title)
        _apply_blue_palette(self)
        self._insp_row_ids = []
        self._selected_insp_id = None
        self._selected_insp_number = None
        self._defect_row_ids = []
        self._spec_row_ids = []
        self._build_ui()
        init_db()
        self._refresh_inspections()
        self._refresh_defects()
        self._refresh_specs()

    def _build_ui(self):
        self._tabs = ButtonNav()
        self._tabs.setStyleSheet(
            "QTabBar::tab{background:white; border:1px solid black; "
            "padding:4px 10px;}"
            "QTabBar::tab:selected{background:rgb(85,255,255);}"
        )
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)
        self._build_inspections_tab()
        self._build_defects_tab()
        self._build_specs_tab()

    def _on_tab_changed(self, index):
        if index == 0:
            self._refresh_inspections()
        elif index == 1:
            self._refresh_defects()
        elif index == 2:
            self._refresh_specs()

    # ── Inspections tab ─────────────────────────────────────────────────────

    def _build_inspections_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_r = QtWidgets.QLabel("Result:")
        lbl_r.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_r)
        self.insp_result_filter = QtWidgets.QComboBox()
        self.insp_result_filter.setStyleSheet(COMBO_STYLE)
        self.insp_result_filter.addItem("(all)", None)
        for s in ("pending", "passed", "failed", "on_hold"):
            self.insp_result_filter.addItem(
                s.replace("_", " ").capitalize(), s)
        self.insp_result_filter.currentIndexChanged.connect(
            self._refresh_inspections)
        fr.addWidget(self.insp_result_filter)

        fr.addSpacing(10)
        lbl_p = QtWidgets.QLabel("Product:")
        lbl_p.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_p)
        self.insp_prod_filter = QtWidgets.QComboBox()
        self.insp_prod_filter.setStyleSheet(COMBO_STYLE)
        self.insp_prod_filter.setMinimumWidth(150)
        self.insp_prod_filter.currentIndexChanged.connect(
            self._refresh_inspections)
        fr.addWidget(self.insp_prod_filter)

        fr.addSpacing(10)
        lbl_s = QtWidgets.QLabel("Search:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.insp_search = QtWidgets.QLineEdit()
        self.insp_search.setStyleSheet(INPUT_STYLE)
        self.insp_search.setFixedWidth(160)
        self.insp_search.returnPressed.connect(self._refresh_inspections)
        fr.addWidget(self.insp_search)
        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_insp_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.insp_table = QtWidgets.QTableWidget()
        self.insp_table.setColumnCount(8)
        self.insp_table.setHorizontalHeaderLabels(
            ["Insp #", "Product", "Work Order", "Date",
             "Inspector", "Defects", "Result", "Created By"]
        )
        hh = self.insp_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6, 7):
            hh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.insp_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.insp_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.insp_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.insp_table.setAlternatingRowColors(True)
        self.insp_table.verticalHeader().setVisible(False)
        self.insp_table.clicked.connect(self._on_insp_clicked)
        splitter.addWidget(self.insp_table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Defects for Selected Inspection")
        dlbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self.defect_detail_table = QtWidgets.QTableWidget()
        self.defect_detail_table.setColumnCount(5)
        self.defect_detail_table.setHorizontalHeaderLabels(
            ["Defect Type", "Severity", "Description", "Resolved", "ID"]
        )
        dh = self.defect_detail_table.horizontalHeader()
        dh.setStyleSheet("color: black; font-weight: bold;")
        dh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (0, 1, 3, 4):
            dh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.defect_detail_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.defect_detail_table.verticalHeader().setVisible(False)
        self.defect_detail_table.setAlternatingRowColors(True)
        dv.addWidget(self.defect_detail_table)
        splitter.addWidget(detail_w)
        splitter.setSizes([380, 200])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Inspection",  self._on_new_insp),
            ("Log Defect",      self._on_log_defect),
            ("Mark Passed",     lambda: self._set_result(
                "passed",  "Mark as Passed?")),
            ("Mark Failed",     lambda: self._set_result(
                "failed",  "Mark as Failed?")),
            ("Mark On Hold",    lambda: self._set_result("on_hold", "Put On "
                                                                    "Hold?")),
            ("Resolve Defect",  self._on_resolve_defect),
            ("Print Inspection", self._on_print_inspection),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Inspections")

    def _load_insp_prod_filter(self):
        conn = get_db()
        try:
            prods = conn.execute("""
                SELECT DISTINCT qi.product_id, p.name AS product_name
                FROM qa_inspection qi JOIN product p ON p.id = qi.product_id
                ORDER BY p.name
            """).fetchall()
        except psycopg2.OperationalError:
            prods = []
        conn.close()
        saved = self.insp_prod_filter.currentData()
        self.insp_prod_filter.blockSignals(True)
        self.insp_prod_filter.clear()
        self.insp_prod_filter.addItem("(all)", None)
        for p in prods:
            self.insp_prod_filter.addItem(p["product_name"], p["product_id"])
        if saved is not None:
            idx = self.insp_prod_filter.findData(saved)
            if idx >= 0:
                self.insp_prod_filter.setCurrentIndex(idx)
        self.insp_prod_filter.blockSignals(False)

    def _refresh_inspections(self):
        self._load_insp_prod_filter()
        result = self.insp_result_filter.currentData()
        prod_id = self.insp_prod_filter.currentData()
        term = self.insp_search.text().strip()

        base = """
            SELECT qi.id, qi.insp_number, qi.insp_date, qi.inspector,
                qi.result, qi.created_by,
                   p.name AS product_name, wo.wo_number,
                   (SELECT COUNT(*) FROM qa_defect d WHERE d.insp_id = qi.id)
                       AS defect_count
            FROM qa_inspection qi
            LEFT JOIN product p  ON p.id  = qi.product_id
            LEFT JOIN work_order wo ON wo.id = qi.wo_id
        """
        conds, params = [], []
        if result:
            conds.append("qi.result = ?")
            params.append(result)
        if prod_id:
            conds.append("qi.product_id = ?")
            params.append(prod_id)
        if term:
            conds.append("(qi.insp_number LIKE ? OR qi.inspector LIKE ?)")
            params += [f"%{term}%", f"%{term}%"]
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        conn = get_db()
        try:
            rows = conn.execute(base + where + " ORDER BY qi.insp_date DESC, qi.insp_number DESC",  # noqa: E501
                                params).fetchall()
        except psycopg2.OperationalError:
            rows = conn.execute(
                "SELECT id, insp_number, insp_date, inspector, result,"
                " NULL AS product_name, NULL AS wo_number, 0 AS defect_count"
                " FROM qa_inspection" + where + " ORDER BY insp_date DESC",
                params
            ).fetchall()
        conn.close()

        self.insp_table.setRowCount(0)
        self._insp_row_ids = []
        for row in rows:
            r = self.insp_table.rowCount()
            self.insp_table.insertRow(r)
            self._insp_row_ids.append(row["id"])
            self.insp_table.setItem(r, 0, _ro(row["insp_number"]))
            self.insp_table.setItem(r, 1, _ro(row["product_name"] or ""))
            self.insp_table.setItem(r, 2, _ro(row["wo_number"] or ""))
            self.insp_table.setItem(r, 3, _ro(row["insp_date"] or ""))
            self.insp_table.setItem(r, 4, _ro(row["inspector"] or ""))
            self.insp_table.setItem(r, 5, _ro(str(row["defect_count"])))
            self.insp_table.setItem(
    r, 6, _ro(
        row["result"].replace(
            "_", " ").capitalize()))
            self.insp_table.setItem(r, 7, _ro(row["created_by"] or ""))
            bg = QtGui.QColor(INSP_COLORS.get(row["result"], "#ffffff"))
            for col in range(8):
                self.insp_table.item(r, col).setBackground(bg)

        self._selected_insp_id = None
        self._selected_insp_number = None
        self.defect_detail_table.setRowCount(0)

    def _on_insp_show_all(self):
        self.insp_search.clear()
        self.insp_result_filter.blockSignals(True)
        self.insp_result_filter.setCurrentIndex(0)
        self.insp_result_filter.blockSignals(False)
        self.insp_prod_filter.blockSignals(True)
        self.insp_prod_filter.setCurrentIndex(0)
        self.insp_prod_filter.blockSignals(False)
        self._refresh_inspections()

    def _on_insp_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._insp_row_ids):
            return
        self._selected_insp_id = self._insp_row_ids[row]
        self._selected_insp_number = self.insp_table.item(row, 0).text()
        self._refresh_defect_detail()

    def _refresh_defect_detail(self):
        self.defect_detail_table.setRowCount(0)
        self._defect_detail_ids = []
        if self._selected_insp_id is None:
            return
        conn = get_db()
        defects = conn.execute(
            "SELECT id, defect_type, severity, description, resolved FROM "
            "qa_defect WHERE insp_id = ?",
            (self._selected_insp_id,)
        ).fetchall()
        conn.close()
        for d in defects:
            r = self.defect_detail_table.rowCount()
            self.defect_detail_table.insertRow(r)
            self._defect_detail_ids = getattr(self, "_defect_detail_ids", [])
            self._defect_detail_ids.append(d["id"])
            self.defect_detail_table.setItem(r, 0, _ro(d["defect_type"] or ""))
            self.defect_detail_table.setItem(
                r, 1, _ro(d["severity"].capitalize()))
            self.defect_detail_table.setItem(r, 2, _ro(d["description"] or ""))
            self.defect_detail_table.setItem(
                r, 3, _ro("Yes" if d["resolved"] else "No"))
            self.defect_detail_table.setItem(r, 4, _ro(str(d["id"])))
            sev_color = SEVERITY_COLORS.get(d["severity"])
            if sev_color and not d["resolved"]:
                for col in range(5):
                    self.defect_detail_table.item(
                        r, col).setBackground(sev_color)

    def _on_new_insp(self):
        dlg = NewInspectionDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_inspections()

    def _on_log_defect(self):
        if self._selected_insp_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an inspection first.")
            return
        dlg = LogDefectDialog(
    self._selected_insp_id,
    self._selected_insp_number,
     self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_inspections()
            self._refresh_defect_detail()

    def _set_result(self, new_result, msg):
        if self._selected_insp_id is None:
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select an inspection first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE qa_inspection SET result = ? WHERE id = ?",
                         (new_result, self._selected_insp_id))
            conn.commit()
            conn.close()
            self._refresh_inspections()

    def _on_resolve_defect(self):
        row = self.defect_detail_table.currentRow()
        ids = getattr(self, "_defect_detail_ids", [])
        if row < 0 or row >= len(ids):
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a defect row first.")
            return
        conn = get_db()
        conn.execute(
    "UPDATE qa_defect SET resolved = 1 WHERE id = ?", (ids[row],))
        conn.commit()
        conn.close()
        self._refresh_defect_detail()
        self._refresh_inspections()

    # ── Defects tab ─────────────────────────────────────────────────────────

    def _build_defects_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Severity:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self.defect_sev_filter = QtWidgets.QComboBox()
        self.defect_sev_filter.setStyleSheet(COMBO_STYLE)
        self.defect_sev_filter.addItem("(all)", None)
        for s in ("minor", "major", "critical"):
            self.defect_sev_filter.addItem(s.capitalize(), s)
        self.defect_sev_filter.currentIndexChanged.connect(
            self._refresh_defects)
        fr.addWidget(self.defect_sev_filter)

        fr.addSpacing(10)
        lbl_r = QtWidgets.QLabel("Status:")
        lbl_r.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_r)
        self.defect_res_filter = QtWidgets.QComboBox()
        self.defect_res_filter.setStyleSheet(COMBO_STYLE)
        self.defect_res_filter.addItem("Open only", 0)
        self.defect_res_filter.addItem("Resolved only", 1)
        self.defect_res_filter.addItem("All", None)
        self.defect_res_filter.currentIndexChanged.connect(
            self._refresh_defects)
        fr.addWidget(self.defect_res_filter)
        fr.addStretch()
        v.addLayout(fr)

        self.defect_table = QtWidgets.QTableWidget()
        self.defect_table.setColumnCount(7)
        self.defect_table.setHorizontalHeaderLabels(
            ["Inspection #", "Product", "Defect Type",
             "Severity", "Description", "Resolved", "Created By"]
        )
        hh = self.defect_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (0, 1, 2, 3, 5, 6):
            hh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.defect_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.defect_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.defect_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.defect_table.setAlternatingRowColors(True)
        self.defect_table.verticalHeader().setVisible(False)
        v.addWidget(self.defect_table, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Resolve Selected", self._on_resolve_defect_tab),
            ("Print Defects",    self._on_print_defects),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Defects")

    def _refresh_defects(self):
        sev = self.defect_sev_filter.currentData()
        resolved = self.defect_res_filter.currentData()

        base = """
            SELECT d.id, d.defect_type, d.severity, d.description, d.resolved,
                   d.created_by, qi.insp_number, p.name AS product_name
            FROM qa_defect d
            JOIN qa_inspection qi ON qi.id = d.insp_id
            LEFT JOIN product p ON p.id = qi.product_id
        """
        conds, params = [], []
        if sev:
            conds.append("d.severity = ?")
            params.append(sev)
        if resolved is not None:
            conds.append("d.resolved = ?")
            params.append(resolved)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        conn = get_db()
        try:
            rows = conn.execute(
                base + where + " ORDER BY d.resolved ASC, d.severity DESC, "
                               "qi.insp_number",
                params
            ).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.defect_table.setRowCount(0)
        self._defect_row_ids = []
        for row in rows:
            r = self.defect_table.rowCount()
            self.defect_table.insertRow(r)
            self._defect_row_ids.append(row["id"])
            self.defect_table.setItem(r, 0, _ro(row["insp_number"]))
            self.defect_table.setItem(r, 1, _ro(row["product_name"] or ""))
            self.defect_table.setItem(r, 2, _ro(row["defect_type"] or ""))
            self.defect_table.setItem(r, 3, _ro(row["severity"].capitalize()))
            self.defect_table.setItem(r, 4, _ro(row["description"] or ""))
            self.defect_table.setItem(
                r, 5, _ro("Yes" if row["resolved"] else "No"))
            self.defect_table.setItem(r, 6, _ro(row["created_by"] or ""))
            if not row["resolved"]:
                sev_color = SEVERITY_COLORS.get(row["severity"])
                if sev_color:
                    for col in range(7):
                        self.defect_table.item(r, col).setBackground(sev_color)

    def _on_resolve_defect_tab(self):
        row = self.defect_table.currentRow()
        if row < 0 or row >= len(self._defect_row_ids):
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a defect first.")
            return
        conn = get_db()
        conn.execute("UPDATE qa_defect SET resolved = 1 WHERE id = ?",
                     (self._defect_row_ids[row],))
        conn.commit()
        conn.close()
        self._refresh_defects()

    # ── Specifications tab ──────────────────────────────────────────────────

    def _build_specs_tab(self):
        w = QtWidgets.QWidget()
        _apply_blue_palette(w)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_p = QtWidgets.QLabel("Filter by product:")
        lbl_p.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_p)
        self.spec_prod_filter = QtWidgets.QComboBox()
        self.spec_prod_filter.setStyleSheet(COMBO_STYLE)
        self.spec_prod_filter.setMinimumWidth(180)
        self.spec_prod_filter.currentIndexChanged.connect(self._refresh_specs)
        fr.addWidget(self.spec_prod_filter)
        fr.addStretch()
        v.addLayout(fr)

        self.spec_table = QtWidgets.QTableWidget()
        self.spec_table.setColumnCount(7)
        self.spec_table.setHorizontalHeaderLabels(
            ["Product", "Spec Name", "Min Value", "Max Value", "Unit", "Notes",
             "Created By"]
        )
        hh = self.spec_table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (0, 2, 3, 4, 5, 6):
            hh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.spec_table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.spec_table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.spec_table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.spec_table.setAlternatingRowColors(True)
        self.spec_table.verticalHeader().setVisible(False)
        v.addWidget(self.spec_table, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add Specification", self._on_add_spec),
            ("Delete Selected",   self._on_delete_spec),
            ("Print Specs",       self._on_print_specs),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)
        self._tabs.addTab(w, "Specifications")

    def _load_spec_prod_filter(self):
        conn = get_db()
        try:
            prods = conn.execute("""
                SELECT DISTINCT s.product_id, p.name AS product_name FROM
                    qa_spec s
                JOIN product p ON p.id = s.product_id ORDER BY p.name
            """).fetchall()
        except psycopg2.OperationalError:
            prods = []
        conn.close()
        saved = self.spec_prod_filter.currentData()
        self.spec_prod_filter.blockSignals(True)
        self.spec_prod_filter.clear()
        self.spec_prod_filter.addItem("(all)", None)
        for p in prods:
            self.spec_prod_filter.addItem(p["product_name"], p["product_id"])
        if saved is not None:
            idx = self.spec_prod_filter.findData(saved)
            if idx >= 0:
                self.spec_prod_filter.setCurrentIndex(idx)
        self.spec_prod_filter.blockSignals(False)

    def _refresh_specs(self):
        self._load_spec_prod_filter()
        prod_id = self.spec_prod_filter.currentData()
        conn = get_db()
        try:
            if prod_id:
                rows = conn.execute("""
                    SELECT s.id, p.name AS product_name, s.spec_name,
                        s.min_value, s.max_value, s.unit, s.notes, s.created_by
                    FROM qa_spec s JOIN product p ON p.id = s.product_id
                    WHERE s.product_id = ? ORDER BY p.name, s.spec_name
                """, (prod_id,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT s.id, p.name AS product_name, s.spec_name,
                        s.min_value, s.max_value, s.unit, s.notes, s.created_by
                    FROM qa_spec s JOIN product p ON p.id = s.product_id
                    ORDER BY p.name, s.spec_name
                """).fetchall()
        except psycopg2.OperationalError:
            rows = []
        conn.close()

        self.spec_table.setRowCount(0)
        self._spec_row_ids = []
        for row in rows:
            r = self.spec_table.rowCount()
            self.spec_table.insertRow(r)
            self._spec_row_ids.append(row["id"])
            self.spec_table.setItem(r, 0, _ro(row["product_name"]))
            self.spec_table.setItem(r, 1, _ro(row["spec_name"]))
            self.spec_table.setItem(
                r, 2, _ro(f"{row['min_value']:.4f}" if row["min_value"] is not None else ""))  # noqa: E501
            self.spec_table.setItem(
                r, 3, _ro(f"{row['max_value']:.4f}" if row["max_value"] is not None else ""))  # noqa: E501
            self.spec_table.setItem(r, 4, _ro(row["unit"] or ""))
            self.spec_table.setItem(r, 5, _ro(row["notes"] or ""))
            self.spec_table.setItem(r, 6, _ro(row["created_by"] or ""))

    def _on_add_spec(self):
        dlg = AddSpecDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh_specs()

    def _on_delete_spec(self):
        row = self.spec_table.currentRow()
        if row < 0 or row >= len(self._spec_row_ids):
            QtWidgets.QMessageBox.warning(
    self, "No Selection", "Select a spec first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete", "Delete this specification?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("DELETE FROM qa_spec WHERE id = ?",
                         (self._spec_row_ids[row],))
            conn.commit()
            conn.close()
            self._refresh_specs()

    def _on_print_inspection(self):
        if self._selected_insp_id is None:
            QtWidgets.QMessageBox.information(
                self, "Print", "Select an inspection first.")
            return
        from ..print_utils import print_document, doc_header, fields_table, data_table, wrap_html
        conn = get_db()
        try:
            insp = conn.execute("""
                SELECT qi.insp_number, qi.insp_date, qi.inspector, qi.result,
                       qi.notes, qi.created_by,
                       p.name AS product_name, wo.wo_number
                FROM qa_inspection qi
                LEFT JOIN product p ON p.id = qi.product_id
                LEFT JOIN work_order wo ON wo.id = qi.wo_id
                WHERE qi.id = %s
            """, (self._selected_insp_id,)).fetchone()
            defects = conn.execute("""
                SELECT defect_type, severity, description,
                       CASE WHEN resolved THEN 'Yes' ELSE 'No' END AS resolved
                FROM qa_defect WHERE insp_id = %s ORDER BY id
            """, (self._selected_insp_id,)).fetchall()
        except Exception:
            conn.close()
            return
        conn.close()
        if not insp:
            return
        fields = [
            ("Inspection #", insp["insp_number"]),
            ("Product",      insp.get("product_name") or ""),
            ("Work Order",   insp.get("wo_number") or ""),
            ("Date",         str(insp.get("insp_date") or "")),
            ("Inspector",    insp.get("inspector") or ""),
            ("Result",       (insp.get("result") or "").replace("_", " ").title()),
            ("Notes",        insp.get("notes") or ""),
            ("Created By",   insp.get("created_by") or ""),
        ]
        defect_rows = [
            [d["defect_type"] or "", (d["severity"] or "").capitalize(),
             d["description"] or "", d["resolved"]]
            for d in defects
        ]
        html = wrap_html(
            doc_header(f"QA Inspection — {insp['insp_number']}")
            + fields_table(fields)
            + "<p style='font-weight:bold;font-size:11pt;margin-bottom:6px;'>"
              "Defects</p>"
            + data_table(
                ["Defect Type", "Severity", "Description", "Resolved"],
                defect_rows or [["(no defects recorded)", "", "", ""]],
            )
        )
        print_document(html, f"Inspection {insp['insp_number']}", self)

    def _on_print_defects(self):
        from ..print_utils import print_document, doc_header, data_table, wrap_html
        t = self.defect_table
        rows = []
        for r in range(t.rowCount()):
            rows.append([
                t.item(r, 0).text() if t.item(r, 0) else "",
                t.item(r, 1).text() if t.item(r, 1) else "",
                t.item(r, 2).text() if t.item(r, 2) else "",
                t.item(r, 3).text() if t.item(r, 3) else "",
                t.item(r, 4).text() if t.item(r, 4) else "",
                t.item(r, 5).text() if t.item(r, 5) else "",
                t.item(r, 6).text() if t.item(r, 6) else "",
            ])
        html = wrap_html(
            doc_header("QA Defects Report")
            + data_table(
                ["Inspection #", "Product", "Defect Type",
                 "Severity", "Description", "Resolved", "Created By"],
                rows or [["(no defects)", "", "", "", "", "", ""]],
            )
        )
        print_document(html, "QA Defects Report", self)

    def _on_print_specs(self):
        from ..print_utils import print_document, doc_header, data_table, wrap_html
        t = self.spec_table
        rows = []
        for r in range(t.rowCount()):
            rows.append([
                t.item(r, 0).text() if t.item(r, 0) else "",
                t.item(r, 1).text() if t.item(r, 1) else "",
                t.item(r, 2).text() if t.item(r, 2) else "",
                t.item(r, 3).text() if t.item(r, 3) else "",
                t.item(r, 4).text() if t.item(r, 4) else "",
                t.item(r, 5).text() if t.item(r, 5) else "",
                t.item(r, 6).text() if t.item(r, 6) else "",
            ])
        html = wrap_html(
            doc_header("QA Specifications Report")
            + data_table(
                ["Product", "Spec Name", "Min Value", "Max Value",
                 "Unit", "Notes", "Created By"],
                rows or [["(no specifications)", "", "", "", "", "", ""]],
            )
        )
        print_document(html, "QA Specifications Report", self)


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = QALab()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
