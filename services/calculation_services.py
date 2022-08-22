from dao.session import Session
from domain.enum import Position, CalculationDataType, StatType
from value.point_values import PointValues
from services import player_services

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
        seen_players = {}
        for pv in value_calc.values:
            if pv.player_id in seen_players:
                player = seen_players[pv.player_id]
            else:
                player = player_services.get_player(pv.player_id)
            pv.player = player
        session.add(value_calc)

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