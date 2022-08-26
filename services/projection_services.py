from pandas import DataFrame
from domain.domain import Player, PlayerProjection, Projection, ProjectionData
from scrape import scrape_fg
from domain.enum import ProjectionType, StatType
from datetime import datetime
from services import player_services
from dao.session import Session
from sqlalchemy.orm import joinedload, load_only
import pandas as pd
import math

def download_projections(projection, ros=False, dc_pt=False):
    """Returns a list of projection dataframes. Item 1 is the batting projections. Item 2 is the pitching projections"""

    if ros:
        if projection == 'steamer':
            #steamer has a different convention for reasons
            projection = 'steamerr'
        else:
            projection = 'r' + projection
    try:
        fg_scraper = scrape_fg.Scrape_Fg()
        pos_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type={projection}&team=0&lg=all&players=0", f'{projection}_pos.csv', True)
        #THE BAT X does not have pitcher projections, so revert them to simply THE BAT
        if projection == 'thebatx':
            pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type=thebat&team=0&lg=all&players=0", f'thebat_pitch.csv', True)     
        elif projection == 'thebatxr':
            fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type=thebatr&team=0&lg=all&players=0", f'thebatr_pitch.csv', True)
        else:
            pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type={projection}&team=0&lg=all&players=0", f'{projection}_pitch.csv', True)

        if dc_pt:
            pos_proj = convertToDcPlayingTime(pos_proj, ros, True, fg_scraper)
            pitch_proj = convertToDcPlayingTime(pitch_proj, ros, False, fg_scraper)

    finally:
        fg_scraper.close()
    
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
            fg_scraper = scrape_fg.Scrape_Fg()
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

def save_projection(projection, projs, progress=None):
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
                else:
                    player = player_services.get_player_by_fg_id(idx)
                    if player == None:
                        player = player_services.create_player(row, fg_id=idx)
                    seen_players[idx] = player
                player_proj = PlayerProjection()
                player_proj.player = player
                player_proj.pitcher = pitch
                player_proj.projection_data = []
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
                            player_proj.projection_data.append(data)
                projection.player_projections.append(player_proj)
                inc_count += 1
                if inc_count == inc_div and progress is not None:
                    progress.increment_completion_percent(1)
                    inc_count = 0

        session.add(projection)
        session.commit()

        new_proj = get_projection(projection.index, player_data=False) 
    return new_proj

def create_projection_from_upload(pos_file, pitch_file, name, desc='', ros=False, year=None, progress=None):
    projection = Projection()
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
        year = get_current_projection_year()
    projection.season = year

    if progress is not None:
        progress.set_task_title('Loading projections...')
    pos_df = pd.read_csv(pos_file)
    pitch_df = pd.read_csv(pitch_file)
    # TODO: Need to confirm data matches expected format/headers/index
    if progress is not None:
        progress.increment_completion_percent(50)
        progress.set_task_title('Saving projections to database...')
    return save_projection(projection, [pos_df, pitch_df])

def create_projection_from_download(type, ros=False, dc_pt=False, year=None, progress=None):
    projection = Projection()
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
    if year == None:
        year = get_current_projection_year()
    projection.season = year

    proj_type_url = ProjectionType.enum_to_url().get(type)
    if progress is not None:
        progress.set_task_title('Downloading projections...')
    projs = download_projections(proj_type_url, ros, dc_pt)
    projection_check(projs)
    if progress is not None:
        progress.increment_completion_percent(50)
        progress.set_task_title('Saving projections to database...')
    return save_projection(projection, projs, progress)

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
                .options(joinedload(Projection.player_projections)
                .options(joinedload(PlayerProjection.projection_data))
                .options(joinedload(PlayerProjection.player)))
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
        if pp.pitcher:
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

def get_current_projection_year():
    """Gets the current year for projections. Assumes October and later is next year, otherwise current year"""
    now = datetime.now()
    if now.month > 9:
        return now.year + 1
    else:
        return now.year

def get_projections_for_current_year():
    return get_projections_for_year(get_current_projection_year)

def get_projections_for_year(year):
    with Session() as session:
        projs = session.query(Projection).filter(Projection.season == year).all()
    return projs

def get_available_seasons():
    with Session() as session:
        seasons = session.query(Projection).options(load_only(Projection.season)).distinct().all()
    tmp_seasons = [record.season for record in seasons]
    return sorted(tmp_seasons, reverse=True)
