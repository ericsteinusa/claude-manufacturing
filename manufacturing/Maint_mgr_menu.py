from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess

class Ui_Maint_mgr_menu(object):
    def setupUi(self, Maint_mgr_menu):
        Maint_mgr_menu.setObjectName("Maint_mgr_menu")
        Maint_mgr_menu.resize(800, 600)
        Maint_mgr_menu.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.centralwidget = QtWidgets.QWidget(parent=Maint_mgr_menu)
        self.centralwidget.setObjectName("centralwidget")
        self.maint_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Maintenance"))
        self.maint_Button.setGeometry(QtCore.QRect(10, 10, 161, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.maint_Button.setFont(font)
        self.maint_Button.setAutoDefault(False)
        self.maint_Button.setObjectName("maint_Button")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 581))
        self.label.setStyleSheet("background-image: url(Maintenance.png);\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        self.label.setText("")
        self.label.setObjectName("label")
        self.label.raise_()
        self.maint_Button.raise_()
        Maint_mgr_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Maint_mgr_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        Maint_mgr_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Maint_mgr_menu)
        self.statusbar.setObjectName("statusbar")
        Maint_mgr_menu.setStatusBar(self.statusbar)

        self.retranslateUi(Maint_mgr_menu)
        QtCore.QMetaObject.connectSlotsByName(Maint_mgr_menu)

    def press_it(self, pressed):
        if pressed == "Maintenance":
            subprocess.Popen(["python3", "Maint_Maint_menu.py"])

    def retranslateUi(self, Maint_mgr_menu):
        _translate = QtCore.QCoreApplication.translate
        Maint_mgr_menu.setWindowTitle(_translate("Maint_mgr_menu", "Maintenance Manager Menu"))
        self.maint_Button.setText(_translate("Maint_mgr_menu", "Maintenance"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Maint_mgr_menu = QtWidgets.QMainWindow()
    ui = Ui_Maint_mgr_menu()
    ui.setupUi(Maint_mgr_menu)
    Maint_mgr_menu.show()
    sys.exit(app.exec())
