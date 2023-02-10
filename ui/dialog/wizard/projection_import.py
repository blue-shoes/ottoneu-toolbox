import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import filedialog as fd
from tkinter import messagebox as mb
from tkinter.messagebox import CANCEL
from tkinter import font
from itertools import islice
import logging
from pathlib import Path
import os
import os.path

from domain.domain import Projection
from domain.enum import ProjectionType, IdType
from domain.exception import InputException
from scrape.exceptions import FangraphsException
from services import projection_services, player_services
from ui.dialog import progress, fg_login
from ui.dialog.wizard import wizard
from util import date_util, string_util

class Dialog(wizard.Dialog):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        self.wizard = Wizard(self)
        self.wizard.pack()
        self.title('Import Projection')
        self.projection = None
        self.deleted_proj_ids = []
        return self.wizard

class Wizard(wizard.Wizard):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.step1 = Step1(self)
        self.step2 = Step2(self)
        self.steps.append(self.step1)
        self.steps.append(self.step2)
        self.projection = Projection()

        self.show_step(0)
    
    def cancel(self):
        self.projection = None
        super().cancel()
    
    def finish(self):
        self.parent.validate_msg = None
        self.projection.name = self.step2.name_tv.get()
        self.projection.detail = self.step2.desc_text.get("1.0",'end-1c')
        pd = progress.ProgressDialog(self.master, title='Saving Values...')
        pd.set_task_title('Uploading')
        pd.set_completion_percent(15)
        if self.step1.source_var.get():
            id_type = IdType.FANGRAPHS
        else:
            id_type = IdType._value2member_map_.get(self.step1.id_type.get())
        self.parent.projection = projection_services.save_projection(self.projection, [self.step1.hitter_df, self.step1.pitcher_df],id_type,pd)
        pd.complete()
        super().finish()

