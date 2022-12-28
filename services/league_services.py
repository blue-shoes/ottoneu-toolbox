from domain.domain import League, Team, Roster_Spot, Player
from domain.enum import ScoringFormat
from dao.session import Session
from scrape.scrape_ottoneu import Scrape_Ottoneu
from sqlalchemy.orm import joinedload

from datetime import datetime

def refresh_league(league_idx, pd=None):
    lg = get_league(league_idx, rosters=False)
    scraper = Scrape_Ottoneu()
    if pd is not None:
        pd.set_task_title("Checking last transaction date...")
        pd.increment_completion_percent(5)
    rec_tr = scraper.scrape_recent_trans_api(lg.ottoneu_id)
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
                team.roster_spots=[]
                team_map[team.site_id] = team
            for idx, row in upd_rost.iterrows():
                team = row['TeamID']
                if team not in team_map:
                    # team not present, possibly on the restricted list
                    continue
                rs = Roster_Spot()
                rs.player = session.query(Player).filter_by(ottoneu_id = idx).first()
                rs.salary = row['Salary'].split('$')[1]
                team_map[team].roster_spots.append(rs)
            
            lg.last_refresh = datetime.now()
            session.commit()
            lg = get_league(league_idx)
    else:
        lg = get_league(league_idx)
    if pd is not None:
        pd.set_completion_percent(100)
    return lg

def get_leagues(active):
    with Session() as session:
        if active:
            return session.query(League).filter(active).order_by(League.ottoneu_id)
        else:
            return session.query(League).order_by(League.ottoneu_id)

def get_league_ottoneu_id(league_idx):
    with Session() as session:
        return session.query(League).filter_by(index = league_idx).first().ottoneu_id

def get_league(league_idx, rosters=True) -> League:
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

def create_league(league_ottoneu_id, pd=None):
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

def save_league(lg, pd=None):
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
