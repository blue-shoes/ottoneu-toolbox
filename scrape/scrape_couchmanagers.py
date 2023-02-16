import pandas as pd
from pandas import DataFrame
import os
import requests

from scrape import scrape_base

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
        with open(tmp_filepath, 'wb') as f:
            f.write(response.content)
            f.close()
        df = pd.read_csv(tmp_filepath)
        df.set_index('ottid', inplace=True)
        os.remove(tmp_filepath)
        return df