from pandas import DataFrame
from dao.session import Session
from domain.domain import ValueCalculation, Projection, PlayerProjection, ProjectionData
from domain.enum import Position, CalculationDataType as CDT, StatType, ScoringFormat, RankingBasis, IdType, RepLevelScheme, ProjectionType
from domain.exception import InputException
from value.point_values import PointValues
from services import player_services, projection_services
from util import string_util, date_util
import math
import logging
import datetime

def perform_point_calculation(value_calc, pd = None):
    if pd is not None:
        pd.set_task_title("Initializing Value Calculation...")
        pd.increment_completion_percent(5)
    value_calculation = PointValues(value_calc=value_calc)
    value_calculation.calculate_values(rank_pos=True, progress=pd)

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
        if value_calc.projection is not None:
            for pp in value_calc.projection.player_projections:
                break
    value_calc.init_value_dict()
    return value_calc

def get_values_for_year(year=None):
    if year is None:
        year = date_util.get_current_ottoneu_year()
    end = datetime.datetime(year, 10, 1)
    start = datetime.datetime(year-1, 10, 1)
    with Session() as session:
        return session.query(ValueCalculation).filter(ValueCalculation.timestamp > start, ValueCalculation.timestamp < end).all()

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

def get_batting_point_rate_from_player_projection(player_proj: PlayerProjection, basis=RankingBasis.PPG):
    points = get_points(player_proj, Position.OFFENSE)
    if basis == RankingBasis.PPG:
        games = player_proj.get_stat(StatType.G_HIT)
        if games is None or games == 0:
            return 0
        return points / games
    if basis == RankingBasis.PPPA:
        pa = player_proj.get_stat(StatType.PA)
        if pa is None or pa == 0:
            return 0
        return points / pa
    return 0

def get_pitching_point_rate_from_player_projection(player_proj: PlayerProjection, format: ScoringFormat, basis=RankingBasis.PIP):
    points = get_points(player_proj, Position.PITCHER, ScoringFormat.is_sabr(format))
    if basis == RankingBasis.PPG:
        games = player_proj.get_stat(StatType.G_PIT)
        if games is None or games == 0:
            return 0
        return points / games
    if basis == RankingBasis.PIP:
        ip = player_proj.get_stat(StatType.IP)
        if ip is None or ip == 0:
            return 0
        return points / ip
    return 0

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

