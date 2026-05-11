import sqlite3
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk
from tkinter import colorchooser
from configparser import ConfigParser

root = tk.Tk()
customer = ''

# Database setup
def setup_database():
	conn = sqlite3.connect('company.db')
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

	cursor.execute("""
	CREATE TABLE if not exists calls2 (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		customer_id INTEGER,
		call TEXT NOT NULL,
		call_date TEXT NOT NULL,
		call_time INTEGER NOT NULL,
		completion_date TEXT NOT NULL,
		completion_time INTEGER NOT NULL,
		comments_box TEXT NOT NULL,
		completion_box INTEGER NOT NULL,
		FOREIGN KEY (customer_id) REFERENCES customer(id)
		)
	""")
	conn.commit()
	conn.close()

def query_database():
	# Clear the Treeview
	for record in my_tree.get_children():
		my_tree.delete(record)
		
	# Create a database or connect to one that exists
	conn = sqlite3.connect('company.db')

	# Create a cursor instance
	c = conn.cursor()

	c.execute("SELECT rowid, * FROM calls2")
	records = c.fetchall()
	
	# Add our data to the screen
	global count
	count = 0
	
	
	for record in records:
		if count % 2 == 0:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[1], record[2],  record[3], record[4], record[5], record[6], record[7], record[8], record[9]), tags=('evenrow',))
		else:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[1], record[2],  record[3], record[4], record[5], record[6], record[7], record[8], record[9]), tags=('oddrow',))
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

	c.execute("SELECT rowid, * FROM calls2 WHERE rowid like ?", (lookup_record,))
	records = c.fetchall()
	
	# Add our data to the screen
	global count
	count = 0
	
	
	for record in records:
		if count % 2 == 0:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[1], record[2],  record[3], record[4], record[5], record[6], record[7], record[8], record[9]), tags=('evenrow',))
		else:
			my_tree.insert(parent='', index='end', iid=count, text='', values=(record[1], record[2],  record[3], record[4], record[5], record[6], record[7], record[8], record[9]), tags=('oddrow',))
		# increment counter
		count += 1


	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()

def lookup_records():
	global search_entry, search

	search = tk.Toplevel(root)
	search.title("Lookup Records")
	search.geometry("400x200")
	# search.iconbitmap('/images/red_dragon2.ico')

	# Create label frame
	search_frame = tk.LabelFrame(search, text="Record Number")
	search_frame.pack(padx=10, pady=10)

	# Add entry box
	search_entry = tk.Entry(search_frame, font=("Helvetica", 18))
	search_entry.pack(pady=20, padx=20)

	# Add button
	search_button = tk.Button(search, text="Search Records", command=search_records)
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
my_menu = tk.Menu(root)
root.config(menu=my_menu)

# Configure our menu
option_menu = tk.Menu(my_menu, tearoff=0)
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
search_menu = tk.Menu(my_menu, tearoff=0)
my_menu.add_cascade(label="Search", menu=search_menu)
# Drop down menu
search_menu.add_command(label="Search", command=lookup_records)
search_menu.add_separator()
search_menu.add_command(label="Reset", command=query_database)



# Step 2: Fetch data for the selection list
def fetch_customer():
	conn = sqlite3.connect("company.db")
	cursor = conn.cursor()
	cursor.execute("SELECT id || ' ' || first_name || ' ' || last_name as full_name FROM customer")
	customer_list = cursor.fetchall()
	conn.close()
	return [row[0] for row in customer_list]

