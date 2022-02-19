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
    
    def setupDriver(self):
        self.driver = webdriver.Chrome(ChromeDriverManager().install())