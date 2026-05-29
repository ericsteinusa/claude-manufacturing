from .db_pg import get_db
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from .registration import Ui_MainWindow  # Import the generated Python file


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

    def save_data(self):
        # Get input data from the form
        first_name = self.ui.fname_lineEdit.text()
        last_name = self.ui.Lname_lineEdit.text()
        address = self.ui.address_lineEdit.text()
        city = self.ui.city_lineEdit.text()
        state = self.ui.state_lineEdit.text()
        zip_code = self.ui.zip_code_lineEdit.text()
        email = self.ui.email_lineEdit.text()

        if not first_name or not last_name or not address or not city or not state or not zip_code or not email:
            QMessageBox.warning(self, "Input Error", "All fields are required!")
            return

        # Save data to SQLite3 database
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO people (first_name, last_name, address, city, state, zip_code, email) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (first_name, last_name, address, city, state, zip_code, email))
            conn.commit()
            conn.close()

            QMessageBox.information(self, "Success", "Data saved successfully!")
            self.ui.fname_lineEdit.clear()
            self.ui.Lname_lineEdit.clear()
            self.ui.address_lineEdit.clear()
            self.ui.city_lineEdit.clear()
            self.ui.state_lineEdit.clear()
            self.ui.zip_code_lineEdit.clear()
            self.ui.email_lineEdit.clear()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
