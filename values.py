import pandas as pd
import numpy as np
import scrape_fg as scrape
import os
from os import path

from scrape_ottoneu import Scrape_Ottoneu

pd.options.mode.chained_assignment = None # from https://stackoverflow.com/a/20627316

bat_pos = ['C','1B','2B','3B','SS','OF','Util']
pitch_pos = ['SP','RP']
replacement_positions = {"C":24,"1B":40,"2B":38,"3B":40,"SS":42,"OF":95,"Util":150,"SP":85,"RP":70}

def set_positions(df, positions):
    df = df.merge(positions[['Position(s)', 'OttoneuID']], how='left', left_index=True, right_index=True)
    df['OttoneuID'] = df['OttoneuID'].fillna(-1) 
    df['OttoneuID'] = df['OttoneuID'].astype(int)
    df['Position(s)'] = df['Position(s)'].fillna('Util')
    df['Team'] = df['Team'].fillna('---')
    return df

def convertToDcPlayingTime(proj, dc_proj, position):
    static_columns = ['playerid', 'Name', 'Team','-1','AVG','OBP','SLG','OPS','wOBA','wRC+','ADP','WHIP','K/9','BB/9','ERA','FIP']
    dc_columns = ['G','PA','GS','IP']
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
            proj[column] = proj[column] / proj[denom] * dc_proj[denom]
    for column in dc_columns:
        if column in proj.columns:
            proj[column] = dc_proj[column]
    return proj

def calc_bat_points(row):
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
    return 7.4*row['IP']+2.0*row['SO']-2.6*row['H']-3.0*row['BB']-3.0*hbp-12.3*row['HR']+5.0*row['SV']+4.0*row['HLD']

def calc_ppi(row):
    if row['IP'] == 0:
        return 0
    return row['Points'] / row['IP']

def get_position_par(df, sort_col):
    for pos in bat_pos:
        rep_level = get_position_rep_level(df, pos, sort_col)
        col = pos + "_PAR"
        df[col] = df.apply(calc_bat_par, args=(rep_level, sort_col, pos), axis=1)
    
    df['Max PAR'] = df.apply(calc_max_par, axis=1)

def calc_bat_par(row, rep_level, sort_col, pos):
    if pos in row['Position(s)'] or pos == 'Util':
        par_rate = row[sort_col] - rep_level
        if sort_col == 'P/PA':
            return par_rate * row['PA']
        else:
            return par_rate * row['G']
    return 0

def calc_max_par(row):
    return np.max([row['C_PAR'], row['1B_PAR'], row['2B_PAR'],row['3B_PAR'],row['SS_PAR'],row['OF_PAR'],row['Util_PAR'],0])

def get_position_rep_level(df, pos, sort_col):
    if pos != 'Util':
        pos_df = df.loc[df['Position(s)'].str.contains(pos)]
    else:
        pos_df = df
    pos_df = pos_df.sort_values(sort_col, ascending=False)
    return pos_df.iloc[replacement_positions[pos]][sort_col]


def get_pitcher_rep_level(df, pos):
    pos_df = df.loc[df['Position(s)'].str.contains(pos)]
    pos_df = pos_df.sort_values("P/IP", ascending=False)
    return pos_df.iloc[replacement_positions[pos]]['P/IP']

proj_set = input("Pick projection system (steamer, zips, fangraphsdc, atc, thebat, thebatx: ")
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

pos_proj = set_positions(pos_proj, positions)
pos_proj['Points'] = pos_proj.apply(calc_bat_points, axis=1)
pos_proj['P/G'] = pos_proj.apply(calc_ppg, axis=1)
pos_proj['P/PA'] = pos_proj.apply(calc_pppa, axis=1)

pitch_proj = set_positions(pitch_proj, positions)
pitch_proj['Points'] = pitch_proj.apply(calc_pitch_points, axis=1)
pitch_proj['P/IP'] = pitch_proj.apply(calc_ppi, axis=1)

pos_150pa = pos_proj.loc[pos_proj['PA'] >= 150]

get_position_par(pos_150pa, "P/G")
#rep_level = {}
#rep_level['C'] = get_position_rep_level(pos_150pa, 'C', 'P/G')
#rep_level['1B'] = get_position_rep_level(pos_150pa, '1B', 'P/G')
#rep_level['2B'] = get_position_rep_level(pos_150pa, '2B', 'P/G')
#rep_level['3B'] = get_position_rep_level(pos_150pa, '3B', 'P/G')
#rep_level['SS'] = get_position_rep_level(pos_150pa, 'SS', 'P/G')
#rep_level['OF'] = get_position_rep_level(pos_150pa, 'OF', 'P/G')
#rep_level['Util'] = get_position_rep_level(pos_150pa, '', 'P/G')

if print_intermediate:
    filepath = os.path.join(subdirpath, f"pos_par_calc.csv")
    pos_150pa.to_csv(filepath, encoding='utf-8-sig')

#rep_level['SP'] = get_pitcher_rep_level(pitch_proj, 'SP')
#rep_level['RP'] = get_pitcher_rep_level(pitch_proj, 'RP')

#print(rep_level)

