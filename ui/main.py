from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import os
from scrape import scrape_ottoneu
from domain.domain import Base, Player, Salary_Info
from dao.session import Session
from services import player_services

def main():
    #dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
    #db_dir = os.path.join(dirname, 'db')
    #if not os.path.exists(db_dir):
    #    os.mkdir(db_dir)
    #db_loc = os.path.join(dirname, 'db', 'otto_toolbox.db')
    #engine = create_engine(f"sqlite:///{db_loc}", echo=True)
    #conn = connection.Connection(db_loc)
    #Base.metadata.create_all(engine)

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

    #create_player_universe(player_df, session)
    #session.commit()

    player_services.create_player_universe()


    test_retrieve = Session().query(Player).join(Salary_Info).filter(Salary_Info.avg_salary > 20.0).all()
    #test_retrieve = select(Player).join(Player.salary_info).where(Salary_Info.avg_salary > 20.0)

    #players = session.scalars(test_retrieve)

    for player in test_retrieve:
        print(f"Name: {player.name}, avg_salary: {player.salary_info[0].avg_salary}")



if __name__ == '__main__':
    main()