# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'cs_main_menu.ui'
##
# Created by: Qt User Interface Compiler version 6.9.2
##
# WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject, QRect,
                            Qt)
from PySide6.QtGui import (QBrush, QColor, QFont, QPalette)
from PySide6.QtWidgets import (QLabel, QMenuBar,
                               QPushButton, QStatusBar, QWidget)


class Ui_Cust_Serv_Main_Menu(object):
    def setupUi(self, Cust_Serv_Main_Menu):
        if not Cust_Serv_Main_Menu.objectName():
            Cust_Serv_Main_Menu.setObjectName(u"Cust_Serv_Main_Menu")
        Cust_Serv_Main_Menu.resize(800, 600)
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
        Cust_Serv_Main_Menu.setPalette(palette)
        Cust_Serv_Main_Menu.setAutoFillBackground(False)
        self.centralwidget = QWidget(Cust_Serv_Main_Menu)
        self.centralwidget.setObjectName(u"centralwidget")
        self.cs_mgr_Button = QPushButton(self.centralwidget)
        self.cs_mgr_Button.setObjectName(u"cs_mgr_Button")
        self.cs_mgr_Button.setGeometry(QRect(20, 20, 191, 41))
        font = QFont()
        font.setPointSize(16)
        self.cs_mgr_Button.setFont(font)
        self.cs_mgr_Button.setStyleSheet(u"QPushButton{background-color: white;\n"
                                         "border: 2px solid black;\n"
                                         "border-radius: 10px;}\n"
                                         "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                         "border: 2px solidrgb(85, 255, 255);\n"
                                         "}")
        self.cs_mgr_Button.setAutoDefault(False)
        self.cust_calls_Button = QPushButton(self.centralwidget)
        self.cust_calls_Button.setObjectName(u"cust_calls_Button")
        self.cust_calls_Button.setGeometry(QRect(20, 160, 161, 41))
        self.cust_calls_Button.setFont(font)
        self.cust_calls_Button.setStyleSheet(u"QPushButton{background-color: white;\n"
                                             "border: 2px solid black;\n"
                                             "border-radius: 10px;}\n"
                                             "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                             "border: 2px solidrgb(85, 255, 255);\n"
                                             "}")
        self.cust_calls_Button.setAutoDefault(False)
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(0, 0, 801, 551))
        self.label.setStyleSheet(u"background-image: url('C:/source/pythonQSG/PyQt6 Apps/images/Customer_service.png');\n"
                                 "background-repeat: no-repeat;\n"
                                 "background-position: center;\n"
                                 "background-attachment: fixed;\n"
                                 "background-color: white; /* Fallback color */")
        self.cust_calls_Button_2 = QPushButton(self.centralwidget)
        self.cust_calls_Button_2.setObjectName(u"cust_calls_Button_2")
        self.cust_calls_Button_2.setGeometry(QRect(20, 90, 241, 41))
        self.cust_calls_Button_2.setFont(font)
        self.cust_calls_Button_2.setStyleSheet(u"QPushButton{background-color: white;\n"
                                               "border: 2px solid black;\n"
                                               "border-radius: 10px;}\n"
                                               "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                               "border: 2px solidrgb(85, 255, 255);\n"
                                               "}")
        self.cust_calls_Button_2.setAutoDefault(False)
        Cust_Serv_Main_Menu.setCentralWidget(self.centralwidget)
        self.label.raise_()
        self.cs_mgr_Button.raise_()
        self.cust_calls_Button.raise_()
        self.cust_calls_Button_2.raise_()
        self.menubar = QMenuBar(Cust_Serv_Main_Menu)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 21))
        Cust_Serv_Main_Menu.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(Cust_Serv_Main_Menu)
        self.statusbar.setObjectName(u"statusbar")
        Cust_Serv_Main_Menu.setStatusBar(self.statusbar)

        self.retranslateUi(Cust_Serv_Main_Menu)

        QMetaObject.connectSlotsByName(Cust_Serv_Main_Menu)
    # setupUi

    def retranslateUi(self, Cust_Serv_Main_Menu):
        Cust_Serv_Main_Menu.setWindowTitle(QCoreApplication.translate("Cust_Serv_Main_Menu", u"MainWindow", None))
        self.cs_mgr_Button.setText(QCoreApplication.translate("Cust_Serv_Main_Menu", u"CS Manager Menu", None))
        self.cust_calls_Button.setText(QCoreApplication.translate("Cust_Serv_Main_Menu", u"Customer Calls", None))
        self.label.setText("")
        self.cust_calls_Button_2.setText(QCoreApplication.translate(
            "Cust_Serv_Main_Menu", u"Customer Service Menu", None))
    # retranslateUi
