from pandas import DataFrame
from domain.domain import PlayerProjection, Projection, ProjectionData
from scrape import scrape_fg
from domain.enum import ProjectionType, StatType, IdType
from domain.exception import FangraphsException, InputException
from datetime import datetime
from services import player_services, browser_services
from dao.session import Session
from sqlalchemy.orm import joinedload
import pandas as pd
import math
from util import date_util

def download_projections(projection, ros=False, dc_pt=False, progress=None):
    """Returns a list of projection dataframes. Item 1 is the batting projections. Item 2 is the pitching projections"""

    if ros:
        if projection == 'steamer':
            #steamer has a different convention for reasons
            projection = 'steamerr'
        else:
            projection = 'r' + projection
    try:
        fg_scraper = scrape_fg.Scrape_Fg(browser_services.get_desired_browser())
        pos_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type={projection}&team=0&lg=all&players=0", f'{projection}_pos.csv', True)
        #THE BAT X does not have pitcher projections, so revert them to simply THE BAT
        if progress is not None:
            progress.increment_completion_percent(20)
        if projection == 'thebatx':
            pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type=thebat&team=0&lg=all&players=0", f'thebat_pitch.csv', True)     
        elif projection == 'thebatxr':
            fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type=thebatr&team=0&lg=all&players=0", f'thebatr_pitch.csv', True)
        else:
            pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type={projection}&team=0&lg=all&players=0", f'{projection}_pitch.csv', True)
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
    
    if len(pos_proj) == 0 or len(pitch_proj) == 0:
        raise FangraphsException('Projection set does not exist')
    
    return [pos_proj, pitch_proj]

def convertToDcPlayingTime(proj, ros, position, fg_scraper=None):
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
            dc_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type={dc_set}&team=0&lg=all&players=0", f'{dc_set}_pos.csv', True)
        else:
            dc_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type={dc_set}&team=0&lg=all&players=0", f'{dc_set}_pitch.csv', True)
    finally:
        if close:
            fg_scraper.close()

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

def save_projection(projection, projs, id_type, progress=None):
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
                if idx in seen_players:
                    player = seen_players[idx]
                    player_proj = projection.get_player_projection(player.index)
                    player_proj.pitcher = False
                    player_proj.two_way = True
                else:
                    if id_type == IdType.FANGRAPHS:
                        player = player_services.get_player_by_fg_id(idx)
                    elif id_type == IdType.OTTONEU:
                        player = player_services.get_player_by_ottoneu_id(idx)
                    else:
                        raise Exception(f'Unsupported IdType {id_type}')
                    if player == None:
                        player = player_services.create_player(row, fg_id=idx)
                    seen_players[idx] = player
                    player_proj = PlayerProjection()
                    projection.player_projections.append(player_proj)
                    player_proj.projection_data = []
                    player_proj.pitcher = pitch
                    player_proj.two_way = False
                player_proj.player = player
                
                for col in stat_cols:
                    if col not in ['Name','Team','-1','playerid']:
                        if pitch:
                            stat_type = StatType.pitch_to_enum_dict().get(col)
                        else:
                            stat_type = StatType.hit_to_enum_dict().get(col)                            
                        if stat_type != None:
                            data = ProjectionData()
                            data.stat_type = stat_type
                            data.stat_value = row[col]
                            if data.stat_value is None or math.isnan(data.stat_value):
                                data.stat_value = 0
                            player_proj.projection_data.append(data)
                
                inc_count += 1
                if inc_count == inc_div and progress is not None:
                    progress.increment_completion_percent(1)
                    inc_count = 0

        session.add(projection)
        session.commit()

        new_proj = get_projection(projection.index, player_data=False) 
    return new_proj

def create_projection_from_upload(projection, pos_file, pitch_file, name, desc='', ros=False, year=None, progress=None):
    projection.type = ProjectionType.CUSTOM

    projection.name = name
    projection.calculations = []
    projection.dc_pt = False
    projection.detail = desc
    projection.hide = False
    projection.player_projections = []
    projection.ros = ros
    projection.timestamp = datetime.now()
    if year == None:
        year = date_util.get_current_ottoneu_year()
    projection.season = year

    if progress is not None:
        progress.set_task_title('Loading projections...')
    pos_df = pd.read_csv(pos_file)
    
    issue_list = normalize_batter_projections(projection, pos_df)

    if len(issue_list) > 0:
        raise InputException(issue_list, 'Could not normalize batter projections')

    pitch_df = pd.read_csv(pitch_file)
    issue_list = normalize_pitcher_projections(projection, pitch_df)

    return pos_df, pitch_df
    #return save_projection(projection, [pos_df, pitch_df], progress)

