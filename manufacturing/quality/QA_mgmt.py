"""
QA_mgmt.py — Quality Assurance Manager feature screens
Widgets: NCRWidget | CAPAWidget | AuditsWidget | SupplierQualityWidget

Each widget is a self-contained, DB-backed register (filter bar + table +
Add/Edit/Delete + a status action) built on the shared _QACrudWidget base.
Schema is created and seeded on first use via init_db().
"""
import sys
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets
from ..button_nav import ButtonNav
from ..db_pg import get_db
from ..accounts import get_current_user_email


def _conn():
    return get_db()


# ═════════════════════════════════════════════════════════════════════════════
# Schema
# ═════════════════════════════════════════════════════════════════════════════
def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS qa_ncr (
            id            SERIAL PRIMARY KEY,
            title         TEXT    NOT NULL,
            source        TEXT    DEFAULT '',
            severity      TEXT    DEFAULT '',
            product       TEXT    DEFAULT '',
            detected_date TEXT    DEFAULT '',
            disposition   TEXT    DEFAULT 'Pending',
            owner         TEXT    DEFAULT '',
            closed_date   TEXT    DEFAULT '',
            status        TEXT    DEFAULT 'Open',
            notes         TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS qa_capa (
            id             SERIAL PRIMARY KEY,
            title          TEXT    NOT NULL,
            capa_type      TEXT    DEFAULT '',
            ncr_ref        TEXT    DEFAULT '',
            owner          TEXT    DEFAULT '',
            due_date       TEXT    DEFAULT '',
            completed_date TEXT    DEFAULT '',
            status         TEXT    DEFAULT 'Open',
            action_plan    TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS qa_audit (
            id             SERIAL PRIMARY KEY,
            title          TEXT    NOT NULL,
            audit_type     TEXT    DEFAULT '',
            auditor        TEXT    DEFAULT '',
            scheduled_date TEXT    DEFAULT '',
            completed_date TEXT    DEFAULT '',
            result         TEXT    DEFAULT '',
            status         TEXT    DEFAULT 'Scheduled',
            findings       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS qa_supplier (
            id        SERIAL PRIMARY KEY,
            supplier  TEXT    NOT NULL,
            material  TEXT    DEFAULT '',
            rating    TEXT    DEFAULT '',
            ppm       TEXT    DEFAULT '',
            last_audit TEXT   DEFAULT '',
            status    TEXT    DEFAULT 'Pending',
            notes     TEXT    DEFAULT ''
        );
        """)
        _seed(con)
    try:
        with _conn() as con:
            for tbl in ("qa_ncr", "qa_capa", "qa_audit", "qa_supplier"):
                con.execute(
                    f"ALTER TABLE {tbl}"
                    " ADD COLUMN IF NOT EXISTS created_by TEXT")
    except Exception:
        pass


def _seed(con):
    today = date.today().isoformat()
    if con.execute("SELECT COUNT(*) FROM qa_ncr").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO qa_ncr (title,source,severity,product,detected_date,disposition,owner,status) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Surface finish out of spec", "In-Process", "Major", "Widget A",
             today, "Rework", "QA Inspector", "Open"))
    if con.execute("SELECT COUNT(*) FROM qa_capa").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO qa_capa "
            "(title,capa_type,ncr_ref,owner,due_date,status) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("Recalibrate grinding machine", "Corrective", "NCR-1", "QA "
                                                                    "Manager",
             "2026-06-20", "In Progress"))
    if con.execute("SELECT COUNT(*) FROM qa_audit").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO qa_audit "
            "(title,audit_type,auditor,scheduled_date,status) "
            "VALUES (%s,%s,%s,%s,%s)",
            ("ISO 9001 surveillance audit", "External", "SGS", "2026-07-15", "Scheduled"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM qa_supplier").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO qa_supplier "
            "(supplier,material,rating,ppm,last_audit,status) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("Acme Supplies Inc.", "Steel stock", "B", "350", "2026-03-01", "Approved"))  # noqa: E501


# ═════════════════════════════════════════════════════════════════════════════
# Shared styling helpers
# ═════════════════════════════════════════════════════════════════════════════
BTN_STYLE = (
    "QPushButton{background-color:white;border:2px solid "
    "black;border-radius:8px;"
    "padding:4px 10px;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid #aaa;background:white;}"
    "QTabBar::tab{background:#cce0ff;padding:6px 14px;font-weight:bold;}"
    "QTabBar::tab:selected{background:white;border-bottom:2px solid "
    "rgb(0,85,255);}"
)

# Row tint keyed by common status words shared across the QA registers.
STATUS_COLORS = {
    "Open": QtGui.QColor(255, 230, 205),
    "Pending": QtGui.QColor(255, 255, 200),
    "Under Review": QtGui.QColor(255, 255, 200),
    "In Progress": QtGui.QColor(255, 255, 200),
    "Verification": QtGui.QColor(255, 255, 200),
    "Scheduled": QtGui.QColor(255, 255, 200),
    "Follow-up": QtGui.QColor(255, 255, 200),
    "Conditional": QtGui.QColor(255, 255, 200),
    "Probation": QtGui.QColor(255, 200, 180),
    "Overdue": QtGui.QColor(255, 190, 190),
    "Disqualified": QtGui.QColor(255, 190, 190),
    "Dispositioned": QtGui.QColor(200, 255, 210),
    "Complete": QtGui.QColor(200, 255, 210),
    "Completed": QtGui.QColor(200, 255, 210),
    "Closed": QtGui.QColor(200, 255, 210),
    "Approved": QtGui.QColor(200, 255, 210),
}


def _apply_blue_palette(widget):
    pal = QtGui.QPalette()
    blue = QtGui.QColor(0, 85, 255)
    pal.setColor(QtGui.QPalette.ColorRole.Window, blue)
    pal.setColor(QtGui.QPalette.ColorRole.Button, blue)
    pal.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(255, 255, 255))
    pal.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(0, 0, 0))
    pal.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(0, 0, 0))
    widget.setPalette(pal)


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft):
    item = QtWidgets.QTableWidgetItem(str(text) if text is not None else "")
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable |
                  QtCore.Qt.ItemFlag.ItemIsEnabled)
    item.setTextAlignment(align | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return item


def _color_row(table, row, color):
    if color:
        for c in range(table.columnCount()):
            it = table.item(row, c)
            if it:
                it.setBackground(color)


# ═════════════════════════════════════════════════════════════════════════════
# Generic record dialog — built from a list of field specs
# ═════════════════════════════════════════════════════════════════════════════
class _RecordDialog(QtWidgets.QDialog):
    """A form dialog generated from field specs.

    Each spec is a dict: {'key', 'label', 'kind', optional 'options'}.
    kind is one of: text, memo, combo, date.
    """

    def __init__(self, title, fields, parent=None, row_data=None, created_by=None):  # noqa: E501
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self._fields = fields
        self._widgets = {}

        v = QtWidgets.QVBoxLayout(self)
        fl = QtWidgets.QFormLayout()
        for f in fields:
            w = self._make_widget(f)
            self._widgets[f["key"]] = w
            fl.addRow(f["label"] + ":", w)
            if row_data is not None:
                self._set_value(f, w, row_data[f["key"]])
        if created_by is not None:
            fl.addRow(
                "Created by:", QtWidgets.QLabel(created_by or "(unknown)")
            )
        v.addLayout(fl)

        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |  # noqa: E501
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)  # noqa: E501
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _make_widget(self, f):
        kind = f["kind"]
        if kind == "text":
            return QtWidgets.QLineEdit()
        if kind == "memo":
            w = QtWidgets.QTextEdit()
            w.setMaximumHeight(80)
            return w
        if kind == "combo":
            w = QtWidgets.QComboBox()
            w.addItems(f["options"])
            w.setEditable(f.get("editable", False))
            return w
        if kind == "date":
            w = QtWidgets.QDateEdit(calendarPopup=True)
            w.setDisplayFormat("yyyy-MM-dd")
            w.setDate(QtCore.QDate.currentDate())
            return w
        raise ValueError(f"unknown field kind: {kind}")

    def _set_value(self, f, w, val):
        kind = f["kind"]
        if kind == "text":
            w.setText(str(val or ""))
        elif kind == "memo":
            w.setPlainText(str(val or ""))
        elif kind == "combo":
            w.setCurrentText(str(val or ""))
        elif kind == "date":
            if val:
                w.setDate(QtCore.QDate.fromString(str(val), "yyyy-MM-dd"))

    def values(self):
        out = {}
        for f in self._fields:
            w = self._widgets[f["key"]]
            kind = f["kind"]
            if kind == "text":
                out[f["key"]] = w.text().strip()
            elif kind == "memo":
                out[f["key"]] = w.toPlainText().strip()
            elif kind == "combo":
                out[f["key"]] = w.currentText().strip()
            elif kind == "date":
                out[f["key"]] = w.date().toString("yyyy-MM-dd")
        return out


# ═════════════════════════════════════════════════════════════════════════════
# Generic register widget — one DB table, configured per subclass via SPEC
# ═════════════════════════════════════════════════════════════════════════════
class _QACrudWidget(QtWidgets.QWidget):
    # Subclasses set SPEC = {
    #   'table', 'title', 'noun',
    #   'statuses': [...],
    #   'columns': [(field_key, header, width|None)],  # 'id' implied first
    #   'fields':  [ {key,label,kind,options?} ],       # dialog + insert/update  # noqa: E501
    #   'order_by': field_key,
    #   'action': {'label', 'status', 'stamp'(optional date field key)},
    # }
    SPEC: dict = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        init_db()
        _apply_blue_palette(self)
        self._build_ui()
        self._refresh()

    # ── UI ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        spec = self.SPEC
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        title = QtWidgets.QLabel(spec["title"])
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size:22px;font-weight:bold;color:white;padding:4px;")
        root.addWidget(title)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Status:"))
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItems(["All Statuses"] + spec["statuses"])
        self.status_filter.currentIndexChanged.connect(self._refresh)
        fb.addWidget(self.status_filter)
        fb.addWidget(QtWidgets.QLabel("Search:"))
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(f"Filter {spec['noun']}s…")
        self.search.textChanged.connect(self._refresh)
        fb.addWidget(self.search, 1)
        fb.addStretch()
        root.addWidget(self._wrap(fb))

        cols = ([("id", "ID", 40)] + spec["columns"]
                + [("created_by", "Created By", 160)])
        self._col_keys = [c[0] for c in cols]
        self.tbl = QtWidgets.QTableWidget(0, len(cols))
        self.tbl.setHorizontalHeaderLabels([c[1] for c in cols])
        for i, (_, _, width) in enumerate(cols):
            if width is None:
                self.tbl.horizontalHeader().setSectionResizeMode(
                    i, QtWidgets.QHeaderView.ResizeMode.Stretch)
            else:
                self.tbl.setColumnWidth(i, width)
        self.tbl.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setDefaultSectionSize(24)
        self.tbl.itemDoubleClicked.connect(self._edit)
        root.addWidget(self.tbl)

        bb = QtWidgets.QHBoxLayout()
        buttons = [(f"Add {spec['noun']}", self._add),
                   (f"Edit {spec['noun']}", self._edit),
                   (f"Delete {spec['noun']}", self._delete)]
        if spec.get("action"):
            buttons.append((spec["action"]["label"], self._do_action))
        for lbl, slot in buttons:
            btn = QtWidgets.QPushButton(lbl)
            btn.setStyleSheet(BTN_STYLE)
            btn.clicked.connect(slot)
            bb.addWidget(btn)
        bb.addStretch()
        root.addWidget(self._wrap(bb))

    def _wrap(self, layout):
        w = QtWidgets.QWidget()
        w.setLayout(layout)
        return w

    # ── Data ────────────────────────────────────────────────────────────────
    def _refresh(self, *_):
        spec = self.SPEC
        sf = self.status_filter.currentText() if hasattr(
            self, "status_filter") else "All Statuses"
        term = self.search.text().strip().lower() if hasattr(self, "search") else ""  # noqa: E501
        with _conn() as con:
            q = f"SELECT * FROM {spec['table']} WHERE 1=1"
            p = []
            if sf != "All Statuses":
                q += " AND status=%s"
                p.append(sf)
            q += f" ORDER BY {spec['order_by']}"
            rows = con.execute(q, p).fetchall()

        self.tbl.setRowCount(0)
        for row in rows:
            if term and not self._matches(row, term):
                continue
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            for c, key in enumerate(self._col_keys):
                if key == "id":
                    self.tbl.setItem(
    r, c, _ro(
        row["id"], QtCore.Qt.AlignmentFlag.AlignRight))
                else:
                    self.tbl.setItem(r, c, _ro(row[key]))
            _color_row(self.tbl, r, STATUS_COLORS.get(row["status"]))

    def _matches(self, row, term):
        for key in self._col_keys:
            if key == "id":
                continue
            if term in str(row[key] or "").lower():
                return True
        return False

    def _selected_id(self):
        if not self.tbl.selectedItems():
            return None
        return int(self.tbl.item(self.tbl.currentRow(), 0).text())

    # ── CRUD ────────────────────────────────────────────────────────────────
    def _add(self, *_):
        spec = self.SPEC
        email = get_current_user_email()
        dlg = _RecordDialog(f"New {spec['noun']}", spec["fields"], self,
                            created_by=email)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        keys = [f["key"] for f in spec["fields"]]
        if not v[keys[0]]:
            QtWidgets.QMessageBox.warning(
    self, "Required", f"{
        spec['fields'][0]['label']} is required.")
            return
        cols = ",".join(keys) + ",created_by"
        ph = ",".join(["%s"] * len(keys)) + ",%s"
        with _conn() as con:
            con.execute(f"INSERT INTO {spec['table']} ({cols}) VALUES ({ph})",
                        [v[k] for k in keys] + [email or None])
        self._refresh()

    def _edit(self, *_):
        spec = self.SPEC
        rid = self._selected_id()
        if rid is None:
            return
        with _conn() as con:
            rd = con.execute(
                f"SELECT * FROM {spec['table']} WHERE id=%s", (rid,)).fetchone()  # noqa: E501
        if not rd:
            return
        dlg = _RecordDialog(
    f"Edit {
        spec['noun']}",
        spec["fields"],
        self,
         row_data=rd)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        keys = [f["key"] for f in spec["fields"]]
        assigns = ",".join(f"{k}=%s" for k in keys)
        with _conn() as con:
            con.execute(f"UPDATE {spec['table']} SET {assigns} WHERE id=%s",
                        [v[k] for k in keys] + [rid])
        self._refresh()

    def _delete(self, *_):
        spec = self.SPEC
        rid = self._selected_id()
        if rid is None:
            return
        if QtWidgets.QMessageBox.question(
                self, "Delete", f"Delete this {spec['noun'].lower()}?") == \
                QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute(f"DELETE FROM {spec['table']} WHERE id=%s", (rid,))
            self._refresh()

    def _do_action(self, *_):
        spec = self.SPEC
        action = spec["action"]
        rid = self._selected_id()
        if rid is None:
            return
        sets = "status=%s"
        params = [action["status"]]
        if action.get("stamp"):
            sets += f", {action['stamp']}=%s"
            params.append(date.today().isoformat())
        params.append(rid)
        with _conn() as con:
            con.execute(
    f"UPDATE {
        spec['table']} SET {sets} WHERE id=%s",
         params)
        self._refresh()


# ═════════════════════════════════════════════════════════════════════════════
# Vocabularies
# ═════════════════════════════════════════════════════════════════════════════
NCR_SOURCES = [
    "Incoming",
    "In-Process",
    "Final",
    "Customer",
    "Supplier",
     "Audit"]
NCR_SEVERITIES = ["Minor", "Major", "Critical"]
NCR_DISPOSITIONS = [
    "Pending",
    "Use As-Is",
    "Rework",
    "Repair",
    "Scrap",
     "Return"]
NCR_STATUSES = ["Open", "Under Review", "Dispositioned", "Closed"]

CAPA_TYPES = ["Corrective", "Preventive"]
CAPA_STATUSES = ["Open", "In Progress", "Verification", "Closed", "Overdue"]

AUDIT_TYPES = [
    "Internal",
    "External",
    "Supplier",
    "Process",
    "Product",
     "ISO 9001"]
AUDIT_STATUSES = [
    "Scheduled",
    "In Progress",
    "Complete",
    "Follow-up",
     "Closed"]

SUPPLIER_RATINGS = ["A", "B", "C", "D"]
SUPPLIER_STATUSES = [
    "Pending",
    "Approved",
    "Conditional",
    "Probation",
     "Disqualified"]


# ═════════════════════════════════════════════════════════════════════════════
# Concrete register widgets
# ═════════════════════════════════════════════════════════════════════════════
class NCRWidget(_QACrudWidget):
    SPEC = {
        "table": "qa_ncr",
        "title": "Non-Conformance Reports",
        "noun": "NCR",
        "statuses": NCR_STATUSES,
        "order_by": "detected_date DESC",
        "action": {"label": "Close NCR", "status": "Closed", "stamp": "closed_date"},  # noqa: E501
        "columns": [
            ("title", "Title", None),
            ("source", "Source", 120),
            ("severity", "Severity", 100),
            ("product", "Product", 140),
            ("disposition", "Disposition", 120),
            ("detected_date", "Detected", 95),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "title", "label": "Title", "kind": "text"},
            {"key": "source", "label": "Source",
                "kind": "combo", "options": NCR_SOURCES},
            {"key": "severity", "label": "Severity",
                "kind": "combo", "options": NCR_SEVERITIES},
            {"key": "product", "label": "Product", "kind": "text"},
            {"key": "detected_date", "label": "Detected Date", "kind": "date"},
            {"key": "disposition", "label": "Disposition",
                "kind": "combo", "options": NCR_DISPOSITIONS},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "status", "label": "Status",
                "kind": "combo", "options": NCR_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class CAPAWidget(_QACrudWidget):
    SPEC = {
        "table": "qa_capa",
        "title": "Corrective & Preventive Actions",
        "noun": "CAPA",
        "statuses": CAPA_STATUSES,
        "order_by": "due_date",
        "action": {"label": "Close CAPA", "status": "Closed", "stamp": "completed_date"},  # noqa: E501
        "columns": [
            ("title", "Title", None),
            ("capa_type", "Type", 120),
            ("ncr_ref", "NCR Ref", 100),
            ("owner", "Owner", 140),
            ("due_date", "Due", 95),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "title", "label": "Title", "kind": "text"},
            {"key": "capa_type", "label": "Type",
                "kind": "combo", "options": CAPA_TYPES},
            {"key": "ncr_ref", "label": "NCR Ref", "kind": "text"},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "due_date", "label": "Due Date", "kind": "date"},
            {"key": "completed_date", "label": "Completed Date", "kind": "date"},  # noqa: E501
            {"key": "status", "label": "Status",
                "kind": "combo", "options": CAPA_STATUSES},
            {"key": "action_plan", "label": "Action Plan", "kind": "memo"},
        ],
    }


class AuditsWidget(_QACrudWidget):
    SPEC = {
        "table": "qa_audit",
        "title": "Quality Audits",
        "noun": "Audit",
        "statuses": AUDIT_STATUSES,
        "order_by": "scheduled_date",
        "action": {"label": "Mark Complete", "status": "Complete", "stamp": "completed_date"},  # noqa: E501
        "columns": [
            ("title", "Audit", None),
            ("audit_type", "Type", 130),
            ("auditor", "Auditor", 150),
            ("scheduled_date", "Scheduled", 100),
            ("completed_date", "Completed", 100),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "title", "label": "Audit", "kind": "text"},
            {"key": "audit_type", "label": "Type", "kind": "combo",
                "options": AUDIT_TYPES, "editable": True},
            {"key": "auditor", "label": "Auditor", "kind": "text"},
            {"key": "scheduled_date", "label": "Scheduled Date", "kind": "date"},  # noqa: E501
            {"key": "completed_date", "label": "Completed Date", "kind": "date"},  # noqa: E501
            {"key": "result", "label": "Result", "kind": "text"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": AUDIT_STATUSES},
            {"key": "findings", "label": "Findings", "kind": "memo"},
        ],
    }


class SupplierQualityWidget(_QACrudWidget):
    SPEC = {
        "table": "qa_supplier",
        "title": "Supplier Quality",
        "noun": "Supplier",
        "statuses": SUPPLIER_STATUSES,
        "order_by": "supplier",
        "action": {"label": "Mark Approved", "status": "Approved"},
        "columns": [
            ("supplier", "Supplier", None),
            ("material", "Material", 160),
            ("rating", "Rating", 80),
            ("ppm", "PPM", 90),
            ("last_audit", "Last Audit", 100),
            ("status", "Status", 120),
        ],
        "fields": [
            {"key": "supplier", "label": "Supplier", "kind": "text"},
            {"key": "material", "label": "Material", "kind": "text"},
            {"key": "rating",
    "label": "Rating",
    "kind": "combo",
     "options": SUPPLIER_RATINGS},
            {"key": "ppm", "label": "PPM (defect rate)", "kind": "text"},
            {"key": "last_audit", "label": "Last Audit", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": SUPPLIER_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Standalone window (for `python -m manufacturing.QA_mgmt`)
# ═════════════════════════════════════════════════════════════════════════════
class QAMgmtWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = f"QA Management — {email}" if email else "QA Management"
        self.setWindowTitle(title)
        self.resize(1150, 740)
        _apply_blue_palette(self)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(NCRWidget(), "Non-Conformance")
        tabs.addTab(CAPAWidget(), "Corrective Actions")
        tabs.addTab(AuditsWidget(), "Quality Audits")
        tabs.addTab(SupplierQualityWidget(), "Supplier Quality")
        self.setCentralWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = QAMgmtWindow()
    w.show()
    sys.exit(app.exec())