def normalize_value_upload(df : DataFrame, game_type:ScoringFormat):
    if ScoringFormat.is_points_type(game_type):
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
    elif game_type == ScoringFormat.OLD_SCHOOL_5X5:
        id_col = None
        value_col = None
        col_map = {}
        for col in df.columns:
            if 'ID' in col.upper():
                id_col = col
            if 'VAL' in col.upper() or 'PRICE' in col.upper() or '$' in col:
                value_col = col
                col_map[value_col] = "Values"
            if 'R_Z' in col.upper() or 'R_SGP' in col.upper():
                col_map[col] = 'R_FOM'
            if 'HR_Z' in col.upper() or 'HR_SGP' in col.upper():
                col_map[col] = 'HR_FOM'
            if 'RBI_Z' in col.upper() or 'RBI_SGP' in col.upper():
                col_map[col] = 'RBI_FOM'
            if 'AVG_Z' in col.upper() or 'AVG_SGP' in col.upper():
                col_map[col] = 'AVG_FOM'
            if 'SB_Z' in col.upper() or 'SB_SGP' in col.upper():
                col_map[col] = 'SB_FOM'
            if 'W_Z' in col.upper() or 'W_SGP' in col.upper():
                col_map[col] = 'W_FOM'
            if 'SV_Z' in col.upper() or 'SV_SGP' in col.upper():
                col_map[col] = 'SV_FOM'
            if 'WHIP_Z' in col.upper() or 'WHIP_SGP' in col.upper():
                col_map[col] = 'WHIP_FOM'
            if 'ERA_Z' in col.upper() or 'ERA_SGP' in col.upper():
                col_map[col] = 'ERA_FOM'
            if 'K_Z' in col.upper() or 'K_SGP' in col.upper():
                col_map[col] = 'K_FOM'
            if 'G' == col.upper() or 'GAME' in col.upper() or 'PA' == col.upper():
                col_map[col] = 'H_PT'
            if 'IP' == col.upper() or 'GS' == col.upper():
                col_map[col] = 'P_PT'
        
        df.rename(columns=col_map, inplace=True)
        validate_msg = ''
        if id_col is None:
            validate_msg += 'No column with header containing \"ID\"\n'
        else:
            df.set_index(id_col, inplace=True)
        if value_col is None:
            validate_msg += 'Value column must be labeled \"Value\", \"Price\", or \"$\"\n'

        if has_required_data_for_rl(df, game_type):
            df['FOM'] = df.apply(calc_old_school_fom, axis=1)

    elif game_type == ScoringFormat.CLASSIC_4X4:
        id_col = None
        value_col = None
        col_map = {}
        for col in df.columns:
            if 'ID' in col.upper():
                id_col = col
            if 'VAL' in col.upper() or 'PRICE' in col.upper() or '$' in col:
                value_col = col
                col_map[value_col] = "Values"
            if 'R_Z' in col.upper() or 'R_SGP' in col.upper():
                col_map[col] = 'R_FOM'
            if 'HR_Z' in col.upper() or 'HR_SGP' in col.upper():
                col_map[col] = 'HR_FOM'
            if 'OBP_Z' in col.upper() or 'OBP_SGP' in col.upper():
                col_map[col] = 'OBP_FOM'
            if 'SLG_Z' in col.upper() or 'SLG_SGP' in col.upper():
                col_map[col] = 'SLG_FOM'
            if 'HR9_Z' in col.upper() or 'HR9_SGP' in col.upper():
                col_map[col] = 'HR9_FOM'
            if 'WHIP_Z' in col.upper() or 'WHIP_SGP' in col.upper():
                col_map[col] = 'WHIP_FOM'
            if 'ERA_Z' in col.upper() or 'ERA_SGP' in col.upper():
                col_map[col] = 'ERA_FOM'
            if 'K_Z' in col.upper() or 'K_SGP' in col.upper():
                col_map[col] = 'K_FOM'
            if 'G' == col.upper() or 'GAME' in col.upper() or 'PA' == col.upper():
                col_map[col] = 'H_PT'
            if 'IP' == col.upper() or 'GS' == col.upper():
                col_map[col] = 'P_PT'
        
        df.rename(columns=col_map, inplace=True)
        validate_msg = ''
        if id_col is None:
            validate_msg += 'No column with header containing \"ID\"\n'
        else:
            df.set_index(id_col, inplace=True)
        if value_col is None:
            validate_msg += 'Value column must be labeled \"Value\", \"Price\", or \"$\"\n'

        if has_required_data_for_rl(df, game_type):
            df['FOM'] = df.apply(calc_classic_fom, axis=1)

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

def calc_old_school_fom(row):
    return na_to_0(row['R_FOM']) + na_to_0(row['HR_FOM']) + na_to_0(row['RBI_FOM']) + na_to_0(row['AVG_FOM']) + na_to_0(row['SB_FOM']) \
            + na_to_0(row['W_FOM']) + na_to_0(row['SV_FOM']) + na_to_0(row['WHIP_FOM']) + na_to_0(row['ERA_FOM']) + na_to_0(row['K_FOM'])

def calc_classic_fom(row):
    return na_to_0(row['R_FOM']) + na_to_0(row['HR_FOM']) + na_to_0(row['OBP_FOM']) + na_to_0(row['SLG_FOM'])  \
            + na_to_0(row['HR9_FOM']) + na_to_0(row['WHIP_FOM']) + na_to_0(row['ERA_FOM']) + na_to_0(row['K_FOM'])


def na_to_0(value):
    if value == 'NA' or math.isnan(value):
        return 0
    else:
        return value

def has_required_data_for_rl(df:DataFrame, game_type:ScoringFormat):
    if ScoringFormat.is_points_type(game_type):
        return set(['Points','H_PT','P_PT']).issubset(df.columns)
    elif game_type == ScoringFormat.OLD_SCHOOL_5X5:
        return set(['R_FOM','HR_FOM','RBI_FOM','AVG_FOM','SB_FOM','W_FOM','SV_FOM','WHIP_FOM','ERA_FOM','K_FOM']).issubset(df.columns)
    elif game_type == ScoringFormat.CLASSIC_4X4:
        return set(['R_FOM','HR_FOM','OBP_FOM','SLG_FOM','HR9_FOM','WHIP_FOM','ERA_FOM','K_FOM']).issubset(df.columns)
    else:
        raise InputException(f'ScoringFormat {game_type} not currently implemented')

