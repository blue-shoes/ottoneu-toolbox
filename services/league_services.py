from pandas import DataFrame
from sqlalchemy.orm import joinedload
from typing import List
from collections import defaultdict

from domain.domain import League, Team, Roster_Spot, Player, Draft, ValueCalculation, Projected_Keeper, PlayerValue, CustomScoring
from domain.enum import ScoringFormat, Position, CalculationDataType as CDT, StatType, RankingBasis, InflationMethod, Platform
from domain.exception import InputException
from dao.session import Session
from scrape.scrape_ottoneu import Scrape_Ottoneu
from services import roster_services, calculation_services, custom_scoring_services
from util import date_util, list_util

def get_leagues(active: bool=True) -> List[League]:
    '''Returns Leagues from the database. If active is True, only Leagues marked as active are listed.'''
    with Session() as session:
        if active:
            return session.query(League).filter(active).order_by(League.site_id).all()
        else:
            return session.query(League).order_by(League.site_id).all()

def get_league_site_id(league_id:int) -> int:
    '''Gets the site id for the input league id'''
    with Session() as session:
        return session.query(League).filter_by(id = league_id).first().site_id

def get_league(league_id:int, rosters:bool=True) -> League:
    '''Retrieves the league from the database for the given id. If rosters is True, the league's teams and roster_spots are populated. Otherwise a shallow load is returned.'''
    with Session() as session:
        league = get_league_in_session(session, league_id, rosters)
    return league

def get_league_in_session(session:Session, league_id:int, rosters:bool=True) -> League:
    if rosters:
        league = (session.query(League)
                .options(
                    joinedload(League.teams)
                    .joinedload(Team.roster_spots)
                    .joinedload(Roster_Spot.player)
                )
                .filter_by(id = league_id).first())
        for keeper in league.projected_keepers:
            pass
        if league.position_set.name != 'Ottoneu':
            for team in league.teams:
                for rs in team.roster_spots:
                    rs.player.custom_positions = league.position_set.get_player_positions(rs.player.id)
        league.starting_set
    else:
        league = (session.query(League).filter_by(id = league_id).first())
    return league

def save_league(lg:League) -> League:
    '''Updates the league in the database with new league name, team names, and rosters, saves it to the database, and returns the updated League.'''
    with Session() as session:
        old_lg = session.query(League).filter(League.id == lg.id).first()
        if old_lg is None:
            session.add(lg)
        else:
            old_lg.name = lg.name
            old_lg.active = lg.active
            for team in old_lg.teams:
                for n_team in lg.teams:
                    if n_team.id == team.id:
                        team.name = n_team.name
        session.commit()
        lg_id = lg.id
    return get_league(lg_id, rosters=False)

def delete_league_by_id(lg_id: int) -> None:
    '''Deletes the league from the database by id.'''
    with Session() as session:
        league = session.query(League).filter(League.id == lg_id).first()
        session.delete(league)
        session.commit()

def league_exists(lg:League) -> bool:
    '''Checks if the given league exists in the database by id.'''
    with Session() as session:
        return session.query(League).filter(League.id == lg.id).first() is not None

def get_league_by_draft(draft:Draft, fill_rosters:bool=False) -> League:
    '''Returns the populated league by Draft'''
    with Session() as session:
        league = session.query(Draft).options(joinedload(Draft.league)).filter(Draft.id == draft.id).first().league
        return get_league(league.id, fill_rosters)

