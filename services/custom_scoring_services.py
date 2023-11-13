from typing import List

from dao.session import Session
from domain.domain import CustomScoring

def get_scoring_format(id:int) -> CustomScoring:
    '''Gets the CustomScoring object by id'''
    with Session() as session:
        cs = session.query(CustomScoring).filter_by(id = id).first()
    return cs

def save_scoring_format(custom_format:CustomScoring) -> CustomScoring:
    '''Saves the CustomScoring object to the db'''
    with Session() as session:
        session.add(custom_format)
        session.commit()
        custom_format = get_scoring_format(custom_format.id)
    return custom_format

def get_all_formats() -> List[CustomScoring]:
    '''Returns all available CustomScoring formats saved in the DB'''
    with Session() as session:
        formats = session.query(CustomScoring).all()
    return formats

def delete_by_id(id:int) -> None:
    '''Deletes a CustomScoring format from the database by id.'''
    with Session() as session:
        cs = session.query(CustomScoring).filter(CustomScoring.id == id).first()
        session.delete(cs)
        session.commit()

def get_format_count() -> int:
    '''Returns number of CustomScoring formats in database.'''
    with Session() as session:
        count = session.query(CustomScoring).count()
    return count