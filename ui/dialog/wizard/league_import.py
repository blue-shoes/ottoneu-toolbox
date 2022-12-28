import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from domain.enum import ScoringFormat
from services import league_services
from ui.dialog import progress
from ui.dialog.wizard import wizard
import logging
from tkinter import messagebox as mb

from pathlib import Path
import os
import os.path

class Dialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Import League')
        self.league = None

        self.wizard = Wizard(self)

        self.wizard.pack()

        self.protocol("WM_DELETE_WINDOW", self.wizard.cancel)

        self.wait_window()

class Wizard(wizard.Wizard):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.step1 = Step1(self)
        self.step2 = Step2(self)
        self.steps.append(self.step1)
        self.steps.append(self.step2)
        self.league = None

        self.show_step(0)
    
    def cancel(self):
        self.league = None
        super().cancel()
    
    def finish(self):
        self.parent.validate_msg = None
        if self.step2.users_team_name.get() == 'None Selected':
            if not mb.askokcancel('No User Team Selected', 'The user did not select their team in this league. Do you wish to continue?'):
                return False
        for team in self.league.teams:
            if team.name == self.step2.users_team_name.get():
                team.users_team = True
            else:
                team.users_team = False
        self.parent.league = league_services.save_league(self.league)
        super().finish()

class Step1(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        ttk.Label(self, text = "Enter League #:").grid(column=0,row=0, pady=5, sticky=tk.E)
        #width is in text units, not pixels
        self.league_num_entry = ttk.Entry(self, width = 10)
        self.league_num_entry.grid(column=1,row=0, sticky=tk.W, padx=5)

        self.pack()

    def on_show(self):
        return True
    
    def validate(self):
        pd = progress.ProgressDialog(self.master, title='Getting League')
        try:
            self.parent.league = league_services.create_league(self.league_num_entry.get(), pd)
        except Exception as e:
            logging.error(f'Error creating league #{self.league_num_entry.get()}')
            logging.error(e.with_traceback())
            self.parent.validate_msg = f"There was an error downloading league number {self.league_num_entry.get()}. Please confirm this is the correct league."
            return False
        pd.complete()
        return True

class Step2(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        header = tk.Label(self, text="Confirm League")
        header.grid(row=0, column=0, columnspan=3)

        ttk.Label(self, text = "League Name", font='bold').grid(column=0,row=1, pady=5, sticky=tk.E)
        self.lg_name_sv = StringVar()
        self.lg_name_sv.set('--')
        ttk.Label(self, textvariable=self.lg_name_sv).grid(column=1, row=1, pady=5, sticky=tk.W)

        ttk.Label(self, text="Users Team", font='bold').grid(column=0, row=2,sticky=tk.E, pady=5)
        self.users_team_name = StringVar()
        self.users_team_name.set('None Selected')
        self.users_team_cb = utcb = ttk.Combobox(self, textvariable=self.users_team_name)
        utcb['values'] = ('None Available')
        utcb.grid(column=1,row=2,pady=5)

        ttk.Label(self, text = "Number of Teams", font='bold').grid(column=0,row=3, pady=5, sticky=tk.E)
        self.num_teams_sv = StringVar()
        self.num_teams_sv.set('--')
        ttk.Label(self, textvariable=self.num_teams_sv).grid(column=1, row=3, pady=5, sticky=tk.W)

        ttk.Label(self, text = "Scoring Format", font='bold').grid(column=0,row=4, pady=5, sticky=tk.E)
        self.format_sv = StringVar()
        self.format_sv.set('--')
        ttk.Label(self, textvariable=self.format_sv).grid(column=1, row=4, pady=5, sticky=tk.W)

    def on_show(self):
        lg = self.parent.league
        self.lg_name_sv.set(lg.name)
        self.num_teams_sv.set(lg.num_teams)
        self.format_sv.set(ScoringFormat.enum_to_full_name_map().get(lg.format))
        teams = []
        for team in lg.teams:
            teams.append(team.name)
        self.users_team_cb['values'] = teams
        return True
