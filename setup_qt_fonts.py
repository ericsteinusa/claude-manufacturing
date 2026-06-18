"""
Deploy Windows system fonts into the PyQt6 Qt6 fonts directory so that
QT_QPA_PLATFORM=offscreen renders text correctly (not as boxes).

Run once after installing PyQt6:
    python setup_qt_fonts.py
"""
import os, shutil, sys

try:
    import PyQt6
except ImportError:
    sys.exit("PyQt6 not installed in this environment.")

fonts_dir = os.path.join(os.path.dirname(PyQt6.__file__), "Qt6", "lib", "fonts")
os.makedirs(fonts_dir, exist_ok=True)

win_fonts = r"C:\Windows\Fonts"
candidates = [
    "arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf",
    "cour.ttf",  "courbd.ttf",
    "verdana.ttf", "verdanab.ttf",
    "tahoma.ttf", "tahomabd.ttf",
]

copied = 0
for name in candidates:
    src = os.path.join(win_fonts, name)
    dst = os.path.join(fonts_dir, name)
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy2(src, dst)
        print(f"  copied {name}")
        copied += 1

print(f"Done — {copied} font(s) deployed to {fonts_dir}")
