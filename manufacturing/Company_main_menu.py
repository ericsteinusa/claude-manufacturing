import sys
import os
import subprocess
from PyQt6 import QtCore, QtGui, QtWidgets

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:5px 10px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


def _apply_blue_palette(widget):
    pal = widget.palette()
    for group in (QtGui.QPalette.ColorGroup.Active,
                  QtGui.QPalette.ColorGroup.Inactive,
                  QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(group, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(group, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


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


DEPARTMENTS = [
    ("Accounting",        "Accounting_Main_menu.py"),
    ("Customer Service",  "cs_main_menu.py"),
    ("Engineering",       "engineering_Main_menu.py"),
    ("Finance",           "Finance_Main_menu.py"),
    ("Information Tech",  "IT_Main_Menu.py"),
    ("Legal",             "Legal_Main_menu.py"),
    ("Maintenance",       "Maint_Main_menu.py"),
    ("Marketing",         "Marketing_Main_menu.py"),
    ("Personnel",         "Personnel_Main_menu.py"),
    ("Production",        "Production_Main_menu.py"),
    ("Purchasing",        "Purchasing_Main_menu.py"),
    ("Quality Assurance", "QA_Main_menu.py"),
    ("Risk Management",   "Risk_mgmt_Main_menu.py"),
    ("Sales",             "Sales_Main_menu.py"),
    ("Warehouse",         "Warehouse_Main_menu.py"),
    ("Budget Management", "Budget_mgmt.py"),
]


class CompanyMainMenuWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(0)
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
        for label, script in DEPARTMENTS:
            tabs.addTab(_launch_tab(script, label), label)
        v.addWidget(tabs)


class CompanyMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Company Main Menu")
        self.resize(1200, 760)
        _apply_blue_palette(self)
        self.setCentralWidget(CompanyMainMenuWidget())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = CompanyMainMenu()
    w.show()
    sys.exit(app.exec())