# Insert data into the database
def insert_data():
	customer_id = customer_combobox.get().split(' ')[0].strip('{')
	call = call_widget.get("1.0", "end-1c") # Get text from Text Widget
	call_date = call_date_entry.get()
	call_time = call_time_entry.get()
	completion_date = completion_date_entry.get()
	completion_time= completion_time_entry.get()
	comments_box= comment_widget.get("1.0", "end-1c") # Get text from Text Widget
	completion_box = checkbox_var.get() # Get value from checkbox (0 or 1)

	if not customer_id or not call or not call_date or not call_time or not completion_date or not completion_time or not comments_box or not completion_box:

		messagebox.showerror("Input Error", "Please fill in all fields.")

	#    return

	else:

		conn = sqlite3.connect("company.db")
		cursor = conn.cursor()
		cursor.execute("INSERT INTO calls2 (customer_id, call, call_date, call_time, completion_date, completion_time, comments_box, completion_box) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (customer_id, call, call_date, call_time, completion_date, completion_time, comments_box, completion_box))
		conn.commit()
		messagebox.showinfo("Message", "Call Saved Successfully.")
		conn.close()
		customer_combobox.delete(0, tk.END)
		call_widget.delete("1.0", tk.END)
		call_date_entry.delete(0, tk.END)
		call_time_entry.delete(0, tk.END)
		completion_date_entry.delete(0, tk.END)
		completion_time_entry.delete(0, tk.END)
		comments_box.delete("1.0", tk.END)
		completion_box.delete(0, tk.END)
		# display_data()

# Display data from the database
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
tree_frame = tk.Frame(root)
tree_frame.pack(pady=10)

# Create a Treeview Scrollbar
tree_scroll = tk.Scrollbar(tree_frame)
tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

# Create The Treeview
my_tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, selectmode="extended")
my_tree.pack()

# Configure the Scrollbar
tree_scroll.config(command=my_tree.yview)

# Define Our Columns
my_tree['columns'] = ("ID", "customer ID", "Problem", "Call Date", "Call Time", "Completion Date", "Completion Time", "Comments", "Completion Box")

# Format Our Columns
my_tree.column("#0", width=0, stretch=tk.NO)
my_tree.column("ID", anchor=tk.CENTER, width=100)
my_tree.column("customer ID", anchor=tk.W, width=140)
my_tree.column("Problem", anchor=tk.W, width=140)
my_tree.column("Call Date", anchor=tk.W, width=140)
my_tree.column("Call Time", anchor=tk.W, width=140)
my_tree.column("Completion Date", anchor=tk.W, width=140)
my_tree.column("Completion Time", anchor=tk.W, width=140)
my_tree.column("Comments", anchor=tk.W, width=140)
my_tree.column("Completion Box", anchor=tk.CENTER, width=100)

# Create Headings
my_tree.heading("#0", text="", anchor=tk.W)
my_tree.heading("ID", text="ID", anchor=tk.CENTER)
my_tree.heading("customer ID", text="customer ID", anchor=tk.W)
my_tree.heading("Problem", text="Problem", anchor=tk.W)
my_tree.heading("Call Date", text="Call Date", anchor=tk.W)
my_tree.heading("Call Time", text="Call Time", anchor=tk.W)
my_tree.heading("Completion Date", text="Completion Date", anchor=tk.W)
my_tree.heading("Completion Time", text="Completion Time", anchor=tk.W)
my_tree.heading("Comments", text="Comments", anchor=tk.W)
my_tree.heading("Completion Box", text="Completion Box", anchor=tk.CENTER)

# Create Striped Row Tags
my_tree.tag_configure('oddrow', background=saved_secondary_color)
my_tree.tag_configure('evenrow', background=saved_primary_color)

root.title("Customer Service Calls")

# Add Record Entry Boxes
data_frame = tk.LabelFrame(root, text="Record")
# data_frame.pack(fill="x", expand="yes", padx=20)
data_frame.place(x=5, y=300, width=1200, height=250)
id_label = tk.Label(data_frame, text="ID")
id_label.grid(row=0, column=0, padx=10, pady=10)
id_entry = tk.Entry(data_frame)
id_entry.grid(row=0, column=1, padx=10, pady=10)

