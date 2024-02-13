from bs4 import BeautifulSoup as Soup
import pandas as pd
from pandas import DataFrame
import os
import requests
from typing import List, Tuple
import logging
import re
import time

from scrape import scrape_base
from scrape.exceptions import CouchManagersException

class Scrape_CouchManagers(scrape_base.Scrape_Base):

    '''Implementation of Scrape_Base class for scraping information from Ottoneu website.'''
    def __init__(self, browser:str=None):
        super().__init__(browser)

    def get_draft_results(self, cm_id:int, reindex:bool=True) -> DataFrame:
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
        if reindex:
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
                team = div.find('div', {'class':'teams_isonline'})
            if team is None:
                continue
            id = int(team.get('id').split('_')[1])
            name = team.find('div', {'class': 'teams_teamname'}).contents[0].strip()
            teams.append((id, name))
        return teams

    def get_current_auctions(self, cm_id:int) -> List[Tuple[str, str, int]]:
        '''Returns a list of the current acutions as a tuple of (name, team, current_bid).'''
        auctions = []
        url = f'https://www.couchmanagers.com/auctions/?auction_id={cm_id}'
        self.setupDriver(force_headless=True)
        self.driver.get(url)
        time.sleep(2)
        html = self.driver.page_source
        self.driver.quit()
        soup = Soup(html, 'html.parser')
        player_divs = soup.find_all('div', {'class':'players_player_name'})
        if len(player_divs) == 0:
            logging.info('No current auctions')
            return auctions
        for pd in player_divs:
            cm_pid = re.findall('\((.+)\)', pd.find('a').get('href'))[0]
            name_tag = pd.find('a').contents
            name = name_tag[0] + name_tag[1].contents[0]
            team = soup.find('div', {'id': f'players_pos_{cm_pid}'}).contents[0].split('-')[-1]
            current_bid = soup.find('div', {'id': f'auction_{cm_pid}_amount'}).contents[0].split('$')[-1]
            auctions.append((name, team, current_bid))
        return auctions        