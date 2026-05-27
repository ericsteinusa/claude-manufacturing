import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtSql import QSqlDatabase

def connect_to_database():
    db = QSqlDatabase.addDatabase('QPSQL')
    db.setHostName('localhost')
    db.setDatabaseName('company')
    db.setUserName('postgres')
    db.setPassword('')
    db.setPort(5432)

    if not db.open():
        QMessageBox.critical(None, 'Database Connection', 'Failed to connect to the database.')
        return False
    else:
        QMessageBox.information(None, 'Database Connection', 'Successfully connected to the database.')
        return True

# Create an instance of QApplication
app = QApplication(sys.argv)

# Connect to the database
if connect_to_database():
    sys.exit(app.exec())
else:
    sys.exit(1)
