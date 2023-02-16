from sqlalchemy.orm import joinedload
from pandas import DataFrame
from typing import List, Tuple

from dao.session import Session
from domain.domain import Draft, Draft_Target
from scrape.scrape_couchmanagers import Scrape_CouchManagers
from util import date_util

def get_draft_by_league(lg_id:int) -> Draft:
    '''Loads a Draft object from the database for the input league id. Draft is always from the current year.'''
    year = date_util.get_current_ottoneu_year()
    with Session() as session:
        draft = session.query(Draft)\
            .options(joinedload(Draft.targets))\
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
                .options(joinedload(Draft.targets))\
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
    '''Gets the dataframe from the CouchManagers draft with no further processing. DataFrame indexed by Ottoneu Player Id'''
    scraper = Scrape_CouchManagers()
    return scraper.get_draft_results(cm_draft_id)