"""Launched as subprocess: python test_one_window.py <module> <class>"""
import sys, os, traceback

_DIR = r"C:\tester\manufacture\manufacturing"
os.chdir(_DIR)
sys.path.insert(0, _DIR)

mod_name, cls_name = sys.argv[1], sys.argv[2]

import importlib
from PyQt6 import QtWidgets, QtCore

app = QtWidgets.QApplication(sys.argv[:1])

try:
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    win = cls()
except Exception:
    print(f"INIT_ERROR: {traceback.format_exc().strip().splitlines()[-1]}", flush=True)
    sys.exit(1)

tab_widgets = win.findChildren(QtWidgets.QTabWidget)
errors = []

for tw in tab_widgets:
    for i in range(tw.count()):
        label = tw.tabText(i)
        try:
            tw.setCurrentIndex(i)
            app.processEvents()
        except Exception as e:
            errors.append(f"tab '{label}': {e}")
            print(f"TAB_ERROR: tab '{label}': {e}", flush=True)

tabs = sum(tw.count() for tw in tab_widgets)
if not errors:
    print(f"OK: {tabs} tabs", flush=True)

import os
os._exit(1 if errors else 0)
