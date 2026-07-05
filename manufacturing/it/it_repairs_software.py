import sys
import csv
from abc import abstractmethod
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
    list_repairs, get_repair, create_repair, update_repair, set_repair_status,
    REPAIR_STATUSES, REPAIR_PRIORITIES,
    list_software, get_software, create_software, update_software,
    SOFTWARE_STATUSES,
    list_licenses, get_license, create_license, update_license,
    LICENSE_TYPES, LICENSE_STATUSES,
)

TEXT_STYLE = (
    "QPlainTextEdit{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
)

_REPAIR_STATUS_COLORS = {
    "open":        "#ffffff",
    "in_progress": "#fff3cd",
    "completed":   "#d4edda",
    "cancelled":   "#dcdcdc",
}
_PRIORITY_COLORS = {
    "critical": QtGui.QColor(248, 215, 218),
    "high":     QtGui.QColor(255, 220, 180),
    "medium":   QtGui.QColor(220, 235, 255),
}
_SW_STATUS_COLORS = {
    "pending":   "#fff3cd",
    "installed": "#d4edda",
    "removed":   "#dcdcdc",
}
_LIC_STATUS_COLORS = {
    "active":    "#d4edda",
    "expired":   "#f8d7da",
    "cancelled": "#dcdcdc",
}


def _get_db():
    return get_db_connection()


# ===========================================================================
# Hardware Repairs
# ===========================================================================

class _RepairDialog(QtWidgets.QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 400)
        _apply_blue_palette(self)
        self.repair_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.asset_tag = QtWidgets.QLineEdit()
        self.asset_tag.setStyleSheet(INPUT_STYLE)
        self.asset_tag.setPlaceholderText("Asset tag being repaired (required)")
        layout.addRow(lbl("Asset Tag:"), self.asset_tag)

        self.problem = QtWidgets.QPlainTextEdit()
        self.problem.setStyleSheet(TEXT_STYLE)
        self.problem.setFixedHeight(72)
        self.problem.setPlaceholderText("Describe the problem (required)")
        layout.addRow(lbl("Problem:"), self.problem)

        self.reported_by = QtWidgets.QLineEdit()
        self.reported_by.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Reported By:"), self.reported_by)

        self.reported_date = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(_date.today().isoformat(), "yyyy-MM-dd"))
        self.reported_date.setCalendarPopup(True)
        self.reported_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Reported Date:"), self.reported_date)

        self.assigned_to = QtWidgets.QLineEdit()
        self.assigned_to.setStyleSheet(INPUT_STYLE)
        self.assigned_to.setPlaceholderText("Assigned technician")
        layout.addRow(lbl("Assigned To:"), self.assigned_to)

        self.priority_combo = QtWidgets.QComboBox()
        self.priority_combo.setStyleSheet(COMBO_STYLE)
        for s in REPAIR_PRIORITIES:
            self.priority_combo.addItem(s.capitalize(), s)
        self.priority_combo.setCurrentIndex(1)
        layout.addRow(lbl("Priority:"), self.priority_combo)

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
        self.asset_tag.setText(rec.get("asset_tag") or "")
        self.problem.setPlainText(rec.get("problem_description") or "")
        self.reported_by.setText(rec.get("reported_by") or "")
        d = rec.get("reported_date")
        if d:
            self.reported_date.setDate(
                QtCore.QDate.fromString(str(d), "yyyy-MM-dd"))
        self.assigned_to.setText(rec.get("assigned_to") or "")
        idx = self.priority_combo.findData(rec.get("priority"))
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)
        self.notes.setText(rec.get("notes") or "")

    def _on_ok(self):
        if not self.asset_tag.text().strip() or \
                not self.problem.toPlainText().strip():
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Asset tag and problem are required.")
            return
        self._save()

    @abstractmethod
    def _save(self) -> None: ...


