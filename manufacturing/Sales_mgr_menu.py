from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess, sys, os

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}\n"
    "QPushButton:hover{background-color:rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)


class Ui_Sales_mgr_menu(object):
    def setupUi(self, Sales_mgr_menu):
        Sales_mgr_menu.setObjectName("Sales_mgr_menu")
        Sales_mgr_menu.resize(800, 600)

        palette = QtGui.QPalette()
        for group in (QtGui.QPalette.ColorGroup.Active,
                      QtGui.QPalette.ColorGroup.Inactive,
                      QtGui.QPalette.ColorGroup.Disabled):
            palette.setColor(group, QtGui.QPalette.ColorRole.Window, QtGui.QColor(0, 85, 255))
            palette.setColor(group, QtGui.QPalette.ColorRole.Button, QtGui.QColor(0, 85, 255))
        Sales_mgr_menu.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=Sales_mgr_menu)
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 60, 801, 501))
        self.label.setStyleSheet(
            "background-image: url(sales.png); background-repeat: no-repeat;"
            " background-position: center; background-color: white;")
        self.label.setText("")

        font = QtGui.QFont(); font.setPointSize(16)

        btn_data = [
            ("Sales",             QtCore.QRect( 10, 10, 151, 41), "Sales Menu"),
            ("Customer Entry",    QtCore.QRect(180, 10, 191, 41), "Customer Entry"),
            ("Accts Receivable",  QtCore.QRect(390, 10, 201, 41), "Accts Receivable"),
            ("Sales Reports",     QtCore.QRect( 10,510, 181, 41), "Sales Reports"),
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

        Sales_mgr_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Sales_mgr_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        Sales_mgr_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Sales_mgr_menu)
        Sales_mgr_menu.setStatusBar(self.statusbar)
        self.retranslateUi(Sales_mgr_menu)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Sales Menu":      "Sales_menu.py",
            "Customer Entry":  "customer_entry.py",
            "Accts Receivable": "Accounts_receivable.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)
        else:
            QtWidgets.QMessageBox.information(None, pressed, f"{pressed} — coming soon.")

    def retranslateUi(self, Sales_mgr_menu):
        Sales_mgr_menu.setWindowTitle(
            QtCore.QCoreApplication.translate("Sales_mgr_menu", "Sales Manager Menu"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    Sales_mgr_menu = QtWidgets.QMainWindow()
    ui = Ui_Sales_mgr_menu()
    ui.setupUi(Sales_mgr_menu)
    Sales_mgr_menu.show()
    sys.exit(app.exec())
