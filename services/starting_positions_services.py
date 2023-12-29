from typing import List
import logging
import datetime

from dao.session import Session
from domain.domain import StartingPosition, StartingPositionSet

def get_or_make_starting_position_set(starting_positions:List[StartingPosition], name:str, description:str=None) -> StartingPositionSet:
    '''Gets the starting position set if one matches the list of StartingPositions and makes and returns one if it does not
    already exist'''
    with Session() as session:
        sps = session.query(StartingPositionSet).all()
        for sp_set in sps:
            found = False
            for sp in sp_set.positions:
                for test_sp in starting_positions:
                    if test_sp.position == sp.position and test_sp.count == sp.count:
                        found = True
                        break
                if not found:
                    break
            if found:
                return sp_set
        logging.info(f'Creating new StartingPositionSet {name}')
        if description is None:
            time = datetime.datetime.now()
            description = f'Automatically created on {time.year}/{time.month}/{time.day}'
        sp_set = StartingPositionSet(name=name, detail=description)
        sp_set.positions.extend(starting_positions)
        session.add(sp_set)
        return sp_set

def get_all_starting_sets() -> List[StartingPositionSet]:
    '''Returns all available StartingPositionSet formats saved in the DB'''
    with Session() as session:
        formats = session.query(StartingPositionSet).all()
    return formats

def delete_by_id(id:int) -> None:
    '''Deletes a StartingPositionSet format from the database by id.'''
    with Session() as session:
        cs = session.query(StartingPositionSet).filter(StartingPositionSet.id == id).first()
        session.delete(cs)
        session.commit()

def get_starting_set_count() -> int:
    '''Returns number of StartingPositionSet formats in database.'''
    with Session() as session:
        count = session.query(StartingPositionSet).count()
    return count

def get_starting_set(id:int) -> StartingPositionSet:
    '''Gets the StartingPositionSet object by id'''
    with Session() as session:
        sps = session.query(StartingPositionSet).filter_by(id = id).first()
    return sps

def save_starting_position_set(starting_set:StartingPositionSet) -> StartingPositionSet:
    '''Saves the StartingPositionSet object to the db'''
    with Session() as session:
        session.add(starting_set)
        session.commit()
        starting_set = get_starting_set(starting_set.id)
    return starting_set

def get_ottoneu_position_set() -> StartingPositionSet:
    '''Gets the default Ottoneu starting set'''
    with Session() as session:
        return session.query(StartingPositionSet).filter(StartingPositionSet.name == 'Ottoneu').first()