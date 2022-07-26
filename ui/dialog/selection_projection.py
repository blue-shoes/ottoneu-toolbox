import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from ui.table import Table

from services import projection_services

class Dialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.projection = None
        self.title("Select a Projection")
        frm = tk.Frame(self, borderwidth=4)

        tk.Label(frm, text="Select projection season: ").grid(row=0,column=0)
        self.season = tk.StringVar()
        season_cb = ttk.Combobox(frm, textvariable=self.season)
        seasons = projection_services.get_available_seasons()
        str_seasons = []
        for season in seasons:
            str_seasons.append(str(season))
        season_cb['values'] = str_seasons
        season_cb.grid(row=0,column=1)

        self.proj_list = projection_services.get_projections_for_year(seasons[0])


        cols = ('Name', 'Type', 'Detail', 'Timestamp','RoS?','DC PT?')
        align = {}
        align['Name'] = W
        align['Detail'] = W
        width = {}
        width['Detail'] = 100

        self.proj_table = pt = Table(frm, cols, align, width, cols)
        pt.grid(row=1, columnspan=2)
        pt.set_row_select_method(self.on_select)

        ttk.Button(frm, text="OK", command=self.set_projection).grid(row=3, column=0)
        ttk.Button(frm, text="Cancel", command=self.cancel).grid(row=3, column=1)

        frm.pack()

        self.wait_window()
    

    def on_select(self, event):
        selection = event.widget.item(event.widget.selection()[0])["text"]
        for proj in self.proj_list:
            if proj.index == int(selection):
                self.projection = proj
                break

    def cancel(self):
        self.projection = None
        self.destroy()
    
    def set_projection(self):
        self.destroy()