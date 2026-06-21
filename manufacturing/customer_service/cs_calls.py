"""Customer Service Calls — PyQt6 desktop screen.

Rewritten from the legacy tkinter version. Launched as a desktop subprocess
from the Customer Service menu leaves (``python -m manufacturing.cs_calls``)
and also embedded as a tab via ``CustomerServiceCallsWidget``
(see cs_calls_widget.py). The full add/update/delete/search logic lives in
that widget; this module is just the standalone window wrapper.
"""
import sys

from PyQt6 import QtWidgets

from ..accounts import get_current_user_email
from .cs_calls_widget import CustomerServiceCallsWidget, _apply_blue_palette


class CustomerServiceCalls(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        email = get_current_user_email()
        title = (f"Customer Service Calls — {email}" if email
                 else "Customer Service Calls")
        self.setWindowTitle(title)
        self.resize(1210, 650)
        _apply_blue_palette(self)
        self.setCentralWidget(CustomerServiceCallsWidget())


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = CustomerServiceCalls()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
