from sqlalchemy.orm import joinedload

from dao.session import Session
from domain.domain import Draft, Draft_Target
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
            
