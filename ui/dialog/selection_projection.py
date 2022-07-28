import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from ui.table import Table, bool_to_table

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
        #seasons = projection_services.get_available_seasons()
        #str_seasons = []
        #for season in seasons:
        #    print(season)
        #    str_seasons.append(str(season))
        #print(seasons)
        #print(str_seasons)
        #season_cb['values'] = [str_seasons]
        season_cb['values'] = ['2022']
        season_cb.grid(row=0,column=1)
        #self.season.set(str_seasons[0])
        self.season.set('2022')
        season_cb.bind("<<ComboboxSelected>>", self.update_season)

        #self.proj_list = projection_services.get_projections_for_year(seasons[0])
        self.proj_list = projection_services.get_projections_for_year(2022)

        cols = ('Name', 'Type', 'Detail', 'Timestamp','RoS?','DC PT?')
        align = {}
        align['Name'] = W
        align['Detail'] = W
        width = {}
        width['Detail'] = 100

        self.proj_table = pt = Table(frm, cols, align, width, cols)
        pt.grid(row=1, columnspan=2)
        pt.set_row_select_method(self.on_select)
        pt.set_refresh_method(self.populate_table)

        self.populate_table()

        ttk.Button(frm, text="OK", command=self.set_projection).grid(row=3, column=0)
        ttk.Button(frm, text="Cancel", command=self.cancel).grid(row=3, column=1)

        frm.pack()

        self.wait_window()
    
    def update_season(self):
        self.proj_list = projection_services.get_projections_for_year(int(self.season.get()))
        self.proj_table.refresh()
    
    def populate_table(self):
        if self.proj_table.sort_col == "Name":
            sorted_proj = sorted(self.proj_list, key=lambda x: x.name)
        else:
            sorted_proj = sorted(self.proj_list, key=lambda x: x.timestamp, reverse=True)
        for proj in sorted_proj:
            self.proj_table.insert('', tk.END, text=id, values=(proj.name, proj.type, proj.detail, proj.timestamp, bool_to_table(proj.ros), bool_to_table(proj.dc_pt)), tags=('removed',))


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