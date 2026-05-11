from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(826, 694)
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 831, 651))
        self.label.setStyleSheet("background-image: url(\'C:/source/pythonQSG/PyQt6 Apps/images/IT_picture.png\');\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: blue; /* Fallback color */")
        self.label.setText("")
        self.label.setObjectName("label")
        self.Dept_list_Button = QtWidgets.QPushButton(parent=self.centralwidget)
        self.Dept_list_Button.setGeometry(QtCore.QRect(0, 20, 171, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Dept_list_Button.setFont(font)
        self.Dept_list_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);}\n"
"")
        self.Dept_list_Button.setAutoDefault(False)
        self.Dept_list_Button.setObjectName("Dept_list_Button")
        self.acct_rcv_Button_2 = QtWidgets.QPushButton(parent=self.centralwidget)
        self.acct_rcv_Button_2.setGeometry(QtCore.QRect(180, 20, 211, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.acct_rcv_Button_2.setFont(font)
        self.acct_rcv_Button_2.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;\n}"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n}"
"")
        self.acct_rcv_Button_2.setAutoDefault(False)
        self.acct_rcv_Button_2.setObjectName("acct_rcv_Button_2")
        self.acct_rcv_Button_3 = QtWidgets.QPushButton(parent=self.centralwidget)
        self.acct_rcv_Button_3.setGeometry(QtCore.QRect(400, 20, 61, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.acct_rcv_Button_3.setFont(font)
        self.acct_rcv_Button_3.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;\n}"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n}"
"")
        self.acct_rcv_Button_3.setAutoDefault(False)
        self.acct_rcv_Button_3.setObjectName("acct_rcv_Button_3")
        self.acct_rcv_Button_4 = QtWidgets.QPushButton(parent=self.centralwidget)
        self.acct_rcv_Button_4.setGeometry(QtCore.QRect(470, 20, 171, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.acct_rcv_Button_4.setFont(font)
        self.acct_rcv_Button_4.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;\n}"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n}"
"")
        self.acct_rcv_Button_4.setAutoDefault(False)
        self.acct_rcv_Button_4.setObjectName("acct_rcv_Button_4")
        self.acct_rcv_Button_5 = QtWidgets.QPushButton(parent=self.centralwidget)
        self.acct_rcv_Button_5.setGeometry(QtCore.QRect(650, 20, 171, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.acct_rcv_Button_5.setFont(font)
        self.acct_rcv_Button_5.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;\n}"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n}"
"")
        self.acct_rcv_Button_5.setAutoDefault(False)
        self.acct_rcv_Button_5.setObjectName("acct_rcv_Button_5")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 826, 21))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.Dept_list_Button.setText(_translate("MainWindow", "Department List"))
        self.acct_rcv_Button_2.setText(_translate("MainWindow", "Email and Password"))
        self.acct_rcv_Button_3.setText(_translate("MainWindow", "OID"))
        self.acct_rcv_Button_4.setText(_translate("MainWindow", "Parent and Child"))
        self.acct_rcv_Button_5.setText(_translate("MainWindow", "People and Dept"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())
