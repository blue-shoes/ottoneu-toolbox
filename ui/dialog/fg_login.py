import tkinter as tk     
from tkinter import *      
from tkinter import messagebox as mb
from tkinter.messagebox import CANCEL, OK 
import configparser

class Dialog(tk.Toplevel):

    def __init__(self, parent, uname=None, password=None):
        super().__init__(parent)
        self.title("Enter FanGraphs Credentials")
        frm = tk.Frame(self, borderwidth=4)

        self.preferences = configparser.ConfigParser()

        tk.Label(frm, text='FanGraphs credentials required to download projections.').grid(row=0, column=0, columnspan=2)

        tk.Label(frm, text="Username").grid(row=1, column=0)
        self.name_tv = StringVar()
        if uname is not None:
            self.name_tv.set(uname)
        tk.Entry(frm, textvariable=self.name_tv).grid(row=1, column=1)

        tk.Label(frm, text="Password").grid(row=2, column=0)
        self.password_tv = StringVar()
        if password is not None:
            self.password_tv.set(password)
        tk.Entry(frm, textvariable=self.password_tv).grid(row=2, column=1)

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
        if self.password_tv.get() is None:
            mb.showerror("Empty password", 'Please provide a password.')
            return
        self.status = OK
        if not self.preferences.has_section('fangraphs-config'):
            self.preferences.add_section('fangraphs-config')
        self.preferences.set('fangraphs-config', 'username', self.name_tv.get())
        self.preferences.set('fangraphs-config', 'password', self.password_tv.get())
        with open('conf/fangraphs.conf', 'w') as fd:
            self.preferences.write(fd)
        self.destroy()
    
    def cancel_click(self):
        self.status = CANCEL
        self.destroy()
