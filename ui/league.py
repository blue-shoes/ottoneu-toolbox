import tkinter as tk     
from tkinter import *              
from tkinter import ttk 

from domain.domain import League, ValueCalculation
from domain.enum import Position
from services import league_services, projected_keeper_services
from ui.dialog import progress
from ui.view import standings, surplus

class League_Analysis(tk.Frame):

    league:League
    value_calculation:ValueCalculation

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        self.league = None
        self.value_calculation = None
        self.inflation = 0.0

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
        self.league_text_var = StringVar()
        self.values_name = StringVar()
        self.inflation_sv = StringVar()

        if self.controller.league is None:
            self.league_text_var.set("--")
        else:
            self.league_text_var.set(self.controller.league.name)
        self.lg_lbl = ttk.Label(self, textvariable=self.league_text_var, font='bold')
        self.lg_lbl.grid(column=0,row=0, pady=5, columnspan=2)

        if self.value_calculation is None:
            self.values_name.set('No value calculation selected')
        else:
            self.values_name.set(f'Selected Values: {self.value_calculation.name}')
        ttk.Label(self, textvariable=self.values_name).grid(row=0, column=2)

        self.inflation_lbl = ttk.Label(self, textvariable=self.inflation_sv)
        self.inflation_lbl.grid(column=3,row=0)

        #TODO: make the user_keepers argument dynamic
        self.standings = standings.Standings(self, use_keepers=True)
        self.standings.grid(row=1, column=0, rowspan=5)

        self.surplus = surplus.Surplus(self, use_keepers=True)
        self.surplus.grid(row=1, column=1, rowspan=4, columnspan=3)
    
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
                    self.league = projected_keeper_services.add_keeper(self.league, rs.player)
    
    def load_tables(self):
        self.league_text_var.set(self.controller.league.name)
        self.values_name.set(f'Value Set: {self.value_calculation.name}')
        projected_keeper_services.get_league_keepers(self.league)
        if self.league.projected_keepers is None or len(self.league.projected_keepers) == 0:
            self.initialize_keepers()
        pd = progress.ProgressDialog(self.parent, 'Initializing League Analysis')
        pd.set_completion_percent(10)
        pd.set_task_title("Optimizing lineups")
        league_services.calculate_league_table(self.league, self.value_calculation, self.standings.standings_type.get() == 1, self.inflation)
        pd.set_completion_percent(90)
        pd.set_task_title('Updating display')
        self.standings.league = self.league
        self.standings.value_calc = self.value_calculation
        self.standings.standings_table.refresh()
        self.surplus.update_league(self.league)
        self.surplus.update_value_calc(self.value_calculation)
        self.surplus.player_table.refresh()
        pd.complete()