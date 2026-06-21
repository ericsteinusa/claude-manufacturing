# ruff: noqa: F403,F405
from .db_pg import get_db
from .schema import init_schema
from tkinter import *  # noqa: F401,F403,F405
from tkinter import ttk

# Database setup


def setup_database():
    init_schema()

    # Fetch data with JOIN


def fetch_data():
    conn = get_db()
    cursor = conn.cursor()

    query = """
    SELECT first_name, last_name,
           COALESCE(dept.dept_name, '(unassigned)') AS dept_name,
           COALESCE(dept_sub.dept_sub_name, '(unassigned)') AS dept_sub_name
    FROM people
    LEFT JOIN dept ON (people.dept_id = dept.dept_id)
    LEFT JOIN dept_sub ON (people.dept_sub_id = dept_sub.dept_sub_id)
    ORDER BY dept_sub_name ASC

    """
    cursor.execute(query)
    data = cursor.fetchall()
    conn.close()
    return data

# Tkinter GUI


def create_gui():
    root = Tk()
    root.title("Employee Department Viewer")

    # Treeview widget
    tree = ttk.Treeview(
    root,
    columns=(
        "First Name",
        "Last Name",
        "Dept Name",
        "Dept Sub Name"),
         show="headings")
    tree.heading("First Name", text="First Name")
    tree.heading("Last Name", text="Last Name")
    tree.heading("Dept Name", text="Dept Name")
    tree.heading("Dept Sub Name", text="Dept Sub Name")
    tree.pack(fill="both", expand=True)

    # Insert data into Treeview
    data = fetch_data()
    for people_first_Name, people_last_name, dept_name, dept_sub_name in data:
        tree.insert(
    "",
    "end",
    values=(
        people_first_Name,
        people_last_name,
        dept_name,
         dept_sub_name))
    root.mainloop()


# Main execution
if __name__ == "__main__":
    setup_database()
    create_gui()
