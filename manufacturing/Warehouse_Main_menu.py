import sys
from PyQt6 import QtWidgets
from .warehouse_inventory import WarehouseWidget, _apply_palette as _apply_blue_palette  # noqa: E501
from .receiving_dept import ReceivingDeptWidget
from .purchase_requisitions import RequisitionsWidget

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; "
    "border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid "
    "rgb(85, 255, 255);}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class WarehouseMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Warehouse & Inventory Menu")
        self.resize(1200, 780)
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
        tabs.addTab(WarehouseWidget(), "Inventory")
        tabs.addTab(ReceivingDeptWidget(), "Receiving")
        tabs.addTab(RequisitionsWidget(default_dept="Warehouse"),
                    "Purchase Requisitions")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = WarehouseMainMenu()
    w.show()
    sys.exit(app.exec())
