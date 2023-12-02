from pandas import DataFrame
from domain.domain import League, Team, Roster_Spot, Player, Draft, ValueCalculation, Projected_Keeper, PlayerValue
from domain.enum import ScoringFormat, Position, CalculationDataType, StatType, RankingBasis, InflationMethod
from domain.exception import InputException
from dao.session import Session
from scrape.scrape_ottoneu import Scrape_Ottoneu
from services import player_services, roster_services, calculation_services
from sqlalchemy.orm import joinedload
from typing import List
from util import date_util, list_util
from collections import defaultdict

from datetime import datetime

def refresh_league(league_idx:int, pd=None) -> League:
    '''Refreshes the given league id in the database. Checks if the most recent transaction is more recent than the last league refresh. If so, retrieves league rosters
    and updates Roster_Spots for the league.'''
    lg = get_league(league_idx, rosters=False)
    scraper = Scrape_Ottoneu()
    if pd is not None:
        pd.set_task_title("Checking last transaction date...")
        pd.increment_completion_percent(5)
    rec_tr = scraper.scrape_recent_trans_api(lg.ottoneu_id)
    if len(rec_tr) == 0:
        most_recent = datetime.now()
    else:
        most_recent = rec_tr.iloc[0]['Date']
    if most_recent > lg.last_refresh:
        if pd is not None:
            pd.set_task_title("Updating rosters...")
            pd.increment_completion_percent(5)
        upd_rost = scraper.scrape_roster_export(lg.ottoneu_id)
        finances = scraper.scrape_finances_page(lg.ottoneu_id)
        if pd is not None:
            pd.increment_completion_percent(30)
        with Session() as session:
            lg = (session.query(League)
                    .options(
                        joinedload(League.teams)
                        .joinedload(Team.roster_spots)
                        .joinedload(Roster_Spot.player)
                    )
                    .filter_by(index = league_idx).first())
            team_map = {}
            for team in lg.teams:
                #Clear roster
                for rs in team.roster_spots:
                    session.delete(rs)
                team_map[team.site_id] = team
            for idx, row in upd_rost.iterrows():
                team = row['TeamID']
                if team not in team_map:
                    # team not present, possibly on the restricted list
                    continue
                rs = Roster_Spot()
                player = session.query(Player).filter_by(ottoneu_id = idx).first()
                if player is None:
                    player = player_services.get_player_from_ottoneu_player_page(idx, lg.ottoneu_id, session=session, pd=pd)
                rs.player = player
                rs.salary = row['Salary'].split('$')[1]
                team_map[team].roster_spots.append(rs)
                if team_map[team].name != row['Team Name']:
                    team_map[team].name = row['Team Name']
            for idx, row in finances.iterrows():
                team = team_map[idx]
                team.num_players = row['Players']
                team.spots = row['Spots'] 
                team.salaries = row['Base Salaries']
                team.penalties = row['Cap Penalties']
                team.loans_in = row['Loans In']
                team.loans_out = row['Loans Out']
                team.free_cap = row['Cap Space']
            
            lg.last_refresh = datetime.now()
            session.commit()
            lg = get_league(league_idx)
    else:
        lg = get_league(league_idx)
    if pd is not None:
        pd.set_completion_percent(100)
    return lg

def get_leagues(active: bool=True) -> List[League]:
    '''Returns Leagues from the database. If active is True, only Leagues marked as active are listed.'''
    with Session() as session:
        if active:
            return session.query(League).filter(active).order_by(League.ottoneu_id).all()
        else:
            return session.query(League).order_by(League.ottoneu_id).all()

def get_league_ottoneu_id(league_idx:int) -> int:
    '''Gets the Ottoneu id for the input league index'''
    with Session() as session:
        return session.query(League).filter_by(index = league_idx).first().ottoneu_id

def get_league(league_idx:int, rosters:bool=True) -> League:
    '''Retrieves the league from the database for the given index. If rosters is True, the league's teams and roster_spots are populated. Otherwise a shallow load is returned.'''
    with Session() as session:
        league = get_league_in_session(session, league_idx, rosters)
    return league

def get_league_in_session(session:Session, league_idx:int, rosters:bool=True) -> League:
    if rosters:
        league = (session.query(League)
                .options(
                    joinedload(League.teams)
                    .joinedload(Team.roster_spots)
                    .joinedload(Roster_Spot.player)
                )
                .filter_by(index = league_idx).first())
        for keeper in league.projected_keepers:
            pass
    else:
        league = (session.query(League).filter_by(index = league_idx).first())
    return league