class AddRepairDialog(_RepairDialog):
    def __init__(self, parent=None):
        super().__init__("New Repair Request", parent)

    def _save(self):
        conn = _get_db()
        try:
            self.repair_id = create_repair(
                conn,
                asset_tag=self.asset_tag.text().strip(),
                problem_description=self.problem.toPlainText().strip(),
                reported_by=self.reported_by.text().strip(),
                reported_date=self.reported_date.date().toString("yyyy-MM-dd"),
                assigned_to=self.assigned_to.text().strip(),
                priority=self.priority_combo.currentData(),
                notes=self.notes.text().strip(),
                created_by=get_current_user_email() or "",
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class EditRepairDialog(_RepairDialog):
    def __init__(self, repair_id: int, parent=None):
        super().__init__("Edit Repair", parent)
        self._edit_id: int = repair_id
        self.repair_id = repair_id
        conn = _get_db()
        rec = get_repair(conn, repair_id)
        conn.close()
        if rec:
            self._populate(rec)

    def _save(self):
        conn = _get_db()
        try:
            update_repair(
                conn, self._edit_id,
                asset_tag=self.asset_tag.text().strip(),
                problem_description=self.problem.toPlainText().strip(),
                reported_by=self.reported_by.text().strip(),
                reported_date=self.reported_date.date().toString("yyyy-MM-dd"),
                assigned_to=self.assigned_to.text().strip(),
                priority=self.priority_combo.currentData(),
                notes=self.notes.text().strip(),
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class ITRepairsWidget(QtWidgets.QWidget):
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
        self._status_filter.addItem("Open & In Progress", "_active")
        for s in REPAIR_STATUSES:
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
        for s in REPAIR_PRIORITIES:
            self._pri_filter.addItem(s.capitalize(), s)
        self._pri_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._pri_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self._search = QtWidgets.QLineEdit()
        self._search.setStyleSheet(INPUT_STYLE)
        self._search.setFixedWidth(160)
        self._search.setPlaceholderText("asset / reporter / problem")
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
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["Asset Tag", "Problem", "Reported By",
             "Reported Date", "Assigned To", "Priority", "Status"])
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6):
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
        dv.addWidget(self._detail_label("Repair Details"))
        self._detail = QtWidgets.QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setStyleSheet(
            "QPlainTextEdit{background:white;border:1px solid black;}")
        dv.addWidget(self._detail)
        splitter.addWidget(detail_w)
        splitter.setSizes([420, 160])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Repair",       self._on_add),
            ("Edit",             self._on_edit),
            ("Start Repair",     lambda: self._set_status("in_progress")),
            ("Mark Completed",   lambda: self._set_status("completed")),
            ("Cancel",           lambda: self._set_status("cancelled")),
            ("Export CSV",       self._on_export),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _detail_label(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        return lbl

    def _refresh(self):
        status_val = self._status_filter.currentData()
        priority = self._pri_filter.currentData()
        term = self._search.text().strip() or None

        conn = _get_db()
        try:
            if status_val == "_active":
                rows = list_repairs(conn, status="open",
                                    priority=priority, search=term)
                rows += list_repairs(conn, status="in_progress",
                                     priority=priority, search=term)
                rows.sort(
                    key=lambda r: r.get("reported_date") or "", reverse=True)
            else:
                rows = list_repairs(
                    conn, status=status_val, priority=priority, search=term)
        except Exception:
            rows = []
        conn.close()

        self._table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._row_ids.append(row["id"])
            self._table.setItem(r, 0, _ro(row.get("asset_tag") or ""))
            prob = (row.get("problem_description") or "").replace("\n", " ")
            self._table.setItem(r, 1, _ro(prob[:80]))
            self._table.setItem(r, 2, _ro(row.get("reported_by") or ""))
            self._table.setItem(
                r, 3, _ro(str(row.get("reported_date") or "")))
            self._table.setItem(r, 4, _ro(row.get("assigned_to") or ""))
            pri = row.get("priority") or "medium"
            self._table.setItem(r, 5, _ro(pri.capitalize()))
            stat = row.get("status") or "open"
            self._table.setItem(
                r, 6, _ro(stat.replace("_", " ").capitalize()))
            bg = QtGui.QColor(
                _REPAIR_STATUS_COLORS.get(stat, "#ffffff"))
            for col in range(7):
                self._table.item(r, col).setBackground(bg)
            pc = _PRIORITY_COLORS.get(pri)
            if pc and stat not in ("completed", "cancelled"):
                self._table.item(r, 5).setBackground(pc)

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
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        rid: int = self._row_ids[row]
        self._selected_id = rid
        conn = _get_db()
        rec = get_repair(conn, rid)
        conn.close()
        if not rec:
            return
        lines = [
            f"Asset Tag:    {rec.get('asset_tag') or '—'}",
            f"Reported By:  {rec.get('reported_by') or '—'}"
            f"   Date: {rec.get('reported_date') or '—'}",
            f"Assigned To:  {rec.get('assigned_to') or '—'}",
            f"Priority:     {(rec.get('priority') or '—').capitalize()}"
            f"   Status: {(rec.get('status') or '—').replace('_', ' ').capitalize()}",
            "",
            "Problem:",
            rec.get("problem_description") or "",
        ]
        if rec.get("resolution"):
            lines += ["", "Resolution:", rec["resolution"]]
        if rec.get("notes"):
            lines += ["", "Notes:", rec["notes"]]
        self._detail.setPlainText("\n".join(lines))

    def _on_add(self):
        dlg = AddRepairDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, *_):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a repair first.")
            return
        rid: int = self._selected_id
        dlg = EditRepairDialog(rid, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status: str):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a repair first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm",
            f"Set status to '{new_status.replace('_', ' ')}'?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = _get_db()
            set_repair_status(conn, self._selected_id, new_status)
            conn.commit()
            conn.close()
            self._refresh()

    def _on_export(self):
        status_val = self._status_filter.currentData()
        priority = self._pri_filter.currentData()
        term = self._search.text().strip() or None
        conn = _get_db()
        try:
            if status_val == "_active":
                rows = list_repairs(conn, status="open", priority=priority,
                                    search=term)
                rows += list_repairs(conn, status="in_progress",
                                     priority=priority, search=term)
            else:
                rows = list_repairs(conn, status=status_val,
                                    priority=priority, search=term)
        except Exception:
            rows = []
        conn.close()
        if not rows:
            QtWidgets.QMessageBox.information(
                self, "Export", "No repairs to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Repairs", "repairs.csv", "CSV Files (*.csv)")
        if not path:
            return
        headers = ["Asset Tag", "Problem", "Reported By", "Reported Date",
                   "Assigned To", "Priority", "Status", "Resolution", "Notes"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({
                    "Asset Tag":    r.get("asset_tag") or "",
                    "Problem":      r.get("problem_description") or "",
                    "Reported By":  r.get("reported_by") or "",
                    "Reported Date": str(r.get("reported_date") or ""),
                    "Assigned To":  r.get("assigned_to") or "",
                    "Priority":     (r.get("priority") or "").capitalize(),
                    "Status":       (r.get("status") or "").replace("_", " ").capitalize(),
                    "Resolution":   r.get("resolution") or "",
                    "Notes":        r.get("notes") or "",
                })
        QtWidgets.QMessageBox.information(
            self, "Export", f"Exported {len(rows)} repair(s) to:\n{path}")


# ===========================================================================
# Software Installations
# ===========================================================================

class _SoftwareDialog(QtWidgets.QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(480, 340)
        _apply_blue_palette(self)
        self.sw_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.asset_tag = QtWidgets.QLineEdit()
        self.asset_tag.setStyleSheet(INPUT_STYLE)
        self.asset_tag.setPlaceholderText("Asset tag (required)")
        layout.addRow(lbl("Asset Tag:"), self.asset_tag)

        self.software_name = QtWidgets.QLineEdit()
        self.software_name.setStyleSheet(INPUT_STYLE)
        self.software_name.setPlaceholderText("Software name (required)")
        layout.addRow(lbl("Software Name:"), self.software_name)

        self.version = QtWidgets.QLineEdit()
        self.version.setStyleSheet(INPUT_STYLE)
        self.version.setPlaceholderText("e.g. 2024.1")
        layout.addRow(lbl("Version:"), self.version)

        self.vendor = QtWidgets.QLineEdit()
        self.vendor.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Vendor:"), self.vendor)

        self.install_date = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(_date.today().isoformat(), "yyyy-MM-dd"))
        self.install_date.setCalendarPopup(True)
        self.install_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Install Date:"), self.install_date)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in SOFTWARE_STATUSES:
            self.status_combo.addItem(s.capitalize(), s)
        self.status_combo.setCurrentIndex(1)  # installed
        layout.addRow(lbl("Status:"), self.status_combo)

        self.installed_by = QtWidgets.QLineEdit()
        self.installed_by.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Installed By:"), self.installed_by)

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
        self.asset_tag.setText(rec.get("asset_tag") or "")
        self.software_name.setText(rec.get("software_name") or "")
        self.version.setText(rec.get("version") or "")
        self.vendor.setText(rec.get("vendor") or "")
        d = rec.get("install_date")
        if d:
            self.install_date.setDate(
                QtCore.QDate.fromString(str(d), "yyyy-MM-dd"))
        idx = self.status_combo.findData(rec.get("status"))
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        self.installed_by.setText(rec.get("installed_by") or "")
        self.notes.setText(rec.get("notes") or "")

    def _on_ok(self):
        if not self.asset_tag.text().strip() or \
                not self.software_name.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Input Error",
                "Asset tag and software name are required.")
            return
        self._save()

    @abstractmethod
    def _save(self) -> None: ...


