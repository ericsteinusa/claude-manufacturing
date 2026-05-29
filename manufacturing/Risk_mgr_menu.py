import sys, os, subprocess
from PyQt6 import QtCore, QtGui, QtWidgets
from .Risk_mgmt_Main_menu import _apply_blue_palette

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


def _launch(script):
    _dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)


def _placeholder_tab(label):
    w = QtWidgets.QWidget(); _apply_blue_palette(w)
    v = QtWidgets.QVBoxLayout(w); v.addStretch()
    lbl = QtWidgets.QLabel(f"{label}\n(Coming Soon)")
    lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("color:white;font-size:20px;font-weight:bold;")
    v.addWidget(lbl); v.addStretch()
    return w


class RiskMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Risk Manager Menu")
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget(); _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8); v.setSpacing(0)
        tabs = QtWidgets.QTabWidget(); tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(_placeholder_tab("Risk Framework"), "Risk Framework")
        tabs.addTab(_placeholder_tab("Risk Reporting"), "Risk Reporting")
        tabs.addTab(_placeholder_tab("Business Continuity"), "Business Continuity")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = RiskMgrMenu(); w.show()
    sys.exit(app.exec())
