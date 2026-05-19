from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess, sys, os

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; border-radius: 10px;}\n"
    "QPushButton:hover{background-color:rgb(85, 255, 255); border: 2px solid rgb(85, 255, 255);}"
)


class Ui_eng_mgr(object):
    def setupUi(self, eng_mgr):
        eng_mgr.setObjectName("eng_mgr")
        eng_mgr.resize(800, 760)

        palette = QtGui.QPalette()
        for group in (QtGui.QPalette.ColorGroup.Active,
                      QtGui.QPalette.ColorGroup.Inactive,
                      QtGui.QPalette.ColorGroup.Disabled):
            palette.setColor(group, QtGui.QPalette.ColorRole.Window, QtGui.QColor(0, 85, 255))
            palette.setColor(group, QtGui.QPalette.ColorRole.Button, QtGui.QColor(0, 85, 255))
        eng_mgr.setPalette(palette)

        self.centralwidget = QtWidgets.QWidget(parent=eng_mgr)
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 721))
        self.label.setStyleSheet(
            "background-image: url(engineering.png); background-repeat: no-repeat;"
            " background-position: center; background-color: white;")
        self.label.setText("")

        font = QtGui.QFont(); font.setPointSize(16)

        btn_data = [
            ("Engineers",       QtCore.QRect( 10, 10, 151, 41), "Engineers"),
            ("Product Entry",   QtCore.QRect(180, 10, 171, 41), "Product Entry"),
            ("Supplier Entry",  QtCore.QRect(370, 10, 171, 41), "Supplier Entry"),
            ("Design Review",   QtCore.QRect( 10,710, 171, 41), "Design Review"),
            ("Eng. Reports",    QtCore.QRect(200,710, 161, 41), "Eng Reports"),
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

        eng_mgr.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=eng_mgr)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        eng_mgr.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=eng_mgr)
        eng_mgr.setStatusBar(self.statusbar)
        self.retranslateUi(eng_mgr)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Engineers":      "engineer.py",
            "Product Entry":  "product_entry_screen.py",
            "Supplier Entry": "Supplier_entry.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)
        else:
            QtWidgets.QMessageBox.information(None, pressed, f"{pressed} — coming soon.")

    def retranslateUi(self, eng_mgr):
        eng_mgr.setWindowTitle(
            QtCore.QCoreApplication.translate("eng_mgr", "Engineering Manager Menu"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    eng_mgr = QtWidgets.QMainWindow()
    ui = Ui_eng_mgr()
    ui.setupUi(eng_mgr)
    eng_mgr.show()
    sys.exit(app.exec())
