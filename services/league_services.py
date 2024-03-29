from domain.domain import League, Team, Roster_Spot, Player, Draft
from domain.enum import ScoringFormat
from dao.session import Session
from scrape.scrape_ottoneu import Scrape_Ottoneu
from services import player_services
from sqlalchemy.orm import joinedload
from typing import List

from datetime import datetime

def refresh_league(league_idx:int, pd=None) -> League:
    '''Refreshes the given league id in the database. Checks if the most recent transaction is more recent than the last league refresh. If so, retrieves league rosters
    and updates Roster_Spots for the league.'''
    lg = get_league(league_idx, rosters=False)
    scraper = Scrape_Ottoneu()
    if pd is not None:
        pd.set_task_title("Checking last transaction date...")
        pd.increment_completion_percent(5)
    rec_tr = scraper.scrape_recent_trans_api(lg.ottoneu_id)
    if len(rec_tr) == 0:
        most_recent = datetime.now()
    else:
        most_recent = rec_tr.iloc[0]['Date']
    if most_recent > lg.last_refresh:
        if pd is not None:
            pd.set_task_title("Updating rosters...")
            pd.increment_completion_percent(5)
        upd_rost = scraper.scrape_roster_export(lg.ottoneu_id)
        if pd is not None:
            pd.increment_completion_percent(30)
        with Session() as session:
            lg = (session.query(League)
                    .options(
                        joinedload(League.teams)
                        .joinedload(Team.roster_spots)
                        .joinedload(Roster_Spot.player)
                    )
                    .filter_by(index = league_idx).first())
            team_map = {}
            for team in lg.teams:
                #Clear roster
                for rs in team.roster_spots:
                    session.delete(rs)
                team_map[team.site_id] = team
            for idx, row in upd_rost.iterrows():
                team = row['TeamID']
                if team not in team_map:
                    # team not present, possibly on the restricted list
                    continue
                rs = Roster_Spot()
                player = session.query(Player).filter_by(ottoneu_id = idx).first()
                if player is None:
                    player = player_services.get_player_from_ottoneu_player_page(idx, lg.ottoneu_id, session=session, pd=pd)
                rs.player = player
                rs.salary = row['Salary'].split('$')[1]
                team_map[team].roster_spots.append(rs)
                if team_map[team].name != row['Team Name']:
                    team_map[team].name = row['Team Name']
            
            lg.last_refresh = datetime.now()
            session.commit()
            lg = get_league(league_idx)
    else:
        lg = get_league(league_idx)
    if pd is not None:
        pd.set_completion_percent(100)
    return lg

def get_leagues(active: bool=True) -> List[League]:
    '''Returns Leagues from the database. If active is True, only Leagues marked as active are listed.'''
    with Session() as session:
        if active:
            return session.query(League).filter(active).order_by(League.ottoneu_id).all()
        else:
            return session.query(League).order_by(League.ottoneu_id).all()

def get_league_ottoneu_id(league_idx:int) -> int:
    '''Gets the Ottoneu id for the input league index'''
    with Session() as session:
        return session.query(League).filter_by(index = league_idx).first().ottoneu_id

def get_league(league_idx:int, rosters:bool=True) -> League:
    '''Retrieves the league from the database for the given index. If rosters is True, the league's teams and roster_spots are populated. Otherwise a shallow load is returned.'''
    with Session() as session:
        if rosters:
            league = (session.query(League)
                    .options(
                        joinedload(League.teams)
                        .joinedload(Team.roster_spots)
                        .joinedload(Roster_Spot.player)
                    )
                    .filter_by(index = league_idx).first())
        else:
            league = (session.query(League).filter_by(index = league_idx).first())
    return league

def create_league(league_ottoneu_id:int, pd=None) -> League:
    '''Creates a league in the Toolbox for a given Ottoneu league number. Scrapes the league info and league finances pages to get required information.'''
    if pd is not None:
        pd.set_task_title("Getting league info...")
        pd.increment_completion_percent(10)
    scraper = Scrape_Ottoneu()
    #rosters = scraper.scrape_roster_export(league_ottoneu_id)
    league_data = scraper.scrape_league_info_page(league_ottoneu_id)
    lg = League()
    lg.ottoneu_id = league_ottoneu_id
    lg.name = league_data['Name']
    lg.num_teams = league_data['Num Teams']
    lg.format = ScoringFormat.name_to_enum_map()[league_data['Format']]
    lg.last_refresh = datetime.min
    lg.active = True

    if pd is not None:
        pd.increment_completion_percent(15)

    fin = scraper.scrape_finances_page(league_ottoneu_id)
        
    for idx, row in fin.iterrows():
        team = Team()
        team.site_id = idx
        team.name = row['Name']
        lg.teams.append(team)

    if pd is not None:
        pd.increment_completion_percent(15)    

    return lg

def save_league(lg:League, pd=None) -> League:
    '''Updates the league in the database with new league name, team names, and rosters, saves it to the database, and returns the updated League.'''
    with Session() as session:
        old_lg = session.query(League).filter(League.index == lg.index).first()
        if old_lg is None:
            session.add(lg)
        else:
            old_lg.name = lg.name
            old_lg.active = lg.active
            for team in old_lg.teams:
                for n_team in lg.teams:
                    if n_team.index == team.index:
                        team.name = n_team.name
        session.commit()
        lg_idx = lg.index
    return refresh_league(lg_idx, pd)

def delete_league_by_id(lg_id: int) -> None:
    '''Deletes the league from the database by id.'''
    with Session() as session:
        league = session.query(League).filter(League.index == lg_id).first()
        session.delete(league)
        session.commit()

def league_exists(lg:League) -> bool:
    '''Checks if the given league exists in the database by index.'''
    with Session() as session:
        return session.query(League).filter(League.index == lg.index).first() is not None

def get_league_by_draft(draft:Draft, fill_rosters:bool=False) -> League:
    '''Returns the populated league by Draft'''
    with Session() as session:
        league = session.query(Draft).options(joinedload(Draft.league)).filter(Draft.index == draft.index).first().league
        return get_league(league.index, fill_rosters)
