# ruff: noqa: F403,F405
from tkinter import messagebox
from tkinter import *  # noqa: F401,F403,F405
from ..db_pg import get_db


# Function to check if the name exists in the database
def check_name():
    name_to_check = name_var.get()
    if not name_to_check.strip():
        messagebox.showwarning("Input Error", "Please enter a Email.")
        return

    conn = get_db()
    cursor = conn.cursor()

    # Query to check if the name exists
    cursor.execute("SELECT * FROM people WHERE email = %s", (name_to_check,))
    result = cursor.fetchone()

    if result:
        messagebox.showinfo("Result", f"Email '{name_to_check}' exists in the database!")
        messagebox.showinfo(
            "User Details", f"id: {result[0]}\nFirst Name: {result[1]}\nLast Name {result[2]}\nEmail: {result[7]}")
    else:
        messagebox.showinfo("Result", f"Email '{name_to_check}' does not exist in the database.")

    # Close the connection
    conn.close()


# Tkinter GUI setup
root = Tk()
root.title("Check Name in PostgreSQL")

Label(root, text="Enter Email:").grid(row=0, column=0, padx=10, pady=10)

name_var = StringVar()
Entry(root, textvariable=name_var).grid(row=0, column=1, padx=10, pady=10)

Button(root, text="Check Email", command=check_name).grid(row=1, column=0, columnspan=2, pady=10)
Button(root, text="Exit", command=root.quit).grid(row=3, column=0, columnspan=2, pady=10)

root.mainloop()