def create_league(league_ottoneu_id:int, pd=None) -> League:
    '''Creates a league in the Toolbox for a given Ottoneu league number. Scrapes the league info and league finances pages to get required information.'''
    if pd is not None:
        pd.set_task_title("Getting league info...")
        pd.increment_completion_percent(10)
    scraper = Scrape_Ottoneu()
    #rosters = scraper.scrape_roster_export(league_ottoneu_id)
    league_data = scraper.scrape_league_info_page(league_ottoneu_id)
    lg = League()
    lg.ottoneu_id = league_ottoneu_id
    lg.name = league_data['Name']
    lg.num_teams = league_data['Num Teams']
    lg.format = ScoringFormat.get_format_by_full_name(league_data['Format'])
    lg.last_refresh = datetime.min
    lg.active = True

    if pd is not None:
        pd.increment_completion_percent(15)

    fin = scraper.scrape_finances_page(league_ottoneu_id)
        
    for idx, row in fin.iterrows():
        team = Team()
        team.site_id = idx
        team.name = row['Name']
        lg.teams.append(team)

    if pd is not None:
        pd.increment_completion_percent(15)    

    return lg

def save_league(lg:League, pd=None) -> League:
    '''Updates the league in the database with new league name, team names, and rosters, saves it to the database, and returns the updated League.'''
    with Session() as session:
        old_lg = session.query(League).filter(League.index == lg.index).first()
        if old_lg is None:
            session.add(lg)
        else:
            old_lg.name = lg.name
            old_lg.active = lg.active
            for team in old_lg.teams:
                for n_team in lg.teams:
                    if n_team.index == team.index:
                        team.name = n_team.name
        session.commit()
        lg_idx = lg.index
    return refresh_league(lg_idx, pd)

def delete_league_by_id(lg_id: int) -> None:
    '''Deletes the league from the database by id.'''
    with Session() as session:
        league = session.query(League).filter(League.index == lg_id).first()
        session.delete(league)
        session.commit()

def league_exists(lg:League) -> bool:
    '''Checks if the given league exists in the database by index.'''
    with Session() as session:
        return session.query(League).filter(League.index == lg.index).first() is not None

def get_league_by_draft(draft:Draft, fill_rosters:bool=False) -> League:
    '''Returns the populated league by Draft'''
    with Session() as session:
        league = session.query(Draft).options(joinedload(Draft.league)).filter(Draft.index == draft.index).first().league
        return get_league(league.index, fill_rosters)

def calculate_league_table(league:League, value_calc:ValueCalculation, fill_pt:bool=False, inflation:float=None, in_season:bool=False, updated_teams:List[Team]=None, use_keepers=False) -> None:
    '''Calculates the projected standings table for the League with the given ValueCalculation'''
    if fill_pt and not ScoringFormat.is_points_type(league.format):
        raise InputException('Roto leagues do not support filling playing time (the math makes my brain hurt)')
    if value_calc.projection is None:
        raise InputException('ValueCalculation requires a projection to calculate league table')
    stats = None
    pt = None
    if use_keepers:
        keepers = league.projected_keepers
    else:
        keepers = []
    if in_season:
        stats ,_, pt = Scrape_Ottoneu().scrape_standings_page(league.index, date_util.get_current_ottoneu_year())
    if updated_teams is None or inflation is not None:
        for team in league.teams:
            project_team_results(team, value_calc, league.format, fill_pt, inflation, stats=stats, accrued_pt=pt, keepers=keepers, use_keepers=use_keepers)   
    else:
        for team in league.teams:
            if __list_contains_team(team, updated_teams):
                project_team_results(team, value_calc, league.format, fill_pt, inflation, stats=stats, accrued_pt=pt, keepers=keepers, use_keepers=use_keepers)   
    if not ScoringFormat.is_points_type(league.format):
        calculate_league_cat_ranks(league)
    team_list = []
    for team in league.teams:
        team_list.append(team)
    set_team_ranks(league)

def __list_contains_team(team:Team, team_list:List[Team]) -> bool:
    for test_team in team_list:
        if team.index == test_team.index:
            return True
    return False