def normalize_batter_projections(proj: Projection, df: DataFrame):
    col_map = {}
    found_id = False
    issue_list = []
    for col in df.columns:
        if 'ID' in col.upper():
            df.set_index(col, inplace=True)
            found_id = True
        elif 'G' == col.upper() or 'GAME' in col.upper():
            col_map[col] = 'G'
        elif 'PA' in col.upper():
            col_map[col] = 'PA'
        elif 'AB' in col.upper():
            col_map[col] = 'AB'
        elif 'H' == col.upper() or 'HIT' in col.upper():
            col_map[col] = 'H'
        elif '2B' in col.upper() or 'DOUBLE' in col.upper():
            col_map[col] = '2B'
        elif '3B' in col.upper() or 'TRIPLE' in col.upper():
            col_map[col] = '3B'
        elif 'HR' in col.upper():
            col_map[col] = 'HR'
        elif 'R' == col.upper() or 'RUN' in col.upper():
            col_map[col] = 'R'
        elif 'RBI' in col.upper():
            col_map[col] = 'RBI'
        elif 'BB' in col.upper() or 'WALK' in col.upper():
            col_map[col] = 'BB'
        elif 'SO' in col.upper() or 'K' == col.upper() or 'STRIKE' in col.upper():
            col_map[col] = 'SO'
        elif 'HBP' in col.upper() or 'BY' in col.upper():
            col_map[col] = 'HBP'
        elif 'SB' in col.upper() or 'STOLEN' in col.upper():
            col_map[col] = 'SB'
        elif 'CS' in col.upper() or 'CAUGHT' in col.upper():
            col_map[col] = 'CS'
        elif 'AVG' in col.upper() or 'BA' == col.upper() or 'AVERAGE' in col.upper():
            col_map[col] = 'AVG'
        elif 'OBP' in col.upper() or 'ON' in col.upper():
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

def calc_average(row):
    return row['H'] / row['AB']

def calc_obp(row):
    #This is not strictly the formula for OBP, as the denominator should remove sac bunts, catcher's interference, etc.
    #But this is close enough for our purposes.
    return (row['H'] + row['BB'] + row['HBP']) / row['PA']

def calc_slg(row):
    return (row['H'] + row['2B'] + 2*row['3B'] + 3*row['HR']) / row['AB']

def normalize_pitcher_projections(proj: Projection, df: DataFrame):
    col_map = {}
    found_id = False
    issue_list = []
    for col in df.columns:
        if 'ID' in col.upper():
            df.set_index(col, inplace=True)
            found_id = True
        elif 'QS' in col.upper() or 'QUALITY' in col.upper():
            col_map[col] = 'QS'
        elif 'GS' in col.upper() or 'START' in col.upper():
            col_map[col] = 'GS'
        elif 'G' == col.upper() or 'GAME' in col.upper():
            col_map[col] = 'G'
        elif 'FIP' in col.upper():
            col_map[col] = 'FIP'
        elif 'WHIP' in col.upper():
            col_map[col] = 'WHIP'
        elif 'IP' in col.upper() or 'INNING' in col.upper():
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
        elif 'HR' in col.upper() or 'HOME' in col.upper():
            col_map[col] = 'HR'
        elif 'HBP' in col.upper() or 'BY' in col.upper():
            col_map[col] = 'HBP'
        elif 'K/9' in col.upper():
            col_map[col] = 'K/9'
        elif 'SO' in col.upper() or 'K' in col.upper():
            col_map[col] = 'SO'
        elif 'ERA' in col.upper():
            col_map[col] = 'ERA'
        elif 'BB/9' in col.upper():
            col_map[col] = 'BB/9'
        elif 'BB' in col.upper() or 'WALK' in col.upper():
            col_map[col] = 'BB'
        elif 'H' == col.upper() or 'HIT' in col.upper():
            col_map[col] = 'H'
        elif 'ER' in col.upper():
            col_map[col] = 'ER'

    if not found_id:
        issue_list.append('No \'ID\' column specified.') 

    df.rename(columns=col_map, inplace=True)

    if 'HBP' not in df.columns and 'BB' in df.columns:
        # If HBP allowed is blank, fill with pre-calculated regression vs BB
        df[StatType.enum_to_display_dict()[StatType.HBP_ALLOWED]] = df[StatType.enum_to_display_dict()[StatType.BB_ALLOWED]].apply(lambda bb: 0.0951*bb+0.4181)
    if 'FIP' not in df.columns and set(['IP', 'SO', 'BB', 'HBP', 'HR']).issubset(df.columns):
        df['FIP'] = df.apply(calc_fip, axis=1)
    if 'ERA' not in df.columns and set(['IP', 'ER']).issubset(df.columns):
        df['ERA'] = df.apply(calc_era, axis=1)
    if 'WHIP' not in df.columns and set(['IP', 'H', 'BB']).issubset(df.columns):
        df['WHIP'] = df.apply(calc_whip, axis=1)
    if 'HR/9' not in df.columns and set(['IP', 'HR']).issubset(df.columns):
        df['HR/9'] = df.apply(calc_hr_per_9, axis=1)
    if 'BB/9' not in df.columns and set(['IP', 'BB']).issubset(df.columns):
        df['BB/9'] = df.apply(calc_bb_per_9, axis=1)
    if 'K/9' not in df.columns and set(['IP', 'SO']).issubset(df.columns):
        df['K/9'] = df.apply(calc_k_per_9, axis=1)
    if 'HLD' not in df.columns:
        df['HLD'] = 0

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

