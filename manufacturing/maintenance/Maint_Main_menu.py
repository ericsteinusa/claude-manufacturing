import sys
from ..launch_utils import launch as _launch
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..dept_menu_widget import DeptMenuWidget

_TITLE = "Maintenance Main Menu"
_ITEMS = [
    ("Maintenance Manager", lambda: _launch("maintenance/Maint_mgr_menu.py")),
    ("Maintenance",         lambda: _launch("maintenance/Maint_Maint_menu.py")),
    ("Purchase Requisitions",
     lambda: _launch("purchase_requisitions.py", "Maintenance")),
]


class MaintenanceMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = MaintenanceMainMenu()
    w.showMaximized()
    sys.exit(app.exec())
