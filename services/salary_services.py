from dao.session import Session
from scrape.scrape_ottoneu import Scrape_Ottoneu
from domain.domain import Player, Salary_Info, Salary_Refresh
from decimal import Decimal
from re import sub
from services import player_services
from datetime import datetime

def update_salary_info(format):
        salary_df = Scrape_Ottoneu.get_avg_salary_ds(game_type = format)
        refresh = Salary_Refresh(format=format,last_refresh=datetime.now())
        with Session() as session:

            for idx, u_player in salary_df.iterrows():
                player = session.query(Player).filter(Player.ottoneu_id == idx).first()
                if player is None:
                    #Player does not exist in universe, need to add
                    player = player_services.create_player(idx, u_player)
                    session.add(player)
                else:
                    #Update player in case attributes have changed
                    player_services.update_player(player, u_player)

            current_players = session.query(Player).join(Salary_Info).all()
            for c_player in current_players:
                si = get_format_salary_info(c_player, format)
                if not c_player.ottoneu_id in salary_df.index:
                    # Not rostered in format, set all to 0
                    si = get_format_salary_info(c_player, format)
                    si.avg_salary = 0.0
                    si.med_salary = 0.0
                    si.min_salary = 0.0
                    si.max_salary = 0.0
                    si.last_10 = 0.0
                    si.roster_percentage = 0.0
                else:
                    u_player = salary_df.loc(c_player.ottoneu_id)
                    update_salary(si, u_player)
            session.add(refresh)
            session.commit()

def get_format_salary_info(player, format):
    for si in player.salary_info:
        if si.format == format:
            return si
    si = Salary_Info()
    player.salary_info.append(si)
    return si

def create_salary(row, format, player):
    salary_info = Salary_Info()
    salary_info.ottoneu_id=player.ottoneu_id
    salary_info.format = format
    salary_info.player = player
    update_salary(salary_info, row)
    player.salary_info.append(salary_info)

def update_salary(salary_info, row):
    salary_info.avg_salary = Decimal(sub(r'[^\d.]', '', row['Avg Salary']))
    salary_info.last_10 = Decimal(sub(r'[^\d.]', '', row['Last 10']))
    salary_info.max_salary = Decimal(sub(r'[^\d.]', '', row['Max Salary']))
    salary_info.med_salary = Decimal(sub(r'[^\d.]', '', row['Median Salary']))
    salary_info.min_salary = Decimal(sub(r'[^\d.]', '', row['Min Salary']))
    salary_info.roster_percentage = row['Roster %']