from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess
import sys
import os

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}\n"
    "QPushButton:hover{background-color:rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)


class Ui_Warehouse_Main_menu(object):
    def setupUi(self, Warehouse_Main_menu):
        Warehouse_Main_menu.setObjectName("Warehouse_Main_menu")
        Warehouse_Main_menu.resize(800, 695)

        palette = QtGui.QPalette()
        for group in (QtGui.QPalette.ColorGroup.Active,
                      QtGui.QPalette.ColorGroup.Inactive,
                      QtGui.QPalette.ColorGroup.Disabled):
            palette.setColor(group, QtGui.QPalette.ColorRole.Window, QtGui.QColor(0, 85, 255))
            palette.setColor(group, QtGui.QPalette.ColorRole.Button, QtGui.QColor(0, 85, 255))
        Warehouse_Main_menu.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=Warehouse_Main_menu)
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 671))
        self.label.setStyleSheet(
            "background-image: url(warehouse.png); background-repeat: no-repeat;"
            " background-position: center; background-color: white;")
        self.label.setText("")

        font = QtGui.QFont()
        font.setPointSize(16)

        btn_data = [
            ("Warehouse", QtCore.QRect(10, 10, 201, 41), "Warehouse Menu"),
            ("Inventory", QtCore.QRect(230, 10, 181, 41), "Inventory"),
        ]

        self._btns = []
        for text, geom, key in btn_data:
            b = QtWidgets.QPushButton(parent=self.centralwidget,
                                      clicked=lambda chk, k=key: self.press_it(k))
            b.setGeometry(geom)
            b.setFont(font)
            b.setStyleSheet(BUTTON_STYLE)
            b.setAutoDefault(False)
            b.setText(text)
            self._btns.append(b)

        self.label.raise_()
        for b in self._btns:
            b.raise_()

        Warehouse_Main_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Warehouse_Main_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        Warehouse_Main_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Warehouse_Main_menu)
        Warehouse_Main_menu.setStatusBar(self.statusbar)
        self.retranslateUi(Warehouse_Main_menu)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Inventory": "warehouse_inventory.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)
        else:
            QtWidgets.QMessageBox.information(None, pressed, f"{pressed} — coming soon.")

    def retranslateUi(self, Warehouse_Main_menu):
        Warehouse_Main_menu.setWindowTitle(
            QtCore.QCoreApplication.translate("Warehouse_Main_menu", "Warehouse & Inventory Menu"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    Warehouse_Main_menu = QtWidgets.QMainWindow()
    ui = Ui_Warehouse_Main_menu()
    ui.setupUi(Warehouse_Main_menu)
    Warehouse_Main_menu.show()
    sys.exit(app.exec())
