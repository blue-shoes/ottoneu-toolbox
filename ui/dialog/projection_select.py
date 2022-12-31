import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from ui.dialog import proj_download
from ui.table import Table, bool_to_table
from domain.enum import ProjectionType

from services import projection_services

class Dialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.projection = None
        self.title("Select a Projection")
        frm = tk.Frame(self, borderwidth=4)

        top_frm = tk.Frame(frm)
        top_frm.grid(row=0, sticky=tk.E)

        tk.Label(top_frm, text="Select projection season: ").grid(row=0,column=0)
        self.season = tk.StringVar()
        season_cb = ttk.Combobox(top_frm, textvariable=self.season)
        seasons = projection_services.get_available_seasons()
        str_seasons = []
        for season in seasons:
            str_seasons.append(str(season))
        season_cb['values'] = str_seasons
        season_cb.grid(row=0,column=1)
        self.season.set(str_seasons[0])
        season_cb.bind("<<ComboboxSelected>>", self.update_season)

        self.proj_list = projection_services.get_projections_for_year(seasons[0])

        cols = ('Name', 'Detail', 'Type', 'Timestamp','RoS?','DC PT?')
        align = {}
        align['Name'] = W
        align['Detail'] = W
        width = {}
        width['Name'] = 150
        width['Type']= 70
        width['Detail'] = 250
        width['Timestamp'] = 70

        self.proj_table = pt = Table(frm, cols, align, width, cols)
        pt.grid(row=1)
        pt.set_row_select_method(self.on_select)
        pt.set_refresh_method(self.populate_table)
        pt.set_double_click_method(self.double_click)

        self.populate_table()

        bot_frm = tk.Frame(frm)
        bot_frm.grid(row=2, sticky=tk.E)

        ttk.Button(bot_frm, text="OK", command=self.set_projection).grid(row=0, column=0)
        ttk.Button(bot_frm, text="Cancel", command=self.cancel).grid(row=0, column=1)
        ttk.Button(bot_frm, text="Import New...", command=self.import_projection).grid(row=0,column=2)

        frm.pack()

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.focus_force()

        self.wait_window()
    
    def import_projection(self):
        dialog = proj_download.Dialog(self.master)
        if dialog.projection is not None:
            self.projection = dialog.projection
            self.destroy()
        else:
            self.lift()

    def update_season(self):
        self.proj_list = projection_services.get_projections_for_year(int(self.season.get()))
        self.proj_table.refresh()
    
    def populate_table(self):
        for proj in self.proj_list:
            self.proj_table.insert('', tk.END, text=str(proj.index), values=(proj.name, proj.detail, ProjectionType.enum_to_name_dict().get(proj.type), proj.timestamp, bool_to_table(proj.ros), bool_to_table(proj.dc_pt)))

    def double_click(self, event):
        self.on_select(event)
        self.set_projection()

    def on_select(self, event):
        selection = event.widget.item(event.widget.selection()[0])["text"]
        for proj in self.proj_list:
            if proj.index == int(selection):
                self.projection = projection_services.get_projection(proj_id=proj.index, player_data=False)
                break

    def cancel(self):
        self.projection = None
        self.destroy()
    
    def set_projection(self):
        self.destroy()