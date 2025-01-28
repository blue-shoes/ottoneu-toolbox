import copy
from typing import Tuple, List, Dict

from domain.domain import Team, Projection, Player, Projected_Keeper, CustomScoring, League, ValueCalculation
from domain.enum import StatType, ScoringFormat, Position, RankingBasis, CalculationDataType as CDT
from domain.exception import InputException
from services import calculation_services, player_services, projection_services

PlayerProjection = tuple[Player, int, float]


def optimize_team_pt(
    team: Team,
    league: League,
    keepers: List[Projected_Keeper],
    value_calc: ValueCalculation,
    s_format: ScoringFormat,
    off_opt_stat: StatType = StatType.R,
    pit_opt_stat: StatType = StatType.WHIP,
    current_pt: Dict[Position, Dict[int, int]] = None,
    use_keepers: bool = False,
    custom_scoring: CustomScoring = None,
) -> Dict[Position, Dict[int, int]]:
    """Creates a season lineup that maximizes the off_opt_stat and pit_opt_stat for the roster. Providing a rep_lvl dictionary will prevent players below replacement
    level from accruing stats/playing time. Providing a current_pt dictionary will inform how much playing time has alraedy been accrued by the team and will solve
    for the remaining playing time."""

    pitch_basis = value_calc.get_input(CDT.PITCHER_RANKING_BASIS, RankingBasis.PIP)

    if current_pt is None:
        current_pt = {pos: {} for pos in league.get_starting_positions()}
    team.index_rs()
    keeper_index = [k.player_id for k in keepers]
    o_opt_pg, p_opt_pg = get_player_rates(team, use_keepers, keeper_index, value_calc.projection, s_format, off_opt_stat, pit_opt_stat, pitch_basis, custom_scoring)
    o_sorted = sorted(o_opt_pg.items(), key=lambda x: x[1][2], reverse=True)
    pt = bat_opt(o_sorted, current_pt, league, team, value_calc.get_rep_level_map(), value_calc.get_input(CDT.BATTER_G_TARGET, 162))

    return pitch_opt(current_pt, p_opt_pg, pt, team, pit_opt_stat, value_calc)


def pitch_opt(current_pt: dict[Position, dict[int, int]], p_opt_pg: list, pt, team: Team, pit_opt_stat: StatType, value_calc: ValueCalculation) -> dict[Position, dict[int, int]]:
    if ScoringFormat.is_points_type(value_calc.s_format):
        p_sorted = sorted(p_opt_pg.items(), key=lambda x: x[1][2], reverse=True)
    elif pit_opt_stat in [StatType.WHIP, StatType.ERA, StatType.HR_PER_9]:
        p_sorted = sorted(p_opt_pg.items(), key=lambda x: x[1][2], reverse=False)
    else:
        p_sorted = sorted(p_opt_pg.items(), key=lambda x: x[1][2], reverse=True)

    rep_lvl = value_calc.get_rep_level_map()

    if value_calc.pitcher_basis == RankingBasis.PPG:
        rp_left = value_calc.get_input(CDT.RP_G_TARGET) * 26
        sp_left = value_calc.get_input(CDT.GS_LIMIT) * 26
    else:
        rp_left = value_calc.get_input(CDT.RP_IP_TARGET)
        sp_left = value_calc.get_input(CDT.IP_TARGET) - value_calc.get_input(CDT.RP_IP_TARGET)

    rp_left = rp_left - sum(current_pt.get(Position.POS_RP, {0: 0}).values())
    sp_left = sp_left - sum(current_pt.get(Position.POS_SP, {0: 0}).values())

    for val in p_sorted:
        player = val[1][0]
        if val[1][1] == (0, 0):
            continue
        rp_ip = val[1][1][1]
        sp_ip = val[1][1][0]

        playing_time = 0
        if rp_left > 0 and rp_ip > 0 and (rep_lvl is None or rep_lvl.get(Position.POS_RP) < val[1][2]):
            if rp_ip > rp_left:
                playing_time = rp_left
            else:
                playing_time = rp_ip
            rp_left = rp_left - playing_time
            team.get_rs_by_player(player).ip = playing_time
            pt.get(Position.POS_RP, {})[player.id] = playing_time
        if sp_left > 0 and sp_ip > 0 and (rep_lvl is None or rep_lvl.get(Position.POS_SP) < val[1][2]):
            if sp_ip > sp_left:
                playing_time = sp_left
            else:
                playing_time = sp_ip
            sp_left = sp_left - playing_time
            team.get_rs_by_player(player).ip = playing_time + team.get_rs_by_player(player).ip
            pt.get(Position.POS_SP, {})[player.id] = playing_time
    return pt


