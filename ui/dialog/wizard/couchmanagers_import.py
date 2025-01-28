import tkinter as tk
from tkinter import StringVar
from tkinter import ttk
from tkinter import messagebox as mb
from typing import Dict

from domain.domain import Draft, CouchManagers_Draft, CouchManagers_Team
from scrape.exceptions import CouchManagersException
from services import draft_services, league_services
from ui.dialog import progress
from ui.dialog.wizard import wizard


class Dialog(wizard.Dialog):
    def __init__(self, parent, draft: Draft):
        self.draft = draft
        super().__init__(parent)

    def setup(self):
        self.wizard = Wizard(self)
        self.wizard.pack()
        self.title('Import CouchManagers Draft')
        return self.wizard


class Wizard(wizard.Wizard):
    parent: Dialog
    cm_draft: CouchManagers_Draft

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.step1 = Step1(self)
        self.step2 = Step2(self)
        self.steps.append(self.step1)
        self.steps.append(self.step2)
        self.draft = self.parent.draft
        self.cm_draft = None

        self.show_step(0)

    def cancel(self):
        self.parent.draft = None
        super().cancel()

    def finish(self):
        self.validate_msg = None
        assigned_names = []
        for team in self.cm_draft.teams:
            name = self.step2.team_sv_dict[team].get()
            if name in assigned_names:
                self.validate_msg = 'Ottoneu Team names used more than once. Please recheck.'
                break
            assigned_names.append(name)
            team.ottoneu_team_id = self.step2.o_team_map.get(name)
        if self.validate_msg is None or len(self.validate_msg) == 0:
            self.parent.draft = draft_services.add_couchmanagers_draft(self.parent.draft, self.cm_draft)
        super().finish()


class Step1(tk.Frame):
    parent: Wizard

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        ttk.Label(self, text='Enter CouchManagers Draft #:').grid(column=0, row=0, pady=5, sticky=tk.E)
        # width is in text units, not pixels
        self.league_num_entry = ttk.Entry(self, width=10)
        self.league_num_entry.grid(column=1, row=0, sticky=tk.W, padx=5)

    def on_show(self):
        return True

    def validate(self):
        pd = progress.ProgressDialog(self.master, title='Getting Slow Draft...')
        pd.set_completion_percent(10)
        try:
            teams = draft_services.get_couchmanagers_teams(self.league_num_entry.get())
            self.parent.cm_draft = cm_draft = CouchManagers_Draft()
            cm_draft.cm_draft_id = int(self.league_num_entry.get())
            cm_draft.teams = []
            cm_draft.setup = True
            for team in teams:
                if len(team[1]) == 0:
                    # Team not claimed yet
                    cm_draft.setup = False
                    continue
                cm_team = CouchManagers_Team()
                cm_team.cm_team_id = team[0]
                cm_team.cm_team_name = team[1]
                cm_draft.teams.append(cm_team)
        except CouchManagersException:
            mb.showerror(f'The CouchManagers draft {self.league_num_entry.get()} does not exist')
            return False
        finally:
            pd.complete()

        return True


class Step2(tk.Frame):
    parent: Wizard
    team_sv_dict: Dict[CouchManagers_Draft, str]

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        ttk.Label(self, text='Link CouchManager Teams to Ottoneu', font='bold').grid(column=0, row=0, pady=5, sticky=tk.E)

        self.team_frm = ttk.Frame(self)
        self.team_frm.grid(row=1, column=0)

    def on_show(self):
        for item in self.team_frm.winfo_children():
            item.destroy()
        o_team_names = []
        self.o_team_map = {}
        league = league_services.get_league_by_draft(self.parent.draft, fill_rosters=True)
        for team in league.teams:
            o_team_names.append(team.name)
            self.o_team_map[team.name] = team.id
        self.team_sv_dict = {}
        row = 0
        ttk.Label(self.team_frm, text='CM Team Name').grid(row=row, column=0)
        ttk.Label(self.team_frm, text='Ottoneu Team Name').grid(row=row, column=1)
        row = row + 1
        for team in self.parent.cm_draft.teams:
            ttk.Label(self.team_frm, text=team.cm_team_name).grid(row=row, column=0)
            self.team_sv_dict[team] = sv = StringVar()
            sv.set(o_team_names[row - 1])
            cb = ttk.Combobox(self.team_frm, textvariable=sv)
            cb['values'] = o_team_names
            cb.grid(row=row, column=1)
            row = row + 1

        self.pack()

        return True
