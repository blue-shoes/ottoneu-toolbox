import copy
from typing import Tuple, List, Dict

from domain.domain import Team, Roster_Spot, Projection, Player
from domain.enum import StatType, ScoringFormat, Position, RankingBasis
from domain.exception import InputException
from services import calculation_services, player_services, projection_services

empty_pt_dict = {Position.POS_C:{},
                Position.POS_1B:{},
                Position.POS_2B:{},
                Position.POS_SS:{},
                Position.POS_3B:{},
                Position.POS_MI:{},
                Position.POS_OF:{},
                Position.POS_UTIL:{},
                Position.POS_SP:{},
                Position.POS_RP:{},}

def optimize_team_pt(team:Team, 
                     proj:Projection, 
                     format=ScoringFormat, 
                     off_opt_stat:StatType=StatType.R, 
                     pit_opt_stat:StatType=StatType.WHIP, 
                     rp_limit:float=350, 
                     sp_limit:float=10, 
                     off_g_limit:float=162,
                     pitch_basis:RankingBasis=RankingBasis.PIP,
                     rep_lvl:Dict[Position, float]=None,
                     current_pt:Dict[Position, Dict[int,int]]=None) -> Dict[Position, Dict[int,int]]:
    '''Creates a season lineup that maximizes the off_opt_stat and pit_opt_stat for the roster. Providing a rep_lvl dictionary will prevent players below replacement
    level from accruing stats/playing time. Providing a current_pt dictionary will inform how much playing time has alraedy been accrued by the team and will solve
    for the remaining playing time.'''
    o_opt_pg = {}
    p_opt_pg = {}
    if current_pt is None:
        current_pt = copy.deepcopy(empty_pt_dict)
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
            if pp is None:
                continue
            g = pp.get_stat(StatType.G_PIT)
            gs = pp.get_stat(StatType.GS_PIT)
            ip = pp.get_stat(StatType.IP)
            if not ScoringFormat.is_points_type(format):
                if g is None or g == 0 or ip is None or ip == 0:
                    p_opt_pg[rs.player] = ((0,0), 0)
                else:
                    if pitch_basis == RankingBasis.PIP:
                        p_opt_pg[rs.player] = (projection_services.get_pitcher_role_ips(pp), pp.get_stat(pit_opt_stat) / ip)
                    elif pitch_basis == RankingBasis.PPG:
                        p_opt_pg[rs.player] = ((gs, g-gs), pp.get_stat(pit_opt_stat) / g)
                    else:
                        raise InputException(f'Unexpected pitch_basis value {pitch_basis}')
            else:
                if g is None or g == 0 or ip is None or ip == 0:
                    p_opt_pg[rs.player] = ((0,0), 0)
                else:
                    if pitch_basis == RankingBasis.PIP:
                        p_opt_pg[rs.player] = (projection_services.get_pitcher_role_ips(pp), calculation_services.get_pitching_point_rate_from_player_projection(pp, format=format, basis=RankingBasis.PIP))
                    elif pitch_basis == RankingBasis.PPG:
                        p_opt_pg[rs.player] = ((gs, g-gs), calculation_services.get_pitching_point_rate_from_player_projection(pp, format=format, basis=RankingBasis.PPG))
                    else:
                        raise InputException(f'Unexpected pitch_basis value {pitch_basis}')
    o_sorted = sorted(o_opt_pg.items(), key=lambda x:x[1][1], reverse=True)

    possibilities = []
    possibilities.append({})
    pt = []
    pt.append(current_pt)
    opt_sum = []
    opt_sum.append(0)
    for val in o_sorted:
        player = val[0]
        if val[1][0] == 0:
            continue
        elig_pos = player_services.get_player_positions(player, discrete=True)
        for i in range(0, len(possibilities)):
            for pos in elig_pos:
                if pos in Position.get_offensive_pos():
                    last_pos = pos
            for pos in elig_pos:
                if pos in Position.get_offensive_pos():
                    last = (pos == last_pos)
                    __add_pt(possibilities, pt, opt_sum, val, pos, i, last=last, rep_lvl=rep_lvl, g_limit=off_g_limit)
                    first = False      
    bat_idx = max(range(len(opt_sum)), key=opt_sum.__getitem__)
    for player_id, games in possibilities[bat_idx].items():
        team.get_rs_by_player_id(player_id).g_h = games

    if ScoringFormat.is_points_type(format):
        p_sorted = sorted(p_opt_pg.items(), key=lambda x:x[1][1], reverse=True)
    elif pit_opt_stat in [StatType.WHIP, StatType.ERA, StatType.HR_PER_9]:
        p_sorted = sorted(p_opt_pg.items(), key=lambda x:x[1][1], reverse=False)
    else:
        p_sorted = sorted(p_opt_pg.items(), key=lambda x:x[1][1], reverse=True) 

    if pitch_basis == RankingBasis.PIP:
        rp_left = rp_limit
        sp_left = 1500 - rp_limit
    else:
        rp_left = rp_limit * 26
        sp_left = sp_limit * 26
    rp_left = rp_left - sum(current_pt.get(Position.POS_RP, {0:0}).values())
    sp_left = sp_left - sum(current_pt.get(Position.POS_SP, {0:0}).values())
    
    for val in p_sorted:
        player = val[0]
        if val[1][0] == (0,0):
            continue
        rp_ip = val[1][0][1]
        sp_ip = val[1][0][0]

        playing_time = 0
        if rp_left > 0 and rp_ip > 0 and (rep_lvl is None or rep_lvl.get(Position.POS_RP) < val[1][1]):
            if rp_ip > rp_left:
                playing_time = rp_left
            else:
                playing_time = rp_ip
            rp_left = rp_left - playing_time
            team.get_rs_by_player(player).ip = playing_time
            pt[bat_idx].get(Position.POS_RP, {})[player.index] = playing_time
        if sp_left > 0 and sp_ip > 0 and (rep_lvl is None or rep_lvl.get(Position.POS_SP) < val[1][1]):
            if sp_ip > sp_left:
                playing_time = sp_left
            else:
                playing_time = sp_ip
            sp_left = sp_left - playing_time
            team.get_rs_by_player(player).ip = playing_time + team.get_rs_by_player(player).ip
            pt[bat_idx].get(Position.POS_SP, {})[player.index] = playing_time
    return pt[bat_idx]

