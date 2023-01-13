import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import filedialog as fd
from domain.domain import ValueCalculation
from domain.enum import ScoringFormat, RankingBasis, CalculationDataType as CDT, Position, RepLevelScheme, IdType
from ui.dialog import progress, projection_select, proj_download
from ui.dialog.wizard import wizard
from services import calculation_services, projection_services
import pandas as pd
import datetime
import logging

from pathlib import Path
import os
import os.path

from util import string_util

class Dialog(wizard.Dialog):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        self.wizard = Wizard(self)
        self.wizard.pack()
        self.title('Import Player Values from File')
        self.value = None

        return self.wizard

class Wizard(wizard.Wizard):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.step1 = Step1(self)
        self.step2 = Step2(self)
        self.steps.append(self.step1)
        self.steps.append(self.step2)
        self.value = ValueCalculation()

        self.show_step(0)
    
    def cancel(self):
        self.value = None
        super().cancel()
    
    def finish(self):
        self.parent.validate_msg = None
        for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
            self.value.set_input(CDT.pos_to_rep_level()[pos], float(self.step2.pos_rep_lvl_sv[pos].get()))
            self.value.set_output(CDT.pos_to_rep_level()[pos], float(self.step2.pos_rep_lvl_sv[pos].get()))
        
        self.value.set_output(CDT.HITTER_DOLLAR_PER_FOM, float(self.step2.hit_dollars_per_fom_val.get()))
        self.value.set_output(CDT.PITCHER_DOLLAR_PER_FOM, float(self.step2.pitch_dollars_per_fom_val.get()))
        self.value.timestamp = datetime.datetime.now()
        self.value.index = None
        self.value.name = self.step1.name_tv.get()
        self.value.description = self.step1.desc_tv.get()
        self.value.set_input(CDT.REP_LEVEL_SCHEME, float(RepLevelScheme.STATIC_REP_LEVEL.value))
        pd = progress.ProgressDialog(self.master, title='Saving Values...')
        pd.set_task_title('Uploading')
        pd.set_completion_percent(15)
        self.value = calculation_services.save_calculation_from_file(self.value, self.step1.df, pd)
        pd.set_task_title("Updating")
        pd.set_completion_percent(80)
        self.parent.value = calculation_services.load_calculation(self.value.index)
        pd.complete()
        super().finish()

