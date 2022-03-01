from cmath import pi
import pandas as pd
import numpy as np
import scrape_fg as scrape
import os
from os import path
from scrape_ottoneu import Scrape_Ottoneu

pd.options.mode.chained_assignment = None # from https://stackoverflow.com/a/20627316

bat_pos = ['C','1B','2B','3B','SS','OF','Util']
default_replacement_positions = {"C":24,"1B":12,"2B":18,"3B":12,"SS":18,"OF":60,"Util":200}
default_replacement_levels = {}

class BatPoint():

    def __init__(self, intermediate_calc=False, rank_basis="P/G", replacement_pos=default_replacement_positions, replacement_levels=default_replacement_levels, target_bat=262):
        self.intermediate_calculations = intermediate_calc
        self.rank_basis = rank_basis
        self.replacement_positions = replacement_pos
        self.replacement_levels = replacement_levels
        self.target_bat = target_bat
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
            if pos == 'Util':
                df[col] = df[self.rank_basis].rank(ascending=False)
            else:
                print(f'Rank Basis = {self.rank_basis}')
                df[col] = df.loc[df['Position(s)'].str.contains(pos)][self.rank_basis].rank(ascending=False)
                df[col].fillna(-999, inplace=True)
        col = "Rank MI Rate"
        df[col] = df.loc[df['Position(s)'].str.contains("2B|SS", case=False, regex=True)][self.rank_basis].rank(ascending=False)
        df[col].fillna(-999, inplace=True)
    
    def get_position_par(self, df):

        self.rank_position_players(df)

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_ranks.csv")
            df.to_csv(filepath, encoding='utf-8-sig')

        num_bats = 0
        while num_bats != self.target_bat:
            #Can't do our rep_level adjustment if we haven't initialized replacement levels
            if len(self.replacement_levels) != 0:
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
            else: 
                #Initial calculation of replacement levels and PAR
                for pos in bat_pos:
                    self.get_position_par_calc(df, pos)
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
        else:
            #No one filters out for Util
            pos_df = df
        pos_df = pos_df.sort_values(self.rank_basis, ascending=False)
        #Get the nth value (here the # of players rostered at the position) from the sorted data
        return pos_df.iloc[self.replacement_positions[pos]][self.rank_basis]

    def calc_par(self, pos_proj):
        pos_proj['Points'] = pos_proj.apply(self.calc_bat_points, axis=1)
        pos_proj['P/G'] = pos_proj.apply(self.calc_ppg, axis=1)
        pos_proj['P/PA'] = pos_proj.apply(self.calc_pppa, axis=1)

        #Filter to players projected to a baseline amount of playing time
        pos_150pa = pos_proj.loc[pos_proj['PA'] >= 150]

        self.get_position_par(pos_150pa)
        return pos_150pa
