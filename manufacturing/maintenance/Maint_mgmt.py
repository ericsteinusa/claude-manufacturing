"""
Maint_mgmt.py — Maintenance Department feature screens
Widgets: WorkOrdersWidget | EquipmentWidget | PartsInventoryWidget |
         MaintScheduleWidget | SafetyInspectionWidget | DowntimeWidget

Each widget is a self-contained, DB-backed register (filter bar + table +
Add/Edit/Delete + a status action) built on the shared _MaintCrudWidget base.
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
        CREATE TABLE IF NOT EXISTS maint_work_order (
            id             SERIAL PRIMARY KEY,
            title          TEXT    NOT NULL,
            equipment      TEXT    DEFAULT '',
            work_type      TEXT    DEFAULT '',
            priority       TEXT    DEFAULT 'Medium',
            assigned_to    TEXT    DEFAULT '',
            requested_date TEXT    DEFAULT '',
            due_date       TEXT    DEFAULT '',
            completed_date TEXT    DEFAULT '',
            status         TEXT    DEFAULT 'Open',
            notes          TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS maint_equipment (
            id           SERIAL PRIMARY KEY,
            name         TEXT    NOT NULL,
            asset_tag    TEXT    DEFAULT '',
            location     TEXT    DEFAULT '',
            manufacturer TEXT    DEFAULT '',
            install_date TEXT    DEFAULT '',
            last_service TEXT    DEFAULT '',
            status       TEXT    DEFAULT 'Operational',
            notes        TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS maint_part (
            id            SERIAL PRIMARY KEY,
            name          TEXT    NOT NULL,
            part_number   TEXT    DEFAULT '',
            category      TEXT    DEFAULT '',
            location      TEXT    DEFAULT '',
            quantity      TEXT    DEFAULT '',
            reorder_level TEXT    DEFAULT '',
            unit_cost     REAL    DEFAULT 0,
            status        TEXT    DEFAULT 'In Stock',
            notes         TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS maint_schedule (
            id          SERIAL PRIMARY KEY,
            task        TEXT    NOT NULL,
            equipment   TEXT    DEFAULT '',
            frequency   TEXT    DEFAULT '',
            assigned_to TEXT    DEFAULT '',
            last_done   TEXT    DEFAULT '',
            next_due    TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'Scheduled',
            notes       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS maint_inspection (
            id              SERIAL PRIMARY KEY,
            area            TEXT    NOT NULL,
            inspection_type TEXT    DEFAULT '',
            inspector       TEXT    DEFAULT '',
            scheduled_date  TEXT    DEFAULT '',
            completed_date  TEXT    DEFAULT '',
            result          TEXT    DEFAULT '',
            status          TEXT    DEFAULT 'Scheduled',
            notes           TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS maint_downtime (
            id        SERIAL PRIMARY KEY,
            equipment TEXT    NOT NULL,
            reason    TEXT    DEFAULT '',
            category  TEXT    DEFAULT '',
            down_date TEXT    DEFAULT '',
            hours     TEXT    DEFAULT '',
            cost      REAL    DEFAULT 0,
            status    TEXT    DEFAULT 'Ongoing',
            notes     TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS maint_mechanic (
            id     SERIAL PRIMARY KEY,
            name   TEXT    NOT NULL,
            trade  TEXT    DEFAULT '',
            shift  TEXT    DEFAULT '',
            phone  TEXT    DEFAULT '',
            status TEXT    DEFAULT 'Active',
            notes  TEXT    DEFAULT ''
        );
        """)
        _seed(con)
    try:
        with _conn() as con:
            for tbl in ("maint_work_order", "maint_equipment", "maint_part",
                        "maint_schedule", "maint_inspection", "maint_downtime",
                        "maint_mechanic"):
                con.execute(
                    f"ALTER TABLE {tbl}"
                    " ADD COLUMN IF NOT EXISTS created_by TEXT")
    except Exception:
        pass


