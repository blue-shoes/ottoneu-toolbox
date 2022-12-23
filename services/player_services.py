from datetime import datetime
from domain.domain import Player, Salary_Refresh
from domain.enum import ScoringFormat, Position
from scrape.scrape_ottoneu import Scrape_Ottoneu
from dao.session import Session
from services import salary_services

def create_player_universe():
    player_df = Scrape_Ottoneu().get_avg_salary_ds()
    refresh = Salary_Refresh(format=ScoringFormat.ALL,last_refresh=datetime.now())
    with Session() as session:
        for idx, row in player_df.iterrows():
            player = create_player(row, ottoneu_id=idx)
            salary_services.create_salary(row, 0, player)
            session.add(player)
        session.add(refresh)
        session.commit()

def update_player(player, u_player):
        player.fg_major_id = u_player['FG MajorLeagueID']
        player.team = u_player['Org']
        player.position = u_player['Position(s)']

def create_player(player_row, ottoneu_id=None, fg_id=None):
        player = Player()
        if ottoneu_id != None:
            player.ottoneu_id = int(ottoneu_id)
            player.fg_major_id = player_row['FG MajorLeagueID']
            player.fg_minor_id = player_row['FG MinorLeagueID']
            player.name = player_row['Name']
            player.team = player_row['Org']
            player.position = player_row['Position(s)']
        else:
            # This must have come from a FG leaderboard
            if isinstance(fg_id, int) or  fg_id.isnumeric():
                player.fg_major_id = int(fg_id)
            else:
                player.fg_minor_id = fg_id
            player.name = player_row['Name']
            player.team = player_row['Team']
            player.position = 'Util'
        player.salary_info = []
        return player

def get_player_by_fg_id(player_id):
    with Session() as session:
        if player_id.isdigit():
            player = session.query(Player).filter(Player.fg_major_id == player_id).first()
        else:
            player = session.query(Player).filter(Player.fg_minor_id == player_id).first()
    return player

def get_player_by_ottoneu_id(ottoneu_id):
    with Session() as session:
        return session.query(Player).filter(Player.ottoneu_id == ottoneu_id).first()

def is_populated():
    with Session() as session:
        count = session.query(Player).count()
    return count > 0

def get_player(player_id) -> Player:
    with Session() as session:
        return session.query(Player).filter(Player.index == player_id).first()

def get_player_positions(player):
    positions = []
    player_pos = player.position.split("/")
    offense = False
    pitcher = False
    mi = False
    for pos in Position.get_offensive_pos():
        if pos.value in player_pos:
            if not offense:
                positions.append(Position.OFFENSE)
                positions.append(Position.POS_UTIL)
                offense = True
            if pos == Position.POS_UTIL:
                continue
            positions.append(pos)
            if (pos == Position.POS_2B or pos == Position.POS_SS) and not mi:
                positions.append(Position.POS_MI)
                mi = True
    for pos in Position.get_pitching_pos():
        if pos.value in player_pos:
            if not pitcher:
                positions.append(Position.PITCHER)
                pitcher = True
            positions.append(pos)
    return positions