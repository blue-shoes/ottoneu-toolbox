import configparser
import os
from os import path
import pandas as pd
from scrape import scrape_base
import requests

class Scrape_Fg(scrape_base.Scrape_Base):

    def __init__(self):
        super().__init__()
        if not os.path.exists('data_dirs'):
            os.mkdir('data_dirs')


    def getLeaderboardDataset(self, page, csv_name, force_download=False, player=True):
        #Create filepath info
        subdir = 'data_dirs/leaderboard'
        dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
        subdirpath = os.path.join(dirname, subdir)
        if not path.exists(subdirpath):
            os.mkdir(subdirpath)
        filepath = os.path.join(subdirpath, csv_name)
        #If we have the file and didn't request a redownload, just load what we have
        if path.exists(filepath) and not force_download:
            dataframe = pd.read_csv(filepath)
            dataframe = dataframe.loc[:, ~dataframe.columns.str.startswith('-1')]
        else:
            #If we haven't used the web yet, initialize the driver
            if self.driver == None:
                self.setupDriver()
                self.setup_fg_login()
            #Use driver to get dataset
            dataframe = self.getDataset(page, 'LeaderBoard1_cmdCSV', filepath, player)
        #If the dataset is player based (not league based), reindex to the FG player id
        if player:
            dataframe.set_index("playerid", inplace=True)
            dataframe.index = dataframe.index.astype(str, copy = False)
        return dataframe

    def getProjectionDataset(self, page, csv_name, force_download=False, player=True):
        #Create filepath info
        subdir = 'data_dirs/projection'
        dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
        subdirpath = os.path.join(dirname, subdir)
        if not path.exists(subdirpath):
            os.mkdir(subdirpath)
        filepath = os.path.join(subdirpath, csv_name)
        #If we have the file and didn't request a redownload, just load what we have
        if path.exists(filepath) and not force_download:
            dataframe = pd.read_csv(filepath)
            dataframe = dataframe.loc[:, ~dataframe.columns.str.startswith('-1')]
        else:
            #If we haven't used the web yet, initialize the driver
            if self.driver == None:
                self.setupDriver()
                self.setup_fg_login()
            #Use driver to get dataset
            dataframe = self.getDataset(page, 'ProjectionBoard1_cmdCSV', filepath)
        #If the dataset is player based (not league based), reindex to the FG player id
        if player:
            dataframe.set_index("playerid", inplace=True)
            dataframe.index = dataframe.index.astype(str, copy = False)
        return dataframe

    def setup_fg_login(self):
        #FG login to get rid of ads
        self.driver.get("https://blogs.fangraphs.com/wp-login.php")
        cparser = configparser.RawConfigParser()
        cparser.read('conf/fangraphs-config.txt')
        uname = cparser.get('fangraphs-config', 'username')
        pword = cparser.get('fangraphs-config', 'password')
        self.driver.find_element_by_id("user_login").send_keys(uname)
        self.driver.find_element_by_id("user_pass").send_keys(pword)
        self.driver.find_element_by_id("wp-submit").click()

    def setupDriver(self):
        driver = super().setupDriver()
        if os.path.exists('conf/fangraphs-config.txt'):
            self.setup_fg_login()
        return driver

    def test(self):
        import datetime
        import urllib.request
        from bs4 import BeautifulSoup as Soup
        from selenium import webdriver
        from webdriver_manager.chrome import ChromeDriverManager
        votto_url = f'https://www.fangraphs.com/players/joey-votto/4314/stats'
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
        driver.get("https://blogs.fangraphs.com/wp-login.php")
        cparser = configparser.RawConfigParser()
        cparser.read('conf/fangraphs-config.txt')
        uname = cparser.get('fangraphs-config', 'username')
        pword = cparser.get('fangraphs-config', 'password')
        driver.find_element_by_id("user_login").send_keys(uname)
        driver.find_element_by_id("user_pass").send_keys(pword)
        driver.find_element_by_id("wp-submit").click()
        start = datetime.datetime.now()
        driver.get(votto_url)
        print(f'load time was {datetime.datetime.now() - start}')
        stat_soup = Soup(driver.page_source, 'html.parser')
        tables = stat_soup.find_all('table')
        print(len(tables))
        #print(tables[7])

#scraper = Scrape_Fg()
#scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type=steamer&team=0&lg=all&players=0", 'steamer_pos.csv', True)