def calculate_league_table(league:League, value_calc:ValueCalculation, fill_pt:bool=False, inflation:float=None, 
                           in_season:bool=False, updated_teams:List[Team]=None, use_keepers:bool=False, prog=None) -> None:
    '''Calculates the projected standings table for the League with the given ValueCalculation'''
    if fill_pt and not ScoringFormat.is_points_type(league.s_format):
        raise InputException('Roto leagues do not support filling playing time (the math makes my brain hurt)')
    if value_calc.projection is None:
        raise InputException('ValueCalculation requires a projection to calculate league table')
    stats = None
    pt = None
    if use_keepers:
        keepers = league.projected_keepers
    else:
        keepers = []
    if value_calc.s_format == ScoringFormat.CUSTOM:
        custom_scoring = custom_scoring_services.get_scoring_format(value_calc.get_input(CDT.CUSTOM_SCORING_FORMAT))
    else:
        custom_scoring = None
    if in_season:
        if league.platform == Platform.OTTONEU:
            stats ,_, pt = Scrape_Ottoneu().scrape_standings_page(league.id, date_util.get_current_ottoneu_year())
    if updated_teams is None or inflation is not None:
        if not league.is_salary_cap():
            inflation = None
        for team in league.teams:
            __project_team_results(team, league, value_calc, league.s_format, fill_pt, inflation, stats=stats, accrued_pt=pt, keepers=keepers, use_keepers=use_keepers, custom_scoring=custom_scoring)   
            if prog:
                prog.increment_completion_percent(int(75/league.num_teams))
    else:
        for team in league.teams:
            if __list_contains_team(team, updated_teams):
                if not league.is_salary_cap():
                    inflation = None
                __project_team_results(team, league, value_calc, league.s_format, fill_pt, inflation, stats=stats, accrued_pt=pt, keepers=keepers, use_keepers=use_keepers, custom_scoring=custom_scoring)   
    if not ScoringFormat.is_points_type(league.s_format) and (custom_scoring is None or not custom_scoring.points_format):
        calculate_league_cat_ranks(league, custom_scoring)
    team_list = []
    for team in league.teams:
        team_list.append(team)
    set_team_ranks(league)

def __list_contains_team(team:Team, team_list:List[Team]) -> bool:
    for test_team in team_list:
        if team.id == test_team.id:
            return True
    return False

