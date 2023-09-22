import tkinter as tk
from tkinter import *              
from tkinter import ttk 

from domain.domain import League, ValueCalculation, Team
from domain.enum import Position
from ui.table import ScrollableTreeFrame

class Standings(tk.Frame):

    _inflation:float = 0
    league:League
    value_calc:ValueCalculation
    
    def __init__(self, parent, use_keepers:bool):
        tk.Frame.__init__(self, parent, width=100)
        self.pack_propagate(False)

        self.cols = ('Rank','Team','Points', 'Salary', 'Value', 'Surplus', '$ Free')
        self.use_keepers = use_keepers

        self.standings_type = IntVar()
        self.standings_type.set(1)

        self.create_view()
    
    def create_view(self):
        self.tab_control = ttk.Notebook(self, height=800)
        self.tab_control.pack(side=TOP, fill='both', expand=True)

        standings_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(standings_frame, text='Standings')
        standings_frame.pack(side='left', fill='both', expand=True)

        button_frame = ttk.Frame(standings_frame)
        button_frame.pack(side=TOP, fill='x', expand=False)

        tk.Radiobutton(button_frame, variable=self.standings_type, value=0, text="Current", command=self.refresh_standings).pack(side=LEFT)
        tk.Radiobutton(button_frame, variable=self.standings_type, value=1, text="Projected", command=self.refresh_standings).pack(side=LEFT)

        cols = self.cols
        widths = {}
        widths['Team'] = 125
        align = {}
        align['Team'] = W
        self.standings_table = st = ScrollableTreeFrame(standings_frame, cols,pack=False,sortable_columns=cols,reverse_col_sort=cols, column_widths=widths, init_sort_col='Rank', column_alignments=align)
        st.table.tag_configure('users', background='#FCE19D')
        st.table.add_scrollbar()
        st.table.set_refresh_method(self.refresh_standings)
        st.pack(fill='both', expand=True)
    
    def set_click_action(self, click_action):
        self.standings_table.table.bind('<<TreeviewSelect>>', click_action)
    
    def refresh_standings(self):
        for team in self.league.teams:
            tags = ''
            if team.users_team:
                tags=('users',)
            self.standings_table.table.insert('', tk.END, text=team.site_id, tags=tags, values=self.calc_values(team))

    def calc_salary_info(self, team:Team) -> list:
        vals = []
        if self.use_keepers:
            salaries = 0.0
            tot_val = 0.0
            surplus = 0.0
            for rs in team.roster_spots:
                if not self.use_keepers or self.league.is_keeper(rs.player_id):
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

