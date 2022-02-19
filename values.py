import pandas as pd
import scrape_fg as scrape
import os
from os import path

from scrape_ottoneu import Scrape_Ottoneu

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

if dc_pt:
    pos_proj = convertToDcPlayingTime(pos_proj, dc_pos_proj, True)
    pitch_proj = convertToDcPlayingTime(pitch_proj, dc_pitch_proj, False)

    if print_intermediate:
        filepath = os.path.join(subdirpath, f"{proj_set}_dc_conv_pos.csv")
        pos_proj.to_csv(filepath)
        filepath = os.path.join(subdirpath, f"{proj_set}_dc_conv_pitch.csv")
        pitch_proj.to_csv(filepath)

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




