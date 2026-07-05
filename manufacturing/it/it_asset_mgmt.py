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
    ScanBar,
    apply_blue_palette as _apply_blue_palette,
    ro as _ro,
)
from ..qt_barcode import open_label
from ..button_nav import ButtonNav
from ..it_core import (
    list_assets, get_asset, create_asset, update_asset,
    ASSET_STATUSES, ASSET_TYPES,
    log_asset_event, list_asset_history,
)

TEXT_STYLE = (
    "QPlainTextEdit{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
)

_STATUS_COLORS = {
    "active":  "#d4edda",
    "spare":   "#d1ecf1",
    "repair":  "#fff3cd",
    "retired": "#dcdcdc",
    "lost":    "#f8d7da",
}
_EVENT_COLORS = {
    "created":       "#d4edda",
    "status_change": "#fff3cd",
    "reassigned":    "#d1ecf1",
    "updated":       "#e2e3e5",
    "disposed":      "#dcdcdc",
}

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


def _get_db():
    return get_db_connection()


def _me() -> str:
    return get_current_user_email() or ""


# ---------------------------------------------------------------------------
# Add / Edit dialogs
# ---------------------------------------------------------------------------

class _AssetDialog(QtWidgets.QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 440)
        _apply_blue_palette(self)
        self.asset_id: int | None = None
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
        self.asset_tag.setPlaceholderText("Unique asset tag (required)")
        layout.addRow(lbl("Asset Tag:"), self.asset_tag)

        self.asset_type = QtWidgets.QComboBox()
        self.asset_type.setStyleSheet(COMBO_STYLE)
        for t in ASSET_TYPES:
            self.asset_type.addItem(t, t)
        layout.addRow(lbl("Type:"), self.asset_type)

        self.make = QtWidgets.QLineEdit()
        self.make.setStyleSheet(INPUT_STYLE)
        self.make.setPlaceholderText("e.g. Dell, HP, Cisco")
        layout.addRow(lbl("Make:"), self.make)

        self.model = QtWidgets.QLineEdit()
        self.model.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Model:"), self.model)

        self.serial = QtWidgets.QLineEdit()
        self.serial.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Serial #:"), self.serial)

        self.assigned_to = QtWidgets.QLineEdit()
        self.assigned_to.setStyleSheet(INPUT_STYLE)
        self.assigned_to.setPlaceholderText("Leave blank if unassigned")
        layout.addRow(lbl("Assigned To:"), self.assigned_to)

        self.department = QtWidgets.QLineEdit()
        self.department.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Department:"), self.department)

        self.purchase_date = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(_date.today().isoformat(), "yyyy-MM-dd"))
        self.purchase_date.setCalendarPopup(True)
        self.purchase_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Purchase Date:"), self.purchase_date)

        self.warranty_exp = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(
                _date.today().replace(
                    year=_date.today().year + 3).isoformat(), "yyyy-MM-dd"))
        self.warranty_exp.setCalendarPopup(True)
        self.warranty_exp.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Warranty Exp:"), self.warranty_exp)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in ASSET_STATUSES:
            self.status_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setStyleSheet(TEXT_STYLE)
        self.notes.setFixedHeight(56)
        layout.addRow(lbl("Notes:"), self.notes)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _populate(self, rec: dict):
        self.asset_tag.setText(rec.get("asset_tag") or "")
        idx = self.asset_type.findData(rec.get("asset_type"))
        if idx >= 0:
            self.asset_type.setCurrentIndex(idx)
        self.make.setText(rec.get("make") or "")
        self.model.setText(rec.get("model") or "")
        self.serial.setText(rec.get("serial_number") or "")
        self.assigned_to.setText(rec.get("assigned_to") or "")
        self.department.setText(rec.get("department") or "")
        for field, widget in (
            ("purchase_date", self.purchase_date),
            ("warranty_exp",  self.warranty_exp),
        ):
            d = rec.get(field)
            if d:
                widget.setDate(
                    QtCore.QDate.fromString(str(d), "yyyy-MM-dd"))
        idx = self.status_combo.findData(rec.get("status"))
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        self.notes.setPlainText(rec.get("notes") or "")

    def _on_ok(self):
        if not self.asset_tag.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Asset tag is required.")
            return
        self._save()

    @abstractmethod
    def _save(self) -> None: ...


