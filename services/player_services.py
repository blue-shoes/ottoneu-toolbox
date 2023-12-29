from datetime import datetime
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from pybaseball import playerid_reverse_lookup
import logging
import numpy

from domain.domain import Player, Salary_Refresh, Salary_Info
from domain.enum import ScoringFormat, Position
from scrape.scrape_ottoneu import Scrape_Ottoneu
from dao.session import Session
from services import salary_services
from util import string_util
from typing import List, Tuple

def create_player_universe() -> None:
    '''Scrapes the Ottoneu overall Average Salary page to get Ottoverse player infromation and save it to the database, creating Players and SalaryInfos as necessary.'''
    player_df = Scrape_Ottoneu().get_avg_salary_ds()
    refresh = Salary_Refresh(format=ScoringFormat.ALL,last_refresh=datetime.now())
    with Session() as session:
        for idx, row in player_df.iterrows():
            player = create_player(row, ottoneu_id=idx)
            salary_services.create_salary(row, 0, player)
            session.add(player)
        session.add(refresh)
        session.commit()

def update_player(player: Player, u_player:list) -> None:
    '''Updates player with new FanGraphs major league id, team, and eligible positions. Expected to be called using values from Ottoneu Average Salaries dataset.'''
    player.fg_major_id = u_player['FG MajorLeagueID']
    player.team = u_player['Org']
    player.position = u_player['Position(s)']

def create_player(player_row:list, ottoneu_id:int=None, fg_id=None) -> Player:
    '''Creates a player with all necessary information, saves it to the database, and returns the loaded Player. Can be from either Ottoneu or FanGraphs dataset.'''
    player = Player()
    if ottoneu_id != None:
        player.ottoneu_id = int(ottoneu_id)
        player.fg_major_id = str(player_row['FG MajorLeagueID'])
        player.fg_minor_id = player_row['FG MinorLeagueID']
        player.name = player_row['Name']
        player.team = player_row['Org']
        player.position = player_row['Position(s)']
        player.search_name = string_util.normalize(player.name)
    else:
        # This must have come from a FG leaderboard
        if isinstance(fg_id, int) or  fg_id.isnumeric():
            player.fg_major_id = str(fg_id)
        else:
            player.fg_minor_id = fg_id
        player.name = player_row['Name']
        player.search_name = string_util.normalize(player.name)
        player.team = player_row['Team']
        player.position = 'Util'
    player.salary_info = []
    return player

def get_player_by_fg_id(player_id, force_major:bool=False) -> Player:
    '''Returns player from database based on input FanGraphs player id. Will resolve either major or minor league id by default. If force_major is true, will only look for major league id'''
    with Session() as session:
        if force_major:
            player = session.query(Player).filter(Player.fg_major_id == player_id).first()
        elif isinstance(player_id, int) or isinstance(player_id, numpy.int64) or isinstance(player_id, numpy.int32) or player_id.isdigit():
            player = session.query(Player).filter(Player.fg_major_id == int(player_id)).first()
        else:
            player = session.query(Player).filter(Player.fg_minor_id == player_id).first()
    return player

def get_player_by_ottoneu_id(ottoneu_id:int, pd=None) -> Player:
    '''Returns player from database based on input Ottoneu player id.'''
    with Session() as session:
        player = session.query(Player).filter(Player.ottoneu_id == ottoneu_id).first()
    if player is None:
        player = get_player_from_ottoneu_player_page(ottoneu_id, 1, pd=pd)
        player = session.query(Player).filter(Player.ottoneu_id == ottoneu_id).first()
    return player

def is_populated() -> bool:
    '''Checks if the player universe has been initially populated.'''
    with Session() as session:
        count = session.query(Player).count()
    return count > 0

def get_player(player_id:int) -> Player:
    '''Returns player from database based on Toolbox player id.'''
    with Session() as session:
        return session.query(Player).filter(Player.index == player_id).first()

