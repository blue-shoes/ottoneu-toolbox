
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import configparser
import os
from os import path
import shutil
import pandas as pd
from urllib.parse import unquote, urlparse

def getLeaderboardDataset(driver, page, csv_name, force_download=False, player=True):
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
        if driver.current_url == 'data:,':
            setup_fg_login(driver)
        return getDataset(driver, page, 'LeaderBoard1_cmdCSV', filepath, player)

def getProjectionDataset(driver, page, csv_name, force_download=False, player=True):
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
        return dataframe
    else:
        if driver.current_url == 'data:,':
            setup_fg_login(driver)
        return getDataset(driver, page, 'ProjectionBoard1_cmdCSV', filepath)

def getDataset(driver, page, element_id, filepath, player=True):
    driver.get(page)
    csvJs = driver.find_element_by_id(element_id)
    csvJs.click()
    url = every_downloads_chrome(driver)
    download_path = unquote(urlparse(url[0]).path)
    shutil.move(download_path, filepath)
    dataframe = pd.read_csv(filepath)
    if(player):
        dataframe.set_index("playerid", inplace=True)
        dataframe.index = dataframe.index.astype(str, copy = False)
    return dataframe

def every_downloads_chrome(driver):
    if not driver.current_url.startswith("chrome://downloads"):
        driver.get("chrome://downloads/")
    return driver.execute_script("""
        return document.querySelector('downloads-manager')
        .shadowRoot.querySelector('#downloadsList')
        .items.filter(e => e.state === 'COMPLETE')
        .map(e => e.filePath || e.file_path || e.fileUrl || e.file_url);
        """)

def setup_fg_login(driver):
    driver.get("https://blogs.fangraphs.com/wp-login.php")
    cparser = configparser.RawConfigParser()
    cparser.read('fangraphs-config.txt')
    uname = cparser.get('fangraphs-config', 'username')
    pword = cparser.get('fangraphs-config', 'password')
    driver.find_element_by_id("user_login").send_keys(uname)
    driver.find_element_by_id("user_pass").send_keys(pword)
    driver.find_element_by_id("wp-submit").click()

def setupDriver():
    driver = webdriver.Chrome(ChromeDriverManager().install())
    #webdriver.ChromeOptions().add_argument("user-data-dir=C:\\Users\\adam.scharf\\AppData\\Local\\Google\\Chrome\\User Data\\Default")
    return driver

