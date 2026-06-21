"""
Marketing_mgmt.py — Marketing Department feature screens
Widgets: CampaignsWidget | LeadsWidget | MarketResearchWidget |
         ContentWidget | MarketingAnalyticsWidget | BudgetApprovalWidget

Each widget is a self-contained, DB-backed register (filter bar + table +
Add/Edit/Delete + a status action) built on the shared _MarketingCrudWidget
base. Schema is created and seeded on first use via init_db().
"""
import sys
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets
from .button_nav import ButtonNav
from .db_pg import get_db
from .accounts import get_current_user_email


def _conn():
    return get_db()


# ═════════════════════════════════════════════════════════════════════════════
# Schema
# ═════════════════════════════════════════════════════════════════════════════
def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS marketing_campaign (
            id         SERIAL PRIMARY KEY,
            name       TEXT    NOT NULL,
            channel    TEXT    DEFAULT '',
            objective  TEXT    DEFAULT '',
            owner      TEXT    DEFAULT '',
            start_date TEXT    DEFAULT '',
            end_date   TEXT    DEFAULT '',
            budget     REAL    DEFAULT 0,
            status     TEXT    DEFAULT 'Planned',
            notes      TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS marketing_lead (
            id            SERIAL PRIMARY KEY,
            name          TEXT    NOT NULL,
            company       TEXT    DEFAULT '',
            email         TEXT    DEFAULT '',
            source        TEXT    DEFAULT '',
            owner         TEXT    DEFAULT '',
            captured_date TEXT    DEFAULT '',
            status        TEXT    DEFAULT 'New',
            notes         TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS marketing_research (
            id             SERIAL PRIMARY KEY,
            title          TEXT    NOT NULL,
            research_type  TEXT    DEFAULT '',
            owner          TEXT    DEFAULT '',
            methodology    TEXT    DEFAULT '',
            start_date     TEXT    DEFAULT '',
            completed_date TEXT    DEFAULT '',
            status         TEXT    DEFAULT 'Proposed',
            findings       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS marketing_content (
            id           SERIAL PRIMARY KEY,
            title        TEXT    NOT NULL,
            content_type TEXT    DEFAULT '',
            channel      TEXT    DEFAULT '',
            author       TEXT    DEFAULT '',
            due_date     TEXT    DEFAULT '',
            publish_date TEXT    DEFAULT '',
            status       TEXT    DEFAULT 'Draft',
            notes        TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS marketing_analytics (
            id            SERIAL PRIMARY KEY,
            metric        TEXT    NOT NULL,
            campaign      TEXT    DEFAULT '',
            channel       TEXT    DEFAULT '',
            target        TEXT    DEFAULT '',
            actual        TEXT    DEFAULT '',
            measured_date TEXT    DEFAULT '',
            status        TEXT    DEFAULT 'On Track',
            notes         TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS marketing_budget (
            id           SERIAL PRIMARY KEY,
            item         TEXT    NOT NULL,
            campaign     TEXT    DEFAULT '',
            category     TEXT    DEFAULT '',
            amount       REAL    DEFAULT 0,
            requested_by TEXT    DEFAULT '',
            request_date TEXT    DEFAULT '',
            status       TEXT    DEFAULT 'Pending',
            notes        TEXT    DEFAULT ''
        );
        """)
        _seed(con)
        for tbl in (
            "marketing_campaign", "marketing_lead", "marketing_research",
            "marketing_content", "marketing_analytics", "marketing_budget"
        ):
            try:
                con.execute(
                    f"ALTER TABLE {tbl} "
                    "ADD COLUMN IF NOT EXISTS created_by TEXT")
            except Exception:
                pass


def _seed(con):
    today = date.today().isoformat()
    if con.execute(
        "SELECT COUNT(*) FROM marketing_campaign").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO marketing_campaign "
            "(name,channel,objective,owner,start_date,end_date,budget,status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Spring Product Launch", "Email", "Launch", "Marketing Team",
             today, "2026-07-31", 45000, "Active"))
    if con.execute("SELECT COUNT(*) FROM marketing_lead").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO marketing_lead "
            "(name,company,email,source,owner,captured_date,status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("Jane Doe", "Acme Corp", "jane@acme.example", "Web", "SDR Team", today, "New"))  # noqa: E501
    if con.execute(
        "SELECT COUNT(*) FROM marketing_research").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO marketing_research "
            "(title,research_type,owner,methodology,start_date,status) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("2026 Buyer Persona Study", "Survey", "Research Lead", "Online "
                                                                    "survey, "
                                                                    "n=500",
             today, "In Progress"))
    if con.execute(
        "SELECT COUNT(*) FROM marketing_content").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO marketing_content "
            "(title,content_type,channel,author,due_date,status) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("How Our Widget Saves Time", "Blog", "Website", "Content Team", "2026-06-15", "Draft"))  # noqa: E501
    if con.execute(
        "SELECT COUNT(*) FROM marketing_analytics").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO marketing_analytics "
            "(metric,campaign,channel,target,actual,measured_date,status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("Email open rate", "Spring Product Launch", "Email", "25%", "31%", today, "Exceeded"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM marketing_budget").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO marketing_budget "
            "(item,campaign,category,amount,requested_by,request_date,status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("Paid social ad spend", "Spring Product Launch", "Advertising", 12000,  # noqa: E501
             "Marketing Team", today, "Pending"))


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

# Row tint keyed by common status words shared across the marketing registers.
STATUS_COLORS = {
    "Planned": QtGui.QColor(255, 255, 200),
    "New": QtGui.QColor(255, 230, 205),
    "Proposed": QtGui.QColor(255, 255, 200),
    "Draft": QtGui.QColor(255, 230, 205),
    "Pending": QtGui.QColor(255, 255, 200),
    "Contacted": QtGui.QColor(255, 255, 200),
    "Nurturing": QtGui.QColor(255, 255, 200),
    "In Progress": QtGui.QColor(255, 255, 200),
    "Analysis": QtGui.QColor(255, 255, 200),
    "In Review": QtGui.QColor(255, 255, 200),
    "At Risk": QtGui.QColor(255, 200, 180),
    "Below Target": QtGui.QColor(255, 200, 180),
    "Paused": QtGui.QColor(255, 200, 180),
    "Cancelled": QtGui.QColor(255, 190, 190),
    "Lost": QtGui.QColor(255, 190, 190),
    "Rejected": QtGui.QColor(255, 190, 190),
    "Active": QtGui.QColor(200, 255, 210),
    "Qualified": QtGui.QColor(200, 255, 210),
    "Converted": QtGui.QColor(200, 255, 210),
    "Complete": QtGui.QColor(200, 255, 210),
    "Completed": QtGui.QColor(200, 255, 210),
    "Approved": QtGui.QColor(200, 255, 210),
    "Published": QtGui.QColor(200, 255, 210),
    "Exceeded": QtGui.QColor(200, 255, 210),
    "On Track": QtGui.QColor(200, 255, 210),
    "Paid": QtGui.QColor(210, 255, 230),
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
class _MarketingCrudWidget(QtWidgets.QWidget):
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
CHANNELS = ["Email", "Social", "Search", "Display", "Content", "Event",
            "PR", "Direct Mail", "Webinar", "Other"]
OBJECTIVES = [
    "Awareness",
    "Lead Gen",
    "Conversion",
    "Retention",
    "Launch",
     "Re-engagement"]
CAMPAIGN_STATUSES = ["Planned", "Active", "Paused", "Completed", "Cancelled"]

LEAD_SOURCES = [
    "Web",
    "Referral",
    "Event",
    "Cold Outreach",
    "Social",
    "Ad",
    "Partner",
     "Other"]
LEAD_STATUSES = [
    "New",
    "Contacted",
    "Qualified",
    "Nurturing",
    "Converted",
     "Lost"]

RESEARCH_TYPES = ["Survey", "Focus Group", "Competitor Analysis", "Market Trends",  # noqa: E501
                  "Customer Interview", "Other"]
RESEARCH_STATUSES = [
    "Proposed",
    "In Progress",
    "Analysis",
    "Complete",
     "Archived"]

CONTENT_TYPES = ["Blog", "Whitepaper", "Video", "Infographic", "Social Post",
                 "Email", "Ad Copy", "Case Study", "Landing Page"]
CONTENT_STATUSES = ["Draft", "In Review", "Approved", "Published", "Archived"]

ANALYTICS_STATUSES = ["On Track", "At Risk", "Below Target", "Exceeded"]

BUDGET_CATEGORIES = ["Advertising", "Events", "Content", "Tools", "Agency",
                     "Sponsorship", "Other"]
BUDGET_STATUSES = ["Pending", "Approved", "Rejected", "Paid"]


# ═════════════════════════════════════════════════════════════════════════════
# Concrete register widgets
# ═════════════════════════════════════════════════════════════════════════════
class CampaignsWidget(_MarketingCrudWidget):
    SPEC = {
        "table": "marketing_campaign",
        "title": "Campaigns",
        "noun": "Campaign",
        "statuses": CAMPAIGN_STATUSES,
        "order_by": "start_date DESC",
        "action": {"label": "Mark Completed", "status": "Completed", "stamp": "end_date"},  # noqa: E501
        "columns": [
            ("name", "Campaign", None),
            ("channel", "Channel", 120),
            ("objective", "Objective", 120),
            ("owner", "Owner", 130),
            ("budget", "Budget", 110),
            ("end_date", "Ends", 95),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "name", "label": "Campaign", "kind": "text"},
            {"key": "channel",
    "label": "Channel",
    "kind": "combo",
    "options": CHANNELS,
     "editable": True},
            {"key": "objective", "label": "Objective",
                "kind": "combo", "options": OBJECTIVES},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "start_date", "label": "Start Date", "kind": "date"},
            {"key": "end_date", "label": "End Date", "kind": "date"},
            {"key": "budget", "label": "Budget", "kind": "money"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": CAMPAIGN_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class LeadsWidget(_MarketingCrudWidget):
    SPEC = {
        "table": "marketing_lead",
        "title": "Leads & Contacts",
        "noun": "Lead",
        "statuses": LEAD_STATUSES,
        "order_by": "captured_date DESC",
        "action": {"label": "Mark Qualified", "status": "Qualified"},
        "columns": [
            ("name", "Name", None),
            ("company", "Company", 160),
            ("email", "Email", 180),
            ("source", "Source", 120),
            ("owner", "Owner", 120),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "name", "label": "Name", "kind": "text"},
            {"key": "company", "label": "Company", "kind": "text"},
            {"key": "email", "label": "Email", "kind": "text"},
            {"key": "source", "label": "Source", "kind": "combo",
                "options": LEAD_SOURCES, "editable": True},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "captured_date", "label": "Captured Date", "kind": "date"},
            {"key": "status", "label": "Status",
                "kind": "combo", "options": LEAD_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class MarketResearchWidget(_MarketingCrudWidget):
    SPEC = {
        "table": "marketing_research",
        "title": "Market Research",
        "noun": "Study",
        "statuses": RESEARCH_STATUSES,
        "order_by": "start_date DESC",
        "action": {"label": "Mark Complete", "status": "Complete", "stamp": "completed_date"},  # noqa: E501
        "columns": [
            ("title", "Study", None),
            ("research_type", "Type", 160),
            ("owner", "Owner", 140),
            ("start_date", "Started", 95),
            ("completed_date", "Completed", 100),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "title", "label": "Study", "kind": "text"},
            {"key": "research_type", "label": "Type", "kind": "combo",
                "options": RESEARCH_TYPES, "editable": True},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "methodology", "label": "Methodology", "kind": "text"},
            {"key": "start_date", "label": "Start Date", "kind": "date"},
            {"key": "completed_date", "label": "Completed Date", "kind": "date"},  # noqa: E501
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": RESEARCH_STATUSES},
            {"key": "findings", "label": "Findings", "kind": "memo"},
        ],
    }


class ContentWidget(_MarketingCrudWidget):
    SPEC = {
        "table": "marketing_content",
        "title": "Content & Collateral",
        "noun": "Content",
        "statuses": CONTENT_STATUSES,
        "order_by": "due_date",
        "action": {"label": "Mark Published", "status": "Published", "stamp": "publish_date"},  # noqa: E501
        "columns": [
            ("title", "Title", None),
            ("content_type", "Type", 130),
            ("channel", "Channel", 120),
            ("author", "Author", 140),
            ("due_date", "Due", 95),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "title", "label": "Title", "kind": "text"},
            {"key": "content_type", "label": "Type", "kind": "combo",
                "options": CONTENT_TYPES, "editable": True},
            {"key": "channel",
    "label": "Channel",
    "kind": "combo",
    "options": CHANNELS,
     "editable": True},
            {"key": "author", "label": "Author", "kind": "text"},
            {"key": "due_date", "label": "Due Date", "kind": "date"},
            {"key": "publish_date", "label": "Publish Date", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": CONTENT_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class MarketingAnalyticsWidget(_MarketingCrudWidget):
    SPEC = {
        "table": "marketing_analytics",
        "title": "Marketing Analytics",
        "noun": "Metric",
        "statuses": ANALYTICS_STATUSES,
        "order_by": "measured_date DESC",
        "action": {"label": "Mark Exceeded", "status": "Exceeded"},
        "columns": [
            ("metric", "Metric", None),
            ("campaign", "Campaign", 170),
            ("channel", "Channel", 120),
            ("target", "Target", 100),
            ("actual", "Actual", 100),
            ("measured_date", "Measured", 100),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "metric", "label": "Metric", "kind": "text"},
            {"key": "campaign", "label": "Campaign", "kind": "text"},
            {"key": "channel",
    "label": "Channel",
    "kind": "combo",
    "options": CHANNELS,
     "editable": True},
            {"key": "target", "label": "Target", "kind": "text"},
            {"key": "actual", "label": "Actual", "kind": "text"},
            {"key": "measured_date", "label": "Measured Date", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": ANALYTICS_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class BudgetApprovalWidget(_MarketingCrudWidget):
    SPEC = {
        "table": "marketing_budget",
        "title": "Budget Approvals",
        "noun": "Request",
        "statuses": BUDGET_STATUSES,
        "order_by": "request_date DESC",
        "action": {"label": "Approve", "status": "Approved"},
        "columns": [
            ("item", "Item", None),
            ("campaign", "Campaign", 170),
            ("category", "Category", 130),
            ("amount", "Amount", 110),
            ("requested_by", "Requested By", 140),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "item", "label": "Item", "kind": "text"},
            {"key": "campaign", "label": "Campaign", "kind": "text"},
            {"key": "category", "label": "Category", "kind": "combo",
                "options": BUDGET_CATEGORIES, "editable": True},
            {"key": "amount", "label": "Amount", "kind": "money"},
            {"key": "requested_by", "label": "Requested By", "kind": "text"},
            {"key": "request_date", "label": "Request Date", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": BUDGET_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Standalone window (for `python -m manufacturing.Marketing_mgmt`)
# ═════════════════════════════════════════════════════════════════════════════
class MarketingMgmtWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (
            f"Marketing Management — {email}"
            if email else "Marketing Management"
        )
        self.setWindowTitle(title)
        self.resize(1150, 740)
        _apply_blue_palette(self)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(CampaignsWidget(), "Campaigns")
        tabs.addTab(LeadsWidget(), "Leads && Contacts")
        tabs.addTab(MarketResearchWidget(), "Market Research")
        tabs.addTab(ContentWidget(), "Content && Collateral")
        tabs.addTab(MarketingAnalyticsWidget(), "Marketing Analytics")
        tabs.addTab(BudgetApprovalWidget(), "Budget Approvals")
        self.setCentralWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = MarketingMgmtWindow()
    w.show()
    sys.exit(app.exec())
