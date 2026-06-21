# ruff: noqa: F403,F405
from tkinter import *  # noqa: F401,F403,F405
from tkinter import ttk
from tkinter import messagebox
import psycopg2  # noqa: F401
from .db_pg import get_db
from tkinter import colorchooser
from configparser import ConfigParser

root = Tk()
root.title('Taxes')
app_width = 650
app_height = 600

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

x = (screen_width / 2) - (app_width / 2)
y = (screen_height / 2) - (app_height / 2)
root.geometry(f'{app_width}x{app_height}+{int(x)}+{int(y)}')

my_label = Label(root, text=f'Width:{screen_width} Height{screen_height}')

# Read our config file and get colors
parser = ConfigParser()
parser.read("personnel.ini")
saved_primary_color = parser.get('colors', 'primary_color')
saved_secondary_color = parser.get('colors', 'secondary_color')
saved_highlight_color = parser.get('colors', 'highlight_color')


def query_database():
    # Clear the Treeview
    for record in my_tree.get_children():
        my_tree.delete(record)

    # Create a database or connect to one that exists
    conn = get_db()

    # Create a cursor instance
    c = conn.cursor()

    c.execute("SELECT id, * FROM tax")
    records = c.fetchall()

    # Add our data to the screen
    global count
    count = 0

    for record in records:
        if count % 2 == 0:
            my_tree.insert(parent='', index='end', iid=count, text='', values=(
                record[2], record[3], record[0]), tags=('evenrow',))
        else:
            my_tree.insert(parent='', index='end', iid=count, text='', values=(
                record[2], record[3], record[0]), tags=('oddrow',))
        count += 1

    conn.commit()
    conn.close()


def search_records():
    lookup_record = search_entry.get()
    search.destroy()

    # Clear the Treeview
    for record in my_tree.get_children():
        my_tree.delete(record)

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT id, * FROM tax WHERE state like %s", (lookup_record,))
    records = c.fetchall()

    global count
    count = 0

    for record in records:
        if count % 2 == 0:
            my_tree.insert(parent='', index='end', iid=count, text='', values=(
                record[2], record[3], record[0]), tags=('evenrow',))
        else:
            my_tree.insert(parent='', index='end', iid=count, text='', values=(
                record[2], record[3], record[0]), tags=('oddrow',))
        count += 1

    conn.commit()
    conn.close()


def lookup_records():
    global search_entry, search

    search = Toplevel(root)
    search.title("Lookup Records")
    search.geometry("400x200")

    search_frame = LabelFrame(search, text="State")
    search_frame.pack(padx=10, pady=10)

    search_entry = Entry(search_frame, font=("Helvetica", 18))
    search_entry.pack(pady=20, padx=20)

    search_button = Button(search, text="Search Records", command=search_records)
    search_button.pack(padx=20, pady=20)


def primary_color():
    primary_color = colorchooser.askcolor()[1]

    if primary_color:
        my_tree.tag_configure('evenrow', background=primary_color)

        parser = ConfigParser()
        parser.read("personnel.ini")
        parser.set('colors', 'primary_color', primary_color)
        with open('personnel.ini', 'w') as configfile:
            parser.write(configfile)


def secondary_color():
    secondary_color = colorchooser.askcolor()[1]

    if secondary_color:
        my_tree.tag_configure('oddrow', background=secondary_color)

        parser = ConfigParser()
        parser.read("personnel.ini")
        parser.set('colors', 'secondary_color', secondary_color)
        with open('personnel.ini', 'w') as configfile:
            parser.write(configfile)


def highlight_color():
    highlight_color = colorchooser.askcolor()[1]

    if highlight_color:
        style.map('Treeview',
                  background=[('selected', highlight_color)])

        parser = ConfigParser()
        parser.read("personnel.ini")
        parser.set('colors', 'highlight_color', highlight_color)
        with open('personnel.ini', 'w') as configfile:
            parser.write(configfile)


def reset_colors():
    parser = ConfigParser()
    parser.read('personnel.ini')
    parser.set('colors', 'primary_color', 'lightblue')
    parser.set('colors', 'secondary_color', 'white')
    parser.set('colors', 'highlight_color', '#347083')
    with open('personnel.ini', 'w') as configfile:
        parser.write(configfile)
    my_tree.tag_configure('oddrow', background='white')
    my_tree.tag_configure('evenrow', background='lightblue')
    style.map('Treeview',
              background=[('selected', '#347083')])


