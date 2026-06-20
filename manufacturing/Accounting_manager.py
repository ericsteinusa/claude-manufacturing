import sys
from PyQt6 import QtWidgets
from .qt_theme import BUTTON_STYLE

from .button_nav import ButtonNav
from .accounts import get_current_user_email
from .Accounts_payable import AccountsPayableWidget, _apply_blue_palette
from .Accounts_receivable import AccountsReceivableWidget
from .Credit_dept import CreditDeptWidget
from .Payroll_dept import PayrollDeptWidget
from .General_ledger import GeneralLedgerWidget
from .Budget_mgmt import BudgetManagementWidget as BudgetMgmtWidget
from .Bank_reconciliation import BankReconciliationWidget
from .Tax_mgmt import TaxMgmtWidget
from .Audit_mgmt import AuditMgmtWidget

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class AccountingManagerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Accounting Manager — {email}" if email
                 else "Accounting Manager")
        self.setWindowTitle(title)
        self.resize(1200, 760)
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
        tabs.addTab(AccountsPayableWidget(), "Accounts Payable")
        tabs.addTab(AccountsReceivableWidget(), "Accounts Receivable")
        tabs.addTab(CreditDeptWidget(), "Credit Dept")
        tabs.addTab(PayrollDeptWidget(), "Payroll")
        tabs.addTab(GeneralLedgerWidget(), "General Ledger")
        tabs.addTab(BudgetMgmtWidget(), "Budget")
        tabs.addTab(BankReconciliationWidget(), "Bank Recon")
        tabs.addTab(TaxMgmtWidget(), "Tax")
        tabs.addTab(AuditMgmtWidget(), "Audit")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = AccountingManagerWindow()
    w.show()
    sys.exit(app.exec())
