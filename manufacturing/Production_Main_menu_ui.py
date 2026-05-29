# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'Production_Main_menu.ui'
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


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(800, 600)
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
        self.Product_Button = QPushButton(self.centralwidget)
        self.Product_Button.setObjectName(u"Product_Button")
        self.Product_Button.setGeometry(QRect(270, 10, 161, 41))
        font = QFont()
        font.setPointSize(16)
        self.Product_Button.setFont(font)
        self.Product_Button.setStyleSheet(u"QPushButton{background-color: white;\n"
                                          "border: 2px solid black;\n"
                                          "border-radius: 10px;}\n"
                                          "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                          "border: 2px solidrgb(85, 255, 255);\n"
                                          "}")
        self.Product_Button.setAutoDefault(False)
        self.Prod_mgr_Button = QPushButton(self.centralwidget)
        self.Prod_mgr_Button.setObjectName(u"Prod_mgr_Button")
        self.Prod_mgr_Button.setGeometry(QRect(10, 10, 221, 41))
        self.Prod_mgr_Button.setFont(font)
        self.Prod_mgr_Button.setStyleSheet(u"QPushButton{background-color: white;\n"
                                           "border: 2px solid black;\n"
                                           "border-radius: 10px;}\n"
                                           "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                           "border: 2px solidrgb(85, 255, 255);\n"
                                           "}")
        self.Prod_mgr_Button.setAutoDefault(False)
        self.Shipping_Button = QPushButton(self.centralwidget)
        self.Shipping_Button.setObjectName(u"Shipping_Button")
        self.Shipping_Button.setGeometry(QRect(470, 10, 161, 41))
        self.Shipping_Button.setFont(font)
        self.Shipping_Button.setStyleSheet(u"QPushButton{background-color: white;\n"
                                           "border: 2px solid black;\n"
                                           "border-radius: 10px;}\n"
                                           "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                           "border: 2px solidrgb(85, 255, 255);\n"
                                           "}")
        self.Shipping_Button.setAutoDefault(False)
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(0, 60, 801, 501))
        self.label.setStyleSheet(u"background-image: url('C:/source/pythonQSG/PyQt6 Apps/images/pharmamfg.png');\n"
                                 "background-repeat: no-repeat;\n"
                                 "background-position: center;\n"
                                 "background-attachment: fixed;\n"
                                 "background-color: white; /* Fallback color */")
        MainWindow.setCentralWidget(self.centralwidget)
        self.label.raise_()
        self.Product_Button.raise_()
        self.Prod_mgr_Button.raise_()
        self.Shipping_Button.raise_()
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
        self.Product_Button.setText(QCoreApplication.translate("MainWindow", u"Production", None))
        self.Prod_mgr_Button.setText(QCoreApplication.translate("MainWindow", u"Production Manager", None))
        self.Shipping_Button.setText(QCoreApplication.translate("MainWindow", u"Shipping", None))
        self.label.setText("")
    # retranslateUi
