from pandas import DataFrame, Index, Series
from domain.domain import PlayerProjection, Projection, ProjectionData, Player
from scrape import scrape_fg, scrape_davenport
from domain.enum import ProjectionType, StatType, IdType, Position
from domain.exception import InputException
from datetime import datetime
from services import player_services, browser_services
from dao.session import Session
from sqlalchemy.orm import joinedload
import pandas as pd
import math
from util import date_util
from typing import List, Tuple

def download_projections(projection:str, ros:bool=False, dc_pt:bool=False, progress=None) -> List[DataFrame]:
    """Returns a list of projection dataframes. Item 1 is the batting projections. Item 2 is the pitching projections"""

    if ros:
        if projection == 'steamer':
            #steamer has a different convention for reasons
            projection = 'steamerr'
        else:
            projection = 'r' + projection
    try:
        fg_scraper = scrape_fg.Scrape_Fg(browser_services.get_desired_browser())
        pos_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections?pos=all&stats=bat&type={projection}", f'{projection}_pos.csv')
        #THE BAT X does not have pitcher projections, so revert them to simply THE BAT
        if progress is not None:
            progress.increment_completion_percent(20)
        if projection == 'thebatx':
            pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections?pos=all&stats=pit&type=thebat", f'thebat_pitch.csv')     
        elif projection == 'thebatxr':
            fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections?pos=all&stats=pit&type=thebatr", f'thebatr_pitch.csv')
        else:
            pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections?pos=all&stats=pit&type={projection}", f'{projection}_pitch.csv')
        if progress is not None:
            progress.increment_completion_percent(20)
        if dc_pt:
            if progress is not None:
                progress.set_task_title('Getting Depth Charts Playing Time')
            pos_proj = convertToDcPlayingTime(pos_proj, ros, True, fg_scraper)
            if progress is not None:
                progress.increment_completion_percent(20)
            pitch_proj = convertToDcPlayingTime(pitch_proj, ros, False, fg_scraper)
            if progress is not None:
                progress.increment_completion_percent(20)

    finally:
        fg_scraper.close()
    
    return [pos_proj, pitch_proj]

