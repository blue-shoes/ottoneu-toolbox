from typing import Tuple

from domain.domain import Team, Roster_Spot, Projection
from domain.enum import StatType, ScoringFormat, Position, RankingBasis
from services import calculation_services

def optimize_team_pt(team:Team, proj:Projection, format=ScoringFormat, off_opt_stat:StatType=StatType.R, pit_opt_stat:StatType=StatType.WHIP, rp_ip:float=350) -> None:
    o_opt_pg = {}
    for rs in team.roster_spots:
        if rs.player.pos_eligible(Position.OFFENSE):
            #Offense
            pp = proj.get_player_projection(rs.player.index)
            g = pp.get_stat(StatType.G_HIT)
            if ScoringFormat.is_points_type(format):
                if g is None or g == 0:
                    o_opt_pg[rs.player] = 0
                else:
                    o_opt_pg[rs.player] = pp.get_stat(off_opt_stat) / g
            else:
                if g is None or g == 0:
                    o_opt_pg[rs.player] = 0
                else:
                    o_opt_pg[rs.player] = calculation_services.get_batting_point_rate_from_player_projection(pp, RankingBasis.PPG)
    o_sorted = sorted(o_opt_pg.items(), key=lambda x:x[1], reverse=True)
