from yfpy.query import YahooFantasySportsQuery as yfs_query
from yfpy import Team as YTeam, League as YLeague, Settings as YSettings, Player as YPlayer
from pathlib import Path
from oauth.custom_yahoo_oauth import Custom_OAuth2

from domain.domain import League, Roster_Spot
from services import player_services

import json
from typing import List
import datetime

def get_league_metadata(league_id:int) -> YLeague:
    '''Gets the league metadata as a yfpy.League object'''
    q = __create_query(league_id)
    return q.get_league_metadata()

def get_teams(league_id:int) -> List[YTeam]:
    '''Gets the list of league teams as a list of yfpy.Team objects'''
    q = __create_query(league_id)
    return q.get_league_teams()

def get_league_players(league_id:int) -> List[YPlayer]:
    '''Gets the list of players for the YLeague'''
    q = __create_query(league_id)
    players = []
    i = 0
    q_players = q.get_league_players(100,0)
    while len(q_players) == 100:
        i += 1
        players.extend(q_players)
        q_players = q.get_league_players(100, 100*i)
    players.extend(q_players)
    return players

def update_league_rosters(league:League) -> None:
    '''Populates the Yahoo league rosters'''
    q = __create_query(league.site_id)
    date = datetime.datetime.now()
    date_string = f'{date.year}-{"{:02d}".format(date.month)}-{"{:02d}".format(date.day)}'
    for team in league.teams:
        team.roster_spots.clear()
        yplayers = q.get_team_roster_player_info_by_date(team.site_id, date_string)
        for yplayer in yplayers:
            player = player_services.get_player_by_yahoo_id(yplayer.player_id)
            if player is None:
                player = player_services.get_player_by_name_and_team(f'{yplayer.name.ascii_first} {yplayer.name.ascii_last}', yplayer.editorial_team_abbr)
                if player is None:
                     continue
        rs = Roster_Spot
        rs.team = team
        rs.player = player
        # This looks like we should be able to get it from is_keeper somehow, but not sure how
        rs.salary = 0
        team.roster_spots.append(rs)

def get_league_settings(league_id:int) -> YSettings:
    q = __create_query(league_id)
    return q.get_league_settings()

def __create_query(league_id:int=1) -> yfs_query:
    return yfs_query(Path('conf'), league_id=league_id, game_code='mlb')

def init_oauth() -> Custom_OAuth2:
    private_json_path = "conf/private.json"
    # load credentials
    with open(private_json_path) as yahoo_app_credentials:
        auth_info = json.load(yahoo_app_credentials)

    token_file_path = 'conf/token.json'
    with open(token_file_path, "w") as yahoo_oauth_token:
                json.dump(auth_info, yahoo_oauth_token)
    return Custom_OAuth2(None, None, from_file=token_file_path)
    
def set_credentials(oauth:Custom_OAuth2, verifier:str):
      oauth.store_token(verifier)

def main():
    oauth = init_oauth()
    verifier = input("Adam, input the verifier: ")
    set_credentials(oauth, verifier=verifier)

if __name__ == '__main__':
    main()