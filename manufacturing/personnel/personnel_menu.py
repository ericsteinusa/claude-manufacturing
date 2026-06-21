import sys
from .launch_utils import launch as _launch
from PyQt6 import QtWidgets
from .qt_theme import apply_blue_palette as _apply_blue_palette
from .dept_menu_widget import DeptMenuWidget
from .time_clock_menu import TimeClockWidget
from .Payroll_dept import PayrollDeptWidget

_TITLE = "Personnel Menu"
_ITEMS = [
    ("Personnel CRM",      lambda: _launch("personnel_crm.py")),
    ("Time Clock",         TimeClockWidget),
    ("Payroll",            PayrollDeptWidget),
    ("Registration Form",  lambda: _launch("registration_form.py")),
    ("Update Password",    lambda: _launch("update_users.py")),
    ("Display Dept",       lambda: _launch("display_people_department.py")),
    ("Dept Entry",         lambda: _launch("dept_entry.py")),
    ("Dept Sub Entry",     lambda: _launch("dept_sub_entry.py")),
]


class PersonnelMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = PersonnelMenu()
    w.show()
    sys.exit(app.exec())
