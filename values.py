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
target_bat = 244
target_pitch = 178
target_innings = 1500.0*12.0
#replacement_positions = {"C":24,"1B":40,"2B":38,"3B":40,"SS":42,"OF":95,"Util":200,"SP":85,"RP":70}
#These are essentially minimums for the positions. I would really not expect to go below these. C and Util are unaffected by the algorithm
replacement_positions = {"C":24,"1B":12,"2B":18,"3B":12,"SS":18,"OF":60,"Util":200,"SP":60,"RP":60}

def set_positions(df, positions):
    df = df.merge(positions[['Position(s)', 'OttoneuID']], how='left', left_index=True, right_index=True)
    #Some projections can be not in the Otto-verse, so set their Ottoneu ID to -1
    df['OttoneuID'] = df['OttoneuID'].fillna(-1) 
    df['OttoneuID'] = df['OttoneuID'].astype(int)
    #Players not in the Otto-verse need a position
    df['Position(s)'] = df['Position(s)'].fillna('Util')
    df['Team'] = df['Team'].fillna('---')
    return df

def convertToDcPlayingTime(proj, dc_proj, position):
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

def calc_bat_points(row):
    #Otto batting points formula from https://ottoneu.fangraphs.com/support
    return -1.0*row['AB'] + 5.6*row['H'] + 2.9*row['2B'] + 5.7*row['3B'] + 9.4*row['HR']+3.0*row['BB']+3.0*row['HBP']+1.9*row['SB']-2.8*row['CS']

def calc_ppg(row):
    if row['G'] == 0:
        return 0
    return row['Points'] / row['G']

def calc_pppa(row):
    if row['PA'] == 0:
        return 0
    return row['Points'] / row['PA']

def pitch_points_engine(row, save, hold):
    #This HBP approximation is from a linear regression is did when I first did values
    try:
        hbp = row['HBP']
    except KeyError:
        #Ask forgiveness, not permission
        hbp = 0.0951*row['BB']+0.4181
    #Otto pitching points (FGP) from https://ottoneu.fangraphs.com/support
    return 7.4*row['IP']+2.0*row['SO']-2.6*row['H']-3.0*row['BB']-3.0*hbp-12.3*row['HR']+5.0*save+4.0*hold

def calc_pitch_points(row):
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
    return pitch_points_engine(row, save, hold)

def calc_pitch_points_no_svh(row):
    return pitch_points_engine(row, 0, 0)

def calc_ppi(row):
    if row['IP'] == 0:
        return 0
    return row['Points'] / row['IP']

def calc_ppi_no_svh(row):
    if row['IP'] == 0:
        return 0
    return row['No SVH Points'] / row['IP']

def get_pitcher_par(df, rp_cap=999):
    #Initial list of replacement levels
    rep_levels = {}
    num_arms = 0
    total_ip = 0
    while num_arms != target_pitch or (abs(total_ip-target_innings) > 100 and replacement_positions['RP'] != rp_cap):
        #Can't do our rep_level adjustment if we haven't initialized replacement levels
        if len(rep_levels) != 0:
            #Going to do optional capping of relievers. It can get a bit out of control otherwise
            if num_arms < target_pitch and replacement_positions['RP'] == rp_cap:
                replacement_positions['SP'] = replacement_positions['SP'] + 1
            elif num_arms == target_pitch:
                #We have the right number of arms, but not in the inning threshold
                if total_ip < target_innings:
                    #Too many relievers
                    replacement_positions['SP'] = replacement_positions['SP'] + 1
                    replacement_positions['RP'] = replacement_positions['RP'] - 1
                else:
                    #Too many starters
                    replacement_positions['SP'] = replacement_positions['SP'] - 1
                    replacement_positions['RP'] = replacement_positions['RP'] + 1
            elif num_arms < target_pitch:
                if target_pitch-num_arms == 1 and target_innings - total_ip > 200:
                    #Add starter, a reliever isn't going to get it done, so don't bother
                    #I got caught in a loop without this
                    replacement_positions['SP'] = replacement_positions['SP'] + 1
                #Not enough pitchers. Preferentially add highest replacement level
                elif rep_levels['SP'] > rep_levels['RP']:
                    #Probably not, but just in case
                    replacement_positions['SP'] = replacement_positions['SP'] + 1
                else:
                    replacement_positions['RP'] = replacement_positions['RP'] + 1
            else:
                if target_pitch-num_arms == -1 and target_innings - total_ip > 50:
                   #Remove a reliever. We're already short on innings, so removing a starter isn't going to get it done, so don't bother
                   #I got caught in a loop without this
                   replacement_positions['RP'] = replacement_positions['RP'] - 1
                #Too many pitchers. Preferentially remove lowest replacement level
                elif rep_levels['SP'] < rep_levels['RP']:
                    replacement_positions['SP'] = replacement_positions['SP'] - 1
                else:
                    #Probably not, but just in case
                    replacement_positions['RP'] = replacement_positions['RP'] - 1
        get_pitcher_par_calc(df, rep_levels)
        #FOM is how many arms with a non-negative PAR...
        rosterable = df.loc[df['PAR'] >= 0]
        num_arms = len(rosterable)
        #...and how many total innings are pitched
        total_ip = usable_innings(rosterable)

