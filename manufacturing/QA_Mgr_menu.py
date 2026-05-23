from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess
import sys
import os

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}\n"
    "QPushButton:hover{background-color:rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)


class Ui_QA_mgr_menu(object):
    def setupUi(self, QA_mgr_menu):
        QA_mgr_menu.setObjectName("QA_mgr_menu")
        QA_mgr_menu.resize(800, 600)

        palette = QtGui.QPalette()
        for group in (QtGui.QPalette.ColorGroup.Active,
                      QtGui.QPalette.ColorGroup.Inactive,
                      QtGui.QPalette.ColorGroup.Disabled):
            palette.setColor(group, QtGui.QPalette.ColorRole.Window, QtGui.QColor(0, 85, 255))
            palette.setColor(group, QtGui.QPalette.ColorRole.Button, QtGui.QColor(0, 85, 255))
        QA_mgr_menu.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=QA_mgr_menu)
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 60, 801, 521))
        self.label.setStyleSheet(
            "background-image: url(Quality-Assurance.png); background-repeat: no-repeat;"
            " background-position: center; background-color: white;")
        self.label.setText("")

        font = QtGui.QFont()
        font.setPointSize(16)

        btn_data = [
            ("Quality Assurance", QtCore.QRect(10, 10, 211, 41), "Quality Assurance Menu"),
            ("QA Lab", QtCore.QRect(240, 10, 141, 41), "QA Lab"),
            ("Inspection Reports", QtCore.QRect(10, 510, 211, 41), "Inspection Reports"),
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

        QA_mgr_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=QA_mgr_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        QA_mgr_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=QA_mgr_menu)
        QA_mgr_menu.setStatusBar(self.statusbar)
        self.retranslateUi(QA_mgr_menu)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Quality Assurance Menu": "Quality_Assurance_menu.py",
            "QA Lab": "QA_Lab_menu.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)
        else:
            QtWidgets.QMessageBox.information(None, pressed, f"{pressed} — coming soon.")

    def retranslateUi(self, QA_mgr_menu):
        QA_mgr_menu.setWindowTitle(
            QtCore.QCoreApplication.translate("QA_mgr_menu", "QA Manager Menu"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    QA_mgr_menu = QtWidgets.QMainWindow()
    ui = Ui_QA_mgr_menu()
    ui.setupUi(QA_mgr_menu)
    QA_mgr_menu.show()
    sys.exit(app.exec())
