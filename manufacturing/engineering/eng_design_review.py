import sys
import psycopg2
from ..db_pg import get_db
from ..accounts import get_current_user_email
from PyQt6 import QtCore, QtGui, QtWidgets
from ..qt_theme import (
    BUTTON_STYLE, apply_blue_palette as _apply_blue_palette, ro as _ro
)


INPUT_STYLE = (
    "QLineEdit{background-color:white;border:2px solid "
    "black;border-radius:4px;padding:2px 6px;}"
)
COMBO_STYLE = (
    "QComboBox{background-color:white;border:2px solid "
    "black;border-radius:4px;padding:2px 6px;}"
    "QComboBox QAbstractItemView{background-color:white;}"
)
TEXT_STYLE = (
    "QPlainTextEdit{background-color:white;border:2px solid "
    "black;border-radius:4px;padding:2px 6px;}"
)
LABEL_STYLE = "color:white;font-size:13px;"

ECR_STATUSES = ("draft", "pending", "approved", "rejected", "revision_needed")

ECR_COLORS = {
    "draft": "#e8f4fd",
    "pending": "#fff3cd",
    "approved": "#d4edda",
    "rejected": "#f8d7da",
    "revision_needed": "#ffe8c0",
}


def _next_ecr_num():
    yr = QtCore.QDate.currentDate().year()
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM eng_design_review WHERE ecr_number LIKE %s",
        (f"ECR-{yr}-%",)
    ).fetchone()[0]
    conn.close()
    return f"ECR-{yr}-{count + 1:04d}"


class NewECRDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Design Review / ECR")
        self.resize(520, 460)
        _apply_blue_palette(self)
        self.ecr_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            widget = QtWidgets.QLabel(t)
            widget.setStyleSheet(LABEL_STYLE)
            return widget

        self.ecr_num = QtWidgets.QLineEdit(_next_ecr_num())
        self.ecr_num.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("ECR #:"), self.ecr_num)

        self.title = QtWidgets.QLineEdit()
        self.title.setStyleSheet(INPUT_STYLE)
        self.title.setPlaceholderText("Design review title (required)")
        layout.addRow(lbl("Title:"), self.title)

        self.project_combo = QtWidgets.QComboBox()
        self.project_combo.setStyleSheet(COMBO_STYLE)
        self.project_combo.addItem("(no project)", None)
        conn = get_db()
        projects = conn.execute(
            "SELECT id, project_number, title FROM eng_project ORDER BY "
            "project_number"
        ).fetchall()
        conn.close()
        for p in projects:
            self.project_combo.addItem(
                f"{p['project_number']} — {p['title']}", p["id"])
        layout.addRow(lbl("Project:"), self.project_combo)

        self.requested_by = QtWidgets.QLineEdit()
        self.requested_by.setStyleSheet(INPUT_STYLE)
        self.requested_by.setPlaceholderText("Requested by")
        layout.addRow(lbl("Requested By:"), self.requested_by)

        self.review_date = QtWidgets.QDateEdit(
            QtCore.QDate.currentDate().addDays(7))
        self.review_date.setCalendarPopup(True)
        self.review_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Review Date:"), self.review_date)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ECR_STATUSES:
            self.status_combo.addItem(s.replace("_", " ").capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setStyleSheet(TEXT_STYLE)
        self.notes.setPlaceholderText("Notes / change description")
        self.notes.setFixedHeight(100)
        layout.addRow(lbl("Notes:"), self.notes)

        created_by_lbl = QtWidgets.QLabel(get_current_user_email() or "(unknown)")  # noqa: E501
        created_by_lbl.setStyleSheet(LABEL_STYLE)
        layout.addRow(lbl("Created by:"), created_by_lbl)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        num = self.ecr_num.text().strip()
        title = self.title.text().strip()
        if not num or not title:
            QtWidgets.QMessageBox.warning(self, "Input Error",
                                          "ECR number and title are required.")
            return
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO eng_design_review"
                " (ecr_number, title, project_id, requested_by, review_date, "
                "status, notes, created_by)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (num, title,
                 self.project_combo.currentData(),
                 self.requested_by.text().strip(),
                 self.review_date.date().toString("yyyy-MM-dd"),
                 self.status_combo.currentData(),
                 self.notes.toPlainText().strip(),
                 get_current_user_email() or None)
            )
            self.ecr_id = cur.fetchone()['id']
            conn.commit()
        except psycopg2.IntegrityError:
            QtWidgets.QMessageBox.warning(self, "Duplicate",
                                          f"ECR number '{num}' already exists.")  # noqa: E501
            conn.close()
            return
        conn.close()
        self.accept()


# ── Embeddable widget (used standalone and embedded in eng_mgr) ─────────

class DesignReviewWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._row_ids = []
        self._selected_id = None
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
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.setStyleSheet(COMBO_STYLE)
        self.status_filter.addItem("Open (Draft & Pending)", "open")
        self.status_filter.addItem("Draft", "draft")
        self.status_filter.addItem("Pending", "pending")
        self.status_filter.addItem("Approved", "approved")
        self.status_filter.addItem("Rejected", "rejected")
        self.status_filter.addItem("Revision Needed", "revision_needed")
        self.status_filter.addItem("All", None)
        self.status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self.status_filter)
        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self.search = QtWidgets.QLineEdit()
        self.search.setStyleSheet(INPUT_STYLE)
        self.search.setFixedWidth(160)
        self.search.returnPressed.connect(self._refresh)
        fr.addWidget(self.search)
        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["ECR #", "Title", "Project", "Requested By", "Review Date",
             "Status", "Created By"]  # noqa: E501
        )
        hh = self.table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(
    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6):
            hh.setSectionResizeMode(
    col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(
    QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
    QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
    QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.clicked.connect(self._on_row_clicked)
        splitter.addWidget(self.table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Notes for Selected Design Review")
        dlbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        dv.addWidget(dlbl)
        self.detail_text = QtWidgets.QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet(
            "QPlainTextEdit{background-color:white;border:1px solid black;}")
        dv.addWidget(self.detail_text)
        splitter.addWidget(detail_w)
        splitter.setSizes([440, 160])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New ECR", self._on_new),
            ("Submit for Review", lambda: self._set_status(
                "pending", "Submit for review%s")),
            ("Approve", lambda: self._set_status(
                "approved", "Approve this design review%s")),
            ("Request Revision", lambda: self._set_status(
                "revision_needed", "Request revision%s")),
            ("Reject", lambda: self._set_status(
                "rejected", "Reject this design review%s")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        status_val = self.status_filter.currentData()
        term = self.search.text().strip()
        conds, params = [], []
        if status_val == "open":
            conds.append("d.status IN ('draft','pending')")
        elif status_val:
            conds.append("d.status = %s")
            params.append(status_val)
        if term:
            conds.append(
                "(d.ecr_number LIKE %s OR d.title LIKE %s OR d.requested_by "
                "LIKE %s)")
            params += [f"%{term}%"] * 3
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        conn = get_db()
        rows = conn.execute(
            "SELECT d.*, p.project_number, p.title as proj_title"
            " FROM eng_design_review d LEFT JOIN eng_project p ON "
            "d.project_id = p.id"
            + where + " ORDER BY d.review_date, d.ecr_number", params
        ).fetchall()
        conn.close()
        self.table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._row_ids.append(row["id"])
            proj_str = row["project_number"] if row["project_number"] else "—"
            self.table.setItem(r, 0, _ro(row["ecr_number"]))
            self.table.setItem(r, 1, _ro(row["title"]))
            self.table.setItem(r, 2, _ro(proj_str))
            self.table.setItem(r, 3, _ro(row["requested_by"] or ""))
            self.table.setItem(r, 4, _ro(row["review_date"] or ""))
            self.table.setItem(
    r, 5, _ro(
        row["status"].replace(
            "_", " ").capitalize()))
            self.table.setItem(r, 6, _ro(row["created_by"] or ""))
            bg = QtGui.QColor(ECR_COLORS.get(row["status"], "#ffffff"))
            for col in range(7):
                self.table.item(r, col).setBackground(bg)
        self._selected_id = None
        self.detail_text.clear()

    def _on_show_all(self):
        self.search.clear()
        self.status_filter.blockSignals(True)
        self.status_filter.setCurrentIndex(self.status_filter.count() - 1)
        self.status_filter.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        self._selected_id = self._row_ids[row]
        conn = get_db()
        rec = conn.execute(
            "SELECT d.*, p.project_number, p.title as proj_title"
            " FROM eng_design_review d LEFT JOIN eng_project p ON "
            "d.project_id = p.id"
            " WHERE d.id = %s", (self._selected_id,)
        ).fetchone()
        conn.close()
        if not rec:
            return
        proj_str = (f"{rec['project_number']} — {rec['proj_title']}"
                    if rec["project_number"] else "—")
        lines = [
            f"ECR:          {rec['ecr_number']}  —  {rec['title']}",
            f"Project:      {proj_str}",
            f"Requested By: {rec['requested_by'] or '—'}",
            f"Review Date:  {rec['review_date'] or '—'}",
            f"Status:       {rec['status'].replace('_', ' ').capitalize()}",
        ]
        if rec["notes"]:
            lines += ["", "Notes:", rec["notes"]]
        self.detail_text.setPlainText("\n".join(lines))

    def _on_new(self):
        dlg = NewECRDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status, msg):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(self, "No Selection",
                                          "Select a design review first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", msg,
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No  # noqa: E501
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = get_db()
            conn.execute("UPDATE eng_design_review SET status = %s WHERE id = %s",  # noqa: E501
                         (new_status, self._selected_id))
            conn.commit()
            conn.close()
            self._refresh()


# ── Standalone window wrapper ───────────────────────────────────────────

class DesignReviewMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Engineering Design Reviews — {email}" if email
                 else "Engineering Design Reviews")
        self.setWindowTitle(title)
        self.resize(1060, 700)
        _apply_blue_palette(self)
        self.setCentralWidget(DesignReviewWidget())


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = DesignReviewMenu()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
