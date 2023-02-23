from dao.session import Session
from scrape.scrape_ottoneu import Scrape_Ottoneu
from domain.domain import Player, Salary_Info, Salary_Refresh
from domain.enum import ScoringFormat
from decimal import Decimal
from re import sub
from services import player_services
from datetime import datetime

def update_salary_info(format=ScoringFormat.ALL, pd=None) -> None:
    '''Updates the database with the salary information for the input scoring format.'''
    scraper = Scrape_Ottoneu()
    salary_df = scraper.get_avg_salary_ds(game_type = format.value)
    if pd is not None:
        pd.set_task_title('Refreshing DB...')
        pd.increment_completion_percent(40)
    with Session() as session:
        refresh = session.query(Salary_Refresh).filter(Salary_Refresh.format == format).first()
        if refresh is None:
            refresh = Salary_Refresh(format=format,last_refresh=datetime.now())
        else:
            refresh.last_refresh = datetime.now()
        players = {}
        for idx, u_player in salary_df.iterrows():
            player = session.query(Player).filter(Player.ottoneu_id == idx).first()
            if player is None:
                #Resolve against FG id, if possible
                if u_player['FG MajorLeagueID'] != '':
                    player = session.query(Player).filter(Player.fg_major_id == u_player['FG MajorLeagueID']).first()
                else:
                    player = session.query(Player).filter(Player.fg_minor_id == u_player['FG MinorLeagueID']).first()
            if player is None:
                #Player does not exist in universe, need to add
                player = player_services.create_player(u_player, ottoneu_id=idx)
                session.add(player)
            else:
                #Update player in case attributes have changed
                player_services.update_player(player, u_player)
            players[idx] = player

        existing_player_ids = []

        current_players = session.query(Player).join(Salary_Info).all()
        for c_player in current_players:
            si = get_format_salary_info(c_player, format)
            existing_player_ids.append(c_player.ottoneu_id)
            if not c_player.ottoneu_id in salary_df.index:
                # Not rostered in format, set all to 0
                si.avg_salary = 0.0
                si.med_salary = 0.0
                si.min_salary = 0.0
                si.max_salary = 0.0
                si.last_10 = 0.0
                si.roster_percentage = 0.0
            else:
                u_player = salary_df.loc[c_player.ottoneu_id]
                update_salary(si, u_player)
        for idx, row in salary_df.iterrows():
            if idx not in existing_player_ids:
                si = Salary_Info()
                si.player = players.get(idx)
                si.format = format
                update_salary(si, row)
                session.add(si)
        session.add(refresh)
        session.commit()
    #TODO: Might want this to automatically update loaded value calc/rosters


def get_format_salary_info(player: Player, format:ScoringFormat) -> Salary_Info:
    '''Returns the salary info for the player for the given format. If the salary info doesn't exist, create a new blank one and add it to the Player's list.'''
    for si in player.salary_info:
        if si.format == format:
            return si
    si = Salary_Info()
    si.format = format
    player.salary_info.append(si)
    return si

def create_salary(row, format:ScoringFormat, player:Player) -> None:
    '''Create a new Salary_Info for the Player in the given ScoringFormat, including setting the specific values. Expects a row from the Ottoneu average salaries dataset.'''
    salary_info = Salary_Info()
    salary_info.player_id=player.index
    salary_info.format = format
    salary_info.player = player
    update_salary(salary_info, row)
    player.salary_info.append(salary_info)

def update_salary(salary_info, row) -> None:
    '''Updates the input Salary_Info with avg_salary, last_10, max_salary, med_salary, min_salary, and roster percentage. Expects a row from the Ottoneu average salaries dataset.'''
    salary_info.avg_salary = Decimal(sub(r'[^\d.]', '', row['Avg Salary']))
    salary_info.last_10 = Decimal(sub(r'[^\d.]', '', row['Last 10']))
    salary_info.max_salary = Decimal(sub(r'[^\d.]', '', row['Max Salary']))
    salary_info.med_salary = Decimal(sub(r'[^\d.]', '', row['Median Salary']))
    salary_info.min_salary = Decimal(sub(r'[^\d.]', '', row['Min Salary']))
    salary_info.roster_percentage = row['Roster %']

def get_last_refresh(scoring_format=ScoringFormat.ALL) -> Salary_Refresh:
    '''Gets the Salary_Refresh for the input scoring format'''
    with Session() as session:
        return session.query(Salary_Refresh).filter(Salary_Refresh.format == scoring_format).first()