import sys
from .launch_utils import launch as _launch
from PyQt6 import QtCore, QtGui, QtWidgets
from .button_nav import ButtonNav

from .engineer import _apply_blue_palette
from .accounts import get_current_user_email
from .eng_design_review import DesignReviewWidget
from .eng_reports import EngReportsWidget

BLUE = QtGui.QColor(0, 85, 255)
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
    """A tab widget with a centered launch button for external tools."""
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


class EngMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Engineering Manager Menu — {email}" if email
                 else "Engineering Manager Menu")
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

        # Engineers tab: nested Projects + Tasks tabs
        eng_w = QtWidgets.QWidget()
        _apply_blue_palette(eng_w)
        eng_v = QtWidgets.QVBoxLayout(eng_w)
        eng_v.setContentsMargins(0, 4, 0, 0)
        eng_tabs = ButtonNav()
        eng_tabs.setStyleSheet(TAB_STYLE)
        eng_tabs.addTab(
    _launch_tab(
        "engineer.py",
        "Engineering Projects"),
         "Engineering Projects")
        eng_tabs.addTab(
    _launch_tab(
        "engineer.py",
        "Engineering Tasks"),
         "Engineering Tasks")
        eng_v.addWidget(eng_tabs)
        tabs.addTab(eng_w, "Engineers")

        tabs.addTab(DesignReviewWidget(), "Design Reviews")
        tabs.addTab(EngReportsWidget(), "Eng Reports")
        tabs.addTab(
    _launch_tab(
        "product_entry_screen.py",
        "Product Entry"),
         "Product Entry")
        tabs.addTab(
    _launch_tab(
        "Supplier_entry.py",
        "Supplier Entry"),
         "Supplier Entry")

        v.addWidget(tabs)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = EngMgrMenu()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
