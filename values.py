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
replacement_positions = {"C":24,"1B":12,"2B":18,"3B":12,"SS":18,"OF":60,"Util":200,"SP":132,"RP":84}

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

def calc_pitch_points(row):
    #This HBP approximation is from a linear regression is did when I first did values
    try:
        hbp = row['HBP']
    except KeyError:
        #Ask forgiveness, not permission
        hbp = 0.0951*row['BB']+0.4181
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
    #Otto pitching points (FGP) from https://ottoneu.fangraphs.com/support
    return 7.4*row['IP']+2.0*row['SO']-2.6*row['H']-3.0*row['BB']-3.0*hbp-12.3*row['HR']+5.0*save+4.0*hold

def calc_ppi(row):
    if row['IP'] == 0:
        return 0
    return row['Points'] / row['IP']

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


def get_pitcher_rep_level(df, pos):
    #TODO: This probably needs to be redone to handle hybrid pitchers
    pos_df = df.loc[df['Position(s)'].str.contains(pos)]
    pos_df = pos_df.sort_values("P/IP", ascending=False)
    return pos_df.iloc[replacement_positions[pos]]['P/IP']

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

pitch_proj = set_positions(pitch_proj, positions)
pitch_proj['Points'] = pitch_proj.apply(calc_pitch_points, axis=1)
pitch_proj['P/IP'] = pitch_proj.apply(calc_ppi, axis=1)

#Filter to players projected to a baseline amount of playing time
pos_150pa = pos_proj.loc[pos_proj['PA'] >= 150]

#TODO: Reimplement when we're ready
get_position_par(pos_150pa, "P/G")

if print_intermediate:
    filepath = os.path.join(subdirpath, f"pos_par_calc.csv")
    pos_150pa.to_csv(filepath, encoding='utf-8-sig')

#Filter to pitchers projected to a baseline amount of playing time
real_pitchers = pitch_proj.loc[pitch_proj.apply(not_a_belly_itcher_filter, axis=1)]
print(f'pitchers.len = {len(pitch_proj)}; real_pitchers.len = {len(real_pitchers)}')

