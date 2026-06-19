import sys
from .launch_utils import launch as _launch
from .purchase_requisitions import RequisitionApprovalsWidget
from PyQt6 import QtCore, QtGui, QtWidgets
from .button_nav import ButtonNav
from .accounts import get_current_user_email


def _apply_blue_palette(widget):
    pal = QtGui.QPalette()
    for g in (QtGui.QPalette.ColorGroup.Active,
              QtGui.QPalette.ColorGroup.Inactive,
              QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(
    g,
    QtGui.QPalette.ColorRole.Window,
    QtGui.QColor(
        0,
        85,
         255))
        pal.setColor(
    g,
    QtGui.QPalette.ColorRole.Button,
    QtGui.QColor(
        0,
        85,
         255))
    widget.setPalette(pal)


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


class PurchasingMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Purchasing Manager Menu — {email}" if email
                 else "Purchasing Manager Menu")
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
        tabs.addTab(
    _launch_tab(
        "Supplier_entry.py",
        "Supplier Entry"),
         "Supplier Entry")
        tabs.addTab(
    _launch_tab(
        "product_entry_screen.py",
        "Product Entry"),
         "Product Entry")
        tabs.addTab(RequisitionApprovalsWidget(), "Requisition Approvals")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = PurchasingMgrMenu()
    w.show()
    sys.exit(app.exec())
