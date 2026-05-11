import tkinter as tk
from tkinter import messagebox, PhotoImage
from tkinter import *
import sqlite3
import subprocess


# Database setup 
def setup_database():
    conn = sqlite3.connect('company.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            ID interger NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            email TEXT NOT NULL
        )
    ''')

    # Create Password table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS passwd (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        password TEXT NOT NULL,
        people_id INTEGER,
        FOREIGN KEY (people_id) REFERENCES people (id)
        )
    ''')

    # Create department table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS department (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept TEXT NOT NULL,
        people_id INTEGER,
        FOREIGN KEY (people_id) REFERENCES people (id)
        )
    ''')

# Function to validate credentials
global email_entry, password_entry
def validate_credentials():
    email = email_entry.get()
    password = password_entry.get()

    conn = sqlite3.connect('company.db')
    cursor = conn.cursor()
    # cursor.execute("SELECT * FROM people WHERE email = ?", (email))
    cursor.execute("SELECT passwd.password AS passwd_password, people.email AS people_email FROM passwd JOIN people ON passwd.people_id = people.id WHERE passwd_password = ? and people_email = ?", (password, email,))
    result = cursor.fetchone()
    # conn.close()

    if result:
        user_id = result[1]
        query = "SELECT id from people WHERE email = ?"
        cursor.execute(query, (user_id,))
        user_id2 = cursor.fetchone()
        print(user_id2)
        # Fetch department
        cursor.execute("SELECT department.dept AS department_dept, people.id AS people_id FROM department JOIN people ON department.people_id = people.id WHERE people_id = ?", (user_id2))
        department = cursor.fetchone()
        if department:
            dept = department[0]
            dept = dept + "_Main_menu.py"
            subprocess.run(["python", "splash.py"])     
            subprocess.run(["python", dept])
    else:
        messagebox.showerror("Error", "Invalid username or Password.")
        if messagebox.askyesno("Register", "Do you want to register as a new user?"):
           subprocess.Popen(["python", "TK_Registration_form.py"])
        else:
           messagebox.showinfo("Info", "please try again later.")
           email_entry.delete(0, tk.END)
           password_entry.delete(0, tk.END)
    conn.close()


# GUI setup
def create_gui():
    global email_entry, password_entry

    root = tk.Tk()
    root.title("Login System")
    app_width = 450
    app_height = 400
    

    # root.configure(bg="lightblue")
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width / 2) - (app_width / 2)
    y = (screen_height / 2 ) - (app_height / 2)

    root.geometry(f'{app_width}x{app_height}+{int(x)}+{int(y)}')
    my_label = tk.Label(root, text=f'Width:{screen_width}  Height:{screen_height}')
    

    background_image = PhotoImage(file="manufacturing2.png")

    # Create a Label with the image
    background_label = tk.Label(root, image=background_image)
    background_label.place(relwidth=1, relheight=1)

    tk.Label(root, text="Email:").place(x=100, y=75)
    email_entry = tk.Entry(root)
    email_entry.place(x=180, y=75)

    tk.Label(root, text="Password:").place(x=100, y=115)
    password_entry = tk.Entry(root, show="*")
    password_entry.place(x=180, y=115)

    login_button = tk.Button(root, text="Login", command=validate_credentials, borderwidth=5)
    login_button.place(x=180, y=155)
    
    Button(root, text="Exit", command=root.quit, borderwidth=5).place(x=180, y=210)

    root.mainloop()



# Main execution
if __name__ == "__main__":
    # setup_database()
    create_gui()
