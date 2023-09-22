import tkinter as tk
from tkinter import *              
from tkinter import ttk 

from domain.domain import League, ValueCalculation, Team, Roster_Spot
from domain.enum import Position, AvgSalaryFom, Preference as Pref
from services import projected_keeper_services
from ui.table import ScrollableTreeFrame

class Surplus(tk.Frame):

    league:League
    team:Team
    value_calc:ValueCalculation
    inflation:float

    def __init__(self, parent, view, use_keepers:bool):
        tk.Frame.__init__(self, parent)

        self.parent = parent
        self.view = view
        #self.controller = parent.controller
        self.use_keepers = use_keepers
        self.league = None
        if use_keepers:
            self.columns = ("Keeper?", 'Player', 'Team', 'Pos', 'Roster', 'Salary', 'Value', 'Inf. Cost', 'Surplus', 'Inf. Surplus')
        else:
            self.columns = ('Player', 'Team', 'Pos', 'Roster', 'Salary', 'Value', 'Inf. Cost', 'Surplus', 'Inf. Surplus')
        self.ottoverse_columns = ('Avg. Price', 'L10 Price', 'Roster %')

        self.team_sv = StringVar()
        self.team_sv.set("All Teams")
        self.inflation = 0.0

        self.__create_view()
    
    def __create_view(self):
        header_frame = ttk.Frame(self)
        header_frame.pack(side=TOP, expand=False, fill='x')

        tk.Label(header_frame, text='Team').pack(side=LEFT)
        self.team_list = ttk.Combobox(header_frame, textvariable=self.team_sv)
        self.__set_team_list()
        self.team_list.bind("<<ComboboxSelected>>", self.team_changed)

        self.team_list.pack(side=LEFT)

        ttk.Button(header_frame, text='Trade Evaluation', command=self.trade_evaluation).pack(side=LEFT)

        #TODO: Add positional filter

        cols = self.columns + self.ottoverse_columns
        widths = {}
        widths['Player'] = 125
        widths['Roster'] = 125
        align = {}
        align['Player'] = W
        align['Roster'] = W
        self.player_table = ScrollableTreeFrame(self, cols,pack=False,sortable_columns=cols,reverse_col_sort=cols, column_widths=widths, init_sort_col='Surplus', column_alignments=align, checkbox=self.use_keepers)
        self.player_table.table.tag_configure('users', background='#FCE19D')
        self.player_table.table.add_scrollbar()
        self.player_table.table.set_refresh_method(self.update_player_table)
        self.player_table.table.set_checkbox_toggle_method(self.toggle_keeper)
        self.player_table.pack(fill='both', expand=True)
    
    def toggle_keeper(self, row_id, selected) -> None:
        row_id = int(row_id)
        if selected:
            updated_team=None
            for team in self.league.teams:
                for rs in team.roster_spots:
                    if rs.player.index == row_id:
                        updated_team = team
                        self.league.projected_keepers.append(projected_keeper_services.add_keeper_and_return(self.league, rs.player))       
        else:
            for keeper in self.league.projected_keepers:
                if keeper.player_id == row_id:
                    projected_keeper_services.remove_keeper(keeper)
                    break
            self.league.projected_keepers.remove(keeper)
            updated_team=None
            for team in self.league.teams:
                for rs in team.roster_spots:
                    if rs.player.index == row_id:
                        updated_team = team
                        break
                if updated_team is not None:
                    break
        self.view.update(team=updated_team)

    def __set_team_list(self):
        name_list = []
        name_list.append('All Teams')
        name_list.append('Free Agents')

        if self.league is not None:
            for team in self.league.teams:
                name_list.append(team.name)
        self.team_list['values'] = tuple(name_list)
        self.team_sv.set('All Teams')
    
    def team_changed(self, event: Event):
        self.player_table.table.refresh()

    def update_player_table(self):
        if self.team_sv.get() == 'All Teams':
            for team in self.league.teams:
                for rs in team.roster_spots:
                    tags = tuple()
                    if team.users_team:
                        tags=('users',)
                    if self.use_keepers:
                        if self.league.is_keeper(rs.player_id):
                            tags = tags + ('checked',)
                        else:
                            tags = tags + ('unchecked',)
                    self.player_table.table.insert('', tk.END, tags=tags, values=self.__get_player_row(rs, team), iid=rs.player_id)
        elif self.team_sv.get() == 'Free Agents':
            #TODO: Free Agents
            ...
        else:
            for team in self.league.teams:
                if team.name == self.team_sv.get():
                    for rs in team.roster_spots:
                        if self.use_keepers:
                            if self.league.is_keeper(rs.player_id):
                                tags = ('checked',)
                            else:
                                tags = ('unchecked',)
                        self.player_table.table.insert('', tk.END, tags=tags, values=self.__get_player_row(rs, team), iid=rs.player_id)
    
    def __get_player_row(self, rs:Roster_Spot, team:Team) -> tuple[str]:
        vals = []
        vals.append(rs.player.name)
        vals.append(rs.player.team)
        vals.append(rs.player.position)
        vals.append(team.name)
        vals.append(f'${rs.salary}')
        vc = self.value_calc.get_player_value(rs.player_id, Position.OVERALL)
        if vc is not None:
            val = vc.value
        else:
            val = 0.0
        vals.append('$' + "{:.1f}".format(val))
        vals.append('$' + "{:.1f}".format(val * (1 + self.inflation)))
        vals.append('$' + "{:.1f}".format(val - rs.salary))
        vals.append('$' + "{:.1f}".format(val * (1 + self.inflation) - rs.salary))

        si = rs.player.get_salary_info_for_format(self.league.format)
        #if self.controller.preferences.get('General', Pref.AVG_SALARY_FOM) == AvgSalaryFom.MEAN.value:
        vals.append(f'$' + "{:.1f}".format(si.avg_salary))
        #else:
        #    vals.append(f'$' + "{:.1f}".format(si.med_salary))
        vals.append(f'$' + "{:.1f}".format(si.last_10))
        vals.append("{:.1f}".format(si.roster_percentage) + '%')
        return tuple(vals)
    
    def trade_evaluation(self):
        ...
    
    def update_league(self, league:League) -> None:
        self.league = league
        self.__set_team_list()
    
    def update_value_calc(self, value_calc:ValueCalculation) -> None:
        self.value_calc = value_calc


