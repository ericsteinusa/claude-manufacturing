import sys
from ..launch_utils import launch as _launch
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..dept_menu_widget import DeptMenuWidget
from .cs_calls_widget import CustomerServiceCallsWidget

_TITLE = "Customer Service Main Menu"
_ITEMS = [
    ("CS Manager",       lambda: _launch("customer_service/cs_mgr_menu.py")),
    ("Customer Service", lambda: _launch("customer_service/cs_menu.py")),
    ("Customer Calls",   CustomerServiceCallsWidget),
    ("Purchase Requisitions",
     lambda: _launch("purchase_requisitions.py", "Customer Service")),
]


class CSMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = CSMainMenu()
    w.show()
    sys.exit(app.exec())
