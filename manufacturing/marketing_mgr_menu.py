from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess

class Ui_Marketing_mgr_menu(object):
    def setupUi(self, Marketing_mgr_menu):
        Marketing_mgr_menu.setObjectName("Marketing_mgr_menu")
        Marketing_mgr_menu.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(parent=Marketing_mgr_menu)
        self.centralwidget.setObjectName("centralwidget")
        self.Marketing = QtWidgets.QLabel(parent=self.centralwidget)
        self.Marketing.setGeometry(QtCore.QRect(0, 0, 801, 561))
        self.Marketing.setStyleSheet("background-image: url(Marketing.png);\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        self.Marketing.setText("")
        self.Marketing.setObjectName("Marketing")
        self.Marketing_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Marketing Menu"))
        self.Marketing_Button.setGeometry(QtCore.QRect(40, 10, 211, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Marketing_Button.setFont(font)
        self.Marketing_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.Marketing_Button.setAutoDefault(False)
        self.Marketing_Button.setObjectName("Marketing_Button")
        Marketing_mgr_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Marketing_mgr_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        Marketing_mgr_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Marketing_mgr_menu)
        self.statusbar.setObjectName("statusbar")
        Marketing_mgr_menu.setStatusBar(self.statusbar)

        self.retranslateUi(Marketing_mgr_menu)
        QtCore.QMetaObject.connectSlotsByName(Marketing_mgr_menu)

    def press_it(self, pressed):
        if pressed == "Marketing Menu":
            subprocess.Popen(["python3", "marketing_menu.py"])

    def retranslateUi(self, Marketing_mgr_menu):
        _translate = QtCore.QCoreApplication.translate
        Marketing_mgr_menu.setWindowTitle(_translate("Marketing_mgr_menu", "Marketing Manager Menu"))
        self.Marketing_Button.setText(_translate("Marketing_mgr_menu", "Marketing"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Marketing_mgr_menu = QtWidgets.QMainWindow()
    ui = Ui_Marketing_mgr_menu()
    ui.setupUi(Marketing_mgr_menu)
    Marketing_mgr_menu.show()
    sys.exit(app.exec())
