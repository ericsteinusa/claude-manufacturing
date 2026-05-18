# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'marketing_menu.ui'
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
    QSizePolicy, QStatusBar, QWidget)

class Ui_Marketing_menu(object):
    def setupUi(self, Marketing_menu):
        if not Marketing_menu.objectName():
            Marketing_menu.setObjectName(u"Marketing_menu")
        Marketing_menu.resize(800, 600)
        self.centralwidget = QWidget(Marketing_menu)
        self.centralwidget.setObjectName(u"centralwidget")
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(0, 0, 801, 571))
        self.label.setStyleSheet(u"background-image: url('C:/source/pythonQSG/PyQt6 Apps/images/marketing.png');\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        Marketing_menu.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(Marketing_menu)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 21))
        Marketing_menu.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(Marketing_menu)
        self.statusbar.setObjectName(u"statusbar")
        Marketing_menu.setStatusBar(self.statusbar)

        self.retranslateUi(Marketing_menu)

        QMetaObject.connectSlotsByName(Marketing_menu)
    # setupUi

    def retranslateUi(self, Marketing_menu):
        Marketing_menu.setWindowTitle(QCoreApplication.translate("Marketing_menu", u"MainWindow", None))
        self.label.setText("")
    # retranslateUi

