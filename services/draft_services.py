from sqlalchemy.orm import joinedload
from pandas import DataFrame
from typing import List, Tuple

from dao.session import Session
from domain.domain import Draft, Draft_Target, CouchManagers_Draft, CouchManagers_Team
from scrape.scrape_couchmanagers import Scrape_CouchManagers
from services import player_services
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
            draft.league_id = lg_id
            draft.year = year
            draft.targets = []
            session.add(draft)
            session.commit()
            draft = session.query(Draft)\
                .filter_by(league_id = lg_id, year = year)\
                .first()
    return draft

def create_target(draft: Draft, playerid: int, price: int) -> Draft_Target:
    '''Creates a Draft target for the given draft based on player id and prices, saves it to the database, and returns the fully loaded target.'''
    with Session() as session:
        target = Draft_Target()
        target.draft_id = draft.index
        target.player_id = playerid
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

def delete_target(target:Draft_Target) -> None:
    '''Deletes the given Draft_Target from the database'''
    with Session() as session:
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
            players = player_services.search_by_name(name).sort(reverse=True, key=lambda p: p.get_salary_info_for_format().roster_percentage)
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
