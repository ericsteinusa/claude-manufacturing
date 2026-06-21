import sys
from PyQt6 import QtWidgets
from ..button_nav import ButtonNav
from .Maint_mgmt import (_apply_blue_palette, WorkOrdersWidget, EquipmentWidget,  # noqa: E501
                         PartsInventoryWidget, MaintScheduleWidget,
                         SafetyInspectionWidget)
from ..accounts import get_current_user_email

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class MaintMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = f"Maintenance Menu — {email}" if email else "Maintenance Menu"
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
        tabs.addTab(WorkOrdersWidget(), "Work Orders")
        tabs.addTab(EquipmentWidget(), "Equipment List")
        tabs.addTab(PartsInventoryWidget(), "Parts Inventory")
        tabs.addTab(MaintScheduleWidget(), "Maintenance Schedule")
        tabs.addTab(SafetyInspectionWidget(), "Safety Inspection")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = MaintMenu()
    w.show()
    sys.exit(app.exec())
