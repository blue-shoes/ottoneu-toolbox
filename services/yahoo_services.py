from yfpy.query import YahooFantasySportsQuery as yfs_query
from yfpy import Team as YTeam, League as YLeague, Settings as YSettings, Player as YPlayer, YahooFantasySportsException, DraftResult as YDR
from pathlib import Path

from dao.session import Session
from domain.domain import League, Roster_Spot, Player, ValueCalculation, Team, PositionSet, PlayerPositions
from domain.enum import InflationMethod, Position, ScoringFormat, Platform
from services import player_services, league_services

import json
from typing import List, Tuple
import datetime
import threading
from time import sleep

game_id:str = ''

def create_league(league_yahoo_id:int, pd=None) -> League:
    '''Creates a league in the Toolbox for a given Yahoo league number.'''

    if pd is not None:
        pd.set_task_title("Getting league info...")
        pd.increment_completion_percent(10)

    yleague = get_league_metadata(league_yahoo_id)
    pd.increment_completion_percent(30)
    teams = get_teams(league_yahoo_id)
    pd.increment_completion_percent(30)
    settings = get_league_settings(league_yahoo_id)

    lg = League()
    lg.site_id = league_yahoo_id
    lg.name = yleague.name.decode("utf-8")
    lg.num_teams = yleague.num_teams
    lg.format = ScoringFormat.CUSTOM
    lg.last_refresh = datetime.datetime.min
    lg.active = True
    lg.platform = Platform.YAHOO
    if settings.is_auction_draft or settings.uses_faab:
        lg.team_salary_cap = 0
    else:
        lg.team_salary_cap = -1

    for yteam in teams:
        team = Team()
        team.site_id = yteam.team_id
        team.name = yteam.name.decode("utf-8")
        lg.teams.append(team)
    
    return lg

def refresh_league(league_idx:int, pd=None) -> League:
    #TODO: Implement this
    lg = league_services.get_league(league_idx, rosters=False)
    return lg

def get_league_metadata(league_id:int) -> YLeague:
    '''Gets the league metadata as a yfpy.League object'''
    q = __create_query(league_id)
    return q.get_league_metadata()

def get_teams(league_id:int) -> List[YTeam]:
    '''Gets the list of league teams as a list of yfpy.Team objects'''
    q = __create_query(league_id)
    return q.get_league_teams()

def get_league_players(league_id:int, player_list:List=[]) -> List[YPlayer]:
    '''Gets the list of players for the YLeague'''
    q = __create_query(league_id)
    player_list.extend(q.get_league_players())
    return player_list

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
    '''Returns the Yahoo Settings object for the given league id'''
    q = __create_query(league_id)
    return q.get_league_settings()

def get_draft_results(league_id:int) -> List[YDR]:
    '''Gets the draft results from the Yahoo league for the given id.'''
    q = __create_query(league_id)
    return q.get_league_draft_results()

def resolve_draft_results_against_rosters(league:League, value_calc:ValueCalculation, inf_method:InflationMethod) -> Tuple[List[Player], List[Player]]:
    '''Gets the latest draft information and updates rosters to reflect newly rostered or cut players.'''
    draft_results = get_draft_results(league.site_id)
    new_drafted = []
    cut = []
    for dr in draft_results:
        pick = (dr.round, dr.pick)
        if pick in league.draft_results:
            continue
        player = player_services.get_player_by_yahoo_id(int(dr.player_key.split('.')[-1]))
        if player is None:
            if league.is_salary_cap():
                league_services.update_league_inflation_last_trans(league, value=0, salary=dr.cost, inf_method=inf_method)
            continue
        new_drafted.append(player)
        team_id = int(dr.team_key.split('.')[-1])
        pv = value_calc.get_player_value(player.index, Position.OVERALL)
        league_services.add_player_to_draft_rosters(league, team_id, player, pv, dr.cost, inf_method)
    pick_list = [(dr.round, dr.pick) for dr in draft_results]
    for pick, player_id in league.draft_results.items():
        if pick not in pick_list:
            player = player_services.get_player(player_id)
            cut.append(player)
            for team in league.teams:
                if team.league_id == team_id:
                    found = False
                    for rs in team.roster_spots:
                        if rs.player.index == player.index:
                            found = True
                            break
                    if found:
                        team.roster_spots.remove(rs)
                        if league.is_salary_cap():
                            salary = rs.salary
                            pv = value_calc.get_player_value(player_id, Position.OVERALL)
                            if pv is None:
                                val = 0
                            else:
                                val = pv.value
                            league_services.update_league_inflation_last_trans(league, value=val, salary=salary, inf_method=inf_method, add_player=False)
                    break
    return (new_drafted, cut)

