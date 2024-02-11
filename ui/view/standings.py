import tkinter as tk
from tkinter import *              
from tkinter import ttk 
from typing import List

from domain.domain import League, ValueCalculation, Team, CustomScoring
from domain.enum import Position, ScoringFormat, Platform, StatType, CalculationDataType, ProjectionType
from services import custom_scoring_services
from ui.table.table import ScrollableTreeFrame
from ui.tool.tooltip import CreateToolTip
from util import date_util

class Standings(tk.Frame):

    _inflation:float = 0
    league:League
    value_calc:ValueCalculation
    custom_scoring:CustomScoring = None

    non_salary_cap_cols = ('Rank','Team','Points','Players')
    cols = ('Rank','Team','Points', 'Salary', 'Value', 'Surplus', 'Players', '$ Free')

    all_hitting_stats = tuple([st.display for st in StatType.get_all_hit_stattype()])
    all_pitching_stats = tuple([st.display for st in StatType.get_all_pitch_stattype()])

    roto_cols = ('Rank', 'Team') + all_hitting_stats + all_pitching_stats
    rev_cols = ('Rank', 'Team') + tuple([st.display for st in StatType if not st.higher_better]) 
    
    def __init__(self, parent, view=None, current:bool=False):
        '''Creates a new Standings View. If the controlling view is different from the view parent (i.e. the overall view is sub-framed), set the view= variable to the controlling view.'''
        tk.Frame.__init__(self, parent, width=100)
        if view is None:
            self.view = parent
        else:
            self.view = view
        self.pack_propagate(False)

        self.standings_type = IntVar()
        if current:
            self.standings_type.set(0)
        else:
            self.standings_type.set(1)

        self.__create_view()
    
    def __create_view(self):

        button_frame = ttk.Frame(self)
        button_frame.pack(side=TOP, fill='x', expand=False)

        tk.Radiobutton(button_frame, variable=self.standings_type, value=0, text="Current", command=self.__refresh_radio).pack(side=LEFT)
        self.proj_button = tk.Radiobutton(button_frame, variable=self.standings_type, value=1, text="Projected", command=self.__refresh_radio)
        self.proj_button.pack(side=LEFT)
        CreateToolTip(self.proj_button, 'Calculates projected point total based on known replacement levels, remaining salary cap, and league inflation.')

        self.tab_control = ttk.Notebook(self, height=800)
        self.tab_control.pack(side=TOP, fill='both', expand=True)

        standings_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(standings_frame, text='Standings')
        #standings_frame.pack(side='left', fill='both', expand=True)
        
        cols = self.cols + ('Message',)
        widths = {}
        widths['Team'] = 125
        widths['Message'] = 500
        align = {}
        align['Team'] = W
        rev_cols = ('Rank','Team')
        self.standings_table = st = ScrollableTreeFrame(standings_frame, cols,pack=False,sortable_columns=cols,reverse_col_sort=rev_cols, column_widths=widths, init_sort_col='Rank', column_alignments=align)
        st.table.tag_configure('users', background='#FCE19D')
        st.table.set_refresh_method(self.__refresh_standings)
        st.table.set_row_select_method(self.__select_team)
        st.pack(fill='both', expand=True)

        roto_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(roto_frame, text='Categories')
        
        cols = self.roto_cols
        widths = {}
        widths['Team'] = 125
        align = {}
        align['Team'] = W
        rev_cols = ('Rank','Team')
        self.roto_table = rt = ScrollableTreeFrame(roto_frame, cols,pack=False,sortable_columns=cols,reverse_col_sort=self.rev_cols, column_widths=widths, init_sort_col='Rank', column_alignments=align)
        rt.table.tag_configure('users', background='#FCE19D')
        rt.table.set_refresh_method(self.__refresh_roto)
        rt.pack(fill='both', expand=True)

        stats_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(stats_frame, text='Stats')
        
        cols = self.roto_cols
        widths = {}
        widths['Team'] = 125
        align = {}
        align['Team'] = W
        rev_cols = ('Rank','Team') + tuple([st.display for st in StatType if not st.higher_better])
        self.stats_table = st = ScrollableTreeFrame(stats_frame, cols,pack=False,sortable_columns=cols,reverse_col_sort=self.rev_cols, column_widths=widths, init_sort_col='Rank', column_alignments=align)
        st.table.tag_configure('users', background='#FCE19D')
        st.table.set_refresh_method(self.__refresh_stats)
        st.pack(fill='both', expand=True)
    
    def __refresh_radio(self):
        self.view.update()
    
    def __select_team(self, event:Event):
        if len(event.widget.selection()) == 1:
            if hasattr(self.view, 'team_selected'):
                self.view.team_selected(int(event.widget.selection()[0]))

    def __refresh_standings(self):
        if not self.value_calc.projection \
                or (self.value_calc.projection.type == ProjectionType.VALUE_DERIVED and not ScoringFormat.is_points_type(self.value_calc.format)):
            msg = self.__create_message_value('Cannot provide standings')
            self.standings_table.table.insert('', tk.END, iid=-2, values=msg)
            if not self.value_calc.projection:
                self.standings_table.table.insert('', tk.END, iid=-1, values=self.__create_message_value('No projection suppliced'))
            else:
                self.standings_table.table.insert('', tk.END, iid=-1, values=self.__create_message_value('Derived projection insufficient'))
        else:
            for team in self.league.teams:
                tags = ''
                if team.users_team:
                    tags=('users',)
                self.standings_table.table.insert('', tk.END, iid=team.site_id, tags=tags, values=self.__calc_values(team))
    
    def __create_message_value(self, msg:str) -> List[str]:
        msg_row = []
        for _ in enumerate(self.cols):
            msg_row.append(0)
        msg_row.append(msg)
        return msg_row

    def __refresh_roto(self):
        for team in self.league.teams:
            tags = ''
            if team.users_team:
                tags=('users',)
            self.roto_table.table.insert('', tk.END, text=team.site_id, tags=tags, values=self.__calc_roto_values(team))
    
    def __refresh_stats(self):
        for team in self.league.teams:
            tags = ''
            if team.users_team:
                tags=('users',)
            self.stats_table.table.insert('', tk.END, text=team.site_id, tags=tags, values=self.__calc_stat_values(team))
    
    def update_league(self, league:League) -> None:
        self.league = league
        show_cats = False
        if self.value_calc.format == ScoringFormat.CUSTOM:
            self.custom_scoring = custom_scoring_services.get_scoring_format(self.value_calc.get_input(CalculationDataType.CUSTOM_SCORING_FORMAT))
            if not self.custom_scoring.points_format:
                self.standings_type.set(0)
                self.proj_button.configure(state='disable')
                show_cats = True
            else:
                self.proj_button.configure(state='active')
        else:
            self.custom_scoring = None
            if not ScoringFormat.is_points_type(self.value_calc.format):
                self.standings_type.set(0)
                self.proj_button.configure(state='disable')
                show_cats = True
            else:
                self.proj_button.configure(state='active')
        self.__set_display_columns()
        for tab_id in self.tab_control.tabs():
            item = self.tab_control.tab(tab_id)
            if item['text']=='Categories' or item['text']=='Stats':
                if show_cats and self.value_calc.projection and self.value_calc.projection.type != ProjectionType.VALUE_DERIVED:
                    self.tab_control.add(tab_id)
                else:
                    self.tab_control.hide(tab_id)

    def __set_display_columns(self) -> None:
        if not self.value_calc.projection \
                or (self.value_calc.projection.type == ProjectionType.VALUE_DERIVED and not ScoringFormat.is_points_type(self.value_calc.format)):
            self.standings_table.table.set_display_columns(('Message'))
            return
        if self.league.is_salary_cap():
            self.standings_table.table.set_display_columns(self.cols)
        else:
            self.standings_table.table.set_display_columns(self.non_salary_cap_cols)
        if self.custom_scoring:
            if not self.custom_scoring.points_format:
                stat_cats = tuple([cat.category.display for cat in self.custom_scoring.stats])
                self.roto_table.table.set_display_columns(('Rank', 'Team') + stat_cats)
                self.stats_table.table.set_display_columns(('Rank', 'Team') + stat_cats)
        elif not ScoringFormat.is_points_type(self.value_calc.format):
            stat_cats = tuple(cat.display for cat in ScoringFormat.get_format_stat_categories(self.value_calc.format))
            self.roto_table.table.set_display_columns(('Rank', 'Team') + stat_cats)
            self.stats_table.table.set_display_columns(('Rank', 'Team') + stat_cats)

    def __calc_salary_info(self, team:Team) -> list:
        vals = []
        if self.league.platform != Platform.OTTONEU or (date_util.is_offseason() and self.standings_type.get() == 1):
            # Use the league.projected_keepers list
            salaries = 0.0
            tot_val = 0.0
            surplus = 0.0
            num_players = 0
            for rs in team.roster_spots:
                if self.league.platform != Platform.OTTONEU or self.league.is_keeper(rs.player_id):
                    if rs.salary:
                        salaries += rs.salary
                    pv = self.value_calc.get_player_value(rs.player_id, pos=Position.OVERALL)
                    if pv is None:
                        val = 0
                    else:
                        val = pv.value
                    tot_val += val
                    if rs.salary:
                        surplus += val - rs.salary
                    num_players += 1
            vals.append('$' + "{:.0f}".format(salaries))
            vals.append('$' + "{:.0f}".format(tot_val))
            vals.append('$' + "{:.0f}".format(surplus))
            vals.append(num_players)
            vals.append(f'${self.league.team_salary_cap - salaries}')
        else:
            vals.append(f'${team.salaries}')
            tot_val = 0.0
            surplus = 0.0
            for rs in team.roster_spots:
                pv = self.value_calc.get_player_value(rs.player_id, pos=Position.OVERALL)
                if pv is None:
                    val = 0
                else:
                    val = pv.value
                tot_val += val
                surplus += val - rs.salary
            vals.append('$' + "{:.0f}".format(tot_val))
            vals.append('$' + "{:.0f}".format(surplus))
            vals.append(team.num_players)
            vals.append(f'${team.free_cap}')
        return vals
    
    def __calc_values(self, team:Team) -> list:
        vals = []
        vals.append(team.lg_rank)
        vals.append(team.name)
        vals.append("{:.1f}".format(team.points))
        if self.league.is_salary_cap():
            vals.extend(self.__calc_salary_info(team))
        else:
            vals.extend([0, 0, 0, len(team.roster_spots), 0])
        return vals
    
    def __calc_roto_values(self, team:Team) -> list:
        vals = []
        vals.append(team.lg_rank)
        vals.append(team.name)
        for st in StatType.get_all_hit_stattype() + StatType.get_all_pitch_stattype():
            if st in team.cat_ranks:
                vals.append(team.cat_ranks[st])
            else:
                vals.append(0)
        return vals
    
    def __calc_stat_values(self, team:Team) -> list:
        vals = []
        vals.append(team.lg_rank)
        vals.append(team.name)
        for st in StatType.get_all_hit_stattype() + StatType.get_all_pitch_stattype():
            if st in team.cat_ranks:
                try:
                    vals.append(st.format.format(team.cat_stats[st]))
                except KeyError:
                    if st.higher_better:
                        vals.append(st.format.format(0))
                    else:
                        vals.append(st.format.format(999))
            else:
                if st.higher_better:
                    vals.append(st.format.format(0))
                else:
                    vals.append(st.format.format(999))
        return vals

    def refresh(self) -> None:
        '''Refreshes all tabs of Standings view'''
        self.standings_table.table.refresh()
        self.roto_table.table.refresh()
        self.stats_table.table.refresh()