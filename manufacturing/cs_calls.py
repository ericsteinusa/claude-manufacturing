import sys
import psycopg2
import psycopg2.extras
from .db_connection import get_db_connection
import os
import csv
from datetime import datetime
from PyQt6 import QtCore, QtGui, QtWidgets


BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE = "QLineEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
COMBO_STYLE = "QComboBox{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}QComboBox QAbstractItemView{background-color:white;}"
DATE_STYLE = "QDateEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 4px;}"
TIME_STYLE = "QTimeEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 4px;}"
TEXT_STYLE = "QTextEdit{background-color:white;border:2px solid black;border-radius:4px;padding:2px 6px;}"
LABEL_STYLE = "color:white;font-size:13px;"
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white; border:2px solid black; padding:6px 18px;"
    " border-bottom:none; border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255); font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)
NOTE_BROWSER_STYLE = (
    "QTextBrowser{background-color:white;border:2px solid black;"
    "border-radius:4px;padding:4px 6px;font-family:monospace;font-size:12px;}"
)

STATUS_COLORS = {
    0: QtGui.QColor(255, 243, 205),   # open — yellow tint
    1: QtGui.QColor(212, 237, 218),   # completed — green tint
}


def get_db():
    conn = get_db_connection()
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer (
            id           SERIAL PRIMARY KEY,
            first_name   TEXT,
            last_name    TEXT,
            company_name TEXT,
            phone_number TEXT,
            address      TEXT,
            city         TEXT,
            state        TEXT,
            zip_code     TEXT,
            email        TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calls2 (
            id              SERIAL PRIMARY KEY,
            customer_id     INTEGER REFERENCES customer(id),
            call            TEXT NOT NULL,
            call_date       TEXT NOT NULL,
            call_time       TEXT NOT NULL,
            completion_date TEXT,
            completion_time TEXT,
            comments_box    TEXT,
            completion_box  INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS call_notes (
            id         SERIAL PRIMARY KEY,
            call_id    INTEGER NOT NULL REFERENCES calls2(id) ON DELETE CASCADE,
            note_text  TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _apply_blue_palette(widget):
    pal = widget.palette()
    for g in (QtGui.QPalette.ColorGroup.Active,
              QtGui.QPalette.ColorGroup.Inactive,
              QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(g, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(g, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _ro(text, align=QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter):
    item = QtWidgets.QTableWidgetItem(str(text))
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(align)
    return item


def _customer_display(row):
    company = (row["company_name"] or "").strip()
    contact = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
    return company if company else contact


class CustomerServiceCallsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._row_ids = []
        self._current_id = None
        self._build_ui()
        self._refresh_customer_combo()
        self._load_calls()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        # ── Filter bar ─────────────────────────────────────────────────────
        fr = QtWidgets.QHBoxLayout()
        fr.setSpacing(8)

        def fl(t):
            lbl = QtWidgets.QLabel(t)
            lbl.setStyleSheet(LABEL_STYLE)
            return lbl

        self.filter_cust = QtWidgets.QComboBox()
        self.filter_cust.setStyleSheet(COMBO_STYLE)
        self.filter_cust.setMinimumWidth(180)

        self.filter_status = QtWidgets.QComboBox()
        self.filter_status.setStyleSheet(COMBO_STYLE)
        self.filter_status.addItems(["(all)", "Open", "Completed"])

        self.filter_from = QtWidgets.QDateEdit()
        self.filter_from.setStyleSheet(DATE_STYLE)
        self.filter_from.setCalendarPopup(True)
        self.filter_from.setDisplayFormat("MM/dd/yyyy")
        self.filter_from.setDate(QtCore.QDate.currentDate().addDays(-90))

        self.filter_to = QtWidgets.QDateEdit()
        self.filter_to.setStyleSheet(DATE_STYLE)
        self.filter_to.setCalendarPopup(True)
        self.filter_to.setDisplayFormat("MM/dd/yyyy")
        self.filter_to.setDate(QtCore.QDate.currentDate())

        self.filter_search = QtWidgets.QLineEdit()
        self.filter_search.setStyleSheet(INPUT_STYLE)
        self.filter_search.setPlaceholderText("Search call / comments...")
        self.filter_search.setMinimumWidth(180)
        self.filter_search.returnPressed.connect(self._load_calls)

        fr.addWidget(fl("Customer:"))
        fr.addWidget(self.filter_cust)
        fr.addWidget(fl("Status:"))
        fr.addWidget(self.filter_status)
        fr.addWidget(fl("From:"))
        fr.addWidget(self.filter_from)
        fr.addWidget(fl("To:"))
        fr.addWidget(self.filter_to)
        fr.addWidget(fl("Search:"))
        fr.addWidget(self.filter_search)
        for t, fn in (("Apply", self._load_calls), ("Show All", self._show_all)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(30)
            b.clicked.connect(fn)
            fr.addWidget(b)
        fr.addStretch()
        outer.addLayout(fr)

        # ── Call table ─────────────────────────────────────────────────────
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Customer", "Problem / Call", "Call Date", "Call Time",
            "Completion Date", "Completion Time", "Comments", "Status"
        ])
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c in (2, 3, 4, 5, 7):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.clicked.connect(self._on_row_clicked)
        outer.addWidget(self.table, stretch=1)

        # ── Entry form ─────────────────────────────────────────────────────
        form_grp = QtWidgets.QGroupBox("Call Record")
        form_grp.setStyleSheet(
            "QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;}")
        grid = QtWidgets.QGridLayout(form_grp)
        grid.setSpacing(6)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.ef_cust = QtWidgets.QComboBox()
        self.ef_cust.setStyleSheet(COMBO_STYLE)
        self.ef_cust.setMinimumWidth(200)

        self.ef_call_date = QtWidgets.QDateEdit()
        self.ef_call_date.setStyleSheet(DATE_STYLE)
        self.ef_call_date.setCalendarPopup(True)
        self.ef_call_date.setDisplayFormat("MM/dd/yyyy")
        self.ef_call_date.setDate(QtCore.QDate.currentDate())

        self.ef_call_time = QtWidgets.QTimeEdit()
        self.ef_call_time.setStyleSheet(TIME_STYLE)
        self.ef_call_time.setDisplayFormat("hh:mm AP")
        self.ef_call_time.setTime(QtCore.QTime.currentTime())

        self.ef_comp_date = QtWidgets.QDateEdit()
        self.ef_comp_date.setStyleSheet(DATE_STYLE)
        self.ef_comp_date.setCalendarPopup(True)
        self.ef_comp_date.setDisplayFormat("MM/dd/yyyy")
        self.ef_comp_date.setDate(QtCore.QDate.currentDate())

        self.ef_comp_time = QtWidgets.QTimeEdit()
        self.ef_comp_time.setStyleSheet(TIME_STYLE)
        self.ef_comp_time.setDisplayFormat("hh:mm AP")
        self.ef_comp_time.setTime(QtCore.QTime.currentTime())

        self.ef_completed = QtWidgets.QCheckBox("Completed")
        self.ef_completed.setStyleSheet("color:white;font-size:13px;")

        self.ef_call = QtWidgets.QTextEdit()
        self.ef_call.setStyleSheet(TEXT_STYLE)
        self.ef_call.setFixedHeight(55)
        self.ef_call.setPlaceholderText("Describe the problem / reason for call...")

        self.ef_comments = QtWidgets.QTextEdit()
        self.ef_comments.setStyleSheet(TEXT_STYLE)
        self.ef_comments.setFixedHeight(55)
        self.ef_comments.setPlaceholderText("Comments / resolution notes...")

        grid.addWidget(lbl("Customer:"), 0, 0)
        grid.addWidget(self.ef_cust, 0, 1)
        grid.addWidget(lbl("Call Date:"), 0, 2)
        grid.addWidget(self.ef_call_date, 0, 3)
        grid.addWidget(lbl("Call Time:"), 0, 4)
        grid.addWidget(self.ef_call_time, 0, 5)
        grid.addWidget(self.ef_completed, 0, 6)
        grid.addWidget(lbl("Completion Date:"), 1, 2)
        grid.addWidget(self.ef_comp_date, 1, 3)
        grid.addWidget(lbl("Completion Time:"), 1, 4)
        grid.addWidget(self.ef_comp_time, 1, 5)
        grid.addWidget(lbl("Problem / Call:"), 2, 0)
        grid.addWidget(self.ef_call, 2, 1, 1, 3)
        grid.addWidget(lbl("Comments:"), 2, 4)
        grid.addWidget(self.ef_comments, 2, 5, 1, 2)
        outer.addWidget(form_grp)

        # ── Notes / History panel ──────────────────────────────────────────
        notes_grp = QtWidgets.QGroupBox("Notes & History")
        notes_grp.setStyleSheet(
            "QGroupBox{color:white;font-weight:bold;border:1px solid white;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;}")
        notes_layout = QtWidgets.QVBoxLayout(notes_grp)
        notes_layout.setSpacing(4)

        self.notes_browser = QtWidgets.QTextBrowser()
        self.notes_browser.setStyleSheet(NOTE_BROWSER_STYLE)
        self.notes_browser.setFixedHeight(90)
        self.notes_browser.setPlaceholderText("Select a call to view its note history.")
        notes_layout.addWidget(self.notes_browser)

        note_input_row = QtWidgets.QHBoxLayout()
        self.note_input = QtWidgets.QLineEdit()
        self.note_input.setStyleSheet(INPUT_STYLE)
        self.note_input.setPlaceholderText("Type a note and click Add Note (requires a saved call selected above)...")
        self.note_input.returnPressed.connect(self._on_add_note)
        note_input_row.addWidget(self.note_input)

        btn_add_note = QtWidgets.QPushButton("Add Note")
        btn_add_note.setStyleSheet(BUTTON_STYLE)
        btn_add_note.setFixedHeight(30)
        btn_add_note.setFixedWidth(100)
        btn_add_note.clicked.connect(self._on_add_note)
        note_input_row.addWidget(btn_add_note)
        notes_layout.addLayout(note_input_row)
        outer.addWidget(notes_grp)

        # ── Action buttons ─────────────────────────────────────────────────
        br = QtWidgets.QHBoxLayout()
        for t, fn in (("Add New", self._on_add), ("Update Selected", self._on_update),
                      ("Mark Complete", self._on_mark_complete),
                      ("Delete Selected", self._on_delete),
                      ("Export CSV", self._on_export),
                      ("Clear", self._clear_form)):
            b = QtWidgets.QPushButton(t)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(34)
            b.clicked.connect(fn)
            br.addWidget(b)
        br.addStretch()
        outer.addLayout(br)

    # ── Data helpers ───────────────────────────────────────────────────────

    def _refresh_customer_combo(self):
        conn = get_db()
        customers = conn.execute(
            "SELECT id, first_name, last_name, company_name FROM customer "
            "ORDER BY company_name, last_name, first_name"
        ).fetchall()
        conn.close()

        for combo in (self.filter_cust, self.ef_cust):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(all customers)" if combo is self.filter_cust else "-- select --", None)
            for c in customers:
                combo.addItem(_customer_display(c), c["id"])
            combo.blockSignals(False)

    def _load_calls(self):
        cid = self.filter_cust.currentData()
        status = self.filter_status.currentText()
        from_s = self.filter_from.date().toString("yyyy-MM-dd")
        to_s = self.filter_to.date().toString("yyyy-MM-dd")
        keyword = self.filter_search.text().strip()

        conn = get_db()
        q = (
            "SELECT c2.id, c2.customer_id, cu.first_name, cu.last_name, cu.company_name, "
            "c2.call, c2.call_date, c2.call_time, c2.completion_date, c2.completion_time, "
            "c2.comments_box, c2.completion_box "
            "FROM calls2 c2 LEFT JOIN customer cu ON cu.id = c2.customer_id "
            "WHERE c2.call_date BETWEEN %s AND %s"
        )
        params = [from_s, to_s]
        if cid:
            q += " AND c2.customer_id = %s"
            params.append(cid)
        if status == "Open":
            q += " AND c2.completion_box = 0"
        elif status == "Completed":
            q += " AND c2.completion_box = 1"
        if keyword:
            q += " AND (c2.call LIKE %s OR c2.comments_box LIKE %s)"
            params += [f"%{keyword}%", f"%{keyword}%"]
        q += " ORDER BY c2.call_date DESC, c2.call_time DESC"
        rows = conn.execute(q, params).fetchall()
        conn.close()

        self.table.setRowCount(0)
        self._row_ids = []
        center = QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter

        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._row_ids.append(row["id"])
            completed = int(row["completion_box"])
            color = STATUS_COLORS.get(completed, QtGui.QColor(255, 255, 255))
            cust_name = _customer_display(row) if row["first_name"] or row["company_name"] else "(no customer)"
            status_str = "Completed" if completed else "Open"
            for c, (val, algn) in enumerate([
                (cust_name, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["call"] or "", QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (row["call_date"] or "", center),
                (row["call_time"] or "", center),
                (row["completion_date"] or "", center),
                (row["completion_time"] or "", center),
                (row["comments_box"] or "", QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                (status_str, center),
            ]):
                item = _ro(val, algn)
                item.setBackground(color)
                self.table.setItem(r, c, item)


    def _show_all(self):
        self.filter_cust.setCurrentIndex(0)
        self.filter_status.setCurrentIndex(0)
        self.filter_from.setDate(QtCore.QDate(2000, 1, 1))
        self.filter_to.setDate(QtCore.QDate.currentDate())
        self.filter_search.clear()
        self._load_calls()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        self._current_id = self._row_ids[row]
        conn = get_db()
        rec = conn.execute("SELECT * FROM calls2 WHERE id=%s", (self._current_id,)).fetchone()
        conn.close()
        if not rec:
            return

        idx = self.ef_cust.findData(rec["customer_id"])
        self.ef_cust.setCurrentIndex(idx if idx >= 0 else 0)

        for date_edit, val in ((self.ef_call_date, rec["call_date"]),
                               (self.ef_comp_date, rec["completion_date"])):
            if val:
                try:
                    parts = val.split("-")
                    date_edit.setDate(QtCore.QDate(int(parts[0]), int(parts[1]), int(parts[2])))
                except (ValueError, IndexError):
                    date_edit.setDate(QtCore.QDate.currentDate())

        for time_edit, val in ((self.ef_call_time, rec["call_time"]),
                               (self.ef_comp_time, rec["completion_time"])):
            if val:
                t = QtCore.QTime.fromString(val, "hh:mm")
                if t.isValid():
                    time_edit.setTime(t)

        self.ef_call.setPlainText(rec["call"] or "")
        self.ef_comments.setPlainText(rec["comments_box"] or "")
        self.ef_completed.setChecked(bool(rec["completion_box"]))
        self._load_notes()

    def _collect_form(self):
        call_text = self.ef_call.toPlainText().strip()
        if not call_text:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Problem / Call description is required.")
            return None
        return {
            "customer_id": self.ef_cust.currentData(),
            "call": call_text,
            "call_date": self.ef_call_date.date().toString("yyyy-MM-dd"),
            "call_time": self.ef_call_time.time().toString("hh:mm"),
            "completion_date": self.ef_comp_date.date().toString("yyyy-MM-dd"),
            "completion_time": self.ef_comp_time.time().toString("hh:mm"),
            "comments_box": self.ef_comments.toPlainText().strip() or None,
            "completion_box": 1 if self.ef_completed.isChecked() else 0,
        }

    def _on_add(self):
        data = self._collect_form()
        if not data:
            return
        conn = get_db()
        conn.execute("""
            INSERT INTO calls2 (customer_id, call, call_date, call_time,
                                completion_date, completion_time, comments_box, completion_box)
            VALUES (:customer_id, :call, :call_date, :call_time,
                    :completion_date, :completion_time, :comments_box, :completion_box)
        """, data)
        conn.commit()
        conn.close()
        self._clear_form()
        self._load_calls()

    def _on_update(self):
        if self._current_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a call first.")
            return
        data = self._collect_form()
        if not data:
            return
        data["id"] = self._current_id
        conn = get_db()
        conn.execute("""
            UPDATE calls2 SET customer_id=:customer_id, call=:call, call_date=:call_date,
                call_time=:call_time, completion_date=:completion_date,
                completion_time=:completion_time, comments_box=:comments_box,
                completion_box=:completion_box
            WHERE id=:id
        """, data)
        conn.commit()
        conn.close()
        self._load_calls()

    def _on_mark_complete(self):
        if self._current_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a call first.")
            return
        now_date = QtCore.QDate.currentDate().toString("yyyy-MM-dd")
        now_time = QtCore.QTime.currentTime().toString("hh:mm")
        conn = get_db()
        conn.execute("""
            UPDATE calls2 SET completion_box=1, completion_date=%s, completion_time=%s
            WHERE id=%s
        """, (now_date, now_time, self._current_id))
        conn.execute("""
            INSERT INTO call_notes (call_id, note_text, created_at)
            VALUES (%s, %s, %s)
        """, (self._current_id, "Call marked as completed.", f"{now_date} {now_time}"))
        conn.commit()
        conn.close()
        self._clear_form()
        self._load_calls()

    def _on_delete(self):
        if self._current_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a call first.")
            return
        if (QtWidgets.QMessageBox.question(
                self, "Confirm Delete", "Delete this call record and all its notes%s",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                == QtWidgets.QMessageBox.StandardButton.Yes):
            conn = get_db()
            conn.execute("DELETE FROM call_notes WHERE call_id=%s", (self._current_id,))
            conn.execute("DELETE FROM calls2 WHERE id=%s", (self._current_id,))
            conn.commit()
            conn.close()
            self._clear_form()
            self._load_calls()

    # ── Notes threading ────────────────────────────────────────────────────

    def _load_notes(self):
        if self._current_id is None:
            self.notes_browser.clear()
            return
        conn = get_db()
        notes = conn.execute(
            "SELECT note_text, created_at FROM call_notes WHERE call_id=%s ORDER BY created_at ASC",
            (self._current_id,)
        ).fetchall()
        conn.close()

        if not notes:
            self.notes_browser.setPlainText("No notes yet for this call.")
            return

        lines = []
        for n in notes:
            ts = n["created_at"]
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M")
                ts = dt.strftime("%m/%d/%Y %I:%M %p")
            except ValueError:
                pass
            lines.append(f"[{ts}]  {n['note_text']}")
        self.notes_browser.setPlainText("\n".join(lines))
        # Scroll to bottom so newest note is visible
        sb = self.notes_browser.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_add_note(self):
        if self._current_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection",
                                          "Select a saved call record before adding a note.")
            return
        text = self.note_input.text().strip()
        if not text:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = get_db()
        conn.execute(
            "INSERT INTO call_notes (call_id, note_text, created_at) VALUES (%s, %s, %s)",
            (self._current_id, text, now)
        )
        conn.commit()
        conn.close()
        self.note_input.clear()
        self._load_notes()

    # ── Export CSV ─────────────────────────────────────────────────────────

    def _on_export(self):
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Export", "No records to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export to CSV", "cs_calls_export.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        headers = [self.table.horizontalHeaderItem(c).text()
                   for c in range(self.table.columnCount())]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in range(self.table.rowCount()):
                writer.writerow([
                    self.table.item(r, c).text() if self.table.item(r, c) else ""
                    for c in range(self.table.columnCount())
                ])
        QtWidgets.QMessageBox.information(self, "Export Complete", f"Saved to:\n{path}")

    # ── Clear form ─────────────────────────────────────────────────────────

    def _clear_form(self):
        self._current_id = None
        self.ef_cust.setCurrentIndex(0)
        self.ef_call_date.setDate(QtCore.QDate.currentDate())
        self.ef_call_time.setTime(QtCore.QTime.currentTime())
        self.ef_comp_date.setDate(QtCore.QDate.currentDate())
        self.ef_comp_time.setTime(QtCore.QTime.currentTime())
        self.ef_call.clear()
        self.ef_comments.clear()
        self.ef_completed.setChecked(False)
        self.note_input.clear()
        self.notes_browser.clear()
        self.table.clearSelection()


class CustomerServiceCalls(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Customer Service Calls")
        self.resize(1200, 820)
        _apply_blue_palette(self)
        self.setCentralWidget(CustomerServiceCallsWidget())


def main():
    init_db()
    app = QtWidgets.QApplication(sys.argv)
    window = CustomerServiceCalls()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
