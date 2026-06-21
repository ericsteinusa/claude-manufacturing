import sys
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..dept_menu_widget import DeptMenuWidget
from .warehouse_inventory import WarehouseWidget
from .receiving_dept import ReceivingDeptWidget
from ..purchase_requisitions import RequisitionsWidget

_TITLE = "Warehouse && Inventory Menu"
_ITEMS = [
    ("Inventory",  WarehouseWidget),
    ("Receiving",  ReceivingDeptWidget),
    ("Purchase Requisitions",
     lambda: RequisitionsWidget(default_dept="Warehouse")),
]


class WarehouseMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        self.resize(1200, 780)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = WarehouseMainMenu()
    w.show()
    sys.exit(app.exec())
