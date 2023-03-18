from domain.domain import League, Team, Roster_Spot, Player, Draft, ValueCalculation
from domain.enum import ScoringFormat, Position, CalculationDataType, RepLevelScheme, RankingBasis
from domain.exception import InputException
from dao.session import Session
from scrape.scrape_ottoneu import Scrape_Ottoneu
from services import player_services, roster_services, calculation_services
from sqlalchemy.orm import joinedload
from typing import List
from util import date_util

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
                    player = player_services.get_player_from_ottoneu_player_page(idx, lg.ottoneu_id)
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
        if rosters:
            league = (session.query(League)
                    .options(
                        joinedload(League.teams)
                        .joinedload(Team.roster_spots)
                        .joinedload(Roster_Spot.player)
                    )
                    .filter_by(index = league_idx).first())
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
    lg.format = ScoringFormat.name_to_enum_map()[league_data['Format']]
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

def calculate_league_table(league:League, value_calc:ValueCalculation, fill_pt:bool=False, inflation:float=None, in_season:bool=False) -> None:
    '''Calculates the projected standings table for the League with the given ValueCalculation'''
    if value_calc.projection is None:
        raise InputException('ValueCalculation requires a projection to calculate league table')
    if in_season:
        stats ,_, pt = Scrape_Ottoneu().scrape_standings_page(league.index, date_util.get_current_ottoneu_year())
    standings = {}
    for team in league.teams:
        if fill_pt:
            rep_lvl = value_calc.get_rep_level_map()
            if ScoringFormat.is_h2h(value_calc.format):
                pt = roster_services.optimize_team_pt(team, value_calc.projection, value_calc.format, rep_lvl=rep_lvl, rp_limit=value_calc.get_input(CalculationDataType.RP_G_TARGET, 10), sp_limit=value_calc.get_input(CalculationDataType.GS_LIMIT, 10), pitch_basis=value_calc.pitcher_basis)
            else:
                pt = roster_services.optimize_team_pt(team, value_calc.projection, value_calc.format, rep_lvl=rep_lvl, rp_limit=value_calc.get_input(CalculationDataType.RP_IP_TARGET, 350))
        else:
            if ScoringFormat.is_h2h(value_calc.format):
                pt = roster_services.optimize_team_pt(team, value_calc.projection, value_calc.format, rp_limit=value_calc.get_input(CalculationDataType.RP_G_TARGET, 10), sp_limit=value_calc.get_input(CalculationDataType.GS_LIMIT, 10), pitch_basis=value_calc.pitcher_basis)
            else:
                pt = roster_services.optimize_team_pt(team, value_calc.projection, value_calc.format, rp_limit=value_calc.get_input(CalculationDataType.RP_IP_TARGET, 350))

        if ScoringFormat.is_points_type(value_calc.format):
            if in_season:
                points = stats.loc[team.ottoneu_id, 'Points']
            else:
                points = 0
            if fill_pt:
                for pos in Position.get_discrete_offensive_pos() + [Position.POS_MI] + Position.get_discrete_pitching_pos():
                    rl = rep_lvl.get(pos)
                    if pos == Position.POS_OF:
                        cap = 5*162
                    elif pos in Position.get_offensive_pos():
                        cap = 162
                    elif pos == Position.POS_SP:
                        if value_calc.pitcher_basis == RankingBasis.PIP:
                            cap = 1150
                        else:
                            cap = value_calc.get_input(CalculationDataType.GS_LIMIT) * 26
                    else:
                        if value_calc.pitcher_basis == RankingBasis.PIP:
                            cap = 350
                        else:
                            cap = value_calc.get_input(CalculationDataType.RP_G_TARGET) * 26
                    used_pt = sum(pt.get(pos, {0:0}).values())
                    if used_pt < cap:
                        additional_pt = cap - used_pt
                        points = points + additional_pt * rl
                if inflation is not None:
                    points1 = points
                    available_surplus_dol = team.free_cap - (team.spots - team.num_players)
                    points = points + available_surplus_dol * (1/value_calc.get_output(CalculationDataType.DOLLARS_PER_FOM)) * (1 - inflation/100)

            for rs in team.roster_spots:
                pp = value_calc.projection.get_player_projection(rs.player.index)
                if pp is None:
                    continue
                points = points + rs.g_h * calculation_services.get_batting_point_rate_from_player_projection(pp)
                points = points + rs.ip * calculation_services.get_pitching_point_rate_from_player_projection(pp, value_calc.format, value_calc.pitcher_basis)
        standings[team] = points
    sorted_standings = sorted(standings.items(), key=lambda x:x[1], reverse=True)
    rank = 1
    for item in sorted_standings:
        print(f'{rank}: {item[0].name}\t{item[1]}')
        rank = rank + 1
    
def main():
    from services import calculation_services
    import time
    #refresh_league(6)
    league = get_league(6)
    value_calc = calculation_services.load_calculation(8)
    start = time.time()
    calculate_league_table(league, value_calc, fill_pt=True, inflation=-40)
    end = time.time()
    print(f'time = {end-start}')

if __name__ == '__main__':
    main()