def set_player_positions_for_league(league:League, pd = None) -> League:
    '''Gets Yahoo league player position eligibilities and creates a new PositionSet, if necessary. Also populates player.yahoo_id if necessary.'''
    ic()
    if not league.position_set:
        timestamp = datetime.datetime.now()
        position_set = PositionSet(name=f'{timestamp.year}-{league.name}')
        date = f'{timestamp.month}/{timestamp.day}/{timestamp.year}'
        position_set.detail = f'Automatic Creation for Yahoo league {league.site_id} on {date}'
        league.position_set = position_set
    else:
        position_set = league.position_set
    if pd:
        pd.set_task_title('Creating player position set (This will take some time)...')
        pd.increment_completion_percent(10)
    yplayers = []
    thread = threading.Thread(target = get_league_players, args=(league.site_id, yplayers))
    thread.start()

    start = datetime.datetime.now()
    while (thread.is_alive()):
        pd.increment_completion_percent(1)
        sleep(10)
    ic((datetime.datetime.now() - start))
    #yplayers = get_league_players(league.site_id)
    ic(len(yplayers))
    start = datetime.datetime.now()
    seen_ids = []
    with Session() as session:
        for yplayer in yplayers:
            player = get_or_set_player_by_yahoo_id(yplayer, session)
            if player is None:
                continue
            if player.index in seen_ids:
                for pp in position_set.positions:
                    if pp.player_id == player.index:
                        pp.position += f'/{yplayer.display_position.replace(",","/")}'
                        break
            else:
                player_position = PlayerPositions()
                player_position.player_id = player.index
                player_position.position = yplayer.display_position.replace(',','/')
                #ic(yplayer, player_position)
                position_set.positions.append(player_position)
                seen_ids.append(player.index)
    ic((datetime.datetime.now() - start))
    return league_services.save_league(league)

def get_or_set_player_by_yahoo_id(yplayer:YPlayer, session) -> Player:
    '''Gets a player by Yahoo id. If no record of Yahoo id exists, looks up player by name and team and sets that player's Yahoo id before
    returning.'''
    player = player_services.get_player_by_yahoo_id_with_session(yplayer.player_id, session)
    if player is None:
        player = player_services.get_player_by_name_and_team_with_no_yahoo_id(f'{yplayer.name.first} {yplayer.name.last}', yplayer.editorial_team_abbr, session)
        if player is None:
            return None
        player = player_services.set_player_yahoo_id_with_session(player.index, yplayer.player_id, session)
    return player

def __create_query(league_id:int=1, year:int=None) -> yfs_query:
    '''Creates a yfs_query object for the given league and year in mlb. If no year provided, the current
    calendar year is found.'''
    global game_id
    if year is not None:
        q = yfs_query(Path('conf'), league_id=league_id, game_code='mlb')
        game_keys = q.get_all_yahoo_fantasy_game_keys()
        for gk in game_keys:
            if gk.code == 'mlb' and int(gk.season) == year:
                return yfs_query(Path('conf'), league_id=league_id, game_code='mlb', game_id=gk.game_id)
        raise YahooFantasySportsException(f'Could not find game_key for year {year}')
    elif game_id == '':
        q = yfs_query(Path('conf'), league_id=league_id, game_code='mlb')
        game_keys = q.get_all_yahoo_fantasy_game_keys()
        for gk in game_keys:
            if gk.code == 'mlb' and int(gk.season) == datetime.datetime.now().year:
                game_id = gk.game_id
        if game_id == '':
             raise YahooFantasySportsException(f'Could not find game_key for current year')
    return yfs_query(Path('conf'), league_id=league_id, game_code='mlb', game_id=game_id)