from sqlalchemy.orm import joinedload
from pandas import DataFrame
from typing import List, Tuple

from dao.session import Session
from domain.domain import Draft, Draft_Target, CouchManagers_Draft, CouchManagers_Team, League, TeamDraft, Player
from scrape.scrape_couchmanagers import Scrape_CouchManagers
from services import player_services, browser_services
from util import date_util

def get_draft_by_league(lg_id:int) -> Draft:
    '''Loads a Draft object from the database for the input league id. Draft is always from the current year.'''
    year = date_util.get_current_ottoneu_year()
    with Session() as session:
        draft = session.query(Draft)\
            .filter_by(league_id = lg_id, year = year)\
            .first()
        if draft is None:
            draft = Draft()
            draft.league = session.query(League).filter_by(index = lg_id).first()
            draft.year = year
            draft.targets = []
            session.add(draft)
            session.commit()
            draft = session.query(Draft)\
                .filter_by(league_id = lg_id, year = year)\
                .first()
    return draft

def create_target(draft_id:int, playerid: int, price: int) -> Draft_Target:
    '''Creates a Draft target for the given draft based on player id and prices, saves it to the database, and returns the fully loaded target.'''
    with Session() as session:
        target = Draft_Target()
        target.draft_id = draft_id
        target.player = player_services.get_player(playerid)
        target.price = price
        session.add(target)
        session.commit()
        target = session.query(Draft_Target).filter_by(index=target.index)\
            .options(joinedload(Draft_Target.player)).first()
    return target

def update_target(target: Draft_Target, price: int) -> None:
    '''Updates the price of the specified Draft_Target'''
    with Session() as session:
        target = session.query(Draft_Target).filter_by(index = target.index).first()
        target.price = price
        session.commit()

def delete_target(target_id:int) -> None:
    '''Deletes the given Draft_Target by id from the database'''
    with Session() as session:
        target = session.query(Draft_Target).filter_by(index = target_id).first()
        session.delete(target)
        session.commit()
            
def get_couchmanagers_teams(cm_draft_id:str) -> List[Tuple[int, str]]:
    '''Gets a list of tuples containing CouchManagers draft team id and team name'''
    scraper = Scrape_CouchManagers()
    return scraper.get_draft_info(cm_draft_id)

def get_couchmanagers_draft_dataframe(cm_draft_id:int) -> DataFrame:
    '''Gets the dataframe from the CouchManagers draft with no further processing. DataFrame autoindexed with column
    "ottid" as the Ottoneu Player Id. "ottid" of 0 is attempted to be resolved by doing a name lookup in the database and
    taking the highest rostered player that matches.'''
    scraper = Scrape_CouchManagers()
    df = scraper.get_draft_results(cm_draft_id, reindex=False)
    for idx, row in df.iterrows():
        if row['ottid'] == 0:
            name = f"{row['First Name']} {row['Last Name']}".upper()
            players = player_services.search_by_name(name)
            players.sort(reverse=True, key=lambda p: p.get_salary_info_for_format().roster_percentage)
            if players is not None and len(players) > 0:
                row['ottid'] = players[0].ottoneu_id
    return df         

def add_couchmanagers_draft(draft:Draft, cm_draft:CouchManagers_Draft) -> Draft:
    '''Saves the CouchManagers_Draft to the input draft'''
    with Session() as session:
        old_draft = session.query(Draft).filter_by(index = draft.index).first()
        old_draft.cm_draft = cm_draft
        session.commit()
        return session.query(Draft).filter_by(index = draft.index).first()

def update_couchmanger_teams(draft_index:int, new_teams:List[CouchManagers_Team], set_up:bool) -> CouchManagers_Draft:
    '''Updates the team mappings from CouchManagers to Ottoneu Toolbox'''
    with Session() as session:
        db_cm_draft = session.query(CouchManagers_Draft).filter_by(index = draft_index).first()
        db_cm_draft.setup = set_up
        for cm_team in new_teams:
            db_cm_draft.teams.append(cm_team)
        session.commit()
        return session.query(CouchManagers_Draft).filter_by(index = draft_index).first()

def delete_couchmanagers_draft(cm_draft:CouchManagers_Draft) -> None:
    '''Deletes the input CouchManagers_Draft'''
    with Session() as session:
        session.delete(cm_draft)
        session.commit()

def update_team_drafts(draft_id:int, team_drafts:List[TeamDraft]) -> Draft:
    '''Updates the draft\'s list of TeamDraft objects'''
    with Session() as session:
        db_draft = session.query(Draft).filter_by(index = draft_id).first()
        if db_draft.team_drafts:
            for new_td in team_drafts:
                found = False
                for old_td in db_draft.team_drafts:
                    if old_td.team_id == new_td.team_id:
                        old_td.custom_draft_budget = new_td.custom_draft_budget
                        found = True
                        break
                if not found:
                    db_draft.append(new_td)
        else:
            db_draft.team_drafts.extend(team_drafts)
        session.commit()
        return session.query(Draft).filter_by(index = draft_id).first()

def get_couchmanagers_current_auctions(cm_draft_id:int) -> List[Tuple[Player,int]]:
    '''Returns a list of the current Couch Managers auctions as a list of Player to current bid.'''
    scraper = Scrape_CouchManagers(browser_services.get_desired_browser())
    current_auctions = scraper.get_current_auctions(cm_draft_id)
    if not current_auctions:
        return []
    auctions = []
    for ca in current_auctions:
        player = player_services.get_player_by_name_and_team(ca[0], ca[1])
        if player:
            auctions.append((player, ca[2]))
    return auctions