def usable_innings(rosterable):
    #Once you get past 5 RP per team, there are diminishing returns on how many relief innings are actually usable
    df = rosterable.sort_values("P/IP RP", ascending=False)
    start = 0
    end = 60
    rp_ip = 0
    multiplier = 1.0
    while end < replacement_positions['RP']:
        rp_ip += df.iloc[start:end]['IP RP'].sum()*multiplier
        start = end
        end += 12
        multiplier -= 0.3
        if multiplier < 0:
            multiplier = 0
    rp_ip += df.iloc[start:replacement_positions['RP']]['IP RP'].sum()*multiplier

    #We're assuming you use all innings for your top 6 pitchers, 85% of next one, 70% of the next, etc
    df = rosterable.sort_values("P/IP SP", ascending=False)
    sp_ip = 0
    start = 0
    end = 72
    multiplier = 1.0
    while end < replacement_positions['SP']:
        sp_ip += df.iloc[start:end]['IP SP'].sum()*multiplier
        start = end
        end += 12
        multiplier -= 0.05
        if multiplier < 0:
            multiplier = 0
    sp_ip += df.iloc[start:replacement_positions['SP']]['IP SP'].sum()*multiplier

    return sp_ip + rp_ip

def get_pitcher_par_calc(df, rep_levels):
    sp_rep_level = get_pitcher_rep_level(df, 'SP')
    rep_levels['SP'] = sp_rep_level
    rp_rep_level = get_pitcher_rep_level(df, 'RP')
    rep_levels['RP'] = rp_rep_level
    df["PAR"] = df.apply(calc_pitch_par, args=(sp_rep_level, rp_rep_level), axis=1)

def calc_pitch_par(row, sp_rep_level, rp_rep_level):
    if row['G'] == 0:
        return -1
    par = 0
    if row['IP SP'] > 0:
        sp_rate = row['P/IP SP'] - sp_rep_level
        par += sp_rate*row['IP SP']
    if row['IP RP'] > 0:
        rp_rate = row['P/IP RP'] - rp_rep_level
        par += rp_rate*row['IP RP']
    return par

def get_pitcher_rep_level(df, pos):
    #Filter DataFrame to just the position of interest
    pos_df = df.loc[df[f'IP {pos}'] > 0]
    sort_col = f"P/IP {pos}"
    pos_df = pos_df.sort_values(sort_col, ascending=False)
    #Get the nth value (here the # of players rostered at the position) from the sorted data
    return pos_df.iloc[replacement_positions[pos]][sort_col]