def __add_pt(possibilities:List[Dict[int, int]], 
             pt:List[Dict[Position, Dict[int,int]]], 
             opt_sum:List[int], 
             val:Tuple[Player,Tuple[int, float]], 
             target_pos:Position, 
             index:int, 
             last:bool=False, 
             used_pos:List[Position]=[], 
             used_pt:int=0, 
             rep_lvl:Dict[Position, float]=None,
             g_limit:float=163) -> None:
    if target_pos == Position.POS_OF:
        cap = 5*g_limit
    else:
        cap = g_limit
    g_h = 0
    if sum(pt[index].get(target_pos, {0:0}).values()) < cap and (rep_lvl is None or rep_lvl.get(target_pos) < val[1][1]):
        if target_pos != Position.POS_UTIL and not last:

            possibilities.append(copy.copy(possibilities[index]))
            opt_sum.append(copy.copy(opt_sum[index]))
            pt.append(copy.deepcopy(pt[index]))
            index = -1
        g_h = possibilities[index].get(val[0].index, 0)
        playing_time = min(val[1][0] - g_h, cap - sum(pt[index].get(target_pos, {0:0}).values()))
        if playing_time == 0:
            return
        pt[index].get(target_pos, {})[val[0].index] = playing_time
        opt_sum[index] = opt_sum[index] + playing_time*val[1][1] 
        g_h = playing_time + g_h
        possibilities[index][val[0].index] = g_h
        if g_h < val[1][0]:
            used_pt = g_h
            used_pos.append(target_pos)
            for pos in player_services.get_player_positions(val[0], discrete=True):
                if pos in used_pos:
                    continue
                if pos in Position.get_offensive_pos():
                    __add_pt(possibilities, pt, opt_sum, val, pos, index=len(possibilities)-1, used_pos = used_pos, used_pt=used_pt)

    if (g_h + used_pt) < val[1][0]:
        used_pos.append(target_pos)
        if val[0].pos_eligible(Position.POS_MI) and target_pos != Position.POS_MI and target_pos != Position.POS_UTIL:
            __add_pt(possibilities, pt, opt_sum, val, Position.POS_MI, index=index, used_pos = used_pos, used_pt=used_pt)
        elif target_pos != Position.POS_UTIL:
            __add_pt(possibilities, pt, opt_sum, val, Position.POS_UTIL, index=index, used_pos = used_pos, used_pt=used_pt)