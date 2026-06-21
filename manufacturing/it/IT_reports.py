from .launch_utils import launch as _launch
from PyQt6 import QtCore, QtGui, QtWidgets
from .qt_theme import BUTTON_STYLE, apply_blue_palette as _apply_blue_palette

LAUNCH_ITEMS = [
    ("Department Entry",        "dept_entry.py"),
    ("Department Sub Entry",    "dept_sub_entry.py"),
    ("Department and Sub List", "dept_sub.py"),
    ("People and Dept",         "display_people_department.py"),
]


class ITReportsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(60, 40, 60, 40)
        v.setSpacing(16)

        title = QtWidgets.QLabel("IT Reports")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size:22px;font-weight:bold;color:white;padding:8px;")
        v.addWidget(title)
        v.addStretch()

        for label, script in LAUNCH_ITEMS:
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.setFixedHeight(44)
            btn.setFont(QtGui.QFont("", 14))
            btn.clicked.connect(lambda chk=False, s=script: _launch(s))
            v.addWidget(btn)

        v.addStretch()
