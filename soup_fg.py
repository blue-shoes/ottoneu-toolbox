from bs4 import BeautifulSoup as Soup
import pandas as pd
import requests
from pandas import DataFrame

URL_2021 = "https://www.fangraphs.com/leaders.aspx?pos=np&stats=bat&lg=all&qual=0&type=8&season=2021&month=0&season1=2021&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=2021-01-01&enddate=2021-12-31&page=1_1000"
URL_2021_short = "https://www.fangraphs.com/leaders.aspx?pos=np&stats=bat&lg=all&qual=0&type=8&season=2021&month=0&season1=2021&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=2021-01-01&enddate=2021-12-31&page=1_4"

stat_response = requests.get(URL_2021)
short_stat_response = requests.get(URL_2021_short)
print(short_stat_response.text)
short_soup = Soup(short_stat_response.text)
div = short_soup.find("LeaderBoard1_dg1")
len(tables)
print(div)