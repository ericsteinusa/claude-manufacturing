"""
Legal_mgmt.py — Legal Department feature screens
Widgets: ContractsWidget | ComplianceWidget | LitigationWidget |
         IPWidget | EmploymentLawWidget

Each widget is a self-contained, DB-backed register (filter bar + table +
Add/Edit/Delete + a status action) built on the shared _LegalCrudWidget base.
Schema is created and seeded on first use via init_db().
"""
import sys
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets
from .button_nav import ButtonNav
from .db_pg import get_db


def _conn():
    return get_db()


# ═════════════════════════════════════════════════════════════════════════════
# Schema
# ═════════════════════════════════════════════════════════════════════════════
def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS legal_contract (
            id            SERIAL PRIMARY KEY,
            title         TEXT    NOT NULL,
            counterparty  TEXT    DEFAULT '',
            contract_type TEXT    DEFAULT '',
            value         REAL    DEFAULT 0,
            start_date    TEXT    DEFAULT '',
            end_date      TEXT    DEFAULT '',
            owner         TEXT    DEFAULT '',
            status        TEXT    DEFAULT 'Draft',
            notes         TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS legal_compliance (
            id             SERIAL PRIMARY KEY,
            requirement    TEXT    NOT NULL,
            regulation     TEXT    DEFAULT '',
            owner          TEXT    DEFAULT '',
            due_date       TEXT    DEFAULT '',
            completed_date TEXT    DEFAULT '',
            status         TEXT    DEFAULT 'Pending',
            notes          TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS legal_litigation (
            id             SERIAL PRIMARY KEY,
            case_name      TEXT    NOT NULL,
            opposing_party TEXT    DEFAULT '',
            court          TEXT    DEFAULT '',
            case_type      TEXT    DEFAULT '',
            filed_date     TEXT    DEFAULT '',
            status         TEXT    DEFAULT 'Open',
            outcome        TEXT    DEFAULT '',
            notes          TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS legal_ip (
            id              SERIAL PRIMARY KEY,
            title           TEXT    NOT NULL,
            ip_type         TEXT    DEFAULT '',
            registration_no TEXT    DEFAULT '',
            jurisdiction    TEXT    DEFAULT '',
            filed_date      TEXT    DEFAULT '',
            expiry_date     TEXT    DEFAULT '',
            status          TEXT    DEFAULT 'Pending',
            notes           TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS legal_employment (
            id          SERIAL PRIMARY KEY,
            matter      TEXT    NOT NULL,
            employee    TEXT    DEFAULT '',
            matter_type TEXT    DEFAULT '',
            owner       TEXT    DEFAULT '',
            opened_date TEXT    DEFAULT '',
            closed_date TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'Open',
            notes       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS legal_governance (
            id        SERIAL PRIMARY KEY,
            item      TEXT    NOT NULL,
            category  TEXT    DEFAULT '',
            owner     TEXT    DEFAULT '',
            ref_date  TEXT    DEFAULT '',
            reference TEXT    DEFAULT '',
            status    TEXT    DEFAULT 'Active',
            notes     TEXT    DEFAULT ''
        );
        """)
        _seed(con)


def _seed(con):
    today = date.today().isoformat()
    if con.execute("SELECT COUNT(*) FROM legal_contract").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO legal_contract (title,counterparty,contract_type,value,start_date,end_date,owner,status) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Master Services Agreement", "Acme Supplies Inc.", "Service "
                                                                "Agreement",
             125000, today, "2027-05-31", "Legal Dept", "Active"))
    if con.execute("SELECT COUNT(*) FROM legal_compliance").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO legal_compliance "
            "(requirement,regulation,owner,due_date,status) "
            "VALUES (%s,%s,%s,%s,%s)",
            ("Annual OSHA safety report", "OSHA 29 CFR 1910", "Compliance Officer", "2026-12-31", "Pending"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM legal_litigation").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO legal_litigation "
            "(case_name,opposing_party,court,case_type,filed_date,status) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("Smith v. Company", "John Smith", "Superior Court", "Employment", today, "Open"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM legal_ip").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO legal_ip (title,ip_type,registration_no,jurisdiction,filed_date,expiry_date,status) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("Widget Fastening Mechanism", "Patent", "US-10-987654", "USPTO", today, "2045-05-31", "Pending"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM legal_employment").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO legal_employment "
            "(matter,employee,matter_type,owner,opened_date,status) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("Policy review request", "HR Department", "Policy Review", "Legal Dept", today, "Open"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM legal_governance").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO legal_governance "
            "(item,category,owner,ref_date,reference,status) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("2026 Annual Report", "Filing", "Corporate Secretary", "2026-04-15", "SEC 10-K", "Pending"))  # noqa: E501


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

# Row tint keyed by common status words shared across the legal registers.
STATUS_COLORS = {
    "Draft": QtGui.QColor(235, 235, 235),
    "Active": QtGui.QColor(200, 255, 210),
    "Pending": QtGui.QColor(255, 255, 200),
    "In Progress": QtGui.QColor(255, 255, 200),
    "Investigating": QtGui.QColor(255, 255, 200),
    "In Discovery": QtGui.QColor(255, 255, 200),
    "Overdue": QtGui.QColor(255, 190, 190),
    "Escalated": QtGui.QColor(255, 200, 180),
    "Complete": QtGui.QColor(200, 255, 210),
    "Completed": QtGui.QColor(200, 255, 210),
    "Resolved": QtGui.QColor(200, 255, 210),
    "Registered": QtGui.QColor(200, 255, 210),
    "Granted": QtGui.QColor(200, 255, 210),
    "Renewed": QtGui.QColor(200, 255, 210),
    "Settled": QtGui.QColor(210, 255, 230),
    "Filed": QtGui.QColor(200, 255, 210),
    "Under Review": QtGui.QColor(255, 255, 200),
    "Archived": QtGui.QColor(220, 220, 220),
    "Closed": QtGui.QColor(220, 220, 220),
    "Dismissed": QtGui.QColor(220, 220, 220),
    "Terminated": QtGui.QColor(220, 220, 220),
    "Expired": QtGui.QColor(220, 220, 220),
    "Abandoned": QtGui.QColor(220, 220, 220),
    "Open": QtGui.QColor(255, 230, 205),
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
class _LegalCrudWidget(QtWidgets.QWidget):
    # Subclasses set SPEC = {
    #   'table', 'title', 'noun',
    #   'statuses': [...],
    #   'columns': [(field_key, header, width|None)],  # 'id' implied first
    #   'fields':  [ {key,label,kind,options?} ],       # dialog + insert/update  # noqa: E501
    #   'order_by': field_key,
    #   'action': {'label', 'status', 'stamp'(optional date field key)},
    # }
    SPEC = None

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
        cols = ",".join(keys)
        ph = ",".join(["%s"] * len(keys))
        with _conn() as con:
            con.execute(f"INSERT INTO {spec['table']} ({cols}) VALUES ({ph})",
                        [v[k] for k in keys])
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
CONTRACT_TYPES = ["NDA", "Service Agreement", "Lease", "Vendor", "Employment",
                  "Licensing", "Partnership", "Other"]
CONTRACT_STATUSES = ["Draft", "Active", "Renewed", "Expired", "Terminated"]

COMPLIANCE_STATUSES = ["Pending", "In Progress", "Complete", "Overdue"]

LITIGATION_TYPES = [
    "Civil",
    "Contract Dispute",
    "IP",
    "Employment",
    "Regulatory",
     "Other"]
LITIGATION_STATUSES = [
    "Open",
    "In Discovery",
    "Settled",
    "Dismissed",
     "Closed"]

IP_TYPES = ["Patent", "Trademark", "Copyright", "Trade Secret"]
IP_STATUSES = ["Pending", "Registered", "Granted", "Expired", "Abandoned"]

EMPLOYMENT_TYPES = ["Grievance", "Discrimination", "Wrongful Termination",
                    "Policy Review", "Contract", "Harassment", "Other"]
EMPLOYMENT_STATUSES = [
    "Open",
    "Investigating",
    "Escalated",
    "Resolved",
     "Closed"]

GOVERNANCE_CATEGORIES = [
    "Board Member",
    "Policy",
    "Filing",
    "Resolution",
     "Committee"]
GOVERNANCE_STATUSES = [
    "Active",
    "Pending",
    "Under Review",
    "Filed",
     "Archived"]


# ═════════════════════════════════════════════════════════════════════════════
# Concrete register widgets
# ═════════════════════════════════════════════════════════════════════════════
class ContractsWidget(_LegalCrudWidget):
    SPEC = {
        "table": "legal_contract",
        "title": "Contracts",
        "noun": "Contract",
        "statuses": CONTRACT_STATUSES,
        "order_by": "end_date",
        "action": {"label": "Mark Renewed", "status": "Renewed"},
        "columns": [
            ("title", "Title", None),
            ("counterparty", "Counterparty", 160),
            ("contract_type", "Type", 130),
            ("value", "Value", 110),
            ("start_date", "Start", 95),
            ("end_date", "End", 95),
            ("status", "Status", 95),
        ],
        "fields": [
            {"key": "title", "label": "Title", "kind": "text"},
            {"key": "counterparty", "label": "Counterparty", "kind": "text"},
            {"key": "contract_type", "label": "Type", "kind": "combo",
                "options": CONTRACT_TYPES, "editable": True},
            {"key": "value", "label": "Value", "kind": "money"},
            {"key": "start_date", "label": "Start Date", "kind": "date"},
            {"key": "end_date", "label": "End Date", "kind": "date"},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": CONTRACT_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class ComplianceWidget(_LegalCrudWidget):
    SPEC = {
        "table": "legal_compliance",
        "title": "Compliance",
        "noun": "Item",
        "statuses": COMPLIANCE_STATUSES,
        "order_by": "due_date",
        "action": {"label": "Mark Complete", "status": "Complete", "stamp": "completed_date"},  # noqa: E501
        "columns": [
            ("requirement", "Requirement", None),
            ("regulation", "Regulation", 160),
            ("owner", "Owner", 140),
            ("due_date", "Due", 95),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "requirement", "label": "Requirement", "kind": "text"},
            {"key": "regulation", "label": "Regulation", "kind": "text"},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "due_date", "label": "Due Date", "kind": "date"},
            {"key": "completed_date", "label": "Completed Date", "kind": "date"},  # noqa: E501
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": COMPLIANCE_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class LitigationWidget(_LegalCrudWidget):
    SPEC = {
        "table": "legal_litigation",
        "title": "Litigation",
        "noun": "Case",
        "statuses": LITIGATION_STATUSES,
        "order_by": "filed_date DESC",
        "action": {"label": "Close Case", "status": "Closed"},
        "columns": [
            ("case_name", "Case", None),
            ("opposing_party", "Opposing Party", 160),
            ("court", "Court", 140),
            ("case_type", "Type", 130),
            ("filed_date", "Filed", 95),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "case_name", "label": "Case Name", "kind": "text"},
            {"key": "opposing_party", "label": "Opposing Party", "kind": "text"},  # noqa: E501
            {"key": "court", "label": "Court", "kind": "text"},
            {"key": "case_type", "label": "Type", "kind": "combo",
                "options": LITIGATION_TYPES, "editable": True},
            {"key": "filed_date", "label": "Filed Date", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": LITIGATION_STATUSES},
            {"key": "outcome", "label": "Outcome", "kind": "text"},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class IPWidget(_LegalCrudWidget):
    SPEC = {
        "table": "legal_ip",
        "title": "Intellectual Property",
        "noun": "Asset",
        "statuses": IP_STATUSES,
        "order_by": "expiry_date",
        "action": {"label": "Mark Registered", "status": "Registered"},
        "columns": [
            ("title", "Title", None),
            ("ip_type", "Type", 120),
            ("registration_no", "Registration #", 140),
            ("jurisdiction", "Jurisdiction", 110),
            ("filed_date", "Filed", 95),
            ("expiry_date", "Expiry", 95),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "title", "label": "Title", "kind": "text"},
            {"key": "ip_type", "label": "Type",
                "kind": "combo", "options": IP_TYPES},
            {"key": "registration_no", "label": "Registration #", "kind": "text"},  # noqa: E501
            {"key": "jurisdiction", "label": "Jurisdiction", "kind": "text"},
            {"key": "filed_date", "label": "Filed Date", "kind": "date"},
            {"key": "expiry_date", "label": "Expiry Date", "kind": "date"},
            {"key": "status", "label": "Status",
                "kind": "combo", "options": IP_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class EmploymentLawWidget(_LegalCrudWidget):
    SPEC = {
        "table": "legal_employment",
        "title": "Employment Law",
        "noun": "Matter",
        "statuses": EMPLOYMENT_STATUSES,
        "order_by": "opened_date DESC",
        "action": {"label": "Mark Resolved", "status": "Resolved", "stamp": "closed_date"},  # noqa: E501
        "columns": [
            ("matter", "Matter", None),
            ("employee", "Employee", 150),
            ("matter_type", "Type", 150),
            ("owner", "Owner", 130),
            ("opened_date", "Opened", 95),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "matter", "label": "Matter", "kind": "text"},
            {"key": "employee", "label": "Employee", "kind": "text"},
            {"key": "matter_type", "label": "Type", "kind": "combo",
                "options": EMPLOYMENT_TYPES, "editable": True},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "opened_date", "label": "Opened Date", "kind": "date"},
            {"key": "closed_date", "label": "Closed Date", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": EMPLOYMENT_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class GovernanceWidget(_LegalCrudWidget):
    SPEC = {
        "table": "legal_governance",
        "title": "Corporate Governance",
        "noun": "Item",
        "statuses": GOVERNANCE_STATUSES,
        "order_by": "ref_date",
        "action": {"label": "Mark Filed", "status": "Filed"},
        "columns": [
            ("item", "Item", None),
            ("category", "Category", 130),
            ("owner", "Owner", 160),
            ("ref_date", "Date", 95),
            ("reference", "Reference", 130),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "item", "label": "Item", "kind": "text"},
            {"key": "category", "label": "Category", "kind": "combo",
                "options": GOVERNANCE_CATEGORIES, "editable": True},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "ref_date", "label": "Date", "kind": "date"},
            {"key": "reference", "label": "Reference", "kind": "text"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": GOVERNANCE_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Standalone window (for `python -m manufacturing.Legal_mgmt`)
# ═════════════════════════════════════════════════════════════════════════════
class LegalMgmtWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Legal Management")
        self.resize(1150, 740)
        _apply_blue_palette(self)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(ContractsWidget(), "Contracts")
        tabs.addTab(ComplianceWidget(), "Compliance")
        tabs.addTab(LitigationWidget(), "Litigation")
        tabs.addTab(IPWidget(), "Intellectual Property")
        tabs.addTab(EmploymentLawWidget(), "Employment Law")
        tabs.addTab(GovernanceWidget(), "Corporate Governance")
        self.setCentralWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = LegalMgmtWindow()
    w.show()
    sys.exit(app.exec())
