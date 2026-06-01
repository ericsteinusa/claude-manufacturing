import sys
from PyQt6 import QtWidgets
from .Maint_mgmt import (_apply_blue_palette, WorkOrderMgmtWidget, MechanicsWidget,
                         DowntimeWidget, EquipmentWidget, SafetyInspectionWidget)

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class MaintMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Maintenance Manager Menu")
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
        tabs.addTab(WorkOrderMgmtWidget(), "Work Order Management")
        tabs.addTab(MechanicsWidget(), "Mechanics")
        tabs.addTab(DowntimeWidget(), "Downtime && Reliability")
        tabs.addTab(EquipmentWidget(), "Equipment")
        tabs.addTab(SafetyInspectionWidget(), "Safety Inspections")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = MaintMgrMenu()
    w.show()
    sys.exit(app.exec())
