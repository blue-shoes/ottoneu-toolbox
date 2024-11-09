import configparser
import os
from os import path
from pandas import DataFrame
from scrape import scrape_base
from scrape.exceptions import FangraphsException
from selenium.webdriver.common.by import By
import keyring

class Scrape_Fg(scrape_base.Scrape_Base):
    '''Implementation of Scrape_Base class for scraping information from FanGraphs website.'''

    def __init__(self, browser):
        super().__init__(browser)
        if not os.path.exists('data_dirs'):
            os.mkdir('data_dirs')


    def getLeaderboardDataset(self, page, csv_name, player=True) -> DataFrame:
        '''Retrieves player leaderboard data at url from FanGraphs using Selenium and returns as a DataFrame'''
        #Create filepath info
        subdir = 'data_dirs/leaderboard'
        dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
        subdirpath = os.path.join(dirname, subdir)
        if not path.exists(subdirpath):
            os.mkdir(subdirpath)
        filepath = os.path.join(subdirpath, csv_name)
        #If we haven't used the web yet, initialize the driver
        if not self.driver:
            self.setupDriver()
        #Use driver to get dataset
        dataframe = self.getDataset(page, 'LeaderBoard1_cmdCSV', filepath, player)
        #If the dataset is player based (not league based), reindex to the FG player id
        if player:
            dataframe.set_index("playerid", inplace=True)
            dataframe.index = dataframe.index.astype(str, copy = False)
        return dataframe

    def getProjectionDataset(self, url, csv_name, player=True) -> DataFrame:
        '''Retrieves projection at url from FanGraphs using Selenium and returns as DataFrame.'''
        #Create filepath info
        subdir = 'tmp'
        if not path.exists(subdir):
            os.mkdir(subdir)
        filepath = os.path.join(subdir, csv_name)
        #If we haven't used the web yet, initialize the driver
        if not self.driver:
            self.setupDriver()
        #Use driver to get dataset
        dataframe = self.getDataset(url, 'Export Data', filepath, by_type=By.LINK_TEXT)
        os.remove(filepath)
        #If the dataset is player based (not league based), reindex to the FG player id
        if player:
            dataframe.drop_duplicates('PlayerId', inplace=True)
            dataframe.set_index("PlayerId", inplace=True)
            dataframe.index = dataframe.index.astype(str, copy = False)
        if len(dataframe) == 0:
            raise FangraphsException('Projection does not exist')
        return dataframe

    def setup_fg_login(self) -> None:
        '''Logs user in to FanGraphs using stored credentials. Required for Projection download.'''
        if not os.path.exists('conf/fangraphs.conf'):
            return
        cparser = configparser.RawConfigParser()
        cparser.read('conf/fangraphs.conf')
        uname = cparser.get('fangraphs-config', 'username', fallback=None)
        pword = keyring.get_password('ottoneu-draft-tool', uname)
        if uname is None or pword is None:
            raise FangraphsException('Missing username and/or password')
        self.driver.get("https://blogs.fangraphs.com/wp-login.php")
        self.driver.find_element(By.ID, "user_login").send_keys(uname)
        self.driver.find_element(By.ID, "user_pass").send_keys(pword)
        self.driver.find_element(By.ID, "wp-submit").click()

    def setupDriver(self) -> None:
        '''Creates the Selenium driver for the scraping event. Logs in to FanGraphs if conf/fangraphs.conf present.'''
        driver = super().setupDriver()
        self.setup_fg_login()
        return driver

