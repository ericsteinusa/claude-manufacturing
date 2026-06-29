import sys
from ..launch_utils import launch as _launch
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..dept_menu_widget import DeptMenuWidget

_TITLE = "Production Main Menu"
_ITEMS = [
    ("Production Manager", lambda: _launch("prod_mgr_Menu.py")),
    ("Production",         lambda: _launch("prod_prod_menu.py")),
    ("Shipping",           lambda: _launch("prod_ship_dept.py")),
    ("Purchase Requisitions",
     lambda: _launch("purchase_requisitions.py", "Production")),
    ("Material Requirements (MRP)", lambda: _launch("mrp.py")),
]


class ProductionMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ProductionMainMenu()
    w.showMaximized()
    sys.exit(app.exec())
