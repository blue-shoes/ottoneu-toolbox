from sqlalchemy.orm import joinedload

from dao.session import Session
from domain.domain import Draft, Draft_Target
from util import date_util

def get_draft(lg_id):
    year = date_util.get_current_ottoneu_year()
    with Session() as session:
        draft = session.query(Draft).joinedload(Draft.targets).filter_by(league_id = lg_id, year = year).first()
        if draft is None:
            draft = Draft()
            draft.league_id = lg_id
            draft.year = year
            draft.targets = []
            session.add(draft)
            session.commit()
    return draft

def save_draft(draft: Draft):
    with Session() as session:
        old_draft = session.query(Draft).joinedload(Draft.targets).filter_by(index = draft.index).first()
        seen_target_ids = []
        for target in draft.targets:
            if target.index is None:
                new_target = Draft_Target()
                new_target.player_id = target.player_id
                new_target.price = target.price
                old_draft.targets.append(new_target)
                continue
            for old_target in old_draft.targets:
                if target.index == old_target.index:
                    old_target.price = target.price
                    updated = True
                    seen_target_ids.append(target.index)
                    break
        to_remove = []
        for old_target in old_draft.targets:
            if old_target.index not in seen_target_ids:
                to_remove.append(old_target)
        for remove_target in to_remove:
            old_draft.targets.remove(remove_target)
        session.commit()
            