def get_player_positions(player:Player, discrete=False) -> List[Position]:
    '''Returns list of Positions the player is eligible fore based on paring the Player.position attribute. If discrete is false, OFFENSE, PITCHING, MI, and UTIL 
    are added to player where appropriate. If discrete is true, these are not added, other than UTIL where the player is not eligible at any other position.'''
    positions = []
    player_pos = player.position.split("/")
    for pos in Position.get_offensive_pos():
        if pos.value in player_pos:
            if Position.OFFENSE not in positions and not discrete:
                positions.append(Position.OFFENSE)
                positions.append(Position.POS_UTIL)
            if pos == Position.POS_UTIL and not discrete:
                continue
            positions.append(pos)
            if (pos == Position.POS_2B or pos == Position.POS_SS) and Position.POS_MI not in positions and not discrete:
                positions.append(Position.POS_MI)
            if (pos == Position.POS_1B or pos == Position.POS_3B) and Position.POS_CI not in positions and not discrete:
                positions.append(Position.POS_CI) 
            if (pos == Position.POS_1B or pos == Position.POS_3B or pos == Position.POS_2B or pos == Position.POS_SS) \
                    and Position.POS_INF not in positions and not discrete:
                positions.append(Position.POS_INF) 
            if (pos == Position.POS_LF or pos == Position.POS_CF or pos == Position.POS_RF) and Position.POS_OF not in positions and not discrete:
                positions.append(Position.POS_OF)
    for pos in Position.get_pitching_pos():
        if pos.value in player_pos:
            if Position.PITCHER not in positions and not discrete:
                positions.append(Position.PITCHER)
                positions.append(Position.POS_P)
            positions.append(pos)
    return positions

def search_by_name(search_str:str, salary_info:bool=True) -> List[Player]:
    '''Returns list of Players whose names match the input string. Search is case-insensitive and matches with diacritics. Includes player salary_info when requested.'''
    with Session() as session:
        if salary_info:
            return session.query(Player).options(joinedload(Player.salary_info)).filter(Player.search_name.contains(search_str)).all()
        else:
            return session.query(Player).filter(Player.search_name.contains(search_str)).all()

def get_player_from_ottoneu_player_page(player_id: int, league_id: int, session:Session=None, pd=None) -> Player:
    '''Scrapes the Ottoneu player page based on Ottoneu player id and League id to retrieve necessary information to populate a player in the Toolbox database.'''
    logging.info(f'Importing player {player_id} from player page')
    if pd is not None:
        pd.set_task_title(f'Populating Ottoneu Id {player_id}')
    player_tuple = Scrape_Ottoneu().get_player_from_player_page(player_id, league_id)
    if session is None:
        with Session() as session2:
            player = update_from_player_page(player_tuple, session2)
            session2.commit()
            return player
    else:
        return update_from_player_page(player_tuple, session)

def get_player_by_name_and_team_with_no_yahoo_id(name:str, team:str, session) -> Player:
    if '(Batter)' in name.split() or '(Pitcher)' in name.split():
        # Handle two-way players
        name = ' '.join(name.split()[:-1])
    name = string_util.normalize(name)
    players = session.query(Player).options(joinedload(Player.salary_info)).filter(and_(Player.search_name.contains(name), Player.yahoo_id.is_(None))).all()
    if len(players) == 0:
        name_array = name.split()
        last_idx = -1
        players = session.query(Player).options(joinedload(Player.salary_info)).filter(and_(Player.search_name.contains(name_array[-1]), Player.yahoo_id.is_(None))).all()
        if len(players) == 0 and len(name_array) > 2:
            last_idx = -2
        i = 1
        if len(players) != 1:
            while True: 
                if i >= len(name_array[0]):
                    break
                name = f'{name_array[0][:i]}% {name_array[last_idx]}'
                tmp_players = session.query(Player).options(joinedload(Player.salary_info)).filter(and_(Player.search_name.contains(name), Player.yahoo_id.is_(None))).all()
                if len(tmp_players) < 1:
                    break
                players = tmp_players
                if len(players) == 1:
                    break
                i += 1
        
    players.sort(reverse=True, key=lambda p: p.get_salary_info_for_format().roster_percentage)
    if players is not None and len(players) > 0:
        player = players[0]
        for possible_player in players:
            if match_team(possible_player, team):
                player = possible_player
                break
    else:
        player = None    
    return player

