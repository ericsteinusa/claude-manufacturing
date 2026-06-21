import sys
from ..launch_utils import launch as _launch
from PyQt6 import QtWidgets
from ..qt_theme import apply_blue_palette as _apply_blue_palette
from ..dept_menu_widget import DeptMenuWidget
from ..payroll.Payroll_dept import PayrollDeptWidget

_TITLE = "Personnel Manager Menu"
_ITEMS = [
    ("Personnel CRM",  lambda: _launch("personnel_crm.py")),
    ("Payroll",        PayrollDeptWidget),
    ("Dept Entry",     lambda: _launch("dept_entry.py")),
    ("Dept Sub Entry", lambda: _launch("dept_sub_entry.py")),
]


class PersonnelMgrMenu(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_TITLE)
        self.resize(1100, 720)
        _apply_blue_palette(self)
        self.setCentralWidget(DeptMenuWidget(_TITLE, _ITEMS))


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = PersonnelMgrMenu()
    w.show()
    sys.exit(app.exec())
