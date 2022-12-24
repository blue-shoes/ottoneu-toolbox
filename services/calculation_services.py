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
    min_indices = {}
    top_10_hit = []
    top_10_pitch = []
    top_10_hit_value = 0
    top_10_pitch_value = 0
    pos_count = {}
    total_value = 0
    total_count = 0
    total_hit_count = 0
    total_pitch_count = 0
    hit_value = 0
    for index, row in sorted.iterrows():
        value = string_util.parse_dollar(row['Values'])
        if value > rep_level_cost:
            break
        total_value += value
        total_count += 1
        if id_type == 'Ottoneu':
            player = player_services.get_player_by_ottoneu_id(int(index))
        elif id_type == "FanGraphs":
            player = player_services.get_player_by_fg_id(index)
        else:
            raise Exception('Invalid id type entered')
        hit = False
        pitch = False
        positions = player_services.get_player_positions(player, discrete=True)
        for pos in positions:
            if pos in Position.get_discrete_offensive_pos():
                hit = True
            if pos in Position.get_discrete_pitching_pos():
                pitch = True
            min_indices[pos] = player.index
            if pos in pos_count:
                pos_count[pos] = pos_count[pos] + 1
            else:
                pos_count[pos] = 1
        if hit and pitch:
            #Two way is hard...we'll split the value in half. It's close enough
            hit_value += value/2
            total_hit_count += 1
        elif hit:
            hit_value += value
            total_hit_count += 1
            if total_hit_count <= 10:
                top_10_hit_value += value
                top_10_hit.append(player.index)
        else:
            total_pitch_count += 1
            if total_pitch_count <= 10:
                top_10_pitch_value += value
                top_10_pitch.append(player.index)
    
    vc.set_input(CDT.NON_PRODUCTIVE_DOLLARS, (400*vc.get_input(CDT.NUM_TEAMS) - (total_value + 40*vc.get_input(CDT.NUM_TEAMS)-total_count)))
    hit_surplus = hit_value - total_count
    hit_split = int(hit_surplus/(total_value - total_count)*100)
    vc.set_input(CDT.HITTER_SPLIT, hit_split)
    for pos in pos_count:
        vc.set_output(CDT.pos_to_num_rostered().get(pos), pos_count[pos])
    for pos in min_indices:
        player_proj = vc.projection.get_player_projection(min_indices[pos])
        if game_type == ScoringFormat.FG_POINTS or game_type == ScoringFormat.H2H_FG_POINTS:
            points = get_points(player_proj, pos, False)
        elif game_type == ScoringFormat.SABR_POINTS or game_type == ScoringFormat.H2H_SABR_POINTS:
            points = get_points(player_proj, pos, True)
        else:
            raise Exception('Unimplemented game type')
        if pos in Position.get_offensive_pos():
            basis = vc.get_input(CDT.HITTER_RANKING_BASIS)
            if basis == RankingBasis.PPG:
                vc.set_output(CDT.pos_to_rep_level().get(pos), points/player_proj.get_stat(StatType.G_HIT))
            elif basis == RankingBasis.PPPA:
                vc.set_output(CDT.pos_to_rep_level().get(pos), points/player_proj.get_stat(StatType.PA))
            else:
                raise Exception('Unimplemented hitter ranking basis')
        else:
            basis = vc.get_input(CDT.PITCHER_RANKING_BASIS)
            if basis == RankingBasis.PIP:
                vc.set_output(CDT.pos_to_rep_level().get(pos), points/player_proj.get_stat(StatType.IP))
            elif basis == RankingBasis.PPG:
                vc.set_output(CDT.pos_to_rep_level().get(pos), points/player_proj.get_stat(StatType.G_PIT))
            else:
                raise Exception('Unimplemented pitcher ranking basis')
        
    top_10_hit_par = 0
    for idx in top_10_hit:
        pp = vc.projection.get_player_projection(idx)
        if game_type == ScoringFormat.FG_POINTS or game_type == ScoringFormat.H2H_FG_POINTS:
            points = get_points(player_proj, pos, False)
        elif game_type == ScoringFormat.SABR_POINTS or game_type == ScoringFormat.H2H_SABR_POINTS:
            points = get_points(player_proj, pos, True)
        else:
            raise Exception('Unimplemented game type')
        positions = player_services.get_player_positions(idx)
        rep_lvl = 999
        for pos in positions:
            test_rep = vc.get_output(CDT.pos_to_rep_level(pos))
            if test_rep < rep_lvl:
                rep_lvl = test_rep
        basis = vc.get_input(CDT.HITTER_RANKING_BASIS)
        if basis == RankingBasis.PPG:
            top_10_hit_par += (points - test_rep * pp.get_stat(StatType.G_HIT))
        elif basis == RankingBasis.PPPA:
            top_10_hit_par += (points - test_rep * pp.get_stat(StatType.PA))
        else:
            raise Exception('Unimplemented hitter ranking basis')
    vc.set_output(CDT.HITTER_DOLLAR_PER_FOM, (top_10_hit_value-10)/top_10_hit_par)

    top_10_pitch_par = 0
    for idx in top_10_pitch:
        pp = vc.projection.get_player_projection(idx)
        if game_type == ScoringFormat.FG_POINTS or game_type == ScoringFormat.H2H_FG_POINTS:
            points = get_points(player_proj, pos, False)
        elif game_type == ScoringFormat.SABR_POINTS or game_type == ScoringFormat.H2H_SABR_POINTS:
            points = get_points(player_proj, pos, True)
        else:
            raise Exception('Unimplemented game type')
        positions = player_services.get_player_positions(idx)
        rep_lvl = 999
        for pos in positions:
            test_rep = vc.get_output(CDT.pos_to_rep_level(pos))
            if test_rep < rep_lvl:
                rep_lvl = test_rep
        basis = vc.get_input(CDT.PITCHER_RANKING_BASIS)
        if basis == RankingBasis.PIP:
            top_10_pitch_par += (points - test_rep * pp.get_stat(StatType.IP))
        elif basis == RankingBasis.PPG:
            top_10_pitch_par += (points - test_rep * pp.get_stat(StatType.G_PIT))
        else:
            raise Exception('Unimplemented pitcher ranking basis')
    vc.set_output(CDT.PITCHER_DOLLAR_PER_FOM, (top_10_pitch_value-10)/top_10_pitch_par)

        
