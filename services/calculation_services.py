from datetime import datetime
from pandas import DataFrame
from sqlalchemy.orm import joinedload, load_only
from sqlalchemy.dialects import sqlite
from dao.session import Session
from domain.domain import PlayerValue, ValueCalculation, Projection, PlayerProjection, Player
from domain.enum import Position, CalculationDataType as CDT, StatType, ScoringFormat, RankingBasis
from value.point_values import PointValues
from services import player_services, projection_services
from util import string_util

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
    for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
        rl_dict[pos.value] = value_calc.get_input(CDT.pos_to_num_rostered().get(pos))
    return rl_dict

def get_rep_levels(value_calc):
    rl_dict = {}
    for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
        rl_dict[pos.value] = value_calc.get_input(CDT.pos_to_rep_level().get(pos))
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

def get_values_for_year(year=None):
    if year is None:
        year = projection_services.get_current_projection_year()
    with Session() as session:
        return session.query(ValueCalculation).join(ValueCalculation.projection).filter(Projection.season == year).all()

def get_points(player_proj, pos, sabr=False):
    try:
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
    except TypeError:
        return 0.0

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

def init_outputs_from_upload(vc: ValueCalculation, df : DataFrame, game_type, rep_level_cost=1, id_type='Ottoneu', pd=None):
    if pd is not None:
        pd.set_task_title("Determining replacement levels...")
        pd.increment_completion_percent(33)
    sorted = df.sort_values(by='Values', ascending=False)
    sample_players = {}
    pos_count = {}
    total_value = 0
    total_count = 0
    total_hit_count = 0
    hit_value = 0
    for index, row in sorted.iterrows():
        value = string_util.parse_dollar(row['Values'])
        if value < rep_level_cost:
            break
        total_value += value
        total_count += 1
        if id_type == 'Ottoneu':
            player = player_services.get_player_by_ottoneu_id(int(index))
        elif id_type == "FanGraphs":
            player = player_services.get_player_by_fg_id(index)
        else:
            raise Exception('Invalid id type entered')
        if player is None:
            #Player not in ottoverse, won't have a projection
            continue
        hit = False
        pitch = False
        positions = player_services.get_player_positions(player, discrete=True)
        if len(positions) == 1 and player.index in vc.projection.proj_dict:
            sample_list = sample_players.get(positions[0])
            if sample_list is None:
                sample_list = []
                sample_players[positions[0]] = sample_list
            sample_list.append((value, player.index))
        for pos in positions:
            if pos in Position.get_discrete_offensive_pos():
                hit = True
            if pos in Position.get_discrete_pitching_pos():
                pitch = True
            if pos in pos_count:
                pos_count[pos] = pos_count[pos] + 1
            else:
                pos_count[pos] = 1
        if hit and pitch:
            #Two way is hard...we'll split the value in half. It's close enough. It's just fro split anyways
            hit_value += value/2
            total_hit_count += 1
        elif hit:
            hit_value += value
            total_hit_count += 1
    
    vc.set_input(CDT.NON_PRODUCTIVE_DOLLARS, (400*vc.get_input(CDT.NUM_TEAMS) - (total_value + 40*vc.get_input(CDT.NUM_TEAMS)-total_count)))
    hit_surplus = hit_value - total_hit_count
    hit_split = int(hit_surplus/(total_value - total_count)*100)
    vc.set_input(CDT.HITTER_SPLIT, hit_split)
    for pos in pos_count:
        vc.set_output(CDT.pos_to_num_rostered().get(pos), pos_count[pos])
    hit_dol_per_fom = -999
    pitch_dol_per_fom = -999
    for pos in sample_players:
        sample_list = sample_players.get(pos)
        if len(sample_list) < 4:
            vc.set_output(CDT.pos_to_rep_level().get(pos), -999)
            continue
        prices = [sample_list[0][0], sample_list[-1][0], sample_list[1][0], sample_list[-2][0]]
        p_idx = [sample_list[0][1], sample_list[-1][1], sample_list[1][1], sample_list[-2][1]]
        pps = []
        for idx in p_idx:
            pps.append(vc.projection.get_player_projection(idx))
        if pos in Position.get_offensive_pos():
            rl, d = calc_rep_levels_from_values(prices, pps, pos, game_type, vc.hitter_basis)
            vc.set_output(CDT.pos_to_rep_level().get(pos), rl)
            if hit_dol_per_fom < 0:
                hit_dol_per_fom = d
        else:
            rl, d = calc_rep_levels_from_values(prices, pps, pos, game_type, vc.pitcher_basis)
            vc.set_output(CDT.pos_to_rep_level().get(pos), rl)
            if pitch_dol_per_fom < 0:
                pitch_dol_per_fom = d

    #Util rep level is either the highest offensive position level, or the Util value, whichever is lower
    max_lvl = 0
    for pos in Position.get_discrete_offensive_pos():
        if pos == Position.POS_UTIL:
            continue
        rl = vc.get_output(CDT.pos_to_rep_level().get(pos), 0)
        if rl > max_lvl:
            max_lvl = rl
    if max_lvl < vc.get_output(CDT.pos_to_rep_level().get(Position.POS_UTIL), 999):
        vc.set_output(CDT.pos_to_rep_level().get(Position.POS_UTIL), max_lvl)
    
    vc.set_output(CDT.HITTER_DOLLAR_PER_FOM, hit_dol_per_fom)
    vc.set_output(CDT.PITCHER_DOLLAR_PER_FOM, pitch_dol_per_fom)

def calc_rep_levels_from_values(vals, pps, pos, format, basis):
    if len(vals) < 4 or len(pps) < 4:
        raise Exception('calc_rep_levels_from_values requires input lists of at least four entries')
    sabr = (format == ScoringFormat.SABR_POINTS or format == ScoringFormat.H2H_SABR_POINTS)
    points = []
    pt = []
    for pp in pps:
        points.append(get_points(pp, pos, sabr))
        if basis == RankingBasis.PPG:
            if pos in Position.get_offensive_pos():
                pt.append(pp.get_stat(StatType.G_HIT))
            else:
                pt.append(pp.get_stat(StatType.G_PIT)) 
        elif basis == RankingBasis.PPPA:
            pt.append(pp.get_stat(StatType.PA))
        elif basis == RankingBasis.PIP:
            pt.append(pp.get_stat(StatType.IP))
        else:
            raise Exception(f'Unimplemented basis type {basis}')
    numer = (vals[0] - vals[1])*(points[2]-points[3])-(vals[2]-vals[3])*(points[0] - points[1])
    denom = (vals[0] - vals[1])*(pt[2] - pt[3]) - (vals[2] - vals[3])*(pt[0] - pt[1])
    rl = numer / denom
    d_per_fom = (vals[0] - vals[1])/((points[0] - rl)*pt[0]-(points[1] - rl)*pt[1])
    return rl, d_per_fom

def save_calculation_from_file(vc : ValueCalculation, df : DataFrame, pd=None):
    #TODO: Proper implementation of this
    return vc