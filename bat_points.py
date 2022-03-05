from cmath import pi
import pandas as pd
import numpy as np
from sqlalchemy import false
import scrape_fg as scrape
import os
from os import path
from scrape_ottoneu import Scrape_Ottoneu

pd.options.mode.chained_assignment = None # from https://stackoverflow.com/a/20627316

bat_pos = ['C','1B','2B','3B','SS','OF','Util']
default_replacement_positions = {"C":12,"1B":12,"2B":18,"3B":12,"SS":18,"OF":60,"Util":200}
default_replacement_levels = {}
total_games = {}
games_filled = {}

class BatPoint():

    def __init__(self, intermediate_calc=False, rank_basis="P/G", replacement_pos=default_replacement_positions, replacement_levels=default_replacement_levels, target_bat=244, 
    calc_using_games=False, max_pos_value=True):
        self.intermediate_calculations = intermediate_calc
        self.rank_basis = rank_basis
        self.replacement_positions = replacement_pos
        self.replacement_levels = replacement_levels
        self.target_bat = target_bat
        self.calc_using_games = calc_using_games
        self.max_pos_value = max_pos_value
        if intermediate_calc:
            self.dirname = os.path.dirname(__file__)
            self.intermed_subdirpath = os.path.join(self.dirname, 'intermediate')
            if not path.exists(self.intermed_subdirpath):
                os.mkdir(self.intermed_subdirpath)

    def calc_bat_points(self, row):
        #Otto batting points formula from https://ottoneu.fangraphs.com/support
        return -1.0*row['AB'] + 5.6*row['H'] + 2.9*row['2B'] + 5.7*row['3B'] + 9.4*row['HR']+3.0*row['BB']+3.0*row['HBP']+1.9*row['SB']-2.8*row['CS']

    def calc_ppg(self, row):
        if row['G'] == 0:
            return 0
        return row['Points'] / row['G']

    def calc_pppa(self, row):
        if row['PA'] == 0:
            return 0
        return row['Points'] / row['PA']

    def rank_position_players(self, df):
        for pos in bat_pos:
            col = f"Rank {pos} Rate"
            g_col = f"{pos} Games"
            df[g_col] = 0
            if pos == 'Util':
                df[col] = df[self.rank_basis].rank(ascending=False)
            else:
                df[col] = df.loc[df['Position(s)'].str.contains(pos)][self.rank_basis].rank(ascending=False)
                df[col].fillna(-999, inplace=True)
        col = "Rank MI Rate"
        df[col] = df.loc[df['Position(s)'].str.contains("2B|SS", case=False, regex=True)][self.rank_basis].rank(ascending=False)
        df[col].fillna(-999, inplace=True)
        df['MI Games'] = 0
    
    def calc_total_games(self, df):
        for pos in bat_pos:
            col = f"{pos} Games"
            df[col] = df.apply(self.calc_pos_games, args=(pos, 1), axis=1)
            total_games[pos] = df[col].sum()

    def calc_pos_games(self, row, pos, empty):
        if pos == 'MI':
            if not row['Position(s)'].contains("2B|SS", case=False, regex=True):
                return 0
            if row['SS_PAR'] < 0 and row['2B_PAR'] < 0:
                return 0
        elif pos == 'Util':
            if row['Util_PAR'] < 0:
                return 0
        else:
            if not pos in row['Position(s)']:
                return 0
            if row[f'{pos}_PAR'] < 0:
                return 0
        if self.max_pos_value:
            positions = row['Position(s)'].split("/")
            min_rep_pos = ''
            min_rep = 999
            for player_pos in positions:
                if player_pos == 'SP' or player_pos == 'RP': continue
                if self.replacement_levels[player_pos] < min_rep:
                    min_rep = self.replacement_levels[player_pos]
                    min_rep_pos = player_pos
            if min_rep_pos == pos:
                return row['G']
            else:
                return 0
        else:
            #TODO: Finish this
            return 0

    def are_games_filled(self, num_teams=12):
        filled_games = True
        if total_games['C'] < num_teams * 162:
            games_filled['C'] = False
            filled_games = False
        else:
            games_filled['C'] = True
        if total_games['1B'] < num_teams * 162:
            games_filled['1B'] = False
            filled_games = False
        else:
            games_filled['1B'] = True
        if total_games['3B'] < num_teams * 162:
            games_filled['3B'] = False
            filled_games = False
        else:
            games_filled['3B'] = True
        if total_games['SS'] + total_games['2B'] < 3*num_teams * 162:
            games_filled['SS'] = False
            games_filled['2B'] = False
            filled_games = False
        else:
            games_filled['SS'] = True
            games_filled['2B'] = True
        if total_games['OF'] < num_teams * 162 * 5:
            games_filled['OF'] = False
            filled_games = False
        else:
            games_filled['OF'] = True
        
        if self.are_util_games_filled(num_teams):
            games_filled['Util'] = True
        else:
            games_filled['Util'] = False
            filled_games = False
        return filled_games
    
    def are_util_games_filled(self, num_teams=12):
        #judgement call that you aren't using C to fill Util
        return total_games['1B'] - 162*num_teams +  total_games['3B'] - 162*num_teams + (total_games['2B'] + total_games['SS'] - 3*162*num_teams) + total_games['OF']-5*162*num_teams + total_games['Util'] >= num_teams*162

    def get_position_par(self, df):

        self.rank_position_players(df)

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_ranks.csv")
            df.to_csv(filepath, encoding='utf-8-sig')

        num_bats = 0

        #Initial calculation of replacement levels and PAR
        for pos in bat_pos:
            self.get_position_par_calc(df, pos)

        if self.calc_using_games:
            #Set maximum PAR value for each player to determine how many are rosterable
            df['Max PAR'] = df.apply(self.calc_max_par, axis=1)
            self.calc_total_games(df)
            while not self.are_games_filled():
                max_rep_lvl = 0.0
                for pos, rep_lvl in self.replacement_levels.items():
                    if pos == 'Util': continue
                    if not games_filled[pos] and rep_lvl > max_rep_lvl:
                        max_rep_lvl = rep_lvl
                        max_pos = pos
                if max_rep_lvl == 0.0:
                    #Need to fill Util games with highest replacement
                    for pos, rep_lvl in self.replacement_levels.items():
                        if rep_lvl > max_rep_lvl:
                            max_rep_lvl = rep_lvl
                            max_pos = pos
                self.replacement_positions[max_pos] = self.replacement_positions[max_pos] + 1
                #Recalcluate PAR for the position given the new replacement level
                self.get_position_par_calc(df, max_pos)
                self.get_position_par_calc(df, 'Util')
                #Set maximum PAR value for each player to determine how many are rosterable
                df['Max PAR'] = df.apply(self.calc_max_par, axis=1)
                self.calc_total_games(df)
        else:
            while num_bats != self.target_bat:
                if num_bats > self.target_bat:
                    #Too many players, find the current minimum replacement level and bump that replacement_position down by 1
                    min_rep_lvl = 999.9
                    for pos, rep_lvl in self.replacement_levels.items():
                        if pos == 'Util' or pos == 'C': continue
                        if rep_lvl < min_rep_lvl:
                            min_rep_lvl = rep_lvl
                            min_pos = pos
                    self.replacement_positions[min_pos] = self.replacement_positions[min_pos]-1
                    #Recalcluate PAR for the position given the new replacement level
                    self.get_position_par_calc(df, min_pos)
                else:
                    #Too few players, find the current maximum replacement level and bump that replacement_position up by 1
                    max_rep_lvl = 0.0
                    for pos, rep_lvl in self.replacement_levels.items():
                        if pos == 'Util' or pos == 'C': continue
                        if rep_lvl > max_rep_lvl:
                            #These two conditionals are arbitrarily determined by me at the time, but they seem to do a good job reigning in 1B and OF
                            #to reasonable levels. No one is going to roster a 1B that hits like a replacement level SS, for example
                            if pos == '1B' and self.replacement_positions['1B'] > 1.5*self.replacement_positions['SS']: continue
                            if pos == 'OF' and self.replacement_positions['OF'] > 3*self.replacement_positions['SS']: continue
                            max_rep_lvl = rep_lvl
                            max_pos = pos
                    self.replacement_positions[max_pos] = self.replacement_positions[max_pos] + 1
                    #Recalcluate PAR for the position given the new replacement level
                    self.get_position_par_calc(df, max_pos)
                    self.get_position_par_calc(df, 'Util')
                #Set maximum PAR value for each player to determine how many are rosterable
                df['Max PAR'] = df.apply(self.calc_max_par, axis=1)
                #FOM is how many bats with a non-negative max PAR
                num_bats = len(df.loc[df['Max PAR'] >= 0])

    def get_position_par_calc(self, df, pos):
        rep_level = self.get_position_rep_level(df, pos)
        self.replacement_levels[pos] = rep_level
        col = pos + "_PAR"
        df[col] = df.apply(self.calc_bat_par, args=(rep_level, pos), axis=1)

    def calc_bat_par(self, row, rep_level, pos):
        if pos in row['Position(s)'] or pos == 'Util':
            #Filter to the current position
            par_rate = row[self.rank_basis] - rep_level
            #Are we doing P/PA values, or P/G values
            if self.rank_basis == 'P/PA':
                return par_rate * row['PA']
            else:
                return par_rate * row['G']
        #If the position doesn't apply, set PAR to -1 to differentiate from the replacement player
        return -1.0

    def calc_max_par(self, row):
        #Find the max PAR for player across all positions
        return np.max([row['C_PAR'], row['1B_PAR'], row['2B_PAR'],row['3B_PAR'],row['SS_PAR'],row['OF_PAR'],row['Util_PAR']])

    def get_position_rep_level(self, df, pos):
        if pos != 'Util':
            #Filter DataFrame to just the position of interest
            pos_df = df.loc[df['Position(s)'].str.contains(pos)]
            pos_df = pos_df.sort_values(self.rank_basis, ascending=False)
            #Get the nth value (here the # of players rostered at the position) from the sorted data
            return pos_df.iloc[self.replacement_positions[pos]][self.rank_basis]
        else:
            #Util replacement level is equal to the highest replacement level at any position
            pos_df = df
            max_rep_lvl = 0.0
            for pos, rep_level in self.replacement_levels.items():
                if pos != 'Util' and rep_level > max_rep_lvl:
                    max_rep_lvl = rep_level
            return max_rep_lvl

    def calc_par(self, pos_proj):
        pos_proj['Points'] = pos_proj.apply(self.calc_bat_points, axis=1)
        pos_proj['P/G'] = pos_proj.apply(self.calc_ppg, axis=1)
        pos_proj['P/PA'] = pos_proj.apply(self.calc_pppa, axis=1)

        #Filter to players projected to a baseline amount of playing time
        pos_150pa = pos_proj.loc[pos_proj['PA'] >= 150]

        self.get_position_par(pos_150pa)
        return pos_150pa