def get_values_from_fg_auction_files(vc: ValueCalculation, hit_df : DataFrame, pitch_df : DataFrame, rep_lvl_dol, pd=None):
    if pd is not None:
        pd.set_task_title("Determining replacement levels...")
        pd.increment_completion_percent(33)
    hit_df.set_index("PlayerId", inplace=True)
    rep_lvl_tuples = []
    for idx, row in hit_df.iterrows():
        if row['Dollars'] == float(rep_lvl_dol):
            rep_lvl_tuples.append((row['POS'], row['aPOS']))
    rep_lvls = {}
    min = 9999
    mi = 9999
    for pos in Position.get_discrete_offensive_pos():
        if pos == Position.POS_UTIL:
            continue
        for rl in rep_lvl_tuples:
            if pos.value in rl[0]:
                if pos not in rep_lvls or rep_lvls.get(pos) > rl[1]:
                    rep_lvls[pos] = rl[1]
                    if rl[1] < min:
                        min = rl[1]
                    if (pos == Position.POS_2B or pos == Position.POS_SS) and rl[1] < mi:
                        mi = rl[1]
    rep_lvls[Position.POS_UTIL] = min
    rep_lvls[Position.POS_MI] = mi

    rost = {}
    total_hitters = 0
    for idx, row in hit_df.iterrows():
        player = player_services.get_player_by_fg_id(idx)
        if row['Dollars'] >= rep_lvl_dol:
            total_hitters = total_hitters + 1
        vc.set_player_value(player.index, Position.OVERALL, row['Dollars'])
        vc.set_player_value(player.index, Position.OFFENSE, row['Dollars'])
        for pos in Position.get_offensive_pos():
            if pos == Position.OFFENSE:
                continue
            if player.pos_eligible(pos):
                val = row['PTS'] + rep_lvls.get(pos) + float(rep_lvl_dol)
                vc.set_player_value(player.index, pos, val)
                if row['Dollars'] >= rep_lvl_dol:
                    rost[pos] = rost.get(pos, 0) + 1

    pitch_df.set_index("PlayerId", inplace=True)
    total_pitchers = 0
    for idx, row in pitch_df.iterrows():
        player = player_services.get_player_by_fg_id(idx)
        if player.position == 'SP':
            rep_lvls[Position.POS_SP] = row['aPOS']
            break
    for idx, row in pitch_df.iterrows():
        player = player_services.get_player_by_fg_id(idx)
        if player.position == 'RP':
            rep_lvls[Position.POS_RP] = row['aPOS']
            break
    for idx, row in pitch_df.iterrows():
        player = player_services.get_player_by_fg_id(idx)
        if player.index in vc.value_dict:
            vc.set_player_value(player.index, Position.OVERALL, row['Dollars'] + vc.get_player_value(player.index, Position.OVERALL).value)
        else:
            vc.set_player_value(player.index, Position.OVERALL, row['Dollars'])
        vc.set_player_value(player.index, Position.PITCHER, row['Dollars'])
        if row['Dollars'] > rep_lvl_dol:
            total_pitchers = total_pitchers + 1
        for pos in Position.get_discrete_pitching_pos():
            if player.pos_eligible(pos):
                #with info given by Auction Calculator, may not be possible to split swing roles, so leave as-is 
                vc.set_player_value(player.index, pos, row['Dollars'])
                if row['Dollars'] >= float(rep_lvl_dol):
                    rost[pos] = rost.get(pos, 0) + 1
    for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
        vc.set_input(CDT.pos_to_num_rostered()[pos], rost[pos])
        vc.set_input(CDT.REP_LEVEL_SCHEME, float(RepLevelScheme.NUM_ROSTERED.value))
        vc.set_output(CDT.pos_to_num_rostered()[pos], rost[pos])
        vc.set_output(CDT.pos_to_rep_level()[pos], rep_lvls[pos])
    vc.set_output(CDT.TOTAL_HITTERS_ROSTERED, total_hitters)
    vc.set_output(CDT.TOTAL_PITCHERS_ROSTERED, total_pitchers)

    if pd is not None:
        pd.set_task_title('Saving Values')
        pd.increment_completion_percent(33)
    return save_calculation(vc)

