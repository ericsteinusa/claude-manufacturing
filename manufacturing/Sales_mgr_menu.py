import sys
from PyQt6 import QtWidgets
from .button_nav import ButtonNav
from .Sales_menu import SalesOrdersWidget
from .qt_theme import apply_blue_palette as _apply_blue_palette
from .Accounts_receivable import AccountsReceivableWidget
from .Sales_mgmt import (QuotesWidget, CustomersWidget, SalesTargetsWidget,
                         CommissionsWidget)
from .accounts import get_current_user_email

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class SalesMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (
            f"Sales Manager Menu — {email}" if email else "Sales Manager Menu"
        )
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
        tabs.addTab(SalesOrdersWidget(), "Sales Orders")
        tabs.addTab(QuotesWidget(), "Quotes")
        tabs.addTab(CustomersWidget(), "Customers")
        tabs.addTab(SalesTargetsWidget(), "Sales Targets")
        tabs.addTab(CommissionsWidget(), "Commissions")
        tabs.addTab(AccountsReceivableWidget(), "Accounts Receivable")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = SalesMgrMenu()
    w.show()
    sys.exit(app.exec())
