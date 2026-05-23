import sqlite3
from tkinter import *
from tkinter import ttk

# Database setup


def setup_database():
    conn = sqlite3.connect("company.db")
    cursor = conn.cursor()

    # Create Parent table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS department (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        FOREIGN KEY (people_id) REFERENCES people (id)
        FOREIGN KEY (dept_id) REFERENCES dept (id)
        FOREIGN KEY (dept_sub_id) REFERENCES dept_sub (id)
    )
    """)

    # Create Child table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS people (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        ID INTEGER,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        zip_code TEXT NOT NULL,
        email TEXT NOT NULL,
        FOREIGN KEY (dept_id) REFERENCES dept (id)
        FOREIGN KEY (dept_sub_id) REFERENCES dept_sub (id)
    )
    """)

    # Create Child table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dept (
        dept_id INTEGER PRIMARY KEY AUTOINCREMENT ,
        dept_name TEXT
        )
    """)

    # Create Child table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dept_sub (
        dept_sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept_sub_name TEXT
        )
    """)

    # Fetch data with JOIN


def fetch_data():
    conn = sqlite3.connect("company.db")
    cursor = conn.cursor()

    query = """
    SELECT dept.dept_name, dept_sub.dept_sub_name
    FROM department
    JOIN dept ON (department.dept_id = dept.dept_id)
    JOIN dept_sub ON (department.dept_sub_id = dept_sub.dept_sub_id)
    ORDER BY dept_name ASC, dept_sub_name ASC

    """
    cursor.execute(query)
    data = cursor.fetchall()
    conn.close()
    return data

# Tkinter GUI


def create_gui():
    root = Tk()
    root.title("Department and Sub Department Viewer")

    # Treeview widget
    tree = ttk.Treeview(root, columns=("Dept Name", "Dept Sub Name"), show="headings")
    tree.heading("Dept Name", text="Dept Name")
    tree.heading("Dept Sub Name", text="Dept Sub Name")
    tree.pack(fill="both", expand=True)

    # Insert data into Treeview
    data = fetch_data()
    for dept_name, dept_sub_name in data:
        tree.insert("", "end", values=(dept_name, dept_sub_name))
    root.mainloop()


# Main execution
setup_database()
create_gui()
