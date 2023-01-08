from sqlalchemy.orm import joinedload

from dao.session import Session
from domain.domain import Draft, Draft_Target
from util import date_util

def get_draft_by_league(lg_id):
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
    return draft

def create_target(draft: Draft, playerid, price):
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

def update_target(target: Draft_Target, price):
    with Session() as session:
        target = session.query(Draft_Target).filter_by(index = target.index).first()
        target.price = price

def delete_target(target):
    with Session() as session:
        session.delete(target)
            