class Step1(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        header = tk.Label(self, text="Upload Value Set")
        header.grid(row=0, column=0, columnspan=3)

        tk.Label(self, text="Source", font="bold").grid(column=0, row=1)
        self.source_var = tk.BooleanVar()
        
        tk.Radiobutton(self, text="FanGraphs", value=True, variable=self.source_var, command=self.toggle_fg_proj).grid(column=1,row=1)
        tk.Radiobutton(self, text="Custom",value=False,variable=self.source_var, command=self.toggle_custom_proj).grid(column=2,row=1)
        self.source_var.set(True)

        self.fg_self = tk.Frame(self, borderwidth=4)
        self.fg_self.grid(row=2,column=0,columnspan=3)
        tk.Label(self.fg_self , text="Projection Type:", font="bold").grid(column=0,row=0)
        
        downloadable = []
        for proj in islice(ProjectionType, 6):
            downloadable.append(ProjectionType.enum_to_name_dict().get(proj))
        
        self.proj_type = tk.StringVar()
        self.proj_type.set('Steamer')
        proj_cb = ttk.Combobox(self.fg_self , textvariable=self.proj_type)
        proj_cb['values'] = downloadable
        proj_cb.grid(column=1, row=0)

        self.dc_var = tk.BooleanVar()
        self.dc_var.set(False)
        ttk.Checkbutton(self.fg_self, text="DC Playing Time?", variable=self.dc_var).grid(column=1,row=1)

        self.ros_var = tk.BooleanVar()
        self.ros_var.set(False)
        ttk.Checkbutton(self.fg_self, text="RoS Projection?", variable=self.ros_var).grid(column=1,row=2)

        self.custom_self = tk.Frame(self, borderwidth=4)
        self.custom_self.grid(row=3,column=0,columnspan=3)

        id_map = [IdType.OTTONEU.value, IdType.FANGRAPHS.value]
        id_label = ttk.Label(self.custom_self, text="Player Id Type:")
        id_label.grid(column=0,row=0,pady=5, stick=W)
        id_label.configure(state='disabled')
        self.id_type = StringVar()
        self.id_type.set(IdType.FANGRAPHS.value)
        id_combo = ttk.Combobox(self.custom_self, textvariable=self.id_type)
        id_combo['values'] = id_map
        id_combo.grid(column=1,row=0,pady=5, columnspan=2)
        id_combo.configure(state='disabled')

        hitter_label = ttk.Label(self.custom_self, text = "Hitter Projections File (csv):")
        hitter_label.grid(column=0,row=1, pady=5, stick=tk.E)
        hitter_label.configure(state='disable')

        self.hitter_proj_file = tk.StringVar()
        hitter_btn = ttk.Button(self.custom_self, textvariable = self.hitter_proj_file, command=self.select_hitter_proj_file)
        hitter_btn.grid(column=1,row=1, padx=5)
        hitter_btn.configure(state='disable')
        self.hitter_proj_file.set(Path.home())

        pitcher_label = ttk.Label(self.custom_self, text = "Pitcher Projections File (csv):")
        pitcher_label.grid(column=0,row=2, pady=5, stick=tk.E)
        pitcher_label.configure(state='disable')
        self.pitcher_proj_file = tk.StringVar()
        pitcher_btn = ttk.Button(self.custom_self, textvariable = self.pitcher_proj_file, command=self.select_pitcher_proj_file)
        pitcher_btn.grid(column=1,row=2, padx=5)
        pitcher_btn.configure(state='disable')
        self.pitcher_proj_file.set(Path.home())

    def toggle_fg_proj(self):
        for child in self.fg_self.winfo_children():
            child.configure(state='active')
        for child in self.custom_self.winfo_children():
            child.configure(state='disable')
    
    def toggle_custom_proj(self):
        for child in self.fg_self.winfo_children():
            child.configure(state='disable')
        for child in self.custom_self.winfo_children():
            child.configure(state='active')
    
    def select_hitter_proj_file(self):
        self.hitter_proj_file.set(self.select_projection_file(True))
    
    def select_pitcher_proj_file(self):
        self.pitcher_proj_file.set(self.select_projection_file(False))

    def select_projection_file(self, batting):
        filetypes = (
            ('csv files', '*.csv'),
            ('All files', '*.*')
        )

        if batting:
            title = 'Choose a hitter projection file'
            if os.path.isfile(self.hitter_proj_file.get()):
                init_dir = os.path.dirname(self.hitter_proj_file.get())
            else:
                init_dir = self.hitter_proj_file.get()
        else:
            title = 'Choose a pitcher projection file'
            if os.path.isfile(self.pitcher_proj_file.get()):
                init_dir = os.path.dirname(self.pitcher_proj_file.get())
            else:
                init_dir = self.pitcher_proj_file.get()

        file = fd.askopenfilename(
            title=title,
            initialdir=init_dir,
            filetypes=filetypes)

        self.parent.lift()
        self.parent.focus_force()

        return file

    def on_show(self):
        return True
    
    def validate(self):
        if not os.path.exists('conf/fangraphs.conf'):
            dialog = fg_login.Dialog(self)
            if dialog.status == CANCEL:
                self.parent.validate_msg = 'Please enter a FanGraphs username and password to proceed'
                mb.showerror('Download Error', 'Projections cannot be downloaded by the Toolbox without FanGraph credentials')
                return False
        self.parent.projection = Projection()
        pd = progress.ProgressDialog(self.master, title='Getting Projection Set')
        year = date_util.get_current_ottoneu_year()
        try:
            if self.source_var.get():
                #Download proj from FG
                self.hitter_df, self.pitcher_df = projection_services.create_projection_from_download(self.parent.projection, ProjectionType.name_to_enum_dict().get(self.proj_type.get()), self.ros_var.get(), self.dc_var.get(), year=year, progress=pd)
            else:
                #Upload proj from files
                self.hitter_df, self.pitcher_df =  projection_services.create_projection_from_upload(self.parent.projection, self.hitter_proj_file.get(), self.pitcher_proj_file.get(), name="User Custom", year=year, progress=pd)
                if 'NAME' in self.hitter_df:
                    found_player = False
                    idx = 0
                    player = None
                    while not found_player and idx < len(self.hitter_df):                        
                        id = list(self.hitter_df.index.values)[idx]
                        if self.id_type.get() == IdType.FANGRAPHS.value:
                            player = player_services.get_player_by_fg_id(id)
                        elif self.id_type.get() == IdType.OTTONEU.value:
                            player = player_services.get_player_by_ottoneu_id(id)
                        found_player = player is not None
                        idx = idx + 1
                    if player is None:
                        raise InputException(f'The input IdType {self.id_type.get()} appears wrong for this projection set.')
                    df_name = string_util.normalize(self.hitter_df.at[id, 'NAME'])
                    if df_name != player.search_name:
                        raise InputException(f'The input IdType {self.id_type.get()} appears wrong for this projection set.')
        except FangraphsException as e:
            self.parent.projection = None
            self.parent.validate_msg = e.validation_msgs
            #mb.showerror('Error retrieving projection',  )
            #self.parent.lift()
            #self.parent.focus_force()
            return False
        except InputException as e:
            self.parent.projection = None
            self.parent.validate_msg = e.validation_msgs
            #mb.showerror('Error uploading projections', f'{e.args[0]}\n{msgs}')
            #self.parent.lift()
            #self.parent.focus_force()
            return False
        except Exception as Argument:
            self.parent.projection = None
            logging.exception("Error retrieving projections")
            self.parent.validate_msg = 'Error retrieving projection. See log file for details.'
            #mb.showerror('Error retrieving projection', 'See log file for details.')
            #self.parent.lift()
            #self.parent.focus_force()
            return False
        finally:
            pd.complete()
        
        return True

class Step2(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        header = tk.Label(self, text="Confirm Projection Set")
        header.grid(row=0, column=0, columnspan=2)

        tk.Label(self, text="Name").grid(row=1, column=0, sticky=tk.E)
        self.name_tv = StringVar()
        self.name_tv.set('Projection')
        tk.Entry(self, textvariable=self.name_tv, width=50).grid(row=1, column=1, sticky='we')

        tk.Label(self, text="Description").grid(row=2, column=0, sticky=tk.E)
        df_font = font.nametofont("TkDefaultFont")
        self.desc_text = tk.Text(self, width=50, height=3)
        self.desc_text.grid(row=2, column=1, pady=5)
        self.desc_text.configure(font = df_font)


        tk.Label(self, text="Points Compatible").grid(row=3, column=0, sticky=tk.E)
        self.points_var = tk.BooleanVar()
        self.points_var.set(False)
        ttk.Checkbutton(self, variable=self.points_var, command=lambda: self.points_var.set(~self.points_var.get())).grid(column=1,row=3, sticky=tk.W)

        tk.Label(self, text="5x5 Compatible").grid(row=4, column=0, sticky=tk.E)
        self.cats5_var = tk.BooleanVar()
        self.cats5_var.set(False)
        ttk.Checkbutton(self, variable=self.cats5_var, command=lambda: self.cats5_var.set(~self.cats5_var.get())).grid(column=1,row=4, sticky=tk.W)

        tk.Label(self, text="4x4 Compatible").grid(row=5, column=0, sticky=tk.E)
        self.cats4_var = tk.BooleanVar()
        self.cats4_var.set(False)
        ttk.Checkbutton(self, variable=self.cats4_var, command=lambda: self.cats4_var.set(~self.cats4_var.get())).grid(column=1,row=5, sticky=tk.W)

    def validate(self):
        return True
    
    def on_show(self):
        self.name_tv.set(self.parent.projection.name)
        self.points_var.set(self.parent.projection.valid_points)
        self.cats5_var.set(self.parent.projection.valid_5x5)
        self.cats4_var.set(self.parent.projection.valid_4x4)
        return True
