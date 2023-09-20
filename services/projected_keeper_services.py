from typing import List
from sqlalchemy.orm import joinedload

from dao.session import Session
from domain.domain import Projected_Keeper, League, Player
from services import league_services
from util import date_util

def get_league_keepers(league:League):
    with Session() as session:
        keepers = session.query(Projected_Keeper) \
            .filter(Projected_Keeper.league_id == league.index) \
            .filter(Projected_Keeper.season == date_util.get_current_ottoneu_year()) \
            .all()
        if keepers == None:
            keepers = []
    league.projected_keepers = keepers

def add_keeper(league:League, player:Player) -> League:
    '''Creates a Projected Keeper for the given league based on player id, saves it to the database, and returns the fully loaded keeper.'''
    with Session() as session:
        _league = league_services.get_league_in_session(session, league.index, False)
        keeper = Projected_Keeper()
        keeper.league = _league
        keeper.player = player
        keeper.season = date_util.get_current_ottoneu_year()
        _league.projected_keepers.append(keeper)
        session.commit()
        keeper = session.query(Projected_Keeper).filter_by(id=keeper.id).first()
    return league_services.get_league(league.index)

def remove_keeper(keeper:Projected_Keeper) -> None:
    '''Deletes the given Projected_Keeper from the database'''
    with Session() as session:
        session.delete(keeper)
        session.commit()