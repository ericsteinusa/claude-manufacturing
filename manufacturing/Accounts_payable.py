from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_accounts_payable(object):
    def setupUi(self, accounts_payable):
        accounts_payable.setObjectName("accounts_payable")
        accounts_payable.resize(800, 696)
        self.centralwidget = QtWidgets.QWidget(parent=accounts_payable)
        self.centralwidget.setObjectName("centralwidget")
        self.ap = QtWidgets.QLabel(parent=self.centralwidget)
        self.ap.setGeometry(QtCore.QRect(0, 10, 801, 651))
        self.ap.setStyleSheet("background-image: url(Accounting2.png);\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        self.ap.setText("")
        self.ap.setObjectName("ap")
        accounts_payable.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=accounts_payable)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        accounts_payable.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=accounts_payable)
        self.statusbar.setObjectName("statusbar")
        accounts_payable.setStatusBar(self.statusbar)

        self.retranslateUi(accounts_payable)
        QtCore.QMetaObject.connectSlotsByName(accounts_payable)

    def retranslateUi(self, accounts_payable):
        _translate = QtCore.QCoreApplication.translate
        accounts_payable.setWindowTitle(_translate("accounts_payable", "Accounts Payable"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    accounts_payable = QtWidgets.QMainWindow()
    ui = Ui_accounts_payable()
    ui.setupUi(accounts_payable)
    accounts_payable.show()
    sys.exit(app.exec())
