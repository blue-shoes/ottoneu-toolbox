import pandas as pd
from pandas import DataFrame
import os
from os import path
from copy import deepcopy
import logging

from domain.domain import ValueCalculation
from domain.enum import RankingBasis, RepLevelScheme, CalculationDataType as CDT, Position
from domain.exception import InputException

pd.options.mode.chained_assignment = None # from https://stackoverflow.com/a/20627316

class BatPoint():

    default_replacement_positions = {"C":24,"1B":12,"2B":18,"3B":12,"SS":18,"OF":60,"Util":150}
    default_surplus_pos = {"C":0,"1B":0,"2B":0,"3B":0,"SS":0,"OF":0,"Util":0}
    default_replacement_levels = {}
    max_rost_num = {}

    def __init__(self, value_calc:ValueCalculation, intermediate_calc=False, target_bat=244, max_pos_value=True):
        self.intermediate_calculations = intermediate_calc
        self.rank_basis = RankingBasis.enum_to_display_dict()[value_calc.hitter_basis]
        self.replacement_positions = deepcopy(self.default_replacement_positions)
        self.replacement_levels = deepcopy(self.default_replacement_levels)
        self.target_bat = target_bat
        self.rep_level_scheme = RepLevelScheme._value2member_map_[int(value_calc.get_input(CDT.REP_LEVEL_SCHEME))]
        self.max_pos_value = max_pos_value
        self.num_teams = value_calc.get_input(CDT.NUM_TEAMS)
        self.surplus_pos = deepcopy(self.default_surplus_pos)
        self.total_games = {}
        self.games_filled = {}
        self.target_games = value_calc.get_input(CDT.BATTER_G_TARGET)
        if intermediate_calc:
            self.dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
            self.intermed_subdirpath = os.path.join(self.dirname, 'data_dirs', 'intermediate')
            if not path.exists(self.intermed_subdirpath):
                os.mkdir(self.intermed_subdirpath)

    def calc_bat_points(self, row) -> float:
        '''Returns the points for the hitter for the given statline'''
        #Otto batting points formula from https://ottoneu.fangraphs.com/support
        return -1.0*row['AB'] + 5.6*row['H'] + 2.9*row['2B'] + 5.7*row['3B'] + 9.4*row['HR']+3.0*row['BB']+3.0*row['HBP']+1.9*row['SB']-2.8*row['CS']

    def calc_ppg(self, row) -> float:
        '''Returns player's points per game based on known df columns'''
        if row['G'] == 0:
            return 0
        return row['Points'] / row['G']

    def calc_pppa(self, row) -> float:
        '''Returns player's points per PA based on known df columns'''
        if row['PA'] == 0:
            return 0
        return row['Points'] / row['PA']

    def rank_position_players(self, df:DataFrame) -> None:
        '''Ranks all players eligible at each discrete position according to the RankingBasis per the DataFrame columns'''
        for pos in Position.get_discrete_offensive_pos():
            col = f"Rank {pos.value} Rate"
            g_col = f"{pos.value} Games"
            df[g_col] = 0
            if pos == Position.POS_UTIL:
                df[col] = df[self.rank_basis].rank(ascending=False)
                self.max_rost_num['Util'] = len(df)
            else:
                df[col] = df.loc[df['Position(s)'].str.contains(pos.value)][self.rank_basis].rank(ascending=False)
                df[col].fillna(-999, inplace=True)
                self.max_rost_num[pos.value] = len(df.loc[df['Position(s)'].str.contains(pos.value)])
        col = "Rank MI Rate"
        df[col] = df.loc[df['Position(s)'].str.contains("2B|SS", case=False, regex=True)][self.rank_basis].rank(ascending=False)
        df[col].fillna(-999, inplace=True)
        df['MI Games'] = 0
    
    def calc_total_games(self, df:DataFrame) -> None:
        '''Calculates the total games above replacement level at each discrete offensive position per the DataFrame columns'''
        for pos in Position.get_discrete_offensive_pos():
            if pos == Position.OFFENSE:
                continue
            col = f"{pos.value} Games"
            df[col] = df.apply(self.calc_pos_games, args=(pos,), axis=1)
            self.total_games[pos.value] = df[col].sum()

    def calc_pos_games(self, row, pos:Position) -> int:
        '''Calculates all games at the input position filled above replacement level for the given replacement level values.
        Eligible position with lowest replacement level gets all games for a given player.'''
        if pos == Position.POS_MI:
            if not row['Position(s)'].contains("2B|SS", case=False, regex=True):
                return 0
            if row['SS_PAR'] < 0 and row['2B_PAR'] < 0:
                return 0
        elif pos == Position.POS_UTIL:
            if row['Util_PAR'] < 0:
                return 0
        else:
            if not pos.value in row['Position(s)']:
                return 0
            if row[f'{pos.value}_PAR'] < 0:
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
            if min_rep_pos == pos.value:
                return row['G']
            else:
                return 0
        else:
            #TODO: Finish this. this is tricky and involves splitting multi-position guys up
            return 0

    def are_games_filled(self, num_teams:int=12) -> bool:
        '''Returns true if all positions have at least the minimum required games filled above replacement level for the league.'''
        filled_games = True
        if self.total_games['C'] < num_teams * self.target_games and self.max_rost_num['C'] > self.replacement_positions['C']:
            self.games_filled['C'] = False
            filled_games = False
        else:
            self.games_filled['C'] = True
        if self.total_games['1B'] < num_teams * self.target_games and self.max_rost_num['1B'] > self.replacement_positions['1B']:
            self.games_filled['1B'] = False
            filled_games = False
        else:
            self.games_filled['1B'] = True
        if self.total_games['3B'] < num_teams * self.target_games and self.max_rost_num['3B'] > self.replacement_positions['3B']:
            self.games_filled['3B'] = False
            filled_games = False
        else:
            self.games_filled['3B'] = True
        if self.total_games['SS'] + self.total_games['2B'] < 3*num_teams * self.target_games:
            if self.max_rost_num['SS'] > self.replacement_positions['SS']:
                self.games_filled['SS'] = False
            if self.max_rost_num['2B'] > self.replacement_positions['2B']:
                self.games_filled['2B'] = False
            if not self.games_filled['SS'] or not self.games_filled['2B']:
                filled_games = False
        else:
            self.games_filled['SS'] = True
            self.games_filled['2B'] = True
        if self.total_games['OF'] < num_teams * self.target_games * 5 and self.max_rost_num['OF'] > self.replacement_positions['OF']:
            self.games_filled['OF'] = False
            filled_games = False
        else:
            self.games_filled['OF'] = True
        
        if self.are_util_games_filled(num_teams):
            self.games_filled['Util'] = True
        else:
            self.games_filled['Util'] = False
            filled_games = False
        return filled_games
    
    def are_util_games_filled(self, num_teams:int=12) -> bool:
        '''Determines if other position excesses are enough to fill Util games. Catcher games are not included in calculation.'''
        #judgement call that you aren't using C to fill Util
        return self.total_games['1B'] - self.target_games*num_teams +  self.total_games['3B'] - self.target_games*num_teams + (self.total_games['2B'] + self.total_games['SS'] - 3*self.target_games*num_teams) + self.total_games['OF']-5*self.target_games*num_teams + self.total_games['Util'] >= num_teams*self.target_games and self.max_rost_num['Util'] > self.replacement_positions['Util']

    def get_position_par(self, df:DataFrame) -> None:
        '''Determines all player PAR values and popluates them in-place in the DataFrame.'''
        self.rank_position_players(df)

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_ranks.csv")
            df.to_csv(filepath, encoding='utf-8-sig')

        num_bats = 0

        #Initial calculation of replacement levels and PAR
        if self.rep_level_scheme == RepLevelScheme.STATIC_REP_LEVEL:
            for pos in Position.get_discrete_offensive_pos():
                self.set_num_rostered_from_rep_level(df, pos)
                self.get_par_from_rep_level(df, pos)
            df['Max PAR'] = df.apply(self.calc_max_par, axis=1)
        else:
            for pos in Position.get_discrete_offensive_pos():
                if self.replacement_positions[pos.value] > self.max_rost_num[pos.value]:
                    self.replacement_positions[pos.value] = self.max_rost_num[pos.value]
                self.get_position_par_calc(df, pos)

            if self.rep_level_scheme == RepLevelScheme.FILL_GAMES:
                #Set maximum PAR value for each player to determine how many are rosterable
                df['Max PAR'] = df.apply(self.calc_max_par, axis=1)
                self.calc_total_games(df)
                while not self.are_games_filled(self.num_teams):
                    max_rep_lvl = 0.0
                    for pos, rep_lvl in self.replacement_levels.items():
                        if pos == 'Util': continue
                        if not self.games_filled[pos] and rep_lvl > max_rep_lvl:
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
                    self.get_position_par_calc(df, Position._value2member_map_.get(max_pos))
                    self.get_position_par_calc(df, Position.POS_UTIL)
                    #Set maximum PAR value for each player to determine how many are rosterable
                    df['Max PAR'] = df.apply(self.calc_max_par, axis=1)
                    self.calc_total_games(df)
                #Augment the replacement levels by the input surpluses to get the final numbers
                for pos in self.replacement_positions:
                    self.replacement_positions[pos] = min(self.replacement_positions[pos] + self.surplus_pos[pos], self.max_rost_num[pos])
                    self.get_position_par_calc(df, Position._value2member_map_.get(pos))
                df['Max PAR'] = df.apply(self.calc_max_par, axis=1)
            elif self.rep_level_scheme == RepLevelScheme.TOTAL_ROSTERED:
                maxed_out = False
                while num_bats != self.target_bat and not maxed_out:
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
                                if self.replacement_positions[pos] == self.max_rost_num[pos]: continue
                                #These two conditionals are arbitrarily determined by me at the time, but they seem to do a good job reigning in 1B and OF
                                #to reasonable levels. No one is going to roster a 1B that hits like a replacement level SS, for example
                                if pos == '1B' and self.replacement_positions['1B'] > 1.5*self.replacement_positions['SS']: continue
                                if pos == 'OF' and self.replacement_positions['OF'] > 3*self.replacement_positions['SS']: continue
                                max_rep_lvl = rep_lvl
                                max_pos = pos
                        if max_rep_lvl == 0.0:
                            maxed_out = True
                        else:
                            self.replacement_positions[max_pos] = self.replacement_positions[max_pos] + 1
                            #Recalcluate PAR for the position given the new replacement level
                            self.get_position_par_calc(df, max_pos)
                            self.get_position_par_calc(df, 'Util')
                    #Set maximum PAR value for each player to determine how many are rosterable
                    df['Max PAR'] = df.apply(self.calc_max_par, axis=1)
                    #FOM is how many bats with a non-negative max PAR
                    num_bats = len(df.loc[df['Max PAR'] >= 0])
            elif self.rep_level_scheme == RepLevelScheme.NUM_ROSTERED:
                df['Max PAR'] = df.apply(self.calc_max_par, axis=1)
            else:
                #shouldn't get here
                logging.error(f'Inappropriate Replacement Level Scheme {self.rep_level_scheme}')
                raise InputException(f"Inappropriate Replacement Level Scheme {self.rep_level_scheme}")

    def get_position_par_calc(self, df:DataFrame, pos:Position) -> None:
        '''Calculate the PAR for each player eligible at a position based on the current replacement level.'''
        rep_level = self.get_position_rep_level(df, pos)
        self.replacement_levels[pos.value] = rep_level
        self.get_par_from_rep_level(df, pos)

    def calc_bat_par(self, row, rep_level:float, pos:Position) -> float:
        '''Calculates PAR for the given player at the input position with the provided replacement level. If the player is
        not eligible at the position, PAR set to -999.9'''
        if pos.value in row['Position(s)'] or pos == Position.POS_UTIL or (pos.value == 'MI' and ('SS' in row['Position(s)'] or '2B' in row['Position(s)'])):
            #Filter to the current position
            par_rate = row[self.rank_basis] - rep_level
            #Are we doing P/PA values, or P/G values
            if self.rank_basis == 'P/PA':
                return par_rate * row['PA']
            else:
                return par_rate * row['G']
        #If the position doesn't apply, set PAR to -999.9 to differentiate from the replacement player
        return -999.9

    def calc_max_par(self, row) -> float:
        '''Returns the max PAR value for the player'''
        #Find the max PAR for player across all positions
        #TODO: Confirm max works here instead of np.max
        return max([row['C_PAR'], row['1B_PAR'], row['2B_PAR'],row['3B_PAR'],row['SS_PAR'],row['OF_PAR'],row['Util_PAR']])

    def set_num_rostered_from_rep_level(self, df:DataFrame, pos:Position) -> None:
        '''Determines the number of players rostered above replacement level at the given position.'''
        #Filter DataFrame to just the position of interest
        if pos != Position.POS_UTIL:
            pos_df = df.loc[df['Position(s)'].str.contains(pos.value)]
        else:
            pos_df = df
        pos_df = pos_df.sort_values(self.rank_basis, ascending=False)
        #Determine the index of the last player above the replacement level for the position
        index = 0
        while True:
            rate = pos_df.iloc[index][self.rank_basis]
            if rate < self.replacement_levels[pos.value] and (index+1) < self.max_rost_num[pos.value]:
                break
            index += 1
        #Set number rostered at position to index + 1 (for zero index)
        self.replacement_positions[pos.value] = index + 1

    def get_par_from_rep_level(self, df:DataFrame, pos:Position) -> None:
        '''Calculates the current PAR for all players for the given position.'''
        col = pos.value + "_PAR"
        df[col] = df.apply(self.calc_bat_par, args=(self.replacement_levels[pos.value], pos), axis=1)
        if pos.value in ["SS", "2B"]:
            rep_level = min(self.get_position_rep_level(df, Position.POS_SS), self.get_position_rep_level(df, Position.POS_2B))
            df['MI_PAR'] = df.apply(self.calc_bat_par, args=(rep_level, Position.POS_MI), axis=1)
    
    def get_position_rep_level(self, df:DataFrame, pos:Position) -> float:
        '''Based on the number of players to roster above replacement level, return the corresponding replacment level
        required for it to be true.'''
        if pos != Position.POS_UTIL:
            #Filter DataFrame to just the position of interest
            pos_df = df.loc[df['Position(s)'].str.contains(pos.value)]
            pos_df = pos_df.sort_values(self.rank_basis, ascending=False)
            #Get the nth value (here the # of players rostered at the position) from the sorted data - 1 for the zero index
            return pos_df.iloc[self.replacement_positions[pos.value]-1][self.rank_basis]
        else:
            #Util replacement level is equal to the highest replacement level at any position
            pos_df = df
            max_rep_lvl = 0.0
            for pos, rep_level in self.replacement_levels.items():
                if pos != 'Util' and rep_level > max_rep_lvl:
                    max_rep_lvl = rep_level
            return max_rep_lvl

    def calc_par(self, pos_proj: DataFrame, min_pa:int) -> DataFrame:
        '''Returns a populated DataFrame with all required PAR information for all players above the minimum PA at all positions.'''
        pos_proj['Points'] = pos_proj.apply(self.calc_bat_points, axis=1)
        pos_proj['P/G'] = pos_proj.apply(self.calc_ppg, axis=1)
        pos_proj['P/PA'] = pos_proj.apply(self.calc_pppa, axis=1)

        #Filter to players projected to a baseline amount of playing time
        pos_min_pa = pos_proj.loc[pos_proj['PA'] >= min_pa]

        self.get_position_par(pos_min_pa)
        return pos_min_pa