def init_outputs_from_upload(vc: ValueCalculation, df : DataFrame, game_type, rep_level_cost=1, id_type=IdType.OTTONEU, pd=None):
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
        above_rep = False
        if value >= rep_level_cost:
            total_value += value
            total_count += 1
            above_rep = True
        if id_type == IdType.OTTONEU:
            player = player_services.get_player_by_ottoneu_id(int(index))
        elif id_type == IdType.FANGRAPHS:
            player = player_services.get_player_by_fg_id(index)
        else:
            raise Exception('Invalid id type entered')
        if player is None:
            #Player not in Ottoneu ToolBox Database, won't have a projection
            df.at[index, 'OTB_Idx'] = -1
            continue
        df.at[index, 'OTB_Idx'] = int(player.index)
        hit = False
        pitch = False
        positions = player_services.get_player_positions(player, discrete=True)
        if vc.projection is not None:
            pp = vc.projection.get_player_projection(player.index)
            if len(positions) == 1 and pp is not None:
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
                if pitch_role_good and above_rep:
                    sample_list = sample_players.get(positions[0])
                    if sample_list is None:
                        sample_list = []
                        sample_players[positions[0]] = sample_list
                    if proj_derive:
                        sample_list.append((value, player.index))
                    elif ScoringFormat.is_points_type(game_type):
                        sample_list.append((value, row['Points'], row['H_PT'], row['P_PT']))
                    elif game_type == ScoringFormat.OLD_SCHOOL_5X5 or game_type == ScoringFormat.CLASSIC_4X4:
                        sample_list.append((value, row['FOM']))
                    else:
                        sample_list.append((value, player.index))
        elif not proj_derive:
            if len(positions) == 1 and above_rep:
                sample_list = sample_players.get(positions[0])
                if sample_list is None:
                    sample_list = []
                    sample_players[positions[0]] = sample_list
                if ScoringFormat.is_points_type(game_type):
                    sample_list.append((value, row['Points'], row['H_PT'], row['P_PT']))
                elif game_type == ScoringFormat.OLD_SCHOOL_5X5 or game_type == ScoringFormat.CLASSIC_4X4:
                    sample_list.append((value, row['FOM']))
                else:
                    sample_list.append((value, player.index))

        for pos in positions:
            if pos in Position.get_discrete_offensive_pos():
                hit = True
            if pos in Position.get_discrete_pitching_pos():
                pitch = True
            if pos in pos_count:
                if above_rep:
                    pos_count[pos] = pos_count[pos] + 1
            else:
                pos_count[pos] = 1
        if hit and pitch and above_rep:
            #Two way is hard...we'll split the value in half. It's close enough. It's just fro split anyways
            hit_value += value/2
            total_hit_count += 1
        elif hit and above_rep:
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
            if pos != Position.POS_UTIL:
                vc.set_output(CDT.pos_to_rep_level().get(pos), -999)
            continue
        prices = [sample_list[0][0], sample_list[-1][0], sample_list[1][0], sample_list[-2][0]]
        if proj_derive:
            if vc.projection is None:
                hit_dol_per_fom = 0
                pitch_dol_per_fom = 0
                vc.set_output(CDT.pos_to_rep_level().get(pos), rl)
                continue
            if ScoringFormat.is_points_type(game_type):
                p_idx = [sample_list[0][1], sample_list[-1][1], sample_list[1][1], sample_list[-2][1]]
                fom = []
                pt = []
                for idx in p_idx:
                    pp = vc.projection.get_player_projection(idx)
                    fom.append(get_points(pp, pos, game_type in [ScoringFormat.SABR_POINTS, ScoringFormat.H2H_SABR_POINTS]))
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
                hit_dol_per_fom = -999
                pitch_dol_per_fom = -999
                vc.set_output(CDT.pos_to_rep_level().get(pos), -999)
                continue
        else:
            if ScoringFormat.is_points_type(game_type):
                fom = [sample_list[0][1], sample_list[-1][1], sample_list[1][1], sample_list[-2][1]]
                if pos in Position.get_offensive_pos():
                    pt = [sample_list[0][2], sample_list[-1][2], sample_list[1][2], sample_list[-2][2]]
                else:
                    pt = [sample_list[0][3], sample_list[-1][3], sample_list[1][3], sample_list[-2][3]]
            elif game_type == ScoringFormat.OLD_SCHOOL_5X5 or game_type == ScoringFormat.CLASSIC_4X4:
                fom = [sample_list[0][1], sample_list[-1][1], sample_list[1][1], sample_list[-2][1]]
                pt = []
        
        rl, d = calc_rep_levels_from_values(prices, game_type, fom, pt, rep_level_cost)
        vc.set_output(CDT.pos_to_rep_level().get(pos), rl)

        if pos in Position.get_offensive_pos() and hit_dol_per_fom < 0:
            hit_dol_per_fom = d
        elif pos in Position.get_pitching_pos() and pitch_dol_per_fom < 0:
            pitch_dol_per_fom = d

    #Util rep level is either the highest offensive position level, or the Util value, whichever is lower
    max_lvl = -999
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

