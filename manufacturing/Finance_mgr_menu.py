import sys
from PyQt6 import QtWidgets
from .Finance_Main_menu import _apply_blue_palette
from .Budget_mgmt import BudgetManagementWidget
from .Credit_dept import CreditDeptWidget
from .Payroll_dept import PayrollDeptWidget
from .Audit_mgmt import AuditMgmtWidget

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class FinanceMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Finance Manager Menu")
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
        tabs.addTab(BudgetManagementWidget(), "Budget")
        tabs.addTab(CreditDeptWidget(), "Credit")
        tabs.addTab(PayrollDeptWidget(), "Payroll")
        tabs.addTab(AuditMgmtWidget(), "Audit")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = FinanceMgrMenu()
    w.show()
    sys.exit(app.exec())