def get_position_par(df, sort_col):
    #Initial list of replacement levels
    rep_levels = {}
    num_bats = 0
    while num_bats != target_bat:
        #Can't do our rep_level adjustment if we haven't initialized replacement levels
        if len(rep_levels) != 0:
            if num_bats > target_bat:
                #Too many players, find the current minimum replacement level and bump that replacement_position down by 1
                min_rep_lvl = 999.9
                for pos, rep_lvl in rep_levels.items():
                    if pos == 'Util' or pos == 'C': continue
                    if rep_lvl < min_rep_lvl:
                        min_rep_lvl = rep_lvl
                        min_pos = pos
                replacement_positions[min_pos] = replacement_positions[min_pos]-1
                #Recalcluate PAR for the position given the new replacement level
                get_position_par_calc(df, min_pos, sort_col, rep_levels)
            else:
                #Too few players, find the current maximum replacement level and bump that replacement_position up by 1
                max_rep_lvl = 0.0
                for pos, rep_lvl in rep_levels.items():
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
                get_position_par_calc(df, max_pos, sort_col, rep_levels)
        else: 
            #Initial calculation of replacement levels and PAR
            for pos in bat_pos:
                get_position_par_calc(df, pos, sort_col, rep_levels)
        #Set maximum PAR value for each player to determine how many are rosterable
        df['Max PAR'] = df.apply(calc_max_par, axis=1)
        #FOM is how many bats with a non-negative max PAR
        num_bats = len(df.loc[df['Max PAR'] >= 0])
    print(f"new replacment level numbers are: {replacement_positions}")
    print(f"new replacement levels are: {rep_levels}")

def get_position_par_calc(df, pos, sort_col, rep_levels):
    rep_level = get_position_rep_level(df, pos, sort_col)
    rep_levels[pos] = rep_level
    col = pos + "_PAR"
    df[col] = df.apply(calc_bat_par, args=(rep_level, sort_col, pos), axis=1)

def calc_bat_par(row, rep_level, sort_col, pos):
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

def calc_max_par(row):
    #Find the max PAR for player across all positions
    return np.max([row['C_PAR'], row['1B_PAR'], row['2B_PAR'],row['3B_PAR'],row['SS_PAR'],row['OF_PAR'],row['Util_PAR']])

def get_position_rep_level(df, pos, sort_col):
    if pos != 'Util':
        #Filter DataFrame to just the position of interest
        pos_df = df.loc[df['Position(s)'].str.contains(pos)]
    else:
        #No one filters out for Util
        pos_df = df
    pos_df = pos_df.sort_values(sort_col, ascending=False)
    #Get the nth value (here the # of players rostered at the position) from the sorted data
    return pos_df.iloc[replacement_positions[pos]][sort_col]

def not_a_belly_itcher_filter(row):
    #Filter pitchers from the data set who don't reach requisite innings. These thresholds are arbitrary.
    if row['Position(s)'] == 'SP':
        return row['IP'] >= 70
    if row['Position(s)'] == 'RP':
        return row['IP'] >= 30
    if row['G'] == 0: return False
    #Got to here, this is a SP/RP with > 0 G. Ration their innings threshold based on their projected GS/G ratio
    start_ratio = row['GS'] / row['G']
    return row['IP'] > 40.0*start_ratio + 30.0

def rp_ip_func(row):
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

def sp_ip_func(row):
    return row['IP'] - row['IP RP']

def sp_fip_calc(row):
    if row['IP RP'] == 0: return row['FIP']
    if row['IP SP'] == 0: return 0
    #Weighted results from 2019-2021 dataset shows an approxiately 0.6 FIP improvement from SP to RP
    return (row['IP']*row['FIP'] + 0.6*row['IP RP']) / row['IP']

def rp_fip_calc(row):
    if row['IP RP'] == 0: return 0
    if row['IP SP'] == 0: return row['FIP']
    return row['FIP SP'] -0.6

def sp_pip_calc(row):
    if row['IP SP'] == 0: return 0
    #Regression of no SVH P/IP from FIP gives linear coefficient of -1.3274
    fip_diff = row['FIP SP'] - row['FIP']
    return row['No SVH P/IP'] -1.3274*fip_diff

def rp_pip_calc(row):
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

def estimate_role_splits(df):
    df['IP RP'] = df.apply(rp_ip_func, axis=1)
    df['IP SP'] = df.apply(sp_ip_func, axis=1)
    
    df['FIP SP'] = df.apply(sp_fip_calc, axis=1)
    df['FIP RP'] = df.apply(rp_fip_calc, axis=1)

    df['P/IP SP'] = df.apply(sp_pip_calc, axis=1)
    df['P/IP RP'] = df.apply(rp_pip_calc, axis=1)

