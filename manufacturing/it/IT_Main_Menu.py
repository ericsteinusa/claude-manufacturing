import sys
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..button_nav import ButtonNav
from .IT_mgr import ITMgrWidget
from .IT_technician import ITTechnicianWidget

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 20px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


class ITMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Information Technologies")
        _apply_blue_palette(self)
        from ..purchase_requisitions import RequisitionsWidget
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(0)
        tabs = ButtonNav()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(ITMgrWidget(),                                    "IT Manager")
        tabs.addTab(ITTechnicianWidget(),                             "IT Technician")
        tabs.addTab(RequisitionsWidget("Information Technologies"),   "Purchase Requisitions")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ITMainMenu()
    w.showMaximized()
    sys.exit(app.exec())
