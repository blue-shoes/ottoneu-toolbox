from domain.domain import Player
from scrape.scrape_ottoneu import Scrape_Ottoneu
from dao.session import Session
from services import salary_services

def create_player_universe():
    player_df = Scrape_Ottoneu().get_avg_salary_ds()
    with Session() as session:
        for idx, row in player_df.iterrows():
            player = create_player(row, ottoneu_id=idx)
            salary_services.create_salary(row, 0, player)
            session.add(player)
        session.commit()

def update_player(player, u_player):
        player.fg_major_id = u_player['FG MajorLeagueID']
        player.team = u_player['Org']
        player.position = u_player['Position(s)']

def create_player(player_row, ottoneu_id=None, fg_id=None):
        player = Player()
        if ottoneu_id != None:
            player.ottoneu_id = int(ottoneu_id)
            player.fg_major_id = player_row['FG MajorLeagueID']
            player.fg_minor_id = player_row['FG MinorLeagueID']
            player.name = player_row['Name']
            player.team = player_row['Org']
            player.position = player_row['Position(s)']
        else:
            # This must have come from a FG leaderboard
            if fg_id.isnumber():
                player.fg_major_id = int(fg_id)
            else:
                player.fg_minor_id = fg_id
            player.name = player_row['Name']
            player.team = player_row['Team']
            player.position = 'Util'
        player.salary_info = []
        return player