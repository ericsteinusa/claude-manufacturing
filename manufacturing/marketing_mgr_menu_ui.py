# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'marketing_mgr_menu.ui'
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

class Ui_Marketing_mgr_menu(object):
    def setupUi(self, Marketing_mgr_menu):
        if not Marketing_mgr_menu.objectName():
            Marketing_mgr_menu.setObjectName(u"Marketing_mgr_menu")
        Marketing_mgr_menu.resize(800, 600)
        self.centralwidget = QWidget(Marketing_mgr_menu)
        self.centralwidget.setObjectName(u"centralwidget")
        self.Marketing = QLabel(self.centralwidget)
        self.Marketing.setObjectName(u"Marketing")
        self.Marketing.setGeometry(QRect(0, 0, 801, 561))
        self.Marketing.setStyleSheet(u"background-image: url('C:/source/pythonQSG/PyQt6 Apps/images/marketing.png');\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        self.Marketing_Button = QPushButton(self.centralwidget)
        self.Marketing_Button.setObjectName(u"Marketing_Button")
        self.Marketing_Button.setGeometry(QRect(40, 10, 211, 41))
        font = QFont()
        font.setPointSize(16)
        self.Marketing_Button.setFont(font)
        self.Marketing_Button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.Marketing_Button.setAutoDefault(False)
        Marketing_mgr_menu.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(Marketing_mgr_menu)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 21))
        Marketing_mgr_menu.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(Marketing_mgr_menu)
        self.statusbar.setObjectName(u"statusbar")
        Marketing_mgr_menu.setStatusBar(self.statusbar)

        self.retranslateUi(Marketing_mgr_menu)

        QMetaObject.connectSlotsByName(Marketing_mgr_menu)
    # setupUi

    def retranslateUi(self, Marketing_mgr_menu):
        Marketing_mgr_menu.setWindowTitle(QCoreApplication.translate("Marketing_mgr_menu", u"MainWindow", None))
        self.Marketing.setText("")
        self.Marketing_Button.setText(QCoreApplication.translate("Marketing_mgr_menu", u"Marketing", None))
    # retranslateUi

