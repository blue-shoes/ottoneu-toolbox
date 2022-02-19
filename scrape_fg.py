import configparser
import os
from os import path
import pandas as pd
import scrape_base

class Scrape_Fg(scrape_base.Scrape_Base):

    def getLeaderboardDataset(self, page, csv_name, force_download=False, player=True):
        subdir = f'leaderboard'
        dirname = os.path.dirname(__file__)
        subdirpath = os.path.join(dirname, subdir)
        if not path.exists(subdirpath):
            os.mkdir(subdirpath)
        filepath = os.path.join(subdirpath, csv_name)
        if path.exists(filepath) and not force_download:
            dataframe = pd.read_csv(filepath)
            dataframe = dataframe.loc[:, ~dataframe.columns.str.startswith('-1')]
        else:
            if self.driver == None:
                self.setupDriver()
                self.setup_fg_login()
            dataframe = self.getDataset(page, 'LeaderBoard1_cmdCSV', filepath, player)
        if player:
            dataframe.set_index("playerid", inplace=True)
            dataframe.index = dataframe.index.astype(str, copy = False)
        return dataframe

    def getProjectionDataset(self, page, csv_name, force_download=False, player=True):
        subdir = f'projection'
        dirname = os.path.dirname(__file__)
        subdirpath = os.path.join(dirname, subdir)
        if not path.exists(subdirpath):
            os.mkdir(subdirpath)
        filepath = os.path.join(subdirpath, csv_name)
        if path.exists(filepath) and not force_download:
            dataframe = pd.read_csv(filepath)
            dataframe = dataframe.loc[:, ~dataframe.columns.str.startswith('-1')]
        else:
            if self.driver == None:
                self.setupDriver()
                self.setup_fg_login()
            dataframe = self.getDataset(page, 'ProjectionBoard1_cmdCSV', filepath)
        if player:
            dataframe.set_index("playerid", inplace=True)
            dataframe.index = dataframe.index.astype(str, copy = False)
        return dataframe

    def setup_fg_login(self):
        self.driver.get("https://blogs.fangraphs.com/wp-login.php")
        cparser = configparser.RawConfigParser()
        cparser.read('fangraphs-config.txt')
        uname = cparser.get('fangraphs-config', 'username')
        pword = cparser.get('fangraphs-config', 'password')
        self.driver.find_element_by_id("user_login").send_keys(uname)
        self.driver.find_element_by_id("user_pass").send_keys(pword)
        self.driver.find_element_by_id("wp-submit").click()

