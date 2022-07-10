from domain.domain import Player, PlayerProjection, Projection, ProjectionData
from scrape import scrape_fg
from domain.enum import ProjectionType
from datetime import datetime
from services import player_services
from dao.session import Session

def get_projections(projection, ros=False, dc_pt=False):
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

def create_projection(type, ros=False, dc_pt=False):
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
    projection.name = f"{ProjectionType.enum_to_name_dict[type]}{ros_string}{dc_string}"
    projection.calculations = []
    projection.dc_pt = dc_pt
    projection.detail = ''
    projection.hide = False
    projection.player_projections = []
    projection.ros = ros
    projection.timestamp = datetime.now()

    projs = get_projections(type, ros, dc_pt)

    with Session as session:
        for proj in projs:
            stat_cols = proj.columns
            for idx, row in proj:
                player = player_services.get_player_by_fg_id(idx)
                if player == None:
                    player = player_services.create_player(idx, row)
                player_proj = PlayerProjection()
                player_proj.player = player
                player_proj.projection = projection
                projection.player_projections.append(player_proj)
                player_proj.projection_data = []
                for col in stat_cols:
                    if col not in ['Name','Team','-1','playerid']:
                        data = ProjectionData()
                        data.player_projection = player_proj
                        player_proj.append(data)
                        data.stat_type = col
                        data.stat_value = row[col]
        session.add(projection)
        session.commit()

