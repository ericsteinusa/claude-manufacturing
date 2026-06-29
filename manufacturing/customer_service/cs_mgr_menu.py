import sys
from ..launch_utils import launch as _launch
from PyQt6 import QtCore, QtWidgets
from ..qt_theme import BUTTON_STYLE

from ..button_nav import ButtonNav
from .cs_calls_widget import CustomerServiceCallsWidget, _apply_blue_palette
from .cs_reports import CSReportsWidget
from .cs_staff_mgmt import CSStaffMgmtWidget
from .cs_satisfaction import CSSatisfactionWidget
from .cs_escalations import CSEscalationsWidget
from ..accounts import get_current_user_email

TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


def _launch_tab(script, label):
    w = QtWidgets.QWidget()
    _apply_blue_palette(w)
    v = QtWidgets.QVBoxLayout(w)
    v.addStretch()
    lbl = QtWidgets.QLabel(label)
    lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("color:white;font-size:20px;font-weight:bold;")
    v.addWidget(lbl)
    v.addSpacing(12)
    btn = QtWidgets.QPushButton(f"Open {label}")
    btn.setStyleSheet(BUTTON_STYLE)
    btn.setFixedHeight(44)
    btn.setFixedWidth(260)
    btn.clicked.connect(lambda: _launch(script))
    row = QtWidgets.QHBoxLayout()
    row.addStretch()
    row.addWidget(btn)
    row.addStretch()
    v.addLayout(row)
    v.addStretch()
    return w


class CSMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Customer Service Manager Menu — {email}" if email
                 else "Customer Service Manager Menu")
        self.setWindowTitle(title)
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
        tabs.addTab(CustomerServiceCallsWidget(), "CS Calls")
        tabs.addTab(CSReportsWidget(), "CS Reports")
        tabs.addTab(CSStaffMgmtWidget(), "CS Staff")
        tabs.addTab(CSSatisfactionWidget(), "Satisfaction")
        tabs.addTab(CSEscalationsWidget(), "Escalations")
        tabs.addTab(
    _launch_tab(
        "customer_entry.py",
        "Customer Entry"),
         "Customer Entry")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = CSMgrMenu()
    w.showMaximized()
    sys.exit(app.exec())
