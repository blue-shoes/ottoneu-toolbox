from itertools import islice
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 

from services import league_services
from ui.dialog.progress import ProgressDialog
import os.path

class Dialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.league = None
        self.title("Import a League")
        frm = tk.Frame(self, borderwidth=4)

        ttk.Label(frm, text = "Enter League #:").grid(column=0,row=0, pady=5, sticky=tk.E)
        #width is in text units, not pixels
        self.league_num_entry = ttk.Entry(frm, width = 10)
        self.league_num_entry.grid(column=1,row=0, sticky=tk.W, padx=5)

        ttk.Button(frm, text="OK", command=self.populate_league).grid(row=1, column=0)
        ttk.Button(frm, text="Cancel", command=self.cancel).grid(row=1, column=1)

        frm.pack()

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.wait_window()
    
    def cancel(self):
        self.league = None
        self.destroy()
    
    def populate_league(self):
        pd = ProgressDialog(self.master, title='Getting League')
        self.league = league_services.create_league(self.league_num_entry.get(), pd)
        pd.set_completion_percent(100)
        pd.destroy()
        self.destroy()