# Add Menu
my_menu = Menu(root)
root.config(menu=my_menu)

option_menu = Menu(my_menu, tearoff=0)
my_menu.add_cascade(label="Options", menu=option_menu)
option_menu.add_command(label="Primary Color", command=primary_color)
option_menu.add_command(label="Secondary Color", command=secondary_color)
option_menu.add_command(label="Highlight Color", command=highlight_color)
option_menu.add_separator()
option_menu.add_command(label="Reset Colors", command=reset_colors)
option_menu.add_separator()
option_menu.add_command(label="Exit", command=root.quit)

search_menu = Menu(my_menu, tearoff=0)
my_menu.add_cascade(label="Search", menu=search_menu)
search_menu.add_command(label="Search", command=lookup_records)
search_menu.add_separator()
search_menu.add_command(label="Reset", command=query_database)

conn = get_db()
c = conn.cursor()

c.execute("""CREATE TABLE if not exists tax (
    state text,
    percent integer,
    id integer)
    """)
conn.commit()
conn.close()

app_width = 780
app_height = 600

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

x = (screen_width / 2) - (app_width / 2)
y = (screen_height / 2) - (app_height / 2)
root.geometry(f'{app_width}x{app_height}+{int(x)}+{int(y)}')

my_label = Label(root, text=f'Width:{screen_width} Height{screen_height}')

style = ttk.Style()
style.theme_use('default')

style.configure("Treeview",
                background="#D3D3D3",
                foreground="black",
                rowheight=25,
                fieldbackground="#D3D3D3")

style.map('Treeview',
          background=[('selected', saved_highlight_color)])

tree_frame = Frame(root)
tree_frame.pack(pady=10)

tree_scroll = Scrollbar(tree_frame)
tree_scroll.pack(side=RIGHT, fill=Y)

my_tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, selectmode="extended")
my_tree.pack()

tree_scroll.config(command=my_tree.yview)

my_tree['columns'] = ("State", "Percent", "ID")

my_tree.column("#0", width=0, stretch=NO)
my_tree.column("State", anchor=W, width=140)
my_tree.column("Percent", anchor=W, width=140)
my_tree.column("ID", anchor=CENTER, width=100)

my_tree.heading("#0", text="", anchor=W)
my_tree.heading("State", text="State", anchor=W)
my_tree.heading("Percent", text="Percent", anchor=W)
my_tree.heading("ID", text="ID", anchor=CENTER)

my_tree.tag_configure('oddrow', background=saved_secondary_color)
my_tree.tag_configure('evenrow', background=saved_primary_color)

data_frame = LabelFrame(root, text="Record")
data_frame.pack(fill="x", expand=True, padx=20)

st_label = Label(data_frame, text="State")
st_label.grid(row=0, column=0, padx=10, pady=10)
st_entry = Entry(data_frame)
st_entry.grid(row=0, column=1, padx=10, pady=10)

pcnt_label = Label(data_frame, text="Percent")
pcnt_label.grid(row=0, column=2, padx=10, pady=10)
pcnt_entry = Entry(data_frame)
pcnt_entry.grid(row=0, column=3, padx=10, pady=10)

id_label = Label(data_frame, text="ID")
id_label.grid(row=0, column=4, padx=10, pady=10)
id_entry = Entry(data_frame)
id_entry.grid(row=0, column=5, padx=10, pady=10)


def up():
    rows = my_tree.selection()
    for row in rows:
        my_tree.move(row, my_tree.parent(row), my_tree.index(row) - 1)


def down():
    rows = my_tree.selection()
    for row in reversed(rows):
        my_tree.move(row, my_tree.parent(row), my_tree.index(row) + 1)


def remove_one():
    x = my_tree.selection()[0]
    my_tree.delete(x)

    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM tax WHERE id = %s", (id_entry.get(),))
    conn.commit()
    conn.close()

    clear_entries()
    messagebox.showinfo("Deleted!", "Your Record Has Been Deleted!")


