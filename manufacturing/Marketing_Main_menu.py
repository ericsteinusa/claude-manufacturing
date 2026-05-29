import sys
import os
import subprocess
from PyQt6 import QtCore, QtWidgets
from Sales_menu import _apply_blue_palette

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


def _launch_tab(script, label):
    w = QtWidgets.QWidget()
    _apply_blue_palette(w)
    v = QtWidgets.QVBoxLayout(w)
    v.addStretch()
    lbl = QtWidgets.QLabel(label)
    lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("color:white;font-size:20px;font-weight:bold;")
    v.addWidget(lbl)
    v.addSpacing(12)
    btn = QtWidgets.QPushButton(f"Open {label}")
    btn.setStyleSheet(BUTTON_STYLE)
    btn.setFixedHeight(44)
    btn.setFixedWidth(260)
    btn.clicked.connect(lambda: _launch(script))
    row = QtWidgets.QHBoxLayout()
    row.addStretch()
    row.addWidget(btn)
    row.addStretch()
    v.addLayout(row)
    v.addStretch()
    return w


class MarketingMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marketing Main Menu")
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(0)
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(_launch_tab("marketing_mgr_menu.py", "Marketing Manager"), "Marketing Manager")
        tabs.addTab(_launch_tab("marketing_menu.py", "Marketing"), "Marketing")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = MarketingMainMenu()
    w.show()
    sys.exit(app.exec())
