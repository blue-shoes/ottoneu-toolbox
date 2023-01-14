from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from winreg import *
import shutil
import pandas as pd
import os
import time

class Scrape_Base(object):
    def __init__(self):
        self.driver = None
        dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
        self.download_dir = dir = os.path.join(dirname, 'tmp')
        if not os.path.exists(dir):
            os.mkdir(dir)
        #clear tmp directory before proceeding
        for f in os.listdir(dir):
            os.remove(os.path.join(dir, f))
        

    def close(self):
        if self.driver != None:
            self.driver.quit()

    def getDataset(self, page, element_id, filepath, by_type=By.ID):
        #Click the passed element id to download the csv file
        self.driver.get(page)
        csvJs = self.driver.find_element(by_type, element_id)
        csvJs.click()
        self.download_wait()
        return self.getDatasetFromDownloads(filepath)
        
    
    def getDatasetAtAddress(self, page, filepath):
        """If you can just hit a URL to download the file, use this one"""
        self.driver.get(page)
        return self.getDatasetFromDownloads(filepath)

    def getDatasetFromDownloads(self, filepath):
        #Move to Chrome downloads page and get list of download URLs
        #This doesn't work for headless clients. Need to create your own downloads dir
        #url = self.every_downloads_chrome()
        #Get the latest download path
        download_path = os.path.join(self.download_dir, os.listdir(self.download_dir)[0])
        #Move the file to the requested location
        shutil.move(download_path, filepath)
        #Read the file into a DataFrame
        dataframe = pd.read_csv(filepath)
        #Strip -1 columns that can appear for vertical spacers
        dataframe = dataframe.loc[:, ~dataframe.columns.str.startswith('-1')]
        return dataframe

    def download_wait(self):
        seconds = 0
        dl_wait = True
        while dl_wait and seconds < 20:
            time.sleep(1)
            dl_wait = False
            files = os.listdir(self.download_dir)
            if len(files) != 1:
                dl_wait = True

            for fname in files:
                if fname.endswith('.crdownload'):
                    dl_wait = True

            seconds += 1
        return seconds
    
    def every_downloads_chrome(self):
        if not self.driver.current_url.startswith("chrome://downloads"):
            self.driver.get("chrome://downloads/")
        return self.driver.execute_script("""
            return document.querySelector('downloads-manager')
            .shadowRoot.querySelector('#downloadsList')
            .items.filter(e => e.state === 'COMPLETE')
            .map(e => e.filePath || e.file_path || e.fileUrl || e.file_url);
            """)
    
    def setupDriver(self):
        
        with OpenKey(HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\http\\UserChoice") as key:
            browser = QueryValueEx(key, 'Progid')[0]
        print(f'browser = {browser}')
        if browser == 'ChromeHTML':
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            prefs = {}
            prefs["profile.default_content_settings.popups"]=0
            prefs["download.default_directory"]=self.download_dir
            options.add_experimental_option("prefs", prefs)
            self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
        elif browser == 'MSEdgeHTM':
            options = webdriver.EdgeOptions()
            options.add_argument('--headless')
            options.add_experimental_option('prefs', {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False})
            self.driver = webdriver.Edge(executable_path=EdgeChromiumDriverManager().install(), options=options)
        elif 'FirefoxURL' in browser:
            options = webdriver.FirefoxOptions()
            options.add_argument('--headless')
            options.set_preference("browser.download.folderList", 2)
            options.set_preference("browser.download.manager.showWhenStarting", False)
            options.set_preference("browser.download.dir", self.download_dir)
            options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/x-gzip")
            self.driver = webdriver.Firefox(executable_path=GeckoDriverManager().install(), options=options, service_log_path='logs/geckodriver.log')

        