def remove_many():
    response = messagebox.askyesno("WOAH!!!!", "This Will Delete EVERYTHING SELECTED From The Table\nAre You Sure?!")

    if response == 1:
        x = my_tree.selection()
        ids_to_delete = []

        for record in x:
            ids_to_delete.append(my_tree.item(record, 'values')[2])

        conn = get_db()
        c = conn.cursor()

        c.executemany("DELETE FROM tax WHERE id = %s", [(a,) for a in ids_to_delete])

        conn.commit()
        conn.close()

        clear_entries()


def remove_all():
    response = messagebox.askyesno("WOAH!!!!", "This Will Delete EVERYTHING From The Table\nAre You Sure?!")

    if response == 1:
        for record in my_tree.get_children():
            my_tree.delete(record)

        conn = get_db()
        c = conn.cursor()

        c.execute("DROP TABLE tax")
        conn.commit()
        conn.close()

        clear_entries()
        create_table_again()


def clear_entries():
    st_entry.delete(0, END)
    pcnt_entry.delete(0, END)
    id_entry.delete(0, END)


def select_record(e):
    st_entry.delete(0, END)
    pcnt_entry.delete(0, END)
    id_entry.delete(0, END)

    selected = my_tree.focus()
    values = my_tree.item(selected, 'values')

    st_entry.insert(0, values[0])
    pcnt_entry.insert(0, values[1])
    id_entry.insert(0, values[2])


def update_record():
    selected = my_tree.focus()
    my_tree.item(selected, text="", values=(st_entry.get(), pcnt_entry.get(), id_entry.get()))

    conn = get_db()
    c = conn.cursor()

    c.execute("""UPDATE tax SET
        state = :state,
        percent = :percent
        WHERE id = %(oid)s""",
              {
                  'state': st_entry.get(),
                  'percent': int(pcnt_entry.get()) if pcnt_entry.get().strip().lstrip('-').isdigit() else 0,
                  'oid': id_entry.get(),
              })

    conn.commit()
    conn.close()

    st_entry.delete(0, END)
    pcnt_entry.delete(0, END)
    id_entry.delete(0, END)


def add_record():
    conn = get_db()
    c = conn.cursor()

    c.execute("INSERT INTO tax (state, percent) VALUES (%s, %s)", (
        st_entry.get(),
        int(pcnt_entry.get()) if pcnt_entry.get().strip().lstrip('-').isdigit() else 0
    ))

    conn.commit()
    conn.close()

    st_entry.delete(0, END)
    pcnt_entry.delete(0, END)
    id_entry.delete(0, END)

    my_tree.delete(*my_tree.get_children())
    query_database()


def create_table_again():
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE if not exists tax (
        state text,
        percent integer,
        id integer)
        """)

    conn.commit()
    conn.close()


# Add Buttons
button_frame = LabelFrame(root, text="Commands")
button_frame.pack(fill="x", expand=True, padx=20)

update_button = Button(button_frame, text="Update Record", command=update_record)
update_button.grid(row=0, column=0, padx=10, pady=10)

add_button = Button(button_frame, text="Add Record", command=add_record)
add_button.grid(row=0, column=1, padx=10, pady=10)

remove_all_button = Button(button_frame, text="Remove All Records", command=remove_all)
remove_all_button.grid(row=0, column=2, padx=10, pady=10)

remove_one_button = Button(button_frame, text="Remove One Selected", command=remove_one)
remove_one_button.grid(row=0, column=3, padx=10, pady=10)

remove_many_button = Button(button_frame, text="Remove Many Selected", command=remove_many)
remove_many_button.grid(row=1, column=0, padx=10, pady=10)

move_up_button = Button(button_frame, text="Move Up", command=up)
move_up_button.grid(row=1, column=1, padx=10, pady=10)

move_down_button = Button(button_frame, text="Move Down", command=down)
move_down_button.grid(row=1, column=2, padx=10, pady=10)

select_record_button = Button(button_frame, text="Clear Entry Boxes", command=clear_entries)
select_record_button.grid(row=1, column=3, padx=10, pady=10)

# Bind the treeview
my_tree.bind("<ButtonRelease-1>", select_record)

# Run to pull data from database on start
query_database()

root.mainloop()
