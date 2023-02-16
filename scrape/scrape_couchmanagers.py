import pandas as pd
from pandas import DataFrame
import os
import requests
from typing import List, Tuple

from scrape import scrape_base
from scrape.exceptions import CouchManagersException

class Scrape_CouchManagers(scrape_base.Scrape_Base):

    '''Implementation of Scrape_Base class for scraping information from Ottoneu website.'''
    def __init__(self, browser:str=None):
        super().__init__(browser)

    def get_draft_results(self, cm_id:int) -> DataFrame:
        '''Retrieves the CouchManagers draft results as a DataFrame with an index of Ottoneu Player Id'''
        tmp_filepath = 'tmp/cm_auction.csv'
        url = f'https://www.couchmanagers.com/auctions/csv/download.php?auction_id={cm_id}'
        s = requests.Session()
        response = s.get(url)
        if response.content == b'No completed auction data yet.':
            raise CouchManagersException("Draft has no results")
        with open(tmp_filepath, 'wb') as f:
            f.write(response.content)
            f.close()
        df = pd.read_csv(tmp_filepath)
        df.set_index('ottid', inplace=True)
        os.remove(tmp_filepath)
        return df
    
    def get_draft_info(self, cm_id:int) -> List[Tuple[int, str]]:
        '''Returns a list of tuples containing CouchManagers draft team id and team name'''
        teams = []
        url = f'https://www.couchmanagers.com/auctions/?auction_id={cm_id}'
        soup = self._get_soup(url)
        team_divs = soup.find_all('div', {'class': 'teams'})
        if len(team_divs) == 0:
            raise CouchManagersException("The input draft does not exist")
        for div in team_divs:
            team = div.find('div', {'class':'teams_notonline'})
            if team is None:
                team = div.find('div', {'class':'teams_online'})
            id = int(team.get('id').split('_')[1])
            name = team.find('div', {'class': 'teams_teamname'}).contents[0].strip()
            teams.append((id, name))
        return teams