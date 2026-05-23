from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess
import sys
import os

BUTTON_STYLE = (
    "QPushButton{background-color: white;\n"
    "border: 2px solid black;\n"
    "border-radius: 10px;}\n"
    "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
    "border: 2px solid rgb(85, 255, 255);\n"
    "}"
)


class Ui_Marketing_menu(object):
    def setupUi(self, Marketing_menu):
        Marketing_menu.setObjectName("Marketing_menu")
        Marketing_menu.resize(800, 600)

        palette = QtGui.QPalette()
        for group in (QtGui.QPalette.ColorGroup.Active,
                      QtGui.QPalette.ColorGroup.Inactive,
                      QtGui.QPalette.ColorGroup.Disabled):
            palette.setColor(group, QtGui.QPalette.ColorRole.Window,
                             QtGui.QColor(0, 85, 255))
            palette.setColor(group, QtGui.QPalette.ColorRole.Button,
                             QtGui.QColor(0, 85, 255))
        Marketing_menu.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=Marketing_menu)
        self.centralwidget.setObjectName("centralwidget")

        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 60, 801, 511))
        self.label.setStyleSheet(
            "background-image: url(Marketing.png);\n"
            "background-repeat: no-repeat;\n"
            "background-position: center;\n"
            "background-attachment: fixed;\n"
            "background-color: white;"
        )
        self.label.setText("")
        self.label.setObjectName("label")

        font = QtGui.QFont()
        font.setPointSize(16)

        btn_data = [
            ("Sales Orders", QtCore.QRect(10, 10, 191, 41), "Sales Orders"),
            ("Customer Contacts", QtCore.QRect(220, 10, 211, 41), "Customer Contacts"),
            ("Campaign Tracker", QtCore.QRect(10, 510, 191, 41), "Campaign Tracker"),
            ("Market Research", QtCore.QRect(220, 510, 191, 41), "Market Research"),
            ("Marketing Reports", QtCore.QRect(430, 510, 211, 41), "Marketing Reports"),
        ]

        self._buttons = {}
        for text, geom, key in btn_data:
            btn = QtWidgets.QPushButton(
                parent=self.centralwidget,
                clicked=lambda checked, k=key: self.press_it(k)
            )
            btn.setGeometry(geom)
            btn.setFont(font)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.setAutoDefault(False)
            btn.setText(text)
            self._buttons[key] = btn

        self.label.raise_()
        for btn in self._buttons.values():
            btn.raise_()

        Marketing_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Marketing_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        Marketing_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Marketing_menu)
        Marketing_menu.setStatusBar(self.statusbar)

        self.retranslateUi(Marketing_menu)
        QtCore.QMetaObject.connectSlotsByName(Marketing_menu)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Sales Orders": "Sales_menu.py",
            "Customer Contacts": "customer_entry.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)
        else:
            QtWidgets.QMessageBox.information(None, pressed, f"{pressed} — coming soon.")

    def retranslateUi(self, Marketing_menu):
        _translate = QtCore.QCoreApplication.translate
        Marketing_menu.setWindowTitle(_translate("Marketing_menu", "Marketing Menu"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    Marketing_menu = QtWidgets.QMainWindow()
    ui = Ui_Marketing_menu()
    ui.setupUi(Marketing_menu)
    Marketing_menu.show()
    sys.exit(app.exec())
