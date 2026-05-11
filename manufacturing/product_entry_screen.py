from tkinter import *
from tkinter import ttk
from tkinter import messagebox
import sqlite3
from tkinter import colorchooser
from configparser import ConfigParser

root = Tk()
root.title('Product')
root.geometry("1350x600")

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

	c.execute("SELECT rowid, * FROM product")
	records = c.fetchall()
	
	# Add our data to the screen
	global count
	count = 0
	
	for record in records:
		print(record)


	for record in records:
		if count % 2 == 0:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[1], record[2], record[3],  record[4], record[5], record[6], record[7]), tags=('evenrow',))
		else:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[1], record[2], record[3],  record[4], record[5], record[6], record[7]), tags=('oddrow',))
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

	c.execute("SELECT rowid, * FROM product WHERE name like ?", (lookup_record,))
	records = c.fetchall()
	
	# Add our data to the screen
	global count
	count = 0
	
	#for record in records:
	#	print(record)


	for record in records:
		if count % 2 == 0:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[0], record[1], record[2],  record[3], record[4], record[5]), tags=('evenrow',))
		else:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[0], record[1], record[2],  record[3], record[4], record[5]), tags=('oddrow',))
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
	search.iconbitmap('/images/red_dragon2.ico')

	# Create label frame
	search_frame = LabelFrame(search, text="Name")
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

# Add Fake Data


# Do some database stuff
# Create a database or connect to one that exists
conn = sqlite3.connect('company.db')

# Create a cursor instance
c = conn.cursor()

# Create Tables

