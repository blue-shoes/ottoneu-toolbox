#from winreg import *
import configparser
import os
import importlib

from domain.enum import Preference as Pref, Browser
from scrape.exceptions import BrowserTypeException

def get_desired_browser() -> Browser:
    '''Determine browser type to use. Checks the conf/otb.conf file for a set browser type first. If the file is not present or it does not have a default browser
    parameter, checks the application associated with UrlAssociations from registery to determine system default browser and returns that. Currently only allows
    Chrome, Firefox, or Microsoft Edge.'''
    preferences = configparser.ConfigParser()
    config_path = 'conf/otb.conf'
    if os.path.exists(config_path):
        preferences.read(config_path)
    browser_pref = preferences.get('Player_Values', Pref.DEFAULT_BROWSER, fallback=None)
    if browser_pref is None:
        if not importlib.util.find_spec('winreg'):
            raise BrowserTypeException('No browser type selected in Preferences. Please use Chrome, Firefox, or Microsoft Edge')        
        
        from winreg import HKEY_CURRENT_USER, OpenKey, QueryValueEx
        with OpenKey(HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\http\\UserChoice") as key:
            browser_pref = QueryValueEx(key, 'Progid')[0]
    if 'Firefox' in browser_pref:
        return Browser.FIREFOX
    if browser_pref == 'ChromeHTML':
        return Browser.CHROME
    if browser_pref == 'MSEdgeHTM':
        return Browser.EDGE
    raise BrowserTypeException('Unknown browser type. Please use Chrome, Firefox, or Microsoft Edge')

    
