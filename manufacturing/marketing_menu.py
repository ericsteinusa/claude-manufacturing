from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess

class Ui_Marketing_menu(object):
    def setupUi(self, Marketing_menu):
        Marketing_menu.setObjectName("Marketing_menu")
        Marketing_menu.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(parent=Marketing_menu)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 571))
        self.label.setStyleSheet("background-image: url(Marketing.png);\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        self.label.setText("")
        self.label.setObjectName("label")
        Marketing_menu.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Marketing_menu)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        Marketing_menu.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Marketing_menu)
        self.statusbar.setObjectName("statusbar")
        Marketing_menu.setStatusBar(self.statusbar)

        self.retranslateUi(Marketing_menu)
        QtCore.QMetaObject.connectSlotsByName(Marketing_menu)

    def retranslateUi(self, Marketing_menu):
        _translate = QtCore.QCoreApplication.translate
        Marketing_menu.setWindowTitle(_translate("Marketing_menu", "Marketing Menu"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    Marketing_menu = QtWidgets.QMainWindow()
    ui = Ui_Marketing_menu()
    ui.setupUi(Marketing_menu)
    Marketing_menu.show()
    sys.exit(app.exec())