class AddSoftwareDialog(_SoftwareDialog):
    def __init__(self, parent=None):
        super().__init__("Add Software Installation", parent)

    def _save(self):
        conn = _get_db()
        try:
            self.sw_id = create_software(
                conn,
                asset_tag=self.asset_tag.text().strip(),
                software_name=self.software_name.text().strip(),
                version=self.version.text().strip(),
                vendor=self.vendor.text().strip(),
                install_date=self.install_date.date().toString("yyyy-MM-dd"),
                status=self.status_combo.currentData(),
                installed_by=self.installed_by.text().strip(),
                notes=self.notes.text().strip(),
                created_by=get_current_user_email() or "",
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class EditSoftwareDialog(_SoftwareDialog):
    def __init__(self, sw_id: int, parent=None):
        super().__init__("Edit Software Installation", parent)
        self._edit_id: int = sw_id
        self.sw_id = sw_id
        conn = _get_db()
        rec = get_software(conn, sw_id)
        conn.close()
        if rec:
            self._populate(rec)

    def _save(self):
        conn = _get_db()
        try:
            update_software(
                conn, self._edit_id,
                asset_tag=self.asset_tag.text().strip(),
                software_name=self.software_name.text().strip(),
                version=self.version.text().strip(),
                vendor=self.vendor.text().strip(),
                install_date=self.install_date.date().toString("yyyy-MM-dd"),
                status=self.status_combo.currentData(),
                installed_by=self.installed_by.text().strip(),
                notes=self.notes.text().strip(),
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class ITSoftwareWidget(QtWidgets.QWidget):
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
        self._status_filter.addItem("Installed", "installed")
        self._status_filter.addItem("Pending", "pending")
        self._status_filter.addItem("Removed", "removed")
        self._status_filter.addItem("All", None)
        self._status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._status_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self._search = QtWidgets.QLineEdit()
        self._search.setStyleSheet(INPUT_STYLE)
        self._search.setFixedWidth(180)
        self._search.setPlaceholderText("software / vendor / asset")
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
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["Asset Tag", "Software Name", "Version",
             "Vendor", "Install Date", "Installed By", "Status"])
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (3, 4, 5, 6):
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
        lbl = QtWidgets.QLabel("Installation Details")
        lbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        dv.addWidget(lbl)
        self._detail = QtWidgets.QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setStyleSheet(
            "QPlainTextEdit{background:white;border:1px solid black;}")
        dv.addWidget(self._detail)
        splitter.addWidget(detail_w)
        splitter.setSizes([420, 140])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add Installation",  self._on_add),
            ("Edit",              self._on_edit),
            ("Mark Installed",    lambda: self._set_status("installed")),
            ("Mark Pending",      lambda: self._set_status("pending")),
            ("Mark Removed",      lambda: self._set_status("removed")),
            ("Export CSV",        self._on_export),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        status = self._status_filter.currentData()
        term = self._search.text().strip() or None
        conn = _get_db()
        try:
            rows = list_software(conn, status=status, search=term)
        except Exception:
            rows = []
        conn.close()

        self._table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._row_ids.append(row["id"])
            self._table.setItem(r, 0, _ro(row.get("asset_tag") or ""))
            self._table.setItem(r, 1, _ro(row.get("software_name") or ""))
            self._table.setItem(r, 2, _ro(row.get("version") or ""))
            self._table.setItem(r, 3, _ro(row.get("vendor") or ""))
            self._table.setItem(
                r, 4, _ro(str(row.get("install_date") or "")))
            self._table.setItem(r, 5, _ro(row.get("installed_by") or ""))
            stat = row.get("status") or "installed"
            self._table.setItem(r, 6, _ro(stat.capitalize()))
            bg = QtGui.QColor(_SW_STATUS_COLORS.get(stat, "#ffffff"))
            for col in range(7):
                self._table.item(r, col).setBackground(bg)

        self._selected_id = None
        self._detail.clear()

    def _on_show_all(self):
        self._search.clear()
        self._status_filter.blockSignals(True)
        self._status_filter.setCurrentIndex(
            self._status_filter.count() - 1)
        self._status_filter.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        sid: int = self._row_ids[row]
        self._selected_id = sid
        conn = _get_db()
        rec = get_software(conn, sid)
        conn.close()
        if not rec:
            return
        lines = [
            f"Asset Tag:     {rec.get('asset_tag') or '—'}",
            f"Software:      {rec.get('software_name') or '—'}"
            f"  v{rec.get('version') or '—'}",
            f"Vendor:        {rec.get('vendor') or '—'}",
            f"Install Date:  {rec.get('install_date') or '—'}"
            f"   Installed By: {rec.get('installed_by') or '—'}",
            f"Status:        {(rec.get('status') or '—').capitalize()}",
        ]
        if rec.get("notes"):
            lines += ["", "Notes:", rec["notes"]]
        self._detail.setPlainText("\n".join(lines))

    def _on_add(self):
        dlg = AddSoftwareDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, *_):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select an installation first.")
            return
        sid: int = self._selected_id
        dlg = EditSoftwareDialog(sid, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status: str):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select an installation first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", f"Set status to '{new_status}'?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = _get_db()
            update_software(conn, self._selected_id, status=new_status)
            conn.commit()
            conn.close()
            self._refresh()

    def _on_export(self):
        status = self._status_filter.currentData()
        term = self._search.text().strip() or None
        conn = _get_db()
        try:
            rows = list_software(conn, status=status, search=term)
        except Exception:
            rows = []
        conn.close()
        if not rows:
            QtWidgets.QMessageBox.information(
                self, "Export", "No software records to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Software", "software_installations.csv",
            "CSV Files (*.csv)")
        if not path:
            return
        headers = ["Asset Tag", "Software Name", "Version", "Vendor",
                   "Install Date", "Installed By", "Status", "Notes"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({
                    "Asset Tag":     r.get("asset_tag") or "",
                    "Software Name": r.get("software_name") or "",
                    "Version":       r.get("version") or "",
                    "Vendor":        r.get("vendor") or "",
                    "Install Date":  str(r.get("install_date") or ""),
                    "Installed By":  r.get("installed_by") or "",
                    "Status":        (r.get("status") or "").capitalize(),
                    "Notes":         r.get("notes") or "",
                })
        QtWidgets.QMessageBox.information(
            self, "Export", f"Exported {len(rows)} installation(s) to:\n{path}")


# ===========================================================================
# Software Licenses
# ===========================================================================

class _LicenseDialog(QtWidgets.QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 430)
        _apply_blue_palette(self)
        self.license_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.software_name = QtWidgets.QLineEdit()
        self.software_name.setStyleSheet(INPUT_STYLE)
        self.software_name.setPlaceholderText("Software name (required)")
        layout.addRow(lbl("Software Name:"), self.software_name)

        self.vendor = QtWidgets.QLineEdit()
        self.vendor.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Vendor:"), self.vendor)

        self.license_key = QtWidgets.QLineEdit()
        self.license_key.setStyleSheet(INPUT_STYLE)
        self.license_key.setPlaceholderText("License key or serial")
        layout.addRow(lbl("License Key:"), self.license_key)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.setStyleSheet(COMBO_STYLE)
        for t in LICENSE_TYPES:
            self.type_combo.addItem(t.replace("_", " ").capitalize(), t)
        layout.addRow(lbl("License Type:"), self.type_combo)

        seat_row = QtWidgets.QHBoxLayout()
        self.seats = QtWidgets.QSpinBox()
        self.seats.setStyleSheet(INPUT_STYLE)
        self.seats.setRange(1, 99999)
        self.seats.setValue(1)
        seat_row.addWidget(self.seats)
        seat_row.addWidget(QtWidgets.QLabel("  Used:"))
        self.seats_used = QtWidgets.QSpinBox()
        self.seats_used.setStyleSheet(INPUT_STYLE)
        self.seats_used.setRange(0, 99999)
        seat_row.addWidget(self.seats_used)
        seat_row.addStretch()
        layout.addRow(lbl("Seats:"), seat_row)

        self.purchase_date = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(_date.today().isoformat(), "yyyy-MM-dd"))
        self.purchase_date.setCalendarPopup(True)
        self.purchase_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Purchase Date:"), self.purchase_date)

        self.expiry_date = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(
                _date.today().replace(year=_date.today().year + 1).isoformat(),
                "yyyy-MM-dd"))
        self.expiry_date.setCalendarPopup(True)
        self.expiry_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Expiry Date:"), self.expiry_date)

        self.cost = QtWidgets.QDoubleSpinBox()
        self.cost.setStyleSheet(INPUT_STYLE)
        self.cost.setRange(0, 9999999)
        self.cost.setDecimals(2)
        self.cost.setPrefix("$ ")
        layout.addRow(lbl("Cost:"), self.cost)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in LICENSE_STATUSES:
            self.status_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

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
        self.software_name.setText(rec.get("software_name") or "")
        self.vendor.setText(rec.get("vendor") or "")
        self.license_key.setText(rec.get("license_key") or "")
        idx = self.type_combo.findData(rec.get("license_type"))
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.seats.setValue(int(rec.get("seats") or 1))
        self.seats_used.setValue(int(rec.get("seats_used") or 0))
        for field, widget in (
            ("purchase_date", self.purchase_date),
            ("expiry_date",   self.expiry_date),
        ):
            d = rec.get(field)
            if d:
                widget.setDate(
                    QtCore.QDate.fromString(str(d), "yyyy-MM-dd"))
        self.cost.setValue(float(rec.get("cost") or 0))
        idx = self.status_combo.findData(rec.get("status"))
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        self.notes.setText(rec.get("notes") or "")

    def _on_ok(self):
        if not self.software_name.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Software name is required.")
            return
        self._save()

    @abstractmethod
    def _save(self) -> None: ...


