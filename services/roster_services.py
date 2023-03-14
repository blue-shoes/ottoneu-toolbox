import copy
from typing import Tuple, List, Dict

from domain.domain import Team, Roster_Spot, Projection, Player
from domain.enum import StatType, ScoringFormat, Position, RankingBasis
from services import calculation_services, player_services

def optimize_team_pt(team:Team, proj:Projection, format=ScoringFormat, off_opt_stat:StatType=StatType.R, pit_opt_stat:StatType=StatType.WHIP, rp_ip:float=350) -> None:
    o_opt_pg = {}
    p_opt_pg = {}
    team.index_rs()
    for rs in team.roster_spots:
        if rs.player.pos_eligible(Position.OFFENSE):
            #Offense
            pp = proj.get_player_projection(rs.player.index)
            if pp is None:
                continue
            g = pp.get_stat(StatType.G_HIT)
            if not ScoringFormat.is_points_type(format):
                if g is None or g == 0:
                    o_opt_pg[rs.player] = (0, 0)
                else:
                    o_opt_pg[rs.player] = (g, pp.get_stat(off_opt_stat) / g)
            else:
                if g is None or g == 0:
                    o_opt_pg[rs.player] = (0, 0)
                else:
                    o_opt_pg[rs.player] = (g, calculation_services.get_batting_point_rate_from_player_projection(pp, RankingBasis.PPG))
        if rs.player.pos_eligible(Position.PITCHER):
            #Pitcher
            pp = proj.get_player_projection(rs.player.index)
            g = pp.get_stat(StatType.G_PIT)
            ip = pp.get_stat(StatType.IP)
            if not ScoringFormat.is_points_type(format):
                if g is None or g == 0 or ip is None or ip == 0:
                    p_opt_pg[rs.player] = (0, 0)
                else:
                    p_opt_pg[rs.player] = (ip, pp.get_stat(pit_opt_stat) / ip)
            else:
                if g is None or g == 0 or ip is None or ip == 0:
                    p_opt_pg[rs.player] = (0, 0)
                else:
                    p_opt_pg[rs.player] = (ip, calculation_services.get_pitching_point_rate_from_player_projection(pp, format=format, basis=RankingBasis.PIP))
    o_sorted = sorted(o_opt_pg.items(), key=lambda x:x[1][1], reverse=True)
    p_sorted = sorted(p_opt_pg.items(), key=lambda x:x[1][1], reverse=True)

    print(o_sorted)

    possibilities = []
    possibilities.append({})
    pt = []
    pt.append({Position.POS_C: 0, Position.POS_1B: 0, Position.POS_2B: 0, Position.POS_3B:0, Position.POS_SS: 0, Position.POS_MI: 0, Position.POS_OF:0, Position.POS_UTIL:0})
    opt_sum = []
    opt_sum.append(0)
    j = 0
    for val in o_sorted:
        j = j+1
        player = val[0]
        print(f'player {j}, {player.name}, len poss = {len(opt_sum)}')
        if val[1][0] == 0:
            continue
        elig_pos = player_services.get_player_positions(player, discrete=True)
        for i in range(0, len(possibilities)):
            first = True
            for pos in elig_pos:
                if pos in Position.get_offensive_pos():
                    __add_pt(possibilities, pt, opt_sum, val, pos, i, first=first)
                    first = False        
    print(f'possibility length = {len(possibilities)}')
    print(f'max points = {max(opt_sum)}')
    idx = max(range(len(opt_sum)), key=opt_sum.__getitem__)
    for idx, games in possibilities[idx].items():
        print(f'{idx}: {games} G')
    for key, games in pt[idx].items():
        print(f'{key}: {games} G')

def __add_pt(possibilities:List[Dict[int, int]], pt:List[Dict[Position, int]], opt_sum:List[int], val:Tuple[Player,Tuple[int, float]], target_pos:Position, index:int, first:bool=False, used_pos:List[Position]=[], used_pt:int=0, elig_pos:List[Position]=[]) -> None:
    if target_pos == Position.POS_OF:
        cap = 5*162
    else:
        cap = 162
    if pt[index].get(target_pos) < cap:
        if target_pos != Position.POS_UTIL and not first:
            possibilities.append(copy.copy(possibilities[index]))
            opt_sum.append(opt_sum[index])
            pt.append(copy.copy(pt[index]))
            index = -1
        g_h = possibilities[index].get(val[0].index, 0)
        playing_time = min(val[1][0] - g_h, cap - pt[index].get(target_pos))
        pt[index][target_pos] = pt[index].get(target_pos) + playing_time
        opt_sum[index] = opt_sum[index] + playing_time*val[1][1] 
        g_h = playing_time + g_h
        possibilities[index][val[0].index] = g_h
        if g_h < val[1][0]:
            used_pt = g_h
            used_pos.append(target_pos)
            for pos in player_services.get_player_positions(val[0]):
                if pos in used_pos or pos == Position.OFFENSE:
                    continue
                if pos in Position.get_offensive_pos():
                    __add_pt(possibilities, pt, opt_sum, val, pos, index=len(possibilities)-1, used_pos = used_pos, used_pt=used_pt)
    elif used_pt == 0:
        used_pos.append(target_pos)
        if val[0].pos_eligible(Position.POS_MI) and target_pos != Position.POS_MI and target_pos != Position.POS_UTIL:
            __add_pt(possibilities, pt, opt_sum, val, Position.POS_MI, index=index, used_pos = used_pos, used_pt=used_pt)
        elif target_pos != Position.POS_UTIL:
            __add_pt(possibilities, pt, opt_sum, val, Position.POS_UTIL, index=index, used_pos = used_pos, used_pt=used_pt)
        #print(f'at cap for {target_pos}')

