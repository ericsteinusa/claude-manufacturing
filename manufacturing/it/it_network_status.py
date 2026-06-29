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
    list_network_devices,
    get_network_dashboard_stats,
    list_incidents,
    get_incident,
    create_incident,
    update_incident,
    set_incident_status,
    INCIDENT_SEVERITIES,
    INCIDENT_STATUSES,
    list_bandwidth_logs,
    list_bandwidth_interfaces,
    create_bandwidth_log,
)

TEXT_STYLE = (
    "QPlainTextEdit{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
)

_DEVICE_COLORS = {
    "online":      "#28a745",
    "offline":     "#dc3545",
    "maintenance": "#ffc107",
    "unknown":     "#6c757d",
}
_INCIDENT_SEVERITY_COLORS = {
    "critical": "#f8d7da",
    "warning":  "#fff3cd",
    "info":     "#d1ecf1",
}
_INCIDENT_STATUS_COLORS = {
    "open":         "#f8d7da",
    "investigating": "#fff3cd",
    "resolved":     "#d4edda",
}


def _get_db():
    return get_db_connection()


# ---------------------------------------------------------------------------
# Network Dashboard
# ---------------------------------------------------------------------------

class ITNetworkDashboardWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        # Stat cards row
        card_row = QtWidgets.QHBoxLayout()
        card_row.setSpacing(8)
        self._stat_labels: dict[str, QtWidgets.QLabel] = {}
        for key, title, bg in (
            ("total",       "Total Devices",    "#343a40"),
            ("online",      "Online",           "#155724"),
            ("offline",     "Offline",          "#721c24"),
            ("maintenance", "Maintenance",      "#856404"),
            ("unknown",     "Unknown",          "#495057"),
            ("open_incidents", "Open Incidents","#0c5460"),
        ):
            card = QtWidgets.QFrame()
            card.setStyleSheet(
                f"QFrame{{background:{bg};border:2px solid black;"
                f"border-radius:8px;padding:6px;}}"
            )
            cl = QtWidgets.QVBoxLayout(card)
            cl.setContentsMargins(10, 6, 10, 6)
            cl.setSpacing(2)
            t_lbl = QtWidgets.QLabel(title)
            t_lbl.setStyleSheet(
                "color:white;font-size:11px;font-weight:bold;background:transparent;")
            t_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(t_lbl)
            n_lbl = QtWidgets.QLabel("—")
            n_lbl.setStyleSheet(
                "color:white;font-size:26px;font-weight:bold;background:transparent;")
            n_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(n_lbl)
            self._stat_labels[key] = n_lbl
            card_row.addWidget(card, stretch=1)
        v.addLayout(card_row)

        # Splitter: devices-by-type on left, recent incidents on right
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # Devices by type
        left = QtWidgets.QWidget()
        _apply_blue_palette(left)
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lt_lbl = QtWidgets.QLabel("Devices by Type")
        lt_lbl.setStyleSheet(
            "color:white;font-weight:bold;font-size:13px;")
        lv.addWidget(lt_lbl)
        self._type_table = QtWidgets.QTableWidget()
        self._type_table.setColumnCount(2)
        self._type_table.setHorizontalHeaderLabels(["Device Type", "Count"])
        hh = self._type_table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self._type_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._type_table.verticalHeader().setVisible(False)
        self._type_table.setAlternatingRowColors(True)
        lv.addWidget(self._type_table)
        splitter.addWidget(left)

        # Recent incidents
        right = QtWidgets.QWidget()
        _apply_blue_palette(right)
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        ri_lbl = QtWidgets.QLabel("Recent Incidents")
        ri_lbl.setStyleSheet(
            "color:white;font-weight:bold;font-size:13px;")
        rv.addWidget(ri_lbl)
        self._recent_table = QtWidgets.QTableWidget()
        self._recent_table.setColumnCount(4)
        self._recent_table.setHorizontalHeaderLabels(
            ["Title", "Severity", "Status", "Reported"])
        rh = self._recent_table.horizontalHeader()
        rh.setStyleSheet("color:black;font-weight:bold;")
        rh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            rh.setSectionResizeMode(
                col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self._recent_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._recent_table.verticalHeader().setVisible(False)
        self._recent_table.setAlternatingRowColors(True)
        rv.addWidget(self._recent_table)
        splitter.addWidget(right)
        splitter.setSizes([300, 500])
        v.addWidget(splitter, stretch=1)

        btn_row = QtWidgets.QHBoxLayout()
        b_ref = QtWidgets.QPushButton("Refresh")
        b_ref.setStyleSheet(BUTTON_STYLE)
        b_ref.setFixedHeight(32)
        b_ref.clicked.connect(self.refresh)
        btn_row.addWidget(b_ref)
        btn_row.addStretch()
        v.addLayout(btn_row)

    def refresh(self):
        conn = _get_db()
        try:
            stats = get_network_dashboard_stats(conn)
        except Exception:
            stats = {
                'total': 0, 'online': 0, 'offline': 0,
                'maintenance': 0, 'unknown': 0,
                'by_type': [], 'open_incidents': 0, 'recent_incidents': [],
            }
        conn.close()

        for key, lbl in self._stat_labels.items():
            lbl.setText(str(stats.get(key, 0)))

        self._type_table.setRowCount(0)
        for row in stats.get('by_type', []):
            r = self._type_table.rowCount()
            self._type_table.insertRow(r)
            self._type_table.setItem(r, 0, _ro(row.get('device_type') or '—'))
            self._type_table.setItem(r, 1, _ro(str(row.get('cnt', 0))))

        self._recent_table.setRowCount(0)
        for row in stats.get('recent_incidents', []):
            r = self._recent_table.rowCount()
            self._recent_table.insertRow(r)
            self._recent_table.setItem(r, 0, _ro(row.get('title') or '—'))
            sev = row.get('severity') or 'info'
            self._recent_table.setItem(r, 1, _ro(sev.capitalize()))
            stat = row.get('status') or 'open'
            self._recent_table.setItem(
                r, 2, _ro(stat.replace('_', ' ').capitalize()))
            self._recent_table.setItem(
                r, 3, _ro(str(row.get('reported_date') or '—')))
            bg = QtGui.QColor(
                _INCIDENT_SEVERITY_COLORS.get(sev, "#ffffff"))
            for col in range(4):
                self._recent_table.item(r, col).setBackground(bg)


# ---------------------------------------------------------------------------
# Network Map
# ---------------------------------------------------------------------------

_NODE_W = 160
_NODE_H = 54
_COL_GAP = 30
_ROW_GAP = 16
_COL_W = _NODE_W + _COL_GAP


class _DeviceNode(QtWidgets.QGraphicsRectItem):
    """A single device node on the network map."""

    def __init__(self, device: dict):
        super().__init__(0, 0, _NODE_W, _NODE_H)
        self._device = device
        status = device.get('status') or 'unknown'
        color = QtGui.QColor(_DEVICE_COLORS.get(status, "#6c757d"))
        self.setBrush(QtGui.QBrush(color))
        pen = QtGui.QPen(QtGui.QColor("#000000"))
        pen.setWidth(1)
        self.setPen(pen)
        self.setToolTip(
            f"{device.get('hostname', '')}\n"
            f"IP: {device.get('ip_address', '—')}\n"
            f"MAC: {device.get('mac_address', '—')}\n"
            f"Location: {device.get('location', '—')}\n"
            f"Status: {status.capitalize()}"
        )

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        rect = self.rect()
        painter.setPen(QtGui.QPen(QtGui.QColor("white")))
        hostname = self._device.get('hostname') or '—'
        ip = self._device.get('ip_address') or ''
        f_bold = QtGui.QFont()
        f_bold.setBold(True)
        f_bold.setPointSize(8)
        painter.setFont(f_bold)
        painter.drawText(
            QtCore.QRectF(rect.x() + 4, rect.y() + 4,
                          rect.width() - 8, rect.height() / 2),
            QtCore.Qt.AlignmentFlag.AlignLeft |
            QtCore.Qt.AlignmentFlag.AlignVCenter,
            hostname,
        )
        f_small = QtGui.QFont()
        f_small.setPointSize(7)
        painter.setFont(f_small)
        painter.drawText(
            QtCore.QRectF(rect.x() + 4,
                          rect.y() + rect.height() / 2,
                          rect.width() - 8,
                          rect.height() / 2 - 4),
            QtCore.Qt.AlignmentFlag.AlignLeft |
            QtCore.Qt.AlignmentFlag.AlignVCenter,
            ip,
        )


class ITNetworkMapWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        fr = QtWidgets.QHBoxLayout()
        lbl_t = QtWidgets.QLabel("Group by:")
        lbl_t.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_t)
        self._group_combo = QtWidgets.QComboBox()
        self._group_combo.setStyleSheet(COMBO_STYLE)
        self._group_combo.addItem("Device Type", "device_type")
        self._group_combo.addItem("Location", "location")
        self._group_combo.addItem("Status", "status")
        self._group_combo.currentIndexChanged.connect(self.refresh)
        fr.addWidget(self._group_combo)
        fr.addSpacing(20)

        # Legend
        for label, color in (
            ("Online", "#28a745"), ("Offline", "#dc3545"),
            ("Maintenance", "#ffc107"), ("Unknown", "#6c757d"),
        ):
            dot = QtWidgets.QLabel("  ")
            dot.setFixedWidth(16)
            dot.setStyleSheet(
                f"background:{color};border:1px solid black;border-radius:3px;")
            fr.addWidget(dot)
            lv = QtWidgets.QLabel(label)
            lv.setStyleSheet(LABEL_STYLE)
            fr.addWidget(lv)
            fr.addSpacing(6)

        fr.addStretch()
        b_ref = QtWidgets.QPushButton("Refresh")
        b_ref.setStyleSheet(BUTTON_STYLE)
        b_ref.setFixedHeight(28)
        b_ref.clicked.connect(self.refresh)
        fr.addWidget(b_ref)
        v.addLayout(fr)

        self._scene = QtWidgets.QGraphicsScene()
        self._view = QtWidgets.QGraphicsView(self._scene)
        self._view.setRenderHint(
            QtGui.QPainter.RenderHint.Antialiasing)
        self._view.setBackgroundBrush(
            QtGui.QBrush(QtGui.QColor("#1e2a3a")))
        self._view.setDragMode(
            QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        v.addWidget(self._view, stretch=1)

        zoom_row = QtWidgets.QHBoxLayout()
        b_zin = QtWidgets.QPushButton("Zoom In")
        b_zin.setStyleSheet(BUTTON_STYLE)
        b_zin.setFixedHeight(28)
        b_zin.clicked.connect(lambda: self._view.scale(1.2, 1.2))
        b_zout = QtWidgets.QPushButton("Zoom Out")
        b_zout.setStyleSheet(BUTTON_STYLE)
        b_zout.setFixedHeight(28)
        b_zout.clicked.connect(lambda: self._view.scale(1 / 1.2, 1 / 1.2))
        b_fit = QtWidgets.QPushButton("Fit All")
        b_fit.setStyleSheet(BUTTON_STYLE)
        b_fit.setFixedHeight(28)
        b_fit.clicked.connect(
            lambda: self._view.fitInView(
                self._scene.sceneRect(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio))
        zoom_row.addWidget(b_zin)
        zoom_row.addWidget(b_zout)
        zoom_row.addWidget(b_fit)
        zoom_row.addStretch()
        v.addLayout(zoom_row)

    def refresh(self):
        self._scene.clear()
        conn = _get_db()
        try:
            devices = list_network_devices(conn)
        except Exception:
            devices = []
        conn.close()

        group_key = self._group_combo.currentData()

        # Group devices
        groups: dict[str, list] = {}
        for d in devices:
            key = d.get(group_key) or '(unset)'
            groups.setdefault(key, []).append(d)

        col_x = 20
        for group_label, devs in sorted(groups.items()):
            # Column header
            header = self._scene.addText(group_label)
            header.setDefaultTextColor(QtGui.QColor("white"))
            f = header.font()
            f.setBold(True)
            f.setPointSize(9)
            header.setFont(f)
            header.setPos(col_x, 10)

            row_y = 38
            for dev in devs:
                node = _DeviceNode(dev)
                node.setPos(col_x, row_y)
                self._scene.addItem(node)
                row_y += _NODE_H + _ROW_GAP

            col_x += _COL_W

        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(
            -10, -10, 10, 10))


# ---------------------------------------------------------------------------
# Bandwidth Monitor
# ---------------------------------------------------------------------------

class _AddBandwidthDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Bandwidth Reading")
        self.resize(420, 280)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.interface = QtWidgets.QLineEdit()
        self.interface.setStyleSheet(INPUT_STYLE)
        self.interface.setPlaceholderText("e.g. WAN, eth0, LAN (required)")
        layout.addRow(lbl("Interface:"), self.interface)

        self.mbps_in = QtWidgets.QDoubleSpinBox()
        self.mbps_in.setStyleSheet(INPUT_STYLE)
        self.mbps_in.setRange(0, 100000)
        self.mbps_in.setDecimals(2)
        self.mbps_in.setSuffix(" Mbps")
        layout.addRow(lbl("Download:"), self.mbps_in)

        self.mbps_out = QtWidgets.QDoubleSpinBox()
        self.mbps_out.setStyleSheet(INPUT_STYLE)
        self.mbps_out.setRange(0, 100000)
        self.mbps_out.setDecimals(2)
        self.mbps_out.setSuffix(" Mbps")
        layout.addRow(lbl("Upload:"), self.mbps_out)

        self.notes = QtWidgets.QLineEdit()
        self.notes.setStyleSheet(INPUT_STYLE)
        self.notes.setPlaceholderText("Optional note")
        layout.addRow(lbl("Notes:"), self.notes)

        created_by_lbl = QtWidgets.QLabel(
            get_current_user_email() or "(unknown)")
        created_by_lbl.setStyleSheet(LABEL_STYLE)
        layout.addRow(lbl("Logged by:"), created_by_lbl)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _on_ok(self):
        if not self.interface.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Interface name is required.")
            return
        conn = _get_db()
        try:
            create_bandwidth_log(
                conn,
                interface_name=self.interface.text().strip(),
                mbps_in=self.mbps_in.value(),
                mbps_out=self.mbps_out.value(),
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


class ITBandwidthWidget(QtWidgets.QWidget):
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
        lbl_i = QtWidgets.QLabel("Interface:")
        lbl_i.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_i)
        self._iface_filter = QtWidgets.QComboBox()
        self._iface_filter.setStyleSheet(COMBO_STYLE)
        self._iface_filter.addItem("(all)", None)
        self._iface_filter.setMinimumWidth(140)
        self._iface_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._iface_filter)
        fr.addStretch()
        v.addLayout(fr)

        self._table = QtWidgets.QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Interface", "Recorded At", "Download (Mbps)",
             "Upload (Mbps)", "Notes"]
        )
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(
            4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        v.addWidget(self._table, stretch=1)

        br = QtWidgets.QHBoxLayout()
        b_log = QtWidgets.QPushButton("Log Reading")
        b_log.setStyleSheet(BUTTON_STYLE)
        b_log.setFixedHeight(32)
        b_log.clicked.connect(self._on_log)
        b_ref = QtWidgets.QPushButton("Refresh")
        b_ref.setStyleSheet(BUTTON_STYLE)
        b_ref.setFixedHeight(32)
        b_ref.clicked.connect(self._refresh)
        br.addWidget(b_log)
        br.addWidget(b_ref)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        # Rebuild interface dropdown
        iface_sel = self._iface_filter.currentData()
        conn = _get_db()
        try:
            ifaces = list_bandwidth_interfaces(conn)
            iface_filter = self._iface_filter.currentData()
            rows = list_bandwidth_logs(conn, interface=iface_filter)
        except Exception:
            ifaces, rows = [], []
        conn.close()

        self._iface_filter.blockSignals(True)
        self._iface_filter.clear()
        self._iface_filter.addItem("(all)", None)
        for iface in ifaces:
            self._iface_filter.addItem(iface, iface)
        idx = self._iface_filter.findData(iface_sel)
        if idx >= 0:
            self._iface_filter.setCurrentIndex(idx)
        self._iface_filter.blockSignals(False)

        self._table.setRowCount(0)
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(
                r, 0, _ro(row.get('interface_name') or ''))
            ts = row.get('recorded_at')
            self._table.setItem(r, 1, _ro(str(ts)[:19] if ts else ''))
            self._table.setItem(
                r, 2, _ro(f"{row.get('mbps_in', 0):.2f}"))
            self._table.setItem(
                r, 3, _ro(f"{row.get('mbps_out', 0):.2f}"))
            self._table.setItem(r, 4, _ro(row.get('notes') or ''))

    def _on_log(self):
        dlg = _AddBandwidthDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()


# ---------------------------------------------------------------------------
# Incident Log
# ---------------------------------------------------------------------------

class _IncidentDialog(QtWidgets.QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 400)
        _apply_blue_palette(self)
        self.incident_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        def lbl(t):
            w = QtWidgets.QLabel(t)
            w.setStyleSheet(LABEL_STYLE)
            return w

        self.title_edit = QtWidgets.QLineEdit()
        self.title_edit.setStyleSheet(INPUT_STYLE)
        self.title_edit.setPlaceholderText("Short incident title (required)")
        layout.addRow(lbl("Title:"), self.title_edit)

        self.severity_combo = QtWidgets.QComboBox()
        self.severity_combo.setStyleSheet(COMBO_STYLE)
        for s in INCIDENT_SEVERITIES:
            self.severity_combo.addItem(s.capitalize(), s)
        layout.addRow(lbl("Severity:"), self.severity_combo)

        self.affected = QtWidgets.QLineEdit()
        self.affected.setStyleSheet(INPUT_STYLE)
        self.affected.setPlaceholderText(
            "e.g. Switch-Core, VLAN 20, Internet")
        layout.addRow(lbl("Affected Systems:"), self.affected)

        self.reported_date = QtWidgets.QDateEdit(
            QtCore.QDate.fromString(
                _date.today().isoformat(), "yyyy-MM-dd"))
        self.reported_date.setCalendarPopup(True)
        self.reported_date.setStyleSheet(INPUT_STYLE)
        layout.addRow(lbl("Reported Date:"), self.reported_date)

        self.description = QtWidgets.QPlainTextEdit()
        self.description.setStyleSheet(TEXT_STYLE)
        self.description.setFixedHeight(80)
        self.description.setPlaceholderText(
            "Describe what happened and the impact")
        layout.addRow(lbl("Description:"), self.description)

        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setStyleSheet(TEXT_STYLE)
        self.notes.setFixedHeight(60)
        self.notes.setPlaceholderText("Resolution steps, follow-up actions")
        layout.addRow(lbl("Notes:"), self.notes)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _populate(self, rec: dict):
        self.title_edit.setText(rec.get('title') or '')
        idx = self.severity_combo.findData(rec.get('severity'))
        if idx >= 0:
            self.severity_combo.setCurrentIndex(idx)
        self.affected.setText(rec.get('affected_systems') or '')
        d = rec.get('reported_date')
        if d:
            self.reported_date.setDate(
                QtCore.QDate.fromString(str(d), "yyyy-MM-dd"))
        self.description.setPlainText(rec.get('description') or '')
        self.notes.setPlainText(rec.get('notes') or '')

    def _on_ok(self):
        if not self.title_edit.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Input Error", "Title is required.")
            return
        self._save()

    def _save(self):
        raise NotImplementedError


class AddIncidentDialog(_IncidentDialog):
    def __init__(self, parent=None):
        super().__init__("New Network Incident", parent)

    def _save(self):
        conn = _get_db()
        try:
            self.incident_id = create_incident(
                conn,
                title=self.title_edit.text().strip(),
                severity=self.severity_combo.currentData(),
                description=self.description.toPlainText().strip(),
                affected_systems=self.affected.text().strip(),
                reported_date=self.reported_date.date().toString(
                    "yyyy-MM-dd"),
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


class EditIncidentDialog(_IncidentDialog):
    def __init__(self, incident_id: int, parent=None):
        super().__init__("Edit Incident", parent)
        self._edit_id: int = incident_id
        self.incident_id = incident_id
        conn = _get_db()
        rec = get_incident(conn, incident_id)
        conn.close()
        if rec:
            self._populate(rec)

    def _save(self):
        conn = _get_db()
        try:
            update_incident(
                conn,
                self._edit_id,
                title=self.title_edit.text().strip(),
                severity=self.severity_combo.currentData(),
                description=self.description.toPlainText().strip(),
                affected_systems=self.affected.text().strip(),
                reported_date=self.reported_date.date().toString(
                    "yyyy-MM-dd"),
                notes=self.notes.toPlainText().strip(),
            )
            conn.commit()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
            conn.close()
            return
        conn.close()
        self.accept()


class ITIncidentLogWidget(QtWidgets.QWidget):
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
        self._status_filter.addItem("Open & Investigating", "_active")
        for s in INCIDENT_STATUSES:
            self._status_filter.addItem(s.replace('_', ' ').capitalize(), s)
        self._status_filter.addItem("All", None)
        self._status_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._status_filter)

        fr.addSpacing(10)
        lbl_sv = QtWidgets.QLabel("Severity:")
        lbl_sv.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_sv)
        self._sev_filter = QtWidgets.QComboBox()
        self._sev_filter.setStyleSheet(COMBO_STYLE)
        self._sev_filter.addItem("(all)", None)
        for s in INCIDENT_SEVERITIES:
            self._sev_filter.addItem(s.capitalize(), s)
        self._sev_filter.currentIndexChanged.connect(self._refresh)
        fr.addWidget(self._sev_filter)

        fr.addSpacing(10)
        lbl_q = QtWidgets.QLabel("Search:")
        lbl_q.setStyleSheet(LABEL_STYLE)
        fr.addWidget(lbl_q)
        self._search = QtWidgets.QLineEdit()
        self._search.setStyleSheet(INPUT_STYLE)
        self._search.setFixedWidth(160)
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
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Title", "Severity", "Status",
             "Affected Systems", "Reported", "Resolved"]
        )
        hh = self._table.horizontalHeader()
        hh.setStyleSheet("color:black;font-weight:bold;")
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 4, 5):
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
        dlbl = QtWidgets.QLabel("Incident Details")
        dlbl.setStyleSheet(
            "color:white;font-weight:bold;font-size:13px;")
        dv.addWidget(dlbl)
        self._detail_text = QtWidgets.QPlainTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setStyleSheet(
            "QPlainTextEdit{background-color:white;border:1px solid black;}")
        dv.addWidget(self._detail_text)
        splitter.addWidget(detail_w)
        splitter.setSizes([400, 160])
        v.addWidget(splitter, stretch=1)

        br = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("New Incident",         self._on_add),
            ("Edit Incident",        self._on_edit),
            ("Mark Investigating",
             lambda: self._set_status("investigating")),
            ("Mark Resolved",
             lambda: self._set_status("resolved")),
            ("Reopen",
             lambda: self._set_status("open")),
        ):
            b = QtWidgets.QPushButton(text)
            b.setStyleSheet(BUTTON_STYLE)
            b.setFixedHeight(32)
            b.clicked.connect(slot)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

    def _refresh(self):
        status_val = self._status_filter.currentData()
        severity = self._sev_filter.currentData()
        term = self._search.text().strip()

        conn = _get_db()
        try:
            if status_val == "_active":
                # fetch open + investigating manually
                rows_open = list_incidents(
                    conn, status='open', severity=severity,
                    search=term or None)
                rows_inv = list_incidents(
                    conn, status='investigating', severity=severity,
                    search=term or None)
                rows = rows_open + rows_inv
                rows.sort(
                    key=lambda r: (r.get('reported_date') or ''),
                    reverse=True)
            else:
                rows = list_incidents(
                    conn, status=status_val, severity=severity,
                    search=term or None)
        except Exception:
            rows = []
        conn.close()

        self._table.setRowCount(0)
        self._row_ids = []
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._row_ids.append(row['id'])
            self._table.setItem(r, 0, _ro(row.get('title') or ''))
            sev = row.get('severity') or 'info'
            self._table.setItem(r, 1, _ro(sev.capitalize()))
            stat = row.get('status') or 'open'
            self._table.setItem(
                r, 2, _ro(stat.replace('_', ' ').capitalize()))
            self._table.setItem(
                r, 3, _ro(row.get('affected_systems') or ''))
            self._table.setItem(
                r, 4, _ro(str(row.get('reported_date') or '')))
            self._table.setItem(
                r, 5, _ro(str(row.get('resolved_date') or '')))
            bg = QtGui.QColor(
                _INCIDENT_STATUS_COLORS.get(stat, "#ffffff"))
            for col in range(6):
                self._table.item(r, col).setBackground(bg)

        self._selected_id = None
        self._detail_text.clear()

    def _on_show_all(self):
        self._search.clear()
        self._status_filter.blockSignals(True)
        self._status_filter.setCurrentIndex(
            self._status_filter.count() - 1)
        self._status_filter.blockSignals(False)
        self._sev_filter.blockSignals(True)
        self._sev_filter.setCurrentIndex(0)
        self._sev_filter.blockSignals(False)
        self._refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        if row < 0 or row >= len(self._row_ids):
            return
        selected_id: int = self._row_ids[row]
        self._selected_id = selected_id
        conn = _get_db()
        rec = get_incident(conn, selected_id)
        conn.close()
        if not rec:
            return
        sev = (rec.get('severity') or 'info').capitalize()
        stat = (rec.get('status') or 'open').replace('_', ' ').capitalize()
        lines = [
            f"Title:           {rec.get('title') or '—'}",
            f"Severity:        {sev}   |   Status: {stat}",
            f"Affected:        {rec.get('affected_systems') or '—'}",
            f"Reported:        {rec.get('reported_date') or '—'}"
            + (f"   Resolved: {rec['resolved_date']}"
               if rec.get('resolved_date') else ""),
            "",
            "Description:",
            rec.get('description') or '',
        ]
        if rec.get('notes'):
            lines += ["", "Notes:", rec['notes']]
        self._detail_text.setPlainText("\n".join(lines))

    def _on_add(self):
        dlg = AddIncidentDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_edit(self, *_):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select an incident first.")
            return
        incident_id: int = self._selected_id
        dlg = EditIncidentDialog(incident_id, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._refresh()

    def _set_status(self, new_status: str):
        if self._selected_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Select an incident first.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm",
            f"Set status to '{new_status.replace('_', ' ')}'?",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            conn = _get_db()
            set_incident_status(conn, self._selected_id, new_status)
            conn.commit()
            conn.close()
            self._refresh()


# ---------------------------------------------------------------------------
# Main container widget (4 tabs)
# ---------------------------------------------------------------------------

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class ITNetworkStatusWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(ITNetworkDashboardWidget(), "Network Dashboard")
        tabs.addTab(ITNetworkMapWidget(),       "Network Map")
        tabs.addTab(ITBandwidthWidget(),        "Bandwidth Monitor")
        tabs.addTab(ITIncidentLogWidget(),      "Incident Log")
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(tabs)


# ---------------------------------------------------------------------------
# Standalone window
# ---------------------------------------------------------------------------

class ITNetworkStatusMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IT Network Status")
        self.resize(1200, 780)
        _apply_blue_palette(self)
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.addWidget(ITNetworkStatusWidget())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ITNetworkStatusMenu()
    w.show()
    sys.exit(app.exec())
