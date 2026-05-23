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


class Ui_Maint_maint_menu(object):
    def setupUi(self, Maint_maint_menu):
        Maint_maint_menu.setObjectName("Maint_maint_menu")
        Maint_maint_menu.resize(800, 600)

        palette = QtGui.QPalette()
        for group in (QtGui.QPalette.ColorGroup.Active,
                      QtGui.QPalette.ColorGroup.Inactive,
                      QtGui.QPalette.ColorGroup.Disabled):
            palette.setColor(group, QtGui.QPalette.ColorRole.Window,
                             QtGui.QColor(0, 85, 255))
            palette.setColor(group, QtGui.QPalette.ColorRole.Button,
                             QtGui.QColor(0, 85, 255))
        Maint_maint_menu.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=Maint_maint_menu)
        self.centralwidget.setObjectName("centralwidget")

        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 60, 801, 511))
        self.label.setStyleSheet(
            "background-image: url(Maintenance.png);\n"
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
            ("Work Orders", QtCore.QRect(10, 10, 181, 41), "Work Orders"),
            ("Equipment List", QtCore.QRect(210, 10, 181, 41), "Equipment List"),
            ("Parts Request", QtCore.QRect(410, 10, 171, 41), "Parts Request"),
            ("Maint. Schedule", QtCore.QRect(10, 510, 181, 41), "Maintenance Schedule"),
            ("Safety Inspection", QtCore.QRect(210, 510, 201, 41), "Safety Inspection"),
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

        Maint_maint_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Maint_maint_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        Maint_maint_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Maint_maint_menu)
        Maint_maint_menu.setStatusBar(self.statusbar)

        self.retranslateUi(Maint_maint_menu)
        QtCore.QMetaObject.connectSlotsByName(Maint_maint_menu)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {}
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)
        else:
            QtWidgets.QMessageBox.information(None, pressed, f"{pressed} — coming soon.")

    def retranslateUi(self, Maint_maint_menu):
        _translate = QtCore.QCoreApplication.translate
        Maint_maint_menu.setWindowTitle(_translate("Maint_maint_menu", "Maintenance Menu"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    Maint_maint_menu = QtWidgets.QMainWindow()
    ui = Ui_Maint_maint_menu()
    ui.setupUi(Maint_maint_menu)
    Maint_maint_menu.show()
    sys.exit(app.exec())