def calc_rep_levels_from_values(vals, game_type, fom, pt, rep_lvl_dol):
    if len(vals) < 4 or len(fom) < 4:
        raise Exception('calc_rep_levels_from_values requires input lists of at least four entries')
    if ScoringFormat.is_points_type(game_type) or ((game_type == ScoringFormat.OLD_SCHOOL_5X5 or game_type == ScoringFormat.CLASSIC_4X4) and len(pt) == 4):
        #Calcs done algebraicly from equation (Value1 - Value2) = Dol/FOM * [(Points1 - rl * Games1) - (Points2 - rl * Games2)]
        numer = (vals[0] - vals[1])*(fom[2]-fom[3])-(vals[2]-vals[3])*(fom[0] - fom[1])
        denom = (vals[0] - vals[1])*(pt[2] - pt[3]) - (vals[2] - vals[3])*(pt[0] - pt[1])
        rl = numer / denom
        d_per_fom = (vals[0] - vals[1])/((fom[0] - rl*pt[0])-(fom[1] - rl*pt[1]))
        return rl, d_per_fom
    elif game_type == ScoringFormat.OLD_SCHOOL_5X5 or game_type == ScoringFormat.CLASSIC_4X4:
        d_per_fom = (vals[0] - vals[1]) / (fom[0] - fom[1])
        rl = fom[0] - (vals[0] - rep_lvl_dol) / d_per_fom
        return rl, d_per_fom
    else:
        raise Exception(f'Unsupported game type {game_type}')

