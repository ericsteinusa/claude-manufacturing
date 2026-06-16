"""Tests for login department scoping (menus.main_menu_script_for_dept).

Qt-free: just the pure dept-name -> main-menu-script mapping used to scope a
non-admin user to their own department after login.
"""

from manufacturing.menus import (
    DEPT_MAIN_MENU, DEPT_MENU_KEY, main_menu_script_for_dept)


def test_known_departments_resolve_to_scripts():
    assert main_menu_script_for_dept("Personnel") == "Personnel_Main_menu.py"
    assert main_menu_script_for_dept("Accounting") == "Accounting_Main_menu.py"
    assert main_menu_script_for_dept("Customer Service") == "cs_main_menu.py"
    assert main_menu_script_for_dept("Warehouse") == "Warehouse_Main_menu.py"


def test_dept_name_alias_resolves():
    # The dev DB stores "Information Technologies"; both names map to IT.
    assert main_menu_script_for_dept(
        "Information Technologies") == "IT_Main_Menu.py"
    assert main_menu_script_for_dept("Information Tech") == "IT_Main_Menu.py"


def test_unknown_or_menuless_departments_return_none():
    assert main_menu_script_for_dept("Company") is None
    assert main_menu_script_for_dept("Labs") is None
    assert main_menu_script_for_dept("Nonexistent") is None
    assert main_menu_script_for_dept("") is None
    assert main_menu_script_for_dept(None) is None


def test_every_menu_key_has_a_main_menu_script():
    # Each routable department key must have a script so scoped users are not
    # silently dropped to the company menu.
    for dept_name, key in DEPT_MENU_KEY.items():
        assert key in DEPT_MAIN_MENU, f"{dept_name} ({key}) missing a script"