def _seed(con):
    today = date.today().isoformat()
    if con.execute("SELECT COUNT(*) FROM maint_work_order").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO maint_work_order (title,equipment,work_type,priority,assigned_to,requested_date,due_date,status) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Replace conveyor belt motor", "Conveyor Line A", "Repair", "High",  # noqa: E501
             "M. Tanaka", today, "2026-06-10", "Open"))
    if con.execute("SELECT COUNT(*) FROM maint_equipment").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO maint_equipment (name,asset_tag,location,manufacturer,install_date,last_service,status) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("CNC Milling Machine #3", "EQ-1042", "Shop Floor B", "Haas", "2022-03-15",  # noqa: E501
             "2026-04-01", "Operational"))
    if con.execute("SELECT COUNT(*) FROM maint_part").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO maint_part (name,part_number,category,location,quantity,reorder_level,unit_cost,status) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Drive belt V-type", "BLT-220", "Belts", "Aisle 4 / Bin 12", "3", "5", 42.50, "Low Stock"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM maint_schedule").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO maint_schedule "
            "(task,equipment,frequency,assigned_to,last_done,next_due,status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("Lubricate bearings", "Conveyor Line A", "Monthly", "M. Tanaka",
             "2026-05-01", "2026-06-01", "Scheduled"))
    if con.execute("SELECT COUNT(*) FROM maint_inspection").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO maint_inspection "
            "(area,inspection_type,inspector,scheduled_date,status) "
            "VALUES (%s,%s,%s,%s,%s)",
            ("Shop Floor B", "Fire Safety", "Safety Officer", "2026-06-20", "Scheduled"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM maint_downtime").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO maint_downtime "
            "(equipment,reason,category,down_date,hours,cost,status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("Conveyor Line A", "Motor failure", "Breakdown", today, "4", 1800, "Ongoing"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM maint_mechanic").fetchone()[0] == 0:
        con.executemany(
            "INSERT INTO maint_mechanic (name,trade,shift,phone,status) "
            "VALUES (%s,%s,%s,%s,%s)",
            [("M. Tanaka", "Mechanical", "Day", "x4101", "Active"),
             ("R. Okafor", "Electrical", "Day", "x4102", "Active"),
             ("L. Petrov", "HVAC", "Swing", "x4103", "Active")])


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

