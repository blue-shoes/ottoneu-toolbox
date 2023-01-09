import tkinter as tk     
from tkinter import *              
from tkinter import ttk
from tkinter import messagebox as mb
from tkinter.messagebox import CANCEL, OK 

class Dialog(tk.Toplevel):

    def __init__(self, parent, title, name=None, desc=None):
        super().__init__(parent)
        self.title(title)
        frm = tk.Frame(self, borderwidth=4)

        tk.Label(frm, text="Name:").grid(row=1, column=0)
        self.name_tv = StringVar()
        if name is not None:
            self.name_tv.set(name)
        tk.Entry(frm, textvariable=self.name_tv).grid(row=1, column=1)

        tk.Label(frm, text="Description:").grid(row=2, column=0)
        self.desc_tv = StringVar()
        if desc is not None:
            self.desc_tv.set(desc)
        tk.Entry(frm, textvariable=self.desc_tv).grid(row=2, column=1)

        tk.Button(frm, text="OK", command=self.ok_click).grid(row=3, column=0)
        tk.Button(frm, text="Cancel", command=self.cancel_click).grid(row=3, column=1)

        self.status = CANCEL

        frm.pack()

        self.lift()
        self.focus_force()

        self.protocol("WM_DELETE_WINDOW", self.cancel_click)

        self.wait_window()
    
    def ok_click(self):
        if self.name_tv.get() is None:
            mb.showerror("Empty Name", 'Please provide a name.')
            return
        if self.desc_tv.get() is None:
            mb.showerror("Empty Description", 'Please provide a description.')
            return
        self.status = OK
        self.destroy()
    
    def cancel_click(self):
        self.status = CANCEL
        self.destroy()
