
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import configparser
import os
from os import path
import shutil
import pandas as pd
from urllib.parse import unquote, urlparse

class Scrape_Fg:

    def __init__(self):
        self.driver = None

    def close(self):
        if self.driver != None:
            self.driver.close()

    def getLeaderboardDataset(self, page, csv_name, force_download=False, player=True):
        subdir = f'leaderboard'
        dirname = os.path.dirname(__file__)
        subdirpath = os.path.join(dirname, subdir)
        if not path.exists(subdirpath):
            os.mkdir(subdirpath)
        filepath = os.path.join(subdirpath, csv_name)
        if path.exists(filepath) and not force_download:
            dataframe = pd.read_csv(filepath)
            if player:
                dataframe.set_index("playerid", inplace=True)
                dataframe.index = dataframe.index.astype(str, copy = False)
            return dataframe
        else:
            if self.driver == None:
                self.setupDriver()
                self.setup_fg_login()
            return self.getDataset(page, 'LeaderBoard1_cmdCSV', filepath, player)

    def getProjectionDataset(self, page, csv_name, force_download=False, player=True):
        subdir = f'projection'
        dirname = os.path.dirname(__file__)
        subdirpath = os.path.join(dirname, subdir)
        if not path.exists(subdirpath):
            os.mkdir(subdirpath)
        filepath = os.path.join(subdirpath, csv_name)
        if path.exists(filepath) and not force_download:
            print('not forced')
            dataframe = pd.read_csv(filepath)
            if player:
                dataframe.set_index("playerid", inplace=True)
                dataframe.index = dataframe.index.astype(str, copy = False)
            dataframe = dataframe.loc[:, ~dataframe.columns.str.startswith('-1')]
            return dataframe
        else:
            if self.driver == None:
                self.setupDriver()
                self.setup_fg_login()
            return self.getDataset(page, 'ProjectionBoard1_cmdCSV', filepath)

    def getDataset(self, page, element_id, filepath, player=True):
        self.driver.get(page)
        csvJs = self.driver.find_element_by_id(element_id)
        csvJs.click()
        url = self.every_downloads_chrome()
        download_path = unquote(urlparse(url[0]).path)
        shutil.move(download_path, filepath)
        dataframe = pd.read_csv(filepath)
        if(player):
            dataframe.set_index("playerid", inplace=True)
            dataframe.index = dataframe.index.astype(str, copy = False)
        dataframe = dataframe.loc[:, ~dataframe.columns.str.startswith('-1')]
        return dataframe

    def every_downloads_chrome(self):
        if not self.driver.current_url.startswith("chrome://downloads"):
            self.driver.get("chrome://downloads/")
        return self.driver.execute_script("""
            return document.querySelector('downloads-manager')
            .shadowRoot.querySelector('#downloadsList')
            .items.filter(e => e.state === 'COMPLETE')
            .map(e => e.filePath || e.file_path || e.fileUrl || e.file_url);
            """)

    def setup_fg_login(self):
        self.driver.get("https://blogs.fangraphs.com/wp-login.php")
        cparser = configparser.RawConfigParser()
        cparser.read('fangraphs-config.txt')
        uname = cparser.get('fangraphs-config', 'username')
        pword = cparser.get('fangraphs-config', 'password')
        self.driver.find_element_by_id("user_login").send_keys(uname)
        self.driver.find_element_by_id("user_pass").send_keys(pword)
        self.driver.find_element_by_id("wp-submit").click()

    def setupDriver(self):
        self.driver = webdriver.Chrome(ChromeDriverManager().install())
        #webdriver.ChromeOptions().add_argument("user-data-dir=C:\\Users\\adam.scharf\\AppData\\Local\\Google\\Chrome\\User Data\\Default")

