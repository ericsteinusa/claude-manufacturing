# ruff: noqa: F403,F405
import tkinter as tk
from tkinter import messagebox, PhotoImage
from tkinter import *  # noqa: F401,F403,F405
from .db_pg import get_db
import subprocess

root = None
email_entry = None
password_entry = None


def validate_credentials():
    email = email_entry.get()
    password = password_entry.get()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT passwd.password FROM passwd "
        "JOIN people ON passwd.people_id = people.id "
        "WHERE people.email = %s AND passwd.password = %s",
        (email, password),
    )
    result = cursor.fetchone()
    conn.close()

    if result:
        root.destroy()
        subprocess.Popen(["python", "Company_main_menu.py"])
    else:
        messagebox.showerror("Error", "Invalid username or Password.")
        if messagebox.askyesno("Register", "Do you want to register as a new user%s"):
            subprocess.Popen(["python", "TK_Registration_form.py"])
        else:
            messagebox.showinfo("Info", "Please try again later.")
            email_entry.delete(0, tk.END)
            password_entry.delete(0, tk.END)


# GUI setup
def create_gui():
    global root, email_entry, password_entry

    root = tk.Tk()
    root.title("Login System")
    app_width = 450
    app_height = 400

    # root.configure(bg="lightblue")
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width / 2) - (app_width / 2)
    y = (screen_height / 2) - (app_height / 2)

    root.geometry(f'{app_width}x{app_height}+{int(x)}+{int(y)}')

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