def project_team_results(team:Team, value_calc:ValueCalculation, format:ScoringFormat, fill_pt:bool=False, inflation:float=None, stats:DataFrame=None, accrued_pt:DataFrame=None, keepers:List[Projected_Keeper]=[], use_keepers:bool=False) -> None:
    if accrued_pt is not None:
        #TODO: Need to adjust targets here
        ...
    if fill_pt and not ScoringFormat.is_points_type(format):
        raise InputException('Roto leagues do not support filling playing time (the math makes my brain hurt)')
    if fill_pt:
        rep_lvl = value_calc.get_rep_level_map()
        if ScoringFormat.is_h2h(format):
            pt = roster_services.optimize_team_pt(team, keepers, value_calc.projection, format, rep_lvl=rep_lvl, rp_limit=value_calc.get_input(CalculationDataType.RP_G_TARGET, 10), sp_limit=value_calc.get_input(CalculationDataType.GS_LIMIT, 10), pitch_basis=value_calc.pitcher_basis, off_g_limit=value_calc.get_input(CalculationDataType.BATTER_G_TARGET, 162), use_keepers=use_keepers)
        else:
            pt = roster_services.optimize_team_pt(team, keepers, value_calc.projection, format, rep_lvl=rep_lvl, rp_limit=value_calc.get_input(CalculationDataType.RP_IP_TARGET, 350), off_g_limit=value_calc.get_input(CalculationDataType.BATTER_G_TARGET, 162), use_keepers=use_keepers)
    else:
        if ScoringFormat.is_h2h(format):
            pt = roster_services.optimize_team_pt(team, keepers, value_calc.projection, format, rp_limit=value_calc.get_input(CalculationDataType.RP_G_TARGET, 10), sp_limit=value_calc.get_input(CalculationDataType.GS_LIMIT, 10), pitch_basis=value_calc.pitcher_basis, off_g_limit=value_calc.get_input(CalculationDataType.BATTER_G_TARGET, 162), use_keepers=use_keepers)
        else:
            pt = roster_services.optimize_team_pt(team, keepers, value_calc.projection, format, rp_limit=value_calc.get_input(CalculationDataType.RP_IP_TARGET, 350), off_g_limit=value_calc.get_input(CalculationDataType.BATTER_G_TARGET, 162), use_keepers=use_keepers)

    if ScoringFormat.is_points_type(format):
        if stats is not None:
            team.points = stats.loc[team.site_id, 'Points']
        else:
            team.points = 0
        if fill_pt:
            for pos in Position.get_discrete_offensive_pos() + [Position.POS_MI] + Position.get_discrete_pitching_pos():
                rl = rep_lvl.get(pos)
                if pos == Position.POS_OF:
                    cap = 5*value_calc.get_input(CalculationDataType.BATTER_G_TARGET, 162)
                elif pos in Position.get_offensive_pos():
                    cap = value_calc.get_input(CalculationDataType.BATTER_G_TARGET, 162)
                elif pos == Position.POS_SP:
                    if value_calc.pitcher_basis == RankingBasis.PIP:
                        cap = value_calc.get_input(CalculationDataType.IP_TARGET, 1500) - value_calc.get_input(CalculationDataType.RP_IP_TARGET, 350)
                    else:
                        cap = value_calc.get_input(CalculationDataType.GS_LIMIT, 10) * value_calc.get_input(CalculationDataType.H2H_WEEKS, 26)
                else:
                    if value_calc.pitcher_basis == RankingBasis.PIP:
                        cap = value_calc.get_input(CalculationDataType.RP_IP_TARGET, 350)
                    else:
                        cap = value_calc.get_input(CalculationDataType.RP_G_TARGET, 10) * value_calc.get_input(CalculationDataType.H2H_WEEKS, 26)
                used_pt = sum(pt.get(pos, {0:0}).values())
                if used_pt < cap:
                    additional_pt = cap - used_pt
                    team.points = team.points + additional_pt * rl
            if inflation is not None:
                if use_keepers:
                    keeper_player_ids = [pk.player_id for pk in keepers]
                    salaries = 0
                    count = 0
                    non_productive = 0
                    for rs in team.roster_spots:
                        if rs.player_id in keeper_player_ids:
                            if rs.g_h == 0 and rs.ip == 0:
                                non_productive += rs.salary
                            else:
                                salaries += rs.salary
                            count += 1
                    non_productive_per_team = value_calc.get_input(CalculationDataType.NON_PRODUCTIVE_DOLLARS) / value_calc.get_input(CalculationDataType.NUM_TEAMS) 
                    productive_dollars = 400 - non_productive_per_team
                    if non_productive > non_productive_per_team:
                        productive_dollars - (non_productive - non_productive_per_team)
                    available_surplus_dol = (productive_dollars - salaries) - (40 - count)
                else:
                    available_surplus_dol = team.free_cap - (team.spots - team.num_players)
                team.points = team.points + available_surplus_dol * (1/value_calc.get_output(CalculationDataType.DOLLARS_PER_FOM)) * (1 - inflation/100)

        for rs in team.roster_spots:
            pp = value_calc.projection.get_player_projection(rs.player.index)
            if pp is None:
                continue
            team.points = team.points + rs.g_h * calculation_services.get_batting_point_rate_from_player_projection(pp)
            team.points = team.points + rs.ip * calculation_services.get_pitching_point_rate_from_player_projection(pp, format, value_calc.pitcher_basis)
    else:
        rate_cats = defaultdict(list)
        if stats is not None:
            prod_bat, _ = Scrape_Ottoneu().scrape_team_production_page(team.league_id, team.site_id)
            for cat in StatType.get_format_stat_categories(format):
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
        for rs in team.roster_spots:
            pp = value_calc.projection.get_player_projection(rs.player.index)
            if pp is None:
                continue
            g = pp.get_stat(StatType.G_HIT)
            ip = pp.get_stat(StatType.IP)
            for cat in ScoringFormat.get_format_stat_categories(format):
                if cat.hitter and rs.g_h > 0 and g > 0:
                    if cat in [StatType.AVG, StatType.SLG]:
                        ab = (pp.get_stat(StatType.AB) / g) * rs.g_h
                        rate_cats[cat].append((ab, pp.get_stat(cat)))
                    elif cat == StatType.OBP:
                        pa = (pp.get_stat(StatType.PA) / g) * rs.g_h
                        rate_cats[cat].append((pa, pp.get_stat(cat)))
                    else:
                        rate = pp.get_stat(cat) / g
                        team.cat_stats[cat] = team.cat_stats.get(cat, 0) + rate * rs.g_h
                elif not cat.hitter and rs.ip > 0 and ip > 0:
                    if cat in [StatType.ERA, StatType.WHIP, StatType.HR_PER_9]:
                        rate_cats[cat].append((rs.ip, pp.get_stat(cat)))
                    else:
                        rate = pp.get_stat(cat) / ip
                        team.cat_stats[cat] = team.cat_stats.get(cat, 0) + rate * rs.ip
        for cat, val in rate_cats.items():
            team.cat_stats[cat] = list_util.weighted_average(val)

