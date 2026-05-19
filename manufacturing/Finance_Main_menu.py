from PyQt6 import QtCore, QtGui, QtWidgets
import sys, subprocess, os

class Ui_Finance_main_menu(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("Finance_main_menu")
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

        title = QtWidgets.QLabel("Finance Main Menu")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;color:white;padding:8px;")
        layout.addWidget(title)

        BTN_STYLE = ("QPushButton{background-color:white;border:2px solid black;"
                     "border-radius:10px;padding:10px;font-size:16px;}"
                     "QPushButton:hover{background-color:rgb(85,255,255);}")

        buttons = [
            ("Financial Analysis",   self._financial_analysis),
            ("Financial Reporting",  self._financial_reporting),
            ("Treasury Operations",  self._treasury_ops),
            ("Capital Management",   self._capital_mgmt),
            ("Tax Planning",         self._tax_planning),
        ]
        for label, slot in buttons:
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(BTN_STYLE)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        layout.addStretch()
        MainWindow.setCentralWidget(self.centralwidget)
        MainWindow.setWindowTitle("Finance")

    def _launch(self, script):
        d = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen([sys.executable, os.path.join(d, script)], cwd=d)

    def _financial_analysis(self):  pass
    def _financial_reporting(self): pass
    def _treasury_ops(self):        pass
    def _capital_mgmt(self):        pass
    def _tax_planning(self):        pass


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    ui = Ui_Finance_main_menu()
    ui.setupUi(win)
    win.show()
    sys.exit(app.exec())
