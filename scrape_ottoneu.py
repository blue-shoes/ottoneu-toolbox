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
        print(df.head())
        df['playerid'] = df['FG MinorLeagueID']
        df['FG MajorLeagueID'] = df['FG MajorLeagueID'].fillna(-1)
        df['FG MajorLeagueID'] = df['FG MajorLeagueID'].astype(int)
        df.loc[df['FG MajorLeagueID'] != -1, 'playerid'] = df['FG MajorLeagueID']
        df.set_index("playerid", inplace=True)
        df.index = df.index.astype(str, copy = False)
        return df    