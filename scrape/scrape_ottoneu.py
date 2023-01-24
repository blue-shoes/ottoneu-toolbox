from bs4 import BeautifulSoup as Soup
import pandas as pd
import requests
from pandas import DataFrame
import os
from os import path
from io import StringIO
import datetime
from decimal import Decimal
from re import sub

from scrape import scrape_base
from scrape.exceptions import OttoneuException

class Scrape_Ottoneu(scrape_base.Scrape_Base):

    def get_soup(self, url, xml=False):
        response = requests.get(url)
        if xml:
            return Soup(response.text, 'xml')
        else:
            return Soup(response.text, 'html.parser')

    def __init__(self, browser=None):
        super().__init__(browser)
        #Initialize directory for output calc files if required
        self.dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
        dir_path = os.path.join(self.dirname, 'data_dirs')
        if not path.exists(dir_path):
            os.mkdir(dir_path)
        self.subdirpath = os.path.join(self.dirname, 'data_dirs', 'output')
        if not path.exists(self.subdirpath):
            os.mkdir(self.subdirpath)

    def getPlayerPositionsDfSoup(self):
        avg_values_url = 'https://ottoneu.fangraphs.com/averageValues'
        #response = requests.get(avg_values_url)
        #avg_val_soup = Soup(response.text, 'html.parser')
        avg_val_soup = self.get_soup(avg_values_url)
        table = avg_val_soup.find_all('table')[0]
        rows = table.find_all('tr')
        parsed_rows = [self.parse_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = self.parse_header(rows[0])
        return df

    def parse_row(self, row):
        tds = row.find_all('td')
        parsed_row = []
        for td in tds:
            if len(list(td.children)) > 1:
                parsed_row.append(str(td.contents[0]).strip())
            else:
                parsed_row.append(td.string)
        return parsed_row

    def parse_header(self, row):
        return [str(x.string) for x in row.find_all('th')]
    
    def get_avg_salary_ds(self, game_type : int = None) -> DataFrame:
        '''Scrapes the average salary page for the given game type (default all game types) and returns a DataFrame with the available data. Index is Ottoneu Id'''
        if game_type is None or game_type == 0:
            avg_salary_url = 'https://ottoneu.fangraphs.com/averageValues?export=xml'
        else:
            avg_salary_url = f'https://ottoneu.fangraphs.com/averageValues?export=xml&gameType={game_type.value}'
        #response = requests.get(avg_salary_url)
        #salary_soup = Soup(response.text, 'xml')
        salary_soup = self.get_soup(avg_salary_url, True)
        rows = salary_soup.find_all('player')
        parsed_rows = [self.parse_avg_salary_row(row) for row in rows]
        df = DataFrame(parsed_rows)
        df.columns = ['Ottoneu ID','Name','FG MajorLeagueID','FG MinorLeagueID','Avg Salary','Min Salary','Max Salary','Median Salary','Last 10','Roster %','Position(s)','Org']
        df.set_index('Ottoneu ID', inplace=True)
        df.index = df.index.astype(int, copy=False)
        return df

    def parse_avg_salary_row(self, row):
        parsed_row = []
        parsed_row.append(row.get('ottoneu_id'))
        parsed_row.append(row.get('name'))
        parsed_row.append(str(row.get('fg_majorleague_id')))
        parsed_row.append(row.get('fg_minorleague_id'))
        parsed_row.append(row.find('avg_salary').text)
        parsed_row.append(row.find('min_salary').text)
        parsed_row.append(row.find('max_salary').text)
        parsed_row.append(row.find('median_salary').text)
        parsed_row.append(row.find('last_10').text)
        parsed_row.append(row.find('rostered_pct').text)
        parsed_row.append(row.find('positions').text)
        parsed_row.append(row.find('mlb_org').text)
        return parsed_row


    def get_player_position_ds(self, force_download=False):
        subdir = 'data_dirs/projection'
        subdirpath = os.path.join(self.dirname, subdir)
        filepath = os.path.join(subdirpath, "ottoneu_positions.csv")
        if path.exists(filepath) and not force_download:
            df = pd.read_csv(filepath)
        else:
            if self.driver == None:
                self.setupDriver()
            df = self.getDatasetAtAddress('https://ottoneu.fangraphs.com/averageValues?export=csv', filepath)
        df['playerid'] = df['FG MinorLeagueID']
        df['FG MajorLeagueID'] = df['FG MajorLeagueID'].fillna(-1)
        df['FG MajorLeagueID'] = df['FG MajorLeagueID'].astype(int)
        df.loc[df['FG MajorLeagueID'] != -1, 'playerid'] = df['FG MajorLeagueID']
        df.set_index("playerid", inplace=True)
        df.index = df.index.astype(str, copy = False)
        return df    

    def parse_prod_row(self, row):
        tds = row.find_all('td')
        parsed_row = []
        for td in tds:
            parsed_row.append(td.string)
        return parsed_row

    def scrape_roster_export(self, lg_id):
        roster_export_url = f'https://ottoneu.fangraphs.com/{lg_id}/rosterexport'
        #response = requests.get(roster_export_url)
        #rost_soup = Soup(response.text, 'html.parser')
        rost_soup = self.get_soup(roster_export_url)
        df = pd.read_csv(StringIO(rost_soup.contents[0]))
        df.set_index("ottoneu ID", inplace=True)
        df.index = df.index.astype(str, copy = False)
        return df
    
    def parse_trans_row(self, row):
        tds = row.find_all('td')
        parsed_row = []
        #url in form of *id=playerid
        playerid = tds[2].find('a').get('href').split('=')[1]
        parsed_row.append(playerid)
        #url in form of *team=teamid
        teamid = tds[3].find('a').get('href').split('=')[1]
        parsed_row.append(teamid)
        required_tds = [2,3,5]
        for ind in required_tds:
            td = tds[ind]
            if td.find('a') != None:
                parsed_row.append(td.find('a').string)
            else:
                parsed_row.append(td.string.strip())
        return parsed_row

    def scrape_transaction_page(self, lg_id):
        transactions_url = f'https://ottoneu.fangraphs.com/{lg_id}/transactions'
        #response = requests.get(transactions_url)
        #trans_soup = Soup(response.text, 'html.parser')
        trans_soup = self.get_soup(transactions_url)
        table = trans_soup.find_all('table')[0]
        rows = table.find_all('tr')
        parsed_rows = [self.parse_trans_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = ['Ottoneu ID','Team ID','Name','Team','Salary']
        df.set_index('Ottoneu ID', inplace=True)
        return df

    def scrape_recent_trans_api(self, lg_id):
        rec_trans_url = f'https://ottoneu.fangraphs.com/api/recent_transactions?leagueID={lg_id}'
        trans_soup = self.get_soup(rec_trans_url, True)
        if trans_soup.find('transactions') is None:
            raise OttoneuException('League Inactive')
        rows = trans_soup.find_all('transaction')
        parsed_rows = [self.parse_rec_trans_row(row) for row in rows]
        if len(parsed_rows) == 0:
            return DataFrame()
        df = DataFrame(parsed_rows)
        df.columns = ['Ottoneu ID','Team ID','Date','Salary','Type']
        df = df.astype({'Ottoneu ID': 'str'})
        return df

    def parse_rec_trans_row(self, row):
        player = row.find('player')
        parsed_row = []
        parsed_row.append(int(player.get('id')))
        team = row.find('team')
        parsed_row.append(int(team.get('id')))
        parsed_row.append(datetime.datetime.strptime(row.find('date').text, '%Y-%m-%d %H:%M:%S'))
        parsed_row.append(row.find('salary').text)
        parsed_row.append(row.find('transaction_type').text)
        return parsed_row

    def scrape_team_production_page(self, lg_id, team_id):
        dfs = []
        prod_url = f'https://ottoneu.fangraphs.com/{lg_id}/teamproduction?teamID={team_id}'
        #response = requests.get(prod_url)
        #prod_soup = Soup(response.text, 'html.parser')
        prod_soup = self.get_soup(prod_url)
        sections = prod_soup.find_all('section')
        pos_df = self.parse_prod_table(sections[0])
        if pos_df.empty:
            return None
        dfs.append(pos_df)
        dfs.append(self.parse_prod_table(sections[1]))
        return dfs
    
    def parse_prod_table(self, section):
        table = section.find_all('table')[0]
        rows = table.find_all('tr')
        if len(rows) == 1:
            #Empty production page. Skip league
            return DataFrame()
        parsed_rows = [self.parse_prod_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = self.parse_header(rows[0])
        df.set_index("POS", inplace=True)
        return df
    
    def scrape_league_production_pages(self, lg_id):
        prod_url = f'https://ottoneu.fangraphs.com/{lg_id}/teamproduction'
        #response = requests.get(prod_url)
        #prod_soup = Soup(response.text, 'html.parser')
        prod_soup = self.get_soup(prod_url)
        select = prod_soup.find_all('select')[0]
        team_opts = select.find_all('option')
        league_bat = []
        league_arm = []
        for team_opt in team_opts:
            id = team_opt['value']
            if id != '-1':
                dfs = self.scrape_team_production_page(lg_id, team_opt['value'])
                if dfs == None:
                    return []
                league_bat.append(dfs[0])
                league_arm.append(dfs[1])
        bat_df = pd.concat(league_bat)
        arm_df = pd.concat(league_arm)
        return [bat_df, arm_df]
        
    
    def parse_leagues_row(self, row):
        tds = row.find_all('td')
        parsed_row = []
        #url in form of /id/home
        val = tds[0].find('a').get('href').split('/')[1]
        parsed_row.append(val)
        for td in tds:
            if len(list(td.children)) > 1:
                parsed_row.append(str(td.contents[0]).strip())
                print('children > 1')
            else:
                parsed_row.append(td.string)
        return parsed_row

    def parse_leagues_header(self, row):
        cols = []
        cols.append('League Id')
        reg_cols = [str(x.string) for x in row.find_all('th')]
        for col in reg_cols:
            cols.append(col)
        return cols

    def scrape_league_table(self):
        url = 'https://ottoneu.fangraphs.com/browseleagues'

        self.setupDriver()
        self.driver.get(url)
        html = self.driver.page_source
        self.driver.quit()
        browse_soup = Soup(html, 'html.parser')
        table = browse_soup.find_all('table')[0]
        rows = table.find_all('tr')
        parsed_rows = [self.parse_leagues_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = self.parse_leagues_header(rows[0])
        df.set_index("League Id", inplace=True)
        return df

    def get_universe_production_tables(self, limit=1e6):
        leagues = self.scrape_league_table()
        bat_dict = {}
        arm_dict = {}
        formats = []
        count = 0
        for lg_id, row in leagues.iterrows():
            if row['Game Type'] not in formats:
                formats.append(row['Game Type'])
            print(f'Scraping league {lg_id}, name {row["League Name"]}, format {row["Game Type"]}')
            dfs = self.scrape_league_production_pages(lg_id)
            if len(dfs) == 0:
                #League has no production values
                continue
            bat_dict[lg_id] = dfs[0]
            arm_dict[lg_id] = dfs[1]
            count += 1
            if count > limit:
                break

        for format in formats:
            filepath = os.path.join(self.subdirpath, f'{format}_prod.xlsx')
            with pd.ExcelWriter(filepath) as writer:
                for lg_id, row in leagues.iterrows():
                    if lg_id in bat_dict:
                        if row['Game Type'] == format:
                            bat_dict[lg_id].to_excel(writer, sheet_name=f'{lg_id}_bat')
                            arm_dict[lg_id].to_excel(writer, sheet_name=f'{lg_id}_arm')

    def scrape_league_info_page(self, lg_id):
        lg_data = {}
        lg_data['ID'] = lg_id
        url = f'https://ottoneu.fangraphs.com/{lg_id}/settings'
        info_soup = self.get_soup(url)
        body = info_soup.find_all('body')[0]
        lg_data['Name'] = body.find_all('h1')[1].string
        tbody = info_soup.find_all('tbody')[0]
        lg_data['Num Teams'] = tbody.find_all('tr')[3].find_all('td')[1].string
        lg_data['Format'] = tbody.find_all('tr')[6].find_all('td')[1].find('a').string
        return lg_data
    
    def scrape_finances_page(self, lg_id):
        url = f'https://ottoneu.fangraphs.com/{lg_id}/tools'
        fin_soup = self.get_soup(url)
        fin_tbl_rows = fin_soup.find(id='finances').find_all('tbody')[0].find_all('tr')
        depth_tbl_rows = fin_soup.find_all('table')[1].find_all('tbody')[0].find_all('tr')
        team_rows = [self.parse_finance_rows(row, depth_tbl_rows) for row in fin_tbl_rows[:]]
        fin_df = DataFrame(team_rows)
        fin_df.columns = ['ID', 'Name','Players','Spots','Base Salaries','Cap Penalties','Loans In','Loans Out','Cap Space','C Depth','1B Depth','2B Depth','SS Depth', '3B Depth', 'OF Depth','Util Depth','SP Depth','RP Depth']
        fin_df.set_index("ID", inplace=True)
        fin_df.index = fin_df.index.astype(int, copy = False)
        return fin_df

    def parse_finance_rows(self, fin_row, depth_tbl_rows):
        tds = fin_row.find_all('td')
        parsed_row = []
        id = tds[0].find('a').get('href').split('=')[1]
        parsed_row.append(id)
        parsed_row.append(tds[0].find('a').string)
        parsed_row.append(tds[1].string)
        parsed_row.append(tds[2].string)
        for idx in range(3,8):
            if tds[idx].string == '$':
                parsed_row.append(0)
            else:
                parsed_row.append(Decimal(sub(r'[^\d.]', '', tds[idx].string)))
        for row in depth_tbl_rows:
            depth_id = row.find('a').get('href').split('=')[1]
            if id == depth_id:
                depth_tds = row.find_all('td')
                for td in depth_tds[1:]:
                    parsed_row.append(td.string)
        return parsed_row

    def get_player_from_player_page(self, player_id, league_id):
        url = f'https://ottoneu.fangraphs.com/{league_id}/playercard?id={player_id}'
        player_soup = self.get_soup(url)
        header = player_soup.findAll('div', {'class': 'page-header__primary'})[0]
        name = header.find('h1').contents[0].string.strip()
        org_info = header.find('h1').find('span', {'class':'strong tinytext'}).contents[0].string.split()
        team = org_info[0]
        pos = org_info[1]
        fg_id = header.find('a').get('href').split('=')[1]
        return (player_id, name, team, pos, fg_id)


def main():
    scraper = Scrape_Ottoneu()
    scraper.get_player_from_player_page(31948, 1128)
    #avg = scraper.get_avg_salary_ds(True)
    #print(scraper.scrape_finances_page(160))
    #scraper.get_universe_production_tables()
    #rost = scraper.scrape_roster_export(160)
    #print(rost.head(50))
    #trans = scraper.scrape_recent_trans_api(160)
    #print(trans.head())

if __name__ == '__main__':
    main()