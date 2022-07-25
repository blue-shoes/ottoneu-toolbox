from itertools import islice
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import filedialog as fd
from tkinter import messagebox as mb

from services import projection_services
from domain.enum import ProjectionType
from pathlib import Path
import os
import os.path

class Dialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.projection = None
        self.title("Import a Projection")
        frm = tk.Frame(self, borderwidth=4)

        tk.Label(frm, text="Source", font="bold").grid(column=0, row=0)
        self.source_var = tk.BooleanVar()
        
        tk.Radiobutton(frm, text="FanGraphs", value=True, variable=self.source_var, command=self.toggle_fg_proj).grid(column=1,row=0)
        tk.Radiobutton(frm, text="Custom",value=False,variable=self.source_var, command=self.toggle_custom_proj).grid(column=2,row=0)
        self.source_var.set(True)

        self.fg_frm = tk.Frame(frm, borderwidth=4)
        self.fg_frm.grid(row=1,column=0,columnspan=3)
        tk.Label(self.fg_frm , text="Projection Type:", font="bold").grid(column=0,row=0)
        
        downloadable = []
        for proj in islice(ProjectionType, 6):
            downloadable.append(ProjectionType.enum_to_name_dict().get(proj))
        
        self.proj_type = tk.StringVar()
        self.proj_type.set('Steamer')
        proj_cb = ttk.Combobox(self.fg_frm , textvariable=self.proj_type)
        proj_cb['values'] = downloadable
        proj_cb.grid(column=1, row=0)

        self.dc_var = tk.BooleanVar()
        self.dc_var.set(False)
        ttk.Checkbutton(self.fg_frm, text="DC Playing Time?", variable=self.dc_var).grid(column=1,row=1)

        self.ros_var = tk.BooleanVar()
        self.ros_var.set(False)
        ttk.Checkbutton(self.fg_frm, text="RoS Projection?", variable=self.ros_var).grid(column=1,row=2)

        self.custom_frm = tk.Frame(frm, borderwidth=4)
        self.custom_frm.grid(row=2,column=0,columnspan=3)

        ttk.Label(self.custom_frm, text = "Hitter Projections File (csv):").grid(column=0,row=0, pady=5, stick=tk.E)
        self.hitter_proj_file = tk.StringVar()
        ttk.Button(self.custom_frm, textvariable = self.hitter_proj_file, command=self.select_hitter_proj_file).grid(column=1,row=0, padx=5)
        self.hitter_proj_file.set(Path.home())

        ttk.Label(self.custom_frm, text = "Pitcher Projections File (csv):").grid(column=0,row=1, pady=5, stick=tk.E)
        self.pitcher_proj_file = tk.StringVar()
        ttk.Button(self.custom_frm, textvariable = self.pitcher_proj_file, command=self.select_pitcher_proj_file).grid(column=1,row=1, padx=5)
        self.pitcher_proj_file.set(Path.home())

        ttk.Button(frm, text="OK", command=self.populate_projection).grid(row=3, column=0)
        ttk.Button(frm, text="Cancel", command=self.cancel).grid(row=3, column=1)

        frm.pack()

        self.wait_window()

    def toggle_fg_proj(self):
        for child in self.fg_frm.winfo_children():
            child.configure(state='active')
        for child in self.custom_frm.winfo_children():
            child.configure(state='disable')
    
    def toggle_custom_proj(self):
        for child in self.fg_frm.winfo_children():
            child.configure(state='disable')
        for child in self.custom_frm.winfo_children():
            child.configure(state='active')
    
    def select_hitter_proj_file(self):
        self.hitter_proj_file.set(self.select_projection_file('Choose a hitter projection file'))
    
    def select_pitcher_proj_file(self):
        self.pitcher_proj_file.set(self.select_projection_file('Choose a pitcher projection file'))

    def select_projection_file(self, title):
        filetypes = (
            ('csv files', '*.csv'),
            ('All files', '*.*')
        )

        if os.path.isfile(self.hitter_proj_file):
            init_dir = os.path.dirname(self.hitter_proj_file.get())
        else:
            init_dir = self.hitter_proj_file.get()

        file = fd.askopenfilename(
            title=title,
            initialdir=init_dir)

        #TODO: perform file validation here

        return file
    
    def cancel(self):
        self.destroy()
    
    def populate_projection(self):
        #TODO: Wrap in progress dialog
        if self.source_var.get():
            #Download proj from FG
            self.projection = projection_services.create_projection_from_download(ProjectionType.name_to_enum_dict().get(self.proj_type.get()), self.ros_var.get(), self.dc_var.get())
        else:
            #Upload proj from files
            #TODO: need user entry of name/desc and indicate it's RoS
            self.projection = projection_services.create_projection_from_upload(self.hitter_proj_file, self.pitcher_proj_file, name="User Custom")
        self.destroy()