import tkinter as tk     
from tkinter import *              
from tkinter import ttk
from tkinter import messagebox as mb
from tkinter.messagebox import CANCEL, OK 

from services import player_services

class Dialog(tk.Toplevel):
    def __init__(self, parent, player_id, price=None):
        super().__init__(parent)
        self.title("Set Target Price")
        frm = tk.Frame(self, borderwidth=4)

        player = player_services.get_player(player_id)

        tk.Label(frm, text=f"Target Price for {player.name}:").grid(row=1, column=0)
        self.price_tv = IntVar()
        if price is not None:
            self.price_tv.set(price)
        tk.Entry(frm, textvariable=self.price_tv).grid(row=1, column=1)

        tk.Button(frm, text="OK", command=self.ok_click).grid(row=3, column=0)
        tk.Button(frm, text="Cancel", command=self.cancel_click).grid(row=3, column=1)

        self.status = CANCEL

        frm.pack()

        self.protocol("WM_DELETE_WINDOW", self.cancel_click)

        self.wait_window()
    
    def ok_click(self):
        self.price = self.price_tv.get()
        self.status = OK
        self.destroy()
    
    def cancel_click(self):
        self.price = None
        self.status = CANCEL
        self.destroy()