def convertToDcPlayingTime(proj:DataFrame, ros:bool, position:bool, fg_scraper:scrape_fg.Scrape_Fg=None) -> DataFrame:
    """Converts a given projection's rate stats to the FanGraph's depth charts playing time projections"""

    if ros:
        dc_set = 'rfangraphsdc'
    else:
        dc_set = 'fangraphsdc'
    close = False
    try:
        if fg_scraper == None:
            fg_scraper = scrape_fg.Scrape_Fg(browser_services.get_desired_browser())
            close = True
        if position:
            dc_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections?pos=all&stats=bat&type={dc_set}", f'{dc_set}_pos.csv')
        else:
            dc_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections?pos=all&stats=pit&type={dc_set}", f'{dc_set}_pitch.csv')
    finally:
        if close:
            fg_scraper.close()

    #String and rate columns that are unaffected
    static_columns = ['playerid', 'Name', 'Team','-1','AVG','OBP','SLG','OPS','wOBA','wRC+','ADP','WHIP','K/9','BB/9','HR/9','K/BB','K%','BB%','K-BB%','BABIP','WAR','RA9-WAR','LOB%','GB%','HR/FB','InterSD', 'InterSK','IntraSD','ERA','FIP']
    #Columns directly taken from DC
    dc_columns = ['G','PA','GS','IP']
    #Filter projection to only players present in the DC projection and then drop the temp DC column
    proj = proj.assign(DC=proj.index.isin(dc_proj.index).astype(bool))
    proj = proj[proj['DC'] == True]
    proj.drop('DC', axis=1, inplace=True)
    if position:
        denom = 'G'
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
    else:
        if 'FIP' not in proj.columns:
            if set(['IP', 'SO', 'BB', 'HBP', 'HR']).issubset(proj.columns):
                proj['FIP'] = proj.apply(__calc_fip, axis=1)
            else:
                # We don't have FIP, so we can't use that to estimate SP/RP splits. We will just extrapolate values en masse.
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

        orig_gr_per_g = (proj['G'] - proj['GS'])/proj['G']

        #Based on second-order poly regression performed for all pitcher seasons from 2019-2021 with GS > 0 and GRP > 0
        #Regression has dep variable of GRP/G (or (G-GS)/G) and IV IPRP/IP. R^2=0.9481. Possible issues with regression: overweighting
        #of pitchers with GRP/G ratios very close to 0 (starters with few RP appearances) or 1 (relievers with few SP appearances)

        orig_ip_rp = (0.7851*orig_gr_per_g**2 + 0.1937*orig_gr_per_g + 0.0328)*proj['IP']
        orig_ip_sp = proj['IP'] - orig_ip_rp

        # Using FIP and Games started/relieved split, we calculate estimated FIP splits (RP FIP ~ 0.6 lower than SP FIP), use this to estimate counting stat splits, then
        # extrapolate these counting stat rates based on role IP. Ratios are then adjusted accoring to counting stats where possible.

        sp_fip = (proj['IP']*proj['FIP'] + 0.6*orig_ip_rp)/proj['IP']

        fip_ratio =  proj['FIP'] / sp_fip

        new_gr_per_g = (dc_proj['G'] - dc_proj['GS'])/dc_proj['G']
        new_ip_rp = (0.7851*new_gr_per_g**2 + 0.1937*new_gr_per_g + 0.0328)*dc_proj['IP']
        new_ip_sp = dc_proj['IP'] - new_ip_rp

        # Counting stat method created to attempt to match expected PIP split based on FIP split. PIP split calculated as linear regression of no SVH P/IP from FIP 
        # giving a linear coefficient of -1.3274. Approximate match achieved by multiplying non-SO counting stats by the ratio of overall FIP to SP FIP to determine SO
        # counting stats (SO unaltered). 

        for column in proj.columns:
            if column in static_columns or column in dc_columns:
                continue
            if column == 'SO':
                proj[column] = (proj[column] * (dc_proj['IP'] / proj['IP'])).apply(na_to_0)
            elif column == 'SV' or column == 'HLD':
                proj[column] = dc_proj[column]
            else:
                orig_sp_count_stat = (proj[column] * (orig_ip_sp/proj['IP']) / fip_ratio).apply(na_to_0)
                orig_rp_count_stat = proj[column] - orig_sp_count_stat
                proj[column] = ((orig_sp_count_stat / orig_ip_sp * new_ip_sp) + (orig_rp_count_stat / orig_ip_rp * new_ip_rp)).apply(na_to_0)
        for column in dc_columns:
            if column in dc_proj:
                proj[column] = dc_proj[column]
        for column in static_columns:
            try:
                if column == 'K/9':
                    continue
                elif column == 'K%':
                    proj[column] = (proj['SO'] / proj['TBF']).apply(na_to_0)
                elif column == 'BB/9':
                    proj[column] = (proj['BB'] / proj['IP']).apply(na_to_0)
                elif column == 'BB%':
                    proj[column] = (proj['BB'] / proj['TBF']).apply(na_to_0)
                elif column == 'K-BB%':
                    proj[column] = ((proj['SO'] - proj['BB']) / proj['TBF']).apply(na_to_0)
                elif column == 'WHIP':
                    proj[column] = ((proj['H'] + proj['BB']) / proj['IP']).apply(na_to_0)
                elif column == 'ERA':
                    proj[column] = (proj['ER'] / proj['IP'] * 9).apply(na_to_0)
                elif column == 'HR/9':
                    proj[column] = (proj['HR'] / proj['IP'] * 9).apply(na_to_0)
                elif column == 'FIP':
                    proj[column] = ((sp_fip * new_ip_sp + (sp_fip - 0.6) * new_ip_rp) / proj['IP']).apply(na_to_0)
                else:
                    # Leave other values unaltered
                    continue
            except KeyError:
                proj[column] = proj[column]

    return proj

def na_to_0(value) -> float:
    '''Sanitizes NA, NaN, and infinite values to 0'''
    if value == 'NA' or math.isnan(value) or math.isinf(value):
        return 0
    else:
        return value

