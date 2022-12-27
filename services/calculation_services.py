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
import math

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

def normalize_value_upload(df : DataFrame):
    id_col = None
    value_col = None
    hit_rate_col = None
    pitch_rate_col = None
    points_col = None
    hit_pt_col = None
    pitch_pt_col = None
    col_map = {}
    for col in df.columns:
        if 'ID' in col.upper():
            id_col = col
        if 'VAL' in col.upper() or 'PRICE' in col.upper() or '$' in col:
            value_col = col
            col_map[value_col] = "Values"
        if 'PTSPG' in col.upper() or 'P/G' in col.upper() or 'PTSPPA' in col.upper() or 'P/PA' in col.upper():
            hit_rate_col = col
            col_map[hit_rate_col] = 'Hit_Rate'
        elif 'PTSPG' in col.upper() or 'P/G' in col.upper() or 'PTSPIP' in col.upper() or 'P/IP' in col.upper():
            pitch_rate_col = col
            col_map[pitch_rate_col] = 'Pitch_Rate'
        elif 'PTS' in col.upper() or 'POINTS' in col.upper():
            points_col = col
            col_map[points_col] = 'Points'
        if 'G' == col.upper() or 'GAME' in col.upper() or 'PA' == col.upper():
            hit_pt_col = col
            col_map[hit_pt_col] = 'H_PT'
        if 'IP' == col.upper() or 'GS' == col.upper():
            pitch_pt_col = col
            col_map[pitch_pt_col] = 'P_PT'
    
    validate_msg = ''
    if id_col is None:
        validate_msg += 'No column with header containing \"ID\"\n'
    else:
        df.set_index(id_col, inplace=True)
    if value_col is None:
        validate_msg += 'Value column must be labeled \"Value\", \"Price\", or \"$\"\n'

    df.rename(columns=col_map, inplace=True)
    if hit_rate_col is not None:
        df['Hit_Rate'] = df['Hit_Rate'].apply(convert_vals)
    if pitch_rate_col is not None:
        df['Pitch_Rate'] = df['Pitch_Rate'].apply(convert_vals)
    if hit_pt_col is not None:
        df['H_PT'] = df['H_PT'].apply(convert_vals)
    if pitch_pt_col is not None:
        df['P_PT'] = df['P_PT'].apply(convert_vals)

    if not None in [hit_rate_col, points_col] or not None in [points_col, hit_pt_col]:
        fill_df_hit_columns(df)

    if not None in [pitch_rate_col, points_col] or not None in [points_col, pitch_pt_col]:
        fill_df_pitch_columns(df)
    
    if 'Points' not in df and not None in [hit_rate_col, hit_pt_col] and not None in [pitch_rate_col, pitch_pt_col]:
        df['Points'] = df.apply(calc_points, axis=0)

    return validate_msg

def fill_df_hit_columns(df:DataFrame):
    if 'Hit_Rate' not in df.columns:
        df['Hit_Rate'] = df.apply(calc_hit_rate, axis=1)
    elif 'H_PT' not in df.columns:
        df['H_PT'] = df.apply(calc_hit_pt, axis=1)

def calc_points(row):
    return row['H_PT'] * row['Hit_Rate'] + row['P_PT'] * row['Pitch_Rate']

def calc_hit_rate(row):
    pt = row['H_PT']
    if pt == 0:
        return 0
    return row['Points']/pt

def calc_hit_pt(row):
    rate = row['Hit_Rate']
    if rate == 0:
        return 0
    return row['Points'] / rate

def fill_df_pitch_columns(df:DataFrame):
    if 'Pitch_Rate' not in df.columns:
        df['Pitch_Rate'] = df.apply(calc_pitch_rate, axis=1)
    elif 'P_PT' not in df.columns:
        df['P_PT'] = df.apply(calc_pitch_pt, axis=1)

def calc_pitch_rate(row):
    pt = row['P_PT']
    if pt == 0:
        return 0
    return row['Points']/pt

def calc_pitch_pt(row):
    rate = row['Pitch_Rate']
    if rate == 0:
        return 0
    return row['Points'] / rate

def convert_vals(value):
    if value == 'NA' or value == '--' or math.isnan(value):
        return float(0)
    elif type(value) == float:
        return value
    else:
        return float(value)

