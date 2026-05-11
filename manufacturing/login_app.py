import sys
import sqlite3
from PyQt6 import QtCore, QtGui, QtWidgets


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect("company.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            ID INTEGER NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS passwd (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            people_id INTEGER NOT NULL UNIQUE,
            password TEXT NOT NULL,
            FOREIGN KEY (people_id) REFERENCES people(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            people_id INTEGER NOT NULL UNIQUE,
            role_id INTEGER NOT NULL,
            FOREIGN KEY (people_id) REFERENCES people(id),
            FOREIGN KEY (role_id) REFERENCES roles(id)
        )
    """)
    default_roles = [
        ("Admin",    "Full access to all screens and settings"),
        ("Manager",  "Access to department management screens"),
        ("Employee", "Standard employee access"),
        ("Viewer",   "Read-only access"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO roles (role_name, description) VALUES (?, ?)",
        default_roles,
    )
    conn.commit()
    conn.close()


def get_all_users_with_roles():
    conn = get_db()
    rows = conn.execute("""
        SELECT p.id, p.first_name, p.last_name, p.email,
               r.id as role_id, r.role_name
        FROM people p
        LEFT JOIN user_roles ur ON ur.people_id = p.id
        LEFT JOIN roles r ON r.id = ur.role_id
        ORDER BY p.last_name, p.first_name
    """).fetchall()
    conn.close()
    return rows


def get_all_roles():
    conn = get_db()
    rows = conn.execute("SELECT id, role_name, description FROM roles ORDER BY id").fetchall()
    conn.close()
    return rows


def set_user_role(people_id: int, role_id: int):
    conn = get_db()
    conn.execute("""
        INSERT INTO user_roles (people_id, role_id) VALUES (?, ?)
        ON CONFLICT(people_id) DO UPDATE SET role_id = excluded.role_id
    """, (people_id, role_id))
    conn.commit()
    conn.close()


def remove_user_role(people_id: int):
    conn = get_db()
    conn.execute("DELETE FROM user_roles WHERE people_id = ?", (people_id,))
    conn.commit()
    conn.close()


def verify_login(email: str, password: str) -> bool:
    conn = get_db()
    row = conn.execute(
        """
        SELECT pw.id as pw_id, pw.password
        FROM passwd pw
        JOIN people p ON pw.people_id = p.id
        WHERE p.email = ?
        """,
        (email,),
    ).fetchone()
    if row is None:
        conn.close()
        return False

    ok = (password == row["password"])
    conn.close()
    return ok


def create_user(email: str, password: str, first_name: str = "", last_name: str = "",
                address: str = "", city: str = "", state: str = "", zip_code: str = "",
                employee_id: int = 0) -> bool:
    try:
        conn = get_db()
        if conn.execute("SELECT id FROM people WHERE email = ?", (email,)).fetchone():
            conn.close()
            return False
        cursor = conn.execute(
            "INSERT INTO people (first_name, last_name, ID, address, city, state, zip_code, email) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (first_name, last_name, employee_id, address, city, state, zip_code, email),
        )
        conn.execute(
            "INSERT INTO passwd (people_id, password) VALUES (?, ?)",
            (cursor.lastrowid, password),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def change_password(email: str, current_password: str, new_password: str) -> bool:
    """Verify current password then update to new one. Returns False if auth fails."""
    if not verify_login(email, current_password):
        return False
    return reset_password(email, new_password)


def reset_password(email: str, new_password: str) -> bool:
    """Update the password for an existing account. Returns False if email not found."""
    conn = get_db()
    row = conn.execute(
        """
        SELECT pw.id as pw_id
        FROM passwd pw
        JOIN people p ON pw.people_id = p.id
        WHERE p.email = ?
        """,
        (email,),
    ).fetchone()
    if row is None:
        conn.close()
        return False
    conn.execute("UPDATE passwd SET password = ? WHERE id = ?", (new_password, row["pw_id"]))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Shared styles
# ---------------------------------------------------------------------------
BLUE = QtGui.QColor(0, 85, 255)

BUTTON_STYLE = (
    "QPushButton{"
    "background-color: white;"
    "border: 2px solid black;"
    "border-radius: 10px;}"
    "QPushButton:hover{"
    "background-color: rgb(85, 255, 255);"
    "border: 2px solid rgb(85, 255, 255);}"
)
INPUT_STYLE = (
    "QLineEdit{"
    "background-color: white;"
    "border: 2px solid black;"
    "border-radius: 4px;"
    "padding: 2px 6px;}"
)
LABEL_STYLE = "color: white; font-size: 13px;"
LINK_STYLE = (
    "QPushButton{color: white; background: transparent; border: none; text-decoration: underline;}"
    "QPushButton:hover{color: rgb(85, 255, 255);}"
)


def _apply_blue_palette(widget: QtWidgets.QWidget):
    palette = widget.palette()
    for group in (
        QtGui.QPalette.ColorGroup.Active,
        QtGui.QPalette.ColorGroup.Inactive,
        QtGui.QPalette.ColorGroup.Disabled,
    ):
        palette.setColor(group, QtGui.QPalette.ColorRole.Window, BLUE)
        palette.setColor(group, QtGui.QPalette.ColorRole.Button, BLUE)
    widget.setPalette(palette)


def _make_row(label_text: str, widget: QtWidgets.QWidget, label_width: int = 100):
    row = QtWidgets.QHBoxLayout()
    lbl = QtWidgets.QLabel(label_text)
    lbl.setFixedWidth(label_width)
    lbl.setStyleSheet(LABEL_STYLE)
    row.addWidget(lbl)
    row.addWidget(widget)
    return row


# ---------------------------------------------------------------------------
# Forgot password window
# ---------------------------------------------------------------------------
class ForgotPasswordWindow(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reset Password")
        self.setFixedSize(420, 300)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(50, 35, 50, 35)
        layout.setSpacing(14)

        title = QtWidgets.QLabel("Reset Your Password")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Enter your email to verify your account,\nthen choose a new password.")
        subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: white; font-size: 11px;")
        layout.addWidget(subtitle)

        layout.addSpacing(4)

        # Email
        self.email_input = QtWidgets.QLineEdit()
        self.email_input.setPlaceholderText("Your registered email")
        self.email_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Email:", self.email_input))

        # New password (hidden until email verified)
        self.new_passwd_input = QtWidgets.QLineEdit()
        self.new_passwd_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.new_passwd_input.setPlaceholderText("Minimum 8 characters")
        self.new_passwd_input.setStyleSheet(INPUT_STYLE)
        self.new_passwd_input.setEnabled(False)
        layout.addLayout(_make_row("New Password:", self.new_passwd_input, label_width=115))

        self.confirm_input = QtWidgets.QLineEdit()
        self.confirm_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("Re-enter new password")
        self.confirm_input.setStyleSheet(INPUT_STYLE)
        self.confirm_input.setEnabled(False)
        layout.addLayout(_make_row("Confirm:", self.confirm_input, label_width=115))

        layout.addSpacing(6)

        btn_row = QtWidgets.QHBoxLayout()
        self.action_btn = QtWidgets.QPushButton("Verify Email")
        self.action_btn.setFixedHeight(36)
        self.action_btn.setStyleSheet(BUTTON_STYLE)
        self.action_btn.clicked.connect(self._on_action)
        self.email_input.returnPressed.connect(self._on_action)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.action_btn)
        btn_row.addSpacing(20)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self._email_verified = False

    def _on_action(self):
        if not self._email_verified:
            self._verify_email()
        else:
            self._save_password()

    def _verify_email(self):
        email = self.email_input.text().strip()
        if not email or "@" not in email:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please enter a valid email address.")
            return

        conn = get_db()
        found = conn.execute("SELECT id FROM people WHERE email = ?", (email,)).fetchone()
        conn.close()

        # Give the same message whether found or not to avoid account enumeration
        if not found:
            QtWidgets.QMessageBox.warning(
                self, "Not Found",
                "No account found for that email address."
            )
            return

        self._email_verified = True
        self.email_input.setEnabled(False)
        self.new_passwd_input.setEnabled(True)
        self.confirm_input.setEnabled(True)
        self.action_btn.setText("Reset Password")
        self.new_passwd_input.setFocus()

    def _save_password(self):
        email = self.email_input.text().strip()
        new_pw = self.new_passwd_input.text()
        confirm = self.confirm_input.text()

        if len(new_pw) < 8:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Password must be at least 8 characters.")
            return
        if new_pw != confirm:
            self.confirm_input.clear()
            QtWidgets.QMessageBox.warning(self, "Input Error", "Passwords do not match.")
            return

        self.action_btn.setEnabled(False)
        self.action_btn.setText("Saving...")

        ok = reset_password(email, new_pw)

        self.action_btn.setEnabled(True)
        self.action_btn.setText("Reset Password")

        if ok:
            QtWidgets.QMessageBox.information(
                self, "Success",
                "Your password has been reset.\nYou can now log in with your new password."
            )
            self.accept()
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Password reset failed. Please try again.")


# ---------------------------------------------------------------------------
# Change password window
# ---------------------------------------------------------------------------
class ChangePasswordWindow(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Password")
        self.setFixedSize(420, 290)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(50, 35, 50, 35)
        layout.setSpacing(14)

        title = QtWidgets.QLabel("Change Password")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        layout.addSpacing(4)

        self.email_input = QtWidgets.QLineEdit()
        self.email_input.setPlaceholderText("Your registered email")
        self.email_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Email:", self.email_input))

        self.current_input = QtWidgets.QLineEdit()
        self.current_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.current_input.setPlaceholderText("Current password")
        self.current_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Current:", self.current_input, label_width=115))

        self.new_input = QtWidgets.QLineEdit()
        self.new_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.new_input.setPlaceholderText("Minimum 8 characters")
        self.new_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("New:", self.new_input, label_width=115))

        self.confirm_input = QtWidgets.QLineEdit()
        self.confirm_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("Re-enter new password")
        self.confirm_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Confirm:", self.confirm_input, label_width=115))

        layout.addSpacing(6)

        btn_row = QtWidgets.QHBoxLayout()
        self.submit_btn = QtWidgets.QPushButton("Change Password")
        self.submit_btn.setFixedHeight(36)
        self.submit_btn.setStyleSheet(BUTTON_STYLE)
        self.submit_btn.clicked.connect(self._on_submit)
        self.confirm_input.returnPressed.connect(self._on_submit)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.submit_btn)
        btn_row.addSpacing(20)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_submit(self):
        email = self.email_input.text().strip()
        current = self.current_input.text()
        new_pw = self.new_input.text()
        confirm = self.confirm_input.text()

        if not email or "@" not in email:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please enter a valid email address.")
            return
        if not current:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please enter your current password.")
            return
        if len(new_pw) < 8:
            QtWidgets.QMessageBox.warning(self, "Input Error", "New password must be at least 8 characters.")
            return
        if new_pw != confirm:
            self.confirm_input.clear()
            QtWidgets.QMessageBox.warning(self, "Input Error", "New passwords do not match.")
            return
        if new_pw == current:
            QtWidgets.QMessageBox.warning(self, "Input Error", "New password must differ from your current password.")
            return

        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("Saving...")

        ok = change_password(email, current, new_pw)

        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Change Password")

        if ok:
            QtWidgets.QMessageBox.information(
                self, "Success", "Your password has been changed successfully."
            )
            self.accept()
        else:
            self.current_input.clear()
            QtWidgets.QMessageBox.warning(
                self, "Failed", "Incorrect email or current password."
            )


# ---------------------------------------------------------------------------
# Register window
# ---------------------------------------------------------------------------
class RegisterWindow(QtWidgets.QDialog):
    registration_complete = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register New User")
        self.setFixedSize(520, 560)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("Register New Employee")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        layout.addSpacing(6)

        # Name row
        name_row = QtWidgets.QHBoxLayout()
        fname_lbl = QtWidgets.QLabel("First Name:")
        fname_lbl.setFixedWidth(90)
        fname_lbl.setStyleSheet(LABEL_STYLE)
        self.fname_input = QtWidgets.QLineEdit()
        self.fname_input.setPlaceholderText("First name")
        self.fname_input.setStyleSheet(INPUT_STYLE)
        lname_lbl = QtWidgets.QLabel("Last Name:")
        lname_lbl.setFixedWidth(80)
        lname_lbl.setStyleSheet(LABEL_STYLE)
        self.lname_input = QtWidgets.QLineEdit()
        self.lname_input.setPlaceholderText("Last name")
        self.lname_input.setStyleSheet(INPUT_STYLE)
        name_row.addWidget(fname_lbl)
        name_row.addWidget(self.fname_input)
        name_row.addSpacing(10)
        name_row.addWidget(lname_lbl)
        name_row.addWidget(self.lname_input)
        layout.addLayout(name_row)

        self.emp_id_input = QtWidgets.QLineEdit()
        self.emp_id_input.setPlaceholderText("Employee ID (numbers only)")
        self.emp_id_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Employee ID:", self.emp_id_input))

        self.address_input = QtWidgets.QLineEdit()
        self.address_input.setPlaceholderText("Street address")
        self.address_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Address:", self.address_input))

        # City / State / Zip row
        csz_row = QtWidgets.QHBoxLayout()
        city_lbl = QtWidgets.QLabel("City:")
        city_lbl.setFixedWidth(35)
        city_lbl.setStyleSheet(LABEL_STYLE)
        self.city_input = QtWidgets.QLineEdit()
        self.city_input.setPlaceholderText("City")
        self.city_input.setStyleSheet(INPUT_STYLE)
        state_lbl = QtWidgets.QLabel("State:")
        state_lbl.setFixedWidth(40)
        state_lbl.setStyleSheet(LABEL_STYLE)
        self.state_input = QtWidgets.QLineEdit()
        self.state_input.setPlaceholderText("ST")
        self.state_input.setMaxLength(2)
        self.state_input.setFixedWidth(40)
        self.state_input.setStyleSheet(INPUT_STYLE)
        zip_lbl = QtWidgets.QLabel("Zip:")
        zip_lbl.setFixedWidth(30)
        zip_lbl.setStyleSheet(LABEL_STYLE)
        self.zip_input = QtWidgets.QLineEdit()
        self.zip_input.setPlaceholderText("Zip")
        self.zip_input.setMaxLength(10)
        self.zip_input.setFixedWidth(80)
        self.zip_input.setStyleSheet(INPUT_STYLE)
        csz_row.addWidget(city_lbl)
        csz_row.addWidget(self.city_input)
        csz_row.addSpacing(8)
        csz_row.addWidget(state_lbl)
        csz_row.addWidget(self.state_input)
        csz_row.addSpacing(8)
        csz_row.addWidget(zip_lbl)
        csz_row.addWidget(self.zip_input)
        layout.addLayout(csz_row)

        self.email_input = QtWidgets.QLineEdit()
        self.email_input.setPlaceholderText("Email address")
        self.email_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Email:", self.email_input))

        self.passwd_input = QtWidgets.QLineEdit()
        self.passwd_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.passwd_input.setPlaceholderText("Minimum 8 characters")
        self.passwd_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Password:", self.passwd_input))

        self.confirm_input = QtWidgets.QLineEdit()
        self.confirm_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("Re-enter password")
        self.confirm_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Confirm:", self.confirm_input))

        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        self.submit_btn = QtWidgets.QPushButton("Register")
        self.submit_btn.setFixedHeight(36)
        self.submit_btn.setStyleSheet(BUTTON_STYLE)
        self.submit_btn.clicked.connect(self._on_register)
        self.confirm_input.returnPressed.connect(self._on_register)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.submit_btn)
        btn_row.addSpacing(20)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_register(self):
        first = self.fname_input.text().strip()
        last = self.lname_input.text().strip()
        email = self.email_input.text().strip()
        password = self.passwd_input.text()
        confirm = self.confirm_input.text()
        emp_id_text = self.emp_id_input.text().strip()
        address = self.address_input.text().strip()
        city = self.city_input.text().strip()
        state = self.state_input.text().strip()
        zip_code = self.zip_input.text().strip()

        if not first or not last:
            QtWidgets.QMessageBox.warning(self, "Input Error", "First and last name are required.")
            return
        if not email or "@" not in email:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please enter a valid email address.")
            return
        if len(password) < 8:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Password must be at least 8 characters.")
            return
        if password != confirm:
            self.confirm_input.clear()
            QtWidgets.QMessageBox.warning(self, "Input Error", "Passwords do not match.")
            return

        emp_id = 0
        if emp_id_text:
            if not emp_id_text.isdigit():
                QtWidgets.QMessageBox.warning(self, "Input Error", "Employee ID must be a number.")
                return
            emp_id = int(emp_id_text)

        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("Saving...")

        ok = create_user(
            email=email, password=password,
            first_name=first, last_name=last,
            address=address, city=city, state=state, zip_code=zip_code,
            employee_id=emp_id,
        )

        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Register")

        if ok:
            QtWidgets.QMessageBox.information(
                self, "Success",
                f"Account created for {first} {last}.\nYou can now log in with your email and password."
            )
            self.registration_complete.emit()
            self.accept()
        else:
            QtWidgets.QMessageBox.warning(
                self, "Registration Failed",
                "That email address is already registered."
            )


# ---------------------------------------------------------------------------
# User roles window
# ---------------------------------------------------------------------------
class RolesWindow(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Roles")
        self.resize(700, 480)
        _apply_blue_palette(self)
        self._pending = {}   # people_id -> role_id, tracks unsaved changes
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("User Role Management")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Email", "Current Role", "Assign Role"])
        self.table.horizontalHeader().setStyleSheet("color: black; font-weight: bold;")
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Save Changes")
        self.save_btn.setFixedHeight(34)
        self.save_btn.setStyleSheet(BUTTON_STYLE)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_changes)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(BUTTON_STYLE)
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(self.save_btn)
        btn_row.addSpacing(20)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_data(self):
        roles = get_all_roles()
        role_names = ["(none)"] + [r["role_name"] for r in roles]
        self._role_id_map = {r["role_name"]: r["id"] for r in roles}

        users = get_all_users_with_roles()
        self.table.setRowCount(len(users))

        for row_idx, user in enumerate(users):
            people_id = user["id"]
            name = f"{user['first_name']} {user['last_name']}"
            email = user["email"]
            current_role = user["role_name"] or "(none)"

            self.table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(name))
            self.table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(email))
            self.table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(current_role))

            combo = QtWidgets.QComboBox()
            combo.addItems(role_names)
            combo.setCurrentText(current_role)
            combo.setProperty("people_id", people_id)
            combo.currentTextChanged.connect(self._on_role_changed)
            self.table.setCellWidget(row_idx, 3, combo)

    def _on_role_changed(self, role_name: str):
        combo = self.sender()
        people_id = combo.property("people_id")
        if role_name == "(none)":
            self._pending[people_id] = None
        else:
            self._pending[people_id] = self._role_id_map.get(role_name)
        self.save_btn.setEnabled(bool(self._pending))

    def _save_changes(self):
        for people_id, role_id in self._pending.items():
            if role_id is None:
                remove_user_role(people_id)
            else:
                set_user_role(people_id, role_id)

        saved = len(self._pending)
        self._pending.clear()
        self.save_btn.setEnabled(False)

        # Refresh the "Current Role" column
        users = get_all_users_with_roles()
        for row_idx, user in enumerate(users):
            current_role = user["role_name"] or "(none)"
            self.table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(current_role))

        QtWidgets.QMessageBox.information(
            self, "Saved", f"{saved} role assignment(s) updated."
        )


# ---------------------------------------------------------------------------
# Session window  (shown after login, hosts the main app + logout button)
# ---------------------------------------------------------------------------
class SessionWindow(QtWidgets.QMainWindow):
    logged_out = QtCore.pyqtSignal()

    def __init__(self, email: str, parent=None):
        super().__init__(parent)
        self.email = email
        self.setWindowTitle("Manufacturing System")
        self.setMinimumSize(729, 761)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        # Toolbar with user info and logout button
        toolbar = self.addToolBar("Session")
        toolbar.setMovable(False)
        toolbar.setStyleSheet(
            "QToolBar { background-color: rgb(0, 60, 180); border: none; spacing: 8px; padding: 4px; }"
        )

        roles_btn = QtWidgets.QPushButton("User Roles")
        roles_btn.setFixedHeight(28)
        roles_btn.setStyleSheet(BUTTON_STYLE)
        roles_btn.clicked.connect(self._open_roles)
        toolbar.addWidget(roles_btn)

        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        toolbar.addWidget(spacer)

        user_lbl = QtWidgets.QLabel(f"Logged in as:  {self.email}")
        user_lbl.setStyleSheet("color: white; font-size: 12px; padding-right: 12px;")
        toolbar.addWidget(user_lbl)

        logout_btn = QtWidgets.QPushButton("Logout")
        logout_btn.setFixedHeight(28)
        logout_btn.setStyleSheet(BUTTON_STYLE)
        logout_btn.clicked.connect(self._on_logout)
        toolbar.addWidget(logout_btn)

        # Central placeholder — replace with your actual main menu widget here
        central = QtWidgets.QWidget()
        _apply_blue_palette(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        welcome = QtWidgets.QLabel(f"Welcome to the Manufacturing System")
        welcome.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        welcome.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        layout.addWidget(welcome)

        self.setCentralWidget(central)

    def _open_roles(self):
        dlg = RolesWindow(self)
        dlg.exec()

    def _on_logout(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Logout", "Are you sure you want to logout?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.logged_out.emit()
            self.close()


# ---------------------------------------------------------------------------
# Login window
# ---------------------------------------------------------------------------
class LoginWindow(QtWidgets.QMainWindow):
    login_successful = QtCore.pyqtSignal(str)  # emits the logged-in email

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Company Login")
        self.setFixedSize(480, 360)
        _apply_blue_palette(self)
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(60, 40, 60, 30)
        layout.setSpacing(16)

        title = QtWidgets.QLabel("Manufacturing System Login")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        layout.addSpacing(10)

        self.email_input = QtWidgets.QLineEdit()
        self.email_input.setPlaceholderText("Enter your email")
        self.email_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Email:", self.email_input))

        self.passwd_input = QtWidgets.QLineEdit()
        self.passwd_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.passwd_input.setPlaceholderText("Enter your password")
        self.passwd_input.setStyleSheet(INPUT_STYLE)
        layout.addLayout(_make_row("Password:", self.passwd_input))

        layout.addSpacing(10)

        self.login_btn = QtWidgets.QPushButton("Login")
        self.login_btn.setFixedHeight(36)
        self.login_btn.setStyleSheet(BUTTON_STYLE)
        self.login_btn.clicked.connect(self._on_login)
        self.passwd_input.returnPressed.connect(self._on_login)
        layout.addWidget(self.login_btn)

        forgot_btn = QtWidgets.QPushButton("Forgot Password?")
        forgot_btn.setFixedHeight(28)
        forgot_btn.setStyleSheet(LINK_STYLE)
        forgot_btn.clicked.connect(self._open_forgot_password)
        layout.addWidget(forgot_btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        change_btn = QtWidgets.QPushButton("Change Password")
        change_btn.setFixedHeight(28)
        change_btn.setStyleSheet(LINK_STYLE)
        change_btn.clicked.connect(self._open_change_password)
        layout.addWidget(change_btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        register_btn = QtWidgets.QPushButton("Register New User")
        register_btn.setFixedHeight(28)
        register_btn.setStyleSheet(LINK_STYLE)
        register_btn.clicked.connect(self._open_register)
        layout.addWidget(register_btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

    def _open_forgot_password(self):
        dlg = ForgotPasswordWindow(self)
        dlg.exec()

    def _open_change_password(self):
        dlg = ChangePasswordWindow(self)
        dlg.exec()

    def _open_register(self):
        dlg = RegisterWindow(self)
        dlg.registration_complete.connect(lambda: self.email_input.setFocus())
        dlg.exec()

    def _on_login(self):
        email = self.email_input.text().strip()
        password = self.passwd_input.text()

        if not email or not password:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please enter both email and password.")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Checking...")

        ok = verify_login(email, password)

        self.login_btn.setEnabled(True)
        self.login_btn.setText("Login")

        if ok:
            self.login_successful.emit(email)
            self.hide()
        else:
            self.passwd_input.clear()
            QtWidgets.QMessageBox.warning(self, "Login Failed", "Invalid email or password.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    init_db()

    app = QtWidgets.QApplication(sys.argv)

    login = LoginWindow()

    def on_login(email: str):
        session = SessionWindow(email)
        session.logged_out.connect(on_logout)
        # Keep a reference so it isn't garbage-collected
        login._session = session
        session.show()

    def on_logout():
        login._session = None
        login.email_input.clear()
        login.passwd_input.clear()
        login.show()

    login.login_successful.connect(on_login)
    login.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
