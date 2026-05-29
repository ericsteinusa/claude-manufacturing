from .db_pg import get_db
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from password import Ui_MainWindow  # Import the generated Python file


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Initialize the database
        self.initialize_database()

    def initialize_database(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS people (
            id SERIAL PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            employee_id INTEGER NOT NULL DEFAULT 0,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            email TEXT NOT NULL
        )
    ''')
        print("Database connected successfully!")

        conn.commit()
        conn.close()

# Connect the Submit button to the save_data method
    #    self.ui.submit_Button.clicked.connect(self.check_name)


def check_name(self):
    conn = get_db()
    cursor = conn.cursor()
    email = self.ui.email_lineEdit.text()

    if not email.strip():
        QMessageBox.showwarning("Input Error", "Please enter your email.")
    else:
        cursor.execute("SELECT passwd.id as passwd_id, passwd.people_id as people_id, people.email as people_email, passwd.password as passwd_password FROM passwd JOIN people ON passwd.people_id = people.id WHERE people_email = %s", (email,))
        result = cursor.fetchone()
        if result:
            # id = result[0]
            email = self.ui.email_lineEdit.text()
            # password = self.ui.passwd_lineEdit.text()
            QMessageBox.information("Result", f"Email '{email}' exists in the database!")
            QMessageBox.information(
                "User Details", f"id: {result[0]}\nPeople ID: {result[1]}\nEmail: {result[2]}\nPassword: {result[3]}")


'''
def save_data(self):
    # Get input data from the form
    conn = get_db()
    cursor = conn.cursor()
    email = self.ui.email_lineEdit.text()
    password = self.ui.passwd_lineEdit.text()


    if not email or not password:
        QMessageBox.warning(self, "Input Error", "All fields are required!")
        return

    # Save data to SQLite3 database
    cursor.execute("UPDATE passwd SET password = %s WHERE id = %s", (password, id))
    QMessageBox.showinfo("Update Status", "Password updated successfully!")

    self.ui.email_lineEdit.clear()
    self.ui.passwd_lineEdit.clear()

        # Update data into the database


    conn.commit()
    conn.close()
'''
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
