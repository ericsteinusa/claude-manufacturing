"""
Audit_mgmt.py — Audit Management module
Tabs: Audit Schedule | Audit Findings | Corrective Actions | Audit Reports
"""
import sys, os, sqlite3
from datetime import date
from PyQt6 import QtCore, QtGui, QtWidgets

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "company.db")

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS audit_schedule (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_name  TEXT    NOT NULL,
            audit_type  TEXT    DEFAULT '',
            department  TEXT    DEFAULT '',
            auditor     TEXT    DEFAULT '',
            scheduled   TEXT    DEFAULT '',
            completed   TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'Scheduled',
            notes       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS audit_finding (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id    INTEGER DEFAULT NULL,
            finding_ref TEXT    DEFAULT '',
            description TEXT    NOT NULL,
            severity    TEXT    DEFAULT 'Minor',
            department  TEXT    DEFAULT '',
            found_date  TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'Open',
            notes       TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS corrective_action (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id  INTEGER DEFAULT NULL,
            description TEXT    NOT NULL,
            assigned_to TEXT    DEFAULT '',
            due_date    TEXT    DEFAULT '',
            completed   TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'Open',
            notes       TEXT    DEFAULT ''
        );
        """)
        if con.execute("SELECT COUNT(*) FROM audit_schedule").fetchone()[0] == 0:
            _seed(con)

def _seed(con):
    today = date.today().isoformat()
    con.execute(
        "INSERT INTO audit_schedule (audit_name, audit_type, department, auditor, scheduled, status) VALUES (?,?,?,?,?,?)",
        ("Annual Financial Audit", "Financial", "Accounting", "External Auditor", today, "Scheduled")
    )

BTN_STYLE = (
    "QPushButton{background-color:white;border:2px solid black;border-radius:8px;"
    "padding:4px 10px;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid #aaa;background:white;}"
    "QTabBar::tab{background:#cce0ff;padding:6px 14px;font-weight:bold;}"
    "QTabBar::tab:selected{background:white;border-bottom:2px solid rgb(0,85,255);}"
)

AUDIT_TYPES   = ["Financial", "Operational", "Compliance", "IT", "Safety", "Quality", "Other"]
DEPARTMENTS   = ["Accounting", "Engineering", "HR", "IT", "Maintenance", "Marketing",
                 "Production", "Purchasing", "Quality Assurance", "Sales", "All"]
AUDIT_STATUSES = ["Scheduled", "In Progress", "Completed", "Cancelled"]
SEVERITIES    = ["Critical", "Major", "Minor", "Observation"]
FINDING_STATUSES = ["Open", "In Progress", "Resolved", "Closed"]
CA_STATUSES   = ["Open", "In Progress", "Completed", "Verified", "Closed"]

STATUS_COLORS = {
    "Scheduled":   QtGui.QColor(200, 230, 255),
    "In Progress": QtGui.QColor(255, 255, 200),
    "Completed":   QtGui.QColor(200, 255, 210),
    "Cancelled":   QtGui.QColor(220, 220, 220),
    "Open":        QtGui.QColor(255, 220, 220),
    "Resolved":    QtGui.QColor(200, 255, 210),
    "Closed":      QtGui.QColor(220, 220, 220),
    "Verified":    QtGui.QColor(210, 255, 230),
}
SEVERITY_COLORS = {
    "Critical":    QtGui.QColor(255, 180, 180),
    "Major":       QtGui.QColor(255, 220, 180),
    "Minor":       QtGui.QColor(255, 255, 200),
    "Observation": QtGui.QColor(220, 235, 255),
}

_TAB_KEYS = {
    'audit_sched': 0,
    'findings':    1,
    'corr_act':    2,
    'audit_rpts':  3,
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
    item.setFlags(QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled)
    item.setTextAlignment(align | QtCore.Qt.AlignmentFlag.AlignVCenter)
    return item

def _color_row(table, row, color):
    if color:
        for c in range(table.columnCount()):
            it = table.item(row, c)
            if it:
                it.setBackground(color)


# ══════════════════════════════════════════════════════════════════════════════
# Audit Schedule Dialog
# ══════════════════════════════════════════════════════════════════════════════
class AuditDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, row_data=None):
        super().__init__(parent)
        self.setWindowTitle("Audit Entry")
        self.setMinimumWidth(420)
        v = QtWidgets.QVBoxLayout(self)
        fl = QtWidgets.QFormLayout()

        self.ef_name   = QtWidgets.QLineEdit()
        self.ef_type   = QtWidgets.QComboBox(); self.ef_type.addItems(AUDIT_TYPES); self.ef_type.setEditable(True)
        self.ef_dept   = QtWidgets.QComboBox(); self.ef_dept.addItems(DEPARTMENTS); self.ef_dept.setEditable(True)
        self.ef_auditor= QtWidgets.QLineEdit()
        self.ef_sched  = QtWidgets.QDateEdit(calendarPopup=True); self.ef_sched.setDisplayFormat("yyyy-MM-dd"); self.ef_sched.setDate(QtCore.QDate.currentDate())
        self.ef_comp   = QtWidgets.QDateEdit(calendarPopup=True); self.ef_comp.setDisplayFormat("yyyy-MM-dd"); self.ef_comp.setDate(QtCore.QDate.currentDate())
        self.ef_status = QtWidgets.QComboBox(); self.ef_status.addItems(AUDIT_STATUSES)
        self.ef_notes  = QtWidgets.QLineEdit()

        fl.addRow("Audit Name:", self.ef_name)
        fl.addRow("Type:", self.ef_type)
        fl.addRow("Department:", self.ef_dept)
        fl.addRow("Auditor:", self.ef_auditor)
        fl.addRow("Scheduled Date:", self.ef_sched)
        fl.addRow("Completed Date:", self.ef_comp)
        fl.addRow("Status:", self.ef_status)
        fl.addRow("Notes:", self.ef_notes)
        v.addLayout(fl)

        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

        if row_data:
            self.ef_name.setText(row_data["audit_name"])
            self.ef_type.setCurrentText(row_data["audit_type"])
            self.ef_dept.setCurrentText(row_data["department"])
            self.ef_auditor.setText(row_data["auditor"])
            if row_data["scheduled"]:
                self.ef_sched.setDate(QtCore.QDate.fromString(row_data["scheduled"], "yyyy-MM-dd"))
            if row_data["completed"]:
                self.ef_comp.setDate(QtCore.QDate.fromString(row_data["completed"], "yyyy-MM-dd"))
            self.ef_status.setCurrentText(row_data["status"])
            self.ef_notes.setText(row_data["notes"])

    def values(self):
        return {
            "audit_name": self.ef_name.text().strip(),
            "audit_type": self.ef_type.currentText().strip(),
            "department": self.ef_dept.currentText().strip(),
            "auditor":    self.ef_auditor.text().strip(),
            "scheduled":  self.ef_sched.date().toString("yyyy-MM-dd"),
            "completed":  self.ef_comp.date().toString("yyyy-MM-dd"),
            "status":     self.ef_status.currentText(),
            "notes":      self.ef_notes.text().strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Finding Dialog
# ══════════════════════════════════════════════════════════════════════════════
class FindingDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, row_data=None):
        super().__init__(parent)
        self.setWindowTitle("Audit Finding")
        self.setMinimumWidth(440)
        v = QtWidgets.QVBoxLayout(self)
        fl = QtWidgets.QFormLayout()

        self.ef_ref   = QtWidgets.QLineEdit()
        self.ef_desc  = QtWidgets.QTextEdit(); self.ef_desc.setMaximumHeight(80)
        self.ef_sev   = QtWidgets.QComboBox(); self.ef_sev.addItems(SEVERITIES)
        self.ef_dept  = QtWidgets.QComboBox(); self.ef_dept.addItems(DEPARTMENTS); self.ef_dept.setEditable(True)
        self.ef_date  = QtWidgets.QDateEdit(calendarPopup=True); self.ef_date.setDisplayFormat("yyyy-MM-dd"); self.ef_date.setDate(QtCore.QDate.currentDate())
        self.ef_status= QtWidgets.QComboBox(); self.ef_status.addItems(FINDING_STATUSES)
        self.ef_notes = QtWidgets.QLineEdit()

        fl.addRow("Reference #:", self.ef_ref)
        fl.addRow("Description:", self.ef_desc)
        fl.addRow("Severity:", self.ef_sev)
        fl.addRow("Department:", self.ef_dept)
        fl.addRow("Found Date:", self.ef_date)
        fl.addRow("Status:", self.ef_status)
        fl.addRow("Notes:", self.ef_notes)
        v.addLayout(fl)

        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

        if row_data:
            self.ef_ref.setText(row_data["finding_ref"])
            self.ef_desc.setPlainText(row_data["description"])
            self.ef_sev.setCurrentText(row_data["severity"])
            self.ef_dept.setCurrentText(row_data["department"])
            if row_data["found_date"]:
                self.ef_date.setDate(QtCore.QDate.fromString(row_data["found_date"], "yyyy-MM-dd"))
            self.ef_status.setCurrentText(row_data["status"])
            self.ef_notes.setText(row_data["notes"])

    def values(self):
        return {
            "finding_ref": self.ef_ref.text().strip(),
            "description": self.ef_desc.toPlainText().strip(),
            "severity":    self.ef_sev.currentText(),
            "department":  self.ef_dept.currentText().strip(),
            "found_date":  self.ef_date.date().toString("yyyy-MM-dd"),
            "status":      self.ef_status.currentText(),
            "notes":       self.ef_notes.text().strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Corrective Action Dialog
# ══════════════════════════════════════════════════════════════════════════════
class CorrectiveActionDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, row_data=None):
        super().__init__(parent)
        self.setWindowTitle("Corrective Action")
        self.setMinimumWidth(420)
        v = QtWidgets.QVBoxLayout(self)
        fl = QtWidgets.QFormLayout()

        self.ef_desc   = QtWidgets.QTextEdit(); self.ef_desc.setMaximumHeight(80)
        self.ef_assign = QtWidgets.QLineEdit()
        self.ef_due    = QtWidgets.QDateEdit(calendarPopup=True); self.ef_due.setDisplayFormat("yyyy-MM-dd"); self.ef_due.setDate(QtCore.QDate.currentDate())
        self.ef_comp   = QtWidgets.QDateEdit(calendarPopup=True); self.ef_comp.setDisplayFormat("yyyy-MM-dd"); self.ef_comp.setDate(QtCore.QDate.currentDate())
        self.ef_status = QtWidgets.QComboBox(); self.ef_status.addItems(CA_STATUSES)
        self.ef_notes  = QtWidgets.QLineEdit()

        fl.addRow("Description:", self.ef_desc)
        fl.addRow("Assigned To:", self.ef_assign)
        fl.addRow("Due Date:", self.ef_due)
        fl.addRow("Completed Date:", self.ef_comp)
        fl.addRow("Status:", self.ef_status)
        fl.addRow("Notes:", self.ef_notes)
        v.addLayout(fl)

        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

        if row_data:
            self.ef_desc.setPlainText(row_data["description"])
            self.ef_assign.setText(row_data["assigned_to"])
            if row_data["due_date"]:
                self.ef_due.setDate(QtCore.QDate.fromString(row_data["due_date"], "yyyy-MM-dd"))
            if row_data["completed"]:
                self.ef_comp.setDate(QtCore.QDate.fromString(row_data["completed"], "yyyy-MM-dd"))
            self.ef_status.setCurrentText(row_data["status"])
            self.ef_notes.setText(row_data["notes"])

    def values(self):
        return {
            "description": self.ef_desc.toPlainText().strip(),
            "assigned_to": self.ef_assign.text().strip(),
            "due_date":    self.ef_due.date().toString("yyyy-MM-dd"),
            "completed":   self.ef_comp.date().toString("yyyy-MM-dd"),
            "status":      self.ef_status.currentText(),
            "notes":       self.ef_notes.text().strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Main Audit Management Window
# ══════════════════════════════════════════════════════════════════════════════
class AuditWindow(QtWidgets.QMainWindow):
    def __init__(self, initial_tab=None):
        super().__init__()
        init_db()
        self.setWindowTitle("Audit Management")
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self._build_ui()
        self._refresh_schedule()
        self._refresh_findings()
        self._refresh_corrective()
        self._refresh_reports()
        if initial_tab in _TAB_KEYS:
            self.tabs.setCurrentIndex(_TAB_KEYS[initial_tab])

    def _build_ui(self):
        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        root = QtWidgets.QVBoxLayout(cw)
        root.setContentsMargins(8, 8, 8, 8)

        title = QtWidgets.QLabel("Audit Management")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;color:white;padding:4px;")
        root.addWidget(title)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_schedule_tab(),   "Audit Schedule")
        self.tabs.addTab(self._build_findings_tab(),   "Audit Findings")
        self.tabs.addTab(self._build_corrective_tab(), "Corrective Actions")
        self.tabs.addTab(self._build_reports_tab(),    "Audit Reports")

    # ── Audit Schedule tab ────────────────────────────────────────────────────
    def _build_schedule_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(6,6,6,6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Status:"))
        self.sched_status_filter = QtWidgets.QComboBox()
        self.sched_status_filter.addItems(["All Statuses"] + AUDIT_STATUSES)
        self.sched_status_filter.currentIndexChanged.connect(self._refresh_schedule)
        fb.addWidget(self.sched_status_filter)
        fb.addWidget(QtWidgets.QLabel("Type:"))
        self.sched_type_filter = QtWidgets.QComboBox()
        self.sched_type_filter.addItems(["All Types"] + AUDIT_TYPES)
        self.sched_type_filter.currentIndexChanged.connect(self._refresh_schedule)
        fb.addWidget(self.sched_type_filter)
        fb.addStretch()
        v.addLayout(fb)

        self.sched_tbl = QtWidgets.QTableWidget(0, 7)
        self.sched_tbl.setHorizontalHeaderLabels(["ID","Audit Name","Type","Department","Auditor","Scheduled","Status"])
        self.sched_tbl.setColumnWidth(0, 40)
        self.sched_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.sched_tbl.setColumnWidth(2, 100); self.sched_tbl.setColumnWidth(3, 120)
        self.sched_tbl.setColumnWidth(4, 120); self.sched_tbl.setColumnWidth(5, 95)
        self.sched_tbl.setColumnWidth(6, 90)
        self.sched_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.sched_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sched_tbl.setAlternatingRowColors(True)
        self.sched_tbl.verticalHeader().setDefaultSectionSize(24)
        self.sched_tbl.itemDoubleClicked.connect(self._edit_audit)
        v.addWidget(self.sched_tbl)

        bb = QtWidgets.QHBoxLayout()
        for lbl, slot in [("Add Audit", self._add_audit), ("Edit Audit", self._edit_audit),
                           ("Delete Audit", self._delete_audit), ("Mark Complete", self._mark_audit_complete)]:
            btn = QtWidgets.QPushButton(lbl); btn.setStyleSheet(BTN_STYLE); btn.clicked.connect(slot); bb.addWidget(btn)
        bb.addStretch(); v.addLayout(bb)
        return w

    def _refresh_schedule(self):
        sf = self.sched_status_filter.currentText() if hasattr(self, 'sched_status_filter') else "All Statuses"
        tf = self.sched_type_filter.currentText()   if hasattr(self, 'sched_type_filter')   else "All Types"
        with _conn() as con:
            q = "SELECT * FROM audit_schedule WHERE 1=1"
            p = []
            if sf != "All Statuses": q += " AND status=?"; p.append(sf)
            if tf != "All Types":    q += " AND audit_type=?"; p.append(tf)
            q += " ORDER BY scheduled"
            rows = con.execute(q, p).fetchall()
        self.sched_tbl.setRowCount(0)
        for row in rows:
            r = self.sched_tbl.rowCount(); self.sched_tbl.insertRow(r)
            self.sched_tbl.setItem(r,0,_ro(row["id"], QtCore.Qt.AlignmentFlag.AlignRight))
            self.sched_tbl.setItem(r,1,_ro(row["audit_name"]))
            self.sched_tbl.setItem(r,2,_ro(row["audit_type"]))
            self.sched_tbl.setItem(r,3,_ro(row["department"]))
            self.sched_tbl.setItem(r,4,_ro(row["auditor"]))
            self.sched_tbl.setItem(r,5,_ro(row["scheduled"]))
            self.sched_tbl.setItem(r,6,_ro(row["status"]))
            _color_row(self.sched_tbl, r, STATUS_COLORS.get(row["status"]))

    def _add_audit(self, *_):
        dlg = AuditDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute("INSERT INTO audit_schedule (audit_name,audit_type,department,auditor,scheduled,completed,status,notes) VALUES (?,?,?,?,?,?,?,?)",
                            (v["audit_name"],v["audit_type"],v["department"],v["auditor"],v["scheduled"],v["completed"],v["status"],v["notes"]))
            self._refresh_schedule()

    def _edit_audit(self, *_):
        if not self.sched_tbl.selectedItems(): return
        rid = int(self.sched_tbl.item(self.sched_tbl.currentRow(), 0).text())
        with _conn() as con:
            rd = con.execute("SELECT * FROM audit_schedule WHERE id=?", (rid,)).fetchone()
        if not rd: return
        dlg = AuditDialog(self, row_data=rd)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute("UPDATE audit_schedule SET audit_name=?,audit_type=?,department=?,auditor=?,scheduled=?,completed=?,status=?,notes=? WHERE id=?",
                            (v["audit_name"],v["audit_type"],v["department"],v["auditor"],v["scheduled"],v["completed"],v["status"],v["notes"],rid))
            self._refresh_schedule()

    def _delete_audit(self, *_):
        if not self.sched_tbl.selectedItems(): return
        rid = int(self.sched_tbl.item(self.sched_tbl.currentRow(), 0).text())
        if QtWidgets.QMessageBox.question(self, "Delete", "Delete this audit?") == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute("DELETE FROM audit_schedule WHERE id=?", (rid,))
            self._refresh_schedule()

    def _mark_audit_complete(self, *_):
        if not self.sched_tbl.selectedItems(): return
        rid = int(self.sched_tbl.item(self.sched_tbl.currentRow(), 0).text())
        today = date.today().isoformat()
        with _conn() as con:
            con.execute("UPDATE audit_schedule SET status='Completed', completed=? WHERE id=?", (today, rid))
        self._refresh_schedule()

    # ── Audit Findings tab ────────────────────────────────────────────────────
    def _build_findings_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(6,6,6,6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Severity:"))
        self.find_sev_filter = QtWidgets.QComboBox()
        self.find_sev_filter.addItems(["All Severities"] + SEVERITIES)
        self.find_sev_filter.currentIndexChanged.connect(self._refresh_findings)
        fb.addWidget(self.find_sev_filter)
        fb.addWidget(QtWidgets.QLabel("Status:"))
        self.find_status_filter = QtWidgets.QComboBox()
        self.find_status_filter.addItems(["All Statuses"] + FINDING_STATUSES)
        self.find_status_filter.currentIndexChanged.connect(self._refresh_findings)
        fb.addWidget(self.find_status_filter)
        fb.addStretch()
        v.addLayout(fb)

        self.find_tbl = QtWidgets.QTableWidget(0, 7)
        self.find_tbl.setHorizontalHeaderLabels(["ID","Reference","Description","Severity","Department","Found Date","Status"])
        self.find_tbl.setColumnWidth(0, 40); self.find_tbl.setColumnWidth(1, 90)
        self.find_tbl.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.find_tbl.setColumnWidth(3, 90); self.find_tbl.setColumnWidth(4, 120)
        self.find_tbl.setColumnWidth(5, 95); self.find_tbl.setColumnWidth(6, 90)
        self.find_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.find_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.find_tbl.setAlternatingRowColors(True)
        self.find_tbl.verticalHeader().setDefaultSectionSize(24)
        self.find_tbl.itemDoubleClicked.connect(self._edit_finding)
        v.addWidget(self.find_tbl)

        bb = QtWidgets.QHBoxLayout()
        for lbl, slot in [("Add Finding", self._add_finding), ("Edit Finding", self._edit_finding),
                           ("Delete Finding", self._delete_finding), ("Mark Resolved", self._mark_finding_resolved)]:
            btn = QtWidgets.QPushButton(lbl); btn.setStyleSheet(BTN_STYLE); btn.clicked.connect(slot); bb.addWidget(btn)
        bb.addStretch(); v.addLayout(bb)
        return w

    def _refresh_findings(self):
        sf = self.find_sev_filter.currentText()    if hasattr(self, 'find_sev_filter')    else "All Severities"
        stf= self.find_status_filter.currentText() if hasattr(self, 'find_status_filter') else "All Statuses"
        with _conn() as con:
            q = "SELECT * FROM audit_finding WHERE 1=1"
            p = []
            if sf  != "All Severities": q += " AND severity=?"; p.append(sf)
            if stf != "All Statuses":   q += " AND status=?";   p.append(stf)
            q += " ORDER BY found_date DESC"
            rows = con.execute(q, p).fetchall()
        self.find_tbl.setRowCount(0)
        for row in rows:
            r = self.find_tbl.rowCount(); self.find_tbl.insertRow(r)
            self.find_tbl.setItem(r,0,_ro(row["id"], QtCore.Qt.AlignmentFlag.AlignRight))
            self.find_tbl.setItem(r,1,_ro(row["finding_ref"]))
            self.find_tbl.setItem(r,2,_ro(row["description"]))
            self.find_tbl.setItem(r,3,_ro(row["severity"]))
            self.find_tbl.setItem(r,4,_ro(row["department"]))
            self.find_tbl.setItem(r,5,_ro(row["found_date"]))
            self.find_tbl.setItem(r,6,_ro(row["status"]))
            _color_row(self.find_tbl, r, SEVERITY_COLORS.get(row["severity"]))

    def _add_finding(self, *_):
        dlg = FindingDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute("INSERT INTO audit_finding (finding_ref,description,severity,department,found_date,status,notes) VALUES (?,?,?,?,?,?,?)",
                            (v["finding_ref"],v["description"],v["severity"],v["department"],v["found_date"],v["status"],v["notes"]))
            self._refresh_findings()
            self._refresh_reports()

    def _edit_finding(self, *_):
        if not self.find_tbl.selectedItems(): return
        rid = int(self.find_tbl.item(self.find_tbl.currentRow(), 0).text())
        with _conn() as con:
            rd = con.execute("SELECT * FROM audit_finding WHERE id=?", (rid,)).fetchone()
        if not rd: return
        dlg = FindingDialog(self, row_data=rd)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute("UPDATE audit_finding SET finding_ref=?,description=?,severity=?,department=?,found_date=?,status=?,notes=? WHERE id=?",
                            (v["finding_ref"],v["description"],v["severity"],v["department"],v["found_date"],v["status"],v["notes"],rid))
            self._refresh_findings()
            self._refresh_reports()

    def _delete_finding(self, *_):
        if not self.find_tbl.selectedItems(): return
        rid = int(self.find_tbl.item(self.find_tbl.currentRow(), 0).text())
        if QtWidgets.QMessageBox.question(self, "Delete", "Delete this finding?") == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute("DELETE FROM audit_finding WHERE id=?", (rid,))
            self._refresh_findings()
            self._refresh_reports()

    def _mark_finding_resolved(self, *_):
        if not self.find_tbl.selectedItems(): return
        rid = int(self.find_tbl.item(self.find_tbl.currentRow(), 0).text())
        with _conn() as con:
            con.execute("UPDATE audit_finding SET status='Resolved' WHERE id=?", (rid,))
        self._refresh_findings()

    # ── Corrective Actions tab ────────────────────────────────────────────────
    def _build_corrective_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(6,6,6,6)

        fb = QtWidgets.QHBoxLayout()
        fb.addWidget(QtWidgets.QLabel("Status:"))
        self.ca_status_filter = QtWidgets.QComboBox()
        self.ca_status_filter.addItems(["All Statuses"] + CA_STATUSES)
        self.ca_status_filter.currentIndexChanged.connect(self._refresh_corrective)
        fb.addWidget(self.ca_status_filter)
        fb.addStretch()
        v.addLayout(fb)

        self.ca_tbl = QtWidgets.QTableWidget(0, 6)
        self.ca_tbl.setHorizontalHeaderLabels(["ID","Description","Assigned To","Due Date","Completed","Status"])
        self.ca_tbl.setColumnWidth(0, 40)
        self.ca_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ca_tbl.setColumnWidth(2, 130); self.ca_tbl.setColumnWidth(3, 95)
        self.ca_tbl.setColumnWidth(4, 95);  self.ca_tbl.setColumnWidth(5, 90)
        self.ca_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ca_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ca_tbl.setAlternatingRowColors(True)
        self.ca_tbl.verticalHeader().setDefaultSectionSize(24)
        self.ca_tbl.itemDoubleClicked.connect(self._edit_ca)
        v.addWidget(self.ca_tbl)

        bb = QtWidgets.QHBoxLayout()
        for lbl, slot in [("Add Action", self._add_ca), ("Edit Action", self._edit_ca),
                           ("Delete Action", self._delete_ca), ("Mark Complete", self._mark_ca_complete)]:
            btn = QtWidgets.QPushButton(lbl); btn.setStyleSheet(BTN_STYLE); btn.clicked.connect(slot); bb.addWidget(btn)
        bb.addStretch(); v.addLayout(bb)
        return w

    def _refresh_corrective(self):
        sf = self.ca_status_filter.currentText() if hasattr(self, 'ca_status_filter') else "All Statuses"
        with _conn() as con:
            q = "SELECT * FROM corrective_action WHERE 1=1"
            p = []
            if sf != "All Statuses": q += " AND status=?"; p.append(sf)
            q += " ORDER BY due_date"
            rows = con.execute(q, p).fetchall()
        self.ca_tbl.setRowCount(0)
        for row in rows:
            r = self.ca_tbl.rowCount(); self.ca_tbl.insertRow(r)
            self.ca_tbl.setItem(r,0,_ro(row["id"], QtCore.Qt.AlignmentFlag.AlignRight))
            self.ca_tbl.setItem(r,1,_ro(row["description"]))
            self.ca_tbl.setItem(r,2,_ro(row["assigned_to"]))
            self.ca_tbl.setItem(r,3,_ro(row["due_date"]))
            self.ca_tbl.setItem(r,4,_ro(row["completed"]))
            self.ca_tbl.setItem(r,5,_ro(row["status"]))
            _color_row(self.ca_tbl, r, STATUS_COLORS.get(row["status"]))

    def _add_ca(self, *_):
        dlg = CorrectiveActionDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute("INSERT INTO corrective_action (description,assigned_to,due_date,completed,status,notes) VALUES (?,?,?,?,?,?)",
                            (v["description"],v["assigned_to"],v["due_date"],v["completed"],v["status"],v["notes"]))
            self._refresh_corrective()
            self._refresh_reports()

    def _edit_ca(self, *_):
        if not self.ca_tbl.selectedItems(): return
        rid = int(self.ca_tbl.item(self.ca_tbl.currentRow(), 0).text())
        with _conn() as con:
            rd = con.execute("SELECT * FROM corrective_action WHERE id=?", (rid,)).fetchone()
        if not rd: return
        dlg = CorrectiveActionDialog(self, row_data=rd)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            v = dlg.values()
            with _conn() as con:
                con.execute("UPDATE corrective_action SET description=?,assigned_to=?,due_date=?,completed=?,status=?,notes=? WHERE id=?",
                            (v["description"],v["assigned_to"],v["due_date"],v["completed"],v["status"],v["notes"],rid))
            self._refresh_corrective()
            self._refresh_reports()

    def _delete_ca(self, *_):
        if not self.ca_tbl.selectedItems(): return
        rid = int(self.ca_tbl.item(self.ca_tbl.currentRow(), 0).text())
        if QtWidgets.QMessageBox.question(self, "Delete", "Delete this corrective action?") == QtWidgets.QMessageBox.StandardButton.Yes:
            with _conn() as con:
                con.execute("DELETE FROM corrective_action WHERE id=?", (rid,))
            self._refresh_corrective()
            self._refresh_reports()

    def _mark_ca_complete(self, *_):
        if not self.ca_tbl.selectedItems(): return
        rid = int(self.ca_tbl.item(self.ca_tbl.currentRow(), 0).text())
        today = date.today().isoformat()
        with _conn() as con:
            con.execute("UPDATE corrective_action SET status='Completed', completed=? WHERE id=?", (today, rid))
        self._refresh_corrective()

    # ── Audit Reports tab ─────────────────────────────────────────────────────
    def _build_reports_tab(self):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(6,6,6,6)

        hdr = QtWidgets.QLabel("Audit Summary Report")
        hdr.setStyleSheet("font-size:16px;font-weight:bold;padding:4px;")
        v.addWidget(hdr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        left = QtWidgets.QWidget(); lv = QtWidgets.QVBoxLayout(left)
        lv.addWidget(QtWidgets.QLabel("<b>Audits by Status</b>"))
        self.rpt_sched_tbl = QtWidgets.QTableWidget(0, 2)
        self.rpt_sched_tbl.setHorizontalHeaderLabels(["Status", "Count"])
        self.rpt_sched_tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rpt_sched_tbl.setColumnWidth(1, 60)
        self.rpt_sched_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rpt_sched_tbl.setAlternatingRowColors(True)
        self.rpt_sched_tbl.verticalHeader().setDefaultSectionSize(24)
        lv.addWidget(self.rpt_sched_tbl)
        splitter.addWidget(left)

        mid = QtWidgets.QWidget(); mv = QtWidgets.QVBoxLayout(mid)
        mv.addWidget(QtWidgets.QLabel("<b>Findings by Severity</b>"))
        self.rpt_find_tbl = QtWidgets.QTableWidget(0, 3)
        self.rpt_find_tbl.setHorizontalHeaderLabels(["Severity", "Open", "Resolved"])
        self.rpt_find_tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rpt_find_tbl.setColumnWidth(1, 60); self.rpt_find_tbl.setColumnWidth(2, 70)
        self.rpt_find_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rpt_find_tbl.setAlternatingRowColors(True)
        self.rpt_find_tbl.verticalHeader().setDefaultSectionSize(24)
        mv.addWidget(self.rpt_find_tbl)
        splitter.addWidget(mid)

        right = QtWidgets.QWidget(); rv = QtWidgets.QVBoxLayout(right)
        rv.addWidget(QtWidgets.QLabel("<b>Corrective Actions by Status</b>"))
        self.rpt_ca_tbl = QtWidgets.QTableWidget(0, 2)
        self.rpt_ca_tbl.setHorizontalHeaderLabels(["Status", "Count"])
        self.rpt_ca_tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.rpt_ca_tbl.setColumnWidth(1, 60)
        self.rpt_ca_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rpt_ca_tbl.setAlternatingRowColors(True)
        self.rpt_ca_tbl.verticalHeader().setDefaultSectionSize(24)
        rv.addWidget(self.rpt_ca_tbl)
        splitter.addWidget(right)

        v.addWidget(splitter)
        btn = QtWidgets.QPushButton("Refresh Report"); btn.setStyleSheet(BTN_STYLE)
        btn.clicked.connect(self._refresh_reports); v.addWidget(btn)
        return w

    def _refresh_reports(self):
        if not hasattr(self, 'rpt_sched_tbl'): return
        with _conn() as con:
            sched_rows = con.execute("SELECT status, COUNT(*) as cnt FROM audit_schedule GROUP BY status").fetchall()
            find_rows  = con.execute(
                "SELECT severity, SUM(CASE WHEN status IN ('Open','In Progress') THEN 1 ELSE 0 END) as open, "
                "SUM(CASE WHEN status IN ('Resolved','Closed') THEN 1 ELSE 0 END) as resolved "
                "FROM audit_finding GROUP BY severity ORDER BY CASE severity WHEN 'Critical' THEN 1 WHEN 'Major' THEN 2 WHEN 'Minor' THEN 3 ELSE 4 END"
            ).fetchall()
            ca_rows = con.execute("SELECT status, COUNT(*) as cnt FROM corrective_action GROUP BY status").fetchall()

        self.rpt_sched_tbl.setRowCount(0)
        for row in sched_rows:
            r = self.rpt_sched_tbl.rowCount(); self.rpt_sched_tbl.insertRow(r)
            self.rpt_sched_tbl.setItem(r,0,_ro(row["status"]))
            self.rpt_sched_tbl.setItem(r,1,_ro(str(row["cnt"]), QtCore.Qt.AlignmentFlag.AlignRight))
            _color_row(self.rpt_sched_tbl, r, STATUS_COLORS.get(row["status"]))

        self.rpt_find_tbl.setRowCount(0)
        for row in find_rows:
            r = self.rpt_find_tbl.rowCount(); self.rpt_find_tbl.insertRow(r)
            self.rpt_find_tbl.setItem(r,0,_ro(row["severity"]))
            self.rpt_find_tbl.setItem(r,1,_ro(str(row["open"]),     QtCore.Qt.AlignmentFlag.AlignRight))
            self.rpt_find_tbl.setItem(r,2,_ro(str(row["resolved"]), QtCore.Qt.AlignmentFlag.AlignRight))
            _color_row(self.rpt_find_tbl, r, SEVERITY_COLORS.get(row["severity"]))

        self.rpt_ca_tbl.setRowCount(0)
        for row in ca_rows:
            r = self.rpt_ca_tbl.rowCount(); self.rpt_ca_tbl.insertRow(r)
            self.rpt_ca_tbl.setItem(r,0,_ro(row["status"]))
            self.rpt_ca_tbl.setItem(r,1,_ro(str(row["cnt"]), QtCore.Qt.AlignmentFlag.AlignRight))
            _color_row(self.rpt_ca_tbl, r, STATUS_COLORS.get(row["status"]))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = AuditWindow(sys.argv[1] if len(sys.argv) > 1 else None)
    win.show()
    sys.exit(app.exec())
