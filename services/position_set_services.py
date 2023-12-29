from typing import List

from dao.session import Session
from domain.domain import PositionSet, League, ValueCalculation

def get_all_position_sets() -> List[PositionSet]:
    '''Returns all available PositionSets saved in the DB'''
    with Session() as session:
        formats = session.query(PositionSet).all()
    return formats

def delete_by_id(id:int) -> None:
    '''Deletes a PositionSet from the database by id.'''
    with Session() as session:

        leagues = session.query(League).filter(League.position_set_id == id).all()
        for league in leagues:
            league.position_set_id = None
        
        vcs = session.query(ValueCalculation).filter(ValueCalculation.position_set_id == id).all()
        for vc in vcs:
            vc.position_set_id = None

        cs = session.query(PositionSet).filter(PositionSet.id == id).first()
        session.delete(cs)
        session.commit()

def get_position_set_count() -> int:
    '''Returns number of PositionSet formats in database.'''
    with Session() as session:
        count = session.query(PositionSet).count()
    return count

def get_ottoneu_position_set() -> PositionSet:
    '''Gets the default Ottoneu position set'''
    with Session() as session:
        return session.query(PositionSet).filter(PositionSet.name == 'Ottoneu').first()