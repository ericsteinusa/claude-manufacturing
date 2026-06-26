import sys
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..dept_menu_widget import DeptMenuWidget
from .Risk_mgmt import (RiskAssessmentWidget, RiskRegisterWidget,
                         InsuranceWidget, BusinessContinuityWidget,
                         ComplianceAuditWidget)
from ..purchase_requisitions import RequisitionsWidget

_TITLE = "Risk Management Main Menu"
_ITEMS = [
    ("Risk Assessment",    RiskAssessmentWidget),
    ("Risk Register",      RiskRegisterWidget),
    ("Insurance Mgmt",     InsuranceWidget),
    ("Business Continuity", BusinessContinuityWidget),
    ("Compliance && Audit", ComplianceAuditWidget),
    ("Purchase Requisitions",
     lambda: RequisitionsWidget(default_dept="Risk Management")),
]


class RiskMgmtMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = RiskMgmtMainMenu()
    w.showMaximized()
    sys.exit(app.exec())
