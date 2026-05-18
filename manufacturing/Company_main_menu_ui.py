# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'Company_main_menu.ui'
##
## Created by: Qt User Interface Compiler version 6.9.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QMenu,
    QMenuBar, QPushButton, QSizePolicy, QStatusBar,
    QWidget)
# import bg_rc
# import 1_rc

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(729, 761)
        palette = QPalette()
        brush = QBrush(QColor(0, 0, 0, 255))
        brush.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText, brush)
        brush1 = QBrush(QColor(0, 85, 255, 255))
        brush1.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.Button, brush1)
        brush2 = QBrush(QColor(127, 170, 255, 255))
        brush2.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.Light, brush2)
        brush3 = QBrush(QColor(63, 127, 255, 255))
        brush3.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.Midlight, brush3)
        brush4 = QBrush(QColor(0, 42, 127, 255))
        brush4.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.Dark, brush4)
        brush5 = QBrush(QColor(0, 56, 170, 255))
        brush5.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.Mid, brush5)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.Text, brush)
        brush6 = QBrush(QColor(255, 255, 255, 255))
        brush6.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.BrightText, brush6)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText, brush)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.Base, brush6)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.Window, brush1)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.Shadow, brush)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.AlternateBase, brush2)
        brush7 = QBrush(QColor(255, 255, 220, 255))
        brush7.setStyle(Qt.BrushStyle.SolidPattern)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.ToolTipBase, brush7)
        palette.setBrush(QPalette.ColorGroup.Active, QPalette.ColorRole.ToolTipText, brush)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.WindowText, brush)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Button, brush1)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Light, brush2)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Midlight, brush3)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Dark, brush4)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Mid, brush5)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Text, brush)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.BrightText, brush6)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.ButtonText, brush)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Base, brush6)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Window, brush1)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Shadow, brush)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.AlternateBase, brush2)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.ToolTipBase, brush7)
        palette.setBrush(QPalette.ColorGroup.Inactive, QPalette.ColorRole.ToolTipText, brush)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, brush4)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, brush1)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Light, brush2)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Midlight, brush3)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Dark, brush4)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Mid, brush5)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, brush4)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.BrightText, brush6)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, brush4)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, brush1)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, brush1)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Shadow, brush)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.AlternateBase, brush1)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ToolTipBase, brush7)
        palette.setBrush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ToolTipText, brush)
        MainWindow.setPalette(palette)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(0, 160, 731, 561))
        self.label.setStyleSheet(u"background-image: url('C:/source/pythonQSG/PyQt6 Apps/images/manufacturing2.png');\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        self.cust_serv_Button = QPushButton(self.centralwidget)
        self.cust_serv_Button.setObjectName(u"cust_serv_Button")
        self.cust_serv_Button.setGeometry(QRect(160, 10, 181, 41))
        font = QFont()
        font.setPointSize(16)
        self.cust_serv_Button.setFont(font)
        self.cust_serv_Button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.cust_serv_Button.setAutoDefault(False)
        self.production_button = QPushButton(self.centralwidget)
        self.production_button.setObjectName(u"production_button")
        self.production_button.setGeometry(QRect(460, 60, 131, 41))
        self.production_button.setFont(font)
        self.production_button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.production_button.setAutoDefault(False)
        self.purchasing_button = QPushButton(self.centralwidget)
        self.purchasing_button.setObjectName(u"purchasing_button")
        self.purchasing_button.setGeometry(QRect(10, 110, 131, 41))
        self.purchasing_button.setFont(font)
        self.purchasing_button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.purchasing_button.setAutoDefault(False)
        self.personnel_button = QPushButton(self.centralwidget)
        self.personnel_button.setObjectName(u"personnel_button")
        self.personnel_button.setGeometry(QRect(310, 60, 131, 41))
        self.personnel_button.setFont(font)
        self.personnel_button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.personnel_button.setAutoDefault(False)
        self.qa_button = QPushButton(self.centralwidget)
        self.qa_button.setObjectName(u"qa_button")
        self.qa_button.setGeometry(QRect(160, 110, 181, 41))
        self.qa_button.setFont(font)
        self.qa_button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.qa_button.setAutoDefault(False)
        self.Accounting_Button = QPushButton(self.centralwidget)
        self.Accounting_Button.setObjectName(u"Accounting_Button")
        self.Accounting_Button.setGeometry(QRect(10, 10, 131, 41))
        self.Accounting_Button.setFont(font)
        self.Accounting_Button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.Accounting_Button.setAutoDefault(False)
        self.maintenance_button = QPushButton(self.centralwidget)
        self.maintenance_button.setObjectName(u"maintenance_button")
        self.maintenance_button.setGeometry(QRect(10, 60, 131, 41))
        self.maintenance_button.setFont(font)
        self.maintenance_button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.maintenance_button.setAutoDefault(False)
        self.Infor_tech_button = QPushButton(self.centralwidget)
        self.Infor_tech_button.setObjectName(u"Infor_tech_button")
        self.Infor_tech_button.setGeometry(QRect(500, 10, 181, 41))
        self.Infor_tech_button.setFont(font)
        self.Infor_tech_button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.Infor_tech_button.setAutoDefault(False)
        self.Marketing_button = QPushButton(self.centralwidget)
        self.Marketing_button.setObjectName(u"Marketing_button")
        self.Marketing_button.setGeometry(QRect(160, 60, 131, 41))
        self.Marketing_button.setFont(font)
        self.Marketing_button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.Marketing_button.setAutoDefault(False)
        self.Engineering_button = QPushButton(self.centralwidget)
        self.Engineering_button.setObjectName(u"Engineering_button")
        self.Engineering_button.setGeometry(QRect(350, 10, 131, 41))
        self.Engineering_button.setFont(font)
        self.Engineering_button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.Engineering_button.setAutoDefault(False)
        self.Sales_button = QPushButton(self.centralwidget)
        self.Sales_button.setObjectName(u"Sales_button")
        self.Sales_button.setGeometry(QRect(360, 110, 131, 41))
        self.Sales_button.setFont(font)
        self.Sales_button.setStyleSheet(u"QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.Sales_button.setAutoDefault(False)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 729, 21))
        self.menuCompany_Main_Menu = QMenu(self.menubar)
        self.menuCompany_Main_Menu.setObjectName(u"menuCompany_Main_Menu")
        font1 = QFont()
        font1.setPointSize(9)
        self.menuCompany_Main_Menu.setFont(font1)
        self.menuCompany_Main_Menu.setLayoutDirection(Qt.LeftToRight)
        self.menuCompany_Main_Menu.setTearOffEnabled(False)
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuCompany_Main_Menu.menuAction())

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.label.setText("")
        self.cust_serv_Button.setText(QCoreApplication.translate("MainWindow", u"Customer Service", None))
        self.production_button.setText(QCoreApplication.translate("MainWindow", u"Production", None))
        self.purchasing_button.setText(QCoreApplication.translate("MainWindow", u"Purchasing", None))
        self.personnel_button.setText(QCoreApplication.translate("MainWindow", u"Personnel", None))
        self.qa_button.setText(QCoreApplication.translate("MainWindow", u"Quality Assurance", None))
        self.Accounting_Button.setText(QCoreApplication.translate("MainWindow", u"Accounting", None))
        self.maintenance_button.setText(QCoreApplication.translate("MainWindow", u"Maintenance", None))
        self.Infor_tech_button.setText(QCoreApplication.translate("MainWindow", u"Information Tech", None))
        self.Marketing_button.setText(QCoreApplication.translate("MainWindow", u"Marketing", None))
        self.Engineering_button.setText(QCoreApplication.translate("MainWindow", u"Engineering", None))
        self.Sales_button.setText(QCoreApplication.translate("MainWindow", u"Sales", None))
        self.menuCompany_Main_Menu.setTitle("")
    # retranslateUi