def get_player_rates(
    team: Team,
    use_keepers: bool,
    keeper_index: list[int],
    proj: Projection,
    s_format: ScoringFormat,
    off_opt_stat: StatType,
    pit_opt_stat: StatType,
    pitch_basis: RankingBasis,
    custom_scoring: CustomScoring,
) -> tuple[list[PlayerProjection], list[PlayerProjection]]:
    o_opt_pg = {}
    p_opt_pg = {}
    for rs in team.roster_spots:
        if not use_keepers or rs.player_id in keeper_index:
            if rs.player.pos_eligible(Position.OFFENSE):
                # Offense
                pp = proj.get_player_projection(rs.player.id)
                if pp is None:
                    continue
                if not pp.get_stat(StatType.G_HIT):
                    continue
                g = int(pp.get_stat(StatType.G_HIT))

                if not ScoringFormat.is_points_type(s_format):
                    if g is None or g == 0:
                        o_opt_pg[rs.player.id] = (rs.player, 0, 0)
                    else:
                        o_opt_pg[rs.player.id] = (rs.player, g, pp.get_stat(off_opt_stat) / g)
                else:
                    if g is None or g == 0:
                        o_opt_pg[rs.player.id] = (rs.player, 0, 0)
                    else:
                        o_opt_pg[rs.player.id] = (rs.player, g, calculation_services.get_batting_point_rate_from_player_projection(pp, RankingBasis.PPG, custom_format=custom_scoring))
            if rs.player.pos_eligible(Position.PITCHER):
                # Pitcher
                pp = proj.get_player_projection(rs.player.id)
                if pp is None:
                    continue
                g = int(pp.get_stat(StatType.G_PIT))
                gs = int(pp.get_stat(StatType.GS_PIT))
                ip = pp.get_stat(StatType.IP)
                if not ScoringFormat.is_points_type(s_format):
                    if g is None or g == 0 or ip is None or ip == 0:
                        p_opt_pg[rs.player.id] = (rs.player, (0, 0), 0)
                    else:
                        if pitch_basis == RankingBasis.PIP:
                            p_opt_pg[rs.player.id] = (rs.player, projection_services.get_pitcher_role_ips(pp), pp.get_stat(pit_opt_stat) / ip)
                        elif pitch_basis == RankingBasis.PPG:
                            p_opt_pg[rs.player.id] = (rs.player, (gs, g - gs), pp.get_stat(pit_opt_stat) / g)
                        else:
                            raise InputException(f'Unexpected pitch_basis value {pitch_basis}')
                else:
                    if g is None or g == 0 or ip is None or ip == 0:
                        p_opt_pg[rs.player.id] = (rs.player, (0, 0), 0)
                    else:
                        # TODO: need to update this to get SP/RP rate splits
                        if pitch_basis == RankingBasis.PIP:
                            p_opt_pg[rs.player.id] = (
                                rs.player,
                                projection_services.get_pitcher_role_ips(pp),
                                calculation_services.get_pitching_point_rate_from_player_projection(pp, s_format=s_format, basis=RankingBasis.PIP),
                            )
                        elif pitch_basis == RankingBasis.PPG:
                            p_opt_pg[rs.player.id] = (rs.player, (gs, g - gs), calculation_services.get_pitching_point_rate_from_player_projection(pp, s_format=s_format, basis=RankingBasis.PPG))
                        else:
                            raise InputException(f'Unexpected pitch_basis value {pitch_basis}')
    return o_opt_pg, p_opt_pg