class AddAssetDialog(_AssetDialog):
    def __init__(self, parent=None):
        super().__init__("New Asset", parent)

    def _save(self):
        tag = self.asset_tag.text().strip()
        conn = _get_db()
        try:
            self.asset_id = create_asset(
                conn,
                asset_tag=tag,
                asset_type=self.asset_type.currentData(),
                make=self.make.text().strip(),
                model=self.model.text().strip(),
                serial_number=self.serial.text().strip(),
                assigned_to=self.assigned_to.text().strip(),
                department=self.department.text().strip(),
                purchase_date=self.purchase_date.date().toString("yyyy-MM-dd"),
                warranty_exp=self.warranty_exp.date().toString("yyyy-MM-dd"),
                status=self.status_combo.currentData(),
                notes=self.notes.toPlainText().strip(),
            )
            log_asset_event(
                conn, tag, self.asset_id,
                "created",
                f"Asset created — type: {self.asset_type.currentData()}, "
                f"status: {self.status_combo.currentData()}",
                _me(),
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class EditAssetDialog(_AssetDialog):
    def __init__(self, asset_id: int, parent=None):
        super().__init__("Edit Asset", parent)
        self._edit_id: int = asset_id
        self.asset_id = asset_id
        conn = _get_db()
        self._orig = get_asset(conn, asset_id) or {}
        conn.close()
        if self._orig:
            self._populate(self._orig)

    def _save(self):
        tag = self.asset_tag.text().strip()
        new_status = self.status_combo.currentData()
        old_status = self._orig.get("status")
        conn = _get_db()
        try:
            update_asset(
                conn, self._edit_id,
                asset_tag=tag,
                asset_type=self.asset_type.currentData(),
                make=self.make.text().strip(),
                model=self.model.text().strip(),
                serial_number=self.serial.text().strip(),
                assigned_to=self.assigned_to.text().strip(),
                department=self.department.text().strip(),
                purchase_date=self.purchase_date.date().toString("yyyy-MM-dd"),
                warranty_exp=self.warranty_exp.date().toString("yyyy-MM-dd"),
                status=new_status,
                notes=self.notes.toPlainText().strip(),
            )
            if new_status != old_status:
                log_asset_event(
                    conn, tag, self._edit_id,
                    "status_change",
                    f"Status changed: {old_status} → {new_status}",
                    _me(),
                )
            else:
                log_asset_event(
                    conn, tag, self._edit_id,
                    "updated", "Asset record updated", _me(),
                )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


# ---------------------------------------------------------------------------
# Asset Inventory
# ---------------------------------------------------------------------------

class ITAssetInventoryWidget(QtWidgets.QWidget):
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
        for s in ASSET_STATUSES:
            if s != "active":
                self._status_filter.addItem(s.capitalize(), s)
        self._status_filter.addItem("All", None)
        self._status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._status_filter)

        fr.addSpacing(10)
        lbl_t = QtWidgets.QLabel("Type:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self._type_filter = QtWidgets.QComboBox()
        self._type_filter.setStyleSheet(COMBO_STYLE)
        self._type_filter.addItem("(all)", None)
        for t in ASSET_TYPES:
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
        self._search.setPlaceholderText("tag / make / model / user")
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
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels([
            "Asset Tag", "Type", "Make", "Model",
            "Serial #", "Assigned To", "Department",
            "Warranty Exp", "Status",
        ])
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 4, 5, 6, 7, 8):
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
        dlbl = QtWidgets.QLabel("Asset Details")
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

        self.scan_bar = ScanBar(self, on_scan=self._on_scan,
                                placeholder="Scan ASSET- barcode…")
        v.addWidget(self.scan_bar)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Asset",      self._on_add),
            ("Edit Asset",     self._on_edit),
            ("Mark Active",    lambda: self._set_status("active")),
            ("Mark Spare",     lambda: self._set_status("spare")),
            ("Send to Repair", lambda: self._set_status("repair")),
            ("Retire",         lambda: self._set_status("retired")),
            ("Mark Lost",      lambda: self._set_status("lost")),
            ("Export CSV",     self._on_export),
            ("Print Label",    self._on_print_label),
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
        asset_type = self._type_filter.currentData()
        term = self._search.text().strip() or None
        conn = _get_db()
        try:
            rows = list_assets(
                conn, status=status, asset_type=asset_type, search=term)
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
            self._table.setItem(r, 1, _ro(row.get("asset_type") or ""))
            self._table.setItem(r, 2, _ro(row.get("make") or ""))
            self._table.setItem(r, 3, _ro(row.get("model") or ""))
            self._table.setItem(r, 4, _ro(row.get("serial_number") or ""))
            self._table.setItem(r, 5, _ro(row.get("assigned_to") or ""))
            self._table.setItem(r, 6, _ro(row.get("department") or ""))
            self._table.setItem(
                r, 7, _ro(str(row.get("warranty_exp") or "")))
            stat = row.get("status") or "active"
            self._table.setItem(r, 8, _ro(stat.capitalize()))
            bg = QtGui.QColor(_STATUS_COLORS.get(stat, "#ffffff"))
            for col in range(9):
                self._table.item(r, col).setBackground(bg)

        self._selected_id = None
        self._detail.clear()

    def _on_show_all(self):
        self._search.clear()
        self._status_filter.blockSignals(True)
        self._status_filter.setCurrentIndex(
            self._status_filter.count() - 1)
        self._status_filter.blockSignals(False)
        self._type_filter.blockSignals(True)
        self._type_filter.setCurrentIndex(0)
        self._type_filter.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        aid: int = self._row_ids[row]
        self._selected_id = aid
        conn = _get_db()
        rec = get_asset(conn, aid)
        conn.close()
        if not rec:
            return
        lines = [
            f"Asset Tag:    {rec.get('asset_tag') or '—'}",
            f"Type:         {rec.get('asset_type') or '—'}"
            f"   Make: {rec.get('make') or '—'}"
            f"   Model: {rec.get('model') or '—'}",
            f"Serial #:     {rec.get('serial_number') or '—'}",
            f"Assigned To:  {rec.get('assigned_to') or '—'}"
            f"   Dept: {rec.get('department') or '—'}",
            f"Purchase:     {rec.get('purchase_date') or '—'}"
            f"   Warranty Exp: {rec.get('warranty_exp') or '—'}",
            f"Status:       {(rec.get('status') or '—').capitalize()}",
        ]
        if rec.get("notes"):
            lines += ["", "Notes:", rec["notes"]]
        self._detail.setPlainText("\n".join(lines))

    def _on_add(self):
        dlg = AddAssetDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, *_):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select an asset first.")
            return
        aid: int = self._selected_id
        dlg = EditAssetDialog(aid, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status: str):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select an asset first.")
            return
        conn = _get_db()
        rec = get_asset(conn, self._selected_id)
        if not rec:
            conn.close()
            return
        old_status = rec.get("status") or ""
        tag = rec.get("asset_tag") or ""
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm",
            f"Set '{tag}' status to '{new_status}'?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            update_asset(conn, self._selected_id, status=new_status)
            log_asset_event(
                conn, tag, self._selected_id,
                "status_change",
                f"Status changed: {old_status} → {new_status}",
                _me(),
            )
            conn.commit()
            self._refresh()
        conn.close()

    def _on_export(self):
        status = self._status_filter.currentData()
        asset_type = self._type_filter.currentData()
        term = self._search.text().strip() or None
        conn = _get_db()
        try:
            rows = list_assets(conn, status=status, asset_type=asset_type,
                               search=term)
        except Exception:
            rows = []
        conn.close()
        if not rows:
            QtWidgets.QMessageBox.information(
                self, "Export", "No assets to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Assets", "assets.csv", "CSV Files (*.csv)")
        if not path:
            return
        headers = ["Asset Tag", "Type", "Make", "Model", "Serial #",
                   "Assigned To", "Department", "Purchase Date",
                   "Warranty Exp", "Status", "Notes"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({
                    "Asset Tag":     r.get("asset_tag") or "",
                    "Type":          r.get("asset_type") or "",
                    "Make":          r.get("make") or "",
                    "Model":         r.get("model") or "",
                    "Serial #":      r.get("serial_number") or "",
                    "Assigned To":   r.get("assigned_to") or "",
                    "Department":    r.get("department") or "",
                    "Purchase Date": str(r.get("purchase_date") or ""),
                    "Warranty Exp":  str(r.get("warranty_exp") or ""),
                    "Status":        (r.get("status") or "").capitalize(),
                    "Notes":         r.get("notes") or "",
                })
        QtWidgets.QMessageBox.information(
            self, "Export", f"Exported {len(rows)} asset(s) to:\n{path}")

    def _on_scan(self, raw: str):
        raw = raw.strip().upper()
        tag = raw[6:] if raw.startswith("ASSET-") else raw
        for i, aid in enumerate(self._row_ids):
            item = self._table.item(i, 0)
            if item and item.text().upper() == tag:
                self._table.selectRow(i)
                self._table.scrollToItem(item)
                self._on_row_clicked(self._table.model().index(i, 0))
                self.scan_bar.set_status(f"Found: {item.text()}", ok=True)
                return
        self.scan_bar.set_status(f"Not found: {tag}", ok=False)

    def _on_print_label(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.information(
                self, "Print Label", "Select an asset first.")
            return
        conn = _get_db()
        try:
            asset = get_asset(conn, self._selected_id)
        finally:
            conn.close()
        if asset:
            ok, msg = open_label(f"ASSET-{asset['asset_tag']}")
            self.scan_bar.set_status(msg, ok=ok)


# ---------------------------------------------------------------------------
# Asset History
# ---------------------------------------------------------------------------

class ITAssetHistoryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_e = QtWidgets.QLabel("Event:")
        lbl_e.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_e)
        self._event_filter = QtWidgets.QComboBox()
        self._event_filter.setStyleSheet(COMBO_STYLE)
        self._event_filter.addItem("(all)", None)
        for ev in ("created", "status_change", "reassigned",
                   "updated", "disposed"):
            self._event_filter.addItem(
                ev.replace("_", " ").capitalize(), ev)
        self._event_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._event_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Asset Tag:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self._tag_search = QtWidgets.QLineEdit()
        self._tag_search.setStyleSheet(INPUT_STYLE)
        self._tag_search.setFixedWidth(160)
        self._tag_search.setPlaceholderText("filter by asset tag")
        self._tag_search.returnPressed.connect(self._refresh)
        fr.addWidget(self._tag_search)
        b_ref = QtWidgets.QPushButton("Refresh")
        b_ref.setStyleSheet(BUTTON_STYLE)
        b_ref.setFixedHeight(28)
        b_ref.clicked.connect(self._refresh)
        fr.addWidget(b_ref)
        fr.addStretch()
        v.addLayout(fr)

        self._table = QtWidgets.QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Asset Tag", "Event", "Description", "Changed By", "Date/Time"])
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        v.addWidget(self._table, stretch=1)

    def _refresh(self):
        event_type = self._event_filter.currentData()
        tag = self._tag_search.text().strip() or None
        conn = _get_db()
        try:
            rows = list_asset_history(
                conn, asset_tag=tag, event_type=event_type)
        except Exception:
            rows = []
        conn.close()

        self._table.setRowCount(0)
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, _ro(row.get("asset_tag") or ""))
            ev = row.get("event_type") or ""
            self._table.setItem(
                r, 1, _ro(ev.replace("_", " ").capitalize()))
            self._table.setItem(r, 2, _ro(row.get("description") or ""))
            self._table.setItem(r, 3, _ro(row.get("changed_by") or ""))
            ts = row.get("changed_at")
            self._table.setItem(r, 4, _ro(str(ts)[:19] if ts else ""))
            bg = QtGui.QColor(_EVENT_COLORS.get(ev, "#ffffff"))
            for col in range(5):
                self._table.item(r, col).setBackground(bg)


