from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess
import sys
import os

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}\n"
    "QPushButton:hover{background-color:rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)


class Ui_CS_Mgr_menu(object):
    def setupUi(self, CS_Mgr_menu):
        CS_Mgr_menu.setObjectName("CS_Mgr_menu")
        CS_Mgr_menu.resize(800, 695)

        palette = QtGui.QPalette()
        for group in (QtGui.QPalette.ColorGroup.Active,
                      QtGui.QPalette.ColorGroup.Inactive,
                      QtGui.QPalette.ColorGroup.Disabled):
            palette.setColor(group, QtGui.QPalette.ColorRole.Window, QtGui.QColor(0, 85, 255))
            palette.setColor(group, QtGui.QPalette.ColorRole.Button, QtGui.QColor(0, 85, 255))
        CS_Mgr_menu.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=CS_Mgr_menu)
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 671))
        self.label.setStyleSheet(
            "background-image: url(customer_service.png); background-repeat: no-repeat;"
            " background-position: center; background-color: white;")
        self.label.setText("")

        font = QtGui.QFont()
        font.setPointSize(16)

        btn_data = [
            ("Customer Service", QtCore.QRect(10, 10, 231, 41), "Customer Service Menu"),
            ("CS Calls", QtCore.QRect(260, 10, 141, 41), "CS Calls"),
            ("Customer Entry", QtCore.QRect(420, 10, 201, 41), "Customer Entry"),
            ("CS Reports", QtCore.QRect(10, 645, 151, 41), "CS Reports"),
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

        CS_Mgr_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=CS_Mgr_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        CS_Mgr_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=CS_Mgr_menu)
        CS_Mgr_menu.setStatusBar(self.statusbar)
        self.retranslateUi(CS_Mgr_menu)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Customer Service Menu": "cs_menu.py",
            "CS Calls": "cs_calls.py",
            "Customer Entry": "customer_entry.py",
            "CS Reports": "cs_reports.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)
        else:
            QtWidgets.QMessageBox.information(None, pressed, f"{pressed} — coming soon.")

    def retranslateUi(self, CS_Mgr_menu):
        CS_Mgr_menu.setWindowTitle(
            QtCore.QCoreApplication.translate("CS_Mgr_menu", "Customer Service Manager Menu"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    CS_Mgr_menu = QtWidgets.QMainWindow()
    ui = Ui_CS_Mgr_menu()
    ui.setupUi(CS_Mgr_menu)
    CS_Mgr_menu.show()
    sys.exit(app.exec())
