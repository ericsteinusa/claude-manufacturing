"""
Risk_mgmt.py — Risk Management Department feature screens
Widgets: RiskAssessmentWidget | RiskRegisterWidget | InsuranceWidget |
         BusinessContinuityWidget | ComplianceAuditWidget | KRIWidget

Each widget is a self-contained, DB-backed register (filter bar + table +
Add/Edit/Delete + a status action) built on the shared _RiskCrudWidget base.
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
        CREATE TABLE IF NOT EXISTS risk_assessment (
            id            SERIAL PRIMARY KEY,
            title         TEXT    NOT NULL,
            category      TEXT    DEFAULT '',
            likelihood    TEXT    DEFAULT '',
            impact        TEXT    DEFAULT '',
            risk_level    TEXT    DEFAULT '',
            owner         TEXT    DEFAULT '',
            assessed_date TEXT    DEFAULT '',
            status        TEXT    DEFAULT 'Identified',
            notes         TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS risk_register (
            id          SERIAL PRIMARY KEY,
            risk        TEXT    NOT NULL,
            category    TEXT    DEFAULT '',
            severity    TEXT    DEFAULT '',
            response    TEXT    DEFAULT '',
            owner       TEXT    DEFAULT '',
            target_date TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'Open',
            mitigation  TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS risk_insurance (
            id         SERIAL PRIMARY KEY,
            policy     TEXT    NOT NULL,
            insurer    TEXT    DEFAULT '',
            policy_type TEXT   DEFAULT '',
            coverage   REAL    DEFAULT 0,
            premium    REAL    DEFAULT 0,
            start_date TEXT    DEFAULT '',
            end_date   TEXT    DEFAULT '',
            status     TEXT    DEFAULT 'Active',
            notes      TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS risk_continuity (
            id          SERIAL PRIMARY KEY,
            plan        TEXT    NOT NULL,
            scope       TEXT    DEFAULT '',
            criticality TEXT    DEFAULT '',
            owner       TEXT    DEFAULT '',
            last_tested TEXT    DEFAULT '',
            next_test   TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'Draft',
            notes       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS risk_audit (
            id             SERIAL PRIMARY KEY,
            audit          TEXT    NOT NULL,
            framework      TEXT    DEFAULT '',
            auditor        TEXT    DEFAULT '',
            scheduled_date TEXT    DEFAULT '',
            completed_date TEXT    DEFAULT '',
            finding        TEXT    DEFAULT '',
            status         TEXT    DEFAULT 'Scheduled',
            notes          TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS risk_kri (
            id            SERIAL PRIMARY KEY,
            indicator     TEXT    NOT NULL,
            category      TEXT    DEFAULT '',
            threshold     TEXT    DEFAULT '',
            current_value TEXT    DEFAULT '',
            owner         TEXT    DEFAULT '',
            measured_date TEXT    DEFAULT '',
            status        TEXT    DEFAULT 'Normal',
            notes         TEXT    DEFAULT ''
        );
        """)
        _seed(con)
        for tbl in ("risk_assessment", "risk_register", "risk_insurance",
                    "risk_continuity", "risk_audit", "risk_kri"):
            try:
                con.execute(
                    f"ALTER TABLE {tbl} "
                    "ADD COLUMN IF NOT EXISTS created_by TEXT")
            except Exception:
                pass


def _seed(con):
    today = date.today().isoformat()
    if con.execute("SELECT COUNT(*) FROM risk_assessment").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO risk_assessment (title,category,likelihood,impact,risk_level,owner,assessed_date,status) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Supply chain disruption", "Operational", "Possible", "Major", "High",  # noqa: E501
             "Risk Manager", today, "Assessed"))
    if con.execute("SELECT COUNT(*) FROM risk_register").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO risk_register (risk,category,severity,response,owner,target_date,status,mitigation) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Single-source supplier dependency", "Operational", "High", "Mitigate",  # noqa: E501
             "Procurement", "2026-09-30", "In Progress", "Qualify a secondary "
                                                         "supplier."))
    if con.execute("SELECT COUNT(*) FROM risk_insurance").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO risk_insurance (policy,insurer,policy_type,coverage,premium,start_date,end_date,status) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("General Liability 2026", "Atlas Mutual", "Liability", 5000000, 48000,  # noqa: E501
             today, "2027-05-31", "Active"))
    if con.execute("SELECT COUNT(*) FROM risk_continuity").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO risk_continuity "
            "(plan,scope,criticality,owner,last_tested,next_test,status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("Plant outage recovery", "Production Line A", "High", "Operations",  # noqa: E501
             "2026-01-15", "2026-07-15", "Active"))
    if con.execute("SELECT COUNT(*) FROM risk_audit").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO risk_audit "
            "(audit,framework,auditor,scheduled_date,status) "
            "VALUES (%s,%s,%s,%s,%s)",
            ("Annual enterprise risk audit", "ISO 31000", "Internal Audit", "2026-08-01", "Scheduled"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM risk_kri").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO risk_kri (indicator,category,threshold,current_value,owner,measured_date,status) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("Supplier on-time delivery", "Operational", "< 90%", "94%",
             "Procurement", today, "Normal"))


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

