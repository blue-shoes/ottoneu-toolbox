from cmath import pi
import pandas as pd
import numpy as np
import scrape_fg as scrape
import os
from os import path

from scrape_ottoneu import Scrape_Ottoneu

pd.options.mode.chained_assignment = None # from https://stackoverflow.com/a/20627316

bat_pos = ['C','1B','2B','3B','SS','OF','Util']
pitch_pos = ['SP','RP']
target_innings = 1500.0*12.0
#replacement_positions = {"C":24,"1B":40,"2B":38,"3B":40,"SS":42,"OF":95,"Util":200,"SP":85,"RP":70}
#These are essentially minimums for the positions. I would really not expect to go below these. C and Util are unaffected by the algorithm
replacement_positions = {"C":24,"1B":12,"2B":18,"3B":12,"SS":18,"OF":60,"Util":200,"SP":60,"RP":60}
replacement_levels = {}

class PointValues():

    def __init__(self, projection='steamer', depthchart_pt=False, ros=False, debug=False, rostered_hitters=244, rostered_pitchers=196,
                    rp_limit=999, SABR_points=False, force_proj_download=False):
        self.projection = projection
        self.depthchart_pt = depthchart_pt
        self.ros = ros
        self.intermediate_calculations = debug
        self.target_bat = rostered_hitters
        self.target_pitch = rostered_pitchers
        self.rp_limit = rp_limit
        self.SABR = SABR_points
        self.force = force_proj_download

        #Initialize directory for intermediate calc files if required
        self.dirname = os.path.dirname(__file__)
        self.intermed_subdirpath = os.path.join(self.dirname, 'intermediate')
        if not path.exists(self.intermed_subdirpath):
            os.mkdir(self.intermed_subdirpath)


    def set_positions(self, df, positions):
        df = df.merge(positions[['Position(s)', 'OttoneuID']], how='left', left_index=True, right_index=True)
        #Some projections can be not in the Otto-verse, so set their Ottoneu ID to -1
        df['OttoneuID'] = df['OttoneuID'].fillna(-1) 
        df['OttoneuID'] = df['OttoneuID'].astype(int)
        #Players not in the Otto-verse need a position
        df['Position(s)'] = df['Position(s)'].fillna('Util')
        df['Team'] = df['Team'].fillna('---')
        return df

    def convertToDcPlayingTime(self, proj, dc_proj, position):
        #String and rate columns that are unaffected
        static_columns = ['playerid', 'Name', 'Team','-1','AVG','OBP','SLG','OPS','wOBA','wRC+','ADP','WHIP','K/9','BB/9','ERA','FIP']
        #Columns directly taken from DC
        dc_columns = ['G','PA','GS','IP']
        #Filter projection to only players present in the DC projection and then drop the temp DC column
        proj = proj.assign(DC=proj.index.isin(dc_proj.index).astype(bool))
        proj = proj[proj['DC'] == True]
        proj.drop('DC', axis=1, inplace=True)
        if position:
            denom = 'PA'
        else:
            denom = 'IP'
        for column in proj.columns:
            if column in static_columns:
                continue
            elif column in dc_columns:
                #take care of this later so we can do the rate work first
                continue
            else:
                #Ration the counting stat
                proj[column] = proj[column] / proj[denom] * dc_proj[denom]
        #We're done with the original projection denominator columns, so now set them to the DC values
        for column in dc_columns:
            if column in proj.columns:
                proj[column] = dc_proj[column]
        return proj

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

    def pitch_points_engine(self, row, save, hold):
        #This HBP approximation is from a linear regression is did when I first did values
        try:
            hbp = row['HBP']
        except KeyError:
            #Ask forgiveness, not permission
            hbp = 0.0951*row['BB']+0.4181
        
        if(self.SABR):
            #Otto pitching points (SABR) from https://ottoneu.fangraphs.com/support
            return 7.4*row['IP']+2.0*row['SO']-3.0*row['BB']-3.0*hbp-13.0*row['HR']+5.0*save+4.0*hold
        else:
            #Otto pitching points (FGP) from https://ottoneu.fangraphs.com/support
            return 5.0*row['IP']+2.0*row['SO']-2.6*row['H']-3.0*row['BB']-3.0*hbp-12.3*row['HR']+5.0*save+4.0*hold

    def calc_pitch_points(self, row):
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

    def calc_pitch_points_no_svh(self, row):
        return self.pitch_points_engine(row, 0, 0)

    def calc_ppi(self, row):
        if row['IP'] == 0:
            return 0
        return row['Points'] / row['IP']

    def calc_ppi_no_svh(self, row):
        if row['IP'] == 0:
            return 0
        return row['No SVH Points'] / row['IP']

    def get_pitcher_par(self, df):
        num_arms = 0
        total_ip = 0
        self.get_pitcher_par_calc(df)
        while num_arms != self.target_pitch or (abs(total_ip-target_innings) > 100 and replacement_positions['RP'] != self.rp_limit):
            #Going to do optional capping of relievers. It can get a bit out of control otherwise
            if num_arms < self.target_pitch and replacement_positions['RP'] == self.rp_limit:
                replacement_positions['SP'] = replacement_positions['SP'] + 1
            elif num_arms == self.target_pitch:
                #We have the right number of arms, but not in the inning threshold
                if total_ip < target_innings:
                    #Too many relievers
                    replacement_positions['SP'] = replacement_positions['SP'] + 1
                    replacement_positions['RP'] = replacement_positions['RP'] - 1
                else:
                    #Too many starters
                    replacement_positions['SP'] = replacement_positions['SP'] - 1
                    replacement_positions['RP'] = replacement_positions['RP'] + 1
            elif num_arms < self.target_pitch:
                if self.target_pitch-num_arms == 1 and target_innings - total_ip > 200:
                    #Add starter, a reliever isn't going to get it done, so don't bother
                    #I got caught in a loop without this
                    replacement_positions['SP'] = replacement_positions['SP'] + 1
                #Not enough pitchers. Preferentially add highest replacement level
                elif replacement_levels['SP'] > replacement_levels['RP']:
                    #Probably not, but just in case
                    replacement_positions['SP'] = replacement_positions['SP'] + 1
                else:
                    replacement_positions['RP'] = replacement_positions['RP'] + 1
            else:
                if self.target_pitch-num_arms == -1 and target_innings - total_ip > 50:
                    #Remove a reliever. We're already short on innings, so removing a starter isn't going to get it done, so don't bother
                    #I got caught in a loop without this
                    replacement_positions['RP'] = replacement_positions['RP'] - 1
                #Too many pitchers. Preferentially remove lowest replacement level
                elif replacement_levels['SP'] < replacement_levels['RP']:
                    replacement_positions['SP'] = replacement_positions['SP'] - 1
                else:
                    #Probably not, but just in case
                    replacement_positions['RP'] = replacement_positions['RP'] - 1
            self.get_pitcher_par_calc(df)
            #FOM is how many arms with a non-negative PAR...
            rosterable = df.loc[df['PAR'] >= 0]
            num_arms = len(rosterable)
            #...and how many total innings are pitched
            #I had to put the 1 in the args because otherwise it treats "SP" like two arugments "S" and "P" for some reason
            total_ip = rosterable.apply(self.usable_ip_calc, args=("SP", 1), axis=1).sum()
            total_ip += rosterable.apply(self.usable_ip_calc, args=("RP", 1), axis=1).sum()
        
        if(self.intermediate_calculations):
            filepath = os.path.join(self.intermed_subdirpath, f"pit_rost.csv")
            rosterable.to_csv(filepath, encoding='utf-8-sig')
            filepath = os.path.join(self.intermed_subdirpath, f"df_tot.csv")
            df.to_csv(filepath, encoding='utf-8-sig')

        return df

    def usable_ip_calc(self, row, role, blank):
        return row[f'IP {role}'] * row[f'{role} Multiplier']

    def usable_par_calc(self, row, role, blank):
        return row[f'PAR {role}'] * row[f'{role} Multiplier']

    def get_pitcher_par_calc(self, df):
        sp_rep_level = self.get_pitcher_rep_level(df, 'SP')
        replacement_levels['SP'] = sp_rep_level
        df['PAR SP'] = df.apply(self.calc_pitch_par_role, args=('SP', sp_rep_level), axis=1)
        rp_rep_level = self.get_pitcher_rep_level(df, 'RP')
        replacement_levels['RP'] = rp_rep_level
        df['PAR RP'] = df.apply(self.calc_pitch_par_role, args=('RP', rp_rep_level), axis=1)

        df['PAR'] = df.apply(self.sum_role_par, axis=1)

    def calc_pitch_par_role(self, row, role, rep_level):
        if row['G'] == 0:
            return -1
        if row[f'IP {role}'] == 0: return 0
        rate = row[f'P/IP {role}'] - rep_level
        return rate * row[f'IP {role}']

    def sum_role_par(self, row):
        return row['PAR SP'] + row['PAR RP']

    def get_pitcher_rep_level(self, df, pos):
        #Filter DataFrame to just the position of interest
        pos_df = df.loc[df[f'IP {pos}'] > 0]
        sort_col = f"P/IP {pos}"
        pos_df = pos_df.sort_values(sort_col, ascending=False)
        #Get the nth value (here the # of players rostered at the position) from the sorted data
        return pos_df.iloc[replacement_positions[pos]][sort_col]

    def rank_position_players(self, df, sort_col):
        for pos in bat_pos:
            col = f"Rank {pos} Rate"
            if pos == 'Util':
                df[col] = df[sort_col].rank(ascending=False)
            else:
                df[col] = df.loc[df['Position(s)'].str.contains(pos)][sort_col].rank(ascending=False)
                df[col].fillna(-999, inplace=True)
        col = "Rank MI Rate"
        df[col] = df.loc[df['Position(s)'].str.contains("2B|SS", case=False, regex=True)][sort_col].rank(ascending=False)
        df[col].fillna(-999, inplace=True)
    
    def get_position_par(self, df, sort_col):

        self.rank_position_players(df, sort_col)

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_ranks.csv")
            df.to_csv(filepath, encoding='utf-8-sig')

        num_bats = 0
        while num_bats != self.target_bat:
            #Can't do our rep_level adjustment if we haven't initialized replacement levels
            if len(replacement_levels) != 0:
                if num_bats > self.target_bat:
                    #Too many players, find the current minimum replacement level and bump that replacement_position down by 1
                    min_rep_lvl = 999.9
                    for pos, rep_lvl in replacement_levels.items():
                        if pos == 'Util' or pos == 'C': continue
                        if rep_lvl < min_rep_lvl:
                            min_rep_lvl = rep_lvl
                            min_pos = pos
                    replacement_positions[min_pos] = replacement_positions[min_pos]-1
                    #Recalcluate PAR for the position given the new replacement level
                    self.get_position_par_calc(df, min_pos, sort_col)
                else:
                    #Too few players, find the current maximum replacement level and bump that replacement_position up by 1
                    max_rep_lvl = 0.0
                    for pos, rep_lvl in replacement_levels.items():
                        if pos == 'Util' or pos == 'C': continue
                        if rep_lvl > max_rep_lvl:
                            #These two conditionals are arbitrarily determined by me at the time, but they seem to do a good job reigning in 1B and OF
                            #to reasonable levels. No one is going to roster a 1B that hits like a replacement level SS, for example
                            if pos == '1B' and replacement_positions['1B'] > 1.5*replacement_positions['SS']: continue
                            if pos == 'OF' and replacement_positions['OF'] > 3*replacement_positions['SS']: continue
                            max_rep_lvl = rep_lvl
                            max_pos = pos
                    replacement_positions[max_pos] = replacement_positions[max_pos] + 1
                    #Recalcluate PAR for the position given the new replacement level
                    self.get_position_par_calc(df, max_pos, sort_col)
            else: 
                #Initial calculation of replacement levels and PAR
                for pos in bat_pos:
                    self.get_position_par_calc(df, pos, sort_col)
            #Set maximum PAR value for each player to determine how many are rosterable
            df['Max PAR'] = df.apply(self.calc_max_par, axis=1)
            #FOM is how many bats with a non-negative max PAR
            num_bats = len(df.loc[df['Max PAR'] >= 0])

    def get_position_par_calc(self, df, pos, sort_col):
        rep_level = self.get_position_rep_level(df, pos, sort_col)
        replacement_levels[pos] = rep_level
        col = pos + "_PAR"
        df[col] = df.apply(self.calc_bat_par, args=(rep_level, sort_col, pos), axis=1)

    def calc_bat_par(self, row, rep_level, sort_col, pos):
        if pos in row['Position(s)'] or pos == 'Util':
            #Filter to the current position
            par_rate = row[sort_col] - rep_level
            #Are we doing P/PA values, or P/G values
            if sort_col == 'P/PA':
                return par_rate * row['PA']
            else:
                return par_rate * row['G']
        #If the position doesn't apply, set PAR to -1 to differentiate from the replacement player
        return -1.0

    def calc_max_par(self, row):
        #Find the max PAR for player across all positions
        return np.max([row['C_PAR'], row['1B_PAR'], row['2B_PAR'],row['3B_PAR'],row['SS_PAR'],row['OF_PAR'],row['Util_PAR']])

    def get_position_rep_level(self, df, pos, sort_col):
        if pos != 'Util':
            #Filter DataFrame to just the position of interest
            pos_df = df.loc[df['Position(s)'].str.contains(pos)]
        else:
            #No one filters out for Util
            pos_df = df
        pos_df = pos_df.sort_values(sort_col, ascending=False)
        #Get the nth value (here the # of players rostered at the position) from the sorted data
        return pos_df.iloc[replacement_positions[pos]][sort_col]

    def not_a_belly_itcher_filter(self, row):
        #Filter pitchers from the data set who don't reach requisite innings. These thresholds are arbitrary.
        if row['Position(s)'] == 'SP':
            return row['IP'] >= 70
        if row['Position(s)'] == 'RP':
            return row['IP'] >= 30
        if row['G'] == 0: return False
        #Got to here, this is a SP/RP with > 0 G. Ration their innings threshold based on their projected GS/G ratio
        start_ratio = row['GS'] / row['G']
        return row['IP'] > 40.0*start_ratio + 30.0

    def rp_ip_func(self, row):
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

    def sp_ip_func(self, row):
        return row['IP'] - row['IP RP']

    def sp_fip_calc(self, row):
        if row['IP RP'] == 0: return row['FIP']
        if row['IP SP'] == 0: return 0
        #Weighted results from 2019-2021 dataset shows an approxiately 0.6 FIP improvement from SP to RP
        return (row['IP']*row['FIP'] + 0.6*row['IP RP']) / row['IP']

    def rp_fip_calc(self, row):
        if row['IP RP'] == 0: return 0
        if row['IP SP'] == 0: return row['FIP']
        return row['FIP SP'] -0.6

    def sp_pip_calc(self, row):
        if row['IP SP'] == 0: return 0
        #Regression of no SVH P/IP from FIP gives linear coefficient of -1.3274
        fip_diff = row['FIP SP'] - row['FIP']
        return row['No SVH P/IP'] -1.3274*fip_diff

    def rp_pip_calc(self, row):
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

    def sp_multiplier_assignment(self, row):
        #We're assuming you use all innings for your top 6 pitchers, 95% of next one, 90% of the next, etc
        if row['Rank SP Rate'] <=72:
            return 1.0
        non_top_rank = row['Rank SP Rate'] - 72
        factor = non_top_rank // 12 + 1
        return 1 - factor * 0.05

    def rp_multiplier_assignment(self, row):
        #Once you get past 5 RP per team, there are diminishing returns on how many relief innings are actually usable
        if row['Rank RP Rate'] <=60:
            return 1.0
        non_top_rank = row['Rank RP Rate'] - 60
        factor = non_top_rank // 12 + 1
        return 1 - factor * 0.3

    def estimate_role_splits(self, df):
        df['IP RP'] = df.apply(self.rp_ip_func, axis=1)
        df['IP SP'] = df.apply(self.sp_ip_func, axis=1)
        
        df['FIP SP'] = df.apply(self.sp_fip_calc, axis=1)
        df['FIP RP'] = df.apply(self.rp_fip_calc, axis=1)

        df['P/IP SP'] = df.apply(self.sp_pip_calc, axis=1)
        df['P/IP RP'] = df.apply(self.rp_pip_calc, axis=1)

        df['Rank SP Rate'] = df['P/IP SP'].rank(ascending=False)
        df['Rank RP Rate'] = df['P/IP RP'].rank(ascending=False)

        df['SP Multiplier'] = df.apply(self.sp_multiplier_assignment, axis=1)
        df['RP Multiplier'] = df.apply(self.rp_multiplier_assignment, axis=1)

    def calculate_values(self):
        if self.ros:
            self.force = True
            if self.projection == 'steamer':
                #steamer has a different convention for reasons
                self.projection = 'steamerr'
            else:
                self.projection = 'r' + self.projection
        try:
            fg_scraper = scrape.Scrape_Fg()
            pos_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type={self.projection}&team=0&lg=all&players=0", f'{self.projection}_pos.csv', self.force)
            pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type={self.projection}&team=0&lg=all&players=0", f'{self.projection}_pitch.csv', self.force)

            if self.depthchart_pt:
                if self.ros:
                    dc_set = 'rfangraphsdc'
                else:
                    dc_set = 'fangraphsdc'
                dc_pos_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type={dc_set}&team=0&lg=all&players=0", f'{dc_set}_pos.csv', self.force)
                dc_pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type={dc_set}&team=0&lg=all&players=0", f'{dc_set}_pitch.csv', self.force)

        finally:
            fg_scraper.close()

        if self.depthchart_pt:
            pos_proj = self.convertToDcPlayingTime(pos_proj, dc_pos_proj, True)
            pitch_proj = self.convertToDcPlayingTime(pitch_proj, dc_pitch_proj, False)

            if self.intermediate_calculations:
                filepath = os.path.join(self.intermed_subdirpath, f"{self.projection}_dc_conv_pos.csv")
                pos_proj.to_csv(filepath, encoding='utf-8-sig')
                filepath = os.path.join(self.intermed_subdirpath, f"{self.projection}_dc_conv_pitch.csv")
                pitch_proj.to_csv(filepath, encoding='utf-8-sig')

        try:
            otto_scraper = Scrape_Ottoneu()
            positions = otto_scraper.get_player_position_ds(self.force)
        finally:
            otto_scraper.close()

        print('Calculating batters')

        #Set position data from Ottoneu and add calculated columns
        pos_proj = self.set_positions(pos_proj, positions)
        pos_proj['Points'] = pos_proj.apply(self.calc_bat_points, axis=1)
        pos_proj['P/G'] = pos_proj.apply(self.calc_ppg, axis=1)
        pos_proj['P/PA'] = pos_proj.apply(self.calc_pppa, axis=1)

        #Filter to players projected to a baseline amount of playing time
        pos_150pa = pos_proj.loc[pos_proj['PA'] >= 150]

        self.get_position_par(pos_150pa, "P/G")

        print('Calculating pitchers')
        pitch_proj = self.set_positions(pitch_proj, positions)
        pitch_proj['Points'] = pitch_proj.apply(self.calc_pitch_points, axis=1)
        pitch_proj['No SVH Points'] = pitch_proj.apply(self.calc_pitch_points_no_svh, axis=1)
        pitch_proj['P/IP'] = pitch_proj.apply(self.calc_ppi, axis=1)
        pitch_proj['No SVH P/IP'] = pitch_proj.apply(self.calc_ppi_no_svh, axis=1)

        #Filter to pitchers projected to a baseline amount of playing time
        real_pitchers = pitch_proj.loc[pitch_proj.apply(self.not_a_belly_itcher_filter, axis=1)]

        self.estimate_role_splits(real_pitchers)

        real_pitchers = self.get_pitcher_par(real_pitchers)

        print(f"Rreplacment level numbers are: {replacement_positions}")
        print(f"Replacement levels are: {replacement_levels}")

        rosterable_pos = pos_150pa.loc[pos_150pa['Max PAR'] >= 0]
        print(f"total games = {rosterable_pos['G'].sum()}")
        rosterable_pitch = real_pitchers.loc[real_pitchers['PAR'] >= 0]
        print(f"total innings = {rosterable_pitch['IP'].sum()}")

        total_par = rosterable_pos['Max PAR'].sum() + rosterable_pitch['PAR'].sum()
        #I had to put the 1 in the args because otherwise it treats "SP" like two arguments "S" and "P" for some reason
        total_usable_par = rosterable_pos['Max PAR'].sum() + rosterable_pitch.apply(self.usable_par_calc, args=('SP',1), axis=1).sum() + rosterable_pitch.apply(self.usable_par_calc, args=('RP',1), axis=1).sum()
        print(f'Total PAR: {total_par}; Total Usable PAR: {total_usable_par}')
        total_players = len(rosterable_pos) + len(rosterable_pitch)

        dollars = 400*12
        #TODO: Make prospect number an input
        dollars -= 48 #estimate $4 for prospects per team
        dollars -= total_players #remove a dollar per player at or above replacement
        dol_per_par = dollars / total_usable_par
        print(f'Dollar/PAR = {dol_per_par}')

        rosterable_pos['Value'] = rosterable_pos['Max PAR'].apply(lambda x: "${:.1f}".format(x*dol_per_par + 1.0))
        rosterable_pitch['Value'] = rosterable_pitch['PAR'].apply(lambda x: "${:.1f}".format(x*dol_per_par + 1.0))

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_rosterable.csv")
            rosterable_pos.to_csv(filepath, encoding='utf-8-sig')
            filepath = os.path.join(self.intermed_subdirpath, f"pitch_rosterable.csv")
            rosterable_pitch.to_csv(filepath, encoding='utf-8-sig')

#--------------------------------------------------------------------------------
#Begin main program
proj_set = input("Pick projection system (steamer, zips, fangraphsdc, atc, thebat, thebatx: ")
#Peform value calc based on Rest of Season projections
ros = input("RoS? (y/n): ") == 'y'

if proj_set != 'fangraphsdc':
    dc_pt = (input("Use DC playing time (y/n): ")) == 'y'

if not ros:
    force = (input("Force update (y/n): ")) == 'y'

print_intermediate = (input("Print intermediate datasets (y/n): ")) == 'y'
value_calc = PointValues(projection=proj_set, depthchart_pt=dc_pt, ros=ros, debug=print_intermediate, rp_limit=84,force_proj_download=force)
value_calc.calculate_values()
