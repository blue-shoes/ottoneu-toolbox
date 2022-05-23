from domain.domain import Player, Salary_Info
from decimal import Decimal
from re import sub
from dao.session import Session

from scrape.scrape_ottoneu import Scrape_Ottoneu

class PlayerDAO():
    def update_salary_info(self, format):
        salary_df = Scrape_Ottoneu.get_avg_salary_ds(game_type = format)
        with Session() as session:

            for idx, u_player in salary_df.iterrows():
                if session.query(Player).filter(Player.ottoneu_id == idx).first() is None:
                    #Player does not exist in universe, need to add
                    player = self.create_player(idx, u_player)
                    session.add(player)

            current_players = session.query(Player).join(Salary_Info).all()
            for c_player in current_players:
                si = self.get_format_salary_info(c_player, format)
                if not c_player.ottoneu_id in salary_df.index:
                    # Not rostered in format, set all to 0
                    si = self.get_format_salary_info(c_player, format)
                    si.avg_salary = 0.0
                    si.med_salary = 0.0
                    si.min_salary = 0.0
                    si.max_salary = 0.0
                    si.last_10 = 0.0
                    si.roster_percentage = 0.0
                else:
                    u_player = salary_df.loc(c_player.ottoneu_id)
                    self.update_salary(si, u_player)
                    c_player.team = u_player['Org']
                    c_player.position = u_player['Position(s)']
            session.commit()
                

    def get_format_salary_info(self, player, format):
        for si in player.salary_info:
            if si.format == format:
                return si
        si = Salary_Info()
        player.salary_info.append(si)
        return si


    def create_player_universe(self):
        player_df = Scrape_Ottoneu().get_avg_salary_ds()
        with Session() as session:
            for idx, row in player_df.iterrows():
                player = self.create_player(idx, row)
                self.create_salary(row, 0, player)
                session.add(player)
            session.commit()
    
    def create_player(self, idx, player_row):
        player = Player()
        player.ottoneu_id = int(idx)
        player.fg_major_id = player_row['FG MajorLeagueID']
        player.fg_minor_id = player_row['FG MinorLeagueID']
        player.name = player_row['Name']
        player.team = player_row['Org']
        player.position = player_row['Position(s)']
        player.salary_info = []
        return player
    
    def create_salary(self, row, format, player):
        salary_info = Salary_Info()
        salary_info.ottoneu_id=player.ottoneu_id
        salary_info.format = format
        salary_info.player = player
        self.update_salary(salary_info, row)
        player.salary_info.append(salary_info)
    
    def update_salary(self, salary_info, row):
        salary_info.avg_salary = Decimal(sub(r'[^\d.]', '', row['Avg Salary']))
        salary_info.last_10 = Decimal(sub(r'[^\d.]', '', row['Last 10']))
        salary_info.max_salary = Decimal(sub(r'[^\d.]', '', row['Max Salary']))
        salary_info.med_salary = Decimal(sub(r'[^\d.]', '', row['Median Salary']))
        salary_info.min_salary = Decimal(sub(r'[^\d.]', '', row['Min Salary']))
        salary_info.roster_percentage = row['Roster %']