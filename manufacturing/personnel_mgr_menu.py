from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess
import sys
import os

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}\n"
    "QPushButton:hover{background-color:rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)


class Ui_Personnel_mgr_menu(object):
    def setupUi(self, Personnel_mgr_menu):
        Personnel_mgr_menu.setObjectName("Personnel_mgr_menu")
        Personnel_mgr_menu.resize(806, 600)

        palette = QtGui.QPalette()
        for group in (QtGui.QPalette.ColorGroup.Active,
                      QtGui.QPalette.ColorGroup.Inactive,
                      QtGui.QPalette.ColorGroup.Disabled):
            palette.setColor(group, QtGui.QPalette.ColorRole.Window, QtGui.QColor(0, 85, 255))
            palette.setColor(group, QtGui.QPalette.ColorRole.Button, QtGui.QColor(0, 85, 255))
        Personnel_mgr_menu.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=Personnel_mgr_menu)
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 60, 821, 521))
        self.label.setStyleSheet(
            "background-image: url(Personnel2.png); background-repeat: no-repeat;"
            " background-position: center; background-color: white;")
        self.label.setText("")

        font = QtGui.QFont()
        font.setPointSize(16)

        btn_data = [
            ("Personnel", QtCore.QRect(10, 10, 161, 41), "Personnel Menu"),
            ("Personnel CRM", QtCore.QRect(190, 10, 181, 41), "Personnel CRM"),
            ("Dept Entry", QtCore.QRect(390, 10, 151, 41), "Dept Entry"),
            ("Dept Sub Entry", QtCore.QRect(560, 10, 171, 41), "Dept Sub Entry"),
            ("Payroll", QtCore.QRect(10, 510, 151, 41), "Payroll"),
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

        Personnel_mgr_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Personnel_mgr_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 806, 21))
        Personnel_mgr_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Personnel_mgr_menu)
        Personnel_mgr_menu.setStatusBar(self.statusbar)
        self.retranslateUi(Personnel_mgr_menu)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Personnel Menu": "personnel_menu.py",
            "Personnel CRM": "personnel_crm.py",
            "Dept Entry": "dept_entry.py",
            "Dept Sub Entry": "dept_sub_entry.py",
            "Payroll": "Payroll_dept.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)
        else:
            QtWidgets.QMessageBox.information(None, pressed, f"{pressed} — coming soon.")

    def retranslateUi(self, Personnel_mgr_menu):
        Personnel_mgr_menu.setWindowTitle(
            QtCore.QCoreApplication.translate("Personnel_mgr_menu", "Personnel Manager Menu"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    Personnel_mgr_menu = QtWidgets.QMainWindow()
    ui = Ui_Personnel_mgr_menu()
    ui.setupUi(Personnel_mgr_menu)
    Personnel_mgr_menu.show()
    sys.exit(app.exec())
