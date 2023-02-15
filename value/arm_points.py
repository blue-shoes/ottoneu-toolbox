import pandas as pd
from pandas import DataFrame
import os
from os import path
from copy import deepcopy

from domain.domain import ValueCalculation
from domain.enum import RepLevelScheme, RankingBasis, CalculationDataType as CDT, ScoringFormat

pd.options.mode.chained_assignment = None # from https://stackoverflow.com/a/20627316

class ArmPoint():

    default_replacement_positions = {"SP":60,"RP":30}
    default_replacement_levels = {}
    default_surplus_pos = {"SP": 0, "RP": 0}
    weeks = 26
    max_rost_num = {}

    def __init__(self, value_calc:ValueCalculation, intermediate_calc=False, target_arm=196, rp_limit=999):
        self.intermediate_calculations = intermediate_calc
        self.replacement_positions = deepcopy(self.default_replacement_positions)
        self.replacement_levels = deepcopy(self.default_replacement_levels)
        self.target_pitch = target_arm
        self.SABR = ScoringFormat.is_sabr(value_calc.format)
        self.rp_limit = rp_limit
        self.rep_level_scheme = RepLevelScheme._value2member_map_[int(value_calc.get_input(CDT.REP_LEVEL_SCHEME))]
        self.num_teams = value_calc.get_input(CDT.NUM_TEAMS)
        self.surplus_pos = deepcopy(self.default_surplus_pos)
        self.min_sp_ip = value_calc.get_input(CDT.SP_IP_TO_RANK)
        self.min_rp_ip = value_calc.get_input(CDT.RP_IP_TO_RANK)
        self.rank_basis = value_calc.pitcher_basis
        self.scoring_format = value_calc.format
        
        self.no_sv_hld = value_calc.get_input(CDT.INCLUDE_SVH) == 0
        
        if ScoringFormat.is_h2h(self.scoring_format):
            self.gs_per_week = value_calc.get_input(CDT.GS_LIMIT)
            self.est_rp_g_per_week = value_calc.get_input(CDT.RP_G_TARGET)
        else:
            self.target_innings = value_calc.get_input(CDT.IP_TARGET) * self.num_teams
            self.ip_per_team = value_calc.get_input(CDT.IP_TARGET)
            self.rp_ip_per_team = value_calc.get_input(CDT.RP_IP_TARGET)

        if intermediate_calc:
            self.dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
            self.intermed_subdirpath = os.path.join(self.dirname, 'data_dirs','intermediate')
            if not path.exists(self.intermed_subdirpath):
                os.mkdir(self.intermed_subdirpath)

    def pitch_points_engine(self, row, save:float, hold:float) -> float:
        '''Returns player pitching points for projection row using input save and hold values. HBP filled via regression
        if not available'''
        #This HBP approximation is from a linear regression I did when I first did values
        try:
            hbp = row['HBP']
        except KeyError:
            #Ask forgiveness, not permission
            hbp = 0.0951*row['BB']+0.4181
        
        if(self.SABR):
            #Otto pitching points (SABR) from https://ottoneu.fangraphs.com/support
            return 5.0*row['IP']+2.0*row['SO']-3.0*row['BB']-3.0*hbp-13.0*row['HR']+5.0*save+4.0*hold
        else:
            #Otto pitching points (FGP) from https://ottoneu.fangraphs.com/support
            return 7.4*row['IP']+2.0*row['SO']-2.6*row['H']-3.0*row['BB']-3.0*hbp-12.3*row['HR']+5.0*save+4.0*hold

    def calc_pitch_points(self, row) -> float:
        '''Returns player pitching points for projection row using row columns.'''
        try:
            save = row['SV']
        except KeyError:
            #TODO: fill-in save calc
            save = 0
        try:
            hold = row['HLD']
        except KeyError:
            #TODO: fill-in hold calc
            hold = 0
        return self.pitch_points_engine(row, save, hold)

    def calc_pitch_points_no_svh(self, row) -> float:
        '''Returns player pitching points for projection row using input and setting zero saves/holds'''
        return self.pitch_points_engine(row, 0, 0)

    def calc_ppi(self, row) -> float:
        '''Calculate points per inning based on known columns'''
        if row['IP'] == 0:
            return 0
        return row['Points'] / row['IP']
    
    def calc_ppg(self, row) -> float:
        '''Calculate points per game based on known columns'''
        if row['G'] == 0:
            return 0
        return row['Points'] / row['G']

    def calc_ppi_no_svh(self, row) -> float:
        '''Calculate points per inning with no saves/holds based on known columns'''
        if row['IP'] == 0:
            return 0
        return row['No SVH Points'] / row['IP']
    
    def calc_ppg_no_svh(self, row) -> float:
        '''Calculate points per game with no saves/holds based on known columns'''
        if row['G'] == 0:
            return 0
        return row['No SVH Points'] / row['G']

    def get_pitcher_par(self, df:DataFrame) -> DataFrame:
        
        if self.rep_level_scheme == RepLevelScheme.STATIC_REP_LEVEL:
            self.get_par(df)
            self.set_number_rostered(df)
        else:
            num_arms = 0
            total_ip = 0
            self.get_pitcher_par_calc(df)

            rosterable = df.loc[df['PAR'] >= 0]
            sp_ip = rosterable.apply(self.usable_ip_calc, args=("SP",), axis=1).sum()
            rp_ip = rosterable.apply(self.usable_ip_calc, args=("RP",), axis=1).sum()
            total_ip = sp_ip + rp_ip

            sp_g = rosterable.apply(self.usable_gs_calc, axis=1).sum()
            rp_g = rosterable.apply(self.usable_rp_g_calc, axis=1).sum()

            if self.rep_level_scheme == RepLevelScheme.FILL_GAMES:
                if not ScoringFormat.is_h2h(self.scoring_format):
                    while sp_ip < self.num_teams * (self.ip_per_team-self.rp_ip_per_team) and self.replacement_positions['SP'] < self.max_rost_num['SP']:
                        self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                        self.get_pitcher_par_calc(df)
                        rosterable = df.loc[df['PAR'] >= 0]
                        sp_ip = rosterable.apply(self.usable_ip_calc, args=("SP",), axis=1).sum()
                    while rp_ip < self.num_teams * self.rp_ip_per_team and self.replacement_positions['RP'] < self.max_rost_num['RP']:
                        self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        self.get_pitcher_par_calc(df)
                        rosterable = df.loc[df['PAR'] >= 0]
                        rp_ip = rosterable.apply(self.usable_ip_calc, args=("RP",), axis=1).sum()
                else:
                    while sp_g < self.num_teams * self.gs_per_week * self.weeks and self.replacement_positions['SP'] < self.max_rost_num['SP']:
                        self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                        self.get_pitcher_par_calc(df)
                        rosterable = df.loc[df['PAR'] >= 0]
                        sp_g = rosterable.apply(self.usable_gs_calc, axis=1).sum()
                    while rp_g < self.num_teams * self.est_rp_g_per_week * self.weeks and self.replacement_positions['RP'] < self.max_rost_num['RP']:
                        self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        self.get_pitcher_par_calc(df)
                        rosterable = df.loc[df['PAR'] >= 0]
                        rp_g = rosterable.apply(self.usable_rp_g_calc, axis=1).sum()
                self.replacement_positions['SP'] = min(self.replacement_positions['SP'] + self.surplus_pos['SP'], self.max_rost_num['SP'])
                self.replacement_positions['RP'] = min(self.replacement_positions['RP'] + self.surplus_pos['RP'], self.max_rost_num['RP'])
                self.get_pitcher_par_calc(df)

            elif self.rep_level_scheme == RepLevelScheme.TOTAL_ROSTERED:
                if self.rank_basis == RankingBasis.PIP:
                    while (num_arms != self.target_pitch or (abs(total_ip-self.target_innings) > 100 and self.replacement_positions['RP'] != self.rp_limit)) and (self.replacement_positions['SP'] < self.max_rost_num['SP'] and self.replacement_positions['RP'] < self.max_rost_num['RP']):
                        #Going to do optional capping of relievers. It can get a bit out of control otherwise
                        if num_arms < self.target_pitch and (self.replacement_positions['RP'] == self.rp_limit or self.replacement_positions['RP'] < self.max_rost_num['RP']):
                            self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                        elif num_arms == self.target_pitch:
                            #We have the right number of arms, but not in the inning threshold
                            if total_ip < self.target_innings:
                                #Too many relievers
                                if self.replacement_positions['SP'] == self.max_rost_num['SP']:
                                    #Don't have any more starters, this is optimal
                                    break
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] - 1
                            else:
                                #Too many starters
                                if self.replacement_positions['RP'] == self.max_rost_num['RP']:
                                    #Don't have any more relievers, this is optimal
                                    break
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] - 1
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        elif num_arms < self.target_pitch:
                            if self.target_pitch-num_arms == 1 and self.target_innings - total_ip > 200 and self.replacement_positions['SP'] < self.max_rost_num['SP']:
                                #Add starter, a reliever isn't going to get it done, so don't bother
                                #I got caught in a loop without this
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                            #Not enough pitchers. Preferentially add highest replacement level
                            elif (self.replacement_levels['SP'] > self.replacement_levels['RP'] and self.replacement_positions['SP'] < self.max_rost_num['SP']) or self.replacement_positions['RP'] == self.max_rost_num['RP']:
                                #Probably not, but just in case
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                            else:
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        else:
                            if self.target_pitch-num_arms == -1 and self.target_innings - total_ip > 50:
                                #Remove a reliever. We're already short on innings, so removing a starter isn't going to get it done, so don't bother
                                #I got caught in a loop without this
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] - 1
                            #Too many pitchers. Preferentially remove lowest replacement level
                            elif self.replacement_levels['SP'] < self.replacement_levels['RP']:
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] - 1
                            else:
                                #Probably not, but just in case
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] - 1
                        self.get_pitcher_par_calc(df)
                        #FOM is how many arms with a non-negative PAR...
                        rosterable = df.loc[df['PAR'] >= 0]
                        num_arms = len(rosterable)
                        #...and how many total innings are pitched
                        total_ip = rosterable.apply(self.usable_ip_calc, args=("SP",), axis=1).sum()
                        total_ip += rosterable.apply(self.usable_ip_calc, args=("RP",), axis=1).sum()
                elif self.rank_basis == RankingBasis.PPG:
                    target_starts = self.num_teams * self.gs_per_week * self.weeks
                    while num_arms != self.target_pitch or abs(sp_g-target_starts) > 10 and (self.replacement_positions['SP'] < self.max_rost_num['SP'] and self.replacement_positions['RP'] < self.max_rost_num['RP']):
                        #Going to do optional capping of relievers. It can get a bit out of control otherwise
                        if num_arms < self.target_pitch and self.replacement_positions['RP'] == self.rp_limit and self.replacement_positions['SP'] < self.max_rost_num['SP']:
                            self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                        elif num_arms == self.target_pitch:
                            #We have the right number of arms, but not in the inning threshold
                            if sp_g < target_starts:
                                #Too many relievers
                                if self.replacement_positions['SP'] == self.max_rost_num['SP']:
                                    #Don't have any more SP, this is optimal
                                    break
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] - 1
                            else:
                                #Too many starters
                                if self.replacement_positions['RP'] == self.max_rost_num['RP']:
                                    #Don't have any more RP, this is optimal
                                    break
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] - 1
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        elif num_arms < self.target_pitch:
                            if (target_starts - sp_g > 10 and self.replacement_positions['SP'] < self.max_rost_num['SP']) or self.replacement_positions['RP'] == self.max_rost_num['RP']:
                                #Add starter
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] + 1
                            else:
                                #Have enough starts, add reliever
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] + 1
                        else:
                            if self.target_pitch-num_arms == -1 and target_starts - sp_g < -20:
                                #Remove a starter. We probably have enough GS
                                #I got caught in a loop without this
                                self.replacement_positions['SP'] = self.replacement_positions['SP'] - 1
                            #Too many pitchers and we don't have enough starts
                            else:
                                self.replacement_positions['RP'] = self.replacement_positions['RP'] - 1
                        self.get_pitcher_par_calc(df)
                        #FOM is how many arms with a non-negative PAR...
                        rosterable = df.loc[df['PAR'] >= 0]
                        num_arms = len(rosterable)
                        #...and how many GS
                        sp_g = rosterable.apply(self.usable_gs_calc, axis=1).sum()
            elif self.rep_level_scheme == RepLevelScheme.NUM_ROSTERED:
                self.get_pitcher_par_calc(df)
            else:
                raise Exception("Unusable Replacement Level Scheme")
        
        if(self.intermediate_calculations):
            filepath = os.path.join(self.intermed_subdirpath, f"pit_rost.csv")
            rosterable.to_csv(filepath, encoding='utf-8-sig')
            filepath = os.path.join(self.intermed_subdirpath, f"df_tot.csv")
            df.to_csv(filepath, encoding='utf-8-sig')

        return df

    def usable_ip_calc(self, row, role:str) -> float:
        '''Returns an estimated usable number of innings pitched based on the projection and pitcher ranking'''
        return row[f'IP {role}'] * row[f'{role} Multiplier']

    def usable_par_calc(self, row, role) -> float:
        '''Returns an estimated usable number of pitching PAR based on the projection and pitcher ranking'''
        return row[f'PAR {role}'] * row[f'{role} Multiplier']

    def usable_gs_calc(self, row) -> float:
        '''Returns an estimated usable number of games started based on the projection and pitcher ranking'''
        return row['GS'] * row['SP Multiplier']
    
    def usable_rp_g_calc(self, row) -> float:
        '''Returns an estimated usable number of relief games pitched based on the projection and pitcher ranking'''
        return (row['G'] - row['GS']) * row['RP Multiplier']

    def get_pitcher_par_calc(self, df:DataFrame) -> None:
        '''Sets replacement levels for the current iteration and populates PAR figures for all pitchers and roles'''
        sp_rep_level = self.get_pitcher_rep_level(df, 'SP')
        self.replacement_levels['SP'] = sp_rep_level
        rp_rep_level = self.get_pitcher_rep_level(df, 'RP')
        self.replacement_levels['RP'] = rp_rep_level
        self.get_par(df)

    def get_par(self, df:DataFrame) -> None:
        '''Calculates role PARs and overall PAR for each pitcher in-place'''
        df['PAR SP'] = df.apply(self.calc_pitch_par_role, args=('SP', self.replacement_levels['SP']), axis=1)
        df['PAR RP'] = df.apply(self.calc_pitch_par_role, args=('RP', self.replacement_levels['RP']), axis=1)
        df['PAR'] = df.apply(self.sum_role_par, axis=1)
    
    def set_number_rostered(self, df:DataFrame) -> None:
        '''Determines what number pitcher represents replacement level for all roles and sets it in the internal dict'''
        sp_count = 0
        rp_count = 0
        for idx, row in df.iterrows():
            if row['PAR'] > 0:
                if 'SP' in row['Position(s)']:
                    sp_count += 1
                if 'RP' in row['Position(s)']:
                    rp_count += 1
        self.replacement_positions['SP'] = sp_count
        self.replacement_positions['RP'] = rp_count

    def calc_pitch_par_role(self, row, role:str, rep_level:float) -> float:
        '''Returns the PAR accumulated by the pitcher in the given role at the given replacement level.'''
        if row['G'] == 0:
            return -1
        if row[f'IP {role}'] == 0: return -1
        if self.no_sv_hld:
            prefix = 'No SVH '
        else:
            prefix = ''
        if self.rank_basis == RankingBasis.PIP:
            rate = row[f'{prefix}P/IP {role}'] - rep_level
            return rate * row[f'IP {role}']
        elif self.rank_basis == RankingBasis.PPG:
            rate = row[f'{prefix}PPG {role}'] - rep_level
            if role == 'SP':
                return rate * row['GS']
            else:
                return rate * (row['G'] - row['GS'])

    def sum_role_par(self, row) -> float:
        '''Sums the pitcher's SP and RP PAR values'''
        sp_par = row['PAR SP']
        if row['IP SP'] == 0:
            sp_par = 0
        rp_par = row['PAR RP']
        if row['IP RP'] == 0:
            rp_par = 0
        return sp_par + rp_par

    def get_pitcher_rep_level(self, df:DataFrame, pos:str) -> float:
        '''Returns pitcher role replacement level based on current rank value in replacement_positions dict'''
        #Filter DataFrame to just the position of interest
        if pos == 'RP':
            min_ip = self.min_rp_ip
        else:
            min_ip = self.min_sp_ip
        pitch_df = df.loc[df[f'IP {pos}'] >= min_ip]
        if self.no_sv_hld:
            prefix = 'No SVH '
        else:
            prefix = ''
        if self.rank_basis == RankingBasis.PIP:
            sort_col = f"{prefix}P/IP {pos}"
        elif self.rank_basis == RankingBasis.PPG:
            sort_col = f"{prefix}PPG {pos}"
        pitch_df = pitch_df.sort_values(sort_col, ascending=False)
        #Get the nth value (here the # of players rostered at the position - 1 for 0 index) from the sorted data
        return pitch_df.iloc[self.replacement_positions[pos] - 1][sort_col]

    def not_a_belly_itcher_filter(self, row) -> bool:
        '''Determines if pitcher has sufficient innings to be included in replacement level calculations. Split role
        pitchers have their innings rationed to role and are checked against an interpolated value.'''
        #Filter pitchers from the data set who don't reach requisite innings. These thresholds are arbitrary.
        if row['Position(s)'] == 'SP':
            return row['IP'] >= self.min_sp_ip
        if row['Position(s)'] == 'RP':
            return row['IP'] >= self.min_rp_ip
        if row['G'] == 0: return False
        #Got to here, this is a SP/RP with > 0 G. Ration their innings threshold based on their projected GS/G ratio
        start_ratio = row['GS'] / row['G']
        return row['IP'] > (self.min_sp_ip - self.min_rp_ip)*start_ratio + self.min_rp_ip

    def rp_ip_func(self, row) -> float:
        '''Calculates the number of innings pitched in relief based on a linear regression using games relieved per total
        games as the independent variable.'''
        #Avoid divide by zero error
        if row['G'] == 0: return 0
        #Only relief appearances
        if row['GS'] == 0: return row['IP']
        #Only starting appearances
        if row['GS'] == row['G']: return 0
        #Based on second-order poly regression performed for all pitcher seasons from 2019-2021 with GS > 0 and GRP > 0
        #Regression has dep variable of GRP/G (or (G-GS)/G) and IV IPRP/IP. R^2=0.9481. Possible issues with regression: overweighting
        #of pitchers with GRP/G ratios very close to 0 (starters with few RP appearances) or 1 (relievers with few SP appearances)
        gr_per_g = (row['G'] - row['GS']) / row['G']
        return row['IP'] * (0.7851*gr_per_g**2 + 0.1937*gr_per_g + 0.0328)

    def sp_ip_func(self, row) -> float:
        '''Calculates the number of innings pitched in starts based on previously calculated relief innings.'''
        return row['IP'] - row['IP RP']

    def sp_fip_calc(self, row) -> float:
        '''Estimates pitcher FIP in the starting role based on overall FIP and number of innings pitched in starts. Assumes
        approximately a 0.6 point improvement in FIP when transitioning from SP to RP based on historical analysis.'''
        if row['IP RP'] == 0: return row['FIP']
        if row['IP SP'] == 0: return 0
        #Weighted results from 2019-2021 dataset shows an approxiately 0.6 FIP improvement from SP to RP
        return (row['IP']*row['FIP'] + 0.6*row['IP RP']) / row['IP']

    def rp_fip_calc(self, row) -> float:
        '''Estimates pitcher FIP in the relieving role based on the previously calculated starter FIP and subtracting 0.6 based
        on historical analysis'''
        if row['IP RP'] == 0: return 0
        if row['IP SP'] == 0: return row['FIP']
        return row['FIP SP'] -0.6

    def sp_pip_calc(self, row) -> float:
        '''Estimates pitcher points per inning in starting role based off of difference between overall FIP and SP FIP
        using a linear regression.'''
        if row['IP SP'] == 0: return 0
        #Regression of no SVH P/IP from FIP gives linear coefficient of -1.3274
        fip_diff = row['FIP SP'] - row['FIP']
        return row['No SVH P/IP'] -1.3274*fip_diff
    
    def sp_ppg_calc(self, row) -> float:
        '''Estimates the pitcher points per game in starting role based off of calculated SP PIP values and IP/GS'''
        if row['GS'] == 0:
            return 0
        sp_pip = self.sp_pip_calc(row)
        sp_points = sp_pip * row['IP SP']
        return sp_points / row['GS']

    def rp_ppg_calc(self, row) -> float:
        '''Estimates the pitcher points per game in relieving role based off of calculated RP PIP values and IP/GR'''
        if row['G'] == row['GS']:
            return 0
        rp_pip = self.rp_pip_calc(row)
        rp_points = rp_pip * row['IP RP']
        return rp_points / (row['G'] - row['GS'])
    
    def rp_no_svh_ppg_calc(self, row) -> float:
        '''Estimates the pitcher points per game in relieving role based off of calculated RP PIP values and IP/GR. Does
        not include saves or holds'''
        if row['G'] == row['GS']:
            return 0
        rp_pip = self.rp_no_svh_pip_calc(row)
        rp_points = rp_pip * row['IP RP']
        return rp_points / (row['G'] - row['GS'])
    
    def rp_no_svh_pip_calc(self, row) -> float:
        '''Estimates pitcher points per inning in relieving role based off of difference between overall FIP and RP FIP
        using a linear regression. Does not include saves or holds'''
        if row['IP RP'] == 0: return 0
        if row['IP SP'] == 0: return row['No SVH P/IP']
        fip_diff = row['FIP RP'] - row['FIP']
        no_svh_pip = row['No SVH P/IP'] - 1.3274*fip_diff 
        return (no_svh_pip * row['IP RP'])/row['IP RP'] 

    def rp_pip_calc(self, row) -> float:
        '''Estimates pitcher points per inning in relieving role based off of difference between overall FIP and RP FIP
        using a linear regression.'''
        if row['IP RP'] == 0: return 0
        if row['IP SP'] == 0: return row['P/IP']
        try:
            save = row['SV']
        except KeyError:
            #TODO: fill-in save calc
            save = 0
        try:
            hold = row['HLD']
        except KeyError:
            #TODO: fill-in hold calc
            hold = 0
        fip_diff = row['FIP RP'] - row['FIP']
        no_svh_pip = row['No SVH P/IP'] - 1.3274*fip_diff 
        return (no_svh_pip * row['IP RP'] + 5.0*save + 4.0*hold)/row['IP RP'] 

    def sp_multiplier_assignment(self, row) -> float:
        '''Assigns a multiplier that estimates what ratio of a pitcher\'s innings will be used by a manager. The top
        num_teams*6 SP have 100% of their innings used. Each num_teams after that has the ratio decreased by a given
        percent to a minimum of 50%'''
        #We're assuming you use all innings for your top 6 pitchers, 95% of next one, 90% of the next, etc
        if row['Rank SP Rate'] <=6 * self.num_teams:
            return 1.0
        non_top_rank = row['Rank SP Rate'] - 6 * self.num_teams
        factor = non_top_rank // self.num_teams + 1
        return max(1 - factor * 0.05, 0.5) #TODO: Move 0.15 factor to preference

    def rp_multiplier_assignment(self, row) -> float:
        '''Assigns a multiplier that estimates what ratio of a pitcher\'s innings will be used by a manager. The top
        num_teams*5 RP have 100% of their innings used. Each num_teams after that has the ratio decreased by a given
        percent to a minimum of 50%'''
        #Once you get past 5 RP per team, there are diminishing returns on how many relief innings are actually usable
        if row['Rank RP Rate'] <=5 * self.num_teams:
            return 1.0
        non_top_rank = row['Rank RP Rate'] - 5 * self.num_teams
        factor = non_top_rank // self.num_teams + 1
        return max(1 - factor * 0.15, 0.5) #TODO: Move 0.15 factor to preference

    def estimate_role_splits(self, df:DataFrame) -> None:
        '''Estimate Innings, Rates, and ranks for pitchers in each role'''
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
            df['PPG SP'] = df.apply(self.sp_ppg_calc, axis=1)
            df['PPG RP'] = df.apply(self.rp_ppg_calc, axis=1)

            df['No SVH PPG SP'] = df['PPG SP']
            df['No SVH PPG RP'] = df.apply(self.rp_no_svh_ppg_calc, axis=1)

            if self.no_sv_hld:
                df['Rank SP Rate'] = df['No SVH PPG SP'].rank(ascending=False)
                df['Rank RP Rate'] = df['No SVH PPG RP'].rank(ascending=False)
            else:
                df['Rank SP Rate'] = df['PPG SP'].rank(ascending=False)
                df['Rank RP Rate'] = df['PPG RP'].rank(ascending=False)

            df['SP Multiplier'] = 1
            df['RP Multiplier'] = 1
        
        self.max_rost_num['SP'] = len(df.loc[df[f'IP SP'] >= self.min_sp_ip])
        self.max_rost_num['RP'] = len(df.loc[df['IP RP'] >= self.min_rp_ip])

    def calc_par(self, df:DataFrame) -> DataFrame:
        '''Returns a populated DataFrame with all required PAR information for all players above the minimum IP at all positions.'''
        df['Points'] = df.apply(self.calc_pitch_points, axis=1)
        df['No SVH Points'] = df.apply(self.calc_pitch_points_no_svh, axis=1)

        df['P/IP'] = df.apply(self.calc_ppi, axis=1)
        df['No SVH P/IP'] = df.apply(self.calc_ppi_no_svh, axis=1)
        if self.rank_basis == RankingBasis.PPG:
            df['PPG'] = df.apply(self.calc_ppg, axis=1)
            df['No SVH PPG'] = df.apply(self.calc_ppg_no_svh, axis=1)

        #Filter to pitchers projected to a baseline amount of playing time
        real_pitchers = df.loc[df.apply(self.not_a_belly_itcher_filter, axis=1)]

        self.estimate_role_splits(real_pitchers)

        real_pitchers = self.get_pitcher_par(real_pitchers)

        return real_pitchers