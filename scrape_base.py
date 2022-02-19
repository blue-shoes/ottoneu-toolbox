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
        self.driver.get(page)
        csvJs = self.driver.find_element_by_id(element_id)
        csvJs.click()
        return self.getDatasetFromDownloads(filepath)
        
    
    def getDatasetAtAddress(self, page, filepath):
        """If you can just hit a URL to download the file, use this one"""
        self.driver.get(page)
        return self.getDatasetFromDownloads(filepath)

    def getDatasetFromDownloads(self, filepath):
        url = self.every_downloads_chrome()
        download_path = unquote(urlparse(url[0]).path)
        shutil.move(download_path, filepath)
        dataframe = pd.read_csv(filepath)
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