# Parent selection Combobox
customer_data = fetch_customer()
customer_id_label = tk.Label(data_frame, text="Customer ID:")
customer_id_label.grid(row=0, column=2, padx=10, pady=10)
customer_combobox = ttk.Combobox(root, values=customer_data)
customer_combobox['values'] = customer_data
customer_combobox.place(x=275, y=327)
# customers = customer_combobox.get()
# customer_id = customers.split(' ')[0] # Extract ID from the selected value
customer_combobox.bind("<<ComboboxSelected>>")


tk.Label(root, text="Call:").place(x=425, y=327)
call_widget = tk.Text(root, wrap="word", width=30, height=5)
call_widget.place(x=460, y=327)
call = call_widget.get("1.0", "end-1c") # Get text from Text widget

tk.Label(root, text="Call Date:").place(x=715, y=327)
call_date_entry = tk.Entry(root)
call_date_entry.place(x=775, y=327)

tk.Label(root, text="Call Time:").place(x=910, y=327)
call_time_entry = tk.Entry(root)
call_time_entry.place(x=975, y=327)

tk.Label(root, text="Completion Date:").place(x=25, y= 440)
completion_date_entry = tk.Entry(root)
completion_date_entry.place(x=130, y=440)

tk.Label(root, text="Completion Time:").place(x=270, y=440)
completion_time_entry = tk.Entry(root)
completion_time_entry.place(x=378, y=440)

tk.Label(root, text="Comments:").place(x=518, y=440)
comment_widget = tk.Text(root, wrap="word", width=30, height=5)
comment_widget.place(x=590, y=440)

# Variable to store completion status
checkbox_var = tk.IntVar()
# Create a checkbox
checkbox = tk.Checkbutton(root, text="Completed", variable=checkbox_var)
checkbox.place(x=850, y=440)

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
	c.execute("DELETE from calls2 WHERE oid=" + id_entry.get())
	


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
		conn = sqlite3.connect('company.db')

		# Create a cursor instance
		c = conn.cursor()

		# Delete Everything From The Table
		c.execute("DROP TABLE calls2")		


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
	id_entry.delete(0, tk.END)
	customer_combobox.delete(0, tk.END)
	call_widget.delete("1.0", tk.END)
	call_date_entry.delete(0, tk.END)
	call_time_entry.delete(0, tk.END)
	completion_date_entry.delete(0, tk.END)
	completion_time_entry.delete(0, tk.END)
	comment_widget.delete("1.0", tk.END)
	checkbox_var.set(0)
	

