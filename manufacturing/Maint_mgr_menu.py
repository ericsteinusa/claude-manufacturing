from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess, sys, os

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}\n"
    "QPushButton:hover{background-color:rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)


class Ui_Maint_mgr_menu(object):
    def setupUi(self, Maint_mgr_menu):
        Maint_mgr_menu.setObjectName("Maint_mgr_menu")
        Maint_mgr_menu.resize(800, 600)

        palette = QtGui.QPalette()
        for group in (QtGui.QPalette.ColorGroup.Active,
                      QtGui.QPalette.ColorGroup.Inactive,
                      QtGui.QPalette.ColorGroup.Disabled):
            palette.setColor(group, QtGui.QPalette.ColorRole.Window, QtGui.QColor(0, 85, 255))
            palette.setColor(group, QtGui.QPalette.ColorRole.Button, QtGui.QColor(0, 85, 255))
        Maint_mgr_menu.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=Maint_mgr_menu)
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 581))
        self.label.setStyleSheet(
            "background-image: url(Maintenance.png); background-repeat: no-repeat;"
            " background-position: center; background-color: white;")
        self.label.setText("")

        font = QtGui.QFont(); font.setPointSize(16)

        btn_data = [
            ("Maintenance",    QtCore.QRect( 10, 10, 161, 41), "Maintenance"),
            ("Work Orders",    QtCore.QRect(190, 10, 161, 41), "Work Orders"),
            ("Equip. Reports", QtCore.QRect(370, 10, 171, 41), "Equip Reports"),
            ("Safety Reports", QtCore.QRect( 10,510, 171, 41), "Safety Reports"),
        ]

        self._btns = []
        for text, geom, key in btn_data:
            b = QtWidgets.QPushButton(parent=self.centralwidget,
                                      clicked=lambda chk, k=key: self.press_it(k))
            b.setGeometry(geom); b.setFont(font)
            b.setStyleSheet(BUTTON_STYLE); b.setAutoDefault(False); b.setText(text)
            self._btns.append(b)

        self.label.raise_()
        for b in self._btns: b.raise_()

        Maint_mgr_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Maint_mgr_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        Maint_mgr_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Maint_mgr_menu)
        Maint_mgr_menu.setStatusBar(self.statusbar)
        self.retranslateUi(Maint_mgr_menu)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Maintenance": "Maint_Maint_menu.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)
        else:
            QtWidgets.QMessageBox.information(None, pressed, f"{pressed} — coming soon.")

    def retranslateUi(self, Maint_mgr_menu):
        Maint_mgr_menu.setWindowTitle(
            QtCore.QCoreApplication.translate("Maint_mgr_menu", "Maintenance Manager Menu"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    Maint_mgr_menu = QtWidgets.QMainWindow()
    ui = Ui_Maint_mgr_menu()
    ui.setupUi(Maint_mgr_menu)
    Maint_mgr_menu.show()
    sys.exit(app.exec())
