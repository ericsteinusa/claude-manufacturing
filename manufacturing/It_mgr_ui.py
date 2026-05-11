# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'It_mgr.ui'
##
## Created by: Qt User Interface Compiler version 6.9.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QMenuBar,
    QPushButton, QSizePolicy, QStatusBar, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(800, 695)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.IT_Calls_Button = QPushButton(self.centralwidget)
        self.IT_Calls_Button.setObjectName(u"IT_Calls_Button")
        self.IT_Calls_Button.setGeometry(QRect(20, 20, 221, 41))
        font = QFont()
        font.setPointSize(16)
        self.IT_Calls_Button.setFont(font)
        self.IT_Calls_Button.setStyleSheet(u"background-color: white;\n"
"border: 2px solid black;\n"
"")
        self.IT_Calls_Button.setAutoDefault(False)
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(0, 0, 801, 651))
        self.label.setStyleSheet(u"background-image: url('C:/source/pythonQSG/PyQt6 Apps/images/IT_picture.png');\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        MainWindow.setCentralWidget(self.centralwidget)
        self.label.raise_()
        self.IT_Calls_Button.raise_()
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 21))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.IT_Calls_Button.setText(QCoreApplication.translate("MainWindow", u"IT Technician", None))
        self.label.setText("")
    # retranslateUi

