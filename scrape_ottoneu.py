from bs4 import BeautifulSoup as Soup
import pandas as pd
import requests
from pandas import DataFrame
import os
from os import path
from io import StringIO

from scrape_base import Scrape_Base

class Scrape_Ottoneu(Scrape_Base):

    def __init__(self):
        super().__init__()
        #Initialize directory for output calc files if required
        self.dirname = os.path.dirname(__file__)
        self.subdirpath = os.path.join(self.dirname, 'output')
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


    def get_player_position_ds(self, force_download=False):
        subdir = f'projection'
        dirname = os.path.dirname(__file__)
        subdirpath = os.path.join(dirname, subdir)
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
        return df[["TeamID","Team Name","Name","Salary"]]

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

#scraper = Scrape_Ottoneu()
#scraper.get_universe_production_tables()
#scraper = Scrape_Ottoneu()
#rost = scraper.scrape_roster_export(160)
#print(rost.head(50))