def __project_team_results(team:Team, league:League, value_calc:ValueCalculation, s_format:ScoringFormat, fill_pt:bool=False, 
                           inflation:float=None, stats:DataFrame=None, accrued_pt:DataFrame=None, keepers:List[Projected_Keeper]=[], 
                           use_keepers:bool=False, custom_scoring:CustomScoring=None) -> None:
    if accrued_pt is not None:
        #TODO: Need to adjust targets here
        ...
    if fill_pt and not ScoringFormat.is_points_type(s_format):
        raise InputException('Roto leagues do not support filling playing time (the math makes my brain hurt)')
    if fill_pt:
        rep_lvl = value_calc.get_rep_level_map()
        if ScoringFormat.is_h2h(s_format):
            pt = roster_services.optimize_team_pt(team, league, keepers, value_calc, s_format, 
                                                  use_keepers=use_keepers, 
                                                  custom_scoring=custom_scoring)
        else:
            pt = roster_services.optimize_team_pt(team, league, keepers, value_calc, s_format, 
                                                  use_keepers=use_keepers,
                                                  custom_scoring=custom_scoring)
    else:
        if ScoringFormat.is_h2h(s_format):
            pt = roster_services.optimize_team_pt(team, league, keepers, value_calc, s_format, use_keepers=use_keepers,
                                                  custom_scoring=custom_scoring)
        else:
            pt = roster_services.optimize_team_pt(team, league, keepers, value_calc, s_format,
                                                  use_keepers=use_keepers,
                                                  custom_scoring=custom_scoring)

    if ScoringFormat.is_points_type(s_format):
        if stats is not None:
            team.points = stats.loc[team.site_id, 'Points']
        else:
            team.points = 0
        positions = [p.position for p in value_calc.starting_set.positions]
        if fill_pt:
            for pos in positions:
                rl = rep_lvl.get(pos)
                if pos.offense:
                    cap = value_calc.starting_set.get_count_for_position(pos)*value_calc.get_input(CDT.BATTER_G_TARGET, 162)
                elif pos == Position.POS_SP:
                    if value_calc.pitcher_basis == RankingBasis.PIP:
                        cap = value_calc.get_input(CDT.IP_TARGET, 1500) - value_calc.get_input(CDT.RP_IP_TARGET, 350)
                    else:
                        cap = value_calc.get_input(CDT.GS_LIMIT, 10) * value_calc.get_input(CDT.H2H_WEEKS, 26)
                else:
                    if value_calc.pitcher_basis == RankingBasis.PIP:
                        cap = value_calc.get_input(CDT.RP_IP_TARGET, 350)
                    else:
                        cap = value_calc.get_input(CDT.RP_G_TARGET, 10) * value_calc.get_input(CDT.H2H_WEEKS, 26)
                used_pt = sum(pt.get(pos, {0:0}).values())
                if used_pt < cap:
                    additional_pt = cap - used_pt
                    team.points = team.points + additional_pt * rl
            if inflation is not None:
                if keepers:
                    keeper_player_ids = [pk.player_id for pk in keepers]
                else:
                    keeper_player_ids = []
                salaries = 0
                count = 0
                non_productive = 0
                for rs in team.roster_spots:
                    if use_keepers:
                        if rs.player_id in keeper_player_ids:
                            if rs.g_h == 0 and rs.ip == 0:
                                non_productive += rs.salary-1
                            salaries += rs.salary
                            count += 1
                    else:
                        if rs.g_h == 0 and rs.ip == 0:
                            non_productive += rs.salary-1
                        salaries += rs.salary
                        count += 1
                non_productive_per_team = value_calc.get_input(CDT.NON_PRODUCTIVE_DOLLARS) / value_calc.get_input(CDT.NUM_TEAMS) 
                productive_dollars = value_calc.get_input(CDT.SALARY_CAP, 400) - non_productive_per_team
                if non_productive > non_productive_per_team:
                    productive_dollars -= (non_productive - non_productive_per_team)
                available_surplus_dol = (productive_dollars - salaries + non_productive) - (value_calc.get_input(CDT.ROSTER_SPOTS, 40) - count)
                team.points += available_surplus_dol * (1/value_calc.get_output(CDT.DOLLARS_PER_FOM)) * (1 - inflation)

        for rs in team.roster_spots:
            pp = value_calc.projection.get_player_projection(rs.player.id)
            if pp is None:
                continue
            team.points += rs.g_h * calculation_services.get_batting_point_rate_from_player_projection(pp)
            team.points += rs.ip * calculation_services.get_pitching_point_rate_from_player_projection(pp, s_format, value_calc.pitcher_basis)
    else:
        team.cat_stats.clear()
        rate_cats = defaultdict(list)
        if stats is not None:
            prod_bat, _ = Scrape_Ottoneu().scrape_team_production_page(team.league_id, team.site_id)
            for cat in StatType.get_format_stat_categories(s_format):
                if cat in [StatType.AVG, StatType.SLG]:
                    rate_cats[cat].append((prod_bat['AB'].sum(), stats.loc[team.site_id, StatType.enum_to_display_dict().get(cat)]))
                elif cat == StatType.OBP:
                    #As of 3/22/23, 4x4 only has AB available, which is not quite correct for OBP
                    #to account for this, we increase AB by 12% to estimate PA per recent historical averages (2019-2022)
                    rate_cats.get(cat).append((prod_bat['AB'].sum() * 1.12, stats.loc[team.site_id, StatType.enum_to_display_dict().get(cat)]))
                elif cat in  [StatType.ERA, StatType.WHIP, StatType.HR_PER_9]:
                    rate_cats[cat].append((stats.loc[team.site_id, 'IP'], stats.loc[team.site_id, StatType.enum_to_display_dict().get(cat)]))
                else:
                    team.cat_stats[cat] = stats.loc[team.site_id, StatType.enum_to_display_dict().get(cat)]
        if custom_scoring:
            categories = [cat.category for cat in custom_scoring.stats]
        else:
            categories = ScoringFormat.get_format_stat_categories(s_format)
        for rs in team.roster_spots:
            pp = value_calc.projection.get_player_projection(rs.player.id)
            if pp is None:
                continue
            g = pp.get_stat(StatType.G_HIT)
            ip = pp.get_stat(StatType.IP)
            
            for cat in categories:
                if cat.hitter and rs.g_h > 0 and g > 0:
                    if cat.ratio:
                        denom = cat.rate_denom / g * rs.g_h
                        rate_cats[cat].append((denom, pp.get_stat(cat)))
                    else:
                        rate = pp.get_stat(cat) / g
                        team.cat_stats[cat] = team.cat_stats.get(cat, 0) + rate * rs.g_h
                elif not cat.hitter and rs.ip > 0 and ip > 0:
                    if cat.ratio:
                        rate_cats[cat].append((rs.ip, pp.get_stat(cat)))
                    else:
                        rate = pp.get_stat(cat) / ip
                        team.cat_stats[cat] = team.cat_stats.get(cat, 0) + rate * rs.ip
        for cat, val in rate_cats.items():
            team.cat_stats[cat] = list_util.weighted_average(val)

