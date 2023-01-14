from winreg import *
import configparser
import os

from domain.enum import Preference as Pref, Browsers

def get_desired_browser():
    preferences = configparser.ConfigParser()
    config_path = 'conf/otb.conf'
    if os.path.exists(config_path):
        preferences.read(config_path)
    browser_pref = preferences.get('Player_Values', Pref.DEFAULT_BROWSER, fallback=None)
    if browser_pref is None:
        with OpenKey(HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\http\\UserChoice") as key:
            browser_pref = QueryValueEx(key, 'Progid')[0]
    if 'Firefox' in browser_pref:
        return Browsers.FIREFOX
    if browser_pref == 'ChromeHTML':
        return Browsers.CHROME
    if browser_pref == 'MSEdgeHTM':
        return Browsers.EDGE
    raise Exception('Unknown browser type. Please use Chrome, Firefox, or Microsoft Edge')

    
