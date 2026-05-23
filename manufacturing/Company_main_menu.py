from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
import sys
import subprocess
import os


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1000, 761)
        palette = QtGui.QPalette()
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.WindowText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 85, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(127, 170, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Light, brush)
        brush = QtGui.QBrush(QtGui.QColor(63, 127, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 42, 127))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Dark, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 56, 170))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Mid, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Text, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.BrightText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.ButtonText, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 85, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Shadow, brush)
        brush = QtGui.QBrush(QtGui.QColor(127, 170, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.AlternateBase, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 220))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.ToolTipBase, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.ToolTipText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.WindowText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 85, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(127, 170, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.Light, brush)
        brush = QtGui.QBrush(QtGui.QColor(63, 127, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 42, 127))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.Dark, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 56, 170))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.Mid, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.Text, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.BrightText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.ButtonText, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 85, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.Shadow, brush)
        brush = QtGui.QBrush(QtGui.QColor(127, 170, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.AlternateBase, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 220))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.ToolTipBase, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Inactive, QtGui.QPalette.ColorRole.ToolTipText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 42, 127))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 85, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Button, brush)
        brush = QtGui.QBrush(QtGui.QColor(127, 170, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Light, brush)
        brush = QtGui.QBrush(QtGui.QColor(63, 127, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Midlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 42, 127))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Dark, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 56, 170))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Mid, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 42, 127))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.BrightText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 42, 127))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 85, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 85, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Window, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Shadow, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 85, 255))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.AlternateBase, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 220))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ToolTipBase, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        palette.setBrush(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ToolTipText, brush)
        MainWindow.setPalette(palette)
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 1000, 731))
        self.label.setStyleSheet("background-image: url(manufacturing.png);\n"
                                 "background-repeat: no-repeat;\n"
                                 "background-position: center;\n"
                                 "background-attachment: fixed;\n"
                                 "background-color: white; /* Fallback color */")
        self.label.setObjectName("label")
        self.cust_serv_Button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Customer Service"))
        self.cust_serv_Button.setGeometry(QtCore.QRect(180, 50, 181, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.cust_serv_Button.setFont(font)
        self.cust_serv_Button.setStyleSheet("QPushButton{background-color: white;\n"
                                            "border: 2px solid black;\n"
                                            "border-radius: 10px;\n}"
                                            "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                            "border: 2px solidrgb(85, 255, 255);\n}"
                                            "")
        self.cust_serv_Button.setAutoDefault(False)
        self.cust_serv_Button.setObjectName("cust_serv_Button")
        self.production_button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Production"))
        self.production_button.setGeometry(QtCore.QRect(180, 260, 131, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.production_button.setFont(font)
        self.production_button.setStyleSheet("QPushButton{background-color: white;\n"
                                             "border: 2px solid black;\n"
                                             "border-radius: 10px;\n}"
                                             "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                             "border: 2px solidrgb(85, 255, 255);\n}"
                                             "")
        self.production_button.setAutoDefault(False)
        self.production_button.setObjectName("production_button")
        self.purchasing_button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Purchasing"))
        self.purchasing_button.setGeometry(QtCore.QRect(20, 330, 131, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.purchasing_button.setFont(font)
        self.purchasing_button.setStyleSheet("QPushButton{background-color: white;\n"
                                             "border: 2px solid black;\n"
                                             "border-radius: 10px;\n}"
                                             "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                             "border: 2px solidrgb(85, 255, 255);\n}"
                                             "")
        self.purchasing_button.setAutoDefault(False)
        self.purchasing_button.setObjectName("purchasing_button")
        self.personnel_button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Personnel"))
        self.personnel_button.setGeometry(QtCore.QRect(20, 260, 131, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.personnel_button.setFont(font)
        self.personnel_button.setStyleSheet("QPushButton{background-color: white;\n"
                                            "border: 2px solid black;\n"
                                            "border-radius: 10px;\n}"
                                            "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                            "border: 2px solidrgb(85, 255, 255);\n}"
                                            "")
        self.personnel_button.setAutoDefault(False)
        self.personnel_button.setObjectName("personnel_button")
        self.qa_button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Quality Assurance"))
        self.qa_button.setGeometry(QtCore.QRect(180, 330, 181, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.qa_button.setFont(font)
        self.qa_button.setStyleSheet("QPushButton{background-color: white;\n"
                                     "border: 2px solid black;\n"
                                     "border-radius: 10px;\n}"
                                     "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                     "border: 2px solidrgb(85, 255, 255);\n}"
                                     "")
        self.qa_button.setAutoDefault(False)
        self.qa_button.setObjectName("qa_button")
        self.Accounting_Button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Accounting"))
        self.Accounting_Button.setGeometry(QtCore.QRect(20, 50, 131, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Accounting_Button.setFont(font)
        self.Accounting_Button.setStyleSheet("QPushButton{background-color: white;\n"
                                             "border: 2px solid black;\n"
                                             "border-radius: 10px;\n}"
                                             "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                             "border: 2px solidrgb(85, 255, 255);\n}"
                                             "")
        self.Accounting_Button.setAutoDefault(False)
        self.Accounting_Button.setObjectName("Accounting_Button")
        self.maintenance_button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Maintenance"))
        self.maintenance_button.setGeometry(QtCore.QRect(20, 190, 131, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.maintenance_button.setFont(font)
        self.maintenance_button.setStyleSheet("QPushButton{background-color: white;\n"
                                              "border: 2px solid black;\n"
                                              "border-radius: 10px;\n}"
                                              "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                              "border: 2px solidrgb(85, 255, 255);\n}"
                                              "")
        self.maintenance_button.setAutoDefault(False)
        self.maintenance_button.setObjectName("maintenance_button")
        self.Infor_tech_button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Information Tech"))
        self.Infor_tech_button.setGeometry(QtCore.QRect(180, 120, 181, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Infor_tech_button.setFont(font)
        self.Infor_tech_button.setStyleSheet("QPushButton{background-color: white;\n"
                                             "border: 2px solid black;\n"
                                             "border-radius: 10px;\n}"
                                             "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                             "border: 2px solidrgb(85, 255, 255);\n}"
                                             "")
        self.Infor_tech_button.setAutoDefault(False)
        self.Infor_tech_button.setObjectName("Infor_tech_button")
        self.Marketing_button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Marketing"))
        self.Marketing_button.setGeometry(QtCore.QRect(180, 190, 131, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Marketing_button.setFont(font)
        self.Marketing_button.setStyleSheet("QPushButton{background-color: white;\n"
                                            "border: 2px solid black;\n"
                                            "border-radius: 10px;\n}"
                                            "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                            "border: 2px solidrgb(85, 255, 255);\n}"
                                            "")
        self.Marketing_button.setAutoDefault(False)
        self.Marketing_button.setObjectName("Marketing_button")
        self.Engineering_button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Engineering"))
        self.Engineering_button.setGeometry(QtCore.QRect(20, 120, 131, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Engineering_button.setFont(font)
        self.Engineering_button.setStyleSheet("QPushButton{background-color: white;\n"
                                              "border: 2px solid black;\n"
                                              "border-radius: 10px;\n}"
                                              "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                              "border: 2px solidrgb(85, 255, 255);\n}"
                                              "")
        self.Engineering_button.setAutoDefault(False)
        self.Engineering_button.setObjectName("Engineering_button")
        self.Sales_button = QtWidgets.QPushButton(parent=self.centralwidget, clicked=lambda: self.press_it("Sales"))
        self.Sales_button.setGeometry(QtCore.QRect(20, 400, 131, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Sales_button.setFont(font)
        self.Sales_button.setStyleSheet("QPushButton{background-color: white;\n"
                                        "border: 2px solid black;\n"
                                        "border-radius: 10px;\n}"
                                        "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                        "border: 2px solidrgb(85, 255, 255);\n}"
                                        "")
        self.Sales_button.setAutoDefault(False)
        self.Sales_button.setObjectName("Sales_button")
        self.budget_mgmt_button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Budget Management"))
        self.budget_mgmt_button.setGeometry(QtCore.QRect(180, 400, 181, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.budget_mgmt_button.setFont(font)
        self.budget_mgmt_button.setStyleSheet("QPushButton{background-color: white;\n"
                                              "border: 2px solid black;\n"
                                              "border-radius: 10px;\n}"
                                              "QPushButton:hover{background-color:rgb(85, 255, 255);\n"
                                              "border: 2px solidrgb(85, 255, 255);\n}"
                                              "")
        self.budget_mgmt_button.setAutoDefault(False)
        self.budget_mgmt_button.setObjectName("budget_mgmt_button")
        BTN_STYLE = ("QPushButton{background-color: white;\nborder: 2px solid black;\nborder-radius: 10px;\n}"
                     "QPushButton:hover{background-color:rgb(85, 255, 255);\nborder: 2px solidrgb(85, 255, 255);\n}")
        self.finance_button = QtWidgets.QPushButton(parent=self.centralwidget, clicked=lambda: self.press_it("Finance"))
        self.finance_button.setGeometry(QtCore.QRect(20, 470, 131, 41))
        self.finance_button.setFont(QtGui.QFont("", 16))
        self.finance_button.setStyleSheet(BTN_STYLE)
        self.finance_button.setAutoDefault(False)
        self.finance_button.setObjectName("finance_button")
        self.legal_button = QtWidgets.QPushButton(parent=self.centralwidget, clicked=lambda: self.press_it("Legal"))
        self.legal_button.setGeometry(QtCore.QRect(180, 470, 131, 41))
        self.legal_button.setFont(QtGui.QFont("", 16))
        self.legal_button.setStyleSheet(BTN_STYLE)
        self.legal_button.setAutoDefault(False)
        self.legal_button.setObjectName("legal_button")
        self.risk_mgmt_button = QtWidgets.QPushButton(
            parent=self.centralwidget, clicked=lambda: self.press_it("Risk Management"))
        self.risk_mgmt_button.setGeometry(QtCore.QRect(20, 540, 181, 41))
        self.risk_mgmt_button.setFont(QtGui.QFont("", 16))
        self.risk_mgmt_button.setStyleSheet(BTN_STYLE)
        self.risk_mgmt_button.setAutoDefault(False)
        self.risk_mgmt_button.setObjectName("risk_mgmt_button")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 729, 21))
        self.menubar.setObjectName("menubar")
        self.menuCompany_Main_Menu = QtWidgets.QMenu(parent=self.menubar)
        font = QtGui.QFont()
        font.setPointSize(9)
        self.menuCompany_Main_Menu.setFont(font)
        self.menuCompany_Main_Menu.setLayoutDirection(QtCore.Qt.LayoutDirection.LeftToRight)
        self.menuCompany_Main_Menu.setTearOffEnabled(False)
        self.menuCompany_Main_Menu.setTitle("")
        self.menuCompany_Main_Menu.setObjectName("menuCompany_Main_Menu")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.menubar.addAction(self.menuCompany_Main_Menu.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Accounting": "Accounting_Main_menu.py",
            "Customer Service": "cs_main_menu.py",
            "Engineering": "engineering_Main_menu.py",
            "Information Tech": "IT_Main_Menu.py",
            "Maintenance": "Maint_Main_menu.py",
            "Marketing": "Marketing_Main_menu.py",
            "Personnel": "Personnel_Main_menu.py",
            "Production": "Production_Main_menu.py",
            "Purchasing": "Purchasing_Main_menu.py",
            "Quality Assurance": "QA_Main_menu.py",
            "Sales": "Sales_Main_menu.py",
            "Budget Management": "Budget_mgmt.py",
            "Finance": "Finance_Main_menu.py",
            "Legal": "Legal_Main_menu.py",
            "Risk Management": "Risk_mgmt_Main_menu.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("Company Main Menu", "Company Main Menu"))
        self.cust_serv_Button.setText(_translate("MainWindow", "Customer Service"))
        self.production_button.setText(_translate("MainWindow", "Production"))
        self.purchasing_button.setText(_translate("MainWindow", "Purchasing"))
        self.personnel_button.setText(_translate("MainWindow", "Personnel"))
        self.qa_button.setText(_translate("MainWindow", "Quality Assurance"))
        self.Accounting_Button.setText(_translate("MainWindow", "Accounting"))
        self.maintenance_button.setText(_translate("MainWindow", "Maintenance"))
        self.Infor_tech_button.setText(_translate("MainWindow", "Information Tech"))
        self.Marketing_button.setText(_translate("MainWindow", "Marketing"))
        self.Engineering_button.setText(_translate("MainWindow", "Engineering"))
        self.Sales_button.setText(_translate("MainWindow", "Sales"))
        self.budget_mgmt_button.setText(_translate("MainWindow", "Budget Management"))
        self.finance_button.setText(_translate("MainWindow", "Finance"))
        self.legal_button.setText(_translate("MainWindow", "Legal"))
        self.risk_mgmt_button.setText(_translate("MainWindow", "Risk Management"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())
