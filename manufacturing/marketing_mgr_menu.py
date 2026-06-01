import sys
from PyQt6 import QtWidgets
from .Marketing_mgmt import (_apply_blue_palette, CampaignsWidget,
                             BudgetApprovalWidget, MarketingAnalyticsWidget,
                             MarketResearchWidget)

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class MarketingMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marketing Manager Menu")
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
        tabs.addTab(CampaignsWidget(), "Campaign Management")
        tabs.addTab(BudgetApprovalWidget(), "Budget Approvals")
        tabs.addTab(MarketingAnalyticsWidget(), "Performance && ROI")
        tabs.addTab(MarketResearchWidget(), "Market Research")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = MarketingMgrMenu()
    w.show()
    sys.exit(app.exec())
