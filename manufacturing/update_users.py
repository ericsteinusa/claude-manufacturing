import tkinter as tk
from tkinter import messagebox
from tkinter import *
import psycopg2
from db_pg import get_db




# Database setup
def setup_database():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS people (
            id SERIAL PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                address TEXT NOT NULL,
                city TEXT NOT NULL,
                state TEXT NOT NULL,
                zip_code TEXT NOT NULL,
                email TEXT NOT NULL
            )
        ''')


global email_entry, password_entry


def check_name():
   
   
    conn = get_db()
    cursor = conn.cursor()
    email = email_entry.get()
    password = password_entry.get()

    if not email.strip():
        messagebox.showwarning("Input Error", "Please enter a name.")
    else:
        cursor.execute("SELECT passwd.id as passwd_id, passwd.people_id as people_id, people.email as people_email, passwd.password as passwd_password FROM passwd JOIN people ON passwd.people_id = people.id WHERE people_email = %s", (email,))
        result = cursor.fetchone()
        if result:
            id = result[0]
            email = email_entry.get()
            password = password_entry.get()
            messagebox.showinfo("Result", f"Email '{email}' exists in the database!")
            messagebox.showinfo(
                "User Details", f"id: {result[0]}\nPeople ID: {result[1]}\nEmail: {result[2]}\nPassword: {result[3]}")
            cursor.execute("UPDATE passwd SET password = %s WHERE id = %s", (password, id))
            messagebox.showinfo("Update Status", "Password updated successfully!")
        else:
            messagebox.showinfo("Result", f"Email '{email}' does not exist in the database.")
            email_entry.delete(0, tk.END)
            password_entry.delete(0, tk.END)
    # Update data into the database

    conn.commit()
    conn.close()


# GUI setup
def create_gui():
    global email_entry, password_entry
    root = Tk()
    root.title("Password Reset")
    root.configure(bg="blue")

    app_width = 500
    app_height = 500

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    x = (screen_width / 2) - (app_width / 2)
    y = (screen_height / 2) - (app_height / 2)
    root.geometry(f'{app_width}x{app_height}+{int(x)}+{int(y)}')

    # my_label = Label(root, text=f'Width:{screen_width} Height{screen_height}' )
    # background_image = PhotoImage(file="c:/source/pythonQSG/PyQt6 apps/images/personnel2.png")

# Create a Label with the image

    # background_label = tk.Label(root, image=background_image)
    # background_label.place(relwidth=1, relheight=1)
    # banner = tk.Label(root, text="Reset Password Form", bg = "white",
    # fg="Black", font=("Arial" , 16, "bold"))
    # banner.place(x=140, y=20) # Place the banner at the top and stretch it horizontally

    Label(root, text="Email:", font=("Arial", 10)).place(x=178, y=125),
    email_entry = Entry(root)
    email_entry.place(x=265, y=125)

    Label(root, text="Enter New Password:", font=("Arial", 10)).place(x=100, y=175)
    password_entry = Entry(root)
    password_entry.place(x=265, y=175)

    Button(root, text="Update Password", command=check_name, borderwidth=5).place(x=200, y=240)
    Button(root, text="Exit", command=root.quit, borderwidth=5).place(x=240, y=300)

    root.mainloop()


if __name__ == "__main__":
    setup_database()
    create_gui()
