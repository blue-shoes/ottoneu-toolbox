import tkinter as tk
from tkinter import *              
from tkinter import ttk 

from domain.domain import League, ValueCalculation
from services import league_services
from ui.table import Table

class Standings(tk.Frame):

    _inflation:float = 0
    league:League
    value_calc:ValueCalculation
    
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        self.fill_pt = BooleanVar()
        self.fill_pt.set(False)

        self.create_view()
    
    def create_view(self):
        self.tab_control = ttk.Notebook(self, width=570, height=300)
        self.tab_control.grid(row=0, column=0)

        standings_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(standings_frame, text='Standings')

        cols = ('Rank','Team','Points')
        widths = {}
        widths['Team'] = 125
        align = {}
        align['Team'] = W
        self.standings_table = st = Table(standings_frame, cols,sortable_columns=cols,reverse_col_sort=cols, column_widths=widths, init_sort_col='Rank', column_alignments=align)
        st.grid(column=0)
        st.tag_configure('users', background='#FCE19D')
        st.add_scrollbar()
        st.set_refresh_method(self.refresh_standings)
    
    def refresh_standings(self):
        league_services.calculate_league_table(self.league, self.value_calc, self.fill_pt.get(), self._inflation)
        for team in self.league.teams:
            tags = ''
            if team.users_team:
                tags=('users',)
            self.standings_table.insert('', tk.END, text=team.site_id, tags=tags, values=(team.lg_rank, team.name, "{:.1f}".format(team.points)))