class Step1(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        header = tk.Label(self, text="Upload Value Set")
        header.grid(row=0, column=0, columnspan=3)

        validation = self.register(string_util.int_validation)

        tk.Label(self, text="Name:").grid(row=1, column=0, stick=W)
        self.name_tv = StringVar()
        tk.Entry(self, textvariable=self.name_tv).grid(row=1, column=1, sticky='we', columnspan=2)

        tk.Label(self, text="Description:").grid(row=2, column=0, stick=W)
        self.desc_tv = StringVar()
        tk.Entry(self, textvariable=self.desc_tv).grid(row=2, column=1, sticky='we', columnspan=2)

        file_label = ttk.Label(self, text = "Player Value File (csv):")
        file_label.grid(column=0,row=3, pady=5, stick=W)

        self.value_file = tk.StringVar()
        file_btn = ttk.Button(self, textvariable = self.value_file, command=self.select_value_file)
        file_btn.grid(column=1,row=3, padx=5, sticky='we', columnspan=2)
        self.value_file.set(Path.home())

        id_map = [IdType.OTTONEU.value, IdType.FANGRAPHS.value]
        ttk.Label(self, text="Player Id Type:").grid(column=0,row=4,pady=5, stick=W)
        self.id_type = StringVar()
        self.id_type.set(IdType.OTTONEU.value)
        id_combo = ttk.Combobox(self, textvariable=self.id_type)
        id_combo['values'] = id_map
        id_combo.grid(column=1,row=4,pady=5, columnspan=2)

        ttk.Label(self, text="Selected Projections:").grid(column=0,row=5, pady=5, stick=W)
        self.sel_proj = tk.StringVar()
        self.sel_proj.set("None")
        self.projection = None
        ttk.Button(self, textvariable=self.sel_proj, command=self.select_projection).grid(column=1,row=5, sticky='we', columnspan=2)
        #ttk.Button(self, text="Select...", command=self.select_projection).grid(column=2,row=5)

        gt_map = ScoringFormat.enum_to_full_name_map()
        ttk.Label(self, text="Game Type:").grid(column=0,row=6,pady=5, stick=W)
        self.game_type = StringVar()
        self.game_type.set(gt_map[ScoringFormat.FG_POINTS])
        gt_combo = ttk.Combobox(self, textvariable=self.game_type)
        gt_combo.bind("<<ComboboxSelected>>", self.update_game_type)
        # TODO: Don't hardcode game types, include other types

        gt_combo['values'] = (gt_map[ScoringFormat.FG_POINTS], gt_map[ScoringFormat.SABR_POINTS])
        gt_combo.grid(column=1,row=6,pady=5, columnspan=2)

        ttk.Label(self, text="Number of Teams:").grid(column=0, row=7,pady=5, stick=W)
        self.num_teams_str = StringVar()
        self.num_teams_str.set("12")
        team_entry = ttk.Entry(self, textvariable=self.num_teams_str)
        team_entry.grid(column=1,row=7,pady=5, sticky='we', columnspan=2)
        team_entry.config(validate="key", validatecommand=(validation, '%P'))

        ttk.Label(self, text="Hitter Value Basis:").grid(column=0,row=8,pady=5, stick=W)
        self.hitter_basis = StringVar()
        self.hitter_basis.set('P/G')
        self.hitter_basis_cb = hbcb = ttk.Combobox(self, textvariable=self.hitter_basis)
        hbcb['values'] = ('P/G','P/PA')
        hbcb.grid(column=1,row=8,pady=5)

        ttk.Label(self, text="Pitcher Value Basis:").grid(column=0,row=9,pady=5, stick=W)
        self.pitcher_basis = StringVar()
        self.pitcher_basis.set('P/IP')
        self.pitcher_basis_cb = pbcb = ttk.Combobox(self, textvariable=self.pitcher_basis)
        pbcb['values'] = ('P/IP','P/G')
        pbcb.grid(column=1,row=9,pady=5)

        ttk.Label(self, text="Replacement Level Value ($): ").grid(column=0, row=10,pady=5, stick=W)
        self.rep_level_value_str = StringVar()
        self.rep_level_value_str.set("1")
        rep_level_entry = ttk.Entry(self, textvariable=self.rep_level_value_str)
        rep_level_entry.grid(column=1,row=10,pady=5, sticky='we', columnspan=2)
        rep_level_entry.config(validate="key", validatecommand=(validation, '%P'))

    def select_value_file(self):
        filetypes = (
            ('csv files', '*.csv'),
            ('All files', '*.*')
        )

        title = 'Choose a player value file'
        if os.path.isfile(self.value_file.get()):
            init_dir = os.path.dirname(self.value_file.get())
        else:
            init_dir = self.value_file.get()

        file = fd.askopenfilename(
            title=title,
            initialdir=init_dir,
            filetypes=filetypes)

        self.value_file.set(file)

        self.parent.parent.lift()
        self.parent.parent.focus_force()

        return file
    
    def on_show(self):
        return True
    
    def validate(self):
        self.parent.validate_msg = ''

        try:
            self.df = df = pd.read_csv(self.value_file.get())
            self.parent.validate_msg = calculation_services.normalize_value_upload(df)
        except PermissionError:
            self.parent.validate_msg = f'Error loading values file. File permission denied.'
            return False
        except FileNotFoundError:
            self.parent.validate_msg = "Error loading values file. Values file not found."
            return False
        except Exception as Argument:
            self.parent.validate_msg = f'Error loading values file. See log file for details.'
            logging.exception('Error loading values file.')
            return False

        if len(self.parent.validate_msg) > 0:
            return False
        
        self.init_value_calc()

        return True
    
    def init_value_calc(self):
        prog = progress.ProgressDialog(self.parent, 'Initializing Value Set')
        vc = self.parent.value
        prog.set_task_title('Getting projections...')
        prog.set_completion_percent(15)
        vc.projection = projection_services.get_projection(self.projection.index, player_data=True)
        vc.format = ScoringFormat.name_to_enum_map()[self.game_type.get()]
        vc.inputs = []
        vc.set_input(CDT.NUM_TEAMS, float(self.num_teams_str.get()))
        vc.hitter_basis = RankingBasis.display_to_enum_map().get(self.hitter_basis.get())
        vc.pitcher_basis = RankingBasis.display_to_enum_map().get(self.pitcher_basis.get())
        vc = calculation_services.init_outputs_from_upload(vc, self.df, 
            ScoringFormat.name_to_enum_map()[self.game_type.get()], int(self.rep_level_value_str.get()), 
            IdType._value2member_map_.get(self.id_type.get()), prog)
        prog.complete()

    def select_projection(self):
        count = projection_services.get_projection_count()
        if count == 0:
            dialog = proj_download.Dialog(self)
            self.projection = dialog.projection
        else:
            dialog = projection_select.Dialog(self)
        if dialog.projection is not None:
            self.projection = dialog.projection
            self.sel_proj.set(self.projection.name)
        else:
            self.projection = None
            self.sel_proj.set("No Projection Selected")

    def update_game_type(self):
        i=1
        #TODO: Implement this

class Step2(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        header = tk.Label(self, text="Confirm Value Set")
        header.grid(row=0, column=0, columnspan=3)

        ttk.Label(self, text="Position", font='bold').grid(row=1, column=0)
        ttk.Label(self, text="# Rostered", font='bold').grid(row=1, column=1)
        self.bat_rep_level_lbl = StringVar()
        self.bat_rep_level_lbl.set("Rep. Level")
        ttk.Label(self, textvariable=self.bat_rep_level_lbl, font='bold').grid(row=1, column=2)

        row = 2
        self.pos_rostered_sv = {}
        self.pos_rep_lvl_sv = {}
        for pos in Position.get_discrete_offensive_pos():
            ttk.Label(self, text=pos.value).grid(row=row, column=0)
            pos_rep = StringVar()
            pos_rep.set("--")
            self.pos_rostered_sv[pos] = pos_rep
            ttk.Label(self, textvariable=pos_rep).grid(row=row, column=1)
            rep_lvl = StringVar()
            rep_lvl.set("--")
            self.pos_rep_lvl_sv[pos] = rep_lvl
            ttk.Entry(self, textvariable=rep_lvl).grid(row=row, column=2)
            row += 1
        
        self.hit_dollars_per_fom_lbl = StringVar()
        self.hit_dollars_per_fom_lbl.set('Calculated $/PAR')
        ttk.Label(self, textvariable=self.hit_dollars_per_fom_lbl).grid(row=row, column=0)

        self.hit_dollars_per_fom_val = StringVar()
        self.hit_dollars_per_fom_val.set('$--')
        ttk.Entry(self, textvariable=self.hit_dollars_per_fom_val).grid(row=row,column=1)

        row += 1
        
        ttk.Label(self, text="Position", font='bold').grid(row=row, column=0)
        ttk.Label(self, text="# Rostered", font='bold').grid(row=row, column=1)
        self.pitch_rep_level_lbl = StringVar()
        self.pitch_rep_level_lbl.set("Rep. Level")
        ttk.Label(self, textvariable=self.pitch_rep_level_lbl, font='bold').grid(row=row, column=2)

        row += 1

        for pos in Position.get_discrete_pitching_pos():

            ttk.Label(self, text=pos.value).grid(row=row, column=0)
            pos_rep = StringVar()
            pos_rep.set("--")
            self.pos_rostered_sv[pos] = pos_rep
            ttk.Label(self, textvariable=pos_rep).grid(row=row, column=1)
            rep_lvl = StringVar()
            rep_lvl.set("--")
            self.pos_rep_lvl_sv[pos] = rep_lvl
            ttk.Entry(self, textvariable=rep_lvl).grid(row=row, column=2)
            row += 1
        
        self.pitch_dollars_per_fom_lbl = StringVar()
        self.pitch_dollars_per_fom_lbl.set('Calculated $/PAR')
        ttk.Label(self, textvariable=self.pitch_dollars_per_fom_lbl).grid(row=row, column=0)

        self.pitch_dollars_per_fom_val = StringVar()
        self.pitch_dollars_per_fom_val.set('$--')
        ttk.Entry(self, textvariable=self.pitch_dollars_per_fom_val).grid(row=row,column=1)

    def on_show(self):
        vc = self.parent.value
        self.hit_dollars_per_fom_val.set("{:.3f}".format(vc.get_output(CDT.HITTER_DOLLAR_PER_FOM)))
        self.pitch_dollars_per_fom_val.set("{:.3f}".format(vc.get_output(CDT.PITCHER_DOLLAR_PER_FOM)))
        hitter_rb = RankingBasis.enum_to_display_dict()[vc.hitter_basis]
        self.bat_rep_level_lbl.set(f"Rep. Level ({hitter_rb})")
        pitcher_rb = RankingBasis.enum_to_display_dict()[vc.pitcher_basis]
        self.pitch_rep_level_lbl.set(f"Rep. Level ({pitcher_rb})")

        for pos in Position.get_discrete_offensive_pos():
            if pos != Position.POS_UTIL:   
                self.pos_rostered_sv[pos].set(int(vc.get_output(CDT.pos_to_num_rostered()[pos])))
            rl = vc.get_output(CDT.pos_to_rep_level()[pos])
            if rl is None:
                self.pos_rep_lvl_sv[pos].set("--")
            else:
                self.pos_rep_lvl_sv[pos].set("{:.2f}".format(rl))
        
        for pos in Position.get_discrete_pitching_pos():
            self.pos_rostered_sv[pos].set(int(vc.get_output(CDT.pos_to_num_rostered()[pos])))
            rl = vc.get_output(CDT.pos_to_rep_level()[pos])
            if rl is None:
                self.pos_rep_lvl_sv[pos].set("--")
            else:
                self.pos_rep_lvl_sv[pos].set("{:.2f}".format(rl))
        return True
    
    def validate(self):
        vc = self.parent.value

        return True