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
from ..it_core import (
    list_tasks, get_task, create_task, update_task, set_task_status,
    next_task_number,
    TASK_STATUSES, TASK_PRIORITIES, TASK_TYPES,
)

TEXT_STYLE = (
    "QPlainTextEdit{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
)

_TASK_COLORS = {
    "pending":     "#ffffff",
    "in_progress": "#fff3cd",
    "on_hold":     "#f8d7da",
    "completed":   "#d4edda",
    "cancelled":   "#dcdcdc",
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

class _TaskDialog(QtWidgets.QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 470)
        _apply_blue_palette(self)
        self.task_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.task_num = QtWidgets.QLineEdit()
        self.task_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Task #:"), self.task_num)

        self.task_name = QtWidgets.QLineEdit()
        self.task_name.setStyleSheet(INPUT_STYLE)
        self.task_name.setPlaceholderText("Short task title (required)")
        layout.addRow(lbl("Task Name:"), self.task_name)

        self.task_type = QtWidgets.QComboBox()
        self.task_type.setStyleSheet(COMBO_STYLE)
        for t in TASK_TYPES:
            self.task_type.addItem(t, t)
        layout.addRow(lbl("Task Type:"), self.task_type)

        self.description = QtWidgets.QPlainTextEdit()
        self.description.setStyleSheet(TEXT_STYLE)
        self.description.setFixedHeight(80)
        self.description.setPlaceholderText("Describe what needs to be done")
        layout.addRow(lbl("Description:"), self.description)

        self.priority_combo = QtWidgets.QComboBox()
        self.priority_combo.setStyleSheet(COMBO_STYLE)
        for s in TASK_PRIORITIES:
            self.priority_combo.addItem(s.capitalize(), s)
        self.priority_combo.setCurrentIndex(1)
        layout.addRow(lbl("Priority:"), self.priority_combo)

        self.assigned_to = QtWidgets.QLineEdit()
        self.assigned_to.setStyleSheet(INPUT_STYLE)
        self.assigned_to.setPlaceholderText("Assigned technician")
        layout.addRow(lbl("Assigned To:"), self.assigned_to)

        self.department = QtWidgets.QLineEdit()
        self.department.setStyleSheet(INPUT_STYLE)
        self.department.setPlaceholderText("Department this task is for")
        layout.addRow(lbl("Department:"), self.department)

        self.scheduled_date = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(_date.today().isoformat(), "yyyy-MM-dd"))
        self.scheduled_date.setCalendarPopup(True)
        self.scheduled_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Scheduled:"), self.scheduled_date)

        self.due_date = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(_date.today().isoformat(),
                                    "yyyy-MM-dd").addDays(7))
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
        self.task_num.setText(rec.get("task_number") or "")
        self.task_name.setText(rec.get("task_name") or "")
        idx = self.task_type.findData(rec.get("task_type"))
        if idx >= 0:
            self.task_type.setCurrentIndex(idx)
        self.description.setPlainText(rec.get("description") or "")
        idx = self.priority_combo.findData(rec.get("priority"))
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)
        self.assigned_to.setText(rec.get("assigned_to") or "")
        self.department.setText(rec.get("department") or "")
        for field, widget in (
            ("scheduled_date", self.scheduled_date),
            ("due_date",       self.due_date),
        ):
            d = rec.get(field)
            if d:
                widget.setDate(
                    QtCore.QDate.fromString(str(d), "yyyy-MM-dd"))
        self.notes.setText(rec.get("notes") or "")

    def _on_ok(self):
        if not self.task_name.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Task name is required.")
            return
        self._save()

    def _save(self):
        raise NotImplementedError


