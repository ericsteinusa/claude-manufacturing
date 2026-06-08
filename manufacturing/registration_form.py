from .db_pg import get_db
from .log_utils import get_logger
import sys
import psycopg2
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from .registration import Ui_MainWindow  # Import the generated Python file

log = get_logger(__name__)


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Initialize the database
        self.initialize_database()

        # Connect the Submit button to the save_data method
        self.ui.submit_pushButton.clicked.connect(self.save_data)

    def initialize_database(self):
        # Connect to SQLite3 database and create table if it doesn't exist
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id SERIAL PRIMARY KEY,
            first_name text not null,
            last_name text not null,
            address text not null,
            city text not null,
            state text not null,
            zip_code text not null,
            email text NOT NULL
        )
        """)
        conn.commit()
        conn.close()
        log.debug("Ensured people table exists")

    def save_data(self):
        # Get input data from the form
        first_name = self.ui.fname_lineEdit.text()
        last_name = self.ui.Lname_lineEdit.text()
        address = self.ui.address_lineEdit.text()
        city = self.ui.city_lineEdit.text()
        state = self.ui.state_lineEdit.text()
        zip_code = self.ui.zip_code_lineEdit.text()
        email = self.ui.email_lineEdit.text()

        if not first_name or not last_name or not address or not city or not state or not zip_code or not email:  # noqa: E501
            QMessageBox.warning(
    self, "Input Error", "All fields are required!")
            return

        # Save data to SQLite3 database
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM people WHERE email = %s", (email,))
            if cursor.fetchone():
                conn.close()
                log.warning(
                    "Registration rejected: %s already exists", email)
                QMessageBox.warning(self, "Email Already Registered",
                                    "An account with that email already "
                                    "exists. "
                                    "Please use a different email address.")
                return
            cursor.execute("INSERT INTO people (first_name, last_name, address, city, state, zip_code, email) VALUES (%s, %s, %s, %s, %s, %s, %s)",  # noqa: E501
                           (first_name, last_name, address, city, state, zip_code, email))  # noqa: E501
            conn.commit()
            conn.close()

            log.info("Registered new person %s", email)
            QMessageBox.information(
    self, "Success", "Data saved successfully!")
            self.ui.fname_lineEdit.clear()
            self.ui.Lname_lineEdit.clear()
            self.ui.address_lineEdit.clear()
            self.ui.city_lineEdit.clear()
            self.ui.state_lineEdit.clear()
            self.ui.zip_code_lineEdit.clear()
            self.ui.email_lineEdit.clear()
        except psycopg2.IntegrityError:
            # UNIQUE(email) violation — e.g. the email was registered between the  # noqa: E501
            # check above and the insert.
            log.warning(
                "Registration race for %s: email already exists", email,
                exc_info=True)
            QMessageBox.warning(self, "Email Already Registered",
                                "An account with that email already exists. "
                                "Please use a different email address.")
        except Exception as e:
            log.error(
                "Registration failed for %s", email, exc_info=True)
            QMessageBox.critical(
    self, "Database Error", f"An error occurred: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