# ---------------------------------------------------------------------------
# Disposition
# ---------------------------------------------------------------------------

class ITDispositionWidget(QtWidgets.QWidget):
    """Shows retired/lost assets and lets staff record formal disposition."""

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

        # Info banner
        info = QtWidgets.QLabel(
            "Assets listed here have status Retired or Lost. "
            "Use 'Record Disposition' to log the final outcome.")
        info.setStyleSheet(
            "color:white;background:#343a40;padding:6px 10px;"
            "border-radius:4px;font-size:12px;")
        info.setWordWrap(True)
        v.addWidget(info)

        fr = QtWidgets.QHBoxLayout()
        lbl_s = QtWidgets.QLabel("Show:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self._status_filter = QtWidgets.QComboBox()
        self._status_filter.setStyleSheet(COMBO_STYLE)
        self._status_filter.addItem("Retired & Lost", "_all")
        self._status_filter.addItem("Retired Only", "retired")
        self._status_filter.addItem("Lost Only", "lost")
        self._status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._status_filter)

        fr.addSpacing(10)
        lbl_t = QtWidgets.QLabel("Type:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self._type_filter = QtWidgets.QComboBox()
        self._type_filter.setStyleSheet(COMBO_STYLE)
        self._type_filter.addItem("(all)", None)
        for t in ASSET_TYPES:
            self._type_filter.addItem(t, t)
        self._type_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._type_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self._search = QtWidgets.QLineEdit()
        self._search.setStyleSheet(INPUT_STYLE)
        self._search.setFixedWidth(150)
        self._search.returnPressed.connect(self._refresh)
        fr.addWidget(self._search)
        fr.addStretch()
        v.addLayout(fr)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self._table = QtWidgets.QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Asset Tag", "Type", "Make", "Model",
            "Serial #", "Department", "Status",
        ])
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 4, 5, 6):
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
        splitter.addWidget(self._table)

        detail_w = QtWidgets.QWidget()
        _apply_blue_palette(detail_w)
        dv = QtWidgets.QVBoxLayout(detail_w)
        dv.setContentsMargins(0, 4, 0, 0)
        dlbl = QtWidgets.QLabel("Asset Details")
        dlbl.setStyleSheet("color:white;font-weight:bold;font-size:13px;")
        dv.addWidget(dlbl)
        self._detail = QtWidgets.QPlainTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setStyleSheet(
            "QPlainTextEdit{background:white;border:1px solid black;}")
        dv.addWidget(self._detail)
        splitter.addWidget(detail_w)
        splitter.setSizes([360, 150])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Record Disposition", self._on_record_disposition),
            ("Restore to Active",  lambda: self._set_status("active")),
            ("Refresh",            self._refresh),
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
        asset_type = self._type_filter.currentData()
        term = self._search.text().strip() or None
        conn = _get_db()
        try:
            if val == "_all":
                rows = list_assets(
                    conn, status="retired",
                    asset_type=asset_type, search=term)
                rows += list_assets(
                    conn, status="lost",
                    asset_type=asset_type, search=term)
                rows.sort(key=lambda r: r.get("asset_tag") or "")
            else:
                rows = list_assets(
                    conn, status=val,
                    asset_type=asset_type, search=term)
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
            self._table.setItem(r, 1, _ro(row.get("asset_type") or ""))
            self._table.setItem(r, 2, _ro(row.get("make") or ""))
            self._table.setItem(r, 3, _ro(row.get("model") or ""))
            self._table.setItem(r, 4, _ro(row.get("serial_number") or ""))
            self._table.setItem(r, 5, _ro(row.get("department") or ""))
            stat = row.get("status") or ""
            self._table.setItem(r, 6, _ro(stat.capitalize()))
            bg = QtGui.QColor(_STATUS_COLORS.get(stat, "#ffffff"))
            for col in range(7):
                self._table.item(r, col).setBackground(bg)

        self._selected_id = None
        self._detail.clear()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        aid: int = self._row_ids[row]
        self._selected_id = aid
        conn = _get_db()
        rec = get_asset(conn, aid)
        conn.close()
        if not rec:
            return
        lines = [
            f"Asset Tag:  {rec.get('asset_tag') or '—'}",
            f"Type:       {rec.get('asset_type') or '—'}"
            f"  Make: {rec.get('make') or '—'}"
            f"  Model: {rec.get('model') or '—'}",
            f"Serial #:   {rec.get('serial_number') or '—'}",
            f"Department: {rec.get('department') or '—'}",
            f"Status:     {(rec.get('status') or '—').capitalize()}",
        ]
        if rec.get("notes"):
            lines += ["", "Notes:", rec["notes"]]
        self._detail.setPlainText("\n".join(lines))

    def _on_record_disposition(self):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select an asset first.")
            return
        conn = _get_db()
        rec = get_asset(conn, self._selected_id)
        conn.close()
        if not rec:
            return
        tag = rec.get("asset_tag") or ""

        method, ok = QtWidgets.QInputDialog.getItem(
            self, "Record Disposition",
            f"How was '{tag}' disposed?",
            ["Sold", "Scrapped", "Donated", "Recycled", "Stolen",
             "Destroyed", "Other"],
            0, False,
        )
        if not ok:
            return
        notes, _ = QtWidgets.QInputDialog.getText(
            self, "Disposition Notes",
            "Additional notes (optional):",
        )
        conn = _get_db()
        log_asset_event(
            conn, tag, self._selected_id,
            "disposed",
            f"Disposition recorded: {method}"
            + (f" — {notes}" if notes.strip() else ""),
            _me(),
        )
        conn.commit()
        conn.close()
        QtWidgets.QMessageBox.information(
            self, "Recorded",
            f"Disposition logged for '{tag}': {method}.")

    def _set_status(self, new_status: str):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select an asset first.")
            return
        conn = _get_db()
        rec = get_asset(conn, self._selected_id)
        if not rec:
            conn.close()
            return
        old_status = rec.get("status") or ""
        tag = rec.get("asset_tag") or ""
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm",
            f"Restore '{tag}' to '{new_status}'?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            update_asset(conn, self._selected_id, status=new_status)
            log_asset_event(
                conn, tag, self._selected_id,
                "status_change",
                f"Status changed: {old_status} → {new_status}",
                _me(),
            )
            conn.commit()
            self._refresh()
        conn.close()


# ---------------------------------------------------------------------------
# Main container widget (3 tabs)
# ---------------------------------------------------------------------------

class ITAssetMgmtWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(ITAssetInventoryWidget(), "Asset Inventory")
        tabs.addTab(ITAssetHistoryWidget(),   "Asset History")
        tabs.addTab(ITDispositionWidget(),    "Disposition")
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(tabs)


# ---------------------------------------------------------------------------
# Standalone window
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("IT Asset Management")
    _apply_blue_palette(win)
    central = QtWidgets.QWidget()
    _apply_blue_palette(central)
    win.setCentralWidget(central)
    vl = QtWidgets.QVBoxLayout(central)
    vl.setContentsMargins(8, 8, 8, 8)
    vl.addWidget(ITAssetMgmtWidget())
    win.showMaximized()
    sys.exit(app.exec())