def calculate_league_cat_ranks(league:League) -> None:    
    for cat in ScoringFormat.get_format_stat_categories(league.format):
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

def calculate_league_inflation(league:League, value_calc:ValueCalculation, inf_method:InflationMethod, use_keepers:bool=False) -> float:
    '''Initializes the League's inflation level based on the method selected in user preferences. Calculates and stores the relevant 
    inputs to all methodologies in the League object. If use_keepers is False, all roster spots are used in the calculation. If it is
    True, only selected keepers are used.'''
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
            league.total_salary += rs.salary
            league.num_rostered += 1
            pv = value_calc.get_player_value(rs.player_id, Position.OVERALL)
            if pv is None:
                val = 0
            else:
                val = pv.value
                if val > 0:
                    league.num_valued_rostered += 1
            league.total_value += val

            if val < 1:
                if rs.salary > 7:
                    npp = 5
                else:
                    npp = min(rs.salary, 3 + (rs.salary-3) - 0.125 * pow(rs.salary-3,2))
                league.npp_spent += npp-1

    return get_league_inflation(league, inf_method)

def update_league_inflation(league:League, pv:PlayerValue, rs:Roster_Spot, inf_method:InflationMethod, add_player:bool=True) -> float:
    '''Updates the league's inflation rate based on the change of one player and their projected value and salary. If add_player is True, the player is newly rostered. If
    it is False, the player is removed from rosters.'''

    if pv is None:
        val = 0
    else:
        val = pv.value

    npp = 0
    if val < 1:
        if rs.salary > 7:
            npp = 5
        else:
            npp = min(rs.salary, 3 + (rs.salary-3) - 0.125 * pow(rs.salary-3,2))

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
        league.npp_spent += npp-1 * mult
    return get_league_inflation(league, inf_method)

def get_league_inflation(league:League, inf_method:InflationMethod) -> float:
    '''Calculates the inflation rate for the given league using the given inflation methodology.'''
    salary_cap = 400*league.num_teams
    if inf_method == InflationMethod.CONVENTIONAL:

        league.inflation = (salary_cap - league.total_salary) / (salary_cap - league.total_value) -1
    elif inf_method == InflationMethod.ROSTER_SPOTS_ONLY:
        league.inflation = (salary_cap - 40*league.num_teams - (league.total_salary - league.num_rostered)) / (salary_cap - 40*league.num_teams - (league.total_value - league.num_rostered)) -1
    else:
        num = league.captured_marginal_value - (league.total_salary - league.npp_spent - league.num_rostered)
        denom = league.captured_marginal_value - (league.total_value - league.num_valued_rostered)
        league.inflation = num / denom - 1
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