def get_player_by_name_and_team(name:str, team:str) -> Player:
    '''Returns player by matching name and team. Full name match is attempted. If no matches found with full name, partial
    matches beginning with just last name are attempted, followed by adding one letter at a time from the start of the first
    name. If the final search by name returns multiple players, they are ordered by roster percentage highest to lowest, and the
    first player with a matching team is returned. If no players match the input team when multiple match the name criteria, None 
    is returned.'''
    name = string_util.normalize(name)
    players = search_by_name(name)
    if len(players) == 0:
        name_array = name.split()
        i = 0

        while True: 
            if i >= len(name_array[0]):
                break
            if i == 0:
                name = name_array[-1]
            else:
                name = f'{name_array[0][:i]}% {name_array[-1]}'
            tmp_players = search_by_name(name_array[-1])
            if len(tmp_players) < 1:
                break
            players = tmp_players
            if len(players) == 1:
                break
            i += 1
        
    players.sort(reverse=True, key=lambda p: p.get_salary_info_for_format().roster_percentage)
    if players is not None and len(players) > 0:
        player = players[0]
        for possible_player in players:
            if match_team(possible_player, team):
                player = possible_player
                break
    else:
        player = None    
    return player

def match_team(player:Player, team_name:str) -> bool:
    if player.team is None:
        return False
    db_team = player.team.split(" ")[0]
    if db_team == team_name:
        return True
    map = {'TBY': 'TBR',
           'CWS': 'CHW',
           'WAS': 'WSN',
           'AZ' : 'ARI',
           'KC' : 'KCR',
           'SD' : 'SDP',
           'SF' : 'SFG',
           'TB' : 'TBR',
           'WSH': 'WSN'}
    if team_name in map:
        return db_team == map.get(team_name)
    return False

def update_from_player_page(player_tuple:Tuple[int, str, str, str, str], session:Session) -> Player:
    fg_id = player_tuple[4]
    player = get_player_by_fg_id(fg_id)
    if player is None:
        player = Player()
        player.name = player_tuple[1]
        player.search_name = string_util.normalize(player.name)
        session.add(player)
        if isinstance(fg_id, int) or  fg_id.isnumeric():
            player.fg_major_id = int(fg_id)
        else:
            player.fg_minor_id = fg_id
    player.ottoneu_id = int(player_tuple[0])
    
    player.team = player_tuple[2]
    player.position = player_tuple[3]

    player.salary_info = []
    sal_info = Salary_Info()
    sal_info.avg_salary = 0
    sal_info.format = ScoringFormat.ALL
    sal_info.last_10 = 0
    sal_info.max_salary = 0
    sal_info.med_salary = 0
    sal_info.min_salary = 0
    sal_info.roster_percentage = 0
    player.salary_info.append(sal_info)
    session.add(sal_info)
    #session.commit()
    return player

def get_player_by_mlb_id(player_id:int) -> Player:
    '''Retrieves a player by MLB Id using the pybaseball playerid_reverse_lookup function to find FanGraphs id'''
    fg_id = get_fg_id_by_mlb_id(player_id)
    return get_player_by_fg_id(fg_id)

def get_fg_id_by_mlb_id(player_id:int) -> str:
    '''Retrieves a player's FanGraphs Id by MLB Id using the pybaseball playerid_reverse_lookup function'''
    p_df = playerid_reverse_lookup([player_id])
    if len(p_df) > 0:
        return p_df.loc[0,'key_fangraphs']
    else:
        return -1
    
def get_player_by_yahoo_id(yahoo_id:int) -> Player:
    '''Gets the Player by their Yahoo id'''
    with Session() as session:
        return get_player_by_yahoo_id_with_session(yahoo_id, session)

def get_player_by_yahoo_id_with_session(yahoo_id:int, session) -> Player:
    '''Gets the Player by their Yahoo id with the given session'''
    return session.query(Player).filter(Player.yahoo_id == yahoo_id).first()  

def set_player_yahoo_id_with_session(player_id:int, yahoo_id:int, session) -> Player:
    '''Sets the Yahoo id for the given player id'''
    player = session.query(Player).filter(Player.index == player_id).first()
    player.yahoo_id = yahoo_id
    session.commit()
    return session.query(Player).filter(Player.index == player_id).first()