import sys
from datetime import date as _date
from ..db_pg import get_db_connection
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
from ..it_core import (
    list_tickets, get_ticket, create_ticket, update_ticket, set_ticket_status,
    next_ticket_number,
    TICKET_STATUSES, TICKET_PRIORITIES, ISSUE_TYPES,
)

TEXT_STYLE = (
    "QPlainTextEdit{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
)

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)

_TICKET_COLORS = {
    "open":        "#ffffff",
    "in_progress": "#fff3cd",
    "resolved":    "#d4edda",
    "closed":      "#dcdcdc",
}
_PRIORITY_COLORS = {
    "critical": QtGui.QColor(248, 215, 218),
    "high":     QtGui.QColor(255, 243, 205),
    "medium":   QtGui.QColor(220, 235, 255),
}


def _get_db():
    return get_db_connection()


def _me() -> str:
    return get_current_user_email() or ""


# ---------------------------------------------------------------------------
# Add / Edit dialogs
# ---------------------------------------------------------------------------

class _TicketDialog(QtWidgets.QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 460)
        _apply_blue_palette(self)
        self.ticket_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.ticket_num = QtWidgets.QLineEdit()
        self.ticket_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Ticket #:"), self.ticket_num)

        self.requester = QtWidgets.QLineEdit()
        self.requester.setStyleSheet(INPUT_STYLE)
        self.requester.setPlaceholderText("Person submitting (required)")
        layout.addRow(lbl("Requester:"), self.requester)

        self.department = QtWidgets.QLineEdit()
        self.department.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Department:"), self.department)

        self.issue_type = QtWidgets.QComboBox()
        self.issue_type.setStyleSheet(COMBO_STYLE)
        for t in ISSUE_TYPES:
            self.issue_type.addItem(t, t)
        layout.addRow(lbl("Issue Type:"), self.issue_type)

        self.description = QtWidgets.QPlainTextEdit()
        self.description.setStyleSheet(TEXT_STYLE)
        self.description.setFixedHeight(80)
        self.description.setPlaceholderText("Describe the problem (required)")
        layout.addRow(lbl("Description:"), self.description)

        self.priority_combo = QtWidgets.QComboBox()
        self.priority_combo.setStyleSheet(COMBO_STYLE)
        for s in TICKET_PRIORITIES:
            self.priority_combo.addItem(s.capitalize(), s)
        self.priority_combo.setCurrentIndex(1)
        layout.addRow(lbl("Priority:"), self.priority_combo)

        self.assigned_to = QtWidgets.QLineEdit()
        self.assigned_to.setStyleSheet(INPUT_STYLE)
        self.assigned_to.setPlaceholderText("Assigned technician")
        layout.addRow(lbl("Assigned To:"), self.assigned_to)

        self.submitted_date = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(_date.today().isoformat(), "yyyy-MM-dd"))
        self.submitted_date.setCalendarPopup(True)
        self.submitted_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Submitted:"), self.submitted_date)

        self.due_date = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(_date.today().isoformat(), "yyyy-MM-dd"
                                    ).addDays(3))
        self.due_date.setCalendarPopup(True)
        self.due_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Due Date:"), self.due_date)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Notes:"), self.notes)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _populate(self, rec: dict):
        self.ticket_num.setText(rec.get("ticket_number") or "")
        self.requester.setText(rec.get("requester") or "")
        self.department.setText(rec.get("department") or "")
        idx = self.issue_type.findData(rec.get("issue_type"))
        if idx >= 0:
            self.issue_type.setCurrentIndex(idx)
        self.description.setPlainText(rec.get("description") or "")
        idx = self.priority_combo.findData(rec.get("priority"))
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)
        self.assigned_to.setText(rec.get("assigned_to") or "")
        for field, widget in (
            ("submitted_date", self.submitted_date),
            ("due_date",       self.due_date),
        ):
            d = rec.get(field)
            if d:
                widget.setDate(
                    QtCore.QDate.fromString(str(d), "yyyy-MM-dd"))
        self.notes.setText(rec.get("notes") or "")

    def _on_ok(self):
        if not self.requester.text().strip() or \
                not self.description.toPlainText().strip():
            QtWidgets.QMessageBox.warning(
                self, "Input Error",
                "Requester and description are required.")
            return
        self._save()

    def _save(self):
        raise NotImplementedError


