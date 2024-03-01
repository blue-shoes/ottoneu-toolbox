import tkinter as tk
from tkinter import *              
from tkinter import ttk 
from typing import List

from domain.domain import League, ValueCalculation, Team, Roster_Spot, PlayerValue, Player
from domain.enum import Position, AvgSalaryFom, Preference as Pref, Platform, InflationMethod
from services import projected_keeper_services
from ui.toolbox_view import ToolboxView
from ui.table.table import ScrollableTreeFrame
from util import date_util

class Surplus(tk.Frame):

    league:League
    team:Team
    value_calc:ValueCalculation
    inflation:float

    def __init__(self, parent:tk.Frame, view:ToolboxView):
        tk.Frame.__init__(self, parent)

        self.parent = parent
        self.view = view
        self.controller = view.controller
        self.league = None
        self.ottoverse_columns = ('Avg. Price', 'L10 Price', 'Roster %')
        if date_util.is_offseason():
            self.all_columns = ("Keeper?", 'Player', 'Team', 'Pos', 'Roster', 'Rank', 'Round', 'Salary', 'Value', 'Inf. Cost', 'Surplus', 'Inf. Surplus') + self.ottoverse_columns
            self.rostered_columns = ("Keeper?", 'Player', 'Team', 'Pos', 'Roster', 'Salary', 'Value', 'Inf. Cost', 'Surplus', 'Inf. Surplus') + self.ottoverse_columns
            self.fa_columns = ("Keeper?", 'Player', 'Team', 'Pos', 'Value', 'Inf. Cost') + self.ottoverse_columns
            self.non_salary_columns = ("Keeper?", 'Player', 'Team', 'Pos', 'Rank', 'Round')
        else:
            self.all_columns = ('Player', 'Team', 'Pos', 'Roster', 'Rank', 'Round', 'Salary', 'Value', 'Inf. Cost', 'Surplus', 'Inf. Surplus') + self.ottoverse_columns
            self.rostered_columns = ('Player', 'Team', 'Pos', 'Roster', 'Salary', 'Value', 'Inf. Cost', 'Surplus', 'Inf. Surplus') + self.ottoverse_columns
            self.fa_columns = ('Player', 'Team', 'Pos', 'Value', 'Inf. Cost') + self.ottoverse_columns
            self.non_salary_columns = ('Player', 'Team', 'Pos', 'Rank', 'Round')

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

        #TODO: Implement
        #ttk.Button(header_frame, text='Trade Evaluation', command=self.trade_evaluation).pack(side=LEFT)

        #TODO: Add positional filter

        cols = self.all_columns
        widths = {}
        widths['Player'] = 125
        widths['Roster'] = 125
        align = {}
        align['Player'] = W
        align['Roster'] = W
        rev_cols = ('Player', 'Team', 'Pos', 'Roster')
        self.player_table = ScrollableTreeFrame(self, cols,pack=False,sortable_columns=cols,reverse_col_sort=rev_cols, column_widths=widths, init_sort_col='Surplus', column_alignments=align, checkbox=date_util.is_offseason())
        self.player_table.table.tag_configure('users', background='#FCE19D')
        self.player_table.table.set_refresh_method(self.update_player_table)
        self.player_table.table.set_checkbox_toggle_method(self.toggle_keeper)
        self.player_table.pack(fill='both', expand=True)
    
    def toggle_keeper(self, row_id, selected) -> None:
        roster_spot = None
        row_id = int(row_id)
        if selected:
            updated_team=None
            for team in self.league.teams:
                for rs in team.roster_spots:
                    if rs.player.index == row_id:
                        updated_team = team
                        self.league.projected_keepers.append(projected_keeper_services.add_keeper_and_return(self.league, rs.player))     
                        roster_spot = rs  
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
                        roster_spot = rs
                        break
                if updated_team is not None:
                    break
        self.view.update(team=updated_team, roster_spot=roster_spot)

    def __set_team_list(self):
        name_list = []
        name_list.append('All Teams')
        name_list.append('Free Agents')

        if date_util.is_offseason():
            name_list.append('Projected FA')

        if self.league is not None:
            for team in self.league.teams:
                name_list.append(team.name)
        self.team_list['values'] = tuple(name_list)
        self.team_sv.set('All Teams')
    
    def team_changed(self, event: Event=None):
        self.player_table.table.refresh()

    def update_player_table(self):
        if self.team_sv.get() == 'All Teams':
            for team in self.league.teams:
                for rs in team.roster_spots:
                    tags = tuple()
                    if team.users_team:
                        tags=('users',)
                    if date_util.is_offseason():
                        if self.league.is_keeper(rs.player_id):
                            tags = tags + ('checked',)
                        else:
                            tags = tags + ('unchecked',)
                    self.player_table.table.insert('', tk.END, tags=tags, values=self.__get_player_row(rs, team), iid=rs.player_id)
            if self.league.is_salary_cap():
                self.player_table.table.set_display_columns(self.rostered_columns)
            else:
                self.player_table.table.set_display_columns(self.non_salary_columns)
        elif self.team_sv.get() == 'Free Agents':
            for pv in self.value_calc.get_position_values(pos=Position.OVERALL):
                if self.league.is_rostered(pv.player_id):
                    continue
                tags = ('disabled',)
                self.player_table.table.insert('', tk.END, tags=tags, values=self.__get_fa_row(pv), iid=pv.player_id)
            if 'Surplus' in self.player_table.table.sort_col:
                self.player_table.table.treeview_sort_column('Value', reverse=True)
            if self.league.is_salary_cap():
                self.player_table.table.set_display_columns(self.fa_columns)
            else:
                self.player_table.table.set_display_columns(self.non_salary_columns)
        elif self.team_sv.get() == 'Projected FA':
            for pv in self.value_calc.get_position_values(pos=Position.OVERALL):
                if self.league.is_keeper(pv.player_id):
                    continue
                tags = ('disabled',)
                self.player_table.table.insert('', tk.END, tags=tags, values=self.__get_fa_row(pv), iid=pv.player_id)
            if 'Surplus' in self.player_table.table.sort_col:
                self.player_table.table.treeview_sort_column('Value', reverse=True)
            if self.league.is_salary_cap():
                self.player_table.table.set_display_columns(self.fa_columns)
            else:
                self.player_table.table.set_display_columns(self.non_salary_columns)
        else:
            for team in self.league.teams:
                if team.name == self.team_sv.get():
                    for rs in team.roster_spots:
                        tags = tuple()
                        if date_util.is_offseason():
                            if self.league.is_keeper(rs.player_id):
                                tags = ('checked',)
                            else:
                                tags = ('unchecked',)
                        self.player_table.table.insert('', tk.END, tags=tags, values=self.__get_player_row(rs, team), iid=rs.player_id)
                    break
            if self.league.is_salary_cap():
                self.player_table.table.set_display_columns(self.rostered_columns)
            else:
                self.player_table.table.set_display_columns(self.non_salary_columns)
        if self.league.is_salary_cap():
            self.player_table.table.sort_col = 'Surplus'
        else:
            self.player_table.table.sort_col = 'Rank'
    
    def update_inflation(self, inflation:float, inf_method:InflationMethod) -> None:
        self.inflation = inflation
        for player_id in self.player_table.table.get_children():
            vals = self.player_table.table.item(player_id)['values']
            if vals[7] == 'NR':
                continue
            pv = float(vals[7].split('$')[1])
            if inf_method == InflationMethod.CONVENTIONAL:
                inf_pv = pv * (1 + self.inflation)
            else:
                inf_pv = (pv - 1) * (1 + self.inflation)
            
            self.player_table.table.set(player_id, [8], '$' + "{:.1f}".format(inf_pv))
            sal = vals[6]
            if sal != '':
                sal = float(sal.split('$')[1])
                inf_surp = inf_pv - sal
                self.player_table.table.set(player_id, [10], '$' + "{:.1f}".format(inf_surp))

    def __get_fa_row(self, pv:PlayerValue) -> tuple[str]:
        vals=[]
        vals.append(pv.player.name)
        vals.append(pv.player.team)
        if pv.player.custom_positions:
            vals.append(pv.player.custom_positions)
        else:
            vals.append(pv.player.position)
        vals.append('') # Team
        if self.league.is_salary_cap():
            vals.extend(['', '', ''])
            vals.append('$' + "{:.1f}".format(pv.value))
            vals.append('$' + "{:.1f}".format(pv.value * (1 + self.inflation)))
        else:
            vals.append(pv.rank)
            vals.append(int((pv.rank - 1) / self.league.num_teams) + 1)
            vals.extend(['', '', ''])
        vals.extend(['', ''])

        vals.extend(self.__get_salary_info(pv.player))

        return tuple(vals)
    
    def __get_player_row(self, rs:Roster_Spot, team:Team) -> tuple[str]:
        vals = []
        vals.append(rs.player.name)
        vals.append(rs.player.team)
        if rs.player.custom_positions:
            vals.append(rs.player.custom_positions)
        else:
            vals.append(rs.player.position)
        vals.append(team.name)
        pv = self.value_calc.get_player_value(rs.player_id, Position.OVERALL)
        if self.league.is_salary_cap():
            vals.append(0) # Rank
            vals.append(0) # Round
            vals.append(f'${rs.salary}')
            if pv is not None:
                val = pv.value
                vals.append('$' + "{:.1f}".format(val))
                if val > 1:
                    vals.append('$' + "{:.1f}".format(max(val-1, 0) * (1 + self.inflation) + 1))
                else:
                    vals.append('$' + "{:.1f}".format(val))
                if rs.salary:
                    vals.append('$' + "{:.1f}".format(val - rs.salary))
                    if val > 1:
                        vals.append('$' + "{:.1f}".format(max(val-1, 0) * (1 + self.inflation) - rs.salary + 1))
                    else:
                        vals.append('$' + "{:.1f}".format(val - rs.salary))
                else:
                    vals.append('$' + "{:.1f}".format(val))
                    if val > 1:
                        vals.append('$' + "{:.1f}".format(max(val-1, 0) * (1 + self.inflation) + 1))
                    else:
                        vals.append('$' + "{:.1f}".format(val))
            else:
                val = 'NR'
                vals.extend([val, val, val, val])
        else:
            if pv is not None:
                vals.append(pv.rank)
                vals.append(int((pv.rank - 1) / self.league.num_teams) + 1)
            else:
                vals.extend(['NR', 'NR'])
            vals.extend([0, 0, 0, 0, 0])
            
        vals.extend(self.__get_salary_info(rs.player))
        
        return tuple(vals)
    
    def __get_salary_info(self, player:Player) -> List[str]:
        if self.league.platform == Platform.OTTONEU:
            vals = []
            si = player.get_salary_info_for_format(self.league.format)
            if self.controller.preferences.get('General', Pref.AVG_SALARY_FOM) == AvgSalaryFom.MEAN.value:
                vals.append(f'$' + "{:.1f}".format(si.avg_salary))
            else:
                vals.append(f'$' + "{:.1f}".format(si.med_salary))
            vals.append(f'$' + "{:.1f}".format(si.last_10))
            vals.append("{:.1f}".format(si.roster_percentage) + '%')
        else:
            vals = [0, 0, 0]
        return vals

    def trade_evaluation(self):
        #TODO: Create Trade Eval section
        ...
    
    def update_league(self, league:League) -> None:
        self.league = league
        self.__set_team_list()
    
    def update_value_calc(self, value_calc:ValueCalculation) -> None:
        self.value_calc = value_calc


