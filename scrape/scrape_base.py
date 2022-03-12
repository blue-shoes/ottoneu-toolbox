from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import shutil
import pandas as pd
from urllib.parse import unquote, urlparse

class Scrape_Base(object):
    def __init__(self):
        self.driver = None

    def close(self):
        if self.driver != None:
            self.driver.close()

    def getDataset(self, page, element_id, filepath):
        #Click the passed element id to download the csv file
        self.driver.get(page)
        csvJs = self.driver.find_element_by_id(element_id)
        csvJs.click()
        return self.getDatasetFromDownloads(filepath)
        
    
    def getDatasetAtAddress(self, page, filepath):
        """If you can just hit a URL to download the file, use this one"""
        self.driver.get(page)
        return self.getDatasetFromDownloads(filepath)

    def getDatasetFromDownloads(self, filepath):
        #Move to Chrome downloads page and get list of download URLs
        url = self.every_downloads_chrome()
        #Get the latest download path
        download_path = unquote(urlparse(url[0]).path)
        #Move the file to the requested location
        shutil.move(download_path, filepath)
        #Read the file into a DataFrame
        dataframe = pd.read_csv(filepath)
        #Strip -1 columns that can appear for vertical spacers
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
    
    def setupDriver(self):
        self.driver = webdriver.Chrome(ChromeDriverManager().install())