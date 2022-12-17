import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from ui.dialog import proj_download
from ui.table import Table, bool_to_table

from services import league_services

class Dialog(tk.Toplevel):
    def __init__(self, parent, active=True):
        super().__init__(parent)
        self.projection = None
        self.title("Select a League")
        frm = tk.Frame(self, borderwidth=4)

        self.league_list = league_services.get_leagues(active)

        cols = ('Lg Id', 'Name', 'Format', '# Teams')
        align = {}
        align['Name'] = W
        width = {}
        width['Name'] = 175

        self.league_table = lt = Table(frm, cols, align, width, cols)
        lt.grid(row=1, columnspan=2)
        lt.set_row_select_method(self.on_select)
        lt.set_refresh_method(self.populate_table)

        self.populate_table()

        ttk.Button(frm, text="OK", command=self.set_projection).grid(row=3, column=0)
        ttk.Button(frm, text="Cancel", command=self.cancel).grid(row=3, column=1)
        ttk.Button(frm, text="Import New...", command=self.import_league).grid(row=3,column=2)

        frm.pack()

        self.wait_window()
    
    def import_league(self):
        dialog = league_download.Dialog(self.master)
        if dialog.projection is not None:
            self.league = dialog.league
            self.destroy()
    
    def populate_table(self):
        for lg in self.league_list:
            self.league_list.insert('', tk.END, text=str(lg.index), values=(lg.ottoneu_id, lg.name, lg.format, lg.num_teams))
        self.league_list.treeview_sort_column(self.league_list.sort_col, self.league_list.reverse_sort)

    def on_select(self, event):
        selection = event.widget.item(event.widget.selection()[0])["text"]
        for lg in self.league_list:
            if lg.index == int(selection):
                self.league = league_services.get_league(lg.index)
                break

    def cancel(self):
        self.projection = None
        self.destroy()
    
    def set_projection(self):
        self.destroy()