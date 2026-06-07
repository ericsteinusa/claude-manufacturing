"""
Sales_mgmt.py — Sales Manager feature screens
Widgets: QuotesWidget | CustomersWidget | SalesTargetsWidget | CommissionsWidget

Each widget is a self-contained, DB-backed register (filter bar + table +
Add/Edit/Delete + a status action) built on the shared _SalesCrudWidget base.
Schema is created and seeded on first use via init_db().
"""
import sys
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets
from .db_pg import get_db


def _conn():
    return get_db()


# ═════════════════════════════════════════════════════════════════════════════
# Schema
# ═════════════════════════════════════════════════════════════════════════════
def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS sales_quote (
            id          SERIAL PRIMARY KEY,
            customer    TEXT    NOT NULL,
            description TEXT    DEFAULT '',
            amount      REAL    DEFAULT 0,
            owner       TEXT    DEFAULT '',
            quote_date  TEXT    DEFAULT '',
            valid_until TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'Draft',
            notes       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS sales_customer (
            id      SERIAL PRIMARY KEY,
            name    TEXT    NOT NULL,
            contact TEXT    DEFAULT '',
            email   TEXT    DEFAULT '',
            phone   TEXT    DEFAULT '',
            segment TEXT    DEFAULT '',
            region  TEXT    DEFAULT '',
            owner   TEXT    DEFAULT '',
            status  TEXT    DEFAULT 'Prospect',
            notes   TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS sales_target (
            id      SERIAL PRIMARY KEY,
            rep     TEXT    NOT NULL,
            period  TEXT    DEFAULT '',
            target  REAL    DEFAULT 0,
            actual  REAL    DEFAULT 0,
            region  TEXT    DEFAULT '',
            status  TEXT    DEFAULT 'On Track',
            notes   TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS sales_commission (
            id           SERIAL PRIMARY KEY,
            rep          TEXT    NOT NULL,
            period       TEXT    DEFAULT '',
            sales_amount REAL    DEFAULT 0,
            rate         TEXT    DEFAULT '',
            commission   REAL    DEFAULT 0,
            status       TEXT    DEFAULT 'Pending',
            notes        TEXT    DEFAULT ''
        );
        """)
        _seed(con)


def _seed(con):
    today = date.today().isoformat()
    if con.execute("SELECT COUNT(*) FROM sales_quote").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO sales_quote (customer,description,amount,owner,quote_date,valid_until,status) "  # noqa: E501
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("Acme Corp", "500 units Widget A", 62000, "J. Rivera", today, "2026-06-30", "Sent"))  # noqa: E501
    if con.execute("SELECT COUNT(*) FROM sales_customer").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO sales_customer "
            "(name,contact,email,phone,segment,region,owner,status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("Acme Corp", "Jane Doe", "jane@acme.example", "555-0100", "Enterprise",  # noqa: E501
             "West", "J. Rivera", "Active"))
    if con.execute("SELECT COUNT(*) FROM sales_target").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO sales_target "
            "(rep,period,target,actual,region,status) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("J. Rivera", "Q2 2026", 250000, 180000, "West", "On Track"))
    if con.execute("SELECT COUNT(*) FROM sales_commission").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO sales_commission "
            "(rep,period,sales_amount,rate,commission,status) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            ("J. Rivera", "Q1 2026", 210000, "4%", 8400, "Pending"))


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

# Row tint keyed by common status words shared across the sales registers.
STATUS_COLORS = {
    "Draft": QtGui.QColor(255, 230, 205),
    "Prospect": QtGui.QColor(255, 255, 200),
    "Sent": QtGui.QColor(255, 255, 200),
    "Negotiation": QtGui.QColor(255, 255, 200),
    "Pending": QtGui.QColor(255, 255, 200),
    "On Track": QtGui.QColor(255, 255, 200),
    "On Hold": QtGui.QColor(255, 255, 200),
    "At Risk": QtGui.QColor(255, 200, 180),
    "Behind": QtGui.QColor(255, 200, 180),
    "Lost": QtGui.QColor(255, 190, 190),
    "Disputed": QtGui.QColor(255, 190, 190),
    "Won": QtGui.QColor(200, 255, 210),
    "Active": QtGui.QColor(200, 255, 210),
    "Met": QtGui.QColor(200, 255, 210),
    "Exceeded": QtGui.QColor(200, 255, 210),
    "Approved": QtGui.QColor(200, 255, 210),
    "Paid": QtGui.QColor(200, 255, 210),
    "Expired": QtGui.QColor(220, 220, 220),
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
class _SalesCrudWidget(QtWidgets.QWidget):
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
QUOTE_STATUSES = ["Draft", "Sent", "Negotiation", "Won", "Lost", "Expired"]

CUSTOMER_SEGMENTS = [
    "Enterprise",
    "Mid-Market",
    "SMB",
    "Government",
     "Reseller"]
CUSTOMER_REGIONS = [
    "North",
    "South",
    "East",
    "West",
    "Central",
     "International"]
CUSTOMER_STATUSES = ["Prospect", "Active", "On Hold", "Inactive"]

TARGET_STATUSES = ["On Track", "At Risk", "Behind", "Met", "Exceeded"]

COMMISSION_STATUSES = ["Pending", "Approved", "Paid", "Disputed"]


# ═════════════════════════════════════════════════════════════════════════════
# Concrete register widgets
# ═════════════════════════════════════════════════════════════════════════════
class QuotesWidget(_SalesCrudWidget):
    SPEC = {
        "table": "sales_quote",
        "title": "Quotes",
        "noun": "Quote",
        "statuses": QUOTE_STATUSES,
        "order_by": "quote_date DESC",
        "action": {"label": "Mark Won", "status": "Won"},
        "columns": [
            ("customer", "Customer", None),
            ("description", "Description", 200),
            ("amount", "Amount", 110),
            ("owner", "Owner", 120),
            ("valid_until", "Valid Until", 100),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "customer", "label": "Customer", "kind": "text"},
            {"key": "description", "label": "Description", "kind": "text"},
            {"key": "amount", "label": "Amount", "kind": "money"},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "quote_date", "label": "Quote Date", "kind": "date"},
            {"key": "valid_until", "label": "Valid Until", "kind": "date"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": QUOTE_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class CustomersWidget(_SalesCrudWidget):
    SPEC = {
        "table": "sales_customer",
        "title": "Customers",
        "noun": "Customer",
        "statuses": CUSTOMER_STATUSES,
        "order_by": "name",
        "action": {"label": "Mark Active", "status": "Active"},
        "columns": [
            ("name", "Customer", None),
            ("contact", "Contact", 140),
            ("email", "Email", 170),
            ("segment", "Segment", 120),
            ("region", "Region", 100),
            ("owner", "Owner", 120),
            ("status", "Status", 100),
        ],
        "fields": [
            {"key": "name", "label": "Customer", "kind": "text"},
            {"key": "contact", "label": "Contact", "kind": "text"},
            {"key": "email", "label": "Email", "kind": "text"},
            {"key": "phone", "label": "Phone", "kind": "text"},
            {"key": "segment", "label": "Segment", "kind": "combo",
                "options": CUSTOMER_SEGMENTS, "editable": True},
            {"key": "region", "label": "Region", "kind": "combo",
                "options": CUSTOMER_REGIONS, "editable": True},
            {"key": "owner", "label": "Owner", "kind": "text"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": CUSTOMER_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class SalesTargetsWidget(_SalesCrudWidget):
    SPEC = {
        "table": "sales_target",
        "title": "Sales Targets",
        "noun": "Target",
        "statuses": TARGET_STATUSES,
        "order_by": "rep",
        "action": {"label": "Mark Met", "status": "Met"},
        "columns": [
            ("rep", "Rep", None),
            ("period", "Period", 120),
            ("target", "Target", 120),
            ("actual", "Actual", 120),
            ("region", "Region", 110),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "rep", "label": "Rep", "kind": "text"},
            {"key": "period", "label": "Period", "kind": "text"},
            {"key": "target", "label": "Target", "kind": "money"},
            {"key": "actual", "label": "Actual", "kind": "money"},
            {"key": "region", "label": "Region", "kind": "combo",
                "options": CUSTOMER_REGIONS, "editable": True},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": TARGET_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


class CommissionsWidget(_SalesCrudWidget):
    SPEC = {
        "table": "sales_commission",
        "title": "Commissions",
        "noun": "Commission",
        "statuses": COMMISSION_STATUSES,
        "order_by": "rep",
        "action": {"label": "Mark Paid", "status": "Paid"},
        "columns": [
            ("rep", "Rep", None),
            ("period", "Period", 120),
            ("sales_amount", "Sales", 120),
            ("rate", "Rate", 80),
            ("commission", "Commission", 120),
            ("status", "Status", 110),
        ],
        "fields": [
            {"key": "rep", "label": "Rep", "kind": "text"},
            {"key": "period", "label": "Period", "kind": "text"},
            {"key": "sales_amount", "label": "Sales Amount", "kind": "money"},
            {"key": "rate", "label": "Rate", "kind": "text"},
            {"key": "commission", "label": "Commission", "kind": "money"},
            {"key": "status",
    "label": "Status",
    "kind": "combo",
     "options": COMMISSION_STATUSES},
            {"key": "notes", "label": "Notes", "kind": "memo"},
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Standalone window (for `python -m manufacturing.Sales_mgmt`)
# ═════════════════════════════════════════════════════════════════════════════
class SalesMgmtWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sales Management")
        self.resize(1150, 740)
        _apply_blue_palette(self)
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(QuotesWidget(), "Quotes")
        tabs.addTab(CustomersWidget(), "Customers")
        tabs.addTab(SalesTargetsWidget(), "Sales Targets")
        tabs.addTab(CommissionsWidget(), "Commissions")
        self.setCentralWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = SalesMgmtWindow()
    w.show()
    sys.exit(app.exec())