class AddLicenseDialog(_LicenseDialog):
    def __init__(self, parent=None):
        super().__init__("Add License", parent)

    def _save(self):
        conn = _get_db()
        try:
            self.license_id = create_license(
                conn,
                software_name=self.software_name.text().strip(),
                vendor=self.vendor.text().strip(),
                license_key=self.license_key.text().strip(),
                license_type=self.type_combo.currentData(),
                seats=self.seats.value(),
                seats_used=self.seats_used.value(),
                purchase_date=self.purchase_date.date().toString("yyyy-MM-dd"),
                expiry_date=self.expiry_date.date().toString("yyyy-MM-dd"),
                cost=self.cost.value(),
                status=self.status_combo.currentData(),
                notes=self.notes.text().strip(),
                created_by=get_current_user_email() or "",
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class EditLicenseDialog(_LicenseDialog):
    def __init__(self, license_id: int, parent=None):
        super().__init__("Edit License", parent)
        self._edit_id: int = license_id
        self.license_id = license_id
        conn = _get_db()
        rec = get_license(conn, license_id)
        conn.close()
        if rec:
            self._populate(rec)

    def _save(self):
        conn = _get_db()
        try:
            update_license(
                conn, self._edit_id,
                software_name=self.software_name.text().strip(),
                vendor=self.vendor.text().strip(),
                license_key=self.license_key.text().strip(),
                license_type=self.type_combo.currentData(),
                seats=self.seats.value(),
                seats_used=self.seats_used.value(),
                purchase_date=self.purchase_date.date().toString("yyyy-MM-dd"),
                expiry_date=self.expiry_date.date().toString("yyyy-MM-dd"),
                cost=self.cost.value(),
                status=self.status_combo.currentData(),
                notes=self.notes.text().strip(),
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class ITLicensesWidget(QtWidgets.QWidget):
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
        self._status_filter.addItem("Active", "active")
        self._status_filter.addItem("Expired", "expired")
        self._status_filter.addItem("Cancelled", "cancelled")
        self._status_filter.addItem("All", None)
        self._status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._status_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self._search = QtWidgets.QLineEdit()
        self._search.setStyleSheet(INPUT_STYLE)
        self._search.setFixedWidth(180)
        self._search.setPlaceholderText("software / vendor")
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
        self._table.setHorizontalHeaderLabels(
            ["Software Name", "Vendor", "Type",
             "Seats", "Used", "Expiry Date", "Cost", "Status"])
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
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
        lbl = QtWidgets.QLabel("License Details")
        lbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        dv.addWidget(lbl)
        self._detail = QtWidgets.QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setStyleSheet(
            "QPlainTextEdit{background:white;border:1px solid black;}")
        dv.addWidget(self._detail)
        splitter.addWidget(detail_w)
        splitter.setSizes([420, 140])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add License",     self._on_add),
            ("Edit License",    self._on_edit),
            ("Mark Active",     lambda: self._set_status("active")),
            ("Mark Expired",    lambda: self._set_status("expired")),
            ("Cancel License",  lambda: self._set_status("cancelled")),
            ("Export CSV",      self._on_export),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        status = self._status_filter.currentData()
        term = self._search.text().strip() or None
        conn = _get_db()
        try:
            rows = list_licenses(conn, status=status, search=term)
        except Exception:
            rows = []
        conn.close()

        self._table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._row_ids.append(row["id"])
            self._table.setItem(r, 0, _ro(row.get("software_name") or ""))
            self._table.setItem(r, 1, _ro(row.get("vendor") or ""))
            self._table.setItem(
                r, 2, _ro((row.get("license_type") or "").replace(
                    "_", " ").capitalize()))
            self._table.setItem(r, 3, _ro(str(row.get("seats") or 1)))
            self._table.setItem(r, 4, _ro(str(row.get("seats_used") or 0)))
            self._table.setItem(
                r, 5, _ro(str(row.get("expiry_date") or "")))
            cost = row.get("cost") or 0
            self._table.setItem(r, 6, _ro(f"${cost:,.2f}"))
            stat = row.get("status") or "active"
            self._table.setItem(r, 7, _ro(stat.capitalize()))
            bg = QtGui.QColor(_LIC_STATUS_COLORS.get(stat, "#ffffff"))
            for col in range(8):
                self._table.item(r, col).setBackground(bg)

        self._selected_id = None
        self._detail.clear()

    def _on_show_all(self):
        self._search.clear()
        self._status_filter.blockSignals(True)
        self._status_filter.setCurrentIndex(
            self._status_filter.count() - 1)
        self._status_filter.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        lid: int = self._row_ids[row]
        self._selected_id = lid
        conn = _get_db()
        rec = get_license(conn, lid)
        conn.close()
        if not rec:
            return
        seats = rec.get("seats") or 1
        used = rec.get("seats_used") or 0
        lines = [
            f"Software:      {rec.get('software_name') or '—'}",
            f"Vendor:        {rec.get('vendor') or '—'}",
            f"License Type:  {(rec.get('license_type') or '—').replace('_', ' ').capitalize()}",
            f"License Key:   {rec.get('license_key') or '—'}",
            f"Seats:         {seats} total  /  {used} used  /  {seats - used} available",
            f"Purchase Date: {rec.get('purchase_date') or '—'}"
            f"   Expiry: {rec.get('expiry_date') or '—'}",
            f"Cost:          ${float(rec.get('cost') or 0):,.2f}",
            f"Status:        {(rec.get('status') or '—').capitalize()}",
        ]
        if rec.get("notes"):
            lines += ["", "Notes:", rec["notes"]]
        self._detail.setPlainText("\n".join(lines))

    def _on_add(self):
        dlg = AddLicenseDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, *_):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a license first.")
            return
        lid: int = self._selected_id
        dlg = EditLicenseDialog(lid, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status: str):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a license first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm", f"Set status to '{new_status}'?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = _get_db()
            update_license(conn, self._selected_id, status=new_status)
            conn.commit()
            conn.close()
            self._refresh()

    def _on_export(self):
        status = self._status_filter.currentData()
        term = self._search.text().strip() or None
        conn = _get_db()
        try:
            rows = list_licenses(conn, status=status, search=term)
        except Exception:
            rows = []
        conn.close()
        if not rows:
            QtWidgets.QMessageBox.information(
                self, "Export", "No licenses to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Licenses", "licenses.csv", "CSV Files (*.csv)")
        if not path:
            return
        headers = ["Software Name", "Vendor", "License Type", "License Key",
                   "Seats", "Seats Used", "Purchase Date", "Expiry Date",
                   "Cost", "Status", "Notes"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({
                    "Software Name": r.get("software_name") or "",
                    "Vendor":        r.get("vendor") or "",
                    "License Type":  (r.get("license_type") or "").replace("_", " ").capitalize(),
                    "License Key":   r.get("license_key") or "",
                    "Seats":         r.get("seats") or 1,
                    "Seats Used":    r.get("seats_used") or 0,
                    "Purchase Date": str(r.get("purchase_date") or ""),
                    "Expiry Date":   str(r.get("expiry_date") or ""),
                    "Cost":          f"{float(r.get('cost') or 0):.2f}",
                    "Status":        (r.get("status") or "").capitalize(),
                    "Notes":         r.get("notes") or "",
                })
        QtWidgets.QMessageBox.information(
            self, "Export", f"Exported {len(rows)} license(s) to:\n{path}")


# ===========================================================================
# Standalone window (for direct launch)
# ===========================================================================

if __name__ == "__main__":
    from ..button_nav import ButtonNav
    from ..qt_theme import apply_blue_palette

    TAB_STYLE = (
        "QTabWidget::pane{border:1px solid black;}"
        "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
        "border-bottom:none;border-radius:4px 4px 0 0;}"
        "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
        "QTabBar::tab:hover{background:rgb(85,255,255);}"
    )

    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("IT — Repairs, Software & Licenses")
    apply_blue_palette(win)
    central = QtWidgets.QWidget()
    apply_blue_palette(central)
    win.setCentralWidget(central)
    vl = QtWidgets.QVBoxLayout(central)
    vl.setContentsMargins(8, 8, 8, 8)
    tabs = ButtonNav()
    tabs.setStyleSheet(TAB_STYLE)
    tabs.addTab(ITRepairsWidget(),  "Hardware Repairs")
    tabs.addTab(ITSoftwareWidget(), "Software Installations")
    tabs.addTab(ITLicensesWidget(), "Licenses")
    vl.addWidget(tabs)
    win.showMaximized()
    sys.exit(app.exec())