# Select Record
def select_record(e):
	# Clear entry boxes
	id_entry.delete(0, tk.END)
	customer_combobox.delete(0, tk.END)
	call_widget.delete("1.0", tk.END)
	call_date_entry.delete(0, tk.END)
	call_time_entry.delete(0, tk.END)
	completion_date_entry.delete(0, tk.END)
	completion_time_entry.delete(0, tk.END)
	comment_widget.delete("1.0", tk.END)
	checkbox_var.set(0)
	
	
	# Grab record Number
	selected = my_tree.focus()
	# Grab record values
	values = my_tree.item(selected, 'values')
		
	# output to entry boxes
	id_entry.insert(0, values[0])
	customer_combobox.insert(0, values[1])
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
	my_tree.item(selected, text="", values=(id_entry.get(), customer_combobox.get().split(' ')[0].strip('{'), call_widget.get("1.0", "end-1c"), call_date_entry.get(), call_time_entry.get(), completion_date_entry.get(), completion_time_entry.get(), comment_widget.get("1.0", "end-1c"), checkbox_var.get()))
	# Update the database
	# Create a database or connect to one that exists
	conn = sqlite3.connect('company.db')

	# Create a cursor instance
	c = conn.cursor()

	c.execute("""UPDATE calls2 SET
		customer_id = :customer,
		call = :call,
		call_date = :call_date,
		call_time = :call_time,
		completion_date = :completion_date,
		completion_time = :completion_time,
		comments_box = :comments_box,
		completion_box = :completion_box
			
		WHERE oid = :oid""",
		{	
			'customer': customer_combobox.get().split(' ')[0].strip('{'),
			'call': call_widget.get("1.0", "end-1c"),
			'call_date': call_date_entry.get(),
			'call_time': call_time_entry.get(),
			'completion_date': completion_date_entry.get(),
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
	id_entry.delete(0, tk.END)
	customer_combobox.delete(0, tk.END)
	call_widget.delete("1.0", tk.END)
	call_date_entry.delete(0, tk.END)
	call_time_entry.delete(0, tk.END)
	completion_date_entry.delete(0, tk.END)
	completion_time_entry.delete(0, tk.END)
	comment_widget.delete("1.0", tk.END)
	checkbox_var.set(0)
	
	
# add new record to database
def add_record():
	# Update the database
	# Create a database or connect to one that exists
	conn = sqlite3.connect('company.db')

	# Create a cursor instance
	c = conn.cursor()

	# Add New Record
	c.execute("INSERT INTO calls2 (customer_id, call, call_date, call_time, completion_date, completion_time, comments_box, completion_box) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (customer_combobox.get().split(' ')[0].strip('{'), call_widget.get("1.0", "end-1c"), call_date_entry.get(), call_time_entry.get(), completion_date_entry.get(), completion_time_entry.get(), comment_widget.get("1.0", "end-1c"), checkbox_var.get()))
	

	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()

	# Clear entry boxes
	id_entry.delete(0, tk.END)
	customer_combobox.delete(0, tk.END)
	call_widget.delete("1.0", tk.END)
	call_date_entry.delete(0, tk.END)
	call_time_entry.delete(0, tk.END)
	completion_date_entry.delete(0, tk.END)
	completion_time_entry.delete(0, tk.END)
	comment_widget.delete("1.0", tk.END)
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
	c.execute("""CREATE TABLE if not exists calls2 (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		customer_id integer,
		call text,
		call_date text,
		call_time text,
		completion_date,
		completion_time,  
		comments_box text,
		completion_box integer,
		FOREIGN KEY (customer_id) REFERENCES customer(id))
		""")
	
	# Commit changes
	conn.commit()

	# Close our connection
	conn.close()


# Add Buttons
button_frame = tk.LabelFrame(root, text="Commands")
button_frame.place(x=5, y=565, width=1200, height=75)
# button_frame.pack(fill="x", expand="yes", padx=20)

update_button = tk.Button(button_frame, text="Update Record", command=update_record)
update_button.grid(row=0, column=0, padx=10, pady=10)

add_button = tk.Button(button_frame, text="Add Record", command=add_record)
add_button.grid(row=0, column=1, padx=10, pady=10)

remove_all_button = tk.Button(button_frame, text="Remove All Records", command=remove_all)
remove_all_button.grid(row=0, column=2, padx=10, pady=10)

remove_one_button = tk.Button(button_frame, text="Remove One Selected", command=remove_one)
remove_one_button.grid(row=0, column=3, padx=10, pady=10)

remove_many_button = tk.Button(button_frame, text="Remove Many Selected", command=remove_many)
remove_many_button.grid(row=0, column=4, padx=10, pady=10)

move_up_button = tk.Button(button_frame, text="Move Up", command=up)
move_up_button.grid(row=0, column=5, padx=10, pady=10)

move_down_button = tk.Button(button_frame, text="Move Down", command=down)
move_down_button.grid(row=0, column=6, padx=10, pady=10)

select_record_button = tk.Button(button_frame, text="Clear Entry Boxes", command=clear_entries)
select_record_button.grid(row=0, column=7, padx=10, pady=10)

# Bind the treeview
my_tree.bind("<ButtonRelease-1>", select_record)

# Initialize database and display data
setup_database()
query_database()
# display_data()

root.mainloop()