def save_calculation_from_file(vc : ValueCalculation, df : DataFrame, pd=None, rep_val=1):
    df.set_index('OTB_Idx', inplace=True)
    pd.set_task_title('Creating position values...')
    remaining = (80 - pd.progress)
    tick = int(len(df)/remaining - 1)
    count = 0
    vc.values = []
    proj_derive = not has_required_data_for_rl(df, vc.format)
    pop_proj = False
    if not proj_derive and vc.projection is None and ScoringFormat.is_points_type(vc.format):
        pop_proj = True
        # Create hidden projection
        proj = Projection()
        proj.name = vc.name
        proj.detail = vc.description
        proj.dc_pt = False
        proj.hide = True
        proj.player_projections = []
        proj.ros = False
        proj.season = date_util.get_current_ottoneu_year()
        proj.timestamp = datetime.datetime.now()
        proj.type = ProjectionType.VALUE_DERIVED
        proj.valid_4x4 = vc.format == ScoringFormat.CLASSIC_4X4
        proj.valid_5x5 = vc.format == ScoringFormat.OLD_SCHOOL_5X5
        proj.valid_points = ScoringFormat.is_points_type(vc.format)
        vc.projection = proj
    for idx, row in df.iterrows():
        count += 1
        if count == tick:
            pd.increment_completion_percent(1)
            count = 0
        player = player_services.get_player(idx)
        if player is None:
            logging.debug(f'player with idx {idx} is not available')
            continue
        vc.set_player_value(idx, Position.OVERALL, row['Values'])
        if proj_derive and vc.projection is not None:
            pp = vc.projection.get_player_projection(idx)
            if pp is None:
                #Can't do any more. They simply won't show up in position-specific tables
                continue
            sabr = vc.format in (ScoringFormat.SABR_POINTS, ScoringFormat.H2H_SABR_POINTS)
            h_points = get_points(pp, Position.OFFENSE, sabr)
            if vc.hitter_basis == RankingBasis.PPG:
                h_pt = pp.get_stat(StatType.G_HIT)
            elif vc.hitter_basis == RankingBasis.PPPA:
                h_pt = pp.get_stat(StatType.PA)
            elif not ScoringFormat.is_points_type(vc.format):
                h_pt = pp.get_stat(StatType.G_HIT)
            else:
                raise Exception(f'Unhandled hitting basis {vc.hitter_basis}')
            p_points = get_points(pp, Position.PITCHER, sabr)
            if vc.pitcher_basis == RankingBasis.PIP:
                p_pt = pp.get_stat(StatType.IP)
            elif vc.pitcher_basis == RankingBasis.PPG:
                p_pt = pp.get_stat(StatType.G_PIT)
            elif not ScoringFormat.is_points_type(vc.format):
                p_pt = pp.get_stat(StatType.IP)
            else:
                raise Exception(f'Unhandled pitching basis {vc.pitcher_basis}')
        elif ScoringFormat.is_points_type(vc.format):
            h_points = row['Points']
            h_pt = row['H_PT']
            if pop_proj:
                p_pt = row['P_PT']
                pp = PlayerProjection()
                pp.player = player
                pp.projection_data = []
                pp.projection_data.append(ProjectionData(stat_type=StatType.POINTS, stat_value=row['Points']))
                pp.projection_data.append(ProjectionData(stat_type=StatType.PPG, stat_value=row['Hit_Rate']))
                pp.projection_data.append(ProjectionData(stat_type=StatType.PIP, stat_value=row['Pitch_Rate']))
                pp.pitcher = p_pt > 0 and h_pt == 0
                pp.two_way = (p_pt > 0 and h_pt > 0) or (row['Hit_Rate'] == 'NA' and row['Pitch_Rate'] == 'NA')
                vc.projection.player_projections.append(pp)
        hit = False
        pitch = False
        if ScoringFormat.is_points_type(vc.format):
            if vc.projection is None:
                # We don't have projections and we don't have points/rates/pt in values. Can't make position-specific determinations
                for pos in player_services.get_player_positions(player, discrete=False):
                    vc.set_player_value(idx, pos, row['Values'])
            elif player.is_two_way():
                #Not a good way to handle this right now, just print the value again
                for pos in player_services.get_player_positions(player, discrete=False):
                    vc.set_player_value(idx, pos, row['Values'])
            else:
                mi_rl = min(vc.get_output(CDT.REP_LEVEL_2B), vc.get_output(CDT.REP_LEVEL_SS))
                for pos in player_services.get_player_positions(player, discrete=True):
                    if pos in Position.get_offensive_pos():
                        if not hit:
                            vc.set_player_value(idx, Position.OFFENSE, row['Values'])
                            u_val = (h_points - vc.get_output(CDT.REP_LEVEL_UTIL) * h_pt) * vc.get_output(CDT.HITTER_DOLLAR_PER_FOM)
                            vc.set_player_value(idx, Position.POS_UTIL, u_val)
                            if player.pos_eligible(Position.POS_MI):
                                mi_val = (h_points - mi_rl * h_pt) * vc.get_output(CDT.HITTER_DOLLAR_PER_FOM)
                                vc.set_player_value(idx, Position.POS_MI, mi_val)
                            hit = True
                        elif pos == Position.POS_UTIL:
                            continue
                        rl = vc.get_output(CDT.pos_to_rep_level().get(pos))
                        val = (h_points - rl * h_pt) * vc.get_output(CDT.HITTER_DOLLAR_PER_FOM)
                        vc.set_player_value(idx, pos, val)

                    if pos in Position.get_pitching_pos():
                        if not pitch:
                            vc.set_player_value(idx, Position.PITCHER, row['Values'])
                            pitch = True
                        #This is a difficult nut to crack. Ideally we would reverse engineer a SP and RP rate, but that
                        #is likely imposible to do without having save/hold information. For now, to make sure we don't miss anyone,
                        #put them in the db positions and if able check projections to see if they do any starting or relieving
                        if vc.projection is None or not proj_derive:
                            vc.set_player_value(idx, pos, row['Values'])
                        else:
                            pp = vc.projection.get_player_projection(idx)
                            if pp is not None:
                                if pp.get_stat(StatType.GS_PIT) > 0 or pos == Position.POS_SP:
                                    vc.set_player_value(idx, Position.POS_SP, row['Values'])
                                if pp.get_stat(StatType.G_PIT) > pp.get_stat(StatType.GS_PIT) or pos == Position.POS_RP:
                                    vc.set_player_value(idx, Position.POS_RP, row['Values'])
                            else:
                                vc.set_player_value(idx, pos, row['Values'])
        else:
            if player.is_two_way():
                #Not a good way to handle this right now, just print the value again
                for pos in player_services.get_player_positions(player, discrete=False):
                    vc.set_player_value(idx, pos, row['Values'])
            elif vc.get_output(CDT.HITTER_DOLLAR_PER_FOM) == -999:
                # Don't have replacement levels, just set overall value
                for pos in player_services.get_player_positions(player, discrete=False):
                    vc.set_player_value(idx, pos, row['Values'])
            else:
                h_points = row['FOM']
                mi_rl = min(vc.get_output(CDT.REP_LEVEL_2B), vc.get_output(CDT.REP_LEVEL_SS))
                for pos in player_services.get_player_positions(player, discrete=True):
                    if pos in Position.get_offensive_pos():
                        if not hit:
                            vc.set_player_value(idx, Position.OFFENSE, row['Values'])
                            if vc.hitter_basis == RankingBasis.ZSCORE_PER_G:
                                u_val = (h_points - vc.get_output(CDT.REP_LEVEL_UTIL)) * (row['H_PT'] / 150) * vc.get_output(CDT.HITTER_DOLLAR_PER_FOM) + rep_val
                            else:
                                u_val = (h_points - vc.get_output(CDT.REP_LEVEL_UTIL)) * vc.get_output(CDT.HITTER_DOLLAR_PER_FOM) + rep_val
                            vc.set_player_value(idx, Position.POS_UTIL, u_val)
                            if player.pos_eligible(Position.POS_MI):
                                if vc.hitter_basis == RankingBasis.ZSCORE_PER_G:
                                    mi_val = (h_points - mi_rl) * (row['H_PT'] / 150) * vc.get_output(CDT.HITTER_DOLLAR_PER_FOM) + rep_val
                                else:
                                    mi_val = (h_points - mi_rl) * vc.get_output(CDT.HITTER_DOLLAR_PER_FOM) + rep_val
                                vc.set_player_value(idx, Position.POS_MI, mi_val)
                            hit = True
                        elif pos == Position.POS_UTIL:
                            continue
                        rl = vc.get_output(CDT.pos_to_rep_level().get(pos))
                        if vc.hitter_basis == RankingBasis.ZSCORE_PER_G:
                            val = (h_points - rl) * (row['H_PT'] / 150) * vc.get_output(CDT.HITTER_DOLLAR_PER_FOM) + rep_val
                        else:
                            val = (h_points - rl) * vc.get_output(CDT.HITTER_DOLLAR_PER_FOM) + rep_val
                        vc.set_player_value(idx, pos, val)

                    if pos in Position.get_pitching_pos():
                        if not pitch:
                            vc.set_player_value(idx, Position.PITCHER, row['Values'])
                            pitch = True
                        #This is a difficult nut to crack. Ideally we would reverse engineer a SP and RP rate, but that
                        #is likely imposible to do without having save/hold information. For now, to make sure we don't miss anyone,
                        #put them in the db positions and if able check projections to see if they do any starting or relieving
                        vc.set_player_value(idx, pos, row['Values'])

    save_calculation(vc)
    return vc

def delete_values_by_id(values_id):
    with Session() as session:
        val = session.query(ValueCalculation).filter(ValueCalculation.index == values_id).first()
        proj = None
        if val.projection is not None and val.projection.type == ProjectionType.VALUE_DERIVED:
            proj = val.projection
        session.delete(val)
        if proj is not None:
            session.delete(proj)
        session.commit()

def get_values_with_projection_id(proj_id):
    '''Gets all ValueCalculations in the databse with the input projection id'''
    with Session() as session:
        return session.query(ValueCalculation).join(ValueCalculation.projection).filter(Projection.index == proj_id).all()