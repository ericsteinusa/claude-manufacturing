import sys, os, subprocess
from PyQt6 import QtCore, QtGui, QtWidgets

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)


def _apply_blue_palette(widget):
    pal = widget.palette()
    for group in (QtGui.QPalette.ColorGroup.Active,
                  QtGui.QPalette.ColorGroup.Inactive,
                  QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(group, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(group, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _launch(script):
    _dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)


BUTTONS = [
    ("Accounting Manager",  "Accounting_manager.py"),
    ("Accounts Payable",    "Accounts_payable.py"),
    ("Accounts Receivable", "Accounts_receivable.py"),
    ("Credit Department",   "Credit_dept.py"),
    ("Payroll",             "Payroll_dept.py"),
    ("General Ledger",      "General_ledger.py"),
    ("Budget Management",   "Budget_mgmt.py"),
    ("Bank Reconciliation", "Bank_reconciliation.py"),
]


class AccountingMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Accounting Main Menu")
        self.resize(800, 520)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)

        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(30, 20, 30, 20)
        outer.setSpacing(12)

        title = QtWidgets.QLabel("Accounting Main Menu")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;color:white;padding:8px;")
        outer.addWidget(title)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)
        cols = 2
        for i, (label, script) in enumerate(BUTTONS):
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.setFixedHeight(44)
            btn.setFont(QtGui.QFont("", 14))
            btn.clicked.connect(lambda chk=False, s=script: _launch(s))
            grid.addWidget(btn, i // cols, i % cols)

        outer.addLayout(grid)
        outer.addStretch()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = AccountingMainMenu()
    w.show()
    sys.exit(app.exec())