def save_projection(projection:Projection, projs:List[DataFrame], id_type:IdType, progress=None) -> Projection:
    '''Saves the input projection and projeciton DataFrames to the database and retursn the populated Projection.'''
    with Session() as session:
        seen_players = {}
        for proj in projs:
            stat_cols = proj.columns
            if 'IP' in stat_cols:
                pitch = True
            else:
                pitch = False
            inc_div = math.ceil(len(proj)/25)
            inc_count=0
            for idx, row in proj.iterrows():
                player = None
                if idx in seen_players:
                    player = seen_players[idx]
                    player_proj = projection.get_player_projection(player.index, idx=idx)
                    player_proj.pitcher = False
                    player_proj.two_way = True
                else:
                    if id_type == IdType.FANGRAPHS:
                        player = player_services.get_player_by_fg_id(idx)
                        id = idx
                    elif id_type == IdType.OTTONEU:
                        player = player_services.get_player_by_ottoneu_id(idx)
                        id = idx
                    elif id_type == IdType.MLB:
                        player = player_services.get_player_by_mlb_id(idx)
                        if player:
                            id = player.index
                        else:
                            #TODO: Maybe reimplement this if it's currently the problem
                            #player = player_services.get_player_by_name_and_team(row['Name'], row['Team'])
                            if player:
                                id = player.index
                    elif id_type == IdType.OTB:
                        player = player_services.get_player(idx)
                        id = idx
                    else:
                        raise Exception(f'Unsupported IdType {id_type}')
                    if not player:
                        if id_type == IdType.OTTONEU:
                            player = player_services.create_player(row, ottoneu_id=id)
                        elif id_type == IdType.FANGRAPHS:
                            player = player_services.create_player(row, fg_id=id)
                        else:
                            # Creating a player needs to happen prior to this for non-Ottoneu/FG id_types. At this point it's probably too late, so we ignore
                            continue
                    seen_players[idx] = player
                    player_proj = PlayerProjection()
                    projection.player_projections.append(player_proj)
                    player_proj.projection_data = []
                    player_proj.pitcher = pitch
                    player_proj.two_way = False
                player_proj.player = player
                
                generic_games = False
                for col in stat_cols:
                    if col not in ['Name','Team','-1','PlayerId', 'Last', 'First', 'Lg']:
                        if pitch:
                            stat_type = StatType.get_pitch_stattype(col)
                        else:
                            stat_type = StatType.get_hit_stattype(col)       
                        if col == 'G':
                            generic_games = True 
                            data = ProjectionData()
                            data.stat_type = stat_type
                            data.stat_value = row[col]
                            if data.stat_value is None or math.isnan(data.stat_value):
                                data.stat_value = 0
                            player_proj.projection_data.append(data)
                        elif stat_type: 
                            if player_proj.get_projection_data(stat_type) is None:
                                data = ProjectionData()
                                data.stat_type = stat_type
                                data.stat_value = row[col]
                                try:
                                    if data.stat_value is None or math.isnan(data.stat_value):
                                        data.stat_value = 0
                                except TypeError:
                                    raise TypeError
                                player_proj.projection_data.append(data)
                            else:
                                data = player_proj.get_projection_data(stat_type)
                                if stat_type == StatType.G_HIT:
                                    if not generic_games:
                                        data.stat_value = data.stat_value + row[col]
                                else:
                                    data.stat_value = row[col]
                                    if data.stat_value is None or math.isnan(data.stat_value):
                                        data.stat_value = 0

                
                inc_count += 1
                if inc_count == inc_div and progress is not None:
                    progress.increment_completion_percent(1)
                    inc_count = 0

        session.add(projection)
        session.commit()

        new_proj = get_projection(projection.index, player_data=False) 
    return new_proj

def create_projection_from_upload(projection: Projection, pos_file:str, pitch_file:str, name:str, desc:str='', ros:bool=False, year:int=None, progress=None):
    '''Creates a new projection from user inputs, saves it to the database, and returns the populated projection.'''
    projection.type = ProjectionType.CUSTOM

    projection.name = name
    projection.calculations = []
    projection.dc_pt = False
    projection.detail = desc
    projection.hide = False
    projection.player_projections = []
    projection.ros = ros
    projection.timestamp = datetime.now()
    if not year:
        year = date_util.get_current_ottoneu_year()
    projection.season = year

    if progress is not None:
        progress.set_task_title('Loading projections...')
    pos_df = pd.read_csv(pos_file)
    
    issue_list = normalize_batter_projections(projection, pos_df)

    pos_df = pos_df[pos_df.index.notnull()] #Remove blank rows

    if len(issue_list) > 0:
        raise InputException(issue_list, 'Could not normalize batter projections')

    pitch_df = pd.read_csv(pitch_file)
    issue_list = normalize_pitcher_projections(projection, pitch_df)

    pitch_df = pitch_df[pitch_df.index.notnull()] #Remove blank rows

    return pos_df, pitch_df
    #return save_projection(projection, [pos_df, pitch_df], progress)

