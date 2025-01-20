import tkinter as tk     
from tkinter import *     
from tkinter import ttk 
from tkinter import messagebox as mb
from tkinter.messagebox import CANCEL, OK 
from typing import List, Tuple

from domain.domain import Draft, CouchManagers_Team
from services import league_services, draft_services

class Dialog(tk.Toplevel):

    def __init__(self, parent, draft:Draft, new_teams:List[Tuple[int, str]]):
        super().__init__(parent)
        self.draft = draft
        self.new_teams = new_teams
        self.title('Import CouchManagers Draft')
        frm = tk.Frame(self, borderwidth=4)

        tk.Label(frm, text = "Link CouchManager Teams to Ottoneu", font='bold').grid(column=0,row=0, pady=5, sticky=tk.E)
        
        self.team_frm = tk.Frame(frm)
        self.team_frm.grid(row=1,column=0)

        o_team_names = []
        self.o_team_map = {}
        league = league_services.get_league_by_draft(self.draft, fill_rosters=True)
        for team in league.teams:
            found = False
            for team2 in self.draft.cm_draft.teams:
                if team2.ottoneu_team_id == team.id:
                    found = True
                    break
            if not found:
                o_team_names.append(team.name)
                self.o_team_map[team.name] = team.id
        self.team_sv_dict = {}
        row = 0
        tk.Label(self.team_frm, text='CM Team Name').grid(row=row, column=0)
        tk.Label(self.team_frm, text='Ottoneu Team Name').grid(row=row, column=1)
        row=row+1
        self.draft.cm_draft.setup = True
        for team in new_teams:
            if team[1] == '':
                self.draft.cm_draft.setup = False
                continue
            tk.Label(self.team_frm, text=team[1]).grid(row=row, column=0)
            self.team_sv_dict[team[0]] = sv = StringVar()
            sv.set(o_team_names[row-1])
            cb = ttk.Combobox(self.team_frm, textvariable=sv)
            cb['values'] = o_team_names
            cb.grid(row=row, column=1)
            row = row+1

        tk.Button(frm, text="OK", command=self.ok_click).grid(row=2, column=0)
        tk.Button(frm, text="Cancel", command=self.cancel_click).grid(row=2, column=1)

        self.status = CANCEL

        frm.pack()

        self.lift()
        self.focus_force()

        self.protocol("WM_DELETE_WINDOW", self.cancel_click)

        self.wait_window()
    
    def ok_click(self):
        assigned_names = []
        new_teams = []
        for key, val in self.team_sv_dict.items():
            name = val.get()
            if name in assigned_names:
                mb.showerror("Team assignment error", 'Ottoneu Team names used more than once. Please recheck.')
                return
            assigned_names.append(name)
            for team2 in self.draft.cm_draft.teams:
                if team2.ottoneu_team_id == name:
                    mb.showerror("Team assignment error", 'Ottoneu Team names used more than once. Please recheck.')
                    return
            cm_team = CouchManagers_Team()
            cm_team.cm_team_id = key
            for new_team in self.new_teams:
                if new_team[0] == key:
                    cm_team.cm_team_name = new_team[1]
                    break
            cm_team.ottoneu_team_id = self.o_team_map.get(name)
            new_teams.append(cm_team)
        self.draft.cm_draft = draft_services.update_couchmanger_teams(self.draft.cm_draft.id, new_teams, self.draft.cm_draft.setup)

        self.status = OK
        self.destroy()
    
    def cancel_click(self):
        self.status = CANCEL
        self.destroy()
