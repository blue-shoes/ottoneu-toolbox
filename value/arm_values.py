import pandas as pd
from pandas import DataFrame, Series
import os
from os import path
from copy import deepcopy
from typing import List
import logging

from domain.domain import ValueCalculation, CustomScoring
from domain.enum import RepLevelScheme, RankingBasis, CalculationDataType as CDT, ScoringFormat, Position, StatType
from services import custom_scoring_services
from util import dataframe_util

pd.options.mode.chained_assignment = None  # from https://stackoverflow.com/a/20627316


class ArmValues:
    default_replacement_positions = {'SP': 60, 'RP': 30}
    default_replacement_levels = {}
    default_surplus_pos = {'SP': 0, 'RP': 0}
    weeks = 26
    max_rost_num = {}
    scoring: CustomScoring = None

    def __init__(self, value_calc: ValueCalculation, intermediate_calc=False, target_arm=196, rp_limit=999):
        self.intermediate_calculations = intermediate_calc
        self.replacement_positions = deepcopy(self.default_replacement_positions)
        self.replacement_levels = deepcopy(self.default_replacement_levels)
        self.target_pitch = target_arm
        self.SABR = ScoringFormat.is_sabr(value_calc.s_format)
        self.rp_limit = rp_limit
        self.rep_level_scheme = RepLevelScheme._value2member_map_[int(value_calc.get_input(CDT.REP_LEVEL_SCHEME))]
        self.num_teams = value_calc.get_input(CDT.NUM_TEAMS)
        self.surplus_pos = deepcopy(self.default_surplus_pos)
        self.min_sp_ip = value_calc.get_input(CDT.SP_IP_TO_RANK)
        self.min_rp_ip = value_calc.get_input(CDT.RP_IP_TO_RANK)
        self.rank_basis = value_calc.pitcher_basis
        self.s_format = value_calc.s_format
        if self.s_format == ScoringFormat.CUSTOM:
            self.scoring = custom_scoring_services.get_scoring_format(value_calc.get_input(CDT.CUSTOM_SCORING_FORMAT))
        self.stat_avg = {}
        self.stat_std = {}

        self.no_sv_hld = value_calc.get_input(CDT.INCLUDE_SVH) == 0

        if self.rep_level_scheme == RepLevelScheme.FILL_GAMES:
            if ScoringFormat.is_h2h(self.s_format):
                self.gs_per_week = value_calc.get_input(CDT.GS_LIMIT)
                self.est_rp_g_per_week = value_calc.get_input(CDT.RP_G_TARGET)
            else:
                self.target_innings = value_calc.get_input(CDT.IP_TARGET) * self.num_teams
                self.target_ip_per_team = value_calc.get_input(CDT.IP_TARGET)
                self.rp_ip_per_team = value_calc.get_input(CDT.RP_IP_TARGET)

        if intermediate_calc:
            self.dirname = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            self.intermed_subdirpath = os.path.join(self.dirname, 'data_dirs', 'intermediate')
            if not path.exists(self.intermed_subdirpath):
                os.mkdir(self.intermed_subdirpath)

    def _hbp_calc(self, bba) -> float:
        # This HBP approximation is from a linear regression I did when I first did values
        return 0.0951 * bba + 0.4181

    def pitch_points_engine(self, row: Series, save: float, hold: float) -> float:
        """Returns player pitching points for projection row using input save and hold values. HBP filled via regression
        if not available"""

        hbp = row.get('HBPA', self._hbp_calc(row['BBA']))

        if self.s_format == ScoringFormat.CUSTOM:
            points = 0
            for cat in self.scoring.stats:
                if cat.category.hitter:
                    continue
                points += cat.points * row[cat.category.display]
                return points
        elif self.SABR:
            # Otto pitching points (SABR) from https://ottoneu.fangraphs.com/support
            return 5.0 * row['IP'] + 2.0 * row['K'] - 3.0 * row['BBA'] - 3.0 * hbp - 13.0 * row['HRA'] + 5.0 * save + 4.0 * hold
        else:
            # Otto pitching points (FGP) from https://ottoneu.fangraphs.com/support
            return 7.4 * row['IP'] + 2.0 * row['K'] - 2.6 * row['HA'] - 3.0 * row['BBA'] - 3.0 * hbp - 12.3 * row['HRA'] + 5.0 * save + 4.0 * hold

    def calc_pitch_points(self, row) -> float:
        """Returns player pitching points for projection row using row columns."""
        try:
            save = row['SV']
        except KeyError:
            # TODO: fill-in save calc
            save = 0
        try:
            hold = row['HLD']
        except KeyError:
            # TODO: fill-in hold calc
            hold = 0
        return self.pitch_points_engine(row, save, hold)

    def calc_pitch_points_no_svh(self, row) -> float:
        """Returns player pitching points for projection row using input and setting zero saves/holds"""
        return self.pitch_points_engine(row, 0, 0)

    def calc_ppi(self, row) -> float:
        """Calculate points per inning based on known columns"""
        if row['IP'] == 0:
            return 0
        return row['Points'] / row['IP']

    def calc_ppg(self, row) -> float:
        """Calculate points per game based on known columns"""
        if row['GP'] == 0:
            return 0
        return row['Points'] / row['GP']

    def calc_ppi_no_svh(self, row) -> float:
        """Calculate points per inning with no saves/holds based on known columns"""
        if row['IP'] == 0:
            return 0
        return row['No SVH Points'] / row['IP']

    def calc_ppg_no_svh(self, row) -> float:
        """Calculate points per game with no saves/holds based on known columns"""
        if row['GP'] == 0:
            return 0
        return row['No SVH Points'] / row['GP']

    def get_pitcher_fom(self, df: DataFrame) -> DataFrame:
        if self.rep_level_scheme == RepLevelScheme.STATIC_REP_LEVEL:
            self.get_fom(df)
            self.set_number_rostered(df)
        else:
            num_arms = 0
            total_ip = 0
            split = ScoringFormat.is_points_type(self.s_format)
            self.get_pitcher_fom_calc(df, split=split)

            rosterable = df.loc[df['FOM'] >= 0]
            sp_ip = rosterable.apply(self.usable_ip_calc, args=('SP',), axis=1).sum()
            rp_ip = rosterable.apply(self.usable_ip_calc, args=('RP',), axis=1).sum()
            total_ip = sp_ip + rp_ip

            sp_g = rosterable.apply(self.usable_gs_calc, axis=1).sum()
            rp_g = rosterable.apply(self.usable_rp_g_calc, axis=1).sum()

            if self.rep_level_scheme == RepLevelScheme.FILL_GAMES:
                if not ScoringFormat.is_h2h(self.s_format):
                    while sp_ip < self.num_teams * (self.target_ip_per_team - self.rp_ip_per_team) and self.replacement_positions['SP'] < self.max_rost_num['SP']:
                        self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                        if not ScoringFormat.is_points_type(self.s_format):
                            self.calculate_roto_bases(df)
                        self.get_pitcher_fom_calc(df, split=split)
                        rosterable = df.loc[df['FOM SP'] >= 0]
                        sp_ip = rosterable.apply(self.usable_ip_calc, args=('SP',), axis=1).sum()
                        if not ScoringFormat.is_points_type(self.s_format) and sp_ip >= self.num_teams * (self.target_ip_per_team - self.rp_ip_per_team):
                            _ = self.iterate_roto(df)
                            sp_ip = rosterable.apply(self.usable_ip_calc, args=('SP',), axis=1).sum()
                    while rp_ip < self.num_teams * self.rp_ip_per_team and self.replacement_positions['RP'] < self.max_rost_num['RP']:
                        self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        if not ScoringFormat.is_points_type(self.s_format):
                            self.calculate_roto_bases(df)
                        self.get_pitcher_fom_calc(df, split=split)
                        rosterable = df.loc[df['FOM RP'] >= 0]
                        rp_ip = rosterable.apply(self.usable_ip_calc, args=('RP',), axis=1).sum()
                        if not ScoringFormat.is_points_type(self.s_format) and rp_ip >= self.num_teams * self.rp_ip_per_team:
                            _ = self.iterate_roto(df)
                            rp_ip = rosterable.apply(self.usable_ip_calc, args=('RP',), axis=1).sum()
                else:
                    while sp_g < self.num_teams * self.gs_per_week * self.weeks and self.replacement_positions['SP'] < self.max_rost_num['SP']:
                        self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                        self.get_pitcher_fom_calc(df)
                        rosterable = df.loc[df['FOM SP'] >= 0]
                        sp_g = rosterable.apply(self.usable_gs_calc, axis=1).sum()
                    while rp_g < self.num_teams * self.est_rp_g_per_week * self.weeks and self.replacement_positions['RP'] < self.max_rost_num['RP']:
                        self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        self.get_pitcher_fom_calc(df)
                        rosterable = df.loc[df['FOM RP'] >= 0]
                        rp_g = rosterable.apply(self.usable_rp_g_calc, axis=1).sum()
                self.replacement_positions['SP'] = min(self.replacement_positions['SP'] + self.surplus_pos['SP'], self.max_rost_num['SP'])
                self.replacement_positions['RP'] = min(self.replacement_positions['RP'] + self.surplus_pos['RP'], self.max_rost_num['RP'])
                if not ScoringFormat.is_points_type(self.s_format) and rp_ip < self.num_teams * self.rp_ip_per_team:
                    _ = self.iterate_roto(df)
                else:
                    self.get_pitcher_fom_calc(df, split=split)

            elif self.rep_level_scheme == RepLevelScheme.TOTAL_ROSTERED:
                if self.rank_basis == RankingBasis.PIP:
                    while (num_arms != self.target_pitch or (abs(total_ip - self.target_innings) > 100 and self.replacement_positions['RP'] != self.rp_limit)) and (
                        self.replacement_positions['SP'] < self.max_rost_num['SP'] and self.replacement_positions['RP'] < self.max_rost_num['RP']
                    ):
                        # Going to do optional capping of relievers. It can get a bit out of control otherwise
                        if num_arms < self.target_pitch and (self.replacement_positions['RP'] == self.rp_limit or self.replacement_positions['RP'] < self.max_rost_num['RP']):
                            self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                        elif num_arms == self.target_pitch:
                            # We have the right number of arms, but not in the inning threshold
                            if total_ip < self.target_innings:
                                # Too many relievers
                                if self.replacement_positions['SP'] == self.max_rost_num['SP']:
                                    # Don't have any more starters, this is optimal
                                    break
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] - 1
                            else:
                                # Too many starters
                                if self.replacement_positions['RP'] == self.max_rost_num['RP']:
                                    # Don't have any more relievers, this is optimal
                                    break
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] - 1
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        elif num_arms < self.target_pitch:
                            if self.target_pitch - num_arms == 1 and self.target_innings - total_ip > 200 and self.replacement_positions['SP'] < self.max_rost_num['SP']:
                                # Add starter, a reliever isn't going to get it done, so don't bother
                                # I got caught in a loop without this
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                            # Not enough pitchers. Preferentially add highest replacement level
                            elif (self.replacement_levels['SP'] > self.replacement_levels['RP'] and self.replacement_positions['SP'] < self.max_rost_num['SP']) or self.replacement_positions[
                                'RP'
                            ] == self.max_rost_num['RP']:
                                # Probably not, but just in case
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                            else:
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        else:
                            if self.target_pitch - num_arms == -1 and self.target_innings - total_ip > 50:
                                # Remove a reliever. We're already short on innings, so removing a starter isn't going to get it done, so don't bother
                                # I got caught in a loop without this
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] - 1
                            # Too many pitchers. Preferentially remove lowest replacement level
                            elif self.replacement_levels['SP'] < self.replacement_levels['RP']:
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] - 1
                            else:
                                # Probably not, but just in case
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] - 1
                        self.get_pitcher_fom_calc(df)
                        # FOM is how many arms with a non-negative FOM...
                        rosterable = df.loc[df['FOM'] >= 0]
                        num_arms = len(rosterable)
                        # ...and how many total innings are pitched
                        total_ip = rosterable.apply(self.usable_ip_calc, args=('SP',), axis=1).sum()
                        total_ip += rosterable.apply(self.usable_ip_calc, args=('RP',), axis=1).sum()
                elif self.rank_basis == RankingBasis.PPG:
                    target_starts = self.num_teams * self.gs_per_week * self.weeks
                    while (
                        num_arms != self.target_pitch
                        or abs(sp_g - target_starts) > 10
                        and (self.replacement_positions['SP'] < self.max_rost_num['SP'] and self.replacement_positions['RP'] < self.max_rost_num['RP'])
                    ):
                        # Going to do optional capping of relievers. It can get a bit out of control otherwise
                        if num_arms < self.target_pitch and self.replacement_positions['RP'] == self.rp_limit and self.replacement_positions['SP'] < self.max_rost_num['SP']:
                            self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                        elif num_arms == self.target_pitch:
                            # We have the right number of arms, but not in the inning threshold
                            if sp_g < target_starts:
                                # Too many relievers
                                if self.replacement_positions['SP'] == self.max_rost_num['SP']:
                                    # Don't have any more SP, this is optimal
                                    break
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] - 1
                            else:
                                # Too many starters
                                if self.replacement_positions['RP'] == self.max_rost_num['RP']:
                                    # Don't have any more RP, this is optimal
                                    break
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] - 1
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        elif num_arms < self.target_pitch:
                            if (target_starts - sp_g > 10 and self.replacement_positions['SP'] < self.max_rost_num['SP']) or self.replacement_positions['RP'] == self.max_rost_num['RP']:
                                # Add starter
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                            else:
                                # Have enough starts, add reliever
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        else:
                            if self.target_pitch - num_arms == -1 and target_starts - sp_g < -20:
                                # Remove a starter. We probably have enough GS
                                # I got caught in a loop without this
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] - 1
                            # Too many pitchers and we don't have enough starts
                            else:
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] - 1
                        self.get_pitcher_fom_calc(df)
                        # FOM is how many arms with a non-negative FOM...
                        rosterable = df.loc[df['FOM'] >= 0]
                        num_arms = len(rosterable)
                        # ...and how many GS
                        sp_g = rosterable.apply(self.usable_gs_calc, axis=1).sum()
            elif self.rep_level_scheme == RepLevelScheme.NUM_ROSTERED:
                if split:
                    self.get_pitcher_fom_calc(df)
                else:
                    _ = self.iterate_roto(df)
            else:
                raise Exception('Unusable Replacement Level Scheme')
        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, 'pit_rost.csv')
            rosterable.to_csv(filepath, encoding='utf-8-sig')
            filepath = os.path.join(self.intermed_subdirpath, 'df_tot.csv')
            df.to_csv(filepath, encoding='utf-8-sig')

        return df

    def usable_ip_calc(self, row, role: str) -> float:
        """Returns an estimated usable number of innings pitched based on the projection and pitcher ranking"""
        return row[f'IP {role}'] * row[f'{role} Multiplier']

    def usable_fom_calc(self, row, role) -> float:
        """Returns an estimated usable number of pitching FOM based on the projection and pitcher ranking"""
        if row[f'FOM {role}'] < -100:
            return 0
        return row[f'FOM {role}'] * row[f'{role} Multiplier']

    def usable_gs_calc(self, row) -> float:
        """Returns an estimated usable number of games started based on the projection and pitcher ranking"""
        return row['GS'] * row['SP Multiplier']

    def usable_rp_g_calc(self, row) -> float:
        """Returns an estimated usable number of relief games pitched based on the projection and pitcher ranking"""
        return (row['GP'] - row['GS']) * row['RP Multiplier']

    def get_pitcher_fom_calc(self, df: DataFrame, split: bool = True) -> None:
        """Sets replacement levels for the current iteration and populates FOM figures for all pitchers and roles"""
        sp_rep_level = self.get_pitcher_rep_level(df, 'SP')
        self.replacement_levels['SP'] = sp_rep_level
        rp_rep_level = self.get_pitcher_rep_level(df, 'RP')
        self.replacement_levels['RP'] = rp_rep_level
        self.get_fom(df, split)

    def get_fom(self, df: DataFrame, split: bool = True) -> None:
        """Calculates role FOMs and overall FOM for each pitcher in-place"""
        if split:
            df['FOM SP'] = df.apply(self.calc_pitch_fom_role, args=('SP', self.replacement_levels['SP']), axis=1)
            df['FOM RP'] = df.apply(self.calc_pitch_fom_role, args=('RP', self.replacement_levels['RP']), axis=1)
            df['FOM'] = df.apply(self.sum_role_fom, axis=1)
        else:
            df['FOM SP'] = df.apply(self.calc_roto_fom_role, args=('SP', self.replacement_levels['SP']), axis=1)
            df['FOM RP'] = df.apply(self.calc_roto_fom_role, args=('RP', self.replacement_levels['RP']), axis=1)
            df['FOM'] = df.apply(self.calc_max_fom, axis=1)

    def calc_roto_fom_role(self, row, pos: str, rep_level: float) -> float:
        if row[f'{pos} Rankable']:
            return row[self.rank_basis.display] - rep_level
        # If the position doesn't apply, set FOM to -999.9 to differentiate from the replacement player
        return -999.9

    def calc_max_fom(self, row) -> float:
        """Returns the max FOM value for the player"""
        # Find the max FOM for player across all positions
        return max([row['FOM SP'], row['FOM RP']])

    def set_number_rostered(self, df: DataFrame) -> None:
        """Determines what number pitcher represents replacement level for all roles and sets it in the internal dict"""
        sp_count = 0
        rp_count = 0
        for idx, row in df.iterrows():
            if row['FOM'] > 0:
                if 'SP' in row['Position(s)']:
                    sp_count += 1
                if 'RP' in row['Position(s)']:
                    rp_count += 1
        self.replacement_positions['SP'] = sp_count
        self.replacement_positions['RP'] = rp_count

    def calc_pitch_fom_role(self, row, role: str, rep_level: float) -> float:
        """Returns the FOM accumulated by the pitcher in the given role at the given replacement level."""
        if row['GP'] == 0:
            return -1
        if row[f'IP {role}'] == 0:
            return -1
        if self.no_sv_hld:
            prefix = 'No SVH '
        else:
            prefix = ''
        if self.rank_basis == RankingBasis.PIP:
            rate = row[f'{prefix}P/IP {role}'] - rep_level
            return rate * row[f'IP {role}']
        elif self.rank_basis == RankingBasis.PPG:
            rate = row[f'{prefix}P/G {role}'] - rep_level
            if role == 'SP':
                return rate * row['GS']
            else:
                return rate * (row['GP'] - row['GS'])

    def sum_role_fom(self, row) -> float:
        """Sums the pitcher's SP and RP FOM values"""
        sp_fom = row['FOM SP']
        if row['IP SP'] == 0:
            sp_fom = 0
        rp_fom = row['FOM RP']
        if row['IP RP'] == 0:
            rp_fom = 0
        return sp_fom + rp_fom

    def get_pitcher_rep_level(self, df: DataFrame, pos: str) -> float:
        """Returns pitcher role replacement level based on current rank value in replacement_positions dict"""
        # Filter DataFrame to just the position of interest
        pitch_df = df.loc[df[f'{pos} Rankable']]
        if self.no_sv_hld:
            prefix = 'No SVH '
        else:
            prefix = ''
        if self.rank_basis == RankingBasis.PIP:
            sort_col = f'{prefix}P/IP {pos}'
        elif self.rank_basis == RankingBasis.PPG:
            sort_col = f'{prefix}P/G {pos}'
        else:
            sort_col = self.rank_basis.display
        pitch_df = pitch_df.sort_values(sort_col, ascending=False)
        # Get the nth value (here the # of players rostered at the position - 1 for 0 index) from the sorted data
        return pitch_df.iloc[self.replacement_positions[pos] - 1][sort_col]

    def calc_rp_ip_split_ratio(self, row: Series) -> float:
        # Based on second-order poly regression performed for all pitcher seasons from 2019-2021 with GS > 0 and GRP > 0
        # Regression has dep variable of GRP/G (or (G-GS)/G) and IV IPRP/IP. R^2=0.9481. Possible issues with regression: overweighting
        # of pitchers with GRP/G ratios very close to 0 (starters with few RP appearances) or 1 (relievers with few SP appearances)
        gr_per_g = (row['GP'] - row['GS']) / row['GP']
        if gr_per_g > 0.85:
            return 1
        if gr_per_g < 0.15:
            return 0
        return 0.7851 * gr_per_g**2 + 0.1937 * gr_per_g + 0.0328

    def not_a_belly_itcher_filter(self, row) -> bool:
        """Determines if pitcher has sufficient innings to be included in replacement level calculations. Split role
        pitchers have their innings rationed to role and are checked against an interpolated value."""
        # Filter pitchers from the data set who don't reach requisite innings. These thresholds are arbitrary.
        try:
            gs = row['GS']
            g = row['GP']
            ip = row['IP']
            if gs == g:
                return ip >= self.min_sp_ip
            if gs == 0:
                return ip >= self.min_rp_ip
            if g == 0:
                return False
        except KeyError:
            return False
        # Got to here, this is a SP/RP with > 0 G. Ration their innings threshold based on their projected GS/G ratio
        start_ip_to_ip = 1 - self.calc_rp_ip_split_ratio(row)
        return row['IP'] > (self.min_sp_ip - self.min_rp_ip) * start_ip_to_ip + self.min_rp_ip

    def rp_ip_func(self, row) -> float:
        """Calculates the number of innings pitched in relief based on a linear regression using games relieved per total
        games as the independent variable."""
        # Avoid divide by zero error
        if row['GP'] == 0:
            return 0
        # Only relief appearances
        if row['GS'] == 0:
            return row['IP']
        # Only starting appearances
        if row['GS'] == row['GP']:
            return 0
        return row['IP'] * self.calc_rp_ip_split_ratio(row)

    def sp_ip_func(self, row) -> float:
        """Calculates the number of innings pitched in starts based on previously calculated relief innings."""
        return row['IP'] - row['IP RP']

    def sp_fip_calc(self, row) -> float:
        """Estimates pitcher FIP in the starting role based on overall FIP and number of innings pitched in starts. Assumes
        approximately a 0.6 point improvement in FIP when transitioning from SP to RP based on historical analysis."""
        if row['IP RP'] == 0:
            return row['FIP']
        if row['IP SP'] == 0:
            return 0
        # Weighted results from 2019-2021 dataset shows an approxiately 0.6 FIP improvement from SP to RP
        return (row['IP'] * row['FIP'] + 0.6 * row['IP RP']) / row['IP']

    def rp_fip_calc(self, row) -> float:
        """Estimates pitcher FIP in the relieving role based on the previously calculated starter FIP and subtracting 0.6 based
        on historical analysis"""
        if row['IP RP'] == 0:
            return 0
        if row['IP SP'] == 0:
            return row['FIP']
        return row['FIP SP'] - 0.6

    def sp_pip_calc(self, row) -> float:
        """Estimates pitcher points per inning in starting role based off of difference between overall FIP and SP FIP
        using a linear regression."""
        if row['IP SP'] == 0:
            return 0
        # Regression of no SVH P/IP from FIP gives linear coefficient of -1.3274
        fip_diff = row['FIP SP'] - row['FIP']
        return row['No SVH P/IP'] - 1.3274 * fip_diff

    def sp_ppg_calc(self, row) -> float:
        """Estimates the pitcher points per game in starting role based off of calculated SP PIP values and IP/GS"""
        if row['GS'] == 0:
            return 0
        sp_pip = self.sp_pip_calc(row)
        sp_points = sp_pip * row['IP SP']
        return sp_points / row['GS']

    def rp_ppg_calc(self, row) -> float:
        """Estimates the pitcher points per game in relieving role based off of calculated RP PIP values and IP/GR"""
        if row['GP'] == row['GS']:
            return 0
        rp_pip = self.rp_pip_calc(row)
        rp_points = rp_pip * row['IP RP']
        return rp_points / (row['GP'] - row['GS'])

    def rp_no_svh_ppg_calc(self, row) -> float:
        """Estimates the pitcher points per game in relieving role based off of calculated RP PIP values and IP/GR. Does
        not include saves or holds"""
        if row['GP'] == row['GS']:
            return 0
        rp_pip = self.rp_no_svh_pip_calc(row)
        rp_points = rp_pip * row['IP RP']
        return rp_points / (row['GP'] - row['GS'])

    def rp_no_svh_pip_calc(self, row) -> float:
        """Estimates pitcher points per inning in relieving role based off of difference between overall FIP and RP FIP
        using a linear regression. Does not include saves or holds"""
        if row['IP RP'] == 0:
            return 0
        if row['IP SP'] == 0:
            return row['No SVH P/IP']
        fip_diff = row['FIP RP'] - row['FIP']
        no_svh_pip = row['No SVH P/IP'] - 1.3274 * fip_diff
        return (no_svh_pip * row['IP RP']) / row['IP RP']

    def rp_pip_calc(self, row) -> float:
        """Estimates pitcher points per inning in relieving role based off of difference between overall FIP and RP FIP
        using a linear regression."""
        if row['IP RP'] == 0:
            return 0
        if row['IP SP'] == 0:
            return row['P/IP']
        try:
            save = row['SV']
        except KeyError:
            # TODO: fill-in save calc
            save = 0
        try:
            hold = row['HLD']
        except KeyError:
            # TODO: fill-in hold calc
            hold = 0
        fip_diff = row['FIP RP'] - row['FIP']
        no_svh_pip = row['No SVH P/IP'] - 1.3274 * fip_diff
        return (no_svh_pip * row['IP RP'] + 5.0 * save + 4.0 * hold) / row['IP RP']

    def sp_multiplier_assignment(self, row) -> float:
        """Assigns a multiplier that estimates what ratio of a pitcher\'s innings will be used by a manager. The top
        num_teams*6 SP have 100% of their innings used. Each num_teams after that has the ratio decreased by a given
        percent to a minimum of 50%"""
        # We're assuming you use all innings for your top 6 pitchers, 95% of next one, 90% of the next, etc
        if row['Rank SP Rate'] <= 6 * self.num_teams:
            return 1.0
        non_top_rank = row['Rank SP Rate'] - 6 * self.num_teams
        factor = non_top_rank // self.num_teams + 1
        return max(1 - factor * 0.05, 0.5)  # TODO: Move 0.15 factor to preference

    def rp_multiplier_assignment(self, row) -> float:
        """Assigns a multiplier that estimates what ratio of a pitcher\'s innings will be used by a manager. The top
        num_teams*5 RP have 100% of their innings used. Each num_teams after that has the ratio decreased by a given
        percent to a minimum of 50%"""
        # Once you get past 5 RP per team, there are diminishing returns on how many relief innings are actually usable
        if row['Rank RP Rate'] <= 5 * self.num_teams:
            return 1.0
        non_top_rank = row['Rank RP Rate'] - 5 * self.num_teams
        factor = non_top_rank // self.num_teams + 1
        return max(1 - factor * 0.15, 0.5)  # TODO: Move 0.15 factor to preference

    def estimate_role_splits(self, df: DataFrame) -> None:
        """Estimate Innings, Rates, and ranks for pitchers in each role"""
        df['IP RP'] = df.apply(self.rp_ip_func, axis=1)
        df['IP SP'] = df.apply(self.sp_ip_func, axis=1)

        df['FIP SP'] = df.apply(self.sp_fip_calc, axis=1)
        df['FIP RP'] = df.apply(self.rp_fip_calc, axis=1)

        if self.rank_basis == RankingBasis.PIP:
            df['P/IP SP'] = df.apply(self.sp_pip_calc, axis=1)
            df['P/IP RP'] = df.apply(self.rp_pip_calc, axis=1)

            df['No SVH P/IP SP'] = df['P/IP SP']
            df['No SVH P/IP RP'] = df.apply(self.rp_no_svh_pip_calc, axis=1)

            if self.no_sv_hld:
                df['Rank SP Rate'] = df['No SVH P/IP SP'].rank(ascending=False)
                df['Rank RP Rate'] = df['No SVH P/IP RP'].rank(ascending=False)
            else:
                df['Rank SP Rate'] = df['P/IP SP'].rank(ascending=False)
                df['Rank RP Rate'] = df['P/IP RP'].rank(ascending=False)

            df['SP Multiplier'] = df.apply(self.sp_multiplier_assignment, axis=1)
            df['RP Multiplier'] = df.apply(self.rp_multiplier_assignment, axis=1)

        elif self.rank_basis == RankingBasis.PPG:
            df['P/G SP'] = df.apply(self.sp_ppg_calc, axis=1)
            df['P/G RP'] = df.apply(self.rp_ppg_calc, axis=1)

            df['No SVH P/G SP'] = df['P/G SP']
            df['No SVH P/G RP'] = df.apply(self.rp_no_svh_ppg_calc, axis=1)

            if self.no_sv_hld:
                df['Rank SP Rate'] = df['No SVH P/G SP'].rank(ascending=False)
                df['Rank RP Rate'] = df['No SVH P/G RP'].rank(ascending=False)
            else:
                df['Rank SP Rate'] = df['P/G SP'].rank(ascending=False)
                df['Rank RP Rate'] = df['P/G RP'].rank(ascending=False)

            df['SP Multiplier'] = 1
            df['RP Multiplier'] = 1

        df['SP Rankable'] = df.apply(self.pos_rankable, axis=1, args=(Position.POS_SP,))
        df['RP Rankable'] = df.apply(self.pos_rankable, axis=1, args=(Position.POS_RP,))
        df['P Rankable'] = df.apply(self.pos_rankable, axis=1, args=(Position.POS_P,))

        self.max_rost_num['SP'] = len(df.loc[df['SP Rankable']])
        self.max_rost_num['RP'] = len(df.loc[df['RP Rankable']])
        self.max_rost_num['P'] = len(df.loc[df['P Rankable']])

    def iterate_roto(self, df: DataFrame) -> float:
        df['Max FOM'] = df.apply(self.calc_max_fom, axis=1)
        sigma = 999
        orig = df['Max FOM'].sum()
        two_prior = 999
        while abs(sigma) > 2:
            self.calculate_roto_bases(df)
            self.get_pitcher_fom_calc(df, split=False)
            df['Max FOM'] = df.apply(self.calc_max_fom, axis=1)
            updated = df['Max FOM'].sum()
            sigma = orig - updated
            if two_prior == updated:
                break
            two_prior = orig
            orig = updated
            logging.debug(f'new arm sigma = {sigma}')
        return sigma

    def rank_roto_pitchers(self, df: DataFrame, rank_col: str = None, ascending=False) -> None:
        """Ranks all players eligible at each discrete pitching position according to the RankingBasis per the DataFrame columns"""
        if rank_col is None:
            rank_col = self.rank_basis.display
        for pos in Position.get_discrete_pitching_pos():
            col = f'Rank {pos.value} Rate'
            g_col = f'{pos.value} Games'
            df[g_col] = 0
            df[col] = df.loc[df[f'{pos.value} Rankable']][rank_col].rank(ascending=ascending)
            df[col] = df[col].fillna(-999)
            self.max_rost_num[pos.value] = len(df.loc[df[f'{pos.value} Rankable']])

    def roto_above_rl(self, proj: DataFrame) -> List[bool]:
        above_rl = []
        for idx, row in proj.iterrows():
            arl = False
            for pos in Position.get_discrete_pitching_pos():
                col = f'Rank {pos.value} Rate'
                if row[col] > 0 and row[col] <= self.replacement_positions.get(pos.value):
                    arl = True
                    break
            above_rl.append(arl)
        return above_rl

    def calc_rate_delta(self, row, stat: StatType) -> float:
        """Using the average of the rate stat and the team total IP calculates the change in the rate stat for the player's contributions"""
        denom = self.ip_per_team
        p_denom = row['IP']

        val = (self.stat_avg[stat] * (denom - p_denom) + row[stat.display] * p_denom) / denom - self.stat_avg[stat]
        if stat.higher_better:
            return val
        else:
            return -val

    def per_ip_rate(self, row, stat: StatType) -> float:
        """Calculates the per ip column for the stat type"""
        return row[stat.display] / row['IP']

    def per_game_rate(self, row, stat: StatType) -> float:
        """Calculates the per game column for the stat type"""
        return row[stat.display] / row['GP']

    def pos_rankable(self, row: Series, pos: Position) -> bool:
        if pos == Position.POS_SP:
            return row['IP SP'] > max(1 - self.calc_rp_ip_split_ratio(row), 0.5) * self.min_sp_ip
        if pos == Position.POS_RP:
            return row['IP RP'] > max(self.calc_rp_ip_split_ratio(row), 0.5) * self.min_rp_ip
        if pos == Position.POS_P:
            return row['IP'] > self.calc_rp_ip_split_ratio(row) * self.min_rp_ip + 1 - self.calc_rp_ip_split_ratio(row) * self.min_sp_ip

    def calculate_roto_bases(self, proj: DataFrame, init=False) -> None:
        """Calculates zScore information (average and stdev of the 4x4 or 5x5 stats). If init is true, will rank off of WHIP, otherwise ranks off of previous zScores"""
        if init:
            self.rank_roto_pitchers(proj, rank_col='WHIP', ascending=True)
        else:
            self.rank_roto_pitchers(proj)
        alr = self.roto_above_rl(proj)
        above_rep_lvl = proj.loc[alr]
        self.ip_per_team = above_rep_lvl['IP'].sum() / self.num_teams
        self.g_per_team = above_rep_lvl['GP'].sum() / self.num_teams

        if self.s_format == ScoringFormat.CUSTOM:
            cat_to_col = {}
            for cat in self.scoring.stats:
                if cat.category.hitter:
                    continue
                if cat.category.rate_denom is None:
                    if RankingBasis.is_roto_fractional(self.rank_basis):
                        proj[f'{cat.category.display}/IP'] = proj.apply(self.per_ip_rate, axis=1, args=(cat.category,))
                    cat_to_col[cat.category] = cat.category.display
                else:
                    self.stat_avg[cat.category] = dataframe_util.weighted_avg(above_rep_lvl, cat.category.display, cat.category.rate_denom.display)
                    proj[f'{cat.category.display}_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(cat.category,))
                    cat_to_col[cat.category] = f'{cat.category.display}_Delta'
        else:
            self.stat_avg[StatType.ERA] = dataframe_util.weighted_avg(above_rep_lvl, 'ERA', 'IP')
            proj['ERA_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(StatType.ERA,))
            self.stat_avg[StatType.WHIP] = dataframe_util.weighted_avg(above_rep_lvl, 'WHIP', 'IP')
            proj['WHIP_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(StatType.WHIP,))

            if RankingBasis.is_roto_fractional(self.rank_basis):
                proj['K/IP'] = proj.apply(self.per_ip_rate, axis=1, args=(StatType.SO,))
                if self.s_format == ScoringFormat.OLD_SCHOOL_5X5:
                    proj['SV/G'] = proj.apply(self.per_game_rate, axis=1, args=(StatType.SV,))
                    proj['W/G'] = proj.apply(self.per_game_rate, axis=1, args=(StatType.W,))
                    cat_to_col = {StatType.SO: 'K/IP', StatType.W: 'W/G', StatType.SV: 'SV/G', StatType.WHIP: 'WHIP_Delta', StatType.ERA: 'ERA_Delta'}
                else:
                    self.stat_avg[StatType.HR_PER_9] = dataframe_util.weighted_avg(above_rep_lvl, 'HR/9', 'IP')
                    proj['HR/9_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(StatType.HR_PER_9,))
                    cat_to_col = {StatType.SO: 'K/IP', StatType.ERA: 'ERA_Delta', StatType.WHIP: 'WHIP_Delta', StatType.HR_PER_9: 'HR/9_Delta'}
            else:
                if self.s_format == ScoringFormat.OLD_SCHOOL_5X5:
                    cat_to_col = {StatType.SO: 'K', StatType.W: 'W', StatType.SV: 'SV', StatType.WHIP: 'WHIP_Delta', StatType.ERA: 'ERA_Delta'}
                else:
                    self.stat_avg[StatType.HR_PER_9] = dataframe_util.weighted_avg(above_rep_lvl, 'HR/9', 'IP')
                    proj['HR/9_Delta'] = proj.apply(self.calc_rate_delta, axis=1, args=(StatType.HR_PER_9,))
                    cat_to_col = {StatType.SO: 'K', StatType.ERA: 'ERA_Delta', StatType.WHIP: 'WHIP_Delta', StatType.HR_PER_9: 'HR/9_Delta'}
        above_rep_lvl = proj.loc[alr]
        means = above_rep_lvl[list(cat_to_col.values())].mean()
        stds = above_rep_lvl[list(cat_to_col.values())].std()
        for cat, col in cat_to_col.items():
            if cat.rate_denom is None:
                self.stat_avg[cat] = means[col]
            self.stat_std[cat] = stds[col]

        col = self.rank_basis.display
        proj[col] = proj.apply(self.calc_z_score, axis=1)

    def calc_z_score(self, row) -> float:
        """Calculates the zScore for the player row"""
        if RankingBasis.is_roto_fractional(self.rank_basis):
            ip_suffix = '/IP'
            g_suffix = '/G'
            ip_rat = row['IP'] / self.ip_per_team
            g_rat = row['GP'] / self.g_per_team
        else:
            ip_suffix = g_suffix = ''
            ip_rat = g_rat = 1
        zScore = 0
        if self.s_format == ScoringFormat.CUSTOM:
            for cat in self.scoring.stats:
                if cat.category.hitter:
                    continue
                if cat.category.rate_denom is None:
                    if cat.category.higher_better:
                        mult = 1
                    else:
                        mult = -1
                    zScore += mult * (row[f'{cat.category.display}{ip_suffix}'] - self.stat_avg.get(cat.category)) / self.stat_std.get(cat.category) * ip_rat
                else:
                    zScore += row[f'{cat.category.display}_Delta'] / self.stat_std.get(cat.category)
        else:
            zScore += (row[f'K{ip_suffix}'] - self.stat_avg.get(StatType.SO)) / self.stat_std.get(StatType.SO) * ip_rat
            zScore += row['ERA_Delta'] / self.stat_std.get(StatType.ERA)
            zScore += row['WHIP_Delta'] / self.stat_std.get(StatType.WHIP)
            if self.s_format == ScoringFormat.OLD_SCHOOL_5X5:
                zScore += (row[f'W{g_suffix}'] - self.stat_avg.get(StatType.W)) / self.stat_std.get(StatType.W) * g_rat
                zScore += (row[f'SV{g_suffix}'] - self.stat_avg.get(StatType.SV)) / self.stat_std.get(StatType.SV) * g_rat
            else:
                zScore += row['HR/9_Delta'] / self.stat_std.get(StatType.HR_PER_9)
        return zScore

    def calc_fom(self, df: DataFrame) -> DataFrame:
        """Returns a populated DataFrame with all required FOM information for all players above the minimum IP at all positions."""
        if ScoringFormat.is_points_type(self.s_format):
            df['Points'] = df.apply(self.calc_pitch_points, axis=1)
            df['No SVH Points'] = df.apply(self.calc_pitch_points_no_svh, axis=1)

            df['P/IP'] = df.apply(self.calc_ppi, axis=1)
            df['No SVH P/IP'] = df.apply(self.calc_ppi_no_svh, axis=1)
            if self.rank_basis == RankingBasis.PPG:
                df['P/G'] = df.apply(self.calc_ppg, axis=1)
                df['No SVH P/G'] = df.apply(self.calc_ppg_no_svh, axis=1)

            # Filter to pitchers projected to a baseline amount of playing time
            real_pitchers = df.loc[df.apply(self.not_a_belly_itcher_filter, axis=1)]

            self.estimate_role_splits(real_pitchers)
        else:
            if self.rank_basis == RankingBasis.SGP:
                # TODO: Implement SGP
                ...
            else:
                real_pitchers = df.loc[df.apply(self.not_a_belly_itcher_filter, axis=1)]
                real_pitchers['IP RP'] = real_pitchers.apply(self.rp_ip_func, axis=1)
                real_pitchers['IP SP'] = real_pitchers.apply(self.sp_ip_func, axis=1)
                real_pitchers['SP Rankable'] = real_pitchers.apply(self.pos_rankable, axis=1, args=(Position.POS_SP,))
                real_pitchers['RP Rankable'] = real_pitchers.apply(self.pos_rankable, axis=1, args=(Position.POS_RP,))
                real_pitchers['P Rankable'] = real_pitchers.apply(self.pos_rankable, axis=1, args=(Position.POS_P,))
                real_pitchers['SP Multiplier'] = 1
                real_pitchers['RP Multiplier'] = 1
                self.calculate_roto_bases(real_pitchers, init=True)

        real_pitchers = self.get_pitcher_fom(real_pitchers)

        if self.intermediate_calculations:
            self.dirname = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            self.intermed_subdirpath = os.path.join(self.dirname, 'data_dirs', 'intermediate')
            if not path.exists(self.intermed_subdirpath):
                os.mkdir(self.intermed_subdirpath)
            filepath = os.path.join(self.intermed_subdirpath, 'pitch_ranks.csv')
            real_pitchers.to_csv(filepath, encoding='utf-8-sig')

        return real_pitchers