def normalize_batter_projections(proj: Projection, df: DataFrame) -> List[str]:
    '''Normalizes and error checks a passed hitter projection DataFrame for later parsing by the Toolbox. Returns a list of errors/issues with the upload.'''
    col_map = {}
    found_id = False
    issue_list = []
    for col in df.columns:
        if '%' in col.upper() or 'INTER' in col.upper() or 'EQ' in col.upper() or 'COMP' in col.upper():
            continue
        if 'ID' in col.upper():
            df.set_index(col, inplace=True)
            found_id = True
        elif 'NAME' == col.upper():
            col_map[col] = 'Name'
        elif 'TEAM' == col.upper():
            col_map[col] = 'Team'
        elif 'G' == col.upper() or 'GAME' in col.upper():
            col_map[col] = 'G'
        elif 'PA' in col.upper():
            col_map[col] = 'PA'
        elif 'BABIP' in col.upper():
            col_map[col] = 'BABIP'
        elif 'AB' in col.upper():
            col_map[col] = 'AB'
        elif 'H' == col.upper() or 'HIT' in col.upper():
            col_map[col] = 'H'
        elif '2B' == col.upper() or 'DOUBLE' in col.upper() or "B2" in col.upper():
            col_map[col] = '2B'
        elif '3B' == col.upper() or 'TRIPLE' in col.upper() or "B3" in col.upper():
            col_map[col] = '3B'
        elif 'HR' == col.upper():
            col_map[col] = 'HR'
        elif 'R' == col.upper() or 'RUN' in col.upper():
            col_map[col] = 'R'
        elif 'RBI' in col.upper():
            col_map[col] = 'RBI'
        elif 'BB' == col.upper() or 'WALK' in col.upper():
            col_map[col] = 'BB'
        elif 'SO' == col.upper() or 'K' == col.upper() or 'STRIKE' in col.upper():
            col_map[col] = 'SO'
        elif 'HBP' in col.upper() or 'BY' in col.upper():
            col_map[col] = 'HBP'
        elif 'SB' == col.upper() or 'STOLEN' in col.upper():
            col_map[col] = 'SB'
        elif 'CS' in col.upper() or 'CAUGHT' in col.upper():
            col_map[col] = 'CS'
        elif 'AVG' in col.upper() or 'BA' == col.upper() or 'AVERAGE' in col.upper():
            col_map[col] = 'AVG'
        elif 'OBP' in col.upper():
            col_map[col] = 'OBP'
        elif 'SLG' in col.upper() or 'SLUG' in col.upper():
            col_map[col] = 'SLG'
    
    if not found_id:
        issue_list.append('No \'ID\' column specified.') 

    df.rename(columns=col_map, inplace=True)

    if 'AVG' not in df.columns and set(['AB', 'H']).issubset(df.columns):
        df['AVG'] = df.apply(calc_average, axis=1)
    if 'OBP' not in df.columns and set(['PA', 'H', 'BB', 'HBP']).issubset(df.columns):
        df['OBP'] = df.apply(calc_obp, axis=1)
    if 'SLG' not in df.columns and set(['H', '2B', '3B', 'HR', 'AB']).issubset(df.columns):
        df['SLG'] = df.apply(calc_slg, axis=1)
    if __must_derive_stat(StatType.NET_SB, [StatType.SB, StatType.CS], df.columns):
        df[StatType.NET_SB.display] = df.apply(__calc_nsb, axis=1)
    if __must_derive_stat(StatType.SINGLE, [StatType.H, StatType.DOUBLE, StatType.TRIPLE, StatType.HR], df.columns):
        df[StatType.SINGLE.display] = df.apply(__calc_singles, axis=1)
    if __must_derive_stat(StatType.TB, [StatType.H, StatType.DOUBLE, StatType.TRIPLE, StatType.HR], df.columns):
        df[StatType.TB.display] = df.apply(__calc_tb, axis=1)
    if __must_derive_stat(StatType.XBH, [StatType.DOUBLE, StatType.TRIPLE, StatType.HR], df.columns):
        df[StatType.XBH.display] = df.apply(__calc_xbh, axis=1)
    
    min_col_set = ['G', 'PA', 'AB']
    if not set(min_col_set).issubset(df.columns):
        issue_list.append('Projection must have the following stats: "G", "PA", "AB"')

    points_req = ['H', '2B', '3B', 'HR', 'BB', 'HBP', 'SB', 'CS']
    proj.valid_points = set(points_req).issubset(df.columns)

    cats_5x5_req = ['R','RBI','HR','SB', 'AVG']
    proj.valid_5x5 = set(cats_5x5_req).issubset(df.columns)

    cats_4x4_req = ['OBP', 'SLG', 'HR', 'R']
    proj.valid_4x4 = set(cats_4x4_req).issubset(df.columns)

    if not (proj.valid_points or proj.valid_5x5 or proj.valid_4x4):
        issue_list.append('Projection does not have sufficient stats for any Ottoneu game type.')
    
    return issue_list

def calc_average(row) -> float:
    '''Calculates hitter batting average based on other columns.'''
    try:
        return row['H'] / row['AB']
    except ZeroDivisionError:
        return 0

def calc_obp(row) -> float:
    '''Calculates approximation of hitter OBP based on other columns. Does not account for sacrifices or catcher's interferance.'''
    #This is not strictly the formula for OBP, as the denominator should remove sac bunts, catcher's interference, etc.
    #But this is close enough for our purposes.
    try:
        return (row['H'] + row['BB'] + row['HBP']) / row['PA']
    except ZeroDivisionError:
        return 0

def calc_slg(row) -> float:
    '''Calculates hitter slugging based on other columns.'''
    try:
        return (row['H'] + row['2B'] + 2*row['3B'] + 3*row['HR']) / row['AB']
    except ZeroDivisionError:
        return 0

