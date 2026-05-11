from tkinter import *
from tkinter import ttk
from tkinter import messagebox
import sqlite3
from tkinter import colorchooser
from configparser import ConfigParser

root = Tk()
root.title('Personnel CRM')
root.geometry("1400x550")

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
 	    email text,
        dept_id INTEGER,
        dept_sub_id INTEGER,
        FOREIGN KEY(dept_id) REFERENCES dept(id),
        FOREIGN KEY(dept_sub_id) REFERENCES dept_sub(id)
        )
	""")

    cursor.execute("""
    CREATE TABLE if not exists dept (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept_id integer,
        dept_name text
        )
    """)
    
    cursor.execute("""
    CREATE TABLE if not exists dept_sub (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept_sub_id integer,
        dept_sub_name text
        )
    """)
    conn.commit()
    conn.close()
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
	conn = sqlite3.connect('company.db')

	# Create a cursor instance
	c = conn.cursor()

	c.execute("SELECT rowid, * FROM people")
	records = c.fetchall()
	
	# Add our data to the screen
	global count
	count = 0
	
	#for record in records:
	#	print(record)


	for record in records:
		if count % 2 == 0:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[2], record[3], record[0], record[4], record[5], record[6], record[7], record[8],  record[9],  record[10]), tags=('evenrow',))
		else:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[2], record[3], record[0], record[4], record[5], record[6], record[7], record[8],  record[9],  record[10]), tags=('oddrow',))
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

	c.execute("SELECT rowid, * FROM people WHERE last_name like ?", (lookup_record,))
	records = c.fetchall()
	
	# Add our data to the screen
	global count
	count = 0
	
	#for record in records:
	#	print(record)


	for record in records:
		if count % 2 == 0:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[2], record[3], record[0], record[4], record[5], record[6], record[7], record[8],  record[9],  record[10]), tags=('evenrow',))
		else:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[2], record[3], record[0], record[4], record[5], record[6], record[7], record[8],  record[9],  record[10]), tags=('oddrow',))
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
	search_frame = LabelFrame(search, text="Last Name")
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

	#Update Treeview Color
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

#Search Menu
search_menu = Menu(my_menu, tearoff=0)
my_menu.add_cascade(label="Search", menu=search_menu)
# Drop down menu
search_menu.add_command(label="Search", command=lookup_records)
search_menu.add_separator()
search_menu.add_command(label="Reset", command=query_database)

# Do some database stuff
# Create a database or connect to one that exists
conn = sqlite3.connect('company.db')

# Create a cursor instance
c = conn.cursor()

# Create Table
c.execute("""CREATE TABLE if not exists people (
	first_name text,
	last_name text,
	id integer,
	address text,
	city text,
	state text,
	zip_code text,
 	email text,
    dept_id INTEGER,
    dept_sub_id INTEGER,
    FOREIGN KEY(dept_id) REFERENCES dept(id),
    FOREIGN KEY(dept_sub_id) REFERENCES dept_sub(id))
	""")

# Commit changes
conn.commit()

# Close our connection
conn.close()



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
my_tree['columns'] = ("First Name", "Last Name", "ID", "Address", "City", "State", "Zipcode", "Email",  "Dept",  "Dept Sub")

# Format Our Columns
my_tree.column("#0", width=0, stretch=NO)
my_tree.column("First Name", anchor=W, width=140)
my_tree.column("Last Name", anchor=W, width=140)
my_tree.column("ID", anchor=CENTER, width=100)
my_tree.column("Address", anchor=CENTER, width=140)
my_tree.column("City", anchor=CENTER, width=140)
my_tree.column("State", anchor=CENTER, width=140)
my_tree.column("Zipcode", anchor=CENTER, width=140)
my_tree.column("Email", anchor=CENTER, width=140)
my_tree.column("Dept",  anchor=CENTER,  width=140)
my_tree.column("Dept Sub",  anchor=CENTER,  width=140)

# Create Headings
my_tree.heading("#0", text="", anchor=W)
my_tree.heading("First Name", text="First Name", anchor=W)
my_tree.heading("Last Name", text="Last Name", anchor=W)
my_tree.heading("ID", text="ID", anchor=CENTER)
my_tree.heading("Address", text="Address", anchor=CENTER)
my_tree.heading("City", text="City", anchor=CENTER)
my_tree.heading("State", text="State", anchor=CENTER)
my_tree.heading("Zipcode", text="Zip_code", anchor=CENTER)
my_tree.heading("Email", text="Email", anchor=CENTER)
my_tree.heading("Dept",  text="Dept",  anchor=CENTER)
my_tree.heading("Dept Sub",  text="Dept Sub",  anchor=CENTER)

# Create Striped Row Tags
my_tree.tag_configure('oddrow', background=saved_secondary_color)
my_tree.tag_configure('evenrow', background=saved_primary_color)



# Add Record Entry Boxes
data_frame = LabelFrame(root, text="Record")
data_frame.pack(fill="x", expand="yes", padx=20)

fn_label = Label(data_frame, text="First Name")
fn_label.grid(row=0, column=0, padx=10, pady=10)
fn_entry = Entry(data_frame)
fn_entry.grid(row=0, column=1, padx=10, pady=10)

ln_label = Label(data_frame, text="Last Name")
ln_label.grid(row=0, column=2, padx=10, pady=10)
ln_entry = Entry(data_frame)
ln_entry.grid(row=0, column=3, padx=10, pady=10)

id_label = Label(data_frame, text="ID")
id_label.grid(row=0, column=4, padx=10, pady=10)
id_entry = Entry(data_frame)
id_entry.grid(row=0, column=5, padx=10, pady=10)

address_label = Label(data_frame, text="Address")
address_label.grid(row=0, column=6, padx=10, pady=10)
address_entry = Entry(data_frame)
address_entry.grid(row=0, column=7, padx=10, pady=10)

city_label = Label(data_frame, text="City")
city_label.grid(row=0, column=8, padx=10, pady=10)
city_entry = Entry(data_frame)
city_entry.grid(row=0, column=9, padx=10, pady=10)

state_label = Label(data_frame, text="State")
state_label.grid(row=0, column=10, padx=10, pady=10)
state_entry = Entry(data_frame)
state_entry.grid(row=0, column=11, padx=10, pady=10)

zip_code_label = Label(data_frame, text="Zipcode")
zip_code_label.grid(row=1, column=0, padx=10, pady=10)
zip_code_entry = Entry(data_frame)
zip_code_entry.grid(row=1, column=1, padx=10, pady=10)

email_label = Label(data_frame, text="Email")
email_label.grid(row=1, column=2, padx=10, pady=10)
email_entry = Entry(data_frame)
email_entry.grid(row=1, column=3, padx=10, pady=10)

dept_label = Label(data_frame, text="Dept")
dept_label.grid(row=1, column=4, padx=10, pady=10)
dept_entry = Entry(data_frame)
dept_entry.grid(row=1, column=5, padx=10, pady=10)

ds_label = Label(data_frame, text="Dept Sub")
ds_label.grid(row=1, column=6, padx=10, pady=10)
ds_entry = Entry(data_frame)
ds_entry.grid(row=1, column=7, padx=10, pady=10)


# Move Row Up
def up():
	rows = my_tree.selection()
	for row in rows:
		my_tree.move(row, my_tree.parent(row), my_tree.index(row)-1)

# Move Rown Down
def down():
	rows = my_tree.selection()
	for row in reversed(rows):
		my_tree.move(row, my_tree.parent(row), my_tree.index(row)+1)

# Remove one record
def remove_one():
	x = my_tree.selection()[0]
	my_tree.delete(x)

	# Create a database or connect to one that exists
	conn = sqlite3.connect('company.db')

	# Create a cursor instance
	c = conn.cursor()

	# Delete From Database
	c.execute("DELETE from people WHERE oid=" + id_entry.get())
	


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

	#Add logic for message box
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
		c.executemany("DELETE FROM people WHERE id = ?", [(a,) for a in ids_to_delete])

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

	#Add logic for message box
	if response == 1:
		# Clear the Treeview
		for record in my_tree.get_children():
			my_tree.delete(record)

		# Create a database or connect to one that exists
		conn = sqlite3.connect('company.db')

		# Create a cursor instance
		c = conn.cursor()

		# Delete Everything From The Table
		c.execute("DROP TABLE people")
			


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
	fn_entry.delete(0, END)
	ln_entry.delete(0, END)
	id_entry.delete(0, END)
	address_entry.delete(0, END)
	city_entry.delete(0, END)
	state_entry.delete(0, END)
	zip_code_entry.delete(0, END)
	email_entry.delete(0, END)
	dept_entry.delete(0, END)
	ds_entry.delete(0, END)
	

# Select Record
def select_record(e):
	# Clear entry boxes
	fn_entry.delete(0, END)
	ln_entry.delete(0, END)
	id_entry.delete(0, END)
	address_entry.delete(0, END)
	city_entry.delete(0, END)
	state_entry.delete(0, END)
	zip_code_entry.delete(0, END)
	email_entry.delete(0, END)
	dept_entry.delete(0, END)
	ds_entry.delete(0, END)
	
	# Grab record Number
	selected = my_tree.focus()
	# Grab record values
	values = my_tree.item(selected, 'values')

	# output to entry boxes
	fn_entry.insert(0, values[0])
	ln_entry.insert(0, values[1])
	id_entry.insert(0, values[2])
	address_entry.insert(0, values[3])
	city_entry.insert(0, values[4])
	state_entry.insert(0, values[5])
	zip_code_entry.insert(0, values[6])
	email_entry.insert(0, values[7])
	dept_entry.insert(0, values[8])
	ds_entry.insert(0,  values[9])
	
# Update record
def update_record():
	# Grab the record number
	selected = my_tree.focus()
	# Update record
	my_tree.item(selected, text="", values=(fn_entry.get(), ln_entry.get(), id_entry.get(), address_entry.get(), city_entry.get(), state_entry.get(), zip_code_entry.get(), email_entry.get(), dept_entry.get(), ds_entry.get()))

	# Update the database
	# Create a database or connect to one that exists
	conn = sqlite3.connect('company.db')

	# Create a cursor instance
	c = conn.cursor()

	# c.execute("SELECT * FROM people WHERE id=?", (selected_id))

	c.execute("""UPDATE people SET
		first_name = :first,
		last_name = :last,
		address = :address,
		city = :city,
		state = :state,
		zip_code = :zip_code,
		email = :email,
        dept = :dept
        dept_sub = :dept_sub
	
		WHERE oid = :oid""",
		{
			'first': fn_entry.get(),
			'last': ln_entry.get(),
			'address': address_entry.get(),
			'city': city_entry.get(),
			'state': state_entry.get(),
			'zip_code': zip_code_entry.get(),
			'email': email_entry.get(),
            'dept': dept_entry.get(), 
            'dept_sub': ds_entry.get(), 
			'oid': id_entry.get(),			
		})
	


	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()


	# Clear entry boxes
	fn_entry.delete(0, END)
	ln_entry.delete(0, END)
	id_entry.delete(0, END)
	address_entry.delete(0, END)
	city_entry.delete(0, END)
	state_entry.delete(0, END)
	zip_code_entry.delete(0, END)
	email_entry.delete(0, END)
	dept_entry.delete(0,  END)
	ds_entry.delete(0, END)
	
# add new record to database
def add_record():
	# Update the database
	# Create a database or connect to one that exists
	conn = sqlite3.connect('company.db')

	# Create a cursor instance
	c = conn.cursor()

	# Add New Record
	c.execute("INSERT INTO people VALUES (:first, :last, :id, :address, :city, :state, :email, :dept_id, :ds_id)",
		{
			'first': fn_entry.get(),
			'last': ln_entry.get(),
			'id': id_entry.get(),
			'address': address_entry.get(),
			'city': city_entry.get(),
			'state': state_entry.get(),
			'zip_code': zip_code_entry.get(),
			'email': email_entry.get(),
            'dept': dept_entry.get(), 
			'dept_sub': ds_entry.get(), 
		})
	

	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()

	# Clear entry boxes
	fn_entry.delete(0, END)
	ln_entry.delete(0, END)
	id_entry.delete(0, END)
	address_entry.delete(0, END)
	city_entry.delete(0, END)
	state_entry.delete(0, END)
	zip_code_entry.delete(0, END)
	email_entry.delete(0, END)
	dept_entry.delete(0,  END)
	ds_entry.delete(0,  END)
    
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
	c.execute("""CREATE TABLE if not exists people (
		first_name text,
		last_name text,
		id integer,
		address text,
		city text,
		state text,
		zip_code text,
		email text),
        dept text),
        dept_sub text)
		""")
	
	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()

# Add Buttons
button_frame = LabelFrame(root, text="Commands")
button_frame.pack(fill="x", expand="yes", padx=20)

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

# Run to pull data from database on start
query_database()

root.mainloop()
