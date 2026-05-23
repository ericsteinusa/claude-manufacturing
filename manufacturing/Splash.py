from tkinter import *
import tkinter as tk
from tkinter import Button, Label, PhotoImage

splash_root = Tk()
splash_root.title("Splash Screen!!")
app_width = 1000
app_height = 560
splash_root.overrideredirect(True)
# Supports .png, .gif, .pgm, .ppm
image = tk.PhotoImage(file="c:/source/pythonQSG/pyqt6 apps/images/manufacturing2.png")
screen_width = splash_root.winfo_screenwidth()
screen_height = splash_root.winfo_screenheight()

x = (screen_width / 2) - (app_width / 2)
y = (screen_height / 2) - (app_height / 2)

splash_root.geometry(f'{app_width}x{app_height}+{int(x)}+{int(y)}')

# Create a Label widget to display the image
splash_label = tk.Label(splash_root, image=image)
splash_label.pack(pady=20)


def main_window():
    # Kill the splash screen
    splash_root.destroy()


# Splash Screen Timer
splash_root.after(3000, main_window)

mainloop()
