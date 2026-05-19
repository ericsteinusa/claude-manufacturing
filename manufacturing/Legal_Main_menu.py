from PyQt6 import QtCore, QtGui, QtWidgets
import sys, subprocess, os

class Ui_Legal_main_menu(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("Legal_main_menu")
        MainWindow.resize(800, 600)
        palette = QtGui.QPalette()
        blue = QtGui.QColor(0, 85, 255)
        palette.setColor(QtGui.QPalette.ColorRole.Window, blue)
        palette.setColor(QtGui.QPalette.ColorRole.Button, blue)
        MainWindow.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        layout = QtWidgets.QVBoxLayout(self.centralwidget)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        title = QtWidgets.QLabel("Legal Main Menu")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;color:white;padding:8px;")
        layout.addWidget(title)

        BTN_STYLE = ("QPushButton{background-color:white;border:2px solid black;"
                     "border-radius:10px;padding:10px;font-size:16px;}"
                     "QPushButton:hover{background-color:rgb(85,255,255);}")

        buttons = [
            ("Contracts",            self._contracts),
            ("Compliance",           self._compliance),
            ("Litigation",           self._litigation),
            ("Intellectual Property",self._ip_mgmt),
            ("Employment Law",       self._emp_law),
        ]
        for label, slot in buttons:
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(BTN_STYLE)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        layout.addStretch()
        MainWindow.setCentralWidget(self.centralwidget)
        MainWindow.setWindowTitle("Legal")

    def _launch(self, script):
        d = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen([sys.executable, os.path.join(d, script)], cwd=d)

    def _contracts(self):   pass
    def _compliance(self):  pass
    def _litigation(self):  pass
    def _ip_mgmt(self):     pass
    def _emp_law(self):     pass


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    ui = Ui_Legal_main_menu()
    ui.setupUi(win)
    win.show()
    sys.exit(app.exec())