class AddTaskDialog(_TaskDialog):
    def __init__(self, parent=None):
        super().__init__("New IT Task", parent)
        conn = _get_db()
        num = next_task_number(conn)
        conn.close()
        self.task_num.setText(num)
        self.task_num.setReadOnly(True)

    def _save(self):
        conn = _get_db()
        try:
            self.task_id = create_task(
                conn,
                task_number=self.task_num.text().strip(),
                task_name=self.task_name.text().strip(),
                task_type=self.task_type.currentData(),
                description=self.description.toPlainText().strip(),
                assigned_to=self.assigned_to.text().strip(),
                department=self.department.text().strip(),
                priority=self.priority_combo.currentData(),
                scheduled_date=self.scheduled_date.date().toString(
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


class EditTaskDialog(_TaskDialog):
    def __init__(self, task_id: int, parent=None):
        super().__init__("Edit Task", parent)
        self._edit_id: int = task_id
        self.task_id = task_id
        self.task_num.setReadOnly(True)
        conn = _get_db()
        rec = get_task(conn, task_id)
        conn.close()
        if rec:
            self._populate(rec)

    def _save(self):
        conn = _get_db()
        try:
            update_task(
                conn, self._edit_id,
                task_name=self.task_name.text().strip(),
                task_type=self.task_type.currentData(),
                description=self.description.toPlainText().strip(),
                assigned_to=self.assigned_to.text().strip(),
                department=self.department.text().strip(),
                priority=self.priority_combo.currentData(),
                scheduled_date=self.scheduled_date.date().toString(
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
# Main tasks widget
# ---------------------------------------------------------------------------

class ITTasksDesktopWidget(QtWidgets.QWidget):
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

        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self._status_filter = QtWidgets.QComboBox()
        self._status_filter.setStyleSheet(COMBO_STYLE)
        self._status_filter.addItem("Pending & In Progress", "_active")
        for s in TASK_STATUSES:
            self._status_filter.addItem(
                s.replace("_", " ").capitalize(), s)
        self._status_filter.addItem("All", None)
        self._status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._status_filter)

        fr.addSpacing(10)
        lbl_p = QtWidgets.QLabel("Priority:")
        lbl_p.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_p)
        self._pri_filter = QtWidgets.QComboBox()
        self._pri_filter.setStyleSheet(COMBO_STYLE)
        self._pri_filter.addItem("(all)", None)
        for s in TASK_PRIORITIES:
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
        for t in TASK_TYPES:
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
        self._search.setPlaceholderText("task / assignee / desc")
        self._search.returnPressed.connect(self._refresh)
        fr.addWidget(self._search)
        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self._table = QtWidgets.QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            "Task #", "Task Name", "Type", "Priority",
            "Assigned To", "Department", "Due Date", "Status",
        ])
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6, 7):
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
        dlbl = QtWidgets.QLabel("Task Details")
        dlbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        dv.addWidget(dlbl)
        self._detail = QtWidgets.QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setStyleSheet(
            "QPlainTextEdit{background:white;border:1px solid black;}")
        dv.addWidget(self._detail)
        splitter.addWidget(detail_w)
        splitter.setSizes([440, 160])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Task",      self._on_add),
            ("Edit Task",     self._on_edit),
            ("Start Task",    lambda: self._set_status("in_progress")),
            ("Put On Hold",   lambda: self._set_status("on_hold")),
            ("Mark Complete", lambda: self._set_status("completed")),
            ("Cancel Task",   lambda: self._set_status("cancelled")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        val = self._status_filter.currentData()
        priority = self._pri_filter.currentData()
        task_type = self._type_filter.currentData()
        term = self._search.text().strip() or None

        conn = _get_db()
        try:
            if val == "_active":
                rows = list_tasks(conn, status=("pending", "in_progress"),
                                  priority=priority, task_type=task_type,
                                  search=term)
            else:
                rows = list_tasks(conn, status=val, priority=priority,
                                  task_type=task_type, search=term)
        except Exception:
            rows = []
        conn.close()

        self._table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._row_ids.append(row["id"])
            self._table.setItem(r, 0, _ro(row.get("task_number") or ""))
            self._table.setItem(r, 1, _ro(row.get("task_name") or ""))
            self._table.setItem(r, 2, _ro(row.get("task_type") or ""))
            pri = row.get("priority") or "medium"
            self._table.setItem(r, 3, _ro(pri.capitalize()))
            self._table.setItem(r, 4, _ro(row.get("assigned_to") or ""))
            self._table.setItem(r, 5, _ro(row.get("department") or ""))
            self._table.setItem(
                r, 6, _ro(str(row.get("due_date") or "")))
            stat = row.get("status") or "pending"
            self._table.setItem(
                r, 7, _ro(stat.replace("_", " ").capitalize()))
            bg = QtGui.QColor(_TASK_COLORS.get(stat, "#ffffff"))
            for col in range(8):
                self._table.item(r, col).setBackground(bg)
            if stat not in ("completed", "cancelled"):
                pc = _PRIORITY_COLORS.get(pri)
                if pc:
                    self._table.item(r, 3).setBackground(pc)
        self._selected_id = None
        self._detail.clear()

    def _on_show_all(self):
        self._search.clear()
        self._status_filter.blockSignals(True)
        self._status_filter.setCurrentIndex(
            self._status_filter.count() - 1)
        self._status_filter.blockSignals(False)
        self._pri_filter.blockSignals(True)
        self._pri_filter.setCurrentIndex(0)
        self._pri_filter.blockSignals(False)
        self._type_filter.blockSignals(True)
        self._type_filter.setCurrentIndex(0)
        self._type_filter.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        tid: int = self._row_ids[row]
        self._selected_id = tid
        conn = _get_db()
        rec = get_task(conn, tid)
        conn.close()
        if not rec:
            return
        lines = [
            f"Task #:      {rec.get('task_number') or '—'}"
            f"  —  {rec.get('task_name') or '—'}",
            f"Type:        {rec.get('task_type') or '—'}"
            f"   Priority: {(rec.get('priority') or '—').capitalize()}",
            f"Assigned To: {rec.get('assigned_to') or '—'}"
            f"   Dept: {rec.get('department') or '—'}",
            f"Scheduled:   {rec.get('scheduled_date') or '—'}"
            f"   Due: {rec.get('due_date') or '—'}",
            f"Status:      {(rec.get('status') or '—').replace('_', ' ').capitalize()}",
        ]
        if rec.get("completed_date"):
            lines.append(f"Completed:   {rec['completed_date']}")
        if rec.get("description"):
            lines += ["", "Description:", rec["description"]]
        if rec.get("notes"):
            lines += ["", "Notes:", rec["notes"]]
        self._detail.setPlainText("\n".join(lines))

    def _on_add(self):
        dlg = AddTaskDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, *_):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a task first.")
            return
        tid: int = self._selected_id
        dlg = EditTaskDialog(tid, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status: str):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a task first.")
            return
        label = new_status.replace("_", " ")
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", f"Set task status to '{label}'?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = _get_db()
            set_task_status(conn, self._selected_id, new_status)
            conn.commit()
            conn.close()
            self._refresh()


# ---------------------------------------------------------------------------
# Standalone window
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("IT Tasks")
    _apply_blue_palette(win)
    central = QtWidgets.QWidget()
    _apply_blue_palette(central)
    win.setCentralWidget(central)
    vl = QtWidgets.QVBoxLayout(central)
    vl.setContentsMargins(8, 8, 8, 8)
    vl.addWidget(ITTasksDesktopWidget())
    win.showMaximized()
    sys.exit(app.exec())