def normalize_pitcher_projections(proj: Projection, df: DataFrame) -> List[str]:
    '''Normalizes and error checks a passed pitcher projection DataFrame for later parsing by the Toolbox. Returns a list of errors/issues with the upload.'''
    col_map = {}
    found_id = False
    issue_list = []
    for col in df.columns:
        if '%' in col.upper() or 'INTER' in col.upper() or 'EQ' in col.upper():
            continue
        if 'ID' in col.upper():
            df.set_index(col, inplace=True)
            found_id = True
        elif 'NAME' == col.upper():
            col_map[col] = 'Name'
        elif 'TEAM' == col.upper():
            col_map[col] = 'Team'
        elif 'QS' in col.upper() or 'QUALITY' in col.upper():
            col_map[col] = 'QS'
        elif 'GS' in col.upper() or 'START' in col.upper():
            col_map[col] = 'GS'
        elif 'G' == col.upper() or 'GAME' in col.upper():
            col_map[col] = 'G'
        elif 'FIP' == col.upper():
            col_map[col] = 'FIP'
        elif 'WHIP' in col.upper():
            col_map[col] = 'WHIP'
        elif 'BABIP' in col.upper():
            col_map[col] = 'BABIP'
        elif 'IP' == col.upper() or 'INNING' in col.upper():
            col_map[col] = 'IP'
        elif 'W' == col.upper() or 'WIN' in col.upper():
            col_map[col] = 'W'
        elif 'L' == col.upper() or 'LOSS' in col.upper():
            col_map[col] = 'L'
        elif 'SV' in col.upper() or 'SAVE' in col.upper():
            col_map[col] = 'SV'
        elif 'HLD' in col.upper() or 'HOLD' in col.upper():
            col_map[col] = 'HLD'
        elif 'HR/9' in col.upper():
            col_map[col] = 'HR/9'
        elif 'HR/FB' in col.upper():
            continue
        elif 'HR' == col.upper() or 'HRA' == col.upper() or 'HOME' in col.upper():
            col_map[col] = 'HR'
        elif 'HBP' in col.upper() or 'BY' in col.upper():
            col_map[col] = 'HBP'
        elif 'K/9' in col.upper() or 'SO9' in col.upper():
            col_map[col] = 'K/9'
        elif 'K/' in col.upper():
            continue
        elif 'SO' == col.upper() or 'K' == col.upper():
            col_map[col] = 'SO'
        elif 'ERA' == col.upper():
            col_map[col] = 'ERA'
        elif 'BB/9' in col.upper() or 'BB9' in col.upper():
            col_map[col] = 'BB/9'
        elif 'BB' == col.upper() or 'WALK' in col.upper():
            col_map[col] = 'BB'
        elif 'H' == col.upper() or 'HIT' in col.upper():
            col_map[col] = 'H'
        elif 'ER' == col.upper():
            col_map[col] = 'ER'

    if not found_id:
        issue_list.append('No \'ID\' column specified.') 

    df.rename(columns=col_map, inplace=True)

    if 'HBP' not in df.columns and 'BB' in df.columns:
        # If HBP allowed is blank, fill with pre-calculated regression vs BB
        df[StatType.HBP_ALLOWED.display] = df[StatType.BB_ALLOWED.display].apply(lambda bb: 0.0951*bb+0.4181)
    if 'FIP' not in df.columns and set(['IP', 'SO', 'BB', 'HBP', 'HR']).issubset(df.columns):
        df['FIP'] = df.apply(__calc_fip, axis=1)
    if 'ERA' not in df.columns and set(['IP', 'ER']).issubset(df.columns):
        df['ERA'] = df.apply(__calc_era, axis=1)
    if 'WHIP' not in df.columns and set(['IP', 'H', 'BB']).issubset(df.columns):
        df['WHIP'] = df.apply(__calc_whip, axis=1)
    if 'HR/9' not in df.columns and set(['IP', 'HR']).issubset(df.columns):
        df['HR/9'] = df.apply(__calc_hr_per_9, axis=1)
    if 'BB/9' not in df.columns and set(['IP', 'BB']).issubset(df.columns):
        df['BB/9'] = df.apply(__calc_bb_per_9, axis=1)
    if 'K/9' not in df.columns and set(['IP', 'SO']).issubset(df.columns):
        df['K/9'] = df.apply(__calc_k_per_9, axis=1)
    if 'HLD' not in df.columns:
        df['HLD'] = 0
    if 'SVH' not in df.columns and set(['SV', 'HLD']).issubset(df.columns):
        df['SVH'] = df.apply(__sum_saves_holds, axis=1)
    if 'BS' not in df.columns and set(['G', 'GS', 'SV', 'HLD', 'ERA']).issubset(df.columns):
        df['BS'] = df.apply(__estimate_bs, axis=1)
    if __must_derive_stat(StatType.NET_SAVES, [StatType.SV, StatType.BS], df.columns):
        df[StatType.NET_SAVES.display] = df.apply(__calc_net_saves, axis=1)
    if __must_derive_stat(StatType.NET_SVH, [StatType.SV, StatType.HLD, StatType.BS], df.columns):
        df[StatType.NET_SVH.display] = df.apply(__calc_net_save_holds, axis=1)

    min_col_set = ['G', 'GS', 'IP']
    if not set(min_col_set).issubset(df.columns):
        issue_list.append('Projection must have the following stats: "G", "GS", "IP"')

    points_req = ['H', 'SO', 'BB', 'HR', 'HBP', 'SV', 'HLD']
    proj.valid_points = proj.valid_points and set(points_req).issubset(df.columns)

    cats_5x5_req = ['W','SO','SV','ERA', 'WHIP']
    proj.valid_5x5 = proj.valid_5x5 and set(cats_5x5_req).issubset(df.columns)

    cats_4x4_req = ['ERA', 'WHIP', 'HR/9', 'SO']
    proj.valid_4x4 = proj.valid_4x4 and set(cats_4x4_req).issubset(df.columns)

    if not (proj.valid_points or proj.valid_5x5 or proj.valid_4x4):
        issue_list.append('Projection does not have sufficient stats for any Ottoneu game type.')
    
    return issue_list

