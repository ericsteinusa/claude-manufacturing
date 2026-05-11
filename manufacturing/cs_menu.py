from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess, sys, os

class Ui_Customer_service_menu(object):
    def setupUi(self, Customer_service_menu):
        Customer_service_menu.setObjectName("Customer_service_menu")
        Customer_service_menu.resize(800, 694)
        self.centralwidget = QtWidgets.QWidget(parent=Customer_service_menu)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 661))
        self.label.setStyleSheet("background-image: url(customer_service.png);\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        self.label.setText("")
        self.label.setObjectName("label")
        self.CS_calls_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Customer Service Calls"))
        self.CS_calls_Button.setGeometry(QtCore.QRect(10, 20, 231, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.CS_calls_Button.setFont(font)
        self.CS_calls_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;\n}"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n}"
"")
        self.CS_calls_Button.setAutoDefault(False)
        self.CS_calls_Button.setObjectName("CS_calls_Button")
        self.Cust_entry_button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Customer Entry Screen"))
        self.Cust_entry_button.setGeometry(QtCore.QRect(10, 80, 241, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Cust_entry_button.setFont(font)
        self.Cust_entry_button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;\n}"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n}"
"")
        self.Cust_entry_button.setAutoDefault(False)
        self.Cust_entry_button.setObjectName("Cust_entry_button")
        Customer_service_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Customer_service_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        Customer_service_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Customer_service_menu)
        self.statusbar.setObjectName("statusbar")
        Customer_service_menu.setStatusBar(self.statusbar)

        self.retranslateUi(Customer_service_menu)
        QtCore.QMetaObject.connectSlotsByName(Customer_service_menu)
   
    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Customer Service Calls": "cs_calls.py",
            "Customer Entry Screen":  "customer_entry.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)

    def retranslateUi(self, Customer_service_menu):
        _translate = QtCore.QCoreApplication.translate
        Customer_service_menu.setWindowTitle(_translate("Customer_service_menu", "Customer Service Menu"))
        self.CS_calls_Button.setText(_translate("Customer_service_menu", "Customer Service Calls"))
        self.Cust_entry_button.setText(_translate("customer_service_menu", "Customer Entry Screen"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Customer_service_menu = QtWidgets.QMainWindow()
    ui = Ui_Customer_service_menu()
    ui.setupUi(Customer_service_menu)
    Customer_service_menu.show()
    sys.exit(app.exec())
