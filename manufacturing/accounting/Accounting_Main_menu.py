import sys
from ..launch_utils import launch as _launch
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..dept_menu_widget import DeptMenuWidget
from .Accounts_payable import AccountsPayableWidget
from .Accounts_receivable import AccountsReceivableWidget
from ..customers.Credit_dept import CreditDeptWidget
from ..payroll.Payroll_dept import PayrollDeptWidget
from .General_ledger import GeneralLedgerWidget
from ..finance.Budget_mgmt import BudgetManagementWidget as BudgetMgmtWidget
from ..finance.Bank_reconciliation import BankReconciliationWidget

_TITLE = "Accounting Main Menu"
_ITEMS = [
    ("Accounting Manager",  lambda: _launch("Accounting_manager.py")),
    ("Accounts Payable",    AccountsPayableWidget),
    ("Accounts Receivable", AccountsReceivableWidget),
    ("Credit Dept",         CreditDeptWidget),
    ("Payroll",             PayrollDeptWidget),
    ("General Ledger",      GeneralLedgerWidget),
    ("Budget",              BudgetMgmtWidget),
    ("Bank Recon",          BankReconciliationWidget),
    ("Purchase Requisitions",
     lambda: _launch("purchase_requisitions.py", "Accounting")),
]


class AccountingMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = AccountingMainMenu()
    w.showMaximized()
    sys.exit(app.exec())
