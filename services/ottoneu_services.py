from typing import Tuple, List
from datetime import datetime
import logging
import os
import pandas as pd
from sqlalchemy.orm import joinedload

from dao.session import Session
from demo import draft_demo
from domain.domain import Player, League, ValueCalculation, Team, Roster_Spot
from domain.enum import InflationMethod, Position, ScoringFormat, Platform
from domain.interface import ProgressUpdater
from scrape.scrape_ottoneu import Scrape_Ottoneu
from services import league_services, player_services
from util import string_util


def create_league(league_ottoneu_id: int, prog:ProgressUpdater=None) -> League:
    """Creates a league in the Toolbox for a given Ottoneu league number. Scrapes the league info and league finances pages to get required information."""
    if prog is not None:
        prog.set_task_title('Getting league info...')
        prog.increment_completion_percent(10)
    scraper = Scrape_Ottoneu()
    # rosters = scraper.scrape_roster_export(league_ottoneu_id)
    league_data = scraper.scrape_league_info_page(league_ottoneu_id)
    lg = League()
    lg.site_id = league_ottoneu_id
    lg.name = league_data['Name']
    lg.num_teams = league_data['Num Teams']
    lg.s_format = ScoringFormat.get_format_by_full_name(league_data['Format'])
    lg.last_refresh = datetime.min
    lg.active = True
    lg.platform = Platform.OTTONEU
    lg.team_salary_cap = 400
    lg.roster_spots = 40

    if prog is not None:
        prog.increment_completion_percent(15)

    fin = scraper.scrape_finances_page(league_ottoneu_id)

    for idx, row in fin.iterrows():
        team = Team()
        team.site_id = idx
        team.name = row['Name']
        lg.teams.append(team)

    if prog is not None:
        prog.increment_completion_percent(15)

    return lg


def refresh_league(league_idx: int, prog:ProgressUpdater=None) -> League:
    """Refreshes the given league id in the database. Checks if the most recent transaction is more recent than the last league refresh. If so, retrieves league rosters
    and updates Roster_Spots for the league."""
    lg = league_services.get_league(league_idx, rosters=False)

    league_idx = lg.id
    scraper = Scrape_Ottoneu()
    if prog is not None:
        prog.set_task_title('Checking last transaction date...')
        prog.increment_completion_percent(5)
    rec_tr = scraper.scrape_recent_trans_api(lg.site_id)
    if len(rec_tr) == 0:
        most_recent = datetime.now()
    else:
        most_recent = rec_tr.iloc[0]['Date']
    if most_recent > lg.last_refresh:
        if prog is not None:
            prog.set_task_title('Updating rosters...')
            prog.increment_completion_percent(5)
        upd_rost = scraper.scrape_roster_export(lg.site_id)
        finances = scraper.scrape_finances_page(lg.site_id)
        
        if prog is not None:
            prog.increment_completion_percent(30)
        with Session() as session:
            lg = session.query(League).options(joinedload(League.teams).joinedload(Team.roster_spots).joinedload(Roster_Spot.player)).filter_by(id=league_idx).first()
            # Possible for start up league that hasn't drafted and either wasn't full or had a team drop and be recreated
            if len([t.id for t in lg.teams if t.site_id not in finances.index]) != 0:
                for t in lg.teams:
                    session.delete(t)
                for idx, row in finances.iterrows():
                    team = Team()
                    team.site_id = idx
                    team.name = row['Name']
                    lg.teams.append(team)
            
            team_map = {}
            for team in lg.teams:
                # Clear roster
                for rs in team.roster_spots:
                    session.delete(rs)
                team_map[team.site_id] = team
            for idx, row in upd_rost.iterrows():
                team = row['TeamID']
                if team == 0:
                    # Restricted list
                    continue
                rs = Roster_Spot()
                player = session.query(Player).filter_by(ottoneu_id=idx).first()
                if player is None:
                    player = player_services.get_player_from_ottoneu_player_page(idx, lg.site_id, session=session, prog=prog)
                rs.player = player
                rs.salary = row['Salary'].split('$')[1]
                team_map[team].roster_spots.append(rs)
                if team_map[team].name != row['Team Name']:
                    team_map[team].name = row['Team Name']
            for idx, row in finances.iterrows():
                team = team_map[idx]
                team.num_players = row['Players']
                team.spots = row['Spots']
                team.salaries = row['Base Salaries']
                team.penalties = row['Cap Penalties']
                team.loans_in = row['Loans In']
                team.loans_out = row['Loans Out']
                team.free_cap = row['Cap Space']

            lg.last_refresh = datetime.now()
            session.commit()
            lg = league_services.get_league(league_idx)
    else:
        lg = league_services.get_league(league_idx)
    if prog is not None:
        prog.set_completion_percent(100)
    return lg


def resolve_draft_results_against_rosters(
    league: League, value_calc: ValueCalculation, last_time: datetime, inf_method: InflationMethod, demo_source: bool = False
) -> Tuple[List[Player], List[Player], datetime]:
    """Retrieves the recent transactions from Ottoneu league and resolves the results against the known rosters. Returns list of newly rostered
    players, list of newly cut players, and the most recent transaction datetime."""
    if not demo_source:
        last_trans = Scrape_Ottoneu().scrape_recent_trans_api(league.site_id)
    else:
        logging.debug('demo_source')
        if not os.path.exists(draft_demo.demo_trans):
            return ([], [], last_time)
        last_trans = pd.read_csv(draft_demo.demo_trans)
        last_trans['Date'] = last_trans['Date'].apply(lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S.%f'))
    most_recent = last_trans.iloc[0]['Date']
    drafted = []
    cut = []
    if most_recent > last_time:
        index = len(last_trans) - 1
        while index >= 0:
            if last_trans.iloc[index]['Date'] > last_time:
                otto_id = last_trans.iloc[index]['Ottoneu ID']
                salary = string_util.parse_dollar(last_trans.iloc[index]['Salary'])
                team_id = last_trans.iloc[index]['Team ID']
                player = player_services.get_player_by_ottoneu_id(int(otto_id))
                if player is None:
                    logging.info(f'Otto id {otto_id} not in database')
                    if 'CUT' in last_trans.iloc[index]['Type'].upper():
                        league_services.update_league_inflation_last_trans(league, value=0, salary=salary, inf_method=inf_method, add_player=False)
                    index -= 1
                    continue

                if last_trans.iloc[index]['Type'].upper() == 'ADD':
                    drafted.append(player)
                    pv = value_calc.get_player_value(player.id, Position.OVERALL)
                    league_services.add_player_to_draft_rosters(league, team_id, player, pv, salary, inf_method)
                elif 'CUT' in last_trans.iloc[index]['Type'].upper():
                    cut.append(player)
                    for team in league.teams:
                        if team.league_id == team_id:
                            found = False
                            for rs in team.roster_spots:
                                if rs.player.id == player.id:
                                    found = True
                                    break
                            if found:
                                salary = rs.salary
                                pv = value_calc.get_player_value(player.id, Position.OVERALL)
                                if pv is None:
                                    val = 0
                                else:
                                    val = pv.value
                                league_services.update_league_inflation_last_trans(league, value=val, salary=salary, inf_method=inf_method, add_player=False)
                                team.roster_spots.remove(rs)
                            break
            index -= 1
        last_time = most_recent
    return (drafted, cut, last_time)
