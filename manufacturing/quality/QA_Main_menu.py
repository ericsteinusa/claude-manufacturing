import sys
from ..launch_utils import launch as _launch
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..dept_menu_widget import DeptMenuWidget

_TITLE = "QA Main Menu"
_ITEMS = [
    ("QA Manager",       lambda: _launch("QA_Mgr_menu.py")),
    ("Quality Assurance", lambda: _launch("Quality_Assurance_menu.py")),
    ("Purchase Requisitions",
     lambda: _launch("purchase_requisitions.py", "Quality Assurance")),
]


class QAMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = QAMainMenu()
    w.showMaximized()
    sys.exit(app.exec())
