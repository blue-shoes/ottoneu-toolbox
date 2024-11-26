import pandas as pd
from pandas import DataFrame, Series
import os
from os import path
from copy import deepcopy
import logging
from typing import List, Dict

from domain.domain import ValueCalculation, CustomScoring, StartingPositionSet
from domain.enum import RankingBasis, RepLevelScheme, CalculationDataType as CDT, Position as P, ScoringFormat, StatType
from domain.exception import InputException
from services import custom_scoring_services
from util import dataframe_util

pd.options.mode.chained_assignment = None # from https://stackoverflow.com/a/20627316

class BatValues():

    default_replacement_positions = {"C":12,"1B":12,"2B":18,"3B":12,"SS":18,"LF":12,"CF":12,"RF":12,"OF":60,"Util":150}
    default_surplus_pos = {"C":0,"1B":0,"2B":0,"3B":0,"SS":0,"LF":0,"CF":0,"RF":0,"OF":0,"Util":0}
    default_replacement_levels = {}
    ottoneu_counts = {P.POS_C:1, P.POS_1B:1, P.POS_2B:1, P.POS_SS:1, P.POS_MI:1, P.POS_3B:1, P.POS_OF:5, P.POS_UTIL:1}
    max_rost_num = {}
    scoring:CustomScoring = None
    starting_pos:StartingPositionSet
    position_keys:List[P]
    start_count:Dict[P, int]

    def __init__(self, value_calc:ValueCalculation, intermediate_calc=False, target_bat=244, max_pos_value=True, prog = None):
        self.format = value_calc.format
        if self.format == ScoringFormat.CUSTOM:
            self.scoring = custom_scoring_services.get_scoring_format(value_calc.get_input(CDT.CUSTOM_SCORING_FORMAT))
        self.intermediate_calculations = intermediate_calc
        self.rank_basis = value_calc.hitter_basis.display
        self.replacement_positions = deepcopy(self.default_replacement_positions)
        self.replacement_levels = deepcopy(self.default_replacement_levels)
        self.target_bat = target_bat
        self.rep_level_scheme = RepLevelScheme._value2member_map_[int(value_calc.get_input(CDT.REP_LEVEL_SCHEME))]
        self.max_pos_value = max_pos_value
        self.num_teams = value_calc.get_input(CDT.NUM_TEAMS)
        self.surplus_pos = deepcopy(self.default_surplus_pos)
        self.total_games = {}
        self.games_filled = {}
        self.stat_avg = {}
        self.stat_std = {}
        self.target_games = value_calc.get_input(CDT.BATTER_G_TARGET)
        self.starting_pos = value_calc.starting_set
        if self.starting_pos:
            self.position_keys = [p.position for p in self.starting_pos.positions if p.position.offense]
            self.start_count = dict([(p.position, p.count) for p in self.starting_pos.positions])
        else:
            self.position_keys = P.get_ottoneu_offensive_pos()
            self.start_count = deepcopy(self.ottoneu_counts)
        if intermediate_calc:
            self.dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
            self.intermed_subdirpath = os.path.join(self.dirname, 'data_dirs', 'intermediate')
            if not path.exists(self.intermed_subdirpath):
                os.mkdir(self.intermed_subdirpath)
        self.prog_dialog = prog

    def calc_bat_points(self, row) -> float:
        '''Returns the points for the hitter for the given statline'''
        #Otto batting points formula from https://ottoneu.fangraphs.com/support
        if self.scoring is None:
            return -1.0*row['AB'] + 5.6*row['H'] + 2.9*row['2B'] + 5.7*row['3B'] + 9.4*row['HR']+3.0*row['BB']+3.0*row['HBP']+1.9*row['SB']-2.8*row['CS']
        points = 0 
        for cat in self.scoring.stats:
            if not cat.category.hitter: continue
            points += cat.points * row[cat.category.display]
        return points

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

    def rank_position_players(self, df:DataFrame, rank_col:str=None) -> None:
        '''Ranks all players eligible at each discrete position according to the RankingBasis per the DataFrame columns'''
        if rank_col is None:
            rank_col = self.rank_basis
        for pos in self.position_keys:
            col = f"Rank {pos.value} Rate"
            g_col = f"{pos.value} Games"
            df[g_col] = 0
            if pos == P.POS_UTIL:
                df[col] = df[rank_col].rank(ascending=False)
                self.max_rost_num['Util'] = len(df)
            else:
                df[col] = df.loc[df['Position(s)'].apply(lambda test_pos, _pos=pos: P.eligible(test_pos, _pos))][rank_col].rank(ascending=False)
                df[col] = df[col].fillna(-999)
                self.max_rost_num[pos.value] = len(df.loc[df['Position(s)'].apply(lambda test_pos, _pos=pos: P.eligible(test_pos, _pos))])
    
    def calc_total_games(self, df:DataFrame) -> None:
        '''Calculates the total games above replacement level at each discrete offensive position per the DataFrame columns'''
        for pos in self.position_keys:
            col = f"{pos.value} Games"
            df[col] = df.apply(self.calc_pos_games, args=(pos,), axis=1)
            self.total_games[pos.value] = df[col].sum()

    def calc_pos_games(self, row, pos:P) -> int:
        '''Calculates all games at the input position filled above replacement level for the given replacement level values.
        Eligible position with lowest replacement level gets all games for a given player.'''
        if not P.eligible(row['Position(s)'], pos):
            return 0
        if (self.__position_is_base(pos) or pos == P.POS_UTIL)and row[f'{pos.value}_FOM'] < 0:
            return 0
        if pos == P.POS_MI:
            if row['SS_FOM'] < 0 and row['2B_FOM'] < 0:
                return 0
        if pos == P.POS_CI:
            if row['1B_FOM'] < 0 and row['3B_FOM'] < 0:
                return 0
        if pos == P.POS_INF:
            if row['1B_FOM'] < 0 and row['3B_FOM'] < 0 and row['SS_FOM'] < 0 and row['2B_FOM'] < 0:
                return 0
        if pos == P.POS_OF and all(x in [P.POS_LF, P.POS_CF, P.POS_RF] for x in self.position_keys):
            if row['LF_FOM'] < 0 and row['CF_FOM'] < 0 and row['RF_FOM'] < 0:
                return 0

        if self.max_pos_value:
            min_rep_pos = ''
            min_rep = 999
            for pos2 in self.position_keys:
                if not (self.__position_is_base(pos2) or pos2 == P.POS_UTIL): continue
                if not P.eligible(row['Position(s)'], pos2): continue
                if self.replacement_levels[pos2.value] < min_rep:
                    min_rep = self.replacement_levels[pos2.value]
                    min_rep_pos = pos2.value
            if min_rep_pos == pos.value:
                return row['G']
            else:
                return 0
        else:
            #TODO: Finish this. this is tricky and involves splitting multi-position guys up
            return 0

    def __position_is_base(self, pos:P) -> bool:
        return P.position_is_base(pos, self.position_keys)

    def are_games_filled(self, df:DataFrame, multi_pos:P=None, multi_pos_idx:int=0) -> bool:
        num_teams = self.num_teams
        '''Returns true if all positions have at least the minimum required games filled above replacement level for the league.'''
        filled_games = True
        non_util_filled = True
        excess_games_dict = {}
        for pos in self.position_keys:
            if self.__position_is_base(pos):
                excess_games = self.total_games[pos.value] - num_teams * self.target_games * self.start_count[pos]
                excess_games_dict[pos.value] = excess_games
                if  excess_games < 0 and self.max_rost_num[pos.value] > self.replacement_positions[pos.value]:
                    self.games_filled[pos.value] = False
                    filled_games = False
                    non_util_filled = False
                else:
                    self.games_filled[pos.value] = True
        if not filled_games:
            return filled_games
        
        component_excess = {}
        for pos in self.position_keys:
            if not self.__position_is_base(pos):
                if pos == P.POS_UTIL:
                    if self.are_util_games_filled(num_teams):
                        self.games_filled['Util'] = True
                    else:
                        self.games_filled['Util'] = False
                        filled_games = False
                else:
                    position_count = sum([self.start_count.get(sub_pos[0], 0) for sub_pos in pos.component_pos]) + self.start_count[pos.value]
                    total_game_sum = sum([self.total_games.get(sub_pos[0], 0) for sub_pos in pos.component_pos])
                    excess_games = total_game_sum - num_teams * self.target_games * position_count
                    excess_games_dict[pos.value] = excess_games
                    for sub_pos in pos.component_pos:
                        component_excess[sub_pos[0]] = excess_games_dict.pop(sub_pos[0], 0)
                    if excess_games < 0:
                        for sub_pos in pos.component_pos:
                            if P.position_is_base(P._value2member_map_[sub_pos[0]], self.position_keys):
                                if self.max_rost_num.get(sub_pos[0], 0) > self.replacement_positions.get(sub_pos[0], 0):
                                    self.games_filled[sub_pos[0]] = False
                                    filled_games = False
                                    non_util_filled = False

        max_excess = -999
        pos_val = None
        for pos, excess in excess_games_dict.items():
            if pos in self.replacement_levels and self.replacement_levels[pos] == self.replacement_levels.get(P.POS_UTIL.value, None): continue
            if excess > max_excess:
                max_excess = excess
                pos_val = pos
        if not non_util_filled and max_excess > self.target_games:
            adj_pos = None
            pos = P._value2member_map_[pos_val]
            if not P.position_is_base(pos, self.position_keys):
                max_sub_excess = 0
                for sub_pos in pos.component_pos:
                    if component_excess.get(sub_pos[0], -999) > max_sub_excess:
                        if sub_pos[0] in self.replacement_levels and self.replacement_levels[sub_pos[0]] == self.replacement_levels.get(P.POS_UTIL.value, None): continue
                        max_sub_excess = component_excess[sub_pos[0]]
                        max_pos = sub_pos[0]
                adj_pos = P._value2member_map_[max_pos] 
            else:
                adj_pos = pos
            if multi_pos == adj_pos:
                index = multi_pos_idx
            else:
                index = self.replacement_positions[adj_pos.value]-1
            pos_df = df.loc[df['Position(s)'].apply(P.eligible, args=(pos,))]
            pos_df = pos_df.sort_values(self.rank_basis, ascending=False)
            excess_games = excess
            while (index > 0):
                pos = pos_df.iloc[index]['Position(s)']
                eligibilities = pos.split('/')
                test_eligibilities = []
                for elig in eligibilities:
                    if elig == pos_val: continue
                    if self.games_filled[elig]: continue
                    test_eligibilities.append(elig)
                if test_eligibilities:
                    min_rl = 999
                    for elig in test_eligibilities:
                        if self.replacement_levels[elig] < min_rl:
                            min_rl = self.replacement_levels[elig]
                            min_pos = elig
                    games = pos_df.iloc[index]['G']
                    self.total_games[adj_pos.value] -= games
                    self.total_games[min_pos] += games
                    return self.are_games_filled(df, multi_pos=adj_pos, multi_pos_idx=index)
                index -= 1
        return filled_games
    
    def are_util_games_filled(self, num_teams:int=12) -> bool:
        '''Determines if other position excesses are enough to fill Util games. Catcher games are not included in calculation.'''
        total_games = 0
        for pos in self.position_keys:
            if pos == P.POS_C: continue
            if self.__position_is_base(pos) or pos == P.POS_UTIL:
                total_games += self.total_games[pos.value] - self.target_games * num_teams * self.start_count[pos]
            else:
                total_games -= self.target_games * self.start_count[pos] * num_teams

        return total_games >= 0 and self.max_rost_num['Util'] > self.replacement_positions['Util']

    def get_position_fom(self, df:DataFrame) -> None:
        '''Determines all player FOM values and popluates them in-place in the DataFrame.'''
        self.rank_position_players(df)

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_ranks.csv")
            df.to_csv(filepath, encoding='utf-8-sig')

        num_bats = 0

        #Initial calculation of replacement levels and FOM
        if self.rep_level_scheme == RepLevelScheme.STATIC_REP_LEVEL:
            for pos in self.position_keys:
                if self.__position_is_base(pos) or pos == P.POS_UTIL:
                    self.set_num_rostered_from_rep_level(df, pos)
                    self.get_fom_from_rep_level(df, pos)
            df['Max FOM'] = df.apply(self.calc_max_fom, axis=1)
        else:
            for pos in self.position_keys:
                if self.__position_is_base(pos) or pos == P.POS_UTIL:
                    if self.replacement_positions[pos.value] > self.max_rost_num[pos.value]:
                        self.replacement_positions[pos.value] = self.max_rost_num[pos.value]
                    self.get_position_fom_calc(df, pos)

            if self.rep_level_scheme == RepLevelScheme.FILL_GAMES:
                #Set maximum FOM value for each player to determine how many are rosterable
                df['Max FOM'] = df.apply(self.calc_max_fom, axis=1)
                self.calc_total_games(df)
                last_inc = 0
                while not self.are_games_filled(df):
                    last_inc += 1
                    if last_inc % int(self.num_teams / 3) == 0 and self.prog_dialog.progress < 70:
                        self.prog_dialog.increment_completion_percent(1)
                        last_inc = 1
                    max_rep_lvl = -999
                    for pos in self.position_keys:
                        if pos == P.POS_UTIL: continue
                        if not self.__position_is_base(pos): continue
                        rep_lvl = self.replacement_levels[pos.value]
                        if not self.games_filled[pos.value] and rep_lvl > max_rep_lvl:
                            max_rep_lvl = rep_lvl
                            max_pos = pos
                    if max_rep_lvl == -999:
                        #Need to fill Util games with highest replacement
                        for pos in self.position_keys:
                            if not self.__position_is_base(pos) or pos == P.POS_UTIL: continue
                            rep_lvl = self.replacement_levels[pos.value]
                            if rep_lvl > max_rep_lvl:
                                max_rep_lvl = rep_lvl
                                max_pos = pos
                    self.replacement_positions[max_pos.value] = self.replacement_positions[max_pos.value] + 1
                    if not ScoringFormat.is_points_type(self.format):
                        self.calculate_roto_bases(df)
                    #Recalculate FOM for the position given the new replacement level
                    if ScoringFormat.is_points_type(self.format):
                        self.get_position_fom_calc(df, max_pos)
                        self.get_position_fom_calc(df, P.POS_UTIL)
                    else:
                        for pos in self.position_keys:
                            if self.__position_is_base(pos)  or pos == P.POS_UTIL:
                                if self.replacement_positions[pos.value] > self.max_rost_num[pos.value]:
                                    self.replacement_positions[pos.value] = self.max_rost_num[pos.value]
                                self.get_position_fom_calc(df, pos)
                    #Set maximum FOM value for each player to determine how many are rosterable
                    df['Max FOM'] = df.apply(self.calc_max_fom, axis=1)
                    self.calc_total_games(df)
                    if not ScoringFormat.is_points_type(self.format) and self.are_games_filled(df):
                        sigma = self.iterate_roto(df)
                        self.calc_total_games(df)
                #Augment the replacement levels by the input surpluses to get the final numbers
                for pos in self.position_keys:
                    if self.__position_is_base(pos):
                        self.replacement_positions[pos.value] = min(self.replacement_positions[pos.value] + self.surplus_pos[pos.value], self.max_rost_num[pos.value])
                        self.get_position_fom_calc(df, pos)
                df['Max FOM'] = df.apply(self.calc_max_fom, axis=1)
            elif self.rep_level_scheme == RepLevelScheme.TOTAL_ROSTERED:
                maxed_out = False
                while num_bats != self.target_bat and not maxed_out:
                    if num_bats > self.target_bat:
                        #Too many players, find the current minimum replacement level and bump that replacement_position down by 1
                        min_rep_lvl = 999.9
                        for pos in self.position_keys:
                            if pos == P.POS_UTIL or pos == P.POS_C: continue
                            if not self.__position_is_base(pos): continue
                            rep_lvl = self.replacement_levels[pos.value]
                            if rep_lvl < min_rep_lvl:
                                min_rep_lvl = rep_lvl
                                min_pos = pos
                        self.replacement_positions[min_pos.value] = self.replacement_positions[min_pos.value]-1
                        if not ScoringFormat.is_points_type(self.format):
                            self.calculate_roto_bases(df)
                        #Recalcluate FOM for the position given the new replacement level
                        self.get_position_fom_calc(df, min_pos)
                    else:
                        #Too few players, find the current maximum replacement level and bump that replacement_position up by 1
                        max_rep_lvl = 0.0
                        for pos in self.position_keys:
                            if pos == P.POS_UTIL or pos == P.POS_C: continue
                            if not self.__position_is_base(pos): continue
                            rep_lvl = self.replacement_levels[pos.value]
                            if rep_lvl > max_rep_lvl:
                                if self.replacement_positions[pos.value] == self.max_rost_num[pos.value]: continue
                                #These two conditionals are arbitrarily determined by me at the time, but they seem to do a good job reigning in 1B and OF
                                #to reasonable levels. No one is going to roster a 1B that hits like a replacement level SS, for example
                                if pos == P.POS_1B and self.replacement_positions['1B'] > 1.5*self.replacement_positions['SS']: continue
                                if pos == P.POS_OF and self.replacement_positions['OF'] > 3*self.replacement_positions['SS']: continue
                                max_rep_lvl = rep_lvl
                                max_pos = pos
                        if max_rep_lvl == 0.0:
                            maxed_out = True
                        else:
                            self.replacement_positions[max_pos.value] = self.replacement_positions[max_pos.value] + 1
                            if not ScoringFormat.is_points_type(self.format):
                                self.calculate_roto_bases(df)
                            #Recalcluate FOM for the position given the new replacement level
                            self.get_position_fom_calc(df, max_pos)
                            self.get_position_fom_calc(df, P.POS_UTIL)
                    #Set maximum FOM value for each player to determine how many are rosterable
                    df['Max FOM'] = df.apply(self.calc_max_fom, axis=1)
                    #FOM is how many bats with a non-negative max FOM
                    num_bats = len(df.loc[df['Max FOM'] >= 0])
            elif self.rep_level_scheme == RepLevelScheme.NUM_ROSTERED:
                if not ScoringFormat.is_points_type(self.format):
                    sigma = self.iterate_roto(df)
                else:
                    df['Max FOM'] = df.apply(self.calc_max_fom, axis=1)
            else:
                #shouldn't get here
                logging.error(f'Inappropriate Replacement Level Scheme {self.rep_level_scheme}')
                raise InputException(f"Inappropriate Replacement Level Scheme {self.rep_level_scheme}")

    def iterate_roto(self, df:DataFrame) -> float:
        df['Max FOM'] = df.apply(self.calc_max_fom, axis=1)
        sigma = 999
        orig = df['Max FOM'].sum()
        two_prior = 999
        while abs(sigma) > 2:
            self.calculate_roto_bases(df)
            for pos in self.position_keys:
                if self.__position_is_base(pos) or pos == P.POS_UTIL:
                    if self.replacement_positions[pos.value] > self.max_rost_num[pos.value]:
                        self.replacement_positions[pos.value] = self.max_rost_num[pos.value]
                    self.get_position_fom_calc(df, pos)
            df['Max FOM'] = df.apply(self.calc_max_fom, axis=1)
            updated = df['Max FOM'].sum()
            sigma = orig - updated
            if two_prior == updated:
                break
            two_prior = orig
            orig = updated
            logging.debug(f'new sigma = {sigma}')
        return sigma

    def get_position_fom_calc(self, df:DataFrame, pos:P) -> None:
        '''Calculate the FOM for each player eligible at a position based on the current replacement level.'''
        rep_level = self.get_position_rep_level(df, pos)
        self.replacement_levels[pos.value] = rep_level
        self.get_fom_from_rep_level(df, pos)

    def calc_bat_fom(self, row, rep_level:float, pos:P) -> float:
        '''Calculates FOM for the given player at the input position with the provided replacement level. If the player is
        not eligible at the position, FOM set to -999.9'''
        if P.eligible(row['Position(s)'], pos):
            #Filter to the current position
            par_rate = row[self.rank_basis] - rep_level
            #Are we doing P/PA values, or P/G values
            if ScoringFormat.is_points_type(self.format):
                if self.rank_basis == 'P/PA':
                    return par_rate * row['PA']
                else:
                    return par_rate * row['G']
            else:
                return par_rate
        #If the position doesn't apply, set FOM to -999.9 to differentiate from the replacement player
        return -999.9

    def calc_max_fom(self, row) -> float:
        '''Returns the max FOM value for the player'''
        foms = []
        for pos in self.position_keys:
            if self.__position_is_base(pos) or pos == P.POS_UTIL:
                foms.append(row[f'{pos.value}_FOM'])
        return max(foms)

    def set_num_rostered_from_rep_level(self, df:DataFrame, pos:P) -> None:
        '''Determines the number of players rostered above replacement level at the given P.'''
        #Filter DataFrame to just the position of interest
        if pos != P.POS_UTIL:
            pos_df = df.loc[df['Position(s)'].apply(P.eligible, args=(pos,))]
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

    def get_fom_from_rep_level(self, df:DataFrame, pos:P) -> None:
        '''Calculates the current FOM for all players for the given P.'''
        col = pos.value + "_FOM"
        df[col] = df.apply(self.calc_bat_fom, args=(self.replacement_levels[pos.value], pos), axis=1)
        if pos.value in ["SS", "2B"]:
            rep_level = max(self.get_position_rep_level(df, P.POS_SS), self.get_position_rep_level(df, P.POS_2B))
            df['MI_FOM'] = df.apply(self.calc_bat_fom, args=(rep_level, P.POS_MI), axis=1)
        if pos.value in ['1B', '3B']:
            rep_level = max(self.get_position_rep_level(df, P.POS_1B), self.get_position_rep_level(df, P.POS_3B))
            df['CI_FOM'] = df.apply(self.calc_bat_fom, args=(rep_level, P.POS_CI), axis=1)
        if pos.value in ['1B', '2B', 'SS', '3B']:
            rep_level = max(self.get_position_rep_level(df, P.POS_1B), self.get_position_rep_level(df, P.POS_3B), \
                            self.get_position_rep_level(df, P.POS_SS), self.get_position_rep_level(df, P.POS_2B))
            df['INF_FOM'] = df.apply(self.calc_bat_fom, args=(rep_level, P.POS_INF), axis=1)
        if pos.value in ['LF', 'CF', 'RF'] and not self.__position_is_base(P.POS_OF):
            rep_level = max(self.get_position_rep_level(df, P.POS_LF), self.get_position_rep_level(df, P.POS_RF), \
                            self.get_position_rep_level(df, P.POS_CF))
            df['OF_FOM'] = df.apply(self.calc_bat_fom, args=(rep_level, P.POS_OF), axis=1)
    
    def get_position_rep_level(self, df:DataFrame, pos:P) -> float:
        '''Based on the number of players to roster above replacement level, return the corresponding replacment level
        required for it to be true.'''
        if not pos in self.position_keys:
            return 999
        if pos != P.POS_UTIL:
            #Filter DataFrame to just the position of interest
            pos_df = df.loc[df['Position(s)'].apply(P.eligible, args=(pos,))]
            pos_df = pos_df.sort_values(self.rank_basis, ascending=False)
            #Get the nth value (here the # of players rostered at the position) from the sorted data - 1 for the zero index
            return pos_df.iloc[self.replacement_positions[pos.value]-1][self.rank_basis]
        else:
            #Util replacement level is equal to the highest replacement level at any position
            pos_df = df
            max_rep_lvl = -100.0
            for pos in self.position_keys:
                if not self.__position_is_base(pos): continue
                rep_level = self.replacement_levels[pos.value]
                if rep_level > max_rep_lvl:
                    max_rep_lvl = rep_level
            return max_rep_lvl
    
    def per_game_rate(self, row, stat:StatType) -> float:
        '''Calculates the per game column for the stat type'''
        return row[stat.display] / row['G']

    def calculate_roto_bases(self, proj:DataFrame, init=False) -> None:
        '''Calculates zScore information (average and stdev of the 4x4 or 5x5 stats). If init is true, will rank off of Runs, otherwise ranks off of previous zScores'''
        if init:
            self.rank_position_players(proj, 'R')
        else:
            self.rank_position_players(proj)
        proj['AB/G'] = proj.apply(self.per_game_rate, axis=1, args=(StatType.AB,))
        proj['PA/G'] = proj.apply(self.per_game_rate, axis=1, args=(StatType.PA,))
        alr = self.roto_above_rl(proj)
        above_rep_lvl = proj.loc[alr]
        if RankingBasis.is_roto_fractional(RankingBasis.get_enum_by_display(self.rank_basis)):
            self.pa_per_team = above_rep_lvl['PA/G'].sum() / self.num_teams
            self.ab_per_team = above_rep_lvl['AB/G'].sum() / self.num_teams
            if self.format == ScoringFormat.CUSTOM:
                cat_to_col = {}
                for cat in self.scoring.stats:
                    if not cat.category.hitter: continue
                    if cat.category.rate_denom is None:
                        proj[f'{cat.category.display}/G'] = proj.apply(self.per_game_rate, axis=1, args=(cat.category,))
                        cat_to_col[cat.category] = f'{cat.category.display}/G'
                    else:
                        self.stat_avg[cat.category] = dataframe_util.weighted_avg(above_rep_lvl, cat.category.display, f'{cat.category.rate_denom.display}/G')
                        proj[f'{cat.category.display}_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(cat.category,))
                        cat_to_col[cat.category] = f'{cat.category.display}_Delta'
            else:
                proj['R/G'] = proj.apply(self.per_game_rate, axis=1, args=(StatType.R,))
                proj['HR/G'] = proj.apply(self.per_game_rate, axis=1, args=(StatType.HR,))
                if self.format == ScoringFormat.OLD_SCHOOL_5X5:
                    proj['RBI/G'] = proj.apply(self.per_game_rate, axis=1, args=(StatType.RBI,))
                    proj['SB/G'] = proj.apply(self.per_game_rate, axis=1, args=(StatType.SB,))
                    self.stat_avg[StatType.AVG] = dataframe_util.weighted_avg(above_rep_lvl, 'AVG', 'AB/G')
                    proj['AVG_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(StatType.AVG,))
                    cat_to_col = {StatType.R : 'R/G', StatType.HR : 'HR/G', StatType.RBI : 'RBI/G', StatType.SB : 'SB/G', StatType.AVG : "AVG_Delta"}
                else:
                    self.stat_avg[StatType.OBP] = dataframe_util.weighted_avg(above_rep_lvl, 'OBP', 'PA/G')
                    proj['OBP_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(StatType.OBP,))
                    self.stat_avg[StatType.SLG] = dataframe_util.weighted_avg(above_rep_lvl, 'SLG', 'AB/G')
                    proj['SLG_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(StatType.SLG,))
                    cat_to_col = {StatType.R : 'R/G', StatType.HR : 'HR/G', StatType.OBP : 'OBP_Delta', StatType.SLG : 'SLG_Delta'}
        else:
            self.pa_per_team = above_rep_lvl['PA'].sum() / self.num_teams
            self.ab_per_team = above_rep_lvl['AB'].sum() / self.num_teams
            if self.format == ScoringFormat.CUSTOM:
                cat_to_col = {}
                for cat in self.scoring.stats:
                    if not cat.category.hitter: continue
                    if cat.category.rate_denom is not None:
                        self.stat_avg[cat.category] = dataframe_util.weighted_avg(above_rep_lvl, cat.category.display, cat.category.display)
                        proj[f'{cat.category.display}_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(cat.category,))
                        cat_to_col[cat.category] = f'{cat.category.display}_Delta'
                    else:
                        cat_to_col[cat.category] = cat.category.display
            else:
                if self.format == ScoringFormat.OLD_SCHOOL_5X5:
                    self.stat_avg[StatType.AVG] = dataframe_util.weighted_avg(above_rep_lvl, 'AVG', 'AB')
                    proj['AVG_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(StatType.AVG,))
                    cat_to_col = {StatType.R : 'R', StatType.HR : 'HR', StatType.RBI : 'RBI', StatType.SB : 'SB', StatType.AVG : "AVG_Delta"}
                else:
                    self.stat_avg[StatType.OBP] = dataframe_util.weighted_avg(above_rep_lvl, 'OBP', 'PA')
                    proj['OBP_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(StatType.OBP,))
                    self.stat_avg[StatType.SLG] = dataframe_util.weighted_avg(above_rep_lvl, 'SLG', 'AB')
                    proj['SLG_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(StatType.SLG,))
                    cat_to_col = {StatType.R : 'R', StatType.HR : 'HR', StatType.OBP : 'OBP_Delta', StatType.SLG : 'SLG_Delta'}
        above_rep_lvl = proj.loc[alr]
        means = above_rep_lvl[list(cat_to_col.values())].mean()
        stds = above_rep_lvl[list(cat_to_col.values())].std()
        for cat in cat_to_col:
            if cat not in [StatType.AVG, StatType.OBP, StatType.SLG]:
                self.stat_avg[cat] = means[cat_to_col.get(cat)]
            self.stat_std[cat] = stds[cat_to_col.get(cat)]
        
        proj[self.rank_basis] = proj.apply(self.calc_z_score, axis=1)
        #print(f'Avg = {self.stat_avg}')
        #print(f'std = {self.stat_std}')

    def calc_rate_delta(self, row, stat:StatType) -> float:
        '''Using the average of the rate stat and the team total AB or PA calculates the change in the rate stat for the player's contributions'''
        if stat.rate_denom == StatType.PA:
            denom = self.pa_per_team
            col = 'PA'
        elif stat.rate_denom == StatType.AB:
            denom = self.ab_per_team
            col = 'AB'
        else:
            raise ValueError(f'Offensive stat {stat.name} did not have a usable rate denominator stat')
        if RankingBasis.is_roto_fractional(RankingBasis.get_enum_by_display(self.rank_basis)):
            col += '/G'
        p_denom = row[col]
        val = ((self.stat_avg[stat] * (denom-p_denom) 
            + row[stat.display] * p_denom)) \
            / denom - self.stat_avg[stat]
        if stat.higher_better:
            return val
        else:
            return -val
    
    def roto_above_rl(self, proj:DataFrame) -> List[bool]:
        above_rl = []
        for _, row in proj.iterrows():
            arl = False
            for pos in self.position_keys:
                if self.__position_is_base(pos):
                    col = f"Rank {pos.value} Rate"
                    if row[col] > 0 and row[col] <= self.replacement_positions.get(pos.value):
                        arl = True
                        break
            above_rl.append(arl)
        return above_rl

    def calc_z_score(self, row) -> float:
        '''Calculates the zScore for the player row'''
        if RankingBasis.is_roto_fractional(RankingBasis.get_enum_by_display(self.rank_basis)):
            col_add = '/G'
            rat = row['G'] / self.target_games
        else:
            col_add = ''
            rat = 1
        zScore = 0
        if self.format == ScoringFormat.CUSTOM:
            for cat in self.scoring.stats:
                if not cat.category.hitter: continue
                if cat.category.rate_denom is None:
                    if cat.category.higher_better:
                        mult = 1
                    else:
                        mult = -1
                    zScore += mult * (row[f'{cat.category.display}{col_add}'] - self.stat_avg.get(cat.category)) / self.stat_std.get(cat.category) * rat
                else:
                    zScore += row[f'{cat.category.display}_Delta'] / self.stat_std.get(cat.category)
        else:
            zScore += (row[f'R{col_add}'] - self.stat_avg.get(StatType.R)) / self.stat_std.get(StatType.R) * rat
            zScore += (row[f'HR{col_add}'] - self.stat_avg.get(StatType.HR)) / self.stat_std.get(StatType.HR) * rat
            if self.format == ScoringFormat.OLD_SCHOOL_5X5:
                zScore += (row[f'RBI{col_add}'] - self.stat_avg.get(StatType.RBI)) / self.stat_std.get(StatType.RBI) * rat
                zScore += (row[f'SB{col_add}'] - self.stat_avg.get(StatType.SB)) / self.stat_std.get(StatType.SB) * rat
                zScore += row['AVG_Delta'] / self.stat_std.get(StatType.AVG)
            else:
                zScore += row['OBP_Delta'] / self.stat_std.get(StatType.OBP)
                zScore += row['SLG_Delta'] / self.stat_std.get(StatType.SLG)
        return zScore

    def calc_fom(self, pos_proj: DataFrame, min_pa:int) -> DataFrame:
        '''Returns a populated DataFrame with all required FOM information for all players above the minimum PA at all positions.'''
        if (self.scoring is not None and self.scoring.points_format) or ScoringFormat.is_points_type(self.format):
            pos_proj['Points'] = pos_proj.apply(self.calc_bat_points, axis=1)
            pos_proj['P/G'] = pos_proj.apply(self.calc_ppg, axis=1)
            pos_proj['P/PA'] = pos_proj.apply(self.calc_pppa, axis=1)
            pos_min_pa = pos_proj.loc[pos_proj['PA'] >= min_pa]
        else:

            if self.rank_basis == RankingBasis.SGP:
                #TODO: Implement SGP
                ...
            else:
                pos_min_pa = pos_proj.loc[pos_proj['PA'] >= min_pa]
                self.calculate_roto_bases(pos_min_pa, init=True)
        #Filter to players projected to a baseline amount of playing time
        
        self.get_position_fom(pos_min_pa)
        if self.intermediate_calculations:
            self.dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
            self.intermed_subdirpath = os.path.join(self.dirname, 'data_dirs', 'intermediate')
            if not path.exists(self.intermed_subdirpath):
                os.mkdir(self.intermed_subdirpath)
            filepath = os.path.join(self.intermed_subdirpath, f"pos_ranks.csv")
            pos_min_pa.to_csv(filepath, encoding='utf-8-sig')
        return pos_min_pa
