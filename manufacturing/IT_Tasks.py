from PyQt6 import QtCore, QtGui, QtWidgets
import sys, subprocess

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(826, 694)
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 831, 651))
        self.label.setStyleSheet("background-image: url(IT_picture2.png);\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        self.label.setText("")
        self.label.setObjectName("label")
        self.Dept_Entry_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Department Entry"))
        self.Dept_Entry_Button.setGeometry(QtCore.QRect(0, 20, 181, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Dept_Entry_Button.setFont(font)
        self.Dept_Entry_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black; border-radius: 10px;\n"
"}\n"
"\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"} \n"
"")
        self.Dept_Entry_Button.setAutoDefault(False)
        self.Dept_Entry_Button.setObjectName("Dept_Entry_Button")
        self.Dept_Sub_entry_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Department Sub Entry"))
        self.Dept_Sub_entry_Button.setGeometry(QtCore.QRect(180, 20, 221, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Dept_Sub_entry_Button.setFont(font)
        self.Dept_Sub_entry_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black; border-radius: 10px;\n"
"}\n"
"\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"} \n"
"")
        self.Dept_Sub_entry_Button.setAutoDefault(False)
        self.Dept_Sub_entry_Button.setObjectName("Dept_Sub_entry_Button")
        self.Dept_sub_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Department and Sub List"))
        self.Dept_sub_Button.setGeometry(QtCore.QRect(400, 20, 241, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Dept_sub_Button.setFont(font)
        self.Dept_sub_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black; border-radius: 10px;\n"
"}\n"
"\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"} \n"
"")
        self.Dept_sub_Button.setAutoDefault(False)
        self.Dept_sub_Button.setObjectName("Dept_sub_Button")
        self.People_Dept_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("People and Department List"))
        self.People_Dept_Button.setGeometry(QtCore.QRect(640, 20, 181, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.People_Dept_Button.setFont(font)
        self.People_Dept_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black; border-radius: 10px;\n"
"}\n"
"\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"} \n"
"")
        self.People_Dept_Button.setAutoDefault(False)
        self.People_Dept_Button.setObjectName("People_Dept_Button")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 826, 20))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def press_it(self, pressed):
        if pressed == "Department Entry":
                subprocess.Popen(["python3", "dept_entry.py"])
        if pressed == "Department Sub Entry":
                subprocess.Popen(["python3", "dept_sub_entry.py"])                
        if pressed == "Department and Sub List":
                subprocess.Popen(["python3", "dept_sub.py"])
        if pressed == "People and Department List":
                subprocess.Popen(["python3", "display_people_department.py"])

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "IT Tasks"))
        self.Dept_Entry_Button.setText(_translate("MainWindow", "Department Entry"))
        self.Dept_Sub_entry_Button.setText(_translate("MainWindow", "Department Sub Entry"))
        self.Dept_sub_Button.setText(_translate("MainWindow", "Department and Sub List"))
        self.People_Dept_Button.setText(_translate("MainWindow", "People and Dept"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())
