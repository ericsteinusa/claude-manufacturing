import sys, os, subprocess
from PyQt6 import QtCore, QtGui, QtWidgets


def _apply_blue_palette(widget):
    pal = QtGui.QPalette()
    for g in (QtGui.QPalette.ColorGroup.Active,
              QtGui.QPalette.ColorGroup.Inactive,
              QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(g, QtGui.QPalette.ColorRole.Window, QtGui.QColor(0, 85, 255))
        pal.setColor(g, QtGui.QPalette.ColorRole.Button, QtGui.QColor(0, 85, 255))
    widget.setPalette(pal)


TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


def _placeholder_tab(label):
    w = QtWidgets.QWidget(); _apply_blue_palette(w)
    v = QtWidgets.QVBoxLayout(w); v.addStretch()
    lbl = QtWidgets.QLabel(f"{label}\n(Coming Soon)")
    lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("color:white;font-size:20px;font-weight:bold;")
    v.addWidget(lbl); v.addStretch()
    return w


class MaintMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Maintenance Menu")
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget(); _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8); v.setSpacing(0)
        tabs = QtWidgets.QTabWidget(); tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(_placeholder_tab("Work Orders"), "Work Orders")
        tabs.addTab(_placeholder_tab("Equipment List"), "Equipment List")
        tabs.addTab(_placeholder_tab("Parts Request"), "Parts Request")
        tabs.addTab(_placeholder_tab("Maintenance Schedule"), "Maint. Schedule")
        tabs.addTab(_placeholder_tab("Safety Inspection"), "Safety Inspection")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = MaintMenu(); w.show()
    sys.exit(app.exec())