class AddTicketDialog(_TicketDialog):
    def __init__(self, parent=None):
        super().__init__("New Help Desk Ticket", parent)
        conn = _get_db()
        num = next_ticket_number(conn)
        conn.close()
        self.ticket_num.setText(num)
        self.ticket_num.setReadOnly(True)

    def _save(self):
        conn = _get_db()
        try:
            self.ticket_id = create_ticket(
                conn,
                ticket_number=self.ticket_num.text().strip(),
                requester=self.requester.text().strip(),
                department=self.department.text().strip(),
                issue_type=self.issue_type.currentData(),
                description=self.description.toPlainText().strip(),
                priority=self.priority_combo.currentData(),
                assigned_to=self.assigned_to.text().strip(),
                submitted_date=self.submitted_date.date().toString(
                    "yyyy-MM-dd"),
                due_date=self.due_date.date().toString("yyyy-MM-dd"),
                notes=self.notes.text().strip(),
                created_by=_me(),
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class EditTicketDialog(_TicketDialog):
    def __init__(self, ticket_id: int, parent=None):
        super().__init__("Edit Ticket", parent)
        self._edit_id: int = ticket_id
        self.ticket_id = ticket_id
        self.ticket_num.setReadOnly(True)
        conn = _get_db()
        rec = get_ticket(conn, ticket_id)
        conn.close()
        if rec:
            self._populate(rec)

    def _save(self):
        conn = _get_db()
        try:
            update_ticket(
                conn, self._edit_id,
                requester=self.requester.text().strip(),
                department=self.department.text().strip(),
                issue_type=self.issue_type.currentData(),
                description=self.description.toPlainText().strip(),
                priority=self.priority_combo.currentData(),
                assigned_to=self.assigned_to.text().strip(),
                submitted_date=self.submitted_date.date().toString(
                    "yyyy-MM-dd"),
                due_date=self.due_date.date().toString("yyyy-MM-dd"),
                notes=self.notes.text().strip(),
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


# ---------------------------------------------------------------------------
# Shared ticket table base
# ---------------------------------------------------------------------------

class _TicketTableWidget(QtWidgets.QWidget):
    """Base for ticket list views — subclasses set _load_rows() and _build_filters()."""

    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._row_ids: list[int] = []
        self._selected_id: int | None = None
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        self._build_filters(fr)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self._table = QtWidgets.QTableWidget()
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels([
            "Ticket #", "Requester", "Department", "Issue Type",
            "Priority", "Assigned To", "Submitted", "Due Date", "Status",
        ])
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6, 7, 8):
            hh.setSectionResizeMode(
                col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.clicked.connect(self._on_row_clicked)
        self._table.doubleClicked.connect(self._on_edit)
        splitter.addWidget(self._table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Ticket Details")
        dlbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        dv.addWidget(dlbl)
        self._detail = QtWidgets.QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setStyleSheet(
            "QPlainTextEdit{background:white;border:1px solid black;}")
        dv.addWidget(self._detail)
        splitter.addWidget(detail_w)
        splitter.setSizes([420, 150])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        self._build_buttons(br)
        br.addStretch()
        v.addLayout(br)

    def _build_filters(self, _fr):
        """Override to add filter widgets."""

    def _build_buttons(self, _br):
        """Override to add action buttons."""

    def _load_rows(self) -> list:
        """Override to return rows from the DB."""
        return []

    def _refresh(self):
        rows = self._load_rows()
        self._table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._row_ids.append(row["id"])
            self._table.setItem(r, 0, _ro(row.get("ticket_number") or ""))
            self._table.setItem(r, 1, _ro(row.get("requester") or ""))
            self._table.setItem(r, 2, _ro(row.get("department") or ""))
            self._table.setItem(r, 3, _ro(row.get("issue_type") or ""))
            pri = row.get("priority") or "medium"
            self._table.setItem(r, 4, _ro(pri.capitalize()))
            self._table.setItem(r, 5, _ro(row.get("assigned_to") or ""))
            self._table.setItem(
                r, 6, _ro(str(row.get("submitted_date") or "")))
            self._table.setItem(
                r, 7, _ro(str(row.get("due_date") or "")))
            stat = row.get("status") or "open"
            self._table.setItem(
                r, 8, _ro(stat.replace("_", " ").capitalize()))
            bg = QtGui.QColor(_TICKET_COLORS.get(stat, "#ffffff"))
            for col in range(9):
                self._table.item(r, col).setBackground(bg)
            if stat not in ("resolved", "closed"):
                pc = _PRIORITY_COLORS.get(pri)
                if pc:
                    self._table.item(r, 4).setBackground(pc)
        self._selected_id = None
        self._detail.clear()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        tid: int = self._row_ids[row]
        self._selected_id = tid
        conn = _get_db()
        rec = get_ticket(conn, tid)
        conn.close()
        if not rec:
            return
        lines = [
            f"Ticket:      {rec.get('ticket_number') or '—'}",
            f"Requester:   {rec.get('requester') or '—'}"
            f"   Dept: {rec.get('department') or '—'}",
            f"Issue Type:  {rec.get('issue_type') or '—'}"
            f"   Priority: {(rec.get('priority') or '—').capitalize()}",
            f"Assigned To: {rec.get('assigned_to') or '—'}",
            f"Submitted:   {rec.get('submitted_date') or '—'}"
            f"   Due: {rec.get('due_date') or '—'}",
            f"Status:      {(rec.get('status') or '—').replace('_', ' ').capitalize()}",
            "",
            "Description:",
            rec.get("description") or "",
        ]
        if rec.get("notes"):
            lines += ["", "Notes:", rec["notes"]]
        self._detail.setPlainText("\n".join(lines))

    def _on_edit(self, *_):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a ticket first.")
            return
        tid: int = self._selected_id
        dlg = EditTicketDialog(tid, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status: str):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a ticket first.")
            return
        label = new_status.replace("_", " ")
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", f"Set ticket status to '{label}'?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = _get_db()
            set_ticket_status(conn, self._selected_id, new_status)
            conn.commit()
            conn.close()
            self._refresh()


# ---------------------------------------------------------------------------
# Open Tickets (open + in_progress)
# ---------------------------------------------------------------------------

class ITOpenTicketsWidget(_TicketTableWidget):
    def _build_filters(self, fr):
        lbl_p = QtWidgets.QLabel("Priority:")
        lbl_p.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_p)
        self._pri_filter = QtWidgets.QComboBox()
        self._pri_filter.setStyleSheet(COMBO_STYLE)
        self._pri_filter.addItem("(all)", None)
        for s in TICKET_PRIORITIES:
            self._pri_filter.addItem(s.capitalize(), s)
        self._pri_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._pri_filter)

        fr.addSpacing(10)
        lbl_t = QtWidgets.QLabel("Type:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self._type_filter = QtWidgets.QComboBox()
        self._type_filter.setStyleSheet(COMBO_STYLE)
        self._type_filter.addItem("(all)", None)
        for t in ISSUE_TYPES:
            self._type_filter.addItem(t, t)
        self._type_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._type_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self._search = QtWidgets.QLineEdit()
        self._search.setStyleSheet(INPUT_STYLE)
        self._search.setFixedWidth(160)
        self._search.setPlaceholderText("ticket / requester / desc")
        self._search.returnPressed.connect(self._refresh)
        fr.addWidget(self._search)

    def _build_buttons(self, br):
        for text, slot in (
            ("New Ticket",     self._on_add),
            ("Edit",           self._on_edit),
            ("Assign / Start", lambda: self._set_status("in_progress")),
            ("Mark Resolved",  lambda: self._set_status("resolved")),
            ("Close Ticket",   lambda: self._set_status("closed")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)

    def _load_rows(self) -> list:
        pri = self._pri_filter.currentData()
        issue = self._type_filter.currentData()
        term = self._search.text().strip() or None
        conn = _get_db()
        try:
            open_rows = list_tickets(conn, status="open",
                                     priority=pri, search=term)
            prog_rows = list_tickets(conn, status="in_progress",
                                     priority=pri, search=term)
            rows = open_rows + prog_rows
            if issue:
                rows = [r for r in rows if r.get("issue_type") == issue]
            rows.sort(
                key=lambda r: (r.get("submitted_date") or "", r.get("id", 0)),
                reverse=True)
        except Exception:
            rows = []
        conn.close()
        return rows

    def _on_add(self):
        dlg = AddTicketDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()


# ---------------------------------------------------------------------------
# My Assigned Tickets
# ---------------------------------------------------------------------------

class ITMyTicketsWidget(_TicketTableWidget):
    def _build_filters(self, fr):
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self._status_filter = QtWidgets.QComboBox()
        self._status_filter.setStyleSheet(COMBO_STYLE)
        self._status_filter.addItem("Open & In Progress", "_active")
        for s in TICKET_STATUSES:
            self._status_filter.addItem(
                s.replace("_", " ").capitalize(), s)
        self._status_filter.addItem("All", None)
        self._status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._status_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self._search = QtWidgets.QLineEdit()
        self._search.setStyleSheet(INPUT_STYLE)
        self._search.setFixedWidth(160)
        self._search.returnPressed.connect(self._refresh)
        fr.addWidget(self._search)

        b_ref = QtWidgets.QPushButton("Refresh")
        b_ref.setStyleSheet(BUTTON_STYLE)
        b_ref.setFixedHeight(28)
        b_ref.clicked.connect(self._refresh)
        fr.addWidget(b_ref)

        user = _me()
        self._me_label = QtWidgets.QLabel(
            f"Showing tickets assigned to: {user or '(no user)'}  ")
        self._me_label.setStyleSheet("color:white;font-size:11px;")
        fr.addWidget(self._me_label)

    def _build_buttons(self, br):
        for text, slot in (
            ("Edit",          self._on_edit),
            ("Mark In Progress", lambda: self._set_status("in_progress")),
            ("Mark Resolved", lambda: self._set_status("resolved")),
            ("Close Ticket",  lambda: self._set_status("closed")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)

    def _load_rows(self) -> list:
        val = self._status_filter.currentData()
        term = self._search.text().strip() or None
        me = _me()
        conn = _get_db()
        try:
            if val == "_active":
                statuses = ("open", "in_progress")
            elif val is None:
                statuses = None  # type: ignore[assignment]
            else:
                statuses = (val,)
            if statuses:
                rows = []
                for s in statuses:
                    rows += list_tickets(
                        conn, status=s, search=term)
            else:
                rows = list_tickets(conn, search=term)
            if me:
                rows = [r for r in rows
                        if me.lower() in (r.get("assigned_to") or "").lower()]
            rows.sort(
                key=lambda r: (r.get("submitted_date") or "", r.get("id", 0)),
                reverse=True)
        except Exception:
            rows = []
        conn.close()
        return rows


# ---------------------------------------------------------------------------
# Ticket History (resolved / closed)
# ---------------------------------------------------------------------------

class ITTicketHistoryWidget(_TicketTableWidget):
    def _build_filters(self, fr):
        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self._status_filter = QtWidgets.QComboBox()
        self._status_filter.setStyleSheet(COMBO_STYLE)
        self._status_filter.addItem("Resolved & Closed", "_done")
        self._status_filter.addItem("Resolved Only", "resolved")
        self._status_filter.addItem("Closed Only", "closed")
        self._status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._status_filter)

        fr.addSpacing(10)
        lbl_t = QtWidgets.QLabel("Type:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self._type_filter = QtWidgets.QComboBox()
        self._type_filter.setStyleSheet(COMBO_STYLE)
        self._type_filter.addItem("(all)", None)
        for t in ISSUE_TYPES:
            self._type_filter.addItem(t, t)
        self._type_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._type_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self._search = QtWidgets.QLineEdit()
        self._search.setStyleSheet(INPUT_STYLE)
        self._search.setFixedWidth(160)
        self._search.returnPressed.connect(self._refresh)
        fr.addWidget(self._search)

    def _build_buttons(self, br):
        for text, slot in (
            ("Reopen Ticket", lambda: self._set_status("open")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)

    def _load_rows(self) -> list:
        val = self._status_filter.currentData()
        issue = self._type_filter.currentData()
        term = self._search.text().strip() or None
        conn = _get_db()
        try:
            if val == "_done":
                rows = list_tickets(conn, status="resolved", search=term)
                rows += list_tickets(conn, status="closed", search=term)
            else:
                rows = list_tickets(conn, status=val, search=term)
            if issue:
                rows = [r for r in rows if r.get("issue_type") == issue]
            rows.sort(
                key=lambda r: (r.get("submitted_date") or "", r.get("id", 0)),
                reverse=True)
        except Exception:
            rows = []
        conn.close()
        return rows


# ---------------------------------------------------------------------------
# Help Desk container (3 tabs)
# ---------------------------------------------------------------------------

class ITHelpDeskWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(ITOpenTicketsWidget(),   "Open Tickets")
        tabs.addTab(ITMyTicketsWidget(),     "My Assigned Tickets")
        tabs.addTab(ITTicketHistoryWidget(), "Ticket History")
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(tabs)


# ---------------------------------------------------------------------------
# Standalone window
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("IT Help Desk")
    _apply_blue_palette(win)
    central = QtWidgets.QWidget()
    _apply_blue_palette(central)
    win.setCentralWidget(central)
    vl = QtWidgets.QVBoxLayout(central)
    vl.setContentsMargins(8, 8, 8, 8)
    vl.addWidget(ITHelpDeskWidget())
    win.showMaximized()
    sys.exit(app.exec())
