import sys, os, subprocess
from PyQt6 import QtCore, QtGui, QtWidgets
from prod_prod_menu import WorkOrdersWidget, _apply_blue_palette
from prod_ship_dept import ShippingDeptWidget

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class ProdMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Production Manager Menu")
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget(); _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8); v.setSpacing(0)
        tabs = QtWidgets.QTabWidget(); tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(WorkOrdersWidget(), "Production")
        tabs.addTab(ShippingDeptWidget(), "Shipping")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ProdMgrMenu(); w.show()
    sys.exit(app.exec())