def calc_fip(row):
    #Estimated FIP constant of 3.15. This should work well enough for our purposes, which is determining starter/reliever
    #PIP splits
    cfip = 3.15
    return (13*row['HR'] + 3*(row['BB'] + row['HBP']) - 2*row['SO']) / row['IP'] + cfip

def calc_era(row):
    return row['ER'] / row['IP'] * 9

def calc_whip(row):
    return (row['H'] + row['BB']) / row['IP']

def calc_hr_per_9(row):
    return row['HR'] / row['IP'] * 9

def calc_bb_per_9(row):
    return row['BB'] / row['IP'] * 9

def calc_k_per_9(row):
    return row['SO'] / row['IP'] * 9

def create_projection_from_download(projection, type, ros=False, dc_pt=False, year=None, progress=None):
    projection.type = type
    if ros:
        ros_string = ' RoS'
    else:
        ros_string = ' full season'
    if dc_pt:
        dc_string = ' DC Playing Time'
    else:
        dc_string = ''
    projection.name = f"{ProjectionType.enum_to_name_dict().get(type)}{ros_string}{dc_string}"
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

    proj_type_url = ProjectionType.enum_to_url().get(type)
    if progress is not None:
        progress.set_task_title('Downloading projections...')
        progress.increment_completion_percent(10)
    projs = download_projections(proj_type_url, ros, dc_pt, progress)
    projection_check(projs)
    return projs[0], projs[1]
    #return save_projection(projection, projs, progress)

def projection_check(projs):
    # Perform checks here, update data as needed
    pitch_proj = projs[1]
    if StatType.enum_to_display_dict()[StatType.HBP_ALLOWED] not in pitch_proj.columns:
        # If HBP allowed is blank, fill with pre-calculated regression vs BB
        pitch_proj[StatType.enum_to_display_dict()[StatType.HBP_ALLOWED]] = pitch_proj[StatType.enum_to_display_dict()[StatType.BB_ALLOWED]].apply(lambda bb: 0.0951*bb+0.4181)

def get_projection_count():
    with Session() as session:
        count = session.query(Projection).count()
    return count

def get_projection(proj_id, player_data=True):
    with Session() as session:
        if player_data:
            proj = (session.query(Projection)
                .options(joinedload(Projection.player_projections))
                .filter_by(index = proj_id).first()
            )
        else:
            proj = session.query(Projection).filter(Projection.index == proj_id).first()
    return proj     

def convert_to_df(proj):
    pos_col = []
    pitch_col = []
    #Loop to get the dataframe columns
    for pp in proj.player_projections:
        if len(pos_col) > 0 and len(pitch_col) > 0:
            break
        if pp.pitcher and len(pitch_col) == 0:
            for pd in pp.projection_data:
                pitch_col.append(pd.stat_type)
        elif not pp.pitcher and len(pos_col) == 0:
            for pd in pp.projection_data:
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
        pos_header.append(StatType.enum_to_display_dict().get(col))
    pitch_header = ['ID', 'Name', 'Team', 'Position(s)']
    for col in pitch_col:
        pitch_header.append(StatType.enum_to_display_dict().get(col))
    
    pos_proj.columns = pos_header
    pos_proj.set_index('ID', inplace=True)
    pitch_proj.columns = pitch_header
    pitch_proj.set_index('ID', inplace=True)

    return [pos_proj, pitch_proj]

def db_rows_to_df(player_proj, columns):
    row = []
    row.append(player_proj.player.index)
    row.append(player_proj.player.name)
    row.append(player_proj.player.team)
    row.append(player_proj.player.position)
    for col in columns:
        row.append(player_proj.get_stat(col))
    return row

def get_projections_for_current_year():
    return get_projections_for_year(date_util.get_current_ottoneu_year())

def get_projections_for_year(year, inc_hidden=False):
    with Session() as session:
        if inc_hidden:
            projs = session.query(Projection).filter(Projection.season == year).all()
        else:
            projs = session.query(Projection).filter(Projection.season == year, Projection.hide == False).all()
    return projs

def get_available_seasons():
    with Session() as session:
        seasons = session.query(Projection.season).distinct().all()
    tmp_seasons = [record.season for record in seasons]
    return sorted(tmp_seasons, reverse=True)

def delete_projection_by_id(proj_id):
    with Session() as session:
        proj = session.query(Projection).filter(Projection.index == proj_id).first()
        session.delete(proj)
        session.commit()

def get_player_projection(pp_id):
    with Session() as session:
        return session.query(PlayerProjection).filter(PlayerProjection.index == pp_id).first()
