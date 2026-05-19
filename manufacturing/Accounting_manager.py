"""
Accounting_manager.py — Accounting Manager dashboard
"""
import sys, os, sqlite3, subprocess
from PyQt6 import QtCore, QtGui, QtWidgets

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "company.db")

BLUE = QtGui.QColor(0, 85, 255)

BUTTON_STYLE = (
    "QPushButton{"
    "  background-color: white;"
    "  border: 2px solid black;"
    "  border-radius: 10px;"
    "  font-size: 15px;"
    "  font-weight: bold;"
    "  padding: 10px;"
    "}"
    "QPushButton:hover{"
    "  background-color: rgb(85, 255, 255);"
    "  border: 2px solid rgb(85, 255, 255);"
    "}"
)


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _apply_palette(widget):
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.ColorRole.Window,      BLUE)
    pal.setColor(QtGui.QPalette.ColorRole.Button,      BLUE)
    pal.setColor(QtGui.QPalette.ColorRole.Base,        QtGui.QColor(255, 255, 255))
    pal.setColor(QtGui.QPalette.ColorRole.WindowText,  QtGui.QColor(255, 255, 255))
    pal.setColor(QtGui.QPalette.ColorRole.ButtonText,  QtGui.QColor(0,   0,   0))
    pal.setColor(QtGui.QPalette.ColorRole.Text,        QtGui.QColor(0,   0,   0))
    widget.setPalette(pal)


class AccountingManagerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Accounting Manager")
        self.resize(820, 580)
        _apply_palette(self)
        self._build_ui()
        self._load_summary()

    def _build_ui(self):
        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        root = QtWidgets.QVBoxLayout(cw)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(18)

        # ── Title ─────────────────────────────────────────────────────────────
        title = QtWidgets.QLabel("Accounting Manager")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 26px; font-weight: bold; color: white; padding: 8px;"
        )
        root.addWidget(title)

        # ── Department buttons (2 × 3 grid) ───────────────────────────────────
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(14)
        grid.setContentsMargins(0, 0, 0, 0)

        departments = [
            ("Accounts Payable",    "Accounts_payable.py"),
            ("Accounts Receivable", "Accounts_receivable.py"),
            ("Credit Department",   "Credit_dept.py"),
            ("Payroll Department",  "Payroll_dept.py"),
            ("General Ledger",      "General_ledger.py"),
            ("Budget Management",   "Budget_mgmt.py"),
        ]

        for i, (label, script) in enumerate(departments):
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(BUTTON_STYLE)
            btn.setMinimumHeight(72)
            btn.clicked.connect(lambda _=False, s=script: self._launch(s))
            grid.addWidget(btn, i // 2, i % 2)

        root.addLayout(grid)

        # ── Summary stats panel ────────────────────────────────────────────────
        stats_box = QtWidgets.QGroupBox()
        stats_box.setStyleSheet(
            "QGroupBox{"
            "  background-color: rgba(255,255,255,20);"
            "  border: 1px solid rgba(255,255,255,80);"
            "  border-radius: 8px;"
            "  margin-top: 0px;"
            "}"
        )
        stats_row = QtWidgets.QHBoxLayout(stats_box)
        stats_row.setContentsMargins(20, 14, 20, 14)
        stats_row.setSpacing(0)

        self._stat_vals = {}
        stats = [
            ("journals",  "Journal Entries"),
            ("posted",    "Posted"),
            ("draft",     "Draft"),
            ("accounts",  "GL Accounts"),
            ("vendors",   "Vendors"),
            ("customers", "Customers"),
        ]

        for idx, (key, label) in enumerate(stats):
            col = QtWidgets.QVBoxLayout()
            col.setSpacing(2)

            val = QtWidgets.QLabel("—")
            val.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")

            lbl = QtWidgets.QLabel(label)
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 10px; color: rgba(255,255,255,180);")

            col.addWidget(val)
            col.addWidget(lbl)
            self._stat_vals[key] = val
            stats_row.addLayout(col)

            if idx < len(stats) - 1:
                sep = QtWidgets.QFrame()
                sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
                sep.setFixedWidth(1)
                sep.setStyleSheet("background-color: rgba(255,255,255,60);")
                stats_row.addWidget(sep)

        root.addWidget(stats_box)

    def _load_summary(self):
        try:
            with _conn() as con:
                total    = con.execute("SELECT COUNT(*) FROM gl_journal").fetchone()[0]
                posted   = con.execute("SELECT COUNT(*) FROM gl_journal WHERE posted=1").fetchone()[0]
                draft    = total - posted
                accounts = con.execute("SELECT COUNT(*) FROM gl_account WHERE is_active=1").fetchone()[0]
                try:
                    vendors = con.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
                except Exception:
                    vendors = 0
                try:
                    customers = con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
                except Exception:
                    customers = 0
            self._stat_vals["journals"].setText(str(total))
            self._stat_vals["posted"].setText(str(posted))
            self._stat_vals["draft"].setText(str(draft))
            self._stat_vals["accounts"].setText(str(accounts))
            self._stat_vals["vendors"].setText(str(vendors))
            self._stat_vals["customers"].setText(str(customers))
        except Exception:
            pass

    def _launch(self, script):
        _dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen([sys.executable, os.path.join(_dir, script)], cwd=_dir)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = AccountingManagerWindow()
    win.show()
    sys.exit(app.exec())
