import copy
from typing import Tuple, List, Dict

from domain.domain import Team, Roster_Spot, Projection, Player
from domain.enum import StatType, ScoringFormat, Position, RankingBasis
from services import calculation_services, player_services

def optimize_team_pt(team:Team, proj:Projection, format=ScoringFormat, off_opt_stat:StatType=StatType.R, pit_opt_stat:StatType=StatType.WHIP, rp_ip:float=350) -> None:
    o_opt_pg = {}
    p_opt_pg = {}
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
    possibilities.append(copy.deepcopy(team))
    pt = []
    pt.append({Position.POS_C: 0, Position.POS_1B: 0, Position.POS_2B: 0, Position.POS_3B:0, Position.POS_SS: 0, Position.POS_MI: 0, Position.POS_OF:0, Position.POS_UTIL:0})
    opt_sum = []
    opt_sum.append(0)
    j = 0
    for val in o_sorted:
        j = j+1
        print(f'player {j}, len poss = {len(opt_sum)}')
        player = val[0]
        elig_pos = player_services.get_player_positions(player, discrete=True)
        for i in range(0, len(possibilities)):
            first = True
            for pos in elig_pos:
                if pos in Position.get_offensive_pos():
                    __add_pt(possibilities, pt, opt_sum, val, pos, i, first=first)
                    first = False
                    #if pos == Position.POS_UTIL:
                        #Util taken care of outside the loop at the current index
                    #    continue
                    #else:
                    #    ...
            '''if player.pos_eligible(Position.POS_MI) and pt[i].get(Position.POS_MI) < 162:
                possibilities.append(copy.deepcopy(possibilities[i]))
                opt_sum.append(opt_sum[i])
                pt.append(copy.deepcopy(pt[i]))
                pt = min(val(1)(0), 162 - pt[-1].get(Position.POS_MI))
                pt[-1][Position.POS_MI] = pt[-1].get(Position.POS_MI) + pt
                opt_sum[-1] = opt_sum[-1] + pt*val(1)(1) 
                possibilities[-1].get_rs_by_player(val(0)).g_h = pt


            if pt[i].get(Position.POS_UTIL) < 162:
                pt = min(val(1)(0), 162 - pt[i].get(Position.POS_UTIL))
                pt[i][Position.POS_UTIL] = pt[i].get(Position.POS_UTIL) + pt
                opt_sum[i] = opt_sum[i] + pt*val(1)(1) 
                possibilities[i].get_rs_by_player(player).g_h = pt      '''            
    print(f'possibility length = {len(possibilities)}')
    print(f'max points = {max(opt_sum)}')

def __add_pt(possibilities:List[Team], pt:List[Dict[Position, int]], opt_sum:List[int], val:Tuple[Player,Tuple[int, float]], target_pos:Position, index:int, first:bool=False, used_pos:List[Position]=[], used_pt:int=0) -> None:
    if target_pos == Position.POS_OF:
        cap = 5*162
    else:
        cap = 162
    if pt[index].get(target_pos) < cap:
        if target_pos != Position.POS_UTIL and not first:
            possibilities.append(copy.deepcopy(possibilities[index]))
            opt_sum.append(opt_sum[index])
            pt.append(copy.deepcopy(pt[index]))
            index = -1
        rs = possibilities[index].get_rs_by_player(val[0])
        playing_time = min(val[1][0] - rs.g_h, cap - pt[index].get(target_pos))
        pt[index][target_pos] = pt[index].get(target_pos) + playing_time
        opt_sum[index] = opt_sum[index] + playing_time*val[1][1] 
        rs.g_h = playing_time + rs.g_h
        if rs.g_h < val[1][0]:
            used_pt = rs.g_h
            used_pos.append(target_pos)
            for pos in player_services.get_player_positions(val[0]):
                if pos in used_pos or pos == Position.OFFENSE:
                    continue
                if pos in Position.get_offensive_pos():
                    __add_pt(possibilities, pt, opt_sum, val, pos, index=len(possibilities)-1, used_pos = used_pos, used_pt=used_pt)
