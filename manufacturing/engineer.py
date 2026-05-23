from PyQt6 import QtCore, QtWidgets


class Ui_engineer(object):
    def setupUi(self, engineer):
        engineer.setObjectName("engineer")
        engineer.resize(800, 759)
        self.centralwidget = QtWidgets.QWidget(parent=engineer)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 711))
        self.label.setStyleSheet("background-image: url(engineering.png);\n"
                                 "background-repeat: no-repeat;\n"
                                 "background-position: center;\n"
                                 "background-attachment: fixed;\n"
                                 "background-color: white; /* Fallback color */")
        self.label.setText("")
        self.label.setObjectName("label")
        engineer.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=engineer)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        engineer.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=engineer)
        self.statusbar.setObjectName("statusbar")
        engineer.setStatusBar(self.statusbar)

        self.retranslateUi(engineer)
        QtCore.QMetaObject.connectSlotsByName(engineer)

    def retranslateUi(self, engineer):
        _translate = QtCore.QCoreApplication.translate
        engineer.setWindowTitle(_translate("engineer", "Engineers Menu"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    engineer = QtWidgets.QMainWindow()
    ui = Ui_engineer()
    ui.setupUi(engineer)
    engineer.show()
    sys.exit(app.exec())