c.execute("""
    CREATE TABLE IF NOT EXISTS supplier (
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

c.execute("""
	CREATE TABLE if not exists product (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		supplier_id INTEGER,
		name text,
		purchase_date text,
		purchase_price integer,
		bin integer,  
	    amount integer,
		FOREIGN KEY (supplier_id) REFERENCES supplier(id)
		)
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
my_tree['columns'] = ("ID", "Supplier ID", "Name", "Purchase Date", "Purchase Price", "Bin", "Amount")

# Format Our Columns
my_tree.column("#0", width=0, stretch=NO)
my_tree.column("ID", anchor=CENTER, width=100)
my_tree.column("Supplier ID", anchor=CENTER, width=100)
my_tree.column("Name", anchor=W, width=140)
my_tree.column("Purchase Date", anchor=W, width=140)
my_tree.column("Purchase Price", anchor=W, width=140)
my_tree.column("Bin", anchor=W, width=140)
my_tree.column("Amount", anchor=W, width=140)

# Create Headings
my_tree.heading("#0", text="", anchor=W)
my_tree.heading("ID", text="ID", anchor=CENTER)
my_tree.heading("Supplier ID", text="Supplier ID", anchor=CENTER)
my_tree.heading("Name", text="Name", anchor=W)
my_tree.heading("Purchase Date", text="Purchase Date", anchor=W)
my_tree.heading("Purchase Price", text="Purchase Price", anchor=W)
my_tree.heading("Bin", text="Bin", anchor=W)
my_tree.heading("Amount", text="Amount")

# Create Striped Row Tags
my_tree.tag_configure('oddrow', background=saved_secondary_color)
my_tree.tag_configure('evenrow', background=saved_primary_color)

# Step 2: Fetch data for the selection list
def fetch_supplier():
	conn = sqlite3.connect("company.db")
	cursor = conn.cursor()
	cursor.execute("SELECT id, company_name FROM supplier")
	supplier = [row[1] for row in cursor.fetchall()]
	conn.close()
	return supplier


# Add Record Entry Boxes
data_frame = LabelFrame(root, text="Record")
data_frame.pack(fill="x", expand="yes", padx=20)

id_label = Label(data_frame, text="ID")
id_label.grid(row=0, column=0, padx=10, pady=10)
id_entry = Entry(data_frame)
id_entry.grid(row=0, column=1, padx=10, pady=10)

si_data = fetch_supplier()
si_label = Label(data_frame, text="Supplier ID:")
si_label.grid(row=0, column=2, padx=10, pady=10)
si_combobox = ttk.Combobox(root, values=si_data)
si_combobox.place(x=292, y=348)
si_combobox.bind("<<ComboboxSelected>>")


nm_label = Label(data_frame, text="Name")
nm_label.grid(row=0, column=4, padx=10, pady=10)
nm_entry = Entry(data_frame)
nm_entry.grid(row=0, column=5, padx=10, pady=10)

pd_label = Label(data_frame, text="Purchase Date")
pd_label.grid(row=0, column=6, padx=10, pady=10)
pd_entry = Entry(data_frame)
pd_entry.grid(row=0, column=7, padx=10, pady=10)

pp_label = Label(data_frame, text="Purchase Price")
pp_label.grid(row=0, column=8, padx=10, pady=10)
pp_entry = Entry(data_frame)
pp_entry.grid(row=0, column=9, padx=10, pady=10)

bin_label = Label(data_frame, text="Bin")
bin_label.grid(row=1, column=0, padx=10, pady=10)
bin_entry = Entry(data_frame)
bin_entry.grid(row=1, column=1, padx=10, pady=10)

amt_label = Label(data_frame, text="Amount")
amt_label.grid(row=1, column=2, padx=10, pady=10)
amt_entry = Entry(data_frame)
amt_entry.grid(row=1, column=3, padx=10, pady=10)

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
	c.execute("DELETE from product WHERE oid=" + id_entry.get())
	


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
		c.executemany("DELETE FROM product WHERE id = ?", [(a,) for a in ids_to_delete])

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
		c.execute("DROP TABLE product")		


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
	si_combobox.delete(0, END)
	nm_entry.delete(0, END)
	pd_entry.delete(0, END)
	pp_entry.delete(0, END)
	bin_entry.delete(0, END)
	amt_entry.delete(0, END)
	

# Select Record
def select_record(e):
	# Clear entry boxes
	id_entry.delete(0, END)
	si_combobox.delete(0, END)
	nm_entry.delete(0, END)
	pd_entry.delete(0, END)	
	pp_entry.delete(0, END)
	bin_entry.delete(0, END)
	amt_entry.delete(0, END)
	
	
	# Grab record Number
	selected = my_tree.focus()
	# Grab record values
	values = my_tree.item(selected, 'values')

	# output to entry boxes
	id_entry.insert(0, values[0])
	si_combobox.insert(0, values[1])
	nm_entry.insert(0, values[2])
	pd_entry.insert(0, values[3])
	pp_entry.insert(0, values[4])
	bin_entry.insert(0, values[5])
	amt_entry.insert(0, values[6])
	
		
# Update record
def update_record():
	# Grab the record number
	selected = my_tree.focus()
	# Update record
	my_tree.item(selected, text="", values=(id_entry.get(), si_combobox.get(), nm_entry.get(), pd_entry.get(), pp_entry.get(), bin_entry.get(), amt_entry.get()))

	# Update the database
	# Create a database or connect to one that exists
	conn = sqlite3.connect('company.db')

	# Create a cursor instance
	c = conn.cursor()

	c.execute("""UPDATE product SET
		supplier_id = :supplier_id,
		name = :name,
		purchase_date = :purchase_date,
		purchase_price = :purchase_price,
		bin = :bin,
		amount = :amount
	
		WHERE oid = :oid""",
		{
			'oid': id_entry.get(),
			'supplier_id': si_combobox.get(),
			'name': nm_entry.get(),
			'purchase_date': pd_entry.get(),
			'purchase_price': pp_entry.get(),
			'bin': bin_entry.get(),
			'amount': amt_entry.get()
		})
	


	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()


	# Clear entry boxes
	id_entry.delete(0, END)
	si_combobox.delete(0, END)
	nm_entry.delete(0, END)
	pd_entry.delete(0, END)
	pp_entry.delete(0, END)
	bin_entry.delete(0, END)
	amt_entry.delete(0, END)
	
# add new record to database
def add_record():
	# Update the database
	# Create a database or connect to one that exists
	conn = sqlite3.connect('company.db')

	# Create a cursor instance
	c = conn.cursor()

	# Add New Record
	c.execute("INSERT INTO product (supplier_id, name, purchase_date, purchase_price, bin, amount) VALUES (?, ?, ?, ?, ?, ?)", (si_combobox.get(), nm_entry.get(), pd_entry.get(), pp_entry.get(), bin_entry.get(), amt_entry.get()))
	

	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()

	# Clear entry boxes
	id_entry.delete(0, END)
	si_combobox.delete(0, END)
	nm_entry.delete(0, END)
	pd_entry.delete(0, END)	
	pp_entry.delete(0, END)
	bin_entry.delete(0, END)
	amt_entry.delete(0, END)
		
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
	c.execute("""CREATE TABLE if not exists product (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		supplier_id INTEGER,
		name text,
		purchase_date text,
		purchase_price integer,
		bin integer,  
	    amount integer)
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
