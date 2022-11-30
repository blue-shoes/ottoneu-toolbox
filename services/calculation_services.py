from datetime import datetime
from pandas import DataFrame
from sqlalchemy.orm import joinedload, load_only
from sqlalchemy.dialects import sqlite
from dao.session import Session
from domain.domain import PlayerValue, ValueCalculation, Projection, PlayerProjection, Player
from domain.enum import Position, CalculationDataType, StatType
from value.point_values import PointValues
from services import player_services, projection_services

def perform_point_calculation(value_calc, pd = None):
    if pd is not None:
        pd.set_task_title("Initializing Value Calculation...")
        pd.increment_completion_percent(5)
    value_calculation = PointValues(value_calc=value_calc)
    value_calculation.calculate_values(rank_pos=True, progress=pd)
    if pd is not None:
        pd.set_task_title("Completed")
        pd.set_completion_percent(100)
        pd.destroy()

def get_num_rostered_rep_levels(value_calc):
    rl_dict = {}
    rl_dict[Position.POS_C.value] = value_calc.get_input(CalculationDataType.ROSTERED_C)
    rl_dict[Position.POS_1B.value] = value_calc.get_input(CalculationDataType.ROSTERED_1B)
    rl_dict[Position.POS_2B.value] = value_calc.get_input(CalculationDataType.ROSTERED_2B)
    rl_dict[Position.POS_SS.value] = value_calc.get_input(CalculationDataType.ROSTERED_SS)
    rl_dict[Position.POS_3B.value] = value_calc.get_input(CalculationDataType.ROSTERED_3B)
    rl_dict[Position.POS_OF.value] = value_calc.get_input(CalculationDataType.ROSTERED_OF)
    rl_dict[Position.POS_UTIL.value] = value_calc.get_input(CalculationDataType.ROSTERED_UTIL)
    rl_dict[Position.POS_SP.value] = value_calc.get_input(CalculationDataType.ROSTERED_SP)
    rl_dict[Position.POS_RP.value] = value_calc.get_input(CalculationDataType.ROSTERED_RP)
    return rl_dict

def get_rep_levels(value_calc):
    rl_dict = {}
    rl_dict[Position.POS_C.value] = value_calc.get_input(CalculationDataType.REP_LEVEL_C)
    rl_dict[Position.POS_1B.value] = value_calc.get_input(CalculationDataType.REP_LEVEL_1B)
    rl_dict[Position.POS_2B.value] = value_calc.get_input(CalculationDataType.REP_LEVEL_2B)
    rl_dict[Position.POS_SS.value] = value_calc.get_input(CalculationDataType.REP_LEVEL_SS)
    rl_dict[Position.POS_3B.value] = value_calc.get_input(CalculationDataType.REP_LEVEL_3B)
    rl_dict[Position.POS_OF.value] = value_calc.get_input(CalculationDataType.REP_LEVEL_OF)
    rl_dict[Position.POS_UTIL.value] = value_calc.get_input(CalculationDataType.REP_LEVEL_UTIL)
    rl_dict[Position.POS_SP.value] = value_calc.get_input(CalculationDataType.REP_LEVEL_SP)
    rl_dict[Position.POS_RP.value] = value_calc.get_input(CalculationDataType.REP_LEVEL_RP)
    return rl_dict

def save_calculation(value_calc):
    with Session() as session:
        session.add(value_calc)
        session.commit()
        saved = load_calculation(value_calc.index)
    return saved

def load_calculation(calc_index):
    with Session() as session:
        #query = (session.query(ValueCalculation)
        #        .filter_by(index = calc_index))
        #print(query)
        value_calc = (session.query(ValueCalculation)
                .filter_by(index = calc_index)
                #.options(joinedload(ValueCalculation.values))
                .first()
        )
        #This is hacky, but it loads these fields so much faster than trying to do the .options(joinedload()) operations. Makes no sense
        for pv in value_calc.values:
            break
        for pp in value_calc.projection.player_projections:
            break
    value_calc.init_value_dict()
    return value_calc

def get_points(player_proj, pos, sabr=False):
    if pos in Position.get_offensive_pos():
        return -1.0*player_proj.get_stat(StatType.AB) + 5.6*player_proj.get_stat(StatType.H) + 2.9*player_proj.get_stat(StatType.DOUBLE) \
            + 5.7*player_proj.get_stat(StatType.TRIPLE) + 9.4*player_proj.get_stat(StatType.HR) +3.0*player_proj.get_stat(StatType.BB) \
            + 3.0*player_proj.get_stat(StatType.HBP) + 1.9*player_proj.get_stat(StatType.SB) - 2.8*player_proj.get_stat(StatType.CS)
    if pos in Position.get_pitching_pos():
        if sabr:
            return 5.0*player_proj.get_stat(StatType.IP) + 2.0*player_proj.get_stat(StatType.SO) - 3.0*player_proj.get_stat(StatType.BB_ALLOWED) \
                - 3.0*player_proj.get_stat(StatType.HBP_ALLOWED) - 13.0*player_proj.get_stat(StatType.HR_ALLOWED) \
                + 5.0*player_proj.get_stat(StatType.SV) + 4.0*player_proj.get_stat(StatType.HLD)
        else:
            return 7.4*player_proj.get_stat(StatType.IP) + 2.0*player_proj.get_stat(StatType.SO) - 2.6*player_proj.get_stat(StatType.H_ALLOWED) \
                - 3.0*player_proj.get_stat(StatType.BB_ALLOWED) - 3.0*player_proj.get_stat(StatType.HBP_ALLOWED) - 12.3*player_proj.get_stat(StatType.HR_ALLOWED) \
                + 5.0*player_proj.get_stat(StatType.SV) + 4.0*player_proj.get_stat(StatType.HLD)

def get_dataframe_with_values(value_calc : ValueCalculation, pos, text_values=True):
    assert isinstance(value_calc, ValueCalculation)
    if pos == Position.OVERALL:
        rows = []
        for pv in value_calc.get_position_values(pos):
            if pv.player is None:
                pv.player = value_calc.projection.get_player_projection(pv.player_id).player
            row = []
            row.append(pv.player.ottoneu_id)
            row.append(pv.player.name)
            row.append(pv.player.team)
            row.append(pv.player.position)
            if text_values:
                row.append("${:.1f}".format(pv.value))
            else:
                row.append(pv.value)
            rows.append(row)
        df = DataFrame(rows)
        header = ['otto', 'Name', 'Team', 'Pos', '$']
        df.columns = header
        df.set_index('otto', inplace=True)
        return df
    else:
        proj_dfs = projection_services.convert_to_df(value_calc.projection)
        if pos in Position.get_offensive_pos():
            proj = proj_dfs[0]
        else:
            proj = proj_dfs[1]
        rows = []
        for pv in value_calc.get_position_values(pos):
            player = player_services.get_player(pv.player_id)
            row = []
            row.append(player.ottoneu_id)
            row.append(pv.value)
            df_row = proj.loc[pv.player_id]
            for col in proj.columns:
                if col == 'ID':
                    continue
                row.append(df_row[col])
            rows.append(row)
        df = DataFrame(rows)
        header = ['Ottoneu Id', 'Value']
        for col in proj.columns:
            if col == 'ID':
                continue
            header.append(col)
        df.columns = header
        df.set_index('Ottoneu Id', inplace=True)
        return df