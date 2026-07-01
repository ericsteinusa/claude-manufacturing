import sys
from PyQt6 import QtWidgets
from ..button_nav import ButtonNav
from .IT_Tasks import _apply_blue_palette
from .it_repairs_software import ITRepairsWidget, ITSoftwareWidget, ITLicensesWidget
from .it_asset_mgmt import ITAssetMgmtWidget
from .it_helpdesk import ITHelpDeskWidget
from .it_tasks_desktop import ITTasksDesktopWidget
from .it_network_devices import ITNetworkDevicesWidget
from .it_network_status import ITNetworkStatusWidget
from .it_reports_desktop import ITReportsDesktopWidget


class ITTechnicianWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(0)
        tabs = ButtonNav()
        tabs.addTab(ITTasksDesktopWidget(),    "IT Tasks")
        tabs.addTab(ITHelpDeskWidget(),         "Help Desk")
        tabs.addTab(ITRepairsWidget(),          "Hardware Repairs")
        tabs.addTab(ITSoftwareWidget(),         "Software Installations")
        tabs.addTab(ITLicensesWidget(),         "Licenses")
        tabs.addTab(ITAssetMgmtWidget(),        "Asset Management")
        tabs.addTab(ITNetworkDevicesWidget(),   "Network Devices")
        tabs.addTab(ITNetworkStatusWidget(),    "Network Status")
        tabs.addTab(ITReportsDesktopWidget(),   "Reports")
        v.addWidget(tabs)


class ITTechnicianMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IT Technician")
        _apply_blue_palette(self)
        self.setCentralWidget(ITTechnicianWidget())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ITTechnicianMenu()
    w.showMaximized()
    sys.exit(app.exec())