#--------------------------------------------------------------------------------
#Begin main program
proj_set = input("Pick projection system (steamer, zips, fangraphsdc, atc, thebat, thebatx: ")
#Peform value calc based on Rest of Season projections
ros = input("RoS? (y/n): ") == 'y'

if proj_set != 'fangraphsdc':
    dc_pt = (input("Use DC playing time (y/n): ")) == 'y'

if ros:
    force = True
    if proj_set == 'steamer':
        #steamer has a different convention for reasons
        proj_set = 'steamerr'
    else:
        proj_set = 'r' + proj_set
else:
    force = (input("Force update (y/n): ")) == 'y'

print_intermediate = (input("Print intermediate datasets (y/n): ")) == 'y'

try:
    fg_scraper = scrape.Scrape_Fg()
    pos_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type={proj_set}&team=0&lg=all&players=0", f'{proj_set}_pos.csv', force)
    pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type={proj_set}&team=0&lg=all&players=0", f'{proj_set}_pitch.csv', force)

    if dc_pt:
        if ros:
            dc_set = 'rfangraphsdc'
        else:
            dc_set = 'fangraphsdc'
        dc_pos_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type={dc_set}&team=0&lg=all&players=0", f'{dc_set}_pos.csv', force)
        dc_pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type={dc_set}&team=0&lg=all&players=0", f'{dc_set}_pitch.csv', force)

finally:
    fg_scraper.close()

#Initialize directory for intermediate calc files if required
dirname = os.path.dirname(__file__)
subdirpath = os.path.join(dirname, 'intermediate')
if not path.exists(subdirpath):
    os.mkdir(subdirpath)

if dc_pt:
    pos_proj = convertToDcPlayingTime(pos_proj, dc_pos_proj, True)
    pitch_proj = convertToDcPlayingTime(pitch_proj, dc_pitch_proj, False)

    if print_intermediate:
        filepath = os.path.join(subdirpath, f"{proj_set}_dc_conv_pos.csv")
        pos_proj.to_csv(filepath, encoding='utf-8-sig')
        filepath = os.path.join(subdirpath, f"{proj_set}_dc_conv_pitch.csv")
        pitch_proj.to_csv(filepath, encoding='utf-8-sig')

try:
    otto_scraper = Scrape_Ottoneu()
    positions = otto_scraper.get_player_position_ds(force)
finally:
    otto_scraper.close()

#Set position data from Ottoneu and add calculated columns
pos_proj = set_positions(pos_proj, positions)
pos_proj['Points'] = pos_proj.apply(calc_bat_points, axis=1)
pos_proj['P/G'] = pos_proj.apply(calc_ppg, axis=1)
pos_proj['P/PA'] = pos_proj.apply(calc_pppa, axis=1)

#Filter to players projected to a baseline amount of playing time
pos_150pa = pos_proj.loc[pos_proj['PA'] >= 150]

#TODO: Reimplement when we're ready
#get_position_par(pos_150pa, "P/G")

if print_intermediate:
    filepath = os.path.join(subdirpath, f"pos_par_calc.csv")
    pos_150pa.to_csv(filepath, encoding='utf-8-sig')

pitch_proj = set_positions(pitch_proj, positions)
pitch_proj['Points'] = pitch_proj.apply(calc_pitch_points, axis=1)
pitch_proj['No SVH Points'] = pitch_proj.apply(calc_pitch_points_no_svh, axis=1)
pitch_proj['P/IP'] = pitch_proj.apply(calc_ppi, axis=1)
pitch_proj['No SVH P/IP'] = pitch_proj.apply(calc_ppi_no_svh, axis=1)

estimate_role_splits(pitch_proj)

#Filter to pitchers projected to a baseline amount of playing time
real_pitchers = pitch_proj.loc[pitch_proj.apply(not_a_belly_itcher_filter, axis=1)]

get_pitcher_par(real_pitchers, 84)

if print_intermediate:
    filepath = os.path.join(subdirpath, f"pitch_par_calc.csv")
    real_pitchers.to_csv(filepath, encoding='utf-8-sig')

#rosterable_pos = pos_150pa.loc[pos_150pa['Max PAR'] >= 0]
#rosterable_pitch = real_pitchers.loc[real_pitchers['PAR'] >= 0]

#total_par = rosterable_pos[]

