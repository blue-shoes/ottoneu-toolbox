from dao.session import Session
from domain.enum import Position, CalculationDataType
from value.point_values import PointValues
from services import player_services

def perform_point_calculation(value_calc, pd = None):
    if pd is not None:
        pd.set_task_title("Initializing Value Calculation...")
        pd.increment_completion_percent(5)
    value_calculation = PointValues(value_calc=value_calc)
    value_calculation.calculate_values(rank_pos=True, pd = pd)
    if pd is not None:
        pd.set_task_title("Completed")
        pd.set_completion_percent(100)

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
        seen_players = {}
        for pv in value_calc.values:
            if pv.player_id in seen_players:
                player = seen_players[pv.player_id]
            else:
                player = player_services.get_player(pv.player_id)
            pv.player = player
        session.add(value_calc)
    