# Row tint keyed by common status words shared across the risk registers.
STATUS_COLORS = {
    "Identified": QtGui.QColor(255, 230, 205),
    "Open": QtGui.QColor(255, 230, 205),
    "Draft": QtGui.QColor(235, 235, 235),
    "Scheduled": QtGui.QColor(255, 255, 200),
    "Pending": QtGui.QColor(255, 255, 200),
    "Assessed": QtGui.QColor(255, 255, 200),
    "In Progress": QtGui.QColor(255, 255, 200),
    "Mitigating": QtGui.QColor(255, 255, 200),
    "Under Review": QtGui.QColor(255, 255, 200),
    "Follow-up": QtGui.QColor(255, 255, 200),
    "Watch": QtGui.QColor(255, 255, 200),
    "Warning": QtGui.QColor(255, 200, 180),
    "Needs Update": QtGui.QColor(255, 200, 180),
    "Overdue": QtGui.QColor(255, 190, 190),
    "Breach": QtGui.QColor(255, 190, 190),
    "Active": QtGui.QColor(200, 255, 210),
    "Mitigated": QtGui.QColor(200, 255, 210),
    "Monitored": QtGui.QColor(200, 255, 210),
    "Complete": QtGui.QColor(200, 255, 210),
    "Completed": QtGui.QColor(200, 255, 210),
    "Resolved": QtGui.QColor(200, 255, 210),
    "Renewed": QtGui.QColor(200, 255, 210),
    "Normal": QtGui.QColor(200, 255, 210),
    "Accepted": QtGui.QColor(210, 255, 230),
    "Closed": QtGui.QColor(220, 220, 220),
    "Expired": QtGui.QColor(220, 220, 220),
    "Cancelled": QtGui.QColor(220, 220, 220),
    "Retired": QtGui.QColor(220, 220, 220),
    "Archived": QtGui.QColor(220, 220, 220),
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


def _money(v):
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return ""


# ═════════════════════════════════════════════════════════════════════════════
# Generic record dialog — built from a list of field specs
# ═════════════════════════════════════════════════════════════════════════════
class _RecordDialog(QtWidgets.QDialog):
    """A form dialog generated from field specs.

    Each spec is a dict: {'key', 'label', 'kind', optional 'options'}.
    kind is one of: text, memo, combo, date, money.
    """

    def __init__(self, title, fields, parent=None, row_data=None):
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
        if kind == "money":
            w = QtWidgets.QDoubleSpinBox()
            w.setRange(0, 1_000_000_000)
            w.setDecimals(2)
            w.setPrefix("$ ")
            w.setGroupSeparatorShown(True)
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
        elif kind == "money":
            w.setValue(float(val or 0))

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
            elif kind == "money":
                out[f["key"]] = w.value()
        return out


# ═════════════════════════════════════════════════════════════════════════════
# Generic register widget — one DB table, configured per subclass via SPEC
# ═════════════════════════════════════════════════════════════════════════════
class _RiskCrudWidget(QtWidgets.QWidget):
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

        cols = [("id", "ID", 40)] + spec["columns"]
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
    def _money_keys(self):
        return {f["key"] for f in self.SPEC["fields"] if f["kind"] == "money"}

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

        money_keys = self._money_keys()
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
                elif key in money_keys:
                    self.tbl.setItem(
    r, c, _ro(
        _money(
            row[key]), QtCore.Qt.AlignmentFlag.AlignRight))
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
        dlg = _RecordDialog(f"New {spec['noun']}", spec["fields"], self)
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
            con.execute(
                f"INSERT INTO {spec['table']} ({cols}) VALUES ({ph})",
                [v[k] for k in keys] + [get_current_user_email() or None])
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
RISK_CATEGORIES = ["Operational", "Financial", "Strategic", "Compliance",
                   "Hazard", "Reputational", "Cyber", "Supply Chain", "Other"]

LIKELIHOODS = ["Rare", "Unlikely", "Possible", "Likely", "Almost Certain"]
IMPACTS = ["Insignificant", "Minor", "Moderate", "Major", "Severe"]
RISK_LEVELS = ["Low", "Medium", "High", "Critical"]

ASSESSMENT_STATUSES = [
    "Identified",
    "Assessed",
    "Mitigating",
    "Monitored",
     "Closed"]

RESPONSES = ["Avoid", "Mitigate", "Transfer", "Accept"]
REGISTER_STATUSES = ["Open", "In Progress", "Mitigated", "Accepted", "Closed"]

INSURANCE_TYPES = ["Property", "Liability", "Workers Comp", "Product",
                   "Cyber", "D&O", "Auto", "Business Interruption", "Other"]
INSURANCE_STATUSES = ["Active", "Pending", "Renewed", "Expired", "Cancelled"]

CONTINUITY_STATUSES = [
    "Draft",
    "Active",
    "Under Review",
    "Needs Update",
     "Retired"]

AUDIT_FRAMEWORKS = [
    "ISO 31000",
    "ISO 27001",
    "SOX",
    "OSHA",
    "NIST",
    "Internal",
     "Other"]
AUDIT_STATUSES = [
    "Scheduled",
    "In Progress",
    "Complete",
    "Overdue",
     "Follow-up"]

KRI_STATUSES = ["Normal", "Watch", "Warning", "Breach", "Resolved"]


# ═════════════════════════════════════════════════════════════════════════════
# Concrete register widgets
# ═════════════════════════════════════════════════════════════════════════════
class RiskAssessmentWidget(_RiskCrudWidget):
    SPEC = {
        "table": "risk_assessment",
        "title": "Risk Assessment",
        "noun": "Risk",
        "statuses": ASSESSMENT_STATUSES,
        "order_by": "assessed_date DESC",
        "action": {"label": "Mark Assessed", "status": "Assessed"},
        "columns": [
            ("title", "Risk", None),
            ("category", "Category", 130),
            ("likelihood", "Likelihood", 110),
            ("impact", "Impact", 110),
            ("risk_level", "Level", 90),
            ("owner", "Owner", 130),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "title", "label": "Risk", "kind": "text"},
            {"key": "category", "label": "Category", "kind": "combo",
                "options": RISK_CATEGORIES, "editable": True},
            {"key": "likelihood", "label": "Likelihood",
                "kind": "combo", "options": LIKELIHOODS},
            {"key": "impact", "label": "Impact",
                "kind": "combo", "options": IMPACTS},
            {"key": "risk_level", "label": "Risk Level",
                "kind": "combo", "options": RISK_LEVELS},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "assessed_date", "label": "Assessed Date", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": ASSESSMENT_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class RiskRegisterWidget(_RiskCrudWidget):
    SPEC = {
        "table": "risk_register",
        "title": "Risk Register",
        "noun": "Risk",
        "statuses": REGISTER_STATUSES,
        "order_by": "target_date",
        "action": {"label": "Mark Mitigated", "status": "Mitigated"},
        "columns": [
            ("risk", "Risk", None),
            ("category", "Category", 130),
            ("severity", "Severity", 100),
            ("response", "Response", 110),
            ("owner", "Owner", 130),
            ("target_date", "Target", 95),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "risk", "label": "Risk", "kind": "text"},
            {"key": "category", "label": "Category", "kind": "combo",
                "options": RISK_CATEGORIES, "editable": True},
            {"key": "severity", "label": "Severity",
                "kind": "combo", "options": RISK_LEVELS},
            {"key": "response", "label": "Response",
                "kind": "combo", "options": RESPONSES},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "target_date", "label": "Target Date", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": REGISTER_STATUSES},
            {"key": "mitigation", "label": "Mitigation", "kind": "memo"},
        ],
    }


class InsuranceWidget(_RiskCrudWidget):
    SPEC = {
        "table": "risk_insurance",
        "title": "Insurance Management",
        "noun": "Policy",
        "statuses": INSURANCE_STATUSES,
        "order_by": "end_date",
        "action": {"label": "Mark Renewed", "status": "Renewed"},
        "columns": [
            ("policy", "Policy", None),
            ("insurer", "Insurer", 150),
            ("policy_type", "Type", 130),
            ("coverage", "Coverage", 120),
            ("premium", "Premium", 110),
            ("end_date", "Expires", 95),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "policy", "label": "Policy", "kind": "text"},
            {"key": "insurer", "label": "Insurer", "kind": "text"},
            {"key": "policy_type", "label": "Type", "kind": "combo",
                "options": INSURANCE_TYPES, "editable": True},
            {"key": "coverage", "label": "Coverage", "kind": "money"},
            {"key": "premium", "label": "Premium", "kind": "money"},
            {"key": "start_date", "label": "Start Date", "kind": "date"},
            {"key": "end_date", "label": "End Date", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": INSURANCE_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class BusinessContinuityWidget(_RiskCrudWidget):
    SPEC = {
        "table": "risk_continuity",
        "title": "Business Continuity",
        "noun": "Plan",
        "statuses": CONTINUITY_STATUSES,
        "order_by": "next_test",
        "action": {"label": "Mark Tested", "status": "Active", "stamp": "last_tested"},  # noqa: E501
        "columns": [
            ("plan", "Plan", None),
            ("scope", "Scope", 160),
            ("criticality", "Criticality", 110),
            ("owner", "Owner", 130),
            ("last_tested", "Last Tested", 100),
            ("next_test", "Next Test", 100),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "plan", "label": "Plan", "kind": "text"},
            {"key": "scope", "label": "Scope", "kind": "text"},
            {"key": "criticality", "label": "Criticality",
                "kind": "combo", "options": RISK_LEVELS},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "last_tested", "label": "Last Tested", "kind": "date"},
            {"key": "next_test", "label": "Next Test", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": CONTINUITY_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class ComplianceAuditWidget(_RiskCrudWidget):
    SPEC = {
        "table": "risk_audit",
        "title": "Compliance & Audit",
        "noun": "Audit",
        "statuses": AUDIT_STATUSES,
        "order_by": "scheduled_date",
        "action": {"label": "Mark Complete", "status": "Complete", "stamp": "completed_date"},  # noqa: E501
        "columns": [
            ("audit", "Audit", None),
            ("framework", "Framework", 140),
            ("auditor", "Auditor", 150),
            ("scheduled_date", "Scheduled", 100),
            ("completed_date", "Completed", 100),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "audit", "label": "Audit", "kind": "text"},
            {"key": "framework", "label": "Framework", "kind": "combo",
                "options": AUDIT_FRAMEWORKS, "editable": True},
            {"key": "auditor", "label": "Auditor", "kind": "text"},
            {"key": "scheduled_date", "label": "Scheduled Date", "kind": "date"},  # noqa: E501
            {"key": "completed_date", "label": "Completed Date", "kind": "date"},  # noqa: E501
            {"key": "finding", "label": "Finding", "kind": "text"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": AUDIT_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class KRIWidget(_RiskCrudWidget):
    SPEC = {
        "table": "risk_kri",
        "title": "Key Risk Indicators",
        "noun": "Indicator",
        "statuses": KRI_STATUSES,
        "order_by": "measured_date DESC",
        "action": {"label": "Mark Resolved", "status": "Resolved"},
        "columns": [
            ("indicator", "Indicator", None),
            ("category", "Category", 130),
            ("threshold", "Threshold", 120),
            ("current_value", "Current", 110),
            ("owner", "Owner", 130),
            ("measured_date", "Measured", 100),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "indicator", "label": "Indicator", "kind": "text"},
            {"key": "category", "label": "Category", "kind": "combo",
                "options": RISK_CATEGORIES, "editable": True},
            {"key": "threshold", "label": "Threshold", "kind": "text"},
            {"key": "current_value", "label": "Current Value", "kind": "text"},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "measured_date", "label": "Measured Date", "kind": "date"},
            {"key": "status", "label": "Status",
                "kind": "combo", "options": KRI_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Standalone window (for `python -m manufacturing.Risk_mgmt`)
# ═════════════════════════════════════════════════════════════════════════════
class RiskMgmtWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = f"Risk Management — {email}" if email else "Risk Management"
        self.setWindowTitle(title)
        _apply_blue_palette(self)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(RiskAssessmentWidget(), "Risk Assessment")
        tabs.addTab(RiskRegisterWidget(), "Risk Register")
        tabs.addTab(InsuranceWidget(), "Insurance Management")
        tabs.addTab(BusinessContinuityWidget(), "Business Continuity")
        tabs.addTab(ComplianceAuditWidget(), "Compliance && Audit")
        tabs.addTab(KRIWidget(), "Key Risk Indicators")
        self.setCentralWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = RiskMgmtWindow()
    w.showMaximized()
    sys.exit(app.exec())
