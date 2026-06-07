import sys
from PyQt6 import QtCore, QtWidgets
from .Budget_mgmt import BudgetManagementWidget, _apply_blue_palette

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


def _placeholder_tab(label):
    w = QtWidgets.QWidget()
    _apply_blue_palette(w)
    v = QtWidgets.QVBoxLayout(w)
    v.addStretch()
    lbl = QtWidgets.QLabel(f"{label}\n(Coming Soon)")
    lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("color:white;font-size:20px;font-weight:bold;")
    v.addWidget(lbl)
    v.addStretch()
    return w


class BudgetMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Budget Manager Menu")
        self.resize(1200, 760)
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
        tabs.addTab(BudgetManagementWidget(), "Budgets")
        tabs.addTab(_placeholder_tab("Budget Detail"), "Budget Detail")
        tabs.addTab(_placeholder_tab("Budget vs. Actual"), "Budget vs. Actual")
        tabs.addTab(_placeholder_tab("Variance Report"), "Variance Report")
        tabs.addTab(
    _placeholder_tab("Department Summaries"),
     "Department Summaries")
        tabs.addTab(_placeholder_tab("Approval Workflow"), "Approval Workflow")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = BudgetMgrMenu()
    w.show()
    sys.exit(app.exec())
