import tkinter as tk     
from tkinter import *     
from tkinter.messagebox import CANCEL, OK 
from typing import Dict

from domain.domain import Draft, TeamDraft
from services import league_services, draft_services
from util import string_util

class Dialog(tk.Toplevel):

    def __init__(self, parent, draft:Draft):
        super().__init__(parent)
        self.draft = draft
        self.title('Set Custom Draft Budgets')
        frm = tk.Frame(self, borderwidth=4)

        tk.Label(frm, text = "Set Custom Draft Budgets for all teams", font='bold').grid(column=0,row=0, pady=5, sticky=tk.E)
        
        self.team_frm = tk.Frame(frm)
        self.team_frm.grid(row=1,column=0)

        tk.Label(self.team_frm, text='Team Name').grid(row=2, column=0)
        tk.Label(self.team_frm, text='Draft Budget (pre-Keeper)').grid(row=2, column=1)

        row = 3

        validation = self.team_frm.register(string_util.int_validation)

        self.team_id_to_budget:Dict[int, StringVar] = {}
        league = league_services.get_league_by_draft(self.draft, fill_rosters=True)
        for team in league.teams:
            found = False
            for td in self.draft.team_drafts:
                if td.team_id == team.id:
                    found = True
                    tk.Label(self.team_frm, text=team.name).grid(row=row, column=0)
                    budget = StringVar()
                    budget.set(td.custom_draft_budget)
                    entry = tk.Entry(self.team_frm, textvariable=budget, justify='center')
                    entry.config(validate="key", validatecommand=(validation, '%P'))
                    entry.grid(row=row, column=1)
                    self.team_id_to_budget[team.id] = budget
                    break
            if not found:
                td = TeamDraft(team_id=team.id)
                #draft.team_drafts.append(td)
                tk.Label(self.team_frm, text=team.name).grid(row=row, column=0)
                budget = StringVar()
                budget.set(league.team_salary_cap)
                entry = tk.Entry(self.team_frm, textvariable=budget, justify='center')
                entry.config(validate="key", validatecommand=(validation, '%P'))
                entry.grid(row=row, column=1)
                self.team_id_to_budget[team.id] = budget
            row += 1

        tk.Button(frm, text="OK", command=self.ok_click).grid(row=2, column=0)
        tk.Button(frm, text="Cancel", command=self.cancel_click).grid(row=2, column=1)

        self.status = CANCEL

        frm.pack()

        self.lift()
        self.focus_force()

        self.protocol("WM_DELETE_WINDOW", self.cancel_click)

        self.wait_window()
    
    def ok_click(self):
        team_drafts = []
        for key, val in self.team_id_to_budget.items():
            team_drafts.append(TeamDraft(team_id=key, custom_draft_budget=int(val.get())))
        self.draft = draft_services.update_team_drafts(self.draft.id, team_drafts)

        self.status = OK
        self.destroy()
    
    def cancel_click(self):
        self.draft = None
        self.status = CANCEL
        self.destroy()
