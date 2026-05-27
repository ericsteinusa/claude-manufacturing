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
    ("Inventory", "warehouse_inventory.py"),
]


class WarehouseMainMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Warehouse & Inventory Menu")
        self.resize(700, 300)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)

        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(60, 40, 60, 40)
        v.setSpacing(16)

        title = QtWidgets.QLabel("Warehouse & Inventory Menu")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;color:white;padding:8px;")
        v.addWidget(title)
        v.addStretch()

        for label, script in BUTTONS:
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.setFixedHeight(44)
            btn.setFont(QtGui.QFont("", 16))
            btn.clicked.connect(lambda chk=False, s=script: _launch(s))
            v.addWidget(btn)

        v.addStretch()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = WarehouseMainMenu()
    w.show()
    sys.exit(app.exec())
