from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 694)
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 791, 661))
        self.label.setStyleSheet("background-image: url(\'C:/source/pythonQSG/PyQt6 Apps/images/IT_picture.png\');\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: blue; /* Fallback color */")
        self.label.setText("")
        self.label.setObjectName("label")
        self.IT_calls_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("IT Support Calls"))
        self.IT_calls_Button.setGeometry(QtCore.QRect(10, 20, 221, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.IT_calls_Button.setFont(font)
        self.IT_calls_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;\n}"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n}"
"")
        self.IT_calls_Button.setAutoDefault(False)
        self.IT_calls_Button.setObjectName("IT_calls_Button")
        self.IT_Tasks_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("IT Tasks"))
        self.IT_Tasks_Button.setGeometry(QtCore.QRect(260, 20, 221, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.IT_Tasks_Button.setFont(font)
        self.IT_Tasks_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;\n}"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n}"
"")
        self.IT_Tasks_Button.setAutoDefault(False)
        self.IT_Tasks_Button.setObjectName("IT_Tasks_Button")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def press_it(self, pressed):
        if pressed == "IT Support Calls":
                subprocess.run(["python", "it_calls.py"])
        if pressed == "IT Tasks":
                subprocess.run(["python", "IT_Tasks.py"])

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "IT Technician Menu"))
        self.IT_calls_Button.setText(_translate("MainWindow", "IT Support Calls"))
        self.IT_Tasks_Button.setText(_translate("MainWindow", "IT Tasks"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())
