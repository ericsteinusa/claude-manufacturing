"""Shared PyQt6 theme constants and stateless helpers.

Import only what a module needs:
    from .qt_theme import (
        BLUE, BUTTON_STYLE, apply_blue_palette as _apply_blue_palette
    )
    from .qt_theme import ro as _ro
"""
from PyQt6 import QtCore, QtGui, QtWidgets

BLUE = QtGui.QColor(0, 85, 255)

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; "
    "border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid "
    "rgb(85, 255, 255);}"
)

INPUT_STYLE = (
    "QLineEdit{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
)

COMBO_STYLE = (
    "QComboBox{background-color: white; border: 2px solid black; "
    "border-radius: 4px; padding: 2px 6px;}"
    "QComboBox QAbstractItemView{background-color: white;}"
)

LABEL_STYLE = "color: white; font-size: 13px;"


def apply_blue_palette(widget):
    pal = widget.palette()
    for group in (QtGui.QPalette.ColorGroup.Active,
                  QtGui.QPalette.ColorGroup.Inactive,
                  QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(group, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(group, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


class ScanBar(QtWidgets.QWidget):
    """
    A docked scan-input row for desktop modules.

    Usage:
        self.scan_bar = ScanBar(self, on_scan=self._handle_scan)
        v.addWidget(self.scan_bar)  # add near top of layout

    on_scan(raw: str) is called when the user hits Enter or clicks Go.
    """
    def __init__(self, parent=None, on_scan=None, placeholder="Scan barcode…"):
        super().__init__(parent)
        self._on_scan = on_scan
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(0, 4, 0, 4)
        h.setSpacing(6)

        icon_lbl = QtWidgets.QLabel("⬛")
        icon_lbl.setStyleSheet("color:white;font-size:14px;")
        h.addWidget(icon_lbl)

        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setStyleSheet(
            "QLineEdit{background:white;border:2px solid #555;"
            "border-radius:4px;padding:2px 8px;font-size:13px;max-width:260px;}"
        )
        self.input.setFixedHeight(28)
        self.input.returnPressed.connect(self._fire)
        h.addWidget(self.input)

        btn = QtWidgets.QPushButton("Go")
        btn.setStyleSheet(BUTTON_STYLE)
        btn.setFixedHeight(28)
        btn.setFixedWidth(48)
        btn.clicked.connect(self._fire)
        h.addWidget(btn)

        self.status_lbl = QtWidgets.QLabel("")
        self.status_lbl.setStyleSheet("color:white;font-size:12px;")
        h.addWidget(self.status_lbl)
        h.addStretch()

    def _fire(self):
        raw = self.input.text().strip()
        if not raw:
            return
        if self._on_scan:
            self._on_scan(raw)
        self.input.clear()
        self.input.setFocus()

    def set_status(self, msg: str, ok: bool = True):
        color = "#90ee90" if ok else "#ff9090"
        self.status_lbl.setStyleSheet(f"color:{color};font-size:12px;font-weight:bold;")
        self.status_lbl.setText(msg)


def ro(text, align=None):
    item = QtWidgets.QTableWidgetItem(text)
    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
    if align is not None:
        item.setTextAlignment(align)
    return item
