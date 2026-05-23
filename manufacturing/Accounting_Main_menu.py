from PyQt6 import QtCore, QtGui, QtWidgets
import subprocess, sys, os

class Ui_Acct_MainWindow(object):
    def setupUi(self, Acct_MainWindow):
        Acct_MainWindow.setObjectName("Acct_MainWindow")
        Acct_MainWindow.resize(800, 695)
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
        Acct_MainWindow.setPalette(palette)
        self.centralwidget = QtWidgets.QWidget(parent=Acct_MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.acct_pay_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Accounts Payable"))
        self.acct_pay_Button.setGeometry(QtCore.QRect(260, 10, 181, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.acct_pay_Button.setFont(font)
        self.acct_pay_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.acct_pay_Button.setAutoDefault(False)
        self.acct_pay_Button.setObjectName("acct_pay_Button")
        self.Acct_mgr_button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Accounting Manager"))
        self.Acct_mgr_button.setGeometry(QtCore.QRect(220, 60, 211, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.Acct_mgr_button.setFont(font)
        self.Acct_mgr_button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.Acct_mgr_button.setAutoDefault(False)
        self.Acct_mgr_button.setObjectName("Acct_mgr_button")
        self.acct_rcv_Button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Accounts Recievable"))
        self.acct_rcv_Button.setGeometry(QtCore.QRect(20, 10, 211, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.acct_rcv_Button.setFont(font)
        self.acct_rcv_Button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.acct_rcv_Button.setAutoDefault(False)
        self.acct_rcv_Button.setObjectName("acct_rcv_Button")
        self.credit_dept_button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Credit Department"))
        self.credit_dept_button.setGeometry(QtCore.QRect(460, 10, 211, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.credit_dept_button.setFont(font)
        self.credit_dept_button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.credit_dept_button.setAutoDefault(False)
        self.credit_dept_button.setObjectName("credit_dept_button")
        self.payroll_button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Payroll Department"))
        self.payroll_button.setGeometry(QtCore.QRect(20, 60, 181, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.payroll_button.setFont(font)
        self.payroll_button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.payroll_button.setAutoDefault(False)
        self.payroll_button.setObjectName("payroll_button")
        self.budget_button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Budget Management"))
        self.budget_button.setGeometry(QtCore.QRect(460, 110, 211, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.budget_button.setFont(font)
        self.budget_button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.budget_button.setAutoDefault(False)
        self.budget_button.setObjectName("budget_button")
        self.bank_recon_button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("Bank Reconciliation"))
        self.bank_recon_button.setGeometry(QtCore.QRect(20, 110, 211, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.bank_recon_button.setFont(font)
        self.bank_recon_button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.bank_recon_button.setAutoDefault(False)
        self.bank_recon_button.setObjectName("bank_recon_button")
        self.gl_button = QtWidgets.QPushButton(parent=self.centralwidget, clicked= lambda: self.press_it("General Ledger"))
        self.gl_button.setGeometry(QtCore.QRect(460, 60, 211, 41))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.gl_button.setFont(font)
        self.gl_button.setStyleSheet("QPushButton{background-color: white;\n"
"border: 2px solid black;\n"
"border-radius: 10px;}\n"
"QPushButton:hover{background-color:rgb(85, 255, 255);\n"
"border: 2px solidrgb(85, 255, 255);\n"
"}")
        self.gl_button.setAutoDefault(False)
        self.gl_button.setObjectName("gl_button")
        self.label = QtWidgets.QLabel(parent=self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 801, 661))
        self.label.setStyleSheet("background-image: url(Accounting2.png);\n"
"background-repeat: no-repeat;\n"
"background-position: center;\n"
"background-attachment: fixed;\n"
"background-color: white; /* Fallback color */")
        self.label.setText("")
        self.label.setObjectName("label")
        self.label.raise_()
        self.acct_pay_Button.raise_()
        self.Acct_mgr_button.raise_()
        self.acct_rcv_Button.raise_()
        self.credit_dept_button.raise_()
        self.payroll_button.raise_()
        self.gl_button.raise_()
        self.budget_button.raise_()
        self.bank_recon_button.raise_()
        Acct_MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(parent=Acct_MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        Acct_MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(parent=Acct_MainWindow)
        self.statusbar.setObjectName("statusbar")
        Acct_MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(Acct_MainWindow)
        QtCore.QMetaObject.connectSlotsByName(Acct_MainWindow)

    def press_it(self, pressed):
        _dir = os.path.dirname(os.path.abspath(__file__))
        scripts = {
            "Accounts Payable":    "Accounts_payable.py",
            "Accounting Manager":  "Accounting_manager.py",
            "Accounts Recievable": "Accounts_receivable.py",
            "Credit Department":   "Credit_dept.py",
            "Payroll Department":  "Payroll_dept.py",
            "General Ledger":      "General_ledger.py",
            "Budget Management":   "Budget_mgmt.py",
            "Bank Reconciliation": "Bank_reconciliation.py",
        }
        script = scripts.get(pressed)
        if script:
            subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)

    def retranslateUi(self, Acct_MainWindow):
        _translate = QtCore.QCoreApplication.translate
        Acct_MainWindow.setWindowTitle(_translate("Acct_MainWindow", "MainWindow"))
        self.acct_pay_Button.setText(_translate("Acct_MainWindow", "Accounts Payable"))
        self.Acct_mgr_button.setText(_translate("Acct_MainWindow", "Accounting Manager"))
        self.acct_rcv_Button.setText(_translate("Acct_MainWindow", "Accounts Receivable"))
        self.credit_dept_button.setText(_translate("Acct_MainWindow", "Credit Department"))
        self.payroll_button.setText(_translate("Acct_MainWindow", "Payroll"))
        self.gl_button.setText(_translate("Acct_MainWindow", "General Ledger"))
        self.budget_button.setText(_translate("Acct_MainWindow", "Budget Management"))
        self.bank_recon_button.setText(_translate("Acct_MainWindow", "Bank Reconciliation"))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    Acct_MainWindow = QtWidgets.QMainWindow()
    ui = Ui_Acct_MainWindow()
    ui.setupUi(Acct_MainWindow)
    Acct_MainWindow.show()
    sys.exit(app.exec())
