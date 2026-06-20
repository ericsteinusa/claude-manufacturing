import sys
from PyQt6 import QtGui, QtWidgets
from .qt_theme import BLUE, apply_blue_palette as _apply_blue_palette

from .button_nav import ButtonNav
from .Risk_mgmt import (RiskAssessmentWidget, RiskRegisterWidget, InsuranceWidget,  # noqa: E501
                        BusinessContinuityWidget, ComplianceAuditWidget)
from .purchase_requisitions import RequisitionsWidget
from .accounts import get_current_user_email

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class RiskMgmtMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Risk Management Main Menu — {email}" if email
                 else "Risk Management Main Menu")
        self.setWindowTitle(title)
        self.resize(1100, 720)
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
        tabs.addTab(RiskAssessmentWidget(), "Risk Assessment")
        tabs.addTab(RiskRegisterWidget(), "Risk Register")
        tabs.addTab(InsuranceWidget(), "Insurance Management")
        tabs.addTab(BusinessContinuityWidget(), "Business Continuity")
        tabs.addTab(ComplianceAuditWidget(), "Compliance && Audit")
        tabs.addTab(RequisitionsWidget(default_dept="Risk Management"),
                    "Purchase Requisitions")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = RiskMgmtMainMenu()
    w.show()
    sys.exit(app.exec())
