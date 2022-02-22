from bs4 import BeautifulSoup as Soup
import pandas as pd
import requests
from pandas import DataFrame
import os
from os import path

from scrape_base import Scrape_Base

class Scrape_Ottoneu(Scrape_Base):
    def getPlayerPositionsDfSoup(self):
        avg_values_url = 'https://ottoneu.fangraphs.com/averageValues'
        response = requests.get(avg_values_url)
        avg_val_soup = Soup(response.text, 'html.parser')
        table = avg_val_soup.find_all('table')[0]
        rows = table.find_all('tr')
        parsed_rows = [self.parse_row(row) for row in rows[1:]]
        print(rows[1])
        print(parsed_rows[0])
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

    def scrape_team_production_page(self, lg_id, team_id):
        dfs = []
        prod_url = f'https://ottoneu.fangraphs.com/{lg_id}/teamproduction?teamID={team_id}'
        response = requests.get(prod_url)
        prod_soup = Soup(response.text, 'html.parser')
        sections = prod_soup.find_all('section')
        dfs.append(self.parse_prod_table(sections[0]))
        dfs.append(self.parse_prod_table(sections[1]))
        return dfs
    
    def parse_prod_table(self, section):
        table = section.find_all('table')[0]
        rows = table.find_all('tr')
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
            if id != -1:
                dfs = self.scrape_team_production_page(lg_id, team_opt['value'])
                league_bat.append(dfs[0])
                league_arm.append(dfs[1])
        bat_df = pd.concat(league_bat)
        arm_df = pd.concat(league_arm)
        print(bat_df.head(20))
        print(arm_df.head(20))
    
    def parse_leagues_row(self, row):
        tds = row.find_all('td')
        parsed_row = []
        #url in form of /id/home
        val = tds[0].find('a').get('href').split('/')[1]
        parsed_row.append(val)
        for td in tds:
            if len(list(td.children)) > 1:
                #print(td)
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
        #print(html)
        browse_soup = Soup(html, 'html.parser')
        table = browse_soup.find_all('table')[0]
        rows = table.find_all('tr')
        parsed_rows = [self.parse_leagues_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = self.parse_leagues_header(rows[0])
        df.set_index("League Id", inplace=True)
        return df


scraper = Scrape_Ottoneu()
#scraper.scrape_team_production_page(160,1186,'FGP')
#scraper.scrape_league_production_pages(160)
scraper.scrape_league_table()