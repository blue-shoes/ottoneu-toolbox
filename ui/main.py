from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
import os
from sql import connection
from scrape import scrape_ottoneu
from domain.domain import Base, Player, Salary_Info
from re import sub
from decimal import Decimal

def main():
    dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
    db_dir = os.path.join(dirname, 'db')
    if not os.path.exists(db_dir):
        os.mkdir(db_dir)
    db_loc = os.path.join(dirname, 'db', 'otto_toolbox.db')
    engine = create_engine(f"sqlite:///{db_loc}", echo=True)
    conn = connection.Connection(db_loc)
    Base.metadata.create_all(engine)

    #player_df = scrape_ottoneu.Scrape_Ottoneu().get_avg_salary_ds()

    #player_sql = player_df[['FG MajorLeagueID','FG MinorLeagueID','Name','Org','Position(s)']]

    #player_sql.to_sql('player',engine)

    #roster_sql = player_df[['Avg Salary','Median Salary','Min Salary','Max Salary','Last 10','Roster %']].reset_index()
    #roster_sql['game_type'] = 0
    #roster_sql['Avg Salary'] = roster_sql['Avg Salary'].apply(lambda x : Decimal(sub(r'[^\d.]', '', x)))
    #roster_sql['Median Salary'] = roster_sql['Median Salary'].apply(lambda x : Decimal(sub(r'[^\d.]', '', x)))
    #roster_sql['Min Salary'] = roster_sql['Min Salary'].apply(lambda x : Decimal(sub(r'[^\d.]', '', x)))
    #roster_sql['Max Salary'] = roster_sql['Max Salary'].apply(lambda x : Decimal(sub(r'[^\d.]', '', x)))
    #roster_sql['Last 10'] = roster_sql['Last 10'].apply(lambda x : Decimal(sub(r'[^\d.]', '', x)))

    #roster_sql.to_sql('salary_info', engine)

    #print("Made it")
    Session = sessionmaker(bind = engine)
    session = Session()

    #create_player_universe(player_df, session)
    #session.commit()

    test_retrieve = session.query(Player).join(Salary_Info).filter(Salary_Info.avg_salary > 20.0).all()
    #test_retrieve = select(Player).join(Player.salary_info).where(Salary_Info.avg_salary > 20.0)

    #players = session.scalars(test_retrieve)

    for player in test_retrieve:
        print(f"Name: {player.name}, avg_salary: {player.salary_info[0].avg_salary}")

def create_player_universe(player_df, session):
    for idx, row in player_df.iterrows():
        #player = Player(ottoneu_id=,name=row['Name'],fg_major_id=,
        #        fg_minor_id=, team=row['Org'], position=row['Position(s)'])
        player = Player()
        player.ottoneu_id = int(idx)
        player.fg_major_id = row['FG MajorLeagueID']
        player.fg_minor_id = row['FG MinorLeagueID']
        player.name = row['Name']
        player.team = row['Org']
        player.position = row['Position(s)']
        player.salary_info = []
        
        salary_info = Salary_Info()
        salary_info.ottoneu_id=player.ottoneu_id
        salary_info.avg_salary = Decimal(sub(r'[^\d.]', '', row['Avg Salary']))
        salary_info.game_type = 0
        salary_info.last_10 = Decimal(sub(r'[^\d.]', '', row['Last 10']))
        salary_info.max_salary = Decimal(sub(r'[^\d.]', '', row['Max Salary']))
        salary_info.med_salary = Decimal(sub(r'[^\d.]', '', row['Median Salary']))
        salary_info.min_salary = Decimal(sub(r'[^\d.]', '', row['Min Salary']))
        salary_info.player = player
        salary_info.roster_percentage = row['Roster %']
        player.salary_info.append(salary_info)
        session.add(player)

if __name__ == '__main__':
    main()