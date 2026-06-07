"""
cs_calls_widget.py — PyQt6 Customer Service Calls widget.
Replaces the legacy tkinter cs_calls.py for embedding in tabbed menus.
"""
from .db_pg import get_db
from PyQt6 import QtCore, QtGui, QtWidgets

BLUE = QtGui.QColor(0, 85, 255)
BUTTON_STYLE = (
    "QPushButton{background-color:white;border:2px solid "
    "black;border-radius:8px;"
    "padding:4px 12px;font-weight:bold;}"
    "QPushButton:hover{background-color:rgb(85,255,255);}"
)
HDR_STYLE = "font-size:20px;font-weight:bold;color:white;padding:4px;"
LABEL_STYLE = "color:white;font-size:13px;"


def _apply_blue_palette(widget):
    pal = widget.palette()
    for group in (QtGui.QPalette.ColorGroup.Active,
                  QtGui.QPalette.ColorGroup.Inactive,
                  QtGui.QPalette.ColorGroup.Disabled):
        pal.setColor(group, QtGui.QPalette.ColorRole.Window, BLUE)
        pal.setColor(group, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(pal)


def _conn():
    return get_db()


COLS = ["ID", "Customer", "Problem", "Call Date", "Call Time",
        "Completion Date", "Completion Time", "Comments", "Completed"]


class CustomerServiceCallsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _apply_blue_palette(self)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)

        hdr = QtWidgets.QLabel("Customer Service Calls")
        hdr.setStyleSheet(HDR_STYLE)
        hdr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(hdr)

        self._table = QtWidgets.QTableWidget(0, len(COLS))
        self._table.setHorizontalHeaderLabels(COLS)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        v.addWidget(self._table)

        btn_row = QtWidgets.QHBoxLayout()
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.setStyleSheet(BUTTON_STYLE)
        refresh_btn.clicked.connect(self._load)
        btn_row.addStretch()
        btn_row.addWidget(refresh_btn)
        v.addLayout(btn_row)

    def _load(self):
        try:
            conn = _conn()
            rows = conn.execute(
                "SELECT id, customer_id, call, call_date, call_time, "
                "completion_date, completion_time, comments_box, "
                "completion_box "
                "FROM calls2 ORDER BY id DESC LIMIT 200"
            ).fetchall()
            conn.close()
        except Exception:
            rows = []

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self._table.setItem(
                    r, c, QtWidgets.QTableWidgetItem(str(val or "")))

        self._table.resizeColumnsToContents()
