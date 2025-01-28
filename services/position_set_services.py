from typing import List
from pandas import DataFrame

from dao.session import Session
from domain.domain import PositionSet, League, ValueCalculation, PlayerPositions
from domain.enum import IdType

from services import player_services


def get_all_position_sets() -> List[PositionSet]:
    """Returns all available PositionSets saved in the DB"""
    with Session() as session:
        formats = session.query(PositionSet).all()
    return formats


def delete_by_id(id: int) -> None:
    """Deletes a PositionSet from the database by id."""
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
    """Returns number of PositionSet formats in database."""
    with Session() as session:
        count = session.query(PositionSet).count()
    return count


def get_ottoneu_position_set() -> PositionSet:
    """Gets the default Ottoneu position set"""
    with Session() as session:
        return session.query(PositionSet).filter(PositionSet.name == 'Ottoneu').first()


def create_position_set_from_df(df: DataFrame, id_type: IdType, name: str, desc: str) -> PositionSet:
    """Creates a PositionSet from an input dataframe. Columns must include ID, NAME, TEAM, POS."""
    pos_set = PositionSet(name=name, detail=desc)
    for _, row in df.iterrows():
        id = row['ID']
        if id_type == IdType.OTTONEU:
            player = player_services.get_player_by_ottoneu_id(id)
        elif id_type == IdType.FANGRAPHS:
            player = player_services.get_player_by_fg_id(str(id))
        elif id_type == IdType.MLB:
            player = player_services.get_player_by_mlb_id(id)
        if not player:
            player = player_services.get_player_by_name_and_team(row['NAME'], row['TEAM'])
        if not player:
            continue
        pos_set.positions.append(PlayerPositions(player_id=player.id, position=row['POS']))
    with Session() as session:
        session.add(pos_set)
        session.commit()
        return session.query(PositionSet).filter(PositionSet.id == pos_set.id).first()


def write_position_set_to_csv(pos_set: PositionSet, filepath: str) -> None:
    """Writes the position set to a csv file at the given filepath"""
    rows = []
    with Session() as session:
        if pos_set.name == 'Ottoneu':
            players = player_services.get_rostered_players()
            for player in players:
                rows.append([player.get_fg_id(), player.name, player.team, player.position])
        else:
            for player_pos in pos_set.positions:
                player = player_services.get_player_with_session(player_id=player_pos.player_id, session=session)
                rows.append([player.get_fg_id(), player.name, player.team, player_pos.position])
    df = DataFrame(rows)
    df.columns = ['ID', 'NAME', 'TEAM', 'POS']
    if not filepath.endswith('.csv'):
        filepath += '.csv'
    df.to_csv(filepath, encoding='utf-8')
