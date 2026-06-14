import sys
from PyQt6 import QtGui, QtWidgets
from .Risk_mgmt import (RiskAssessmentWidget, RiskRegisterWidget, InsuranceWidget,  # noqa: E501
                        BusinessContinuityWidget, ComplianceAuditWidget)
from .purchase_requisitions import RequisitionsWidget

BLUE = QtGui.QColor(0, 85, 255)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


def _apply_blue_palette(widget):
    pal = widget.palette()
    for group in (QtGui.QPalette.ColorGroup.Active,
                  QtGui.QPalette.ColorGroup.Inactive,
                  QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(group, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(group, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


class RiskMgmtMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Risk Management Main Menu")
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
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(RiskAssessmentWidget(), "Risk Assessment")
        tabs.addTab(RiskRegisterWidget(), "Risk Register")
        tabs.addTab(InsuranceWidget(), "Insurance Management")
        tabs.addTab(BusinessContinuityWidget(), "Business Continuity")
        tabs.addTab(ComplianceAuditWidget(), "Compliance && Audit")
        tabs.addTab(RequisitionsWidget(), "Purchase Requisitions")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = RiskMgmtMainMenu()
    w.show()
    sys.exit(app.exec())