def __calc_net_saves(row) -> int:
    '''Calculates the net saves column'''
    return row['SV'] - row['BS']

def __calc_net_save_holds(row) -> int:
    '''Calculates the net save/holds column'''
    return row['SV'] + row['HLD'] - row['BS']

def __sum_saves_holds(row) -> int:
    '''Sums save and hold columns'''
    return row['SV'] + row['HLD']

def __estimate_bs(row) -> int:
    '''Estimates blown saves total based on regression vs relief games, saves, holds, and ERA performed for relief seasons from 2021-23'''
    g_rp = row['G'] - row['GS']
    if g_rp == 0:
        return 0
    reg_bs = int(-0.8425 + 0.0314*g_rp + 0.112 * row['SV'] + 0.0848 * row['HLD'] + 0.1323 * row['ERA'])
    return min(max(0, reg_bs), g_rp - row['SV'] - row['HLD'])

def __calc_singles(row) -> float:
    '''Calculates singles'''
    return row[StatType.H.display] - row[StatType.DOUBLE.display] - row[StatType.TRIPLE.display] - row[StatType.HR.display]

def __calc_tb(row) -> float:
    '''Calculates total bases'''
    return row[StatType.H.display] + row[StatType.DOUBLE.display] + 2*row[StatType.TRIPLE.display] + 3*row[StatType.HR.display]

def __calc_xbh(row) -> float:
    '''Calculates total extra base hits'''
    return row[StatType.DOUBLE.display] + row[StatType.TRIPLE.display] + row[StatType.HR.display]

def __calc_nsb(row) -> float:
    '''Calculates net stolen bases'''
    return row[StatType.SB.display] - row[StatType.CS.display]

def __calc_fip(row) -> float:
    '''Approximates pitcher FIP based on other columns. Assums a FIP constant of 3.15.'''
    #Estimated FIP constant of 3.15. This should work well enough for our purposes, which is determining starter/reliever
    #PIP splits
    try:
        cfip = 3.15
        return (13*row['HR'] + 3*(row['BB'] + row['HBP']) - 2*row['SO']) / row['IP'] + cfip
    except ZeroDivisionError:
        return 9.99

def __calc_era(row) -> float:
    '''Calculates pitcher ERA based on other columns'''
    try:
        return row['ER'] / row['IP'] * 9
    except ZeroDivisionError:
        return 9.99

def __calc_whip(row) -> float:
    '''Calculates pitcher WHIP based on other columns'''
    try:
        return (row['H'] + row['BB']) / row['IP']
    except ZeroDivisionError:
        return 9.99

def __calc_hr_per_9(row) -> float:
    '''Calculates pitcher HR/9 based on other columns'''
    try:
        return row['HR'] / row['IP'] * 9
    except ZeroDivisionError:
        return 9.99

def __calc_bb_per_9(row) -> float:
    '''Calculates pitcher BB/9 based on other columns'''
    try:
        return row['BB'] / row['IP'] * 9
    except ZeroDivisionError:
        return 9.99

def __calc_k_per_9(row) -> float:
    '''Calculates pitcher K/9 based on other columns'''
    try:
        return row['SO'] / row['IP'] * 9
    except ZeroDivisionError:
        return 0
        
def create_projection_from_download(projection: Projection, type:ProjectionType, ros:bool=False, dc_pt:bool=False, year:int=None, progress=None) -> Tuple[DataFrame, DataFrame]:
    '''Creates a Projection based on automatic download and returns the hitter and pitcher dataframes requested.'''
    projection.type = type
    if ros:
        ros_string = ' RoS'
    else:
        ros_string = ' full season'
    if dc_pt:
        dc_string = ' DC Playing Time'
    else:
        dc_string = ''
    projection.name = f"{type.type_name}{ros_string}{dc_string}"
    projection.calculations = []
    projection.dc_pt = dc_pt
    projection.detail = ''
    projection.hide = False
    projection.player_projections = []
    projection.ros = ros
    projection.timestamp = datetime.now()
    projection.valid_points = True 
    projection.valid_5x5 = True
    projection.valid_4x4 = True
    if year == None:
        year = date_util.get_current_ottoneu_year()
    projection.season = year

    if type in ProjectionType.get_fg_downloadable():
        proj_type_url = type.url
        if progress is not None:
            progress.set_task_title('Downloading projections...')
            progress.increment_completion_percent(10)
        projs = download_projections(proj_type_url, ros, dc_pt, progress)
    elif type == ProjectionType.DAVENPORT:
        projs = scrape_davenport.Scrape_Davenport().get_projections()
        for proj in projs:
            proj['OTB_ID'] = proj.apply(__set_otb_id_from_davenport, axis=1)
            proj.set_index('OTB_ID', inplace=True)
    else:
        raise InputException(f"Unhandled projection type passed to create_projection_from_download {type}")
    projection_check(projs)
    return projs[0], projs[1]
    #return save_projection(projection, projs, progress)

