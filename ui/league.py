import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
import threading
from typing import List

from math import ceil

from domain.domain import League, ValueCalculation, Team, Roster_Spot
from domain.enum import Position, ScoringFormat
from services import league_services, projected_keeper_services
from ui.dialog import progress
from ui.view import standings, surplus
from util import date_util

class League_Analysis(tk.Frame):

    league:League
    value_calculation:ValueCalculation
    offseason:bool

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, height=600, width=1300)
        self.parent = parent
        self.controller = controller
        self.league = None
        self.value_calculation = None
        self.inflation = 0.0

        self.offseason = date_util.is_offseason()

        self.create_main()
    
    def on_show(self):
        if self.controller.league is None or not league_services.league_exists(self.controller.league):
            self.controller.select_league()
        if self.controller.value_calculation is None or len(self.controller.value_calculation.values) == 0:
            self.controller.select_value_set()
        if self.controller.league is None or self.controller.value_calculation is None:
            return False

        self.league = self.controller.league
        self.value_calculation = self.controller.value_calculation

        self.load_tables()

        return True
    
    def leave_page(self):
        return True
    
    def create_main(self):
        self.pack_propagate(False)

        self.league_text_var = StringVar()
        self.values_name = StringVar()
        self.inflation_sv = StringVar()

        header_frame = ttk.Frame(self)
        header_frame.pack(side=TOP, fill='x', expand=False)

        if self.controller.league is None:
            self.league_text_var.set("--")
        else:
            self.league_text_var.set(self.controller.league.name)
        self.lg_lbl = ttk.Label(header_frame, textvariable=self.league_text_var, font='bold')
        self.lg_lbl.grid(row=0, column=0)

        if self.value_calculation is None:
            self.values_name.set('No value calculation selected')
        else:
            self.values_name.set(f'Selected Values: {self.value_calculation.name}')
        ttk.Label(header_frame, textvariable=self.values_name).grid(row=0, column=1)

        self.inflation_lbl = ttk.Label(header_frame, textvariable=self.inflation_sv)
        self.inflation_lbl.grid(row=0, column=2)

        big_frame = ttk.Frame(self)
        big_frame.pack(side=TOP, expand=True, fill='both')

        #TODO: make the user_keepers argument dynamic
        self.standings = standings.Standings(big_frame, view=self)
        self.standings.pack(side=LEFT, fill='both', expand=True)

        self.surplus = surplus.Surplus(big_frame, view=self)
        self.surplus.pack(side=LEFT, fill='both', expand=True)
    
    def league_change(self):
        self.league = self.controller.league
        self.load_tables()
    
    def value_change(self):
        self.value_calculation = self.controller.value_calculation
        self.load_tables()
    
    def initialize_keepers(self):
        if self.league.projected_keepers is None:
            self.league.projected_keepers = []
        for team in self.league.teams:
            for rs in team.roster_spots:
                pv = self.value_calculation.get_player_value(rs.player_id, Position.OVERALL)
                if pv is not None and pv.value > rs.salary:
                    self.league.projected_keepers.append(projected_keeper_services.add_keeper_and_return(self.league, rs.player))

    def handle_inflation(self, roster_spot:Roster_Spot):
        self.inflation = league_services.update_league_inflation(self.league, self.value_calculation.get_player_value(roster_spot.player_id, Position.OVERALL), roster_spot)
        self.inflation_sv.set(f'League Inflation: {"{:.1f}".format(self.inflation * 100)}%')
        self.surplus.update_inflation(self.inflation)
    
    def initialize_inflation(self):
        self.inflation = league_services.calculate_league_inflation(self.league, self.value_calculation, use_keepers=self.__is_use_keepers())
        self.inflation_sv.set(f'League Inflation: {"{:.1f}".format(self.inflation * 100)}%')
        self.surplus.inflation = self.inflation
        if len(self.league.projected_keepers) > 0:
            self.optimize_keepers()

    def optimize_keepers(self):
        while(True):
            discrepancies = []
            overpredict=False
            underpredict=False
            for team in self.league.teams:
                for rs in team.roster_spots:
                    pv = self.value_calculation.get_player_value(rs.player_id, Position.OVERALL)
                    if pv is None:
                        continue
                    if pv.value * (1 + self.inflation) > rs.salary and not self.league.is_keeper(pv.player_id):
                        discrepancies.append((pv.value * (1 + self.inflation) - rs.salary, rs.player_id))
                        overpredict=True
                    elif pv.value * (1 + self.inflation) < rs.salary and self.league.is_keeper(pv.player_id):
                        discrepancies.append((rs.salary - (pv.value * (1 + self.inflation)), rs.player_id))
                        underpredict=True
            len(discrepancies), overpredict, underpredict, ceil(2*len(discrepancies)/3)
            if len(discrepancies) < 2 or (overpredict and underpredict):
                break
            sorted_list = sorted(discrepancies, reverse=True)
            for i in range(0, ceil(2*len(sorted_list)/3)):
                if overpredict:
                    self.league.projected_keepers.append(projected_keeper_services.add_keeper_by_player_id(self.league, sorted_list[i][1]))
                else:
                    self.league.projected_keepers.remove(projected_keeper_services.remove_keeper_by_league_and_player(self.league, sorted_list[i][1]))

    def load_tables(self):
        self.league_text_var.set(self.controller.league.name)
        self.values_name.set(f'Value Set: {self.value_calculation.name}')
        projected_keeper_services.get_league_keepers(self.league)
        if self.offseason and (self.league.projected_keepers is None or len(self.league.projected_keepers) == 0):
            self.initialize_keepers()
        pd = progress.ProgressDialog(self.parent, 'Initializing League Analysis')
        pd.set_task_title("Optimizing lineups")
        self.initialize_inflation()
        self.standings.update_league(self.league)
        self.standings.value_calc = self.value_calculation
        pd.set_completion_percent(10)
        league_services.calculate_league_table(self.league, self.value_calculation, \
                                                fill_pt=(self.standings.standings_type.get() == 1), \
                                                inflation=self.inflation,\
                                                use_keepers=self.__is_use_keepers())
        pd.set_completion_percent(90)
        pd.set_task_title('Updating display')
        self.standings.standings_table.table.refresh()
        self.surplus.update_league(self.league)
        self.surplus.update_value_calc(self.value_calculation)
        self.surplus.player_table.table.refresh()
        pd.complete()
    
    def __is_use_keepers(self) -> bool:
        return (self.offseason and self.standings.standings_type.get() == 1)
    
    def update_league_table(self, team_list:List):
        league_services.calculate_league_table(self.league, self.value_calculation, self.standings.standings_type.get() == 1, self.inflation, updated_teams=team_list, use_keepers=self.__is_use_keepers())
    
    def check_if_league_table_ready(self, calc_thread:threading.Thread):
        if calc_thread.is_alive():
            self.after(200, self.check_if_league_table_ready, calc_thread)
        else:
            self.standings.standings_table.table.refresh()

    def update(self, team:Team=None, roster_spot:Roster_Spot=None):
        if team is None:
            team_list=None
        else:
            team_list = [team]
        self.handle_inflation(roster_spot)
        thread = threading.Thread(target=self.update_league_table, args=(team_list,))
        thread.start()
        self.after(200, self.check_if_league_table_ready, thread)
        self.surplus.player_table.table.refresh()
