import tkinter as tk     
from tkinter import *              
from tkinter import ttk
from tkinter import messagebox as mb
from tkinter.messagebox import CANCEL, OK 

from domain.domain import Draft_Target
from services import player_services

class Dialog(tk.TopLevel):
    def __init__(self, parent, target:Draft_Target):
        super().__init__(parent)
        self.title("Set Target Price")
        frm = tk.Frame(self, borderwidth=4)

        self.target = target

        if target.player is None:
            target.player = player_services.get_player(target.player_id)

        tk.Label(frm, text=f"Target Price for {target.player.name}:").grid(row=1, column=0)
        self.price_tv = IntVar()
        if target.price is not None:
            self.price_tv.set(target.price)
        tk.Entry(frm, textvariable=self.price_tv).grid(row=1, column=1)

        tk.Button(frm, text="OK", command=self.ok_click).grid(row=3, column=0)
        tk.Button(frm, text="Cancel", command=self.cancel_click).grid(row=3, column=1)

        self.status = CANCEL

        frm.pack()

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.wait_window()
    
    def ok_click(self):
        self.target.price = self.price_tv.get()
        self.status = OK
        self.destroy()
    
    def cancel_click(self):
        self.status = CANCEL
        self.destroy()