def __set_otb_id_from_davenport(row:Series) -> int:
    name = f'{row["First"]} {row["Last"]}'
    player = player_services.get_player_by_mlb_id(row['MLBID'], name=name, team=row['Team'])
    if not player:
        player = player_services.create_player_from_davenport(row)
    return player.index

def __must_derive_stat(stat_type:StatType, base_stats:List[StatType], df_cols:Index) -> bool:
    if any(x in stat_type.stat_list for x in df_cols): return False
    for st in base_stats:
        if not any(x in st.stat_list for x in df_cols): return False
    return True

def projection_check(projs:List[DataFrame]) -> None:
    '''Performs checks for uploaded projections'''
    # Perform checks here, update data as needed
    hit_proj = projs[0]
    if __must_derive_stat(StatType.NET_SB, [StatType.SB, StatType.CS], hit_proj.columns):
        hit_proj[StatType.NET_SB.display] = hit_proj.apply(__calc_nsb, axis=1)
    pitch_proj = projs[1]
    if 'HBP' not in pitch_proj.columns and 'BB' in pitch_proj.columns:
        # If HBP allowed is blank, fill with pre-calculated regression vs BB
        pitch_proj['HBP'] = pitch_proj['BB'].apply(lambda bb: 0.0951*bb+0.4181)
    if 'FIP' not in pitch_proj.columns and set(['IP', 'SO', 'BB', 'HBP', 'HR']).issubset(pitch_proj.columns):
        pitch_proj['FIP'] = pitch_proj.apply(__calc_fip, axis=1)
    if 'ERA' not in pitch_proj.columns and set(['IP', 'ER']).issubset(pitch_proj.columns):
        pitch_proj['ERA'] = pitch_proj.apply(__calc_era, axis=1)
    if 'WHIP' not in pitch_proj.columns and set(['IP', 'H', 'BB']).issubset(pitch_proj.columns):
        pitch_proj['WHIP'] = pitch_proj.apply(__calc_whip, axis=1)
    if 'HR/9' not in pitch_proj.columns and set(['IP', 'HR']).issubset(pitch_proj.columns):
        pitch_proj['HR/9'] = pitch_proj.apply(__calc_hr_per_9, axis=1)
    if 'BB/9' not in pitch_proj.columns and set(['IP', 'BB']).issubset(pitch_proj.columns):
        pitch_proj['BB/9'] = pitch_proj.apply(__calc_bb_per_9, axis=1)
    if 'K/9' not in pitch_proj.columns and set(['IP', 'SO']).issubset(pitch_proj.columns):
        pitch_proj['K/9'] = pitch_proj.apply(__calc_k_per_9, axis=1)
    if 'SVH' not in pitch_proj.columns and set(['SV', 'HLD']).issubset(pitch_proj.columns):
        pitch_proj['SVH'] = pitch_proj.apply(__sum_saves_holds, axis=1)
    if 'BS' not in pitch_proj.columns and set(['G', 'GS', 'SV', 'HLD', 'ERA']).issubset(pitch_proj.columns):
        pitch_proj['BS'] = pitch_proj.apply(__estimate_bs, axis=1)
    if __must_derive_stat(StatType.NET_SAVES, [StatType.SV, StatType.BS], pitch_proj.columns):
        pitch_proj[StatType.NET_SAVES.display] = pitch_proj.apply(__calc_net_saves, axis=1)
    if __must_derive_stat(StatType.NET_SVH, [StatType.SV, StatType.HLD, StatType.BS], pitch_proj.columns):
        pitch_proj[StatType.NET_SVH.display] = pitch_proj.apply(__calc_net_save_holds, axis=1)
    

def get_projection_count() -> int:
    '''Returns number of Projections in database.'''
    with Session() as session:
        count = session.query(Projection).count()
    return count

def get_projection(proj_id: int, player_data=True) -> Projection:
    '''Returns Projection from database by id. Loads PLayer_Projection data if requested.'''
    with Session() as session:
        if player_data:
            proj = (session.query(Projection)
                .options(joinedload(Projection.player_projections))
                .filter_by(index = proj_id).first()
            )
        else:
            proj = session.query(Projection).filter(Projection.index == proj_id).first()
    return proj     

