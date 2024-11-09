from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
#from subprocess import CREATE_NO_WINDOW
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from bs4 import BeautifulSoup as Soup

import shutil
import pandas as pd
from pandas import DataFrame
import os
import time
import logging
import requests

from scrape.exceptions import BrowserTypeException

class Scrape_Base(object):
    '''Abstract scraper class'''
    def __init__(self, browser=None):
        self.driver = None
        self.browser = browser
        dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
        self.download_dir = dir = os.path.join(dirname, 'tmp') + '\\'
        if not os.path.exists(dir):
            os.mkdir(dir)
        #clear tmp directory before proceeding
        for f in os.listdir(dir):
            os.remove(os.path.join(dir, f))
        
    def _get_soup(self, url:str, xml:bool=False) -> Soup:
        '''Convenience method to return Soup object from url.'''
        response = requests.get(url)
        if xml:
            return Soup(response.text, 'xml')
        else:
            return Soup(response.text, 'html.parser')

    def close(self) -> None:
        '''Quits the internal driver once it is no longer needed'''
        if self.driver:
            self.driver.quit()

    def getDataset(self, page, element_id, filepath, by_type=By.ID) -> DataFrame:
        '''Navigates on webpage with Selenium to find an click the input element id, waits for download, and then parses and returns the DataFrame.'''
        #Click the passed element id to download the csv file
        self.driver.get(page)
        try:
            wait = WebDriverWait(self.driver, 5)
            #wait.until(EC.presence_of_element_located((by_type, element_id)))
            export_btn = wait.until(EC.element_to_be_clickable((by_type, element_id)))
            action = webdriver.ActionChains(self.driver)
            action.move_to_element(export_btn)
            counter = 0
            while self.download_wait() and counter < 5:
                export_btn = wait.until(EC.element_to_be_clickable((by_type, element_id)))
                export_btn.click()
                counter = counter + 1
            if counter == 5:
                raise TimeoutException('Timeout exception waiting for download')
        except TimeoutException as Argument:
            logging.exception('Timeout exception waiting for csv click')
            return None
        except Exception as Argument:
            logging.exception('Exception getting download')
            return None

        return self.getDatasetFromDownloads(filepath)
        
    
    def getDatasetAtAddress(self, url, filepath) -> DataFrame:
        """Allows download of file separate from Selenium if accessing a URL directly starts download"""
        self.driver.get(url)
        return self.getDatasetFromDownloads(filepath)

    def getDatasetFromDownloads(self, filepath) -> DataFrame:
        '''Accesses file from dowload location, moves it to the input location, reads the csv file, and returns the DataFrame'''
        #Get the latest download path
        download_path = os.path.join(self.download_dir, os.listdir(self.download_dir)[0])
        #Move the file to the requested location
        shutil.move(download_path, filepath)
        #Read the file into a DataFrame
        dataframe = pd.read_csv(filepath)
        #Strip -1 columns that can appear for vertical spacers
        dataframe = dataframe.loc[:, ~dataframe.columns.str.startswith('-1')]
        return dataframe

    def download_wait(self) -> int:
        '''Waits up to 20 seconds while checking if the desired file has been downloaded.'''
        seconds = 0
        dl_wait = True
        while dl_wait and seconds < 5:
            time.sleep(1)
            dl_wait = False
            files = os.listdir(self.download_dir)
            if len(files) != 1:
                dl_wait = True

            for fname in files:
                if fname.endswith('.crdownload'):
                    dl_wait = True

            seconds += 1
        return dl_wait
    
    def setupDriver(self, force_headless:bool=False):
        '''Sets up the driver based on the established browser type. Currently supports Chrome, Firefox, Microsoft Edge.'''
        try:
            from subprocess import CREATE_NO_WINDOW
            flags = CREATE_NO_WINDOW
        except ImportError:
            flags = None
        try:
            if self.browser == 'ChromeHTML':
                options = webdriver.ChromeOptions()
                if force_headless:
                    options.add_argument('--headless')
                prefs = {}
                prefs["profile.default_content_settings.popups"]=0
                prefs["download.default_directory"]=self.download_dir
                options.add_experimental_option("prefs", prefs)
                service = ChromeService()
                if flags:
                    service.creationflags = CREATE_NO_WINDOW
                self.driver = webdriver.Chrome(service=service, options=options)
                self.driver.set_window_size(1920, 1080)
            elif self.browser == 'MSEdgeHTM':
                options = webdriver.EdgeOptions()
                if force_headless:
                    options.add_argument('--headless')
                options.add_experimental_option('prefs', {
                    "download.default_directory": self.download_dir,
                    "download.prompt_for_download": False})
                service = EdgeService()
                if flags:
                    service.creationflags = CREATE_NO_WINDOW
                self.driver = webdriver.Edge(service=service, options=options)
            elif self.browser is not None and 'FirefoxURL' in self.browser:
                options = webdriver.FirefoxOptions()
                options.add_argument('--headless')
                options.set_preference("browser.download.folderList", 2)
                options.set_preference("browser.download.manager.showWhenStarting", False)
                options.set_preference("browser.download.dir", self.download_dir)
                options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/x-gzip")
                service = FirefoxService(log_path='logs/geckodriver.log')
                if flags:
                    service.creationflags = CREATE_NO_WINDOW
                self.driver = webdriver.Firefox(service=service, options=options)
            else:
                raise BrowserTypeException('Unknown browser type. Please use Chrome, Firefox, or Microsoft Edge')
        except WebDriverException:
            raise BrowserTypeException('Issue creating browser type. Please select a different browser in Preferences.')
        