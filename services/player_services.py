from datetime import datetime
from sqlalchemy.orm import joinedload

from domain.domain import Player, Salary_Refresh, Salary_Info
from domain.enum import ScoringFormat, Position
from scrape.scrape_ottoneu import Scrape_Ottoneu
from dao.session import Session
from services import salary_services
from util import string_util
from typing import List

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
        player.fg_major_id = player_row['FG MajorLeagueID']
        player.fg_minor_id = player_row['FG MinorLeagueID']
        player.name = player_row['Name']
        player.team = player_row['Org']
        player.position = player_row['Position(s)']
        player.search_name = string_util.normalize(player.name)
    else:
        # This must have come from a FG leaderboard
        if isinstance(fg_id, int) or  fg_id.isnumeric():
            player.fg_major_id = int(fg_id)
        else:
            player.fg_minor_id = fg_id
        player.name = player_row['Name']
        player.search_name = string_util.normalize(player.name)
        player.team = player_row['Team']
        player.position = 'Util'
    player.salary_info = []
    return player

def get_player_by_fg_id(player_id) -> Player:
    '''Returns player from database based on input FanGraphs player id. Will resolve either major or minor league id.'''
    with Session() as session:
        if isinstance(player_id, int) or player_id.isdigit():
            player = session.query(Player).filter(Player.fg_major_id == player_id).first()
        else:
            player = session.query(Player).filter(Player.fg_minor_id == player_id).first()
    return player

def get_player_by_ottoneu_id(ottoneu_id:int) -> Player:
    '''Returns player from database based on input Ottoneu player id.'''
    with Session() as session:
        player = session.query(Player).filter(Player.ottoneu_id == ottoneu_id).first()
    if player is None:
        player = get_player_from_ottoneu_player_page(ottoneu_id, 1)
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
    offense = False
    pitcher = False
    mi = False
    for pos in Position.get_offensive_pos():
        if pos.value in player_pos:
            if not offense and not discrete:
                positions.append(Position.OFFENSE)
                positions.append(Position.POS_UTIL)
                offense = True
            if pos == Position.POS_UTIL and not discrete:
                continue
            positions.append(pos)
            if (pos == Position.POS_2B or pos == Position.POS_SS) and not mi and not discrete:
                positions.append(Position.POS_MI)
                mi = True
    for pos in Position.get_pitching_pos():
        if pos.value in player_pos:
            if not pitcher and not discrete:
                positions.append(Position.PITCHER)
                pitcher = True
            positions.append(pos)
    return positions

def search_by_name(search_str:str, salary_info:bool=True) -> List[Player]:
    '''Returns list of Players whose names match the input string. Search is case-insensitive and matches with diacritics. Includes player salary_info when requested.'''
    with Session() as session:
        if salary_info:
            return session.query(Player).options(joinedload(Player.salary_info)).filter(Player.search_name.contains(search_str)).all()
        else:
            return session.query(Player).filter(Player.search_name.contains(search_str)).all()

def get_player_from_ottoneu_player_page(player_id: int, league_id: int) -> Player:
    '''Scrapes the Ottoneu player page based on Ottoneu player id and League id to retrieve necessary information to populate a player in the Toolbox database.'''
    player_tuple = Scrape_Ottoneu().get_player_from_player_page(player_id, league_id)
    with Session() as session:
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
        session.commit()
    return player