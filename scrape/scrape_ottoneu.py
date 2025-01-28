from bs4 import BeautifulSoup as Soup
from bs4.element import ResultSet
import pandas as pd
from pandas import DataFrame
import os
from os import path
from io import StringIO
import datetime
from re import sub
import time
from typing import List, Tuple, Dict

from scrape import scrape_base
from scrape.exceptions import OttoneuException


class Scrape_Ottoneu(scrape_base.Scrape_Base):
    """Implementation of Scrape_Base class for scraping information from Ottoneu website."""

    def __init__(self, browser: str = None):
        super().__init__(browser)
        # Initialize directory for output calc files if required
        self.dirname = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        dir_path = os.path.join(self.dirname, 'data_dirs')
        if not path.exists(dir_path):
            os.mkdir(dir_path)
        self.subdirpath = os.path.join(self.dirname, 'data_dirs', 'output')
        if not path.exists(self.subdirpath):
            os.mkdir(self.subdirpath)

    def __parse_row(self, row) -> List[str]:
        """Convenience method to return all values in an html string with td tag to list of strings"""
        tds = row.find_all('td')
        parsed_row = []
        for td in tds:
            if len(list(td.children)) > 1:
                parsed_row.append(str(td.contents[0]).strip())
            else:
                parsed_row.append(td.string)
        return parsed_row

    def __parse_header(self, row) -> list[str]:
        """Convenience method to parse a table header and return it as a list of strings"""
        return [str(x.string) for x in row.find_all('th')]

    def get_avg_salary_ds(self, game_type: int = None) -> DataFrame:
        """Scrapes the average salary page for the given game type (default all game types) and returns a DataFrame with the available data. Index is Ottoneu Id"""
        if game_type is None or game_type == 0:
            avg_salary_url = 'https://ottoneu.fangraphs.com/averageValues?export=xml'
        else:
            avg_salary_url = f'https://ottoneu.fangraphs.com/averageValues?export=xml&gameType={game_type}'
        # response = requests.get(avg_salary_url)
        # salary_soup = Soup(response.text, 'xml')
        salary_soup = self._get_soup(avg_salary_url, True)
        rows = salary_soup.find_all('player')
        parsed_rows = [self.__parse_avg_salary_row(row) for row in rows]
        df = DataFrame(parsed_rows)
        df.columns = ['Ottoneu ID', 'Name', 'FG MajorLeagueID', 'FG MinorLeagueID', 'Avg Salary', 'Min Salary', 'Max Salary', 'Median Salary', 'Last 10', 'Roster %', 'Position(s)', 'Org']
        df.set_index('Ottoneu ID', inplace=True)
        df.index = df.index.astype(int, copy=False)
        return df

    def __parse_avg_salary_row(self, row) -> List[str]:
        """Returns a list of string describing the average salary row"""
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

    def get_player_position_ds(self, force_download: bool = False) -> DataFrame:
        """Scrapes the aveage values page for player id and position information. DataFrame index set to FanGraphs Id"""
        subdir = 'data_dirs/projection'
        subdirpath = os.path.join(self.dirname, subdir)
        filepath = os.path.join(subdirpath, 'ottoneu_positions.csv')
        if path.exists(filepath) and not force_download:
            df = pd.read_csv(filepath)
        else:
            if not self.driver:
                self.setupDriver()
            df = self.getDatasetAtAddress('https://ottoneu.fangraphs.com/averageValues?export=csv', filepath)
        df['playerid'] = df['FG MinorLeagueID']
        df['FG MajorLeagueID'] = df['FG MajorLeagueID'].fillna(-1)
        df['FG MajorLeagueID'] = df['FG MajorLeagueID'].astype(int)
        df.loc[df['FG MajorLeagueID'] != -1, 'playerid'] = df['FG MajorLeagueID']
        df.set_index('playerid', inplace=True)
        df.index = df.index.astype(str, copy=False)
        return df

    def __parse_prod_row(self, row) -> List[str]:
        """Returns all values from td tags in an input string"""
        tds = row.find_all('td')
        parsed_row = []
        for td in tds:
            parsed_row.append(td.string)
        return parsed_row

    def scrape_roster_export(self, lg_id: int) -> DataFrame:
        """'Scrapes the /rosterexport page for a league (in csv format) and returns a DataFrame of the information. Index is Ottoneu Id"""
        roster_export_url = f'https://ottoneu.fangraphs.com/{lg_id}/rosterexport'
        # response = requests.get(roster_export_url)
        # rost_soup = Soup(response.text, 'html.parser')
        rost_soup = self._get_soup(roster_export_url)
        df = pd.read_csv(StringIO(rost_soup.contents[0]))
        df.set_index('ottoneu ID', inplace=True)
        df.index = df.index.astype(str, copy=False)
        return df

    def __parse_trans_row(self, row) -> list[str]:
        """'Parses a row of the transactions table and returns a list of strings describing the relevant information"""
        tds = row.find_all('td')
        parsed_row = []
        # url in form of *id=playerid
        playerid = tds[2].find('a').get('href').split('/')[-1]
        parsed_row.append(playerid)
        # url in form of *team=teamid
        teamid = tds[3].find('a').get('href').split('=')[1]
        parsed_row.append(teamid)
        required_tds = [2, 3, 5]
        for ind in required_tds:
            td = tds[ind]
            if td.find('a'):
                parsed_row.append(td.find('a').string)
            else:
                parsed_row.append(td.string.strip())
        return parsed_row

    def scrape_transaction_page(self, lg_id: int) -> DataFrame:
        """'Scrapes the transactions page to return a DataFrame of the recent transactions information. Index is Ottoneu Id"""
        transactions_url = f'https://ottoneu.fangraphs.com/{lg_id}/transactions'
        # response = requests.get(transactions_url)
        # trans_soup = Soup(response.text, 'html.parser')
        trans_soup = self._get_soup(transactions_url)
        table = trans_soup.find_all('table')[0]
        rows = table.find_all('tr')
        parsed_rows = [self.__parse_trans_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = ['Ottoneu ID', 'Team ID', 'Name', 'Team', 'Salary']
        df.set_index('Ottoneu ID', inplace=True)
        return df

    def scrape_recent_trans_api(self, lg_id: int) -> DataFrame:
        """'Scrapes the recent transactions api page to return a DataFrame of the recent transactions information. Index is Ottoneu Id"""
        rec_trans_url = f'https://ottoneu.fangraphs.com/api/recent_transactions?leagueID={lg_id}'
        trans_soup = self._get_soup(rec_trans_url, True)
        if trans_soup.find('transactions') is None:
            raise OttoneuException('League Inactive')
        rows = trans_soup.find_all('transaction')
        parsed_rows = [self.__parse_rec_trans_row(row) for row in rows]
        if len(parsed_rows) == 0:
            return DataFrame()
        df = DataFrame(parsed_rows)
        df.columns = ['Ottoneu ID', 'Team ID', 'Date', 'Salary', 'Type']
        df = df.astype({'Ottoneu ID': 'str'})
        return df

    def __parse_rec_trans_row(self, row) -> list[str]:
        """Returns a list of strings describing the information for a single item from recent transactions"""
        player = row.find('player')
        parsed_row = []
        parsed_row.append(int(player.get('id')))
        team = row.find('team')
        parsed_row.append(int(team.get('id')))
        parsed_row.append(datetime.datetime.strptime(row.find('date').text, '%Y-%m-%d %H:%M:%S'))
        parsed_row.append(row.find('salary').text)
        parsed_row.append(row.find('transaction_type').text)
        return parsed_row

    def scrape_team_production_page(self, lg_id: int, team_id: int) -> list[DataFrame]:
        """Scrapes the production by position tables for a team and return a list of DataFrames with hitting in index 0 and pitching in index 1. Indices are Position"""
        dfs = []
        prod_url = f'https://ottoneu.fangraphs.com/{lg_id}/teamproduction?teamID={team_id}'
        # response = requests.get(prod_url)
        # prod_soup = Soup(response.text, 'html.parser')
        prod_soup = self._get_soup(prod_url)
        sections = prod_soup.find_all('section')
        pos_df = self.__parse_prod_table(sections[0])
        if pos_df.empty:
            return None
        dfs.append(pos_df)
        dfs.append(self.__parse_prod_table(sections[1]))
        return dfs

    def __parse_prod_table(self, section) -> DataFrame:
        """Parses individual table to a player production DataFrame"""
        table = section.find_all('table')[0]
        rows = table.find_all('tr')
        if len(rows) == 1:
            # Empty production page. Skip league
            return DataFrame()
        parsed_rows = [self.__parse_prod_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = self.__parse_header(rows[0])
        df.set_index('POS', inplace=True)
        return df

    def scrape_league_production_pages(self, lg_id: int) -> List[DataFrame]:
        """Scrapes the Team production table by position for each team in the league and concatenates them.
        Returns list of DataFrames with the league hitting prodution in index 0 and the league pitching production in index 1.
        Indicies are position"""
        prod_url = f'https://ottoneu.fangraphs.com/{lg_id}/teamproduction'
        # response = requests.get(prod_url)
        # prod_soup = Soup(response.text, 'html.parser')
        prod_soup = self._get_soup(prod_url)
        select = prod_soup.find_all('select')[0]
        team_opts = select.find_all('option')
        league_bat = []
        league_arm = []
        for team_opt in team_opts:
            id = team_opt['value']
            if id != '-1':
                dfs = self.scrape_team_production_page(lg_id, team_opt['value'])
                if not dfs:
                    return []
                league_bat.append(dfs[0])
                league_arm.append(dfs[1])
        bat_df = pd.concat(league_bat)
        arm_df = pd.concat(league_arm)
        return [bat_df, arm_df]

    def __parse_leagues_row(self, row) -> List[str]:
        """Returns list of information for each row in the Ottoneu Browse Leagues table"""
        tds = row.find_all('td')
        parsed_row = []
        # url in form of /id/home
        val = tds[0].find('a').get('href').split('/')[1]
        parsed_row.append(val)
        for td in tds:
            if len(list(td.children)) > 1:
                parsed_row.append(str(td.contents[0]).strip())
            else:
                parsed_row.append(td.string)
        return parsed_row

    def __parse_leagues_header(self, row) -> List[str]:
        """Returns list corresponding to table headers in Ottoneu Browse Leagues table"""
        cols = []
        cols.append('League Id')
        reg_cols = [str(x.string) for x in row.find_all('th')]
        for col in reg_cols:
            cols.append(col)
        return cols

    def get_all_leagues_by_format(self, s_format: int = 0, OPL: bool = True) -> DataFrame:
        """Returns all leagues with the given format. If OPL is True, only OPL-eligible leagues are returned. Otherwise all leagues of the format are returned. DataFrame
        indexed by league id. A format of 0 returns all formats"""
        leagues = self.scrape_league_table()
        if s_format > 0:
            if s_format == 1:
                gt = 'Ottoneu Classic (4x4)'
            elif s_format == 2:
                gt = 'Old School (5x5)'
            elif s_format == 3:
                gt = 'FanGraphs Points'
            elif s_format == 4:
                gt = 'SABR Points'
            elif s_format == 5:
                gt = 'H2H FanGraphs Points'
            elif s_format == 6:
                gt = 'H2H SABR Points'
            else:
                raise OttoneuException(f'Invalid format requested {s_format}')
            leagues = leagues.loc[leagues['Game Type'] == gt]
        if OPL:
            leagues = leagues.loc[leagues['OPL-eligible'] == 'Yes']
        return leagues

    def scrape_league_table(self) -> DataFrame:
        """Scrapes the Ottoneu Browse Leagues page to return DataFrame with available information for all active leagues. Index is League Id"""
        url = 'https://ottoneu.fangraphs.com/browseleagues'

        self.setupDriver()
        self.driver.get(url)
        time.sleep(5)
        html = self.driver.page_source
        self.driver.quit()
        browse_soup = Soup(html, 'html.parser')
        table = browse_soup.find_all('table')[0]
        rows = table.find_all('tr')
        parsed_rows = [self.__parse_leagues_row(row) for row in rows[1:]]
        df = DataFrame(parsed_rows)
        df.columns = self.__parse_leagues_header(rows[0])
        df.set_index('League Id', inplace=True)
        return df

    def get_universe_production_tables(self, limit: int = 1e6) -> None:
        """Writes the production tables for all active leagues to Excel file"""
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
                # League has no production values
                continue
            bat_dict[lg_id] = dfs[0]
            arm_dict[lg_id] = dfs[1]
            count += 1
            if count > limit:
                break

        for s_format in formats:
            filepath = os.path.join(self.subdirpath, f'{s_format}_prod.xlsx')
            with pd.ExcelWriter(filepath) as writer:
                for lg_id, row in leagues.iterrows():
                    if lg_id in bat_dict:
                        if row['Game Type'] == s_format:
                            bat_dict[lg_id].to_excel(writer, sheet_name=f'{lg_id}_bat')
                            arm_dict[lg_id].to_excel(writer, sheet_name=f'{lg_id}_arm')

    def scrape_league_info_page(self, lg_id: int) -> Dict[str, str]:
        """Returns relevant information from the Ottoneu Settings page fro the input league as a dict"""
        lg_data = {}
        lg_data['ID'] = lg_id
        url = f'https://ottoneu.fangraphs.com/{lg_id}/settings'
        info_soup = self._get_soup(url)
        body = info_soup.find_all('body')[0]
        lg_data['Name'] = body.find_all('h1')[1].string
        tbody = info_soup.find_all('tbody')[0]
        lg_data['Num Teams'] = tbody.find_all('tr')[3].find_all('td')[1].string
        lg_data['Format'] = tbody.find_all('tr')[6].find_all('td')[1].find('a').string
        return lg_data

    def scrape_finances_page(self, lg_id: int) -> DataFrame:
        """Returns contents of the Financial Overview table for the league as a DataFrame. Index is Team Id"""
        url = f'https://ottoneu.fangraphs.com/{lg_id}/tools'
        fin_soup = self._get_soup(url)
        fin_tbl_rows = fin_soup.find(id='finances').find_all('tbody')[0].find_all('tr')
        depth_tbl_rows = fin_soup.find_all('table')[1].find_all('tbody')[0].find_all('tr')
        team_rows = [self.__parse_finance_rows(row, depth_tbl_rows) for row in fin_tbl_rows[:]]
        fin_df = DataFrame(team_rows)
        fin_df.columns = [
            'ID',
            'Name',
            'Players',
            'Spots',
            'Base Salaries',
            'Cap Penalties',
            'Loans In',
            'Loans Out',
            'Cap Space',
            'C Depth',
            '1B Depth',
            '2B Depth',
            'SS Depth',
            '3B Depth',
            'OF Depth',
            'Util Depth',
            'SP Depth',
            'RP Depth',
        ]
        fin_df.set_index('ID', inplace=True)
        fin_df.index = fin_df.index.astype(int, copy=False)
        if len(fin_df) == 0:
            raise OttoneuException(f'No teams in selected league #{lg_id}')
        return fin_df

    def __parse_finance_rows(self, fin_row, depth_tbl_rows) -> List[str]:
        """Returns the contents of a Team Finance table row. Returns a list of [Team_Id, Team_Name, # Players, # Spots, Base Salary, Cap Penalties, Loans in, Loans out, Available cap space]"""
        tds = fin_row.find_all('td')
        parsed_row = []
        id = tds[0].find('a').get('href').split('/')[-1]
        parsed_row.append(id)
        parsed_row.append(tds[0].find('a').string)
        parsed_row.append(tds[1].string)
        parsed_row.append(tds[2].string)
        for idx in range(3, 8):
            if tds[idx].string == '$':
                parsed_row.append(0)
            else:
                parsed_row.append(sub(r'[^\d.]', '', tds[idx].string))
        for row in depth_tbl_rows:
            depth_id = row.find('a').get('href').split('/')[-1]
            if id == depth_id:
                depth_tds = row.find_all('td')
                for td in depth_tds[1:]:
                    parsed_row.append(td.string)
        return parsed_row

    def get_player_from_player_page(self, player_id: int, league_id: int) -> Tuple[int, str, str, str, str]:
        """Access the Ottoneu player page for the given player and league. Returns a tuple of (Ottoneu_Id, Name, Team, Position(s), FanGraphs_Id)"""
        url = f'https://ottoneu.fangraphs.com/playercard/{player_id}/1'
        player_soup = self._get_soup(url)
        header = player_soup.findAll('div', {'class': 'page-header__primary'})[0]
        name = header.find('h1').contents[0].string.strip()
        org_info = header.find('h1').find('span', {'class': 'strong tinytext'}).contents[0].string.split()
        team = org_info[0]
        pos = org_info[-2]
        fg_id = None
        for tag in header.find_all('a'):
            if tag.contents[0].string == 'FanGraphs Player Page':
                fg_id = tag.get('href').split('/')[-1]
        return (player_id, name, team, pos, fg_id)

    def scrape_standings_page(self, lg_id: int, year: int) -> Tuple[DataFrame, DataFrame, DataFrame]:
        """Gets the standings page for the input league for the input year. Returns results as a tuple of two DataFrames. First DataFrame represents the league 'Statistics'\
        table. The second DataFrame represents the 'Rankings' table, if one exists. If not, a None is returned for the second DF. DataFrames are indexed by team id."""
        url = f'https://ottoneu.fangraphs.com/{lg_id}/standings?date={year}-10-31'
        soup = self._get_soup(url)
        table_sects = soup.find_all('section', {'class': 'section-container'})
        stat_df = self.__parse_standings_stats_table(table_sects)
        rank_df = self.__parse_standings_rank_table(table_sects)
        games_and_ip_df = self.__parse_standings_pt_table(table_sects)
        return (stat_df, rank_df, games_and_ip_df)

    def __parse_standings_rank_table(self, table_sects: ResultSet) -> DataFrame:
        """Parses the 'Rankings' table from the league statings page. Returns None if the table does not exist (Points leagues)"""
        sect = None
        for section in table_sects:
            header = section.find('h3')
            if header is not None and header.contents is not None and len(header.contents) > 0 and header.contents[0].string == 'Rankings':
                sect = section
                break
        if sect is None:
            return None
        return self.__get_stats_table(sect)

    def __parse_standings_pt_table(self, table_sects: ResultSet) -> DataFrame:
        """Parses the 'Games Played and Innings Pitched' table from the league standings page."""
        """Parses the 'Statistics' table from the league statings page."""
        sect = None
        for section in table_sects:
            header = section.find('h3')
            if header is not None and header.contents is not None and len(header.contents) > 0 and header.contents[0].string == 'Games Played and Innings Pitched':
                sect = section
                break
        if sect is None:
            return None
        return self.__get_stats_table(sect)

    def __parse_standings_stats_table(self, table_sects: ResultSet) -> DataFrame:
        """Parses the 'Statistics' table from the league statings page."""
        for section in table_sects:
            header = section.find('h3').contents[0].string
            if header == 'Statistics':
                break
        return self.__get_stats_table(section)

    def __get_stats_table(self, section) -> DataFrame:
        """Returns a DataFrame populated with the passed section table from the league standings page."""
        table = section.find('table')
        body = table.find('tbody')
        rows = body.find_all('tr')
        stat_rows = [self.__parse_standings_stat_row(row) for row in rows[:]]
        stat_df = DataFrame(stat_rows)
        header = self.__parse_standings_stat_header(table.find('thead').find_all('tr')[0].find_all('th'))
        stat_df.columns = header
        stat_df.set_index('team_id', inplace=True)
        return stat_df

    def __parse_standings_stat_row(self, row) -> List[float]:
        """Parses a row from the table body from a passed league standings table."""
        tds = row.find_all('td')
        team_id = tds[0].find('a').get('href').split('/')[-1]
        rows = []
        rows.append(team_id)
        for td in tds[1:]:
            try:
                if len(td.find_all('strong')) > 0:
                    rows.append(td.find_all('strong')[0].contents[0].strip())
                elif len(td.find_all('span', {'class': 'negative-change-from-yesterday'})) > 0 or len(td.find_all('span', {'class': 'positive-change-from-yesterday'})) > 0:
                    rows.append(td.contents[0].strip())
                elif len(td.find_all('i', {'class': 'fa fa-caret-up'})) > 0:
                    rows.append(f'{td.find_all("i", {"class": "fa fa-caret-up"})[0].next_sibling.strip()}')
                elif len(td.find_all('i', {'class': 'fa fa-caret-down'})) > 0:
                    rows.append(f'{td.find_all("i", {"class": "fa fa-caret-down"})[0].next_sibling.strip()}')
                else:
                    rows.append(td.contents[0].strip())
            except Exception:
                rows.append(0)
        rows = [float(val) for val in rows]
        return rows

    def __parse_standings_stat_header(self, header_row) -> List[str]:
        """Parses the header row from the table from a passed league standings table."""
        header = []
        header.append('team_id')
        for th in header_row[1:]:
            header.append(th.contents[0].strip())
        return header


def main():
    scraper = Scrape_Ottoneu('FirefoxURL')
    # scraper.get_player_from_player_page(31948, 1128)
    # avg = scraper.get_avg_salary_ds(True)
    # print(scraper.scrape_finances_page(160))
    # scraper.get_universe_production_tables()
    # rost = scraper.scrape_roster_export(160)
    # print(rost.head(50))
    # trans = scraper.scrape_recent_trans_api(160)
    # print(trans.head())
    # leagues = scraper.get_all_leagues_by_format(3)
    # league_ids = [league_id for league_id in leagues.index]
    league_ids = [
        '15',
        '26',
        '40',
        '43',
        '52',
        '74',
        '81',
        '85',
        '90',
        '93',
        '94',
        '98',
        '100',
        '107',
        '120',
        '137',
        '153',
        '160',
        '171',
        '175',
        '179',
        '183',
        '184',
        '207',
        '220',
        '226',
        '228',
        '234',
        '235',
        '248',
        '285',
        '300',
        '303',
        '324',
        '347',
        '375',
        '380',
        '382',
        '389',
        '400',
        '430',
        '435',
        '441',
        '447',
        '468',
        '480',
        '481',
        '482',
        '493',
        '502',
        '504',
        '513',
        '529',
        '530',
        '553',
        '566',
        '568',
        '569',
        '581',
        '591',
        '617',
        '639',
        '652',
        '653',
        '663',
        '699',
        '717',
        '719',
        '726',
        '743',
        '752',
        '757',
        '760',
        '761',
        '765',
        '766',
        '767',
        '772',
        '774',
        '783',
        '785',
        '788',
        '791',
        '800',
        '802',
        '815',
        '823',
        '834',
        '835',
        '842',
        '844',
        '846',
        '859',
        '863',
        '869',
        '879',
        '891',
        '948',
        '1011',
        '1013',
        '1033',
        '1039',
        '1043',
        '1059',
        '1085',
        '1124',
        '1130',
        '1151',
        '1170',
        '1202',
        '1213',
        '1231',
        '1238',
        '1242',
        '1252',
        '1260',
        '1271',
        '1272',
        '1286',
        '1323',
        '1337',
        '1350',
        '1354',
        '1355',
        '1385',
        '1395',
        '1396',
        '1419',
        '1431',
        '1452',
        '1464',
        '1469',
        '1478',
        '1487',
        '1511',
        '1513',
        '1588',
        '1600',
        '1604',
        '1659',
        '1684',
    ]
    # print(league_ids)

    # league_ids = ['815']

    ppg_rank_count = dict()
    pip_rank_count = dict()

    failed = 0

    for lid in league_ids:
        try:
            print(lid)
            df, _, _ = scraper.scrape_standings_page(lid, 2023)

            df['Rank'] = df['Pts'].rank(ascending=False)
            df['PPG Rank'] = df['P/G'].rank(ascending=False)
            df['PIP Rank'] = df['P/IP'].rank(ascending=False)

            for rank in df['Rank'].unique():
                if rank not in ppg_rank_count:
                    ppg_rank_count[rank] = dict()
                    pip_rank_count[rank] = dict()
                ppg_rank_row = df.loc[df['Rank'] == rank]
                ppg_rank = ppg_rank_row['PPG Rank'].values[0]
                pip_rank_row = df.loc[df['Rank'] == rank]
                pip_rank = pip_rank_row['PIP Rank'].values[0]

                ppg_rank_count[rank][ppg_rank] = ppg_rank_count[rank].get(ppg_rank, 0) + 1
                pip_rank_count[rank][pip_rank] = pip_rank_count[rank].get(pip_rank, 0) + 1
        except Exception:
            failed += 1
        # break

    print(f'There are {len(league_ids)} FGP, OPL leagues')
    print(f'There were {failed} standings parsing errors')

    print(ppg_rank_count)
    print(pip_rank_count)


if __name__ == '__main__':
    main()