def calculate_league_cat_ranks(league:League, custom_scoring:CustomScoring=None) -> None:  
    if custom_scoring:
        categories = [cat.category for cat in custom_scoring.stats]
    else:
        categories = ScoringFormat.get_format_stat_categories(league.s_format)
    for cat in categories:
        cat_list = [team.cat_stats.get(cat) for team in league.teams]
        rank_map = list_util.rank_list_with_ties(cat_list,reverse=cat.higher_better, max_rank=league.num_teams)
        for team in league.teams:
            team.cat_ranks[cat] = rank_map.get(team.cat_stats.get(cat))
    for team in league.teams:
        team.points = sum(team.cat_ranks.values())
    set_team_ranks(league)

def set_team_ranks(league:League) -> None:
    sorted_teams = sorted(league.teams, key=lambda x: x.points, reverse=True)
    rank = 1
    for team in sorted_teams:
        team.lg_rank = rank
        rank = rank + 1

def calculate_league_inflation(league:League, value_calc:ValueCalculation, inf_method:InflationMethod, use_keepers:bool=False, reinitialize:bool=True, draft:Draft=None) -> float:
    '''Initializes the League's inflation level based on the method selected in user preferences. Calculates and stores the relevant 
    inputs to all methodologies in the League object. If use_keepers is False, all roster spots are used in the calculation. If it is
    True, only selected keepers are used.'''
    if reinitialize:
        league.init_inflation_calc()
    if use_keepers:
        use_keepers = league.projected_keepers is not None
    for pv in value_calc.get_position_values(Position.OVERALL):
        if pv.value > 1:
            league.captured_marginal_value += (pv.value - 1)
    for team in league.teams:
        for rs in team.roster_spots:
            if use_keepers and not league.is_keeper(rs.player_id):
                continue
            if rs.salary:
                league.total_salary += rs.salary
            league.num_rostered += 1
            pv = value_calc.get_player_value(rs.player_id, Position.OVERALL)
            if pv is None:
                val = 0
            else:
                val = max(0, pv.value)
                if val > 0:
                    league.num_valued_rostered += 1
            league.total_value += val

            if rs.salary:
                if val < 1:
                    if rs.salary > 7:
                        npp = 5
                    elif rs.salary < 3:
                        npp = rs.salary
                    else:
                        npp = min(rs.salary, 3 + (rs.salary-3) - 0.125 * pow(rs.salary-3,2))
                    league.npp_spent += npp-1
    if draft and draft.team_drafts:
        league.salary_cap = sum([team_draft.custom_draft_budget for team_draft in draft.team_drafts])
    else:
        league.salary_cap = league.team_salary_cap * league.num_teams
    league.max_npp = league.salary_cap-value_calc.get_input(CDT.ROSTER_SPOTS, 40) * league.num_teams - league.captured_marginal_value
    league.npp_spent = min(league.npp_spent, league.max_npp)
    return get_league_inflation(league, inf_method)