# Row tint keyed by common status words shared across the maintenance
# registers.
STATUS_COLORS = {
    "Open": QtGui.QColor(255, 230, 205),
    "Assigned": QtGui.QColor(255, 255, 200),
    "In Progress": QtGui.QColor(255, 255, 200),
    "Scheduled": QtGui.QColor(255, 255, 200),
    "Due": QtGui.QColor(255, 255, 200),
    "Needs Service": QtGui.QColor(255, 255, 200),
    "Low Stock": QtGui.QColor(255, 255, 200),
    "On Order": QtGui.QColor(255, 255, 200),
    "Follow-up": QtGui.QColor(255, 255, 200),
    "Investigating": QtGui.QColor(255, 255, 200),
    "On Hold": QtGui.QColor(255, 200, 180),
    "Under Repair": QtGui.QColor(255, 200, 180),
    "Recurring": QtGui.QColor(255, 200, 180),
    "Down": QtGui.QColor(255, 190, 190),
    "Ongoing": QtGui.QColor(255, 190, 190),
    "Overdue": QtGui.QColor(255, 190, 190),
    "Failed": QtGui.QColor(255, 190, 190),
    "Out of Stock": QtGui.QColor(255, 190, 190),
    "Cancelled": QtGui.QColor(255, 190, 190),
    "Operational": QtGui.QColor(200, 255, 210),
    "Completed": QtGui.QColor(200, 255, 210),
    "In Stock": QtGui.QColor(200, 255, 210),
    "Passed": QtGui.QColor(200, 255, 210),
    "Resolved": QtGui.QColor(200, 255, 210),
    "Active": QtGui.QColor(200, 255, 210),
    "On Leave": QtGui.QColor(255, 255, 200),
    "Skipped": QtGui.QColor(220, 220, 220),
    "Retired": QtGui.QColor(220, 220, 220),
    "Discontinued": QtGui.QColor(220, 220, 220),
    "Inactive": QtGui.QColor(220, 220, 220),
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
class _MaintCrudWidget(QtWidgets.QWidget):
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
        buttons += self._extra_buttons()
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

    def _extra_buttons(self):
        """Subclasses return a list of (label, slot) for extra action buttons."""  # noqa: E501
        return []

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
WORK_TYPES = ["Repair", "Inspection", "Installation", "Calibration",
              "Cleaning", "Replacement", "Preventive", "Other"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
WORK_ORDER_STATUSES = [
    "Open",
    "Assigned",
    "In Progress",
    "On Hold",
    "Completed",
     "Cancelled"]

EQUIPMENT_STATUSES = [
    "Operational",
    "Needs Service",
    "Under Repair",
    "Down",
     "Retired"]

PART_CATEGORIES = ["Belts", "Bearings", "Filters", "Motors", "Electrical",
                   "Hydraulics", "Fasteners", "Lubricants", "Other"]
PART_STATUSES = [
    "In Stock",
    "Low Stock",
    "On Order",
    "Out of Stock",
     "Discontinued"]

FREQUENCIES = [
    "Daily",
    "Weekly",
    "Monthly",
    "Quarterly",
    "Semi-Annual",
     "Annual"]
SCHEDULE_STATUSES = ["Scheduled", "Due", "Overdue", "Completed", "Skipped"]

INSPECTION_TYPES = ["Fire Safety", "Electrical", "Machine Guarding", "PPE",
                    "Lockout/Tagout", "Environmental", "General"]
INSPECTION_STATUSES = [
    "Scheduled",
    "In Progress",
    "Passed",
    "Failed",
     "Follow-up"]

DOWNTIME_CATEGORIES = ["Breakdown", "Planned", "Setup", "Material Shortage",
                       "Quality", "Changeover", "Other"]
DOWNTIME_STATUSES = ["Ongoing", "Investigating", "Resolved", "Recurring"]

MECHANIC_TRADES = ["Mechanical", "Electrical", "HVAC", "Hydraulics",
                   "Welding", "General"]
MECHANIC_SHIFTS = ["Day", "Swing", "Night"]
MECHANIC_STATUSES = ["Active", "On Leave", "Inactive"]


def _mechanic_names():
    """Active mechanics from the roster, ordered by name — used for assignment."""  # noqa: E501
    with _conn() as con:
        rows = con.execute(
            "SELECT name FROM maint_mechanic WHERE status='Active' ORDER BY "
            "name"
        ).fetchall()
    return [r["name"] for r in rows]


# ═════════════════════════════════════════════════════════════════════════════
# Concrete register widgets
# ═════════════════════════════════════════════════════════════════════════════
class WorkOrdersWidget(_MaintCrudWidget):
    SPEC = {
        "table": "maint_work_order",
        "title": "Work Orders",
        "noun": "Work Order",
        "statuses": WORK_ORDER_STATUSES,
        "order_by": "due_date",
        "action": {"label": "Mark Completed", "status": "Completed", "stamp": "completed_date"},  # noqa: E501
        "columns": [
            ("title", "Work Order", None),
            ("equipment", "Equipment", 150),
            ("work_type", "Type", 120),
            ("priority", "Priority", 90),
            ("assigned_to", "Assigned", 130),
            ("due_date", "Due", 95),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "title", "label": "Work Order", "kind": "text"},
            {"key": "equipment", "label": "Equipment", "kind": "text"},
            {"key": "work_type", "label": "Type", "kind": "combo",
                "options": WORK_TYPES, "editable": True},
            {"key": "priority", "label": "Priority",
                "kind": "combo", "options": PRIORITIES},
            {"key": "assigned_to", "label": "Assigned To", "kind": "text"},
            {"key": "requested_date", "label": "Requested Date", "kind": "date"},  # noqa: E501
            {"key": "due_date", "label": "Due Date", "kind": "date"},
            {"key": "completed_date", "label": "Completed Date", "kind": "date"},  # noqa: E501
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": WORK_ORDER_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }

    def _extra_buttons(self):
        return [("Print Work Order", self._on_print_wo)]

    def _on_print_wo(self, *_):
        rid = self._selected_id()
        if rid is None:
            QtWidgets.QMessageBox.information(
                self, "Print", "Select a work order first.")
            return
        from ..print_utils import print_document, doc_header, fields_table, wrap_html
        with _conn() as con:
            row = con.execute(
                "SELECT * FROM maint_work_order WHERE id = %s", (rid,)
            ).fetchone()
        if not row:
            return
        wo = dict(row)
        fields = [
            ("ID",             str(wo.get("id") or "")),
            ("Work Order",     wo.get("title") or ""),
            ("Equipment",      wo.get("equipment") or ""),
            ("Type",           wo.get("work_type") or ""),
            ("Priority",       wo.get("priority") or ""),
            ("Assigned To",    wo.get("assigned_to") or ""),
            ("Requested Date", str(wo.get("requested_date") or "")),
            ("Due Date",       str(wo.get("due_date") or "")),
            ("Completed Date", str(wo.get("completed_date") or "")),
            ("Status",         wo.get("status") or ""),
            ("Notes",          wo.get("notes") or ""),
            ("Created By",     wo.get("created_by") or ""),
        ]
        html = wrap_html(
            doc_header(f"Maintenance Work Order — {wo.get('title', '')}")
            + fields_table(fields)
        )
        print_document(html, f"Maint WO {rid}", self)


class WorkOrderMgmtWidget(WorkOrdersWidget):
    """Manager view of work orders: adds the ability to assign a mechanic.

    Assigning picks an active mechanic from the roster, writes ``assigned_to``,
    and moves the order to ``Assigned``.
    """

    def _extra_buttons(self):
        return super()._extra_buttons() + [("Assign to Mechanic", self._assign)]

    def _assign(self, *_):
        rid = self._selected_id()
        if rid is None:
            return
        mechanics = _mechanic_names()
        if not mechanics:
            QtWidgets.QMessageBox.information(
                self, "No Mechanics",
                "No active mechanics in the roster. Add one in the Mechanics "
                "tab first.")
            return
        name, ok = QtWidgets.QInputDialog.getItem(
            self, "Assign Work Order", "Mechanic:", mechanics, 0, False)
        if not ok or not name:
            return
        with _conn() as con:
            con.execute(
                "UPDATE maint_work_order SET assigned_to=%s, "
                "status='Assigned' WHERE id=%s",
                (name, rid))
        self._refresh()


class EquipmentWidget(_MaintCrudWidget):
    SPEC = {
        "table": "maint_equipment",
        "title": "Equipment",
        "noun": "Equipment",
        "statuses": EQUIPMENT_STATUSES,
        "order_by": "name",
        "action": {"label": "Mark Operational", "status": "Operational"},
        "columns": [
            ("name", "Equipment", None),
            ("asset_tag", "Asset Tag", 110),
            ("location", "Location", 140),
            ("manufacturer", "Manufacturer", 130),
            ("last_service", "Last Service", 110),
            ("status", "Status", 120),
        ],
        "fields": [
            {"key": "name", "label": "Equipment", "kind": "text"},
            {"key": "asset_tag", "label": "Asset Tag", "kind": "text"},
            {"key": "location", "label": "Location", "kind": "text"},
            {"key": "manufacturer", "label": "Manufacturer", "kind": "text"},
            {"key": "install_date", "label": "Install Date", "kind": "date"},
            {"key": "last_service", "label": "Last Service", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": EQUIPMENT_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class PartsInventoryWidget(_MaintCrudWidget):
    SPEC = {
        "table": "maint_part",
        "title": "Parts Inventory",
        "noun": "Part",
        "statuses": PART_STATUSES,
        "order_by": "name",
        "action": {"label": "Mark On Order", "status": "On Order"},
        "columns": [
            ("name", "Part", None),
            ("part_number", "Part #", 120),
            ("category", "Category", 120),
            ("location", "Location", 140),
            ("quantity", "Qty", 70),
            ("unit_cost", "Unit Cost", 100),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "name", "label": "Part", "kind": "text"},
            {"key": "part_number", "label": "Part #", "kind": "text"},
            {"key": "category", "label": "Category", "kind": "combo",
                "options": PART_CATEGORIES, "editable": True},
            {"key": "location", "label": "Location", "kind": "text"},
            {"key": "quantity", "label": "Quantity", "kind": "text"},
            {"key": "reorder_level", "label": "Reorder Level", "kind": "text"},
            {"key": "unit_cost", "label": "Unit Cost", "kind": "money"},
            {"key": "status", "label": "Status",
                "kind": "combo", "options": PART_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class MaintScheduleWidget(_MaintCrudWidget):
    SPEC = {
        "table": "maint_schedule",
        "title": "Maintenance Schedule",
        "noun": "Task",
        "statuses": SCHEDULE_STATUSES,
        "order_by": "next_due",
        "action": {"label": "Mark Completed", "status": "Completed", "stamp": "last_done"},  # noqa: E501
        "columns": [
            ("task", "Task", None),
            ("equipment", "Equipment", 160),
            ("frequency", "Frequency", 110),
            ("assigned_to", "Assigned", 130),
            ("next_due", "Next Due", 100),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "task", "label": "Task", "kind": "text"},
            {"key": "equipment", "label": "Equipment", "kind": "text"},
            {"key": "frequency", "label": "Frequency",
                "kind": "combo", "options": FREQUENCIES},
            {"key": "assigned_to", "label": "Assigned To", "kind": "text"},
            {"key": "last_done", "label": "Last Done", "kind": "date"},
            {"key": "next_due", "label": "Next Due", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": SCHEDULE_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class SafetyInspectionWidget(_MaintCrudWidget):
    SPEC = {
        "table": "maint_inspection",
        "title": "Safety Inspections",
        "noun": "Inspection",
        "statuses": INSPECTION_STATUSES,
        "order_by": "scheduled_date",
        "action": {"label": "Mark Passed", "status": "Passed", "stamp": "completed_date"},  # noqa: E501
        "columns": [
            ("area", "Area", None),
            ("inspection_type", "Type", 150),
            ("inspector", "Inspector", 150),
            ("scheduled_date", "Scheduled", 100),
            ("completed_date", "Completed", 100),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "area", "label": "Area", "kind": "text"},
            {"key": "inspection_type", "label": "Type", "kind": "combo",
                "options": INSPECTION_TYPES, "editable": True},
            {"key": "inspector", "label": "Inspector", "kind": "text"},
            {"key": "scheduled_date", "label": "Scheduled Date", "kind": "date"},  # noqa: E501
            {"key": "completed_date", "label": "Completed Date", "kind": "date"},  # noqa: E501
            {"key": "result", "label": "Result", "kind": "text"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": INSPECTION_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class DowntimeWidget(_MaintCrudWidget):
    SPEC = {
        "table": "maint_downtime",
        "title": "Downtime & Reliability",
        "noun": "Event",
        "statuses": DOWNTIME_STATUSES,
        "order_by": "down_date DESC",
        "action": {"label": "Mark Resolved", "status": "Resolved"},
        "columns": [
            ("equipment", "Equipment", None),
            ("reason", "Reason", 180),
            ("category", "Category", 140),
            ("down_date", "Date", 95),
            ("hours", "Hours", 70),
            ("cost", "Cost", 110),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "equipment", "label": "Equipment", "kind": "text"},
            {"key": "reason", "label": "Reason", "kind": "text"},
            {"key": "category", "label": "Category", "kind": "combo",
                "options": DOWNTIME_CATEGORIES, "editable": True},
            {"key": "down_date", "label": "Date", "kind": "date"},
            {"key": "hours", "label": "Hours", "kind": "text"},
            {"key": "cost", "label": "Cost", "kind": "money"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": DOWNTIME_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class MechanicsWidget(_MaintCrudWidget):
    SPEC = {
        "table": "maint_mechanic",
        "title": "Mechanics",
        "noun": "Mechanic",
        "statuses": MECHANIC_STATUSES,
        "order_by": "name",
        "action": {"label": "Mark Active", "status": "Active"},
        "columns": [
            ("name", "Name", None),
            ("trade", "Trade", 130),
            ("shift", "Shift", 100),
            ("phone", "Phone", 110),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "name", "label": "Name", "kind": "text"},
            {"key": "trade", "label": "Trade", "kind": "combo",
                "options": MECHANIC_TRADES, "editable": True},
            {"key": "shift",
    "label": "Shift",
    "kind": "combo",
     "options": MECHANIC_SHIFTS},
            {"key": "phone", "label": "Phone", "kind": "text"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": MECHANIC_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Standalone window (for `python -m manufacturing.Maint_mgmt`)
# ═════════════════════════════════════════════════════════════════════════════
class MaintMgmtWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Maintenance Management — {email}" if email
                 else "Maintenance Management")
        self.setWindowTitle(title)
        _apply_blue_palette(self)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(WorkOrdersWidget(), "Work Orders")
        tabs.addTab(EquipmentWidget(), "Equipment")
        tabs.addTab(PartsInventoryWidget(), "Parts Inventory")
        tabs.addTab(MaintScheduleWidget(), "Maintenance Schedule")
        tabs.addTab(SafetyInspectionWidget(), "Safety Inspections")
        tabs.addTab(DowntimeWidget(), "Downtime && Reliability")
        tabs.addTab(MechanicsWidget(), "Mechanics")
        self.setCentralWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = MaintMgmtWindow()
    w.showMaximized()
    sys.exit(app.exec())
