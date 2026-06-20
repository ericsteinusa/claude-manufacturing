import sys
from .launch_utils import launch as _launch
from .accounts import get_current_user_email
from PyQt6 import QtCore, QtWidgets
from .qt_theme import apply_blue_palette as _apply_blue_palette

_DEPT_BTN = (
    "QPushButton{background-color:white;border:2px solid black;"
    "border-radius:10px;padding:12px 16px;font-size:16px;text-align:center;}"
    "QPushButton:hover{background-color:rgb(85,255,255);"
    "border-color:rgb(85,255,255);}"
)
DEPARTMENTS = [
    ("Accounting",            "Accounting_Main_menu.py"),
    ("Customer Service",      "cs_main_menu.py"),
    ("Engineering",           "engineering_Main_menu.py"),
    ("Finance",               "Finance_Main_menu.py"),
    ("Information Tech",      "IT_Main_Menu.py"),
    ("Legal",                 "Legal_Main_menu.py"),
    ("Maintenance",           "Maint_Main_menu.py"),
    ("Marketing",             "Marketing_Main_menu.py"),
    ("Personnel",             "Personnel_Main_menu.py"),
    ("Production",            "Production_Main_menu.py"),
    ("Purchasing",            "Purchasing_Main_menu.py"),
    ("Quality Assurance",     "QA_Main_menu.py"),
    ("Risk Management",       "Risk_mgmt_Main_menu.py"),
    ("Sales",                 "Sales_Main_menu.py"),
    ("Warehouse",             "Warehouse_Main_menu.py"),
    ("Budget Management",     "Budget_mgmt.py"),
    ("Reports",               "Reports_Main_menu.py"),
    ("Purchase Requisitions", "purchase_requisitions.py"),
]


class CompanyMainMenuWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ── Toolbar ───────────────────────────────────────────────
        toolbar = QtWidgets.QWidget()
        toolbar.setStyleSheet("background-color:rgb(0,60,180);")
        toolbar.setFixedHeight(44)
        tr = QtWidgets.QHBoxLayout(toolbar)
        tr.setContentsMargins(16, 0, 16, 0)
        tr.setSpacing(12)
        tr.addStretch()
        email = get_current_user_email()
        if email:
            user_lbl = QtWidgets.QLabel(f"Logged in as: {email}")
            user_lbl.setStyleSheet(
                "color:white;font-size:13px;padding-right:12px;")
            tr.addWidget(user_lbl)
        v.addWidget(toolbar)

        # ── Scrollable content ────────────────────────────────────
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QtWidgets.QWidget()
        _apply_blue_palette(inner)
        inner.setAutoFillBackground(True)

        cv = QtWidgets.QVBoxLayout(inner)
        cv.setContentsMargins(20, 40, 20, 40)
        cv.setSpacing(0)

        title = QtWidgets.QLabel("Company Main Menu")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color:white;font-size:22px;font-weight:bold;")
        cv.addWidget(title)
        cv.addSpacing(32)

        # 3-column grid of department buttons
        grid_wrap = QtWidgets.QWidget()
        _apply_blue_palette(grid_wrap)
        grid_wrap.setAutoFillBackground(True)
        grid = QtWidgets.QGridLayout(grid_wrap)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)

        for i, (label, script) in enumerate(DEPARTMENTS):
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(_DEPT_BTN)
            btn.setMinimumWidth(200)
            btn.setFixedHeight(60)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, s=script: _launch(s))
            grid.addWidget(btn, i // 3, i % 3)

        center = QtWidgets.QHBoxLayout()
        center.addStretch()
        center.addWidget(grid_wrap)
        center.addStretch()
        cv.addLayout(center)
        cv.addStretch()

        scroll.setWidget(inner)
        v.addWidget(scroll, 1)


class CompanyMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Company Main Menu")
        self.resize(1200, 760)
        _apply_blue_palette(self)
        self.setCentralWidget(CompanyMainMenuWidget())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = CompanyMainMenu()
    w.show()
    sys.exit(app.exec())
