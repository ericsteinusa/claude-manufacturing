import sqlite3
from tkinter import *
from tkinter import Label, Entry, Button, END
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk
from tkinter import colorchooser
from configparser import ConfigParser
from datetime import datetime


def _to_iso_date(val):
    """Normalize M/D/YYYY or MM/DD/YYYY input to ISO YYYY-MM-DD; pass through if already ISO or empty."""
    if not val or val.strip() == '':
        return val
    val = val.strip()
    if len(val) == 10 and val[4] == '-':
        return val
    for fmt in ('%m/%d/%Y', '%m/%d/%y'):
        try:
            return datetime.strptime(val, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return val

root = Tk()
people = ''

# Database setup


def setup_database():
    conn = sqlite3.connect('company.db')
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE if not exists people (
        first_name text,
        last_name text,
        id integer,
        address text,
        city text,
        state text,
        zip_code text,
        email text
        )
    """)

    cursor.execute("""
    CREATE TABLE if not exists calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        People_id INTEGER,
        call TEXT NOT NULL,
        call_date TEXT NOT NULL,
        call_time INTEGER NOT NULL,
        completion_date TEXT NOT NULL,
        completion_time INTEGER NOT NULL,
        comments_box TEXT NOT NULL,
        completion_box INTEGER NOT NULL,
        FOREIGN KEY (people_id) REFERENCES people(id)
        )
    """)
    conn.commit()
    conn.close()


'''
# Read our config file and get colors
parser = ConfigParser()
parser.read("personnel.ini")
saved_primary_color = parser.get('colors', 'primary_color')
saved_secondary_color = parser.get('colors', 'secondary_color')
saved_highlight_color = parser.get('colors', 'highlight_color')
'''


def query_database():
    # Clear the Treeview
    for record in my_tree.get_children():
        my_tree.delete(record)

    # Create a database or connect to one that exists
    conn = sqlite3.connect('company.db')

    # Create a cursor instance
    c = conn.cursor()

    c.execute("SELECT rowid, * FROM calls")
    records = c.fetchall()

    # Add our data to the screen
    global count
    count = 0

    for record in records:
        if count % 2 == 0:
            my_tree.insert(parent='', index='end', iid=count, text='', values=(
                record[1], record[2], record[3], record[4], record[5], record[6], record[7], record[8], record[9]), tags=('evenrow',))
        else:
            my_tree.insert(parent='', index='end', iid=count, text='', values=(
                record[1], record[2], record[3], record[4], record[5], record[6], record[7], record[8], record[9]), tags=('oddrow',))
        # increment counter
        count += 1

    # Commit changes
    conn.commit()

    # Close our connection
    conn.close()


def search_records():
    lookup_record = search_entry.get()
    # close the search box
    search.destroy()

    # Clear the Treeview
    for record in my_tree.get_children():
        my_tree.delete(record)

    # Create a database or connect to one that exists
    conn = sqlite3.connect('company.db')

    # Create a cursor instance
    c = conn.cursor()

    c.execute("SELECT rowid, * FROM calls WHERE rowid like ?", (lookup_record,))
    records = c.fetchall()

    # Add our data to the screen
    global count
    count = 0

    for record in records:
        if count % 2 == 0:
            my_tree.insert(parent='', index='end', iid=count, text='', values=(
                record[1], record[2], record[3], record[4], record[5], record[6], record[7], record[8], record[9]), tags=('evenrow',))
        else:
            my_tree.insert(parent='', index='end', iid=count, text='', values=(
                record[1], record[2], record[3], record[4], record[5], record[6], record[7], record[8], record[9]), tags=('oddrow',))
        # increment counter
        count += 1

    # Commit changes
    conn.commit()

    # Close our connection
    conn.close()


def lookup_records():
    global search_entry, search

    search = Toplevel(root)
    search.title("Lookup Records")
    search.geometry("400x200")

    # Create label frame
    search_frame = LabelFrame(search, text="Record Number")
    search_frame.pack(padx=10, pady=10)

    # Add entry box
    search_entry = Entry(search_frame, font=("Helvetica", 18))
    search_entry.pack(pady=20, padx=20)

    # Add button
    search_button = Button(search, text="Search Records", command=search_records)
    search_button.pack(padx=20, pady=20)


def primary_color():
    # Pick Color
    primary_color = colorchooser.askcolor()[1]

    # Update Treeview Color
    if primary_color:
        # Create Striped Row Tags
        my_tree.tag_configure('evenrow', background=primary_color)

        # Config file
        parser = ConfigParser()
        parser.read("personnel.ini")
        # Set the color change
        parser.set('colors', 'primary_color', primary_color)
        # Save the config file
        with open('personnel.ini', 'w') as configfile:
            parser.write(configfile)


def secondary_color():
    # Pick Color
    secondary_color = colorchooser.askcolor()[1]

    # Update Treeview Color
    if secondary_color:
        # Create Striped Row Tags
        my_tree.tag_configure('oddrow', background=secondary_color)

        # Config file
        parser = ConfigParser()
        parser.read("personnel.ini")
        # Set the color change
        parser.set('colors', 'secondary_color', secondary_color)
        # Save the config file
        with open('personnel.ini', 'w') as configfile:
            parser.write(configfile)


def highlight_color():
    # Pick Color
    highlight_color = colorchooser.askcolor()[1]

    # Update Treeview Color
    # Change Selected Color
    if highlight_color:
        style.map('Treeview',
                  background=[('selected', highlight_color)])

        # Config file
        parser = ConfigParser()
        parser.read("personnel.ini")
        # Set the color change
        parser.set('colors', 'highlight_color', highlight_color)
        # Save the config file
        with open('personnel.ini', 'w') as configfile:
            parser.write(configfile)


def reset_colors():
    # Save original colors to config file
    parser = ConfigParser()
    parser.read('personnel.ini')
    parser.set('colors', 'primary_color', 'lightblue')
    parser.set('colors', 'secondary_color', 'white')
    parser.set('colors', 'highlight_color', '#347083')
    with open('personnel.ini', 'w') as configfile:
        parser.write(configfile)
    # Reset the colors
    my_tree.tag_configure('oddrow', background='white')
    my_tree.tag_configure('evenrow', background='lightblue')
    style.map('Treeview',
              background=[('selected', '#347083')])


# Add Menu
my_menu = Menu(root)
root.config(menu=my_menu)

# Configure our menu
option_menu = Menu(my_menu, tearoff=0)
my_menu.add_cascade(label="Options", menu=option_menu)
# Drop down menu
option_menu.add_command(label="Primary Color", command=primary_color)
option_menu.add_command(label="Secondary Color", command=secondary_color)
option_menu.add_command(label="Highlight Color", command=highlight_color)
option_menu.add_separator()
option_menu.add_command(label="Reset Colors", command=reset_colors)
option_menu.add_separator()
option_menu.add_command(label="Exit", command=root.quit)

# Search Menu
search_menu = Menu(my_menu, tearoff=0)
my_menu.add_cascade(label="Search", menu=search_menu)
# Drop down menu
search_menu.add_command(label="Search", command=lookup_records)
search_menu.add_separator()
search_menu.add_command(label="Reset", command=query_database)


# Step 2: Fetch data for the selection list
def fetch_people():
    conn = sqlite3.connect("company.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id || ' ' || first_name || ' ' || last_name as full_name FROM people")
    people = [row[0] for row in cursor.fetchall()]
    conn.close()
    return people

# Insert data into the database


def insert_data():
    people_id = people_combobox.get().split(' ')[0].strip('{')
    call = call_widget.get("1.0", "end-1c")  # Get text from Text Widget
    call_date = _to_iso_date(call_date_entry.get())
    call_time = call_time_entry.get()
    completion_date = _to_iso_date(completion_date_entry.get())
    completion_time = completion_time_entry.get()
    comments_box = comment_widget.get("1.0", "end-1c")  # Get text from Text Widget
    completion_box = checkbox_var.get()  # Get value from checkbox (0 or 1)

    if not people_id or not call or not call_date or not call_time or not completion_date or not completion_time or not comments_box or not completion_box:

        messagebox.showerror("Input Error", "Please fill in all fields.")

    #    return

    else:

        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO calls (people_id, call, call_date, call_time, completion_date, completion_time, comments_box, completion_box) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (people_id, call, call_date, call_time, completion_date, completion_time, comments_box, completion_box))
        conn.commit()
        messagebox.showinfo("Message", "Call Saved Successfully.")
        conn.close()
        people_id.delete(0, END)
        call_widget.delete("1.0", END)
        call_date_entry.delete(0, END)
        call_time_entry.delete(0, END)
        completion_date_entry.delete(0, END)
        completion_time_entry.delete(0, END)
        comments_box.delete("1.0", END)
        completion_box.delete(0, END)
        # display_data()


# Display data from the database
'''
def display_data():
    user_list.delete(0, END)
    conn = sqlite3.connect("company.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, people_id, call, call_date, call_time, completion_date, completion_time, comments_box, completion_box FROM calls")
    for row in cursor.fetchall():
    user_list.insert(END, f"ID: {row[0]}, people_id: {row[1]}, call: {row[2]}, call_date: {row[3]}, call_time: {row[4]}, completion_date: {row[5]}, completion_time: {row[6]}, comments_box: {row[7]}, completion_box: {row[8]}")
  conn.close()
'''
root.configure(bg="lightblue")
# Designate Height and Width of our app
app_width = 1210
app_height = 650

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

x = (screen_width / 2) - (app_width / 2)
y = (screen_height / 2) - (app_height / 2)
root.geometry(f'{app_width}x{app_height}+{int(x)}+{int(y)}')

# Read our config file and get colors
parser = ConfigParser()
parser.read("personnel.ini")
saved_primary_color = parser.get('colors', 'primary_color')
saved_secondary_color = parser.get('colors', 'secondary_color')
saved_highlight_color = parser.get('colors', 'highlight_color')

# Add Some Style
style = ttk.Style()

# Pick A Theme
style.theme_use('default')

# Configure the Treeview Colors
style.configure("Treeview",
                background="#D3D3D3",
                foreground="black",
                rowheight=25,
                fieldbackground="#D3D3D3")

# Change Selected Color #347083
style.map('Treeview',
          background=[('selected', saved_highlight_color)])


# Create a Treeview Frame
tree_frame = Frame(root)
tree_frame.pack(pady=10)

# Create a Treeview Scrollbar
tree_scroll = Scrollbar(tree_frame)
tree_scroll.pack(side=RIGHT, fill=Y)

# Create The Treeview
my_tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, selectmode="extended")
my_tree.pack()

# Configure the Scrollbar
tree_scroll.config(command=my_tree.yview)

# Define Our Columns
my_tree['columns'] = ("ID", "People ID", "Problem", "Call Date", "Call Time",
                      "Completion Date", "Completion Time", "Comments", "Completion Box")

# Format Our Columns
my_tree.column("#0", width=0, stretch=NO)
my_tree.column("ID", anchor=CENTER, width=100)
my_tree.column("People ID", anchor=W, width=140)
my_tree.column("Problem", anchor=W, width=140)
my_tree.column("Call Date", anchor=W, width=140)
my_tree.column("Call Time", anchor=W, width=140)
my_tree.column("Completion Date", anchor=W, width=140)
my_tree.column("Completion Time", anchor=W, width=140)
my_tree.column("Comments", anchor=W, width=140)
my_tree.column("Completion Box", anchor=CENTER, width=100)

# Create Headings
my_tree.heading("#0", text="", anchor=W)
my_tree.heading("ID", text="ID", anchor=CENTER)
my_tree.heading("People ID", text="People ID", anchor=W)
my_tree.heading("Problem", text="Problem", anchor=W)
my_tree.heading("Call Date", text="Call Date", anchor=W)
my_tree.heading("Call Time", text="Call Time", anchor=W)
my_tree.heading("Completion Date", text="Completion Date", anchor=W)
my_tree.heading("Completion Time", text="Completion Time", anchor=W)
my_tree.heading("Comments", text="Comments", anchor=W)
my_tree.heading("Completion Box", text="Completion Box", anchor=CENTER)

# Create Striped Row Tags
my_tree.tag_configure('oddrow', background=saved_secondary_color)
my_tree.tag_configure('evenrow', background=saved_primary_color)

root.title("Call Records")

# Add Record Entry Boxes
data_frame = LabelFrame(root, text="Record")
data_frame.place(x=5, y=300, width=1200, height=250)
id_label = Label(data_frame, text="ID")
id_label.grid(row=0, column=0, padx=10, pady=10)
id_entry = Entry(data_frame)
id_entry.grid(row=0, column=1, padx=10, pady=10)

# Parent selection Combobox
people_data = fetch_people()
people_id_label = Label(data_frame, text="People ID:")
people_id_label.grid(row=0, column=2, padx=10, pady=10)
people_combobox = ttk.Combobox(root, values=people_data)
people_combobox.place(x=265, y=327)
people_combobox.bind("<<ComboboxSelected>>")


Label(root, text="Call:").place(x=425, y=327)
call_widget = Text(root, wrap="word", width=30, height=5)
call_widget.place(x=460, y=327)
call = call_widget.get("1.0", "end-1c")  # Get text from Text widget

Label(root, text="Call Date:").place(x=715, y=327)
call_date_entry = Entry(root)
call_date_entry.place(x=775, y=327)

Label(root, text="Call Time:").place(x=910, y=327)
call_time_entry = Entry(root)
call_time_entry.place(x=975, y=327)

Label(root, text="Completion Date:").place(x=25, y=440)
completion_date_entry = Entry(root)
completion_date_entry.place(x=130, y=440)

Label(root, text="Completion Time:").place(x=270, y=440)
completion_time_entry = Entry(root)
completion_time_entry.place(x=378, y=440)

Label(root, text="Comments:").place(x=518, y=440)
comment_widget = Text(root, wrap="word", width=30, height=5)
comment_widget.place(x=590, y=440)

# Variable to store completion status
checkbox_var = IntVar()
# Create a checkbox
checkbox = tk.Checkbutton(root, text="Completed", variable=checkbox_var)
checkbox.place(x=850, y=440)

# Move Row Up


def up():
    rows = my_tree.selection()
    for row in rows:
        my_tree.move(row, my_tree.parent(row), my_tree.index(row) - 1)

# Move Rown Down


def down():
    rows = my_tree.selection()
    for row in reversed(rows):
        my_tree.move(row, my_tree.parent(row), my_tree.index(row) + 1)

# Remove one record


def remove_one():
    x = my_tree.selection()[0]
    my_tree.delete(x)

    # Create a database or connect to one that exists
    conn = sqlite3.connect('company.db')

    # Create a cursor instance
    c = conn.cursor()

    # Delete From Database
    c.execute("DELETE from calls WHERE oid=" + id_entry.get())

    # Commit changes
    conn.commit()

    # Close our connection
    conn.close()

    # Clear The Entry Boxes
    clear_entries()

    # Add a little message box for fun
    messagebox.showinfo("Deleted!", "Your Record Has Been Deleted!")


# Remove Many records
def remove_many():
    # Add a little message box for fun
    response = messagebox.askyesno("WOAH!!!!", "This Will Delete EVERYTHING SELECTED From The Table\nAre You Sure?!")

    # Add logic for message box
    if response == 1:
        # Designate selections
        x = my_tree.selection()

        # Create List of ID's
        ids_to_delete = []

        # Add selections to ids_to_delete list
        for record in x:
            ids_to_delete.append(my_tree.item(record, 'values')[2])

        # Delete From Treeview
        for record in x:
            my_tree.delete(record)

        # Create a database or connect to one that exists
        conn = sqlite3.connect('company.db')

        # Create a cursor instance
        c = conn.cursor()

        # Delete Everything From The Table
        c.executemany("DELETE FROM calls WHERE id = ?", [(a,) for a in ids_to_delete])

        # Reset List
        ids_to_delete = []

        # Commit changes
        conn.commit()

        # Close our connection
        conn.close()

        # Clear entry boxes if filled
        clear_entries()


# Remove all records
def remove_all():
    # Add a little message box for fun
    response = messagebox.askyesno("WOAH!!!!", "This Will Delete EVERYTHING From The Table\nAre You Sure?!")

    # Add logic for message box
    if response == 1:
        # Clear the Treeview
        for record in my_tree.get_children():
            my_tree.delete(record)

        # Create a database or connect to one that exists
        conn = sqlite3.connect('company.db')

        # Create a cursor instance
        c = conn.cursor()

        # Delete Everything From The Table
        c.execute("DROP TABLE calls")

        # Commit changes
        conn.commit()

        # Close our connection
        conn.close()

        # Clear entry boxes if filled
        clear_entries()

        # Recreate The Table
        create_table_again()

# Clear entry boxes


def clear_entries():
    # Clear entry boxes
    id_entry.delete(0, END)
    people_combobox.delete(0, END)
    call_widget.delete("1.0", END)
    call_date_entry.delete(0, END)
    call_time_entry.delete(0, END)
    completion_date_entry.delete(0, END)
    completion_time_entry.delete(0, END)
    comment_widget.delete("1.0", END)
    checkbox_var.set(0)


# Select Record
def select_record(e):
    # Clear entry boxes
    id_entry.delete(0, END)
    people_combobox.delete(0, END)
    call_widget.delete("1.0", END)
    call_date_entry.delete(0, END)
    call_time_entry.delete(0, END)
    completion_date_entry.delete(0, END)
    completion_time_entry.delete(0, END)
    comment_widget.delete("1.0", END)
    checkbox_var.set(0)

    # Grab record Number
    selected = my_tree.focus()
    # Grab record values
    values = my_tree.item(selected, 'values')

    # output to entry boxes
    id_entry.insert(0, values[0])
    people_combobox.insert(0, values[1])
    call_widget.insert("1.0", values[2])
    call_date_entry.insert(0, values[3])
    call_time_entry.insert(0, values[4])
    completion_date_entry.insert(0, values[5])
    completion_time_entry.insert(0, values[6])
    comment_widget.insert("1.0", values[7])
    checkbox_var.set(values[8])


# Update record
def update_record():
    # Grab the record number
    selected = my_tree.focus()
    # Update record
    my_tree.item(selected, text="", values=(id_entry.get(), people_combobox.get().split(' ')[0].strip('{'), call_widget.get("1.0", "end-1c"), call_date_entry.get(
    ), call_time_entry.get(), completion_date_entry.get(), completion_time_entry.get(), comment_widget.get("1.0", "end-1c"), checkbox_var.get()))
    # Update the database
    # Create a database or connect to one that exists
    conn = sqlite3.connect('company.db')

    # Create a cursor instance
    c = conn.cursor()

    c.execute("""UPDATE calls SET
        people_id = :people,
        call = :call,
        call_date = :call_date,
        call_time = :call_time,
        completion_date = :completion_date,
        completion_time = :completion_time,
        comments_box = :comments_box,
        completion_box = :completion_box

        WHERE oid = :oid""",
              {
                  'people': people_combobox.get().split(' ')[0].strip('{'),
                  'call': call_widget.get("1.0", "end-1c"),
                  'call_date': _to_iso_date(call_date_entry.get()),
                  'call_time': call_time_entry.get(),
                  'completion_date': _to_iso_date(completion_date_entry.get()),
                  'completion_time': completion_time_entry.get(),
                  'comments_box': comment_widget.get("1.0", "end-1c"),
                  'completion_box': checkbox_var.get(),
                  'oid': id_entry.get(),
              })

    # Commit changes
    conn.commit()

    # Close our connection
    conn.close()

    # Clear entry boxes
    id_entry.delete(0, END)
    people_combobox.delete(0, END)
    call_widget.delete("1.0", END)
    call_date_entry.delete(0, END)
    call_time_entry.delete(0, END)
    completion_date_entry.delete(0, END)
    completion_time_entry.delete(0, END)
    comment_widget.delete("1.0", END)
    checkbox_var.set(0)


# add new record to database
def add_record():
    # Update the database
    # Create a database or connect to one that exists
    conn = sqlite3.connect('company.db')

    # Create a cursor instance
    c = conn.cursor()

    # Add New Record
    c.execute("INSERT INTO calls (people_id, call, call_date, call_time, completion_date, completion_time, comments_box, completion_box) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (people_combobox.get().split(' ')[0].strip(
        '{'), call_widget.get("1.0", "end-1c"), _to_iso_date(call_date_entry.get()), call_time_entry.get(), _to_iso_date(completion_date_entry.get()), completion_time_entry.get(), comment_widget.get("1.0", "end-1c"), checkbox_var.get()))

    # Commit changes
    conn.commit()

    # Close our connection
    conn.close()

    # Clear entry boxes
    id_entry.delete(0, END)
    people_combobox.delete(0, END)
    call_widget.delete("1.0", END)
    call_date_entry.delete(0, END)
    call_time_entry.delete(0, END)
    completion_date_entry.delete(0, END)
    completion_time_entry.delete(0, END)
    comment_widget.delete("1.0", END)
    checkbox_var.set(0)

    # Clear The Treeview Table
    my_tree.delete(*my_tree.get_children())

    # Run to pull data from database on start
    query_database()


def create_table_again():
    # Create a database or connect to one that exists
    conn = sqlite3.connect('company.db')

    # Create a cursor instance
    c = conn.cursor()

    # Create Table
    c.execute("""CREATE TABLE if not exists calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        people_id integer,
        call text,
        call_date text,
        call_time text,
        completion_date,
        completion_time,
        comments_box text,
        completion_box integer,
        FOREIGN KEY (people_id) REFERENCES people(id))
        """)

    # Commit changes
    conn.commit()

    # Close our connection
    conn.close()


# Add Buttons
button_frame = LabelFrame(root, text="Commands")
button_frame.place(x=5, y=565, width=1200, height=75)

update_button = Button(button_frame, text="Update Record", command=update_record)
update_button.grid(row=0, column=0, padx=10, pady=10)

add_button = Button(button_frame, text="Add Record", command=add_record)
add_button.grid(row=0, column=1, padx=10, pady=10)

remove_all_button = Button(button_frame, text="Remove All Records", command=remove_all)
remove_all_button.grid(row=0, column=2, padx=10, pady=10)

remove_one_button = Button(button_frame, text="Remove One Selected", command=remove_one)
remove_one_button.grid(row=0, column=3, padx=10, pady=10)

remove_many_button = Button(button_frame, text="Remove Many Selected", command=remove_many)
remove_many_button.grid(row=0, column=4, padx=10, pady=10)

move_up_button = Button(button_frame, text="Move Up", command=up)
move_up_button.grid(row=0, column=5, padx=10, pady=10)

move_down_button = Button(button_frame, text="Move Down", command=down)
move_down_button.grid(row=0, column=6, padx=10, pady=10)

select_record_button = Button(button_frame, text="Clear Entry Boxes", command=clear_entries)
select_record_button.grid(row=0, column=7, padx=10, pady=10)

# Bind the treeview
my_tree.bind("<ButtonRelease-1>", select_record)

# Initialize database and display data
setup_database()
query_database()

root.mainloop()
