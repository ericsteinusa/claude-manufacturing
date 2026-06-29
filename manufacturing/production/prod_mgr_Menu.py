import sys
import os
import subprocess
from PyQt6 import QtCore, QtWidgets
from ..qt_theme import BUTTON_STYLE, apply_blue_palette as _apply_blue_palette

from ..button_nav import ButtonNav
from ..accounts import get_current_user_email

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


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
    btn.clicked.connect(lambda: _do_launch(script))
    row = QtWidgets.QHBoxLayout()
    row.addStretch()
    row.addWidget(btn)
    row.addStretch()
    v.addLayout(row)
    v.addStretch()
    return w


def _do_launch(script):
    _dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen([sys.executable,
    "-m",
    "manufacturing." + os.path.splitext(script)[0]],
     cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ProdMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Production Manager Menu — {email}" if email
                 else "Production Manager Menu")
        self.setWindowTitle(title)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(0)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(
    _launch_tab(
        "prod_prod_menu.py",
        "Production"),
         "Production")
        tabs.addTab(_launch_tab("prod_ship_dept.py", "Shipping"), "Shipping")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ProdMgrMenu()
    w.showMaximized()
    sys.exit(app.exec())