def has_required_data_for_rl(df:DataFrame, game_type:ScoringFormat):
    if ScoringFormat.is_points_type(game_type):
        return set(['Points','H_PT','P_PT']).issubset(df.columns)
    else:
        raise Exception(f'ScoringFormat {game_type} not currently implemented')

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
    proj_derive = not has_required_data_for_rl(df, game_type)
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
            #Player not in Ottoneu ToolBox Database, won't have a projection
            continue
        df['OTB_Idx'] = player.index
        hit = False
        pitch = False
        positions = player_services.get_player_positions(player, discrete=True)
        if len(positions) == 1 and player.index in vc.projection.proj_dict:
            pos = positions[0]
            pitch_role_good = True
            if pos in Position.get_pitching_pos():
                #This mitigates potential issues where a pitcher's Ottoneu position doens't reflect their projection
                #and protects against swingman roles being used to determine replacement level
                pp = vc.projection.get_player_projection(player.index)
                if pos == Position.POS_SP:
                    if pp.get_stat(StatType.G_PIT) > pp.get_stat(StatType.GS_PIT):
                        pitch_role_good = False
                else:
                    if pp.get_stat(StatType.GS_PIT) > 0:
                        pitch_role_good = False
            if pitch_role_good:
                sample_list = sample_players.get(positions[0])
                if sample_list is None:
                    sample_list = []
                    sample_players[positions[0]] = sample_list
                if proj_derive:
                    sample_list.append((value, player.index))
                else:
                    sample_list.append((value, row['Points'], row['H_PT'], row['P_PT']))
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
        if proj_derive:
            p_idx = [sample_list[0][1], sample_list[-1][1], sample_list[1][1], sample_list[-2][1]]
            points = []
            pt = []
            for idx in p_idx:
                pp = vc.projection.get_player_projection(idx)
                points.append(get_points(pp, pos, game_type in [ScoringFormat.SABR_POINTS, ScoringFormat.H2H_SABR_POINTS]))
                if pos in Position.get_discrete_offensive_pos():
                    if vc.hitter_basis == RankingBasis.PPG:
                        pt.append(pp.get_stat(StatType.G_HIT))
                    elif vc.hitter_basis == RankingBasis.PPPA:
                        pt.append(pp.get_stat(StatType.PA))
                    else:
                        raise Exception(f'Hitter basis {vc.hitter_basis.value} not implemented')
                else:
                    if vc.pitcher_basis == RankingBasis.PPG:
                        pt.append(pp.get_stat(StatType.G_PIT))
                    elif vc.hitter_basis == RankingBasis.PIP:
                        pt.append(pp.get_stat(StatType.IP))
                    else:
                        raise Exception(f'Pitcher basis {vc.pitcher_basis.value} not implemented')
        else:
            points = [sample_list[0][1], sample_list[-1][1], sample_list[1][1], sample_list[-2][1]]
            if pos in Position.get_offensive_pos():
                pt = [sample_list[0][2], sample_list[-1][2], sample_list[1][2], sample_list[-2][2]]
            else:
                pt = [sample_list[0][3], sample_list[-1][3], sample_list[1][3], sample_list[-2][3]]
        
        rl, d = calc_rep_levels_from_values(prices, points, pt)
        vc.set_output(CDT.pos_to_rep_level().get(pos), rl)

        if pos in Position.get_offensive_pos() and hit_dol_per_fom < 0:
            hit_dol_per_fom = d
        elif pos in Position.get_pitching_pos() and pitch_dol_per_fom < 0:
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

def calc_rep_levels_from_values(vals, points, pt):
    #Calcs done algebraicly from equation (Value1 - Value2) = Dol/FOM * [(Points1 - rl * Games1) - (Points2 - rl * Games2)]
    if len(vals) < 4 or len(points) < 4 or len(pt) < 4:
        raise Exception('calc_rep_levels_from_values requires input lists of at least four entries')
    numer = (vals[0] - vals[1])*(points[2]-points[3])-(vals[2]-vals[3])*(points[0] - points[1])
    denom = (vals[0] - vals[1])*(pt[2] - pt[3]) - (vals[2] - vals[3])*(pt[0] - pt[1])
    rl = numer / denom
    d_per_fom = (vals[0] - vals[1])/((points[0] - rl*pt[0])-(points[1] - rl*pt[1]))
    return rl, d_per_fom

def save_calculation_from_file(vc : ValueCalculation, df : DataFrame, pd=None):
    #TODO: Proper implementation of this
    return vc