from .db_pg import get_db
from tkinter import *  # noqa: F401,F403,F405
from tkinter import Label, Entry, Button, Listbox, END
from tkinter import messagebox
import tkinter as tk


# Database setup
def setup_database():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplier (
            id SERIAL PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            company_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# Insert data into the database


def insert_data():
    first_name = first_name_entry.get()
    last_name = last_name_entry.get()
    company_name = company_name_entry.get()
    phone_number = phone_number_entry.get()
    address = address_entry.get()
    city = city_entry.get()
    state = state_entry.get()
    zip_code = zip_code_entry.get()
    email = email_entry.get()

    if not first_name or not last_name or not company_name or not phone_number or not address or not city or not state or not zip_code or not email:

        messagebox.showerror("Input Error", "Please fill in all fields.")

    #    return

    else:

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO supplier (first_name, last_name, company_name, phone_number, address, city, state, zip_code, email) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                       (first_name, last_name, company_name, phone_number, address, city, state, zip_code, email))
        conn.commit()
        messagebox.showinfo("Message", "Person Saved Successfully.")
        conn.close()
        first_name_entry.delete(0, END)
        last_name_entry.delete(0, END)
        company_name_entry.delete(0, END)
        phone_number_entry.delete(0, END)
        address_entry.delete(0, END)
        city_entry.delete(0, END)
        state_entry.delete(0, END)
        zip_code_entry.delete(0, END)
        email_entry.delete(0, END)
        display_data()

# Display data from the database


def display_data():
    user_list.delete(0, END)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, first_name, last_name, company_name, phone_number, address, city, state, zip_code, email FROM supplier")
    for row in cursor.fetchall():
        user_list.insert(
            END, f"ID: {row[0]}, first_name: {row[1]}, last_name: {row[2]}, company_name: {row[3]}, phone_number: {row[4]}, address: {row[5]}, city: {row[6]}, state: {row[7]}, zip_code: {row[8]}, email: {row[9]}")
    conn.close()


# GUI setup
root = tk.Tk()

# Create the banner (Label widget)
banner = tk.Label(root, text="Supplier Entry Form", bg="white",
                  fg="Black", font=("Arial", 16, "bold"))
banner.place(x=510, y=10)  # Place the banner at the top and stretch it horizontally

root.configure(bg="blue")
# Designate Height and Width of our app
app_width = 1210
app_height = 500

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

x = (screen_width / 2) - (app_width / 2)
y = (screen_height / 2) - (app_height / 2)
root.geometry(f'{app_width}x{app_height}+{int(x)}+{int(y)}')

root.title("Supplier Records")

Label(root, text="First Name:").place(x=130, y=60)
first_name_entry = Entry(root)
first_name_entry.place(x=210, y=60)

Label(root, text="Last Name:").place(x=370, y=60)
last_name_entry = Entry(root)
last_name_entry.place(x=450, y=60)

Label(root, text="Company:").place(x=610, y=60)
company_name_entry = Entry(root)
company_name_entry.place(x=690, y=60)

Label(root, text="Phone Number:").place(x=850, y=60)
phone_number_entry = Entry(root)
phone_number_entry.place(x=950, y=60)

Label(root, text="Address:").place(x=130, y=100)
address_entry = Entry(root)
address_entry.place(x=210, y=100)

Label(root, text="City:").place(x=370, y=100)
city_entry = Entry(root)
city_entry.place(x=450, y=100)

Label(root, text="State:").place(x=610, y=100)
state_entry = Entry(root)
state_entry.place(x=690, y=100)

Label(root, text="Zip Code:").place(x=850, y=100)
zip_code_entry = Entry(root)
zip_code_entry.place(x=950, y=100)

Label(root, text="Email:").place(x=130, y=140)
email_entry = Entry(root)
email_entry.place(x=210, y=140)


# Buttons for adding Records
Button(root, text="Add Supplier", command=insert_data).place(x=600, y=180)
Button(root, text="Exit", command=root.quit).place(x=630, y=220)

user_list = Listbox(root, width=180, height=10)
user_list.place(x=60, y=270)


# Initialize database and display data
setup_database()

display_data()

root.mainloop()
