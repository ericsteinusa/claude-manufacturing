import sys
from .launch_utils import launch as _launch
from PyQt6 import QtWidgets
from .qt_theme import apply_blue_palette as _apply_blue_palette
from .dept_menu_widget import DeptMenuWidget

_TITLE = "IT Main Menu"
_ITEMS = [
    ("IT Manager",    lambda: _launch("IT_mgr.py")),
    ("IT Technician", lambda: _launch("IT_technician.py")),
    ("Purchase Requisitions",
     lambda: _launch("purchase_requisitions.py", "Information Technologies")),
]


class ITMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ITMainMenu()
    w.show()
    sys.exit(app.exec())
