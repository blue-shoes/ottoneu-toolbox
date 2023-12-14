import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from domain.domain import League
from domain.enum import ScoringFormat, Platform
from services import league_services
from ui.dialog import progress
from ui.dialog.wizard import wizard, yahoo_setup
from ui.tool.tooltip import CreateToolTip
import logging
from tkinter import messagebox as mb
from tkinter.messagebox import CANCEL
import os

class Dialog(wizard.Dialog):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        self.wizard = Wizard(self)
        self.wizard.pack()
        self.title('Import League')
        self.league = None
        return self.wizard

class Wizard(wizard.Wizard):

    league:League

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
        if self.league.platform == Platform.YAHOO and self.league.is_salary_cap():
            self.league.team_salary_cap = float(self.step2.yahoo_salary.get())

        prog = progress.ProgressDialog(self, 'Saving League')
        prog.set_task_title('Saving league')
        prog.set_completion_percent(20)
        self.parent.league = league_services.save_league(self.league, pd=prog)
        prog.complete()
        super().finish()

class Step1(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        ttk.Label(self, text = 'League Platform').grid(column=0,row=0, pady=5, sticky=tk.E)
        self.platform = StringVar()
        self.platform.set(Platform.OTTONEU)
        cb = ttk.Combobox(self, textvariable=self.platform)
        cb['values'] = (Platform.OTTONEU.value, Platform.YAHOO.value)
        cb.grid(column=1,row=0, sticky=tk.W, padx=5)
        ttk.Label(self, text = "Enter League #:").grid(column=0,row=1, pady=5, sticky=tk.E)
        #width is in text units, not pixels
        self.league_num_entry = ttk.Entry(self, width = 10)
        self.league_num_entry.grid(column=1,row=1, sticky=tk.W, padx=5)

        CreateToolTip(self.league_num_entry, 'The league id (find it in the league URL)')

        self.pack()

    def on_show(self):
        return True
    
    def validate(self):
        pd = progress.ProgressDialog(self.master, title='Getting League')
        try:
            if self.platform.get() == Platform.OTTONEU:
                self.parent.league = league_services.create_ottoneu_league(self.league_num_entry.get(), pd)
            elif self.platform.get() == Platform.YAHOO:
                if not os.path.exists('conf/private.json'):
                    dialog = yahoo_setup.Dialog(self)
                    if dialog.status == CANCEL:
                        self.parent.validate_msg = 'Please enter a FanGraphs username and password to proceed'
                        mb.showerror('Download Error', 'Projections cannot be downloaded by the Toolbox without FanGraphs credentials')
                        return False
                self.parent.league = league_services.create_yahoo_league(self.league_num_entry.get(), pd)
            else:
                logging.exception(f'Error creating league for platform {self.platform.get()}')
                self.parent.validate_msg = f"The platform {self.platform.get()} is not implemented."
                return False

        except Exception as Argument:
            logging.exception(f'Error creating league #{self.league_num_entry.get()}')
            self.parent.validate_msg = f"There was an error downloading league number {self.league_num_entry.get()}. Please confirm this is the correct league."
            return False
        finally:
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

        ttk.Label(self, text="User's Team", font='bold').grid(column=0, row=2,sticky=tk.E, pady=5)
        self.users_team_name = StringVar()
        self.users_team_name.set('None Selected')
        self.users_team_cb = utcb = ttk.Combobox(self, textvariable=self.users_team_name)
        CreateToolTip(self.users_team_cb, "Select the user's team in the league to enable additional functionality.")
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

        self.yahoo_frame = ttk.Frame(self)
        self.yahoo_frame.grid(row=5, column=0, columnspan=2)

        self.yahoo_salary_frame = ysf = ttk.Frame(self.yahoo_frame)
        ysf.grid(row=0, column=0)
        ttk.Label(ysf, text='Team Salary Cap', font='bold').grid(row=0, column=0)
        self.yahoo_salary = ys = StringVar()
        ys.set('260')
        ttk.Entry(ysf, textvariable=ys).grid(row=0, column = 1)

    def on_show(self):
        lg = self.parent.league
        self.lg_name_sv.set(lg.name)
        self.num_teams_sv.set(lg.num_teams)
        self.format_sv.set(lg.format.full_name)
        if lg.platform == Platform.YAHOO:
            if lg.is_salary_cap():
                self.yahoo_salary_frame.grid(row=5, column=0, columnspan=2)
            else:
                self.yahoo_salary_frame.grid_forget()
        else:
            self.yahoo_salary_frame.grid_forget()
        teams = []
        for team in lg.teams:
            teams.append(team.name)
        self.users_team_cb['values'] = teams
        return True
