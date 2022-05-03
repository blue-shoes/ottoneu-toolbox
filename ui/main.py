from sqlalchemy import create_engine
import os
from sql import connection
from scrape import scrape_ottoneu

def main():
    dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
    db_dir = os.path.join(dirname, 'db')
    if not os.path.exists(db_dir):
        os.mkdir(db_dir)
    db_loc = os.path.join(dirname, 'db', 'otto_toolbox.db')
    engine = create_engine(f"sqlite:///{db_loc}", echo=True)
    conn = connection.Connection(db_loc)

    player_df = scrape_ottoneu.Scrape_Ottoneu().get_avg_salary_ds()

    player_sql = player_df[['FG MajorLeagueID','FG MinorLeagueID','Name','Org','Position(s)']]

    player_sql.to_sql('player',engine)

    roster_sql = player_df[['Avg Salary','Median Salary','Min Salary','Max Salary','Last 10','Roster %']]
    roster_sql['game_type'] = 0

    roster_sql.to_sql('salary_info', engine)

    print("Made it")

if __name__ == '__main__':
    main()