import sys
from .launch_utils import launch as _launch
from PyQt6 import QtCore, QtWidgets
from .personnel_crm import _apply_blue_palette
from .time_clock_menu import TimeClockWidget
from .Payroll_dept import PayrollDeptWidget

BUTTON_STYLE = (
    "QPushButton{background-color: white; border: 2px solid black; "
    "border-radius: 10px;}"
    "QPushButton:hover{background-color: rgb(85, 255, 255); border: 2px solid "
    "rgb(85, 255, 255);}"
)
TAB_STYLE = (
    "QTabWidget::pane{border:1px solid black;}"
    "QTabBar::tab{background:white;border:2px solid black;padding:6px 18px;"
    "border-bottom:none;border-radius:4px 4px 0 0;}"
    "QTabBar::tab:selected{background:rgb(85,255,255);font-weight:bold;}"
    "QTabBar::tab:hover{background:rgb(85,255,255);}"
)


def _launch_tab(script, label):
    w = QtWidgets.QWidget()
    _apply_blue_palette(w)
    v = QtWidgets.QVBoxLayout(w)
    v.addStretch()
    lbl = QtWidgets.QLabel(label)
    lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("color:white;font-size:20px;font-weight:bold;")
    v.addWidget(lbl)
    v.addSpacing(12)
    btn = QtWidgets.QPushButton(f"Open {label}")
    btn.setStyleSheet(BUTTON_STYLE)
    btn.setFixedHeight(44)
    btn.setFixedWidth(260)
    btn.clicked.connect(lambda: _launch(script))
    row = QtWidgets.QHBoxLayout()
    row.addStretch()
    row.addWidget(btn)
    row.addStretch()
    v.addLayout(row)
    v.addStretch()
    return w


class PersonnelMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        import personnel_crm as _pcrm
        _pcrm.init_db()
        self.setWindowTitle("Personnel Menu")
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(0)
        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet(TAB_STYLE)
        tabs.addTab(
    _launch_tab(
        "personnel_crm.py",
        "Personnel CRM"),
         "Personnel CRM")
        tabs.addTab(TimeClockWidget(), "Time Clock")
        tabs.addTab(PayrollDeptWidget(), "Payroll")
        tabs.addTab(
    _launch_tab(
        "registration_form.py",
        "Registration Form"),
         "Registration Form")
        tabs.addTab(
    _launch_tab(
        "update_users.py",
        "Update Password"),
         "Update Password")
        tabs.addTab(
    _launch_tab(
        "display_people_department.py",
        "Display Department"),
         "Display Dept")
        tabs.addTab(_launch_tab("dept_entry.py", "Dept Entry"), "Dept Entry")
        tabs.addTab(
    _launch_tab(
        "dept_sub_entry.py",
        "Dept Sub Entry"),
         "Dept Sub Entry")
        v.addWidget(tabs)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = PersonnelMenu()
    w.show()
    sys.exit(app.exec())
