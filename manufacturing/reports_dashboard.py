"""reports_dashboard.py — PyQt6 reporting dashboard widget."""

from __future__ import annotations

import datetime

from PyQt6 import QtCore, QtWidgets

from .db_pg import get_db_connection
from .reports_core import cs_summary, inventory_alerts, po_summary, wo_summary

PO_STATUS_COLORS = {
    "draft":     "#f8f9fa",
    "sent":      "#cce5ff",
    "partial":   "#fff3cd",
    "received":  "#d4edda",
    "cancelled": "#dcdcdc",
}
WO_STATUS_COLORS = {
    "draft":       "#f8f9fa",
    "open":        "#cce5ff",
    "in_progress": "#fff3cd",
    "completed":   "#d4edda",
    "cancelled":   "#dcdcdc",
}


def _kpi_card(value: str, label: str, bg: str = "#f8f9fa") -> QtWidgets.QFrame:
    frame = QtWidgets.QFrame()
    frame.setFixedSize(140, 84)
    frame.setStyleSheet(
        f"QFrame{{background:{bg};border:1px solid #aaa;border-radius:6px;}}"
    )
    v = QtWidgets.QVBoxLayout(frame)
    v.setContentsMargins(8, 6, 8, 6)
    v.setSpacing(2)
    num = QtWidgets.QLabel(value)
    num.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    num.setStyleSheet("font-size:22px;font-weight:bold;border:none;background:transparent;")
    lbl = QtWidgets.QLabel(label)
    lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("font-size:11px;color:#555;border:none;background:transparent;")
    v.addWidget(num)
    v.addWidget(lbl)
    return frame


def _section(title: str) -> tuple[QtWidgets.QGroupBox, QtWidgets.QVBoxLayout]:
    box = QtWidgets.QGroupBox(title)
    box.setStyleSheet(
        "QGroupBox{font-weight:bold;font-size:13px;border:2px solid #888;"
        "border-radius:8px;margin-top:10px;padding:6px;}"
        "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}"
    )
    layout = QtWidgets.QVBoxLayout(box)
    layout.setSpacing(8)
    return box, layout


def _clear(layout: QtWidgets.QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
        elif item.layout():
            _clear(item.layout())


class ReportsDashboardWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        hdr = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Reports Dashboard")
        title.setStyleSheet("font-size:20px;font-weight:bold;")
        self._status_lbl = QtWidgets.QLabel("")
        self._status_lbl.setStyleSheet("color:#888;font-size:11px;")
        btn = QtWidgets.QPushButton("Refresh")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.refresh)
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._status_lbl)
        hdr.addWidget(btn)
        root.addLayout(hdr)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        container = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(container)
        grid.setSpacing(16)
        scroll.setWidget(container)
        root.addWidget(scroll)

        self._po_box, self._po_layout = _section("Purchase Orders")
        self._wo_box, self._wo_layout = _section("Work Orders")
        self._inv_box, self._inv_layout = _section("Inventory Alerts")
        self._cs_box, self._cs_layout = _section("Customer Service")

        grid.addWidget(self._po_box, 0, 0)
        grid.addWidget(self._wo_box, 0, 1)
        grid.addWidget(self._inv_box, 1, 0)
        grid.addWidget(self._cs_box, 1, 1)

    def _populate_po(self, data: dict) -> None:
        _clear(self._po_layout)
        by_status = data["by_status"]

        row1 = QtWidgets.QHBoxLayout()
        for status, color in PO_STATUS_COLORS.items():
            row1.addWidget(_kpi_card(
                str(by_status.get(status, 0)), status.capitalize(), color
            ))
        row1.addStretch()
        self._po_layout.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout()
        spend = f"${data['total_spend']:,.0f}"
        overdue = data["overdue"]
        row2.addWidget(_kpi_card(spend, "Total Spend", "#e8f4f8"))
        row2.addWidget(_kpi_card(
            str(overdue), "Overdue", "#f8d7da" if overdue else "#f8f9fa"
        ))
        row2.addStretch()
        self._po_layout.addLayout(row2)

    def _populate_wo(self, data: dict) -> None:
        _clear(self._wo_layout)
        by_status = data["by_status"]

        row1 = QtWidgets.QHBoxLayout()
        for status, color in WO_STATUS_COLORS.items():
            label = status.replace("_", " ").capitalize()
            row1.addWidget(
                _kpi_card(str(by_status.get(status, 0)), label, color)
            )
        row1.addStretch()
        self._wo_layout.addLayout(row1)

        active = by_status.get("open", 0) + by_status.get("in_progress", 0)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(
            _kpi_card(str(active), "Active (Open + In Progress)", "#fff3cd")
        )
        row2.addStretch()
        self._wo_layout.addLayout(row2)

    def _populate_inv(self, data: dict) -> None:
        _clear(self._inv_layout)
        count = data["alert_count"]

        row1 = QtWidgets.QHBoxLayout()
        color = "#f8d7da" if count > 0 else "#d4edda"
        row1.addWidget(
            _kpi_card(str(count), "Items Below Reorder Point", color)
        )
        row1.addStretch()
        self._inv_layout.addLayout(row1)

        items = data["items"]
        if items:
            tbl = QtWidgets.QTableWidget(len(items), 3)
            tbl.setHorizontalHeaderLabels(
                ["Product", "On Hand", "Reorder Point"]
            )
            hdr = tbl.horizontalHeader()
            if hdr:
                hdr.setSectionResizeMode(
                    0, QtWidgets.QHeaderView.ResizeMode.Stretch
                )
            vh = tbl.verticalHeader()
            if vh:
                vh.setVisible(False)
            tbl.setEditTriggers(
                QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
            )
            tbl.setMaximumHeight(200)
            for i, item in enumerate(items):
                tbl.setItem(
                    i, 0, QtWidgets.QTableWidgetItem(str(item["name"]))
                )
                tbl.setItem(
                    i, 1, QtWidgets.QTableWidgetItem(str(item["on_hand"]))
                )
                tbl.setItem(i, 2, QtWidgets.QTableWidgetItem(
                    str(item["reorder_point"])
                ))
            self._inv_layout.addWidget(tbl)

    def _populate_cs(self, data: dict) -> None:
        _clear(self._cs_layout)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(_kpi_card(str(data["total"]), "Total Calls", "#f8f9fa"))
        row.addWidget(
            _kpi_card(str(data["open"]), "Open",
                      "#fff3cd" if data["open"] else "#f8f9fa")
        )
        row.addWidget(_kpi_card(str(data["closed"]), "Closed", "#d4edda"))
        row.addWidget(_kpi_card(str(data["today"]), "Today", "#cce5ff"))
        row.addStretch()
        self._cs_layout.addLayout(row)

    def refresh(self) -> None:
        try:
            conn = get_db_connection()
            po = po_summary(conn)
            wo = wo_summary(conn)
            inv = inventory_alerts(conn)
            cs = cs_summary(conn)
            conn.close()
            self._populate_po(po)
            self._populate_wo(wo)
            self._populate_inv(inv)
            self._populate_cs(cs)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._status_lbl.setText(f"Updated {ts}")
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Error", f"Could not load data:\n{exc}"
            )
