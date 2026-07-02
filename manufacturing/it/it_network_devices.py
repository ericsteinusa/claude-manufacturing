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
    list_network_devices,
    get_network_device,
    create_network_device,
    update_network_device,
    NETWORK_DEVICE_TYPES,
    NETWORK_DEVICE_STATUSES,
)

TEXT_STYLE = (
    "QPlainTextEdit{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
)

STATUS_COLORS = {
    "online":      "#d4edda",
    "offline":     "#f8d7da",
    "maintenance": "#fff3cd",
    "unknown":     "#dcdcdc",
}


def _get_db():
    return get_db_connection()


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

class _DeviceDialog(QtWidgets.QDialog):
    """Shared base for Add and Edit dialogs."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 420)
        _apply_blue_palette(self)
        self.device_id = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.hostname = QtWidgets.QLineEdit()
        self.hostname.setStyleSheet(INPUT_STYLE)
        self.hostname.setPlaceholderText("e.g. sw-core-01 (required)")
        layout.addRow(lbl("Hostname:"), self.hostname)

        self.ip_address = QtWidgets.QLineEdit()
        self.ip_address.setStyleSheet(INPUT_STYLE)
        self.ip_address.setPlaceholderText("e.g. 192.168.1.1")
        layout.addRow(lbl("IP Address:"), self.ip_address)

        self.mac_address = QtWidgets.QLineEdit()
        self.mac_address.setStyleSheet(INPUT_STYLE)
        self.mac_address.setPlaceholderText("e.g. AA:BB:CC:DD:EE:FF")
        layout.addRow(lbl("MAC Address:"), self.mac_address)

        self.device_type = QtWidgets.QComboBox()
        self.device_type.setStyleSheet(COMBO_STYLE)
        for t in NETWORK_DEVICE_TYPES:
            self.device_type.addItem(t, t)
        layout.addRow(lbl("Type:"), self.device_type)

        self.manufacturer = QtWidgets.QLineEdit()
        self.manufacturer.setStyleSheet(INPUT_STYLE)
        self.manufacturer.setPlaceholderText("e.g. Cisco, Ubiquiti, Netgear")
        layout.addRow(lbl("Manufacturer:"), self.manufacturer)

        self.model = QtWidgets.QLineEdit()
        self.model.setStyleSheet(INPUT_STYLE)
        self.model.setPlaceholderText("Model name / number")
        layout.addRow(lbl("Model:"), self.model)

        self.location = QtWidgets.QLineEdit()
        self.location.setStyleSheet(INPUT_STYLE)
        self.location.setPlaceholderText("e.g. Server Room Rack A")
        layout.addRow(lbl("Location:"), self.location)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.setStyleSheet(COMBO_STYLE)
        for s in NETWORK_DEVICE_STATUSES:
            self.status_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Status:"), self.status_combo)

        self.last_seen = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(
                _date.today().isoformat(), "yyyy-MM-dd"))
        self.last_seen.setCalendarPopup(True)
        self.last_seen.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Last Seen:"), self.last_seen)

        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setStyleSheet(TEXT_STYLE)
        self.notes.setFixedHeight(60)
        layout.addRow(lbl("Notes:"), self.notes)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _populate(self, rec: dict):
        self.hostname.setText(rec.get("hostname") or "")
        self.ip_address.setText(rec.get("ip_address") or "")
        self.mac_address.setText(rec.get("mac_address") or "")
        idx = self.device_type.findData(rec.get("device_type"))
        if idx >= 0:
            self.device_type.setCurrentIndex(idx)
        self.manufacturer.setText(rec.get("manufacturer") or "")
        self.model.setText(rec.get("model") or "")
        self.location.setText(rec.get("location") or "")
        idx = self.status_combo.findData(rec.get("status"))
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        last = rec.get("last_seen")
        if last:
            self.last_seen.setDate(
                QtCore.QDate.fromString(str(last), "yyyy-MM-dd"))
        self.notes.setPlainText(rec.get("notes") or "")

    def _on_ok(self):
        if not self.hostname.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Hostname is required.")
            return
        self._save()

    def _save(self):
        raise NotImplementedError


class AddDeviceDialog(_DeviceDialog):
    def __init__(self, parent=None):
        super().__init__("Add Network Device", parent)

    def _save(self):
        conn = _get_db()
        try:
            self.device_id = create_network_device(
                conn,
                hostname=self.hostname.text().strip(),
                ip_address=self.ip_address.text().strip(),
                mac_address=self.mac_address.text().strip(),
                device_type=self.device_type.currentData(),
                manufacturer=self.manufacturer.text().strip(),
                model=self.model.text().strip(),
                location=self.location.text().strip(),
                status=self.status_combo.currentData(),
                last_seen=self.last_seen.date().toString("yyyy-MM-dd"),
                notes=self.notes.toPlainText().strip(),
                created_by=get_current_user_email() or "",
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class EditDeviceDialog(_DeviceDialog):
    def __init__(self, device_id: int, parent=None):
        super().__init__("Edit Network Device", parent)
        self._edit_id: int = device_id
        self.device_id = device_id
        conn = _get_db()
        rec = get_network_device(conn, device_id)
        conn.close()
        if rec:
            self._populate(rec)

    def _save(self):
        conn = _get_db()
        try:
            update_network_device(
                conn,
                self._edit_id,
                hostname=self.hostname.text().strip(),
                ip_address=self.ip_address.text().strip(),
                mac_address=self.mac_address.text().strip(),
                device_type=self.device_type.currentData(),
                manufacturer=self.manufacturer.text().strip(),
                model=self.model.text().strip(),
                location=self.location.text().strip(),
                status=self.status_combo.currentData(),
                last_seen=self.last_seen.date().toString("yyyy-MM-dd"),
                notes=self.notes.toPlainText().strip(),
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


# ---------------------------------------------------------------------------
# Embeddable widget
# ---------------------------------------------------------------------------

class ITNetworkDevicesWidget(QtWidgets.QWidget):
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

        # Filter bar
        fr = QtWidgets.QHBoxLayout()

        lbl_s = QtWidgets.QLabel("Status:")
        lbl_s.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_s)
        self._status_filter = QtWidgets.QComboBox()
        self._status_filter.setStyleSheet(COMBO_STYLE)
        self._status_filter.addItem("Online", "online")
        self._status_filter.addItem("Offline", "offline")
        self._status_filter.addItem("Maintenance", "maintenance")
        self._status_filter.addItem("Unknown", "unknown")
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
        for t in NETWORK_DEVICE_TYPES:
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
        self._search.setPlaceholderText("hostname / IP / location")
        self._search.returnPressed.connect(self._refresh)
        fr.addWidget(self._search)

        b_all = QtWidgets.QPushButton("Show All")
        b_all.setStyleSheet(BUTTON_STYLE)
        b_all.setFixedHeight(28)
        b_all.clicked.connect(self._on_show_all)
        fr.addWidget(b_all)
        fr.addStretch()
        v.addLayout(fr)

        # Splitter: table on top, detail below
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self._table = QtWidgets.QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels(
            ["Hostname", "IP Address", "MAC Address",
             "Type", "Manufacturer", "Model", "Location", "Status"]
        )
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color: black; font-weight: bold;")
        hh.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
            6, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
            7, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
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
        dlbl = QtWidgets.QLabel("Device Details")
        dlbl.setStyleSheet(
            "color: white; font-weight: bold; font-size: 13px;")
        dv.addWidget(dlbl)
        self._detail_text = QtWidgets.QPlainTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setStyleSheet(
            "QPlainTextEdit{background-color: white; border: 1px solid black;}")
        dv.addWidget(self._detail_text)
        splitter.addWidget(detail_w)
        splitter.setSizes([420, 160])
        v.addWidget(splitter, stretch=1)

        # Button row
        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Add Device",       self._on_add),
            ("Edit Device",      self._on_edit),
            ("Mark Online",      lambda: self._set_status("online")),
            ("Mark Offline",     lambda: self._set_status("offline")),
            ("Maintenance",      lambda: self._set_status("maintenance")),
            ("Refresh",          self._refresh),
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
        device_type = self._type_filter.currentData()
        term = self._search.text().strip()

        conn = _get_db()
        try:
            rows = list_network_devices(
                conn, status=status, device_type=device_type,
                search=term or None)
        except Exception:
            rows = []
        conn.close()

        self._table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._row_ids.append(row["id"])
            self._table.setItem(r, 0, _ro(row.get("hostname") or ""))
            self._table.setItem(r, 1, _ro(row.get("ip_address") or ""))
            self._table.setItem(r, 2, _ro(row.get("mac_address") or ""))
            self._table.setItem(r, 3, _ro(row.get("device_type") or ""))
            self._table.setItem(r, 4, _ro(row.get("manufacturer") or ""))
            self._table.setItem(r, 5, _ro(row.get("model") or ""))
            self._table.setItem(r, 6, _ro(row.get("location") or ""))
            status_val = row.get("status") or "unknown"
            self._table.setItem(r, 7, _ro(status_val.capitalize()))
            bg = QtGui.QColor(STATUS_COLORS.get(status_val, "#ffffff"))
            for col in range(8):
                self._table.item(r, col).setBackground(bg)

        self._selected_id = None
        self._detail_text.clear()

    def _on_show_all(self):
        self._search.clear()
        self._status_filter.blockSignals(True)
        self._status_filter.setCurrentIndex(
            self._status_filter.count() - 1)  # "All"
        self._status_filter.blockSignals(False)
        self._type_filter.blockSignals(True)
        self._type_filter.setCurrentIndex(0)
        self._type_filter.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        selected_id = self._row_ids[row]
        self._selected_id = selected_id
        conn = _get_db()
        rec = get_network_device(conn, selected_id)
        conn.close()
        if not rec:
            return
        lines = [
            f"Hostname:     {rec.get('hostname') or '—'}",
            f"IP Address:   {rec.get('ip_address') or '—'}"
            f"   MAC: {rec.get('mac_address') or '—'}",
            f"Type:         {rec.get('device_type') or '—'}"
            f"   Manufacturer: {rec.get('manufacturer') or '—'}",
            f"Model:        {rec.get('model') or '—'}",
            f"Location:     {rec.get('location') or '—'}",
            f"Status:       {(rec.get('status') or '—').capitalize()}"
            f"   Last Seen: {rec.get('last_seen') or '—'}",
        ]
        if rec.get("notes"):
            lines += ["", "Notes:", rec["notes"]]
        self._detail_text.setPlainText("\n".join(lines))

    def _on_add(self):
        dlg = AddDeviceDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, *_):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a device first.")
            return
        device_id: int = self._selected_id
        dlg = EditDeviceDialog(device_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status: str):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select a device first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm",
            f"Set status to '{new_status}'?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = _get_db()
            update_network_device(conn, self._selected_id, status=new_status)
            conn.commit()
            conn.close()
            self._refresh()


# ---------------------------------------------------------------------------
# Standalone window
# ---------------------------------------------------------------------------

class ITNetworkDevicesMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IT Network Devices")
        self.resize(1100, 720)
        _apply_blue_palette(self)
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.addWidget(ITNetworkDevicesWidget())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ITNetworkDevicesMenu()
    w.show()
    sys.exit(app.exec())
