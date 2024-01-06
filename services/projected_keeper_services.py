from typing import List
from sqlalchemy.orm import joinedload

from dao.session import Session
from domain.domain import Projected_Keeper, League, Player
from services import league_services, player_services
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
        keeper = Projected_Keeper()
        keeper.league_id = league.index
        keeper.player = player
        keeper.season = date_util.get_current_ottoneu_year()
        session.add(keeper)
        session.commit()
        keeper = session.query(Projected_Keeper).filter_by(id=keeper.id).first()
    return league_services.get_league(league.index)

def remove_keeper_by_league_and_player(league:League, player:Player) -> Projected_Keeper:
    '''Deletes the keeper from the database based on the league and player'''
    with Session() as session:
        _keeper = session.query(Projected_Keeper).filter_by(league_id=league.id).filter_by(player_id=player.index).first()
        session.delete(_keeper)
        session.commit()
    return _keeper

def remove_keeper(keeper:Projected_Keeper) -> None:
    '''Deletes the given Projected_Keeper from the database'''
    with Session() as session:
        _keeper = session.query(Projected_Keeper).filter_by(id=keeper.id).first()
        session.delete(_keeper)
        session.commit()

def clear_keepers_for_league(league:League) -> None:
    with Session() as session:
        keepers = session.query(Projected_Keeper).filter_by(league_id=league.index).all()
        for keeper in keepers:
            session.delete(keeper)
        session.commit()

def add_keeper_and_return(league:League, player:Player) -> Projected_Keeper:
    with Session() as session:
        keeper = Projected_Keeper()
        keeper.league_id = league.index
        keeper.player = player
        keeper.season = date_util.get_current_ottoneu_year()
        session.add(keeper)
        session.commit()
        keeper = session.query(Projected_Keeper).filter_by(id=keeper.id).first()
    return keeper

def add_keeper_by_player_id(league:League, player_id:int) -> Projected_Keeper:
    with Session() as session:
        keeper = Projected_Keeper()
        keeper.league_id = league.index
        keeper.player = player_services.get_player(player_id)
        keeper.season = date_util.get_current_ottoneu_year()
        session.add(keeper)
        session.commit()
        keeper = session.query(Projected_Keeper).filter_by(id=keeper.id).first()
    return keeper