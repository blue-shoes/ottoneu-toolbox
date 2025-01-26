import pandas as pd
from pandas import DataFrame
import requests
from io import StringIO
from typing import Tuple, List
import os
import logging

from scrape import scrape_base
from scrape.exceptions import DavenportException

class Scrape_Davenport(scrape_base.Scrape_Base):

    '''Implementation of Scrape_Base class for scraping information from Ottoneu website.'''
    def __init__(self, browser:str=None):
        super().__init__(browser)
    
    def get_projections(self) -> Tuple[DataFrame,DataFrame]:
        '''Retrieves the Davenport projections as a tuple of DataFrames [position, pitcher] with an index of MLB Id'''
        pos_df = self.__get_dataset(lookup_url='https://claydavenport.com/projections/hitter_projections.txt', csv_url='https://claydavenport.com/projections/clayhitters.csv', lookup_col=['IDNO','MLBID'])
        pitch_df = self.__get_dataset(lookup_url='https://claydavenport.com/projections/pitcher_projections.txt', csv_url='https://claydavenport.com/projections/claypitchers.csv', lookup_col=['HOWEID','BPID'])
        return (pos_df, pitch_df)

    def __get_dataset(self, lookup_url:str, csv_url:str, lookup_col:List[str]) -> DataFrame:
        response = requests.get(lookup_url)
        pos_lookup = pd.read_csv(StringIO(response.text), sep='\\s+', on_bad_lines='skip')[lookup_col]
        pos_lookup.set_index(lookup_col[0], inplace=True)

        s = requests.Session()
        try:
            response = s.get(csv_url)
            if response.content is None or len(response.content) == 0:
                raise DavenportException("Projections do not exist")
            tmp_filepath = 'tmp/davenport.csv'
            with open(tmp_filepath, 'wb') as f:
                f.write(response.content)
                f.close()
            df = pd.read_csv(tmp_filepath)
            df = df.loc[df['HOWEID'] != '0'] #Remove team rows
            df['MLBID'] = df.apply(self.__get_mlbid, args=(pos_lookup,lookup_col), axis=1)
            df = df.loc[df['MLBID'] != -1] #Remove blank rows
            os.remove(tmp_filepath)
        except Exception as Argument:
            logging.exception('Davenport Exception')
            raise DavenportException('Error retrieving player projections.')
        return df
    
    def __get_mlbid(self, row, lookup, col):
        howeid = row['HOWEID']
        if pd.isna(howeid):
            return -1
        #print(howeid)
        try:
            return lookup.loc[howeid, col[1]]
        except KeyError:
            return -1


def main():
    scraper = Scrape_Davenport()
    dfs = scraper.get_projections()
    print(dfs[0].head())
    print(dfs[1].head())

if __name__ == '__main__':
    main()