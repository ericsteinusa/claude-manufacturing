# ruff: noqa: F403,F405
from ..db_pg import get_db
from tkinter import *  # noqa: F401,F403,F405
from tkinter import ttk

def fetch_data():
    conn = get_db()
    cursor = conn.cursor()

    query = """
    SELECT COALESCE(dept.dept_name, '(unassigned)') AS dept_name,
           COALESCE(dept_sub.dept_sub_name, '(unassigned)') AS dept_sub_name
    FROM department
    LEFT JOIN dept ON (department.dept_id = dept.dept_id)
    LEFT JOIN dept_sub ON (department.dept_sub_id = dept_sub.dept_sub_id)
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
    tree = ttk.Treeview(
    root,
    columns=(
        "Dept Name",
        "Dept Sub Name"),
         show="headings")
    tree.heading("Dept Name", text="Dept Name")
    tree.heading("Dept Sub Name", text="Dept Sub Name")
    tree.pack(fill="both", expand=True)

    # Insert data into Treeview
    data = fetch_data()
    for dept_name, dept_sub_name in data:
        tree.insert("", "end", values=(dept_name, dept_sub_name))
    root.mainloop()


# Main execution
if __name__ == "__main__":
    create_gui()
