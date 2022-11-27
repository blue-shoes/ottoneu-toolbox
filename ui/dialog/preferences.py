import tkinter as tk     
from tkinter import *              
from tkinter import ttk 

class Dialog:
    def __init__(self, pref_dict=None):
        self.top = top = tk.Toplevel(None)
        top.title("Preferences")
        frm = tk.Frame(top, borderwidth=4)
        tk.Label(frm, text="Item", font="bold").grid(column=0, row=0)
        tk.Label(frm, text="Value", font="bold").grid(column=1, row=0)

        frm.pack(fill='both', expand=True)