def add_player_to_draft_rosters(league:League, team_id:int, player:Player, pv:PlayerValue, salary:int, inf_method:InflationMethod):
    for team in league.teams:
        if team.site_id == team_id:
            rs = Roster_Spot()
            rs.player = player
            rs.player_id = player.id
            if league.is_salary_cap():
                rs.salary = salary
            else:
                rs.salary = 0
            team.roster_spots.append(rs)
            break
    if league.is_salary_cap():
        if pv is not None and pv.value > 0:
            val = pv.value
        else:
            val = 0
        update_league_inflation_last_trans(league, val, salary=salary, inf_method=inf_method, add_player=True)

def update_league_inflation_last_trans(league:League, value:float, salary:float, inf_method:InflationMethod, add_player:bool=True) -> float:
    '''Updates the league's inflation rate based on the change of one player and their projected value and salary. If add_player is True, the player is newly rostered. If
    it is False, the player is removed from rosters.'''
    if value < 1:
        if salary > 7:
            npp = 5
        elif salary < 3:
            npp = salary
        else:
            npp = 3 + (salary-3) - 0.125 * pow(salary-3,2)

    if add_player:
        mult = 1
    else:
        mult = -1
    league.total_salary += salary * mult
    league.total_value += max(0, value) * mult
    league.num_rostered += mult
    if value > 0:
        league.num_valued_rostered += mult
    else:
        league.npp_spent += npp-1 * mult
    league.npp_spent = min(league.npp_spent, league.max_npp)
    return get_league_inflation(league, inf_method)

def update_league_inflation(league:League, pv:PlayerValue, rs:Roster_Spot, inf_method:InflationMethod, add_player:bool=True) -> float:
    '''Updates the league's inflation rate based on the change of one player and their projected value and salary. If add_player is True, the player is newly rostered. If
    it is False, the player is removed from rosters.'''

    if pv is None:
        val = 0
    else:
        val = max(0, pv.value)

    npp = 0
    if val < 1:
        if rs.salary > 7:
            npp = 5
        elif rs.salary < 3:
            npp = rs.salary
        else:
            npp = 3 + (rs.salary-3) - 0.125 * pow(rs.salary-3,2)

    if add_player:
        mult = 1
    else:
        mult = -1

    league.total_salary += rs.salary * mult
    league.total_value += val * mult
    league.num_rostered += mult
    if val > 0:
        league.num_valued_rostered += mult
    else:
        league.npp_spent += (npp-1) * mult
    league.npp_spent = min(league.npp_spent, league.max_npp)
    return get_league_inflation(league, inf_method)

def get_league_inflation(league:League, inf_method:InflationMethod) -> float:
    '''Calculates the inflation rate for the given league using the given inflation methodology.'''
    salary_cap = league.salary_cap
    roster_spots = league.roster_spots
    if inf_method == InflationMethod.CONVENTIONAL:
        league.inflation = (salary_cap - league.total_salary) / (salary_cap - league.total_value) -1
    elif inf_method == InflationMethod.ROSTER_SPOTS_ONLY:
        league.inflation = (salary_cap - roster_spots*league.num_teams - (league.total_salary - league.num_rostered)) / (salary_cap - roster_spots*league.num_teams - (league.total_value - league.num_rostered)) -1
    else:
        num = league.captured_marginal_value - (league.total_salary - league.npp_spent - league.num_rostered)
        denom = league.captured_marginal_value - (league.total_value - league.num_valued_rostered)
        league.inflation = num / denom - 1
    league.inflation = max(-1, league.inflation)
    return league.inflation

def calculate_total_league_salary(league:League, use_keepers:bool=False) -> float:
    '''Returns the total amount of salary currently rostered by the league. The use_keepers flag will only count players currently in the league's projected_keepers list.'''
    salary = 0.0
    for team in league.teams:
            for rs in team.roster_spots:
                if use_keepers:
                   if not league.is_keeper(rs.player_id):
                       continue
                salary += rs.salary
    return salary