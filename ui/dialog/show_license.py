import tkinter as tk     
from tkinter import *   
from tkinter import scrolledtext, font  

class Dialog(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent) 
        license_path = parent.get_resource_path('LICENSE')
        with open(license_path, 'r') as lic_fil:
            long_text = lic_fil.read()
        text_widget = scrolledtext.ScrolledText(self, width=100, height=20,
            font = font.nametofont("TkDefaultFont"))

        text_widget.insert(tk.INSERT, long_text)
        text_widget.configure(state='disabled')

        text_widget.insert(tk.END, long_text)
        text_widget.pack()
        self.focus_force()