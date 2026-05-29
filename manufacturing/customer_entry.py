import psycopg2
from .db_pg import get_db
from tkinter import *
from tkinter import Label, Entry, Button, END
from tkinter import messagebox
from tkinter import ttk
from tkinter import colorchooser
from configparser import ConfigParser
import tkinter as tk

root = Tk()
customer = ''

# Database setup
def setup_database():
	conn = get_db()
	cursor = conn.cursor()
	cursor.execute("""
	CREATE TABLE IF NOT EXISTS customer (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
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

def query_database():
	global my_tree
	# Clear the Treeview
	for record in my_tree.get_children():
		my_tree.delete(record)
		
	# Create a database or connect to one that exists
	conn = get_db()

	# Create a cursor instance
	c = conn.cursor()

	c.execute("SELECT rowid, * FROM customer")
	records = c.fetchall()
	
	# Add our data to the screen
	global count
	count = 0
	
	
	for record in records:
		if count % 2 == 0:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[1], record[2],  record[3], record[4], record[5], record[6], record[7], record[8], record[9], record[10]), tags=('evenrow',))
		else:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[1], record[2],  record[3], record[4], record[5], record[6], record[7], record[8], record[9], record[10]), tags=('oddrow',))
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
	conn = get_db()

	# Create a cursor instance
	c = conn.cursor()

	c.execute("SELECT rowid, * FROM customer WHERE CAST(rowid AS TEXT) LIKE ?", (lookup_record,))
	records = c.fetchall()
	
	# Add our data to the screen
	global count
	count = 0
	
	
	for record in records:
		if count % 2 == 0:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[1], record[2],  record[3], record[4], record[5], record[6], record[7], record[8], record[9], record[10]), tags=('evenrow',))
		else:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[1], record[2],  record[3], record[4], record[5], record[6], record[7], record[8], record[9], record[10]), tags=('oddrow',))
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
	# search.iconbitmap('/images/red_dragon2.ico')

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

	#Update Treeview Color
	# Change Selected Color
	if highlight_color:
		style = ttk.Style()
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
	style = ttk.Style()
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
	customer_id = customer_id_entry.get()

	if not customer_id or not first_name or not last_name or not company_name or not phone_number or not address or not city or not state or not zip_code or not email:

		messagebox.showerror("Input Error", "Please fill in all fields.")

	#    return

	else:

		conn = get_db()
		cursor = conn.cursor()
		cursor.execute("INSERT INTO customer (first_name, last_name, company_name, phone_number, address, city, state, zip_code, email) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (customer_id, first_name, last_name, company_name, phone_number, address, city, state, zip_code, email))
		conn.commit()
		messagebox.showinfo("Message", "Customer Saved Successfully.")
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

		# display_data()

# Display data from the database
root.configure(bg="lightblue")
# Designate Height and Width of our app
app_width = 1400
app_height = 625

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

x = (screen_width / 2) - (app_width / 2)
y = (screen_height / 2) - (app_height / 2)
root.geometry(f'{app_width}x{app_height}+{int(x)}+{int(y)}')

# Read our config file and get colors
parser = ConfigParser()
parser.read("personnel.ini")
saved_primary_color = parser.get('colors', 'primary_color', fallback='lightblue')
saved_secondary_color = parser.get('colors', 'secondary_color', fallback='white')
saved_highlight_color = parser.get('colors', 'highlight_color', fallback='#347083')

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
my_tree['columns'] = ("Customer ID", "First Name", "Last Name", "Company Name", "Phone Number", "Address", "City", "State", "Zip Code", "Email")

# Format Our Columns
my_tree.column("#0", width=0, stretch=NO)
my_tree.column("Customer ID", anchor=CENTER, width=100)
my_tree.column("First Name", anchor=W, width=140)
my_tree.column("Last Name", anchor=W, width=140)
my_tree.column("Company Name", anchor=W, width=140)
my_tree.column("Phone Number", anchor=W, width=140)
my_tree.column("Address", anchor=W, width=140)
my_tree.column("City", anchor=W, width=140)
my_tree.column("State", anchor=W, width=140)
my_tree.column("Zip Code", anchor=W, width=140)
my_tree.column("Email", anchor=W, width=140)

# Create Headings
my_tree.heading("#0", text="", anchor=W)
my_tree.heading("Customer ID", text="Customer ID", anchor=CENTER)
my_tree.heading("First Name", text="First Name", anchor=W)
my_tree.heading("Last Name", text="Last Name", anchor=W)
my_tree.heading("Company Name", text="Company Name", anchor=W)
my_tree.heading("Phone Number", text="Phone Number", anchor=W)
my_tree.heading("Address", text="Address", anchor=W)
my_tree.heading("City", text="City", anchor=W)
my_tree.heading("State", text="State", anchor=W)
my_tree.heading("Zip Code", text="Zip Code", anchor=W)
my_tree.heading("Email", text="Email", anchor=W)

# Create Striped Row Tags
my_tree.tag_configure('oddrow', background=saved_secondary_color)
my_tree.tag_configure('evenrow', background=saved_primary_color)

root.title("Customer Entry")

# Add Record Entry Boxes
data_frame = LabelFrame(root, text="Record")
data_frame.pack(fill="x", expand="yes", padx=20)
data_frame.place(x=5, y=300, width=1385, height=100)
customer_id_label = Label(data_frame, text="ID")
customer_id_label.grid(row=0, column=0, padx=10, pady=10)
customer_id_entry = Entry(data_frame)
customer_id_entry.grid(row=0, column=1, padx=10, pady=10)

first_name_label = Label(data_frame, text="First Name:")
first_name_label.grid(row=0, column=2, padx=10, pady=10)
first_name_entry = Entry(data_frame)
first_name_entry.grid(row=0, column=3, padx=10, pady=10)

last_name_label = Label(data_frame, text="Last Name:")
last_name_label.grid(row=0, column=4, padx=10, pady=10)
last_name_entry = Entry(data_frame)
last_name_entry.grid(row=0, column=5, padx=10, pady=10)

company_name_label = Label(data_frame, text="Company Name:")
company_name_label.grid(row=0, column=6, padx=10, pady=10)
company_name_entry = Entry(data_frame)
company_name_entry.grid(row=0, column=7, padx=10, pady=10)

phone_number_label = Label(data_frame, text="Phone Number:")
phone_number_label.grid(row=0, column=8, padx=10, pady=10)
phone_number_entry = Entry(data_frame)
phone_number_entry.grid(row=0, column=9, padx=10, pady=10)

address_Label = Label(data_frame, text="Address:")
address_Label.grid(row=1, column=0, padx=10, pady=10)
address_entry = Entry(data_frame)
address_entry.grid(row=1, column=1, padx=10, pady=10)

city_Label = Label(data_frame, text="City:")
city_Label.grid(row=1, column=2, padx=10, pady=10)
city_entry = Entry(data_frame)
city_entry.grid(row=1, column=3, padx=10, pady=10)

state_label = Label(data_frame, text="State:")
state_label.grid(row=1, column=4, padx=10, pady=10)
state_entry = Entry(data_frame)
state_entry.grid(row=1, column=5, padx=10, pady=10)

zip_code_label = Label(data_frame, text="Zip Code:")
zip_code_label.grid(row=1, column=6, padx=10, pady=10)
zip_code_entry = Entry(data_frame)
zip_code_entry.grid(row=1, column=7, padx=10, pady=10)

email_Label = Label(data_frame, text="email:")
email_Label.grid(row=1, column=8, padx=10, pady=10)
email_entry = Entry(data_frame)
email_entry.grid(row=1, column=9, padx=10, pady=10)


# Move Row Up
def up():
	rows = my_tree.selection()
	for row in rows:
		my_tree.move(row, my_tree.parent(row), my_tree.index(row)-1)

# Move Row Down
def down():
	rows = my_tree.selection()
	for row in reversed(rows):
		my_tree.move(row, my_tree.parent(row), my_tree.index(row)+1)

# Remove one record
def remove_one():
	x = my_tree.selection()[0]
	my_tree.delete(x)

	# Create a database or connect to one that exists
	conn = get_db()

	# Create a cursor instance
	c = conn.cursor()

	# Delete From Database
	c.execute("DELETE from customer WHERE id=?", (customer_id_entry.get(),))

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
		conn = get_db()

		# Create a cursor instance
		c = conn.cursor()
		

		# Delete Everything From The Table
		c.executemany("DELETE FROM calls2 WHERE id = ?", [(a,) for a in ids_to_delete])

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
		conn = get_db()

		# Create a cursor instance
		c = conn.cursor()

		# Delete Everything From The Table
		c.execute("DROP TABLE customer")		


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
		global customer_id_entry, first_name_entry, last_name_entry, company_name_entry, phone_number_entry, address_entry, city_entry, state_entry, zip_code_entry, email_entry
		customer_id_entry.delete(0, END)
		first_name_entry.delete(0, END)
		last_name_entry.delete(0, END)
		company_name_entry.delete(0, END)
		phone_number_entry.delete(0, END)
		address_entry.delete(0, END)
		city_entry.delete(0, END)
		state_entry.delete(0, END)
		zip_code_entry.delete(0, END)
		email_entry.delete(0, END)
	

# Select Record
def select_record(e):
	# Clear entry boxes
	customer_id_entry.delete(0, END)
	first_name_entry.delete(0, END)
	last_name_entry.delete(0, END)
	company_name_entry.delete(0, END)
	phone_number_entry.delete(0, END)
	address_entry.delete(0, END)
	city_entry.delete(0, END)
	state_entry.delete(0, END)
	zip_code_entry.delete(0, END)
	email_entry.delete(0, END)
	
	
	# Grab record Number
	selected = my_tree.focus()
	# Grab record values
	values = my_tree.item(selected, 'values')
		
	# output to entry boxes
	customer_id_entry.insert(0, values[0])
	first_name_entry.insert(0, values[1])
	last_name_entry.insert(0, values[2])
	company_name_entry.insert(0, values[3])
	phone_number_entry.insert(0, values[4])
	address_entry.insert(0, values[5])
	city_entry.insert(0, values[6])
	state_entry.insert(0, values[7])
	zip_code_entry.insert(0, values[8])
	email_entry.insert(0, values[9])
	
		
# Update record
def update_record():
	# Grab the record number
	selected = my_tree.focus()
	# Update record
	my_tree.item(selected, text="", values=(customer_id_entry.get(), first_name_entry.get(), last_name_entry.get(), company_name_entry.get(), phone_number_entry.get(), address_entry.get(), city_entry.get(), state_entry.get(), zip_code_entry.get(), email_entry.get()))
	# Update the database
	# Create a database or connect to one that exists
	conn = get_db()

	# Create a cursor instance
	c = conn.cursor()

	c.execute("""UPDATE customer SET
		customer_id = :customer,
		first_name = :first_name,
		last_name = :last_name,
		company_name = :company_name,
		phone_number = :phone_number,
		address = :address,
		city = :city,
		zip_code = :zip_code,
		email = :email
			
		WHERE oid = :oid""",
		{	
			'first_name': first_name_entry.get(),
			'last_name': last_name_entry.get(),
			'company_name': company_name_entry.get(),
			'phone_number': phone_number_entry.get(),
			'address': address_entry.get(),
			'city': city_entry.get(),
			'state': state_entry.get(),
			'zip_code': zip_code_entry.get(),
			'email': email_entry.get(),
			'oid': customer_id_entry.get(),
		})
	
	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()


	# Clear entry boxes
	customer_id_entry.delete(0, END)
	first_name_entry.delete(0, END)
	last_name_entry.delete(0, END)
	company_name_entry.delete(0, END)
	phone_number_entry.delete(0, END)
	address_entry.delete(0, END)
	city_entry.delete(0, END)
	state_entry.delete(0, END)
	zip_code_entry.delete(0, END)
	email_entry.delete(0, END)
	
	
# add new record to database
def add_record():
	# Update the database
	# Create a database or connect to one that exists
	conn = get_db()

	# Create a cursor instance
	c = conn.cursor()

	# Add New Record
	c.execute("INSERT INTO customer (first_name, last_name, company_name, phone_number, address, city, state, zip_code, email) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (first_name_entry.get(), last_name_entry.get(), company_name_entry.get(), phone_number_entry.get(), address_entry.get(), city_entry.get(), state_entry.get(), zip_code_entry.get(), email_entry.get()))
	

	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()

	# Clear entry boxes
	customer_id_entry.delete(0, END)
	first_name_entry.delete(0, END)
	last_name_entry.delete(0, END)
	company_name_entry.delete(0, END)
	phone_number_entry.delete(0, END)
	address_entry.delete(0, END)
	city_entry.delete(0, END)
	state_entry.delete(0, END)
	zip_code_entry.delete(0, END)
	email_entry.delete(0, END)
		
	# Clear The Treeview Table
	my_tree.delete(*my_tree.get_children())

	# Run to pull data from database on start
	query_database()

def create_table_again():
	# Create a database or connect to one that exists
	conn = get_db()

	# Create a cursor instance
	c = conn.cursor()

	# Create Table
	c.execute("""CREATE TABLE if not exists customer (
		customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
		first_name text,
		last_name text,
		company_name text,
		phone_number text,
		address text,  
		city text,
		state text,
		zip_code text,
		email text
		)
		""")
	
	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()


# Add Buttons
button_frame = LabelFrame(root, text="Commands")
button_frame.place(x=5, y=650, width=1400, height=75)
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

# Initialize database and display data
setup_database()
query_database()
# display_data()

root.mainloop()