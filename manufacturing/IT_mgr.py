from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess
import sys
import os

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}\n"
    "QPushButton:hover{background-color:rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 695)

        palette = QtGui.QPalette()
        for group in (QtGui.QPalette.ColorGroup.Active,
                      QtGui.QPalette.ColorGroup.Inactive,
                      QtGui.QPalette.ColorGroup.Disabled):
            palette.setColor(group, QtGui.QPalette.ColorRole.Window, QtGui.QColor(0, 85, 255))
            palette.setColor(group, QtGui.QPalette.ColorRole.Button, QtGui.QColor(0, 85, 255))
        MainWindow.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 651))
        self.label.setStyleSheet(
            "background-image: url(IT_picture2.png); background-repeat: no-repeat;"
            " background-position: center; background-color: white;")
        self.label.setText("")

        font = QtGui.QFont()
        font.setPointSize(16)

        btn_data = [
            ("IT Technician", QtCore.QRect(10, 10, 191, 41), "IT Technician"),
            ("IT Tasks", QtCore.QRect(220, 10, 141, 41), "IT Tasks"),
            ("System Admin", QtCore.QRect(10, 645, 161, 41), "System Admin"),
            ("IT Reports", QtCore.QRect(190, 645, 151, 41), "IT Reports"),
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

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=MainWindow)
        MainWindow.setStatusBar(self.statusbar)
        self.retranslateUi(MainWindow)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "IT Technician": "IT_technician.py",
            "IT Tasks": "IT_Tasks.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)
        else:
            QtWidgets.QMessageBox.information(None, pressed, f"{pressed} — coming soon.")

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(
            QtCore.QCoreApplication.translate("MainWindow", "IT Manager Menu"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())