def convert_to_df(proj:Projection) -> List[DataFrame]:
    '''Converts input Projection to a list of DataFrames, index 0 for hitter and index 1 for pitcher.'''
    pos_col = []
    pitch_col = []
    #Loop to get the dataframe columns
    for pp in proj.player_projections:
        if len(pos_col) > 0 and len(pitch_col) > 0:
            break
        if pp.pitcher or pp.two_way and len(pitch_col) == 0:
            for pd in pp.projection_data:
                if not pd.stat_type.hitter:
                    pitch_col.append(pd.stat_type)
        elif not pp.pitcher and not pp.two_way and len(pos_col) == 0:
            for pd in pp.projection_data:
                if pd.stat_type.hitter:
                    pos_col.append(pd.stat_type)
    
    pos_rows = []
    pitch_rows = []
    for pp in proj.player_projections:
        if pp.two_way:
            pos_rows.append(db_rows_to_df(pp, pos_col))
            pitch_rows.append(db_rows_to_df(pp, pitch_col))
        elif pp.pitcher:
            pitch_rows.append(db_rows_to_df(pp, pitch_col))
        else:
            pos_rows.append(db_rows_to_df(pp, pos_col))
    
    pos_proj = DataFrame(pos_rows)
    pitch_proj = DataFrame(pitch_rows)

    pos_header = ['ID', 'Name','Team', 'Position(s)']
    for col in pos_col:
        pos_header.append(col.display)
    pitch_header = ['ID', 'Name', 'Team', 'Position(s)']
    for col in pitch_col:
        pitch_header.append(col.display)
    
    pos_proj.columns = pos_header
    pos_proj.set_index('ID', inplace=True)
    pitch_proj.columns = pitch_header
    pitch_proj.set_index('ID', inplace=True)

    return [pos_proj, pitch_proj]

def db_rows_to_df(player_proj:PlayerProjection, columns):
    row = []
    row.append(player_proj.player.index)
    row.append(player_proj.player.name)
    row.append(player_proj.player.team)
    if player_proj.player.custom_positions:
        row.append(player_proj.player.custom_positions)
    else:
        row.append(player_proj.player.position)
    for col in columns:
        row.append(player_proj.get_stat(col))
    return row

def get_projections_for_current_year() -> List[Projection]:
    '''Returns list of all projections for the current Ottoneu year.'''
    return get_projections_for_year(date_util.get_current_ottoneu_year())

def get_projections_for_year(year:int, inc_hidden:bool=False) -> List[Projection]:
    '''Returns list of all Projections for the input year.'''
    with Session() as session:
        if inc_hidden:
            projs = session.query(Projection).filter(Projection.season == year).all()
        else:
            projs = session.query(Projection).filter(Projection.season == year, Projection.hide == False).all()
    return projs

def get_available_seasons() -> List[int]:
    '''Returns list of all seasons that have at least one projection associated with them, sorted in descending order.'''
    with Session() as session:
        seasons = session.query(Projection.season).distinct().all()
    tmp_seasons = [record.season for record in seasons]
    return sorted(tmp_seasons, reverse=True)

def delete_projection_by_id(proj_id: int) -> None:
    '''Deletes a Projection from the database by index.'''
    with Session() as session:
        proj = session.query(Projection).filter(Projection.index == proj_id).first()
        session.delete(proj)
        session.commit()

def get_player_projection(pp_id: int) -> PlayerProjection:
    '''Returns a PlayerProjection from the database based on index.'''
    with Session() as session:
        return session.query(PlayerProjection).filter(PlayerProjection.index == pp_id).first()

def get_pitcher_role_ips(pp:PlayerProjection) -> Tuple[float, float]:
    '''Calculates the number of innings pitched in relief based on a linear regression using games relieved per total
    games as the independent variable.'''
    if not pp.player.pos_eligible(Position.PITCHER):
        return (0, 0)

    g = pp.get_stat(StatType.G_PIT)
    gs = pp.get_stat(StatType.GS_PIT)
    ip = pp.get_stat(StatType.IP)

    if g is None or gs is None or ip is None:
        return (0, 0)
    if g == 0 or ip == 0:
        return (0, 0)

    if gs == 0:
        return (0, ip)
    
    if gs == g:
        return (ip, 0)

    #Based on second-order poly regression performed for all pitcher seasons from 2019-2021 with GS > 0 and GRP > 0
    #Regression has dep variable of GRP/G (or (G-GS)/G) and IV IPRP/IP. R^2=0.9481. Possible issues with regression: overweighting
    #of pitchers with GRP/G ratios very close to 0 (starters with few RP appearances) or 1 (relievers with few SP appearances)
    gr_per_g = (g - gs) / g
    rp_ip = ip * (0.7851*gr_per_g**2 + 0.1937*gr_per_g + 0.0328)
    return (ip - rp_ip, rp_ip)