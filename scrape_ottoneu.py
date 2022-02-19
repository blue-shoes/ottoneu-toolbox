from bs4 import BeautifulSoup as Soup
import pandas as pd
import requests
from pandas import DataFrame

def getPlayerPositionsDfSoup():
    avg_values_url = 'https://ottoneu.fangraphs.com/averageValues'
    response = requests.get(avg_values_url)
    avg_val_soup = Soup(response.text, 'html.parser')
    table = avg_val_soup.find_all('table')[0]
    rows = table.find_all('tr')
    parsed_rows = [parse_row(row) for row in rows[1:]]
    print(rows[1])
    print(parsed_rows[0])
    df = DataFrame(parsed_rows)
    df.columns = parse_header(rows[0])
    return df

def parse_row(row):
    tds = row.find_all('td')
    parsed_row = []
    for td in tds:
        if len(list(td.children)) > 1:
            parsed_row.append(str(td.contents[0]).strip())
        else:
            parsed_row.append(td.string)
    return parsed_row

def parse_header(row):
    return [str(x.string) for x in row.find_all('th')]


df = getPlayerPositionsDfSoup()
print(df.head())