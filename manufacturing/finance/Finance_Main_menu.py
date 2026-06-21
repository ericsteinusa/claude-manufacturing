import sys
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..dept_menu_widget import DeptMenuWidget
from .Budget_mgmt import BudgetManagementWidget
from ..customers.Credit_dept import CreditDeptWidget
from ..payroll.Payroll_dept import PayrollDeptWidget
from .Audit_mgmt import AuditMgmtWidget
from ..purchase_requisitions import RequisitionsWidget

_TITLE = "Finance Main Menu"
_ITEMS = [
    ("Budget",     BudgetManagementWidget),
    ("Credit",     CreditDeptWidget),
    ("Payroll",    PayrollDeptWidget),
    ("Audit",      AuditMgmtWidget),
    ("Purchase Requisitions",
     lambda: RequisitionsWidget(default_dept="Finance")),
]


class FinanceMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    import traceback
    app = QtWidgets.QApplication(sys.argv)
    try:
        w = FinanceMainMenu()
        w.show()
        sys.exit(app.exec())
    except Exception:
        msg = traceback.format_exc()
        print(msg, file=sys.stderr, flush=True)
        QtWidgets.QMessageBox.critical(None, "Finance Menu Error", msg)
        sys.exit(1)
