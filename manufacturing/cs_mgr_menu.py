from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess

class Ui_CS_Mgr_menu(object):
    def setupUi(self, CS_Mgr_menu):
        CS_Mgr_menu.setObjectName("CS_Mgr_menu")
        CS_Mgr_menu.resize(800, 695)
        self.centralwidget = QtWidgets.QWidget(parent=CS_Mgr_menu)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 671))
        self.label.setStyleSheet("background-image: url(customer_service.png);\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        self.label.setText("")
        self.label.setObjectName("label")
        self.cs_menu_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Customer Service Menu"))
        self.cs_menu_Button.setGeometry(QtCore.QRect(10, 10, 251, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.cs_menu_Button.setFont(font)
        self.cs_menu_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;\n}"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n}"
"")
        self.cs_menu_Button.setAutoDefault(False)
        self.cs_menu_Button.setObjectName("cs_menu_Button")
        CS_Mgr_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=CS_Mgr_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        CS_Mgr_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=CS_Mgr_menu)
        self.statusbar.setObjectName("statusbar")
        CS_Mgr_menu.setStatusBar(self.statusbar)

        self.retranslateUi(CS_Mgr_menu)
        QtCore.QMetaObject.connectSlotsByName(CS_Mgr_menu)

    def press_it(self, pressed):
        if pressed == "Customer Service Menu":
                subprocess.Popen(["python3", "cs_menu.py"])

    def retranslateUi(self, CS_Mgr_menu):
        _translate = QtCore.QCoreApplication.translate
        CS_Mgr_menu.setWindowTitle(_translate("CS_Mgr_menu", "Customer Service Manager Menu"))
        self.cs_menu_Button.setText(_translate("CS_Mgr_menu", "Customer Service Menu"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    CS_Mgr_menu = QtWidgets.QMainWindow()
    ui = Ui_CS_Mgr_menu()
    ui.setupUi(CS_Mgr_menu)
    CS_Mgr_menu.show()
    sys.exit(app.exec())
