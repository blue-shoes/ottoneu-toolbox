import tkinter as tk
from tkinter import *              
from tkinter import ttk 

from domain.domain import League, ValueCalculation, Team
from domain.enum import Position
from services import league_services
from ui.table import Table

class Standings(tk.Frame):

    _inflation:float = 0
    league:League
    value_calc:ValueCalculation
    
    def __init__(self, parent, use_keepers:bool):
        tk.Frame.__init__(self, parent)

        self.cols = ('Rank','Team','Points', 'Salary', 'Value', 'Surplus', '$ Free')
        self.use_keepers = use_keepers

        self.standings_type = IntVar()
        self.standings_type.set(1)

        self.create_view()
    
    def create_view(self):
        self.tab_control = ttk.Notebook(self, width=570, height=300)
        self.tab_control.grid(row=0, column=0)

        standings_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(standings_frame, text='Standings')

        tk.Radiobutton(standings_frame, variable=self.standings_type, value=0, text="Current", command=self.refresh_standings).grid(row=0, column=0)
        tk.Radiobutton(standings_frame, variable=self.standings_type, value=1, text="Projected", command=self.refresh_standings).grid(row=0, column=0)

        cols = self.cols
        widths = {}
        widths['Team'] = 125
        align = {}
        align['Team'] = W
        self.standings_table = st = Table(standings_frame, cols,sortable_columns=cols,reverse_col_sort=cols, column_widths=widths, init_sort_col='Rank', column_alignments=align)
        st.grid(column=0, row=1, columnspan=2)
        st.tag_configure('users', background='#FCE19D')
        st.add_scrollbar()
        st.set_refresh_method(self.refresh_standings)
    
    def set_click_action(self, click_action):
        self.standings_table.bind('<<TreeviewSelect>>', click_action)
    
    def refresh_standings(self):
        league_services.calculate_league_table(self.league, self.value_calc, self.standings_type.get() == 1, self._inflation)
        for team in self.league.teams:
            tags = ''
            if team.users_team:
                tags=('users',)
            self.standings_table.insert('', tk.END, text=team.site_id, tags=tags, values=self.calc_values(team))

    def calc_salary_info(self, team:Team) -> list:
        vals = []
        if self.use_keepers:
            salaries = 0.0
            tot_val = 0.0
            surplus = 0.0
            for rs in team.roster_spots:
                if self.league.is_keeper(rs.player_id):
                    salaries += rs.salary
                    pv = self.value_calc.get_player_value(rs.player_id, pos=Position.OVERALL)
                    tot_val += pv.value
                    surplus += pv.value - rs.salary
            vals.append('$' + "{:.0f}".format(salaries))
            vals.append('$' + "{:.0f}".format(tot_val))
            vals.append('$' + "{:.0f}".format(surplus))
            vals.append(f'${400 - salaries}')
        else:
            vals.append(f'${team.salaries}')
            tot_val = 0.0
            surplus = 0.0
            for rs in team.roster_spots:
                pv = self.value_calc.get_player_value(rs.player_id, pos=Position.OVERALL)
                tot_val += pv.value
                surplus += pv.value - rs.salary
            vals.append('$' + "{:.0f}".format(tot_val))
            vals.append('$' + "{:.0f}".format(surplus))
            vals.append(f'S{team.free_cap}')
        return vals
    
    def calc_values(self, team:Team) -> list:
        vals = []
        vals.append(team.lg_rank)
        vals.append(team.name)
        vals.append("{:.1f}".format(team.points))
        vals.extend(self.calc_salary_info(team))
        return vals

