from typing import List
import logging
import datetime

from dao.session import Session
from domain.domain import CustomScoring, CustomScoringCategory

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

def get_or_make_custom_scoring(custom_stats:List[CustomScoringCategory], name:str, description:str=None) -> CustomScoring:
    '''Gets the custom scoring set if one matches the list of CustomScoringCategory and makes and returns one if it does not
    already exist'''
    with Session() as session:
        css = session.query(CustomScoring).all()
        for cs_set in css:
            if len(cs_set.stats) != len(custom_stats):
                continue
            found = False
            for cs in cs_set.stats:
                for test_cs in custom_stats:
                    if test_cs.category == cs.category and test_cs.points == cs.points:
                        found = True
                        break
                if not found:
                    break
            if not found:
                return cs_set
        logging.info(f'Creating new CustomScoring {name}')
        if description is None:
            time = datetime.datetime.now()
            description = f'Automatically created on {time.year}/{time.month}/{time.day}'
        cs_set = CustomScoring(name=name, description=description)
        cs_set.stats.extend(custom_stats)
        session.add(cs_set)
        session.commit()
        return cs_set