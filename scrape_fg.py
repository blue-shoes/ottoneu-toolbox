
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
import pyvirtualdisplay
import configparser
import os
from os import path
import shutil
import pandas as pd
from urllib.parse import unquote, urlparse

def getLeaderboardDataset(driver, page, csv_name):
    subdir = f'leaderboard'
    dirname = os.path.dirname(__file__)
    subdirpath = os.path.join(dirname, subdir)
    if not path.exists(subdirpath):
        os.mkdir(subdirpath)
    filepath = os.path.join(subdirpath, csv_name)
    if path.exists(filepath):
        return pd.read_csv(filepath)
    else:
        if driver.current_url == 'data:,':
            setup_fg_login(driver)
        return getDataset(driver, page, 'LeaderBoard1_cmdCSV', filepath)

def getProjectionDataset(driver, page, csv_name):
    subdir = f'projection'
    dirname = os.path.dirname(__file__)
    subdirpath = os.path.join(dirname, subdir)
    if not path.exists(subdirpath):
        os.mkdir(subdirpath)
    filepath = os.path.join(subdirpath, csv_name)
    if path.exists(filepath):
        return pd.read_csv(filepath)
    else:
        if driver.current_url == 'data:,':
            setup_fg_login(driver)
        return getDataset(driver, page, 'ProjectionBoard1_cmdCSV', filepath)

def getDataset(driver, page, element_id, filepath):
    driver.get(page)
    csvJs = driver.find_element_by_id(element_id)
    csvJs.click()
    url = every_downloads_chrome(driver)
    download_path = unquote(urlparse(url[0]).path)
    #Need to add the [1:] annotation to get rid of leading / character in path
    download_path = download_path[1:]
    shutil.move(download_path, filepath)
    dataframe = pd.read_csv(filepath)
    dataframe.set_index("playerid")
    return dataframe

def every_downloads_chrome(driver):
    if not driver.current_url.startswith("chrome://downloads"):
        driver.get("chrome://downloads/")
    return driver.execute_script("""
        var items = downloads.Manager.get().items_;
        if (items.every(e => e.state === "COMPLETE"))
            return items.map(e => e.fileUrl || e.file_url);
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
    driver = webdriver.Chrome()
    return driver

