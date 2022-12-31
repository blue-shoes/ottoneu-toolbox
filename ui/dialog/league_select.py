import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import messagebox as mb
from ui.dialog.wizard import league_import
from ui.table import Table
import logging

from services import league_services
from domain.enum import ScoringFormat

class Dialog(tk.Toplevel):
    def __init__(self, parent, active=True):
        super().__init__(parent)
        self.league = None
        self.title("Select a League")
        frm = tk.Frame(self, borderwidth=4)

        self.league_list = league_services.get_leagues(active)

        cols = ('Lg Id', 'Name', 'Format', '# Teams')
        align = {}
        align['Name'] = W
        width = {}
        width['Name'] = 175

        self.league_table = lt = Table(frm, cols, align, width, cols)
        lt.grid(row=0, columnspan=3)
        lt.set_row_select_method(self.on_select)
        lt.set_refresh_method(self.populate_table)
        lt.set_double_click_method(self.double_click)

        self.populate_table()

        ttk.Button(frm, text="OK", command=self.set_league).grid(row=1, column=0)
        ttk.Button(frm, text="Cancel", command=self.cancel).grid(row=1, column=1)
        ttk.Button(frm, text="Import New...", command=self.import_league).grid(row=1,column=2)

        frm.pack()

        self.focus_force()

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.wait_window()
    
    def import_league(self):
        try:
            dialog = league_import.Dialog(self.master)
            if dialog.league is not None:
                self.league = dialog.league
                self.destroy()
            else:
                self.lift()
                self.focus_force()
        except Exception as Arguement:
            mb.showerror('Error downloading league, please try again')
            logging.exception('Error downloading league')
    
    def populate_table(self):
        for lg in self.league_list:
            lgfmt = ScoringFormat.enum_to_short_name_map()[lg.format]
            self.league_table.insert('', tk.END, text=str(lg.index), values=(lg.ottoneu_id, lg.name, lgfmt, lg.num_teams))

    def double_click(self, event):
        self.on_select(event)
        self.set_league()

    def on_select(self, event):
        selection = event.widget.item(event.widget.selection()[0])["text"]
        for lg in self.league_list:
            if lg.index == int(selection):
                self.league = league_services.get_league(lg.index)
                break

    def cancel(self):
        self.league = None
        self.destroy()
    
    def set_league(self):
        self.destroy()