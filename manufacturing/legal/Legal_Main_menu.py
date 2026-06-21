import sys
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..dept_menu_widget import DeptMenuWidget
from .Legal_mgmt import (ContractsWidget, ComplianceWidget, LitigationWidget,
                          IPWidget, EmploymentLawWidget)
from ..purchase_requisitions import RequisitionsWidget

_TITLE = "Legal Main Menu"
_ITEMS = [
    ("Contracts",            ContractsWidget),
    ("Compliance",           ComplianceWidget),
    ("Litigation",           LitigationWidget),
    ("Intellectual Property", IPWidget),
    ("Employment Law",       EmploymentLawWidget),
    ("Purchase Requisitions",
     lambda: RequisitionsWidget(default_dept="Legal")),
]


class LegalMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = LegalMainMenu()
    w.show()
    sys.exit(app.exec())
