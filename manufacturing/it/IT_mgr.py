import sys
from PyQt6 import QtWidgets
from ..button_nav import ButtonNav
from .IT_Tasks import _apply_blue_palette
from .it_repairs_software import ITRepairsWidget, ITSoftwareWidget, ITLicensesWidget
from .it_asset_mgmt import ITAssetMgmtWidget
from .it_helpdesk import ITHelpDeskWidget
from .it_tasks_desktop import ITTasksDesktopWidget

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class ITMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IT Manager")
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        from .it_mgr_reports_desktop import ITMgrReportsDesktopWidget
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(0)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(ITTasksDesktopWidget(),      "IT Tasks")
        tabs.addTab(ITHelpDeskWidget(),           "Help Desk")
        tabs.addTab(ITRepairsWidget(),            "Hardware Repairs")
        tabs.addTab(ITSoftwareWidget(),           "Software Installations")
        tabs.addTab(ITLicensesWidget(),           "Licenses")
        tabs.addTab(ITAssetMgmtWidget(),          "Asset Management")
        tabs.addTab(ITMgrReportsDesktopWidget(),  "Reports")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ITMgrMenu()
    w.showMaximized()
    sys.exit(app.exec())