def __add_pt(
    team: Team,
    league: League,
    possibilities: List[Dict[int, int]],
    pt: List[Dict[Position, Dict[int, int]]],
    opt_sum: List[float],
    val: Tuple[int, Tuple[Player, int, float]],
    target_pos: Position,
    index: int,
    last: bool = False,
    used_pos: List[Position] = [],
    used_pt: int = 0,
    rep_lvl: Dict[Position, float] = None,
    g_limit: float = 162,
) -> List[Dict[Position, int]]:
    cap = league.get_starting_slots().get(target_pos, 0) * g_limit
    results = []
    g_h = 0
    playing_time = 0
    if sum(pt[index].get(target_pos, {0: 0}).values()) < cap and (rep_lvl is None or rep_lvl.get(target_pos) < val[1][2]):
        if target_pos != Position.POS_UTIL and not last:
            possibilities.append(copy.copy(possibilities[index]))
            opt_sum.append(copy.copy(opt_sum[index]))
            pt.append(copy.deepcopy(pt[index]))
            index = -1
        g_h = possibilities[index].get(val[0], 0)
        playing_time = min(val[1][1] - g_h, cap - sum(pt[index].get(target_pos, {0: 0}).values()))
        if playing_time == 0:
            return results
        pt[index].get(target_pos, {})[val[0]] = playing_time
        opt_sum[index] = opt_sum[index] + playing_time * val[1][2]
        g_h = playing_time + g_h
        possibilities[index][val[0]] = g_h
        if g_h < val[1][1]:
            used_pt = g_h
            used_pos.append(target_pos)
            sub_list = None
            for pos in player_services.get_player_positions(val[1][0], discrete=True):
                if pos in used_pos:
                    continue
                if pos.offense:
                    sub_list = __add_pt(team, league, possibilities, pt, opt_sum, val, pos, index=-1, rep_lvl=rep_lvl, used_pos=used_pos, used_pt=used_pt, g_limit=g_limit)
                    for pos_dict in sub_list:
                        pos_dict[target_pos] = playing_time
                    results.extend(sub_list)
            if not sub_list:
                end_dict = {}
                end_dict[target_pos] = playing_time
                results.append(end_dict)

    if possibilities[index].get(val[0], 0) < val[1][1]:
        used_pos.append(target_pos)
        start_pos = [p for p in league.get_starting_positions() if p.offense and p not in used_pos and val[1][0].pos_eligible(p)]
        if start_pos:
            sub_list = __add_pt(team, league, possibilities, pt, opt_sum, val, start_pos[0], rep_lvl=rep_lvl, index=index, used_pos=used_pos, used_pt=used_pt, g_limit=g_limit)
            for pos_dict in sub_list:
                pos_dict[target_pos] = playing_time
            results.extend(sub_list)
        else:
            end_dict = {}
            end_dict[target_pos] = playing_time
            if end_dict not in results:
                results.append(end_dict)
    else:
        end_dict = {}
        end_dict[target_pos] = playing_time
        if end_dict not in results:
            results.append(end_dict)

    return results


def bat_opt(o_sorted: list, current_pt: list, league: League, team: Team, rep_lvl, off_g_limit) -> dict:
    possibilities = []
    possibilities.append({})
    pt = []
    pt.append(current_pt)
    opt_sum = []
    opt_sum.append(0)
    for val in o_sorted:
        stored = {}
        player = val[1][0]
        if val[1][1] == 0:
            continue
        elig_pos = player_services.get_player_positions(player, discrete=True)
        max_opt_sum = max(opt_sum)
        for i in range(len(possibilities)):
            for pos in elig_pos:
                if pos.offense:
                    last_pos = pos
            used_pt = []
            for pos in league.get_starting_positions():
                if player.pos_eligible(pos):
                    used_pt.append((pos, sum(pt[i].get(pos, {0: 0}).values())))
            answer_key = tuple(used_pt)
            answer_list = stored.get(answer_key, None)
            if answer_list:
                for idx, answers in enumerate(answer_list):
                    for idx2, entry in enumerate(answers):
                        if opt_sum[i] + val[1][2] * sum(entry.values()) < max_opt_sum:
                            continue
                        if idx < len(answer_list) - 1 or idx2 < len(answers) - 1:
                            possibilities.append(copy.copy(possibilities[i]))
                            opt_sum.append(copy.copy(opt_sum[i]))
                            pt.append(copy.deepcopy(pt[i]))
                            target_index = -1
                        else:
                            target_index = i
                        total_pt = 0
                        for key, games in entry.items():
                            pt[target_index].get(key, {})[val[0]] = games
                            total_pt += games
                        possibilities[target_index][val[0]] = total_pt
                        opt_sum[target_index] = opt_sum[target_index] + total_pt * val[1][2]
            else:
                answer_list = []
                for pos in elig_pos:
                    if pos.offense:
                        last = pos == last_pos
                        answer = __add_pt(team, league, possibilities, pt, opt_sum, val, pos, i, last=last, rep_lvl=rep_lvl, g_limit=off_g_limit, used_pos=[])
                        for possibility in answer:
                            to_delete = []
                            for pos, g in possibility.items():
                                if g == 0:
                                    to_delete.append(pos)
                            for pos in to_delete:
                                possibility.pop(pos)
                        if answer not in answer_list:
                            answer_list.append(answer)
                stored[answer_key] = answer_list

    bat_idx = max(range(len(opt_sum)), key=opt_sum.__getitem__)
    for player_id, games in possibilities[bat_idx].items():
        team.get_rs_by_player_id(player_id).g_h = games

    return pt[bat_idx]
