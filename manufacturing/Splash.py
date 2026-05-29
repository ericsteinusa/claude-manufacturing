import sys
import os
from PyQt6 import QtCore, QtGui, QtWidgets


class SplashScreen(QtWidgets.QSplashScreen):
    def __init__(self):
        img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manufacturing2.png")
        pixmap = QtGui.QPixmap(img_path)
        super().__init__(pixmap, QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setMask(pixmap.mask())


def main():
    app = QtWidgets.QApplication(sys.argv)

    splash = SplashScreen()
    splash.show()
    app.processEvents()

    def launch_login():
        splash.finish(None)
        from login_app import init_db, LoginWindow, SessionWindow

        init_db()

        login = LoginWindow()

        def on_login(email: str):
            session = SessionWindow(email)
            session.logged_out.connect(on_logout)
            login._session = session
            session.show()

        def on_logout():
            login._session = None
            login.email_input.clear()
            login.passwd_input.clear()
            login.show()

        login.login_successful.connect(on_login)
        login.show()
        # Keep references alive for the duration of the app
        app._login = login

    QtCore.QTimer.singleShot(3000, launch_login)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
