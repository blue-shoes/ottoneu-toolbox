from bs4 import BeautifulSoup as Soup
import pandas as pd
import requests
from pandas import DataFrame
import os
from os import path
from io import StringIO
import hashlib
import datetime

from scrape import scrape_base

class Scrape_Ottoneu(scrape_base.Scrape_Base):

    def __init__(self):
        super().__init__()
        #Initialize directory for output calc files if required
        self.dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
        dir_path = os.path.join(self.dirname, 'data_dirs')
        if not path.exists(dir_path):
            os.mkdir(dir_path)
        self.subdirpath = os.path.join(self.dirname, 'data_dirs', 'output')
        if not path.exists(self.subdirpath):
            os.mkdir(self.subdirpath)

    def getPlayerPositionsDfSoup(self):
        avg_values_url = 'https://ottoneu.fangraphs.com/averageValues'
        response = requests.get(avg_values_url)
        avg_val_soup = Soup(response.text, 'html.parser')
        table = avg_val_soup.find_all('table')[0]
        rows = table.find_all('tr')
        parsed_rows = [self.parse_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = self.parse_header(rows[0])
        return df

    def parse_row(self, row):
        tds = row.find_all('td')
        parsed_row = []
        for td in tds:
            if len(list(td.children)) > 1:
                parsed_row.append(str(td.contents[0]).strip())
            else:
                parsed_row.append(td.string)
        return parsed_row

    def parse_header(self, row):
        return [str(x.string) for x in row.find_all('th')]
    
    def get_avg_salary_ds(self, force_download=True, game_type=0):
        if game_type == 0:
            avg_salary_url = 'https://ottoneu.fangraphs.com/averageValues?export=xml'
        else:
            avg_salary_url = f'https://ottoneu.fangraphs.com/averageValues?export=xml&gameType={game_type}'
        response = requests.get(avg_salary_url)
        salary_soup = Soup(response.text, 'xml')
        rows = salary_soup.find_all('player')
        parsed_rows = [self.parse_avg_salary_row(row) for row in rows]
        df = DataFrame(parsed_rows)
        df.columns = ['Ottoneu ID','FG MajorLeagueID','FG MinorLeagueID','Avg Salary','Min Salary','Max Salary','Last 10','Roster %','Position(s)','Org']
        df.set_index('Ottoneu ID', inplace=True)
        df.index = df.index.astype(str, copy=False)
        return df

    def parse_avg_salary_row(self, row):
        parsed_row = []
        parsed_row.append(row.get('ottoneu_id'))
        parsed_row.append(str(row.get('fg_majorleague_id')))
        parsed_row.append(row.get('fg_minorleague_id'))
        parsed_row.append(row.find('avg_salary').text)
        parsed_row.append(row.find('min_salary').text)
        parsed_row.append(row.find('max_salary').text)
        parsed_row.append(row.find('last_10').text)
        parsed_row.append(row.find('rostered_pct').text)
        parsed_row.append(row.find('positions').text)
        parsed_row.append(row.find('mlb_org').text)
        return parsed_row


    def get_player_position_ds(self, force_download=False):
        subdir = 'data_dirs/projection'
        subdirpath = os.path.join(self.dirname, subdir)
        filepath = os.path.join(subdirpath, "ottoneu_positions.csv")
        if path.exists(filepath) and not force_download:
            df = pd.read_csv(filepath)
        else:
            if self.driver == None:
                self.setupDriver()
            df = self.getDatasetAtAddress('https://ottoneu.fangraphs.com/averageValues?export=csv', filepath)
        df['playerid'] = df['FG MinorLeagueID']
        df['FG MajorLeagueID'] = df['FG MajorLeagueID'].fillna(-1)
        df['FG MajorLeagueID'] = df['FG MajorLeagueID'].astype(int)
        df.loc[df['FG MajorLeagueID'] != -1, 'playerid'] = df['FG MajorLeagueID']
        df.set_index("playerid", inplace=True)
        df.index = df.index.astype(str, copy = False)
        return df    

    def parse_prod_row(self, row):
        tds = row.find_all('td')
        parsed_row = []
        for td in tds:
            parsed_row.append(td.string)
        return parsed_row

    def scrape_roster_export(self, lg_id):
        roster_export_url = f'https://ottoneu.fangraphs.com/{lg_id}/rosterexport'
        response = requests.get(roster_export_url)
        rost_soup = Soup(response.text, 'html.parser')
        df = pd.read_csv(StringIO(rost_soup.contents[0]))
        df.set_index("ottoneu ID", inplace=True)
        df.index = df.index.astype(str, copy = False)
        return df
    
    def parse_trans_row(self, row):
        tds = row.find_all('td')
        parsed_row = []
        #url in form of *id=playerid
        playerid = tds[2].find('a').get('href').split('=')[1]
        parsed_row.append(playerid)
        #url in form of *team=teamid
        teamid = tds[3].find('a').get('href').split('=')[1]
        parsed_row.append(teamid)
        required_tds = [2,3,5]
        for ind in required_tds:
            td = tds[ind]
            if td.find('a') != None:
                parsed_row.append(td.find('a').string)
            else:
                parsed_row.append(td.string.strip())
        return parsed_row

    def scrape_transaction_page(self, lg_id):
        transactions_url = f'https://ottoneu.fangraphs.com/{lg_id}/transactions'
        response = requests.get(transactions_url)
        trans_soup = Soup(response.text, 'html.parser')
        table = trans_soup.find_all('table')[0]
        rows = table.find_all('tr')
        parsed_rows = [self.parse_trans_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = ['Ottoneu ID','Team ID','Name','Team','Salary']
        df.set_index('Ottoneu ID', inplace=True)
        return df

    def scrape_recent_trans_api(self, lg_id):
        rec_trans_url = f'https://ottoneu.fangraphs.com/api/recent_transactions?leagueID={lg_id}'
        response = requests.get(rec_trans_url)
        trans_soup = Soup(response.text, 'xml')
        rows = trans_soup.find_all('transaction')
        parsed_rows = [self.parse_rec_trans_row(row) for row in rows]
        df = DataFrame(parsed_rows)
        df.columns = ['Ottoneu ID','Team ID','Date','Salary','Type']
        df = df.astype({'Ottoneu ID': 'str'})
        return df

    def parse_rec_trans_row(self, row):
        player = row.find('player')
        parsed_row = []
        parsed_row.append(int(player.get('id')))
        team = row.find('team')
        parsed_row.append(int(team.get('id')))
        parsed_row.append(datetime.datetime.strptime(row.find('date').text, '%Y-%m-%d %H:%M:%S'))
        parsed_row.append(row.find('salary').text)
        parsed_row.append(row.find('transaction_type').text)
        return parsed_row

    def scrape_team_production_page(self, lg_id, team_id):
        dfs = []
        prod_url = f'https://ottoneu.fangraphs.com/{lg_id}/teamproduction?teamID={team_id}'
        response = requests.get(prod_url)
        prod_soup = Soup(response.text, 'html.parser')
        sections = prod_soup.find_all('section')
        pos_df = self.parse_prod_table(sections[0])
        if pos_df.empty:
            return None
        dfs.append(pos_df)
        dfs.append(self.parse_prod_table(sections[1]))
        return dfs
    
    def parse_prod_table(self, section):
        table = section.find_all('table')[0]
        rows = table.find_all('tr')
        if len(rows) == 1:
            #Empty production page. Skip league
            return DataFrame()
        parsed_rows = [self.parse_prod_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = self.parse_header(rows[0])
        df.set_index("POS", inplace=True)
        return df
    
    def scrape_league_production_pages(self, lg_id):
        prod_url = f'https://ottoneu.fangraphs.com/{lg_id}/teamproduction'
        response = requests.get(prod_url)
        prod_soup = Soup(response.text, 'html.parser')
        select = prod_soup.find_all('select')[0]
        team_opts = select.find_all('option')
        league_bat = []
        league_arm = []
        for team_opt in team_opts:
            id = team_opt['value']
            if id != '-1':
                dfs = self.scrape_team_production_page(lg_id, team_opt['value'])
                if dfs == None:
                    return []
                league_bat.append(dfs[0])
                league_arm.append(dfs[1])
        bat_df = pd.concat(league_bat)
        arm_df = pd.concat(league_arm)
        return [bat_df, arm_df]
        
    
    def parse_leagues_row(self, row):
        tds = row.find_all('td')
        parsed_row = []
        #url in form of /id/home
        val = tds[0].find('a').get('href').split('/')[1]
        parsed_row.append(val)
        for td in tds:
            if len(list(td.children)) > 1:
                parsed_row.append(str(td.contents[0]).strip())
                print('children > 1')
            else:
                parsed_row.append(td.string)
        return parsed_row

    def parse_leagues_header(self, row):
        cols = []
        cols.append('League Id')
        reg_cols = [str(x.string) for x in row.find_all('th')]
        for col in reg_cols:
            cols.append(col)
        return cols

    def scrape_league_table(self):
        url = 'https://ottoneu.fangraphs.com/browseleagues'

        self.setupDriver()
        self.driver.get(url)
        html = self.driver.page_source
        self.driver.close()
        browse_soup = Soup(html, 'html.parser')
        table = browse_soup.find_all('table')[0]
        rows = table.find_all('tr')
        parsed_rows = [self.parse_leagues_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = self.parse_leagues_header(rows[0])
        df.set_index("League Id", inplace=True)
        return df

    def get_universe_production_tables(self, limit=1e6):
        leagues = self.scrape_league_table()
        bat_dict = {}
        arm_dict = {}
        formats = []
        count = 0
        for lg_id, row in leagues.iterrows():
            if row['Game Type'] not in formats:
                formats.append(row['Game Type'])
            print(f'Scraping league {lg_id}, name {row["League Name"]}, format {row["Game Type"]}')
            dfs = self.scrape_league_production_pages(lg_id)
            if len(dfs) == 0:
                #League has no production values
                continue
            bat_dict[lg_id] = dfs[0]
            arm_dict[lg_id] = dfs[1]
            count += 1
            if count > limit:
                break

        for format in formats:
            filepath = os.path.join(self.subdirpath, f'{format}_prod.xlsx')
            with pd.ExcelWriter(filepath) as writer:
                for lg_id, row in leagues.iterrows():
                    if lg_id in bat_dict:
                        if row['Game Type'] == format:
                            bat_dict[lg_id].to_excel(writer, sheet_name=f'{lg_id}_bat')
                            arm_dict[lg_id].to_excel(writer, sheet_name=f'{lg_id}_arm')

def main():
    scraper = Scrape_Ottoneu()
    avg = scraper.get_avg_salary_ds(True)
    print(avg.index.dtype)
    #scraper.get_universe_production_tables()
    #rost = scraper.scrape_roster_export(160)
    #print(rost.head(50))
    #trans = scraper.scrape_recent_trans_api(160)
    #print(trans.head())

if __name__ == '__main__':
    main()