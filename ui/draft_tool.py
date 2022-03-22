from re import search
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import filedialog as fd
from tkinter import messagebox as mb
from tkinter.messagebox import showinfo
import os
import os.path
import pandas as pd
import numpy as np
from sklearn.metrics import jaccard_score
import util.string_util
import queue
import logging
import math

from scrape.scrape_ottoneu import Scrape_Ottoneu 

from pathlib import Path
import threading
from time import sleep
from datetime import datetime, timedelta

from enum import Enum

bat_pos = ['C','1B','2B','3B','SS','MI','OF','Util']
pitch_pos = ['SP','RP']

class IdType(Enum):
    OTTONEU = 0
    FG = 1

class DraftTool:
    def __init__(self, run_event, demo_source=None):
        self.setup_logging()
        logging.info('Starting session')
        self.demo_source = demo_source
        self.run_event = run_event
        self.queue = queue.Queue()
        self.setup_win = tk.Tk() 
        self.value_dir = tk.StringVar()
        self.value_dir.set(Path.home())
        #self.value_dir.set('C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Staging')
        self.setup_win.title("FBB Draft Tool v0.8") 
        self.extra_cost = 0
        self.lg_id = None

        setup_tab = ttk.Frame(self.setup_win)
        
        logging.debug('Creating setup tab')
        self.create_setup_tab(setup_tab)

        logging.debug('Starting setup window')
        self.setup_win.mainloop()   

        if self.lg_id == None:
            return

        logging.info(f'League id = {self.lg_id}; Values Directory: {self.value_dir.get()}')

        self.create_main()

        logging.debug('Starting main loop')
        self.main_win.mainloop()
    
    def setup_logging(self, config=None):
        if config != None and 'log_level' in config:
            level = logging.getLevelName(config['log_level'].upper())
        else:
            level = logging.INFO
        if not os.path.exists('.\\logs'):
            os.mkdir('.\\logs')
        logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=level, filename='.\\logs\\draft.log')

    def create_main(self):
        self.main_win = tk.Tk()
        self.main_win.title("FBB Draft Tool v0.1")
        main_frame = ttk.Frame(self.main_win)
        ttk.Label(main_frame, text = f"League {self.lg_id} Draft", font='bold').grid(column=0,row=0)

        search_frame = ttk.Frame(main_frame)
        search_frame.grid(column=0,row=1)
        ttk.Label(search_frame, text = 'Player Search: ', font='bold').grid(column=0,row=1,pady=5)

        self.search_string = sv = tk.StringVar()
        sv.trace("w", lambda name, index, mode, sv=sv: self.update_player_search())
        ttk.Entry(search_frame, textvariable=sv).grid(column=1,row=1)

        self.start_monitor = ttk.Button(search_frame, text='Start Draft Monitor', command=self.start_draft_monitor).grid(column=0,row=2)
        self.stop_monitor = ttk.Button(search_frame, text="Stop Draft Monitor", command=self.stop_draft_monitor).grid(column=0,row=3)

        self.inflation_str_var = tk.StringVar()

        self.inflation_lbl = ttk.Label(search_frame, textvariable=self.inflation_str_var)
        self.inflation_lbl.grid(column=0,row=4)

        f = ttk.Frame(main_frame)
        f.grid(column=1,row=1)

        cols = ('Name','Value','Salary','Inf. Cost','Pos','Team','Points','P/G','P/IP')
        self.search_view = sv = ttk.Treeview(f, columns=cols, show='headings')    
        for col in cols:
            self.search_view.heading(col, text=col) 
        self.search_view.grid(column=0,row=0)   
        self.search_view.bind('<<TreeviewSelect>>', self.on_select)
        sv.column("# 1",anchor=W, stretch=NO, width=200)
        sv.column("# 2",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 3",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 4",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 5",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 6",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 7",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 8",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 9",anchor=CENTER, stretch=NO, width=50)

        tab_control = ttk.Notebook(main_frame)
        tab_control.grid(row=2, column=0, columnspan=2)

        self.pos_view = {}

        overall_frame = ttk.Frame(tab_control)
        tab_control.add(overall_frame, text='Overall')
        cols = ('Name','Value','Inf. Cost','Pos','Team','Points','P/G','P/IP')
        self.overall_view = ov = ttk.Treeview(overall_frame, columns=cols, show='headings')
        ov.column("# 1",anchor=W, stretch=NO, width=200)
        ov.column("# 2",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 3",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 4",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 5",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 6",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 7",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 8",anchor=CENTER, stretch=NO, width=50)
        for col in cols:
            self.overall_view.heading(col, text=col)
        self.overall_view.bind('<<TreeviewSelect>>', self.on_select)
        self.overall_view.pack()
        vsb = ttk.Scrollbar(overall_frame, orient="vertical", command=self.overall_view.yview)
        vsb.pack(side='right', fill='y')

        for pos in self.pos_values:
            pos_frame = ttk.Frame(tab_control)
            tab_control.add(pos_frame, text=pos) 
            if pos in bat_pos:
                cols = ('Name','Value','Inf. Cost','Pos','Team','Points','P/G')
            else:
                cols = ('Name','Value','Inf. Cost','Pos','Team','Points','P/IP')
            self.pos_view[pos] = pv = ttk.Treeview(pos_frame, columns=cols, show='headings')
            pv.column("# 1",anchor=W, stretch=NO, width=200)
            pv.column("# 2",anchor=CENTER, stretch=NO, width=50)
            pv.column("# 3",anchor=CENTER, stretch=NO, width=50)
            pv.column("# 4",anchor=CENTER, stretch=NO, width=50)
            pv.column("# 5",anchor=CENTER, stretch=NO, width=50)
            pv.column("# 6",anchor=CENTER, stretch=NO, width=50)
            pv.column("# 7",anchor=CENTER, stretch=NO, width=50)
            for col in cols:
                self.pos_view[pos].heading(col, text=col)
            self.pos_view[pos].bind('<<TreeviewSelect>>', self.on_select)
            self.pos_view[pos].pack()
            vsb = ttk.Scrollbar(pos_frame, orient="vertical", command=self.pos_view[pos].yview)
            vsb.pack(side='right', fill='y')

        self.refresh_views()

        main_frame.pack()

    def on_select(self, event):
        if len(event.widget.selection()) == 1:
            print(f'Selection is {event.widget.item(event.widget.selection()[0])["text"]}')

    def start_draft_monitor(self):
        logging.info('---Starting Draft Monitor---')
        self.run_event.set()
        self.monitor_thread = threading.Thread(target = self.refresh_thread)
        self.monitor_thread.start()
        self.main_win.after(1000, self.update_ui)

    def update_ui(self):
        if not self.run_event.is_set and self.queue.empty():
            return
        if not self.queue.empty():
            key, data = self.queue.get()
            logging.debug(f'Updating the following positions: {data}')
            self.refresh_views(data)
        self.main_win.after(1000, self.update_ui)
    
    def stop_draft_monitor(self):
        logging.info('!!!Stopping Draft Monitor!!!')
        self.run_event.clear()
    
    def refresh_thread(self):
        last_time = datetime.now()
        #Below line for testing against api outside of draft
        #last_time = datetime.now() - timedelta(days=10)
        while(self.run_event.is_set()):
            if self.demo_source == None:
                last_trans = Scrape_Ottoneu().scrape_recent_trans_api(self.lg_id)
            else:
                logging.debug("demo_source")
                last_trans = pd.read_csv(self.demo_source)
                last_trans['Date'] = last_trans['Date'].apply(lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S.%f'))
            most_recent = last_trans.iloc[0]['Date']
            if most_recent > last_time:
                index = len(last_trans)-1
                update_pos = []
                while index >= 0:
                    if last_trans.iloc[index]['Date'] > last_time:
                        otto_id = last_trans.iloc[index]['Ottoneu ID']
                        if self.positions.loc[otto_id]['FG MajorLeagueID'] == '':
                            playerid = self.positions.loc[otto_id]['FG MinorLeagueID']
                        else:
                            playerid = self.positions.loc[otto_id]['FG MajorLeagueID']
                        if not otto_id in self.positions.index:
                            logging.info(f'Otto id {otto_id} not in self.positions.index')
                            self.extra_cost += int(last_trans.iloc[index]['Salary'].split('$')[1])
                        else:
                            self.positions.at[otto_id, "Int Salary"] = int(last_trans.iloc[index]['Salary'].split('$')[1])
                        if not playerid in self.values.index:
                            logging.info(f'id {playerid} not in values')
                            index -= 1
                            continue
                        pos = self.values.loc[playerid, 'Position(s)'].split("/")
                        if '2B' in pos or 'SS' in pos:
                            pos.append('MI')
                        if not ('SP' in pos or 'RP' in pos) and not 'Util' in pos:
                            pos.append('Util')
                        update_pos = np.append(update_pos, pos)
                        if last_trans.iloc[index]['Type'].upper() == 'ADD':
                            self.values.at[playerid, 'Salary'] = last_trans.iloc[index]['Salary']
                            self.values.at[playerid, 'Int Salary'] = int(last_trans.iloc[index]['Salary'].split('$')[1])
                            for p in pos:                                    
                                self.pos_values[p].at[playerid, 'Salary'] = last_trans.iloc[index]['Salary']
                        elif last_trans.iloc[index]['Type'].upper() == 'CUT':
                            self.values.at[playerid, 'Salary'] = "$0"
                            self.values.at[playerid, 'Int Salary'] = 0
                            for p in pos:
                                self.pos_values[p].at[playerid, 'Salary'] = "$0"
                    index -= 1
                last_time = most_recent
                self.queue.put(('pos', list(set(update_pos))))
            sleep(45)

    def refresh_views(self, pos_keys=None):
        self.overall_view.delete(*self.overall_view.get_children())
        pos_df = self.values.loc[self.values['Salary'] == '$0']
        pos_val = pos_df.loc[~pos_df['Value'].str.contains("-")]
        self.remaining_value = pos_val['Value'].apply(lambda x: int(x.split('$')[1])).sum()
        self.calc_inflation()
        for i in range(len(pos_df)):
            id = pos_df.iloc[i, 0]
            name = pos_df.iloc[i, 2]
            value = pos_df.iloc[i, 1]
            inf_cost = '$' + "{:.0f}".format(int(value.split('$')[1]) * self.inflation)
            position = pos_df.iloc[i, 4]
            team = pos_df.iloc[i, 3]
            pts = "{:.1f}".format(pos_df.iloc[i, 5])
            ppg = "{:.2f}".format(pos_df.iloc[i, 7])
            pip = "{:.2f}".format(pos_df.iloc[i, 8])
            self.overall_view.insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts, ppg, pip))
        
        if pos_keys == None:
            for pos in self.pos_values:
                self.refresh_pos_table(pos)
        else:
            for pos in pos_keys:
                logging.debug(f'updating {pos}')
                self.refresh_pos_table(pos)

    def refresh_pos_table(self, pos):
        self.pos_view[pos].delete(*self.pos_view[pos].get_children())
        pos_df = self.pos_values[pos].loc[self.pos_values[pos]['Salary'] == '$0']
        for i in range(len(pos_df)):
            id = pos_df.iloc[i, 0]
            name = pos_df.iloc[i, 2]
            value = pos_df.iloc[i, 1]
            inf_cost = '$' + "{:.0f}".format(int(value.split('$')[1]) * self.inflation)
            position = pos_df.iloc[i, 4]
            team = pos_df.iloc[i, 3]
            pts = "{:.1f}".format(pos_df.iloc[i, 5])
            rate = "{:.2f}".format(pos_df.iloc[i, 7])
            self.pos_view[pos].insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts, rate))

    def update_player_search(self):
        text = self.search_string.get().upper()
        if text == '' or len(text) == 1:
            df = pd.DataFrame() 
        else:
            df = self.values.loc[self.values['Search_Name'].str.contains(text, case=False, regex=True)]
        #from https://stackoverflow.com/a/27068344
        self.search_view.delete(*self.search_view.get_children())
        for i in range(len(df)):
            id = df.iloc[i, 0]
            name = df.iloc[i, 2]
            value = df.iloc[i, 1]
            inf_cost = '$' + "{:.0f}".format(int(value.split('$')[1]) * self.inflation)
            salary = df.iloc[i,10]
            pos = df.iloc[i, 4]
            team = df.iloc[i, 3]
            pts = "{:.1f}".format(df.iloc[i, 5])
            ppg = "{:.2f}".format(df.iloc[i, 7])
            pip = "{:.2f}".format(df.iloc[i, 8])
            self.search_view.insert('', tk.END, values=(name, value, salary, inf_cost,pos, team, pts, ppg, pip))

    
    def create_setup_tab(self, tab):
        ttk.Label(tab, text = "Enter League #:").grid(column=0,row=0)
        #width is in text units, not pixels
        self.league_num_entry = ttk.Entry(tab, width = 10)
        self.league_num_entry.grid(column=1,row=0)
        ttk.Label(tab, text = "Select Directory with Player Values:").grid(column=0,row=1)
        self.dir_button = ttk.Button(tab, textvariable = self.value_dir, command=self.select_dir)
        self.dir_button.grid(column=1,row=1)

        ttk.Button(tab, text='Initialize Session', command=self.initialize_draft).grid(column=0,row=2)

        tab.pack()

    def select_dir(self):
        filetypes = (
            ('csv files', '*.csv'),
            ('All files', '*.*')
        )

        dir = fd.askdirectory(
            title='Choose a directory',
            initialdir=self.value_dir.get())

        value_file = os.path.join(dir, 'values.csv')
        
        if not os.path.exists(value_file):
            value_file = os.path.join(dir, 'ottoneu_values.csv')
            if not os.path.exists(value_file):
                mb.showinfo('Bad Directory', f'The directory {dir} does not contain a values.csv or ottoneu_values.csv file. Please select a different directory.')
                return

        self.value_dir.set(dir)
        
    def initialize_draft(self):
        self.value_file_path = os.path.join(self.value_dir.get(), 'values.csv')

        if not os.path.exists(self.value_file_path):
            self.value_file_path = os.path.join(self.value_dir.get(), 'ottoneu_values.csv')
            if not os.path.exists(self.value_file_path):
                mb.showinfo('Bad Directory', f'The directory {self.value_dir.get()} does not contain a values.csv or ottoneu_values.csv file. Please select a different directory.')
                return
        
        scraper = Scrape_Ottoneu()
        self.positions = scraper.get_avg_salary_ds()

        result = self.load_values()
        if not result:
            mb.showinfo('Bad Player Ids', f'The player ids did not match Ottoneu or FanGraphs ids. Please use one of these player id types.')
            return

        self.lg_id = self.league_num_entry.get()
        self.rosters = scraper.scrape_roster_export(self.lg_id)
        #Below used for api testing
        #self.rosters = pd.read_csv('C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Test\\rosters.csv')
        #self.rosters.set_index("ottoneu ID", inplace=True)

        self.update_rostered_players()
        if 'Blank col 0' in self.values.columns:
            self.values.sort_values(by=['Blank col 0'], ascending=[False], inplace=True)
            for pos in bat_pos:
                self.pos_values[pos].sort_values(by=['P/G'], ascending=[False], inplace=True)
            for pos in pitch_pos:
                self.pos_values[pos].sort_values(by=['P/IP'], ascending=[False], inplace=True)
        self.setup_win.destroy()
    
    def calc_inflation(self):
        self.remaining_dollars = 12*400 - (self.positions['Int Salary'].sum() + self.extra_cost)
        self.inflation = self.remaining_dollars / self.remaining_value
        self.inflation_str_var.set(f'Inflation: {"{:.1f}".format((self.inflation - 1.0)*100)}%')

    def update_rostered_players(self):
        if self.id_type == IdType.FG:
            self.values = self.values.merge(self.rosters[['Salary']], how='left', left_on='OttoneuID', right_index=True, sort=False).fillna('$0')
        else:
            self.values = self.values.merge(self.rosters[['Salary']], how='left', left_index=True, right_index=True, sort=False).fillna('$0')
        self.values['Int Salary'] = self.values['Salary'].apply(self.load_roster_salaries)
        self.positions = self.positions.merge(self.rosters[['Salary']], how='left', left_index=True, right_index=True, sort=False).fillna('$0')
        self.positions['Int Salary'] = self.positions['Salary'].apply(self.load_roster_salaries)
        #self.positions.to_csv('C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Test\\positions.csv')
        for pos in self.pos_values:
            if self.id_type == IdType.FG:
                self.pos_values[pos] = self.pos_values[pos].merge(self.rosters[['Salary']], how='left', left_on='OttoneuID', right_index=True, sort=False).fillna('$0')
            else:
                self.pos_values[pos] = self.pos_values[pos].merge(self.rosters[['Salary']], how='left', left_index=True, right_index=True, sort=False).fillna('$0')
            #set index to str because if you managed to get them all as ints, you will not match up on the back side
            self.pos_values[pos].index = self.pos_values[pos].index.astype(str, copy = False)

    def load_roster_salaries(self, salary_col):
        split = salary_col.split('$')
        if len(split) > 1:
            return int(split[1])
        else:
            return 0

    def convert_rates(self, value):
        if value == 'NA' or math.isnan(value):
            return float(0)
        else:
            return float(value)

    def load_values(self):
        self.values = pd.read_csv(self.value_file_path, index_col=0)
        #self.values.set_index('ottoneu_ID', inplace=True)
        self.values.index = self.values.index.astype(str, copy = False)
        soto_id = self.values.index[self.values['Name'] == "Juan Soto"].tolist()[0]
        if soto_id == '23717':
            self.id_type = IdType.OTTONEU
        elif soto_id == '20123':
            self.id_type = IdType.FG
        else:
            return False
        if 'price' in self.values.columns:
            #Leif output. Remap columns
            self.values.rename(columns={'price': 'Value', 'Pos':'Position(s)', 'FGPts':'Points', 'FGPtspIP':'P/IP', 'FGPtspG':'P/G'}, inplace=True)
            
            self.values['Blank col 0'] = self.values['Value']
            self.values['Value'] = self.values['Value'].apply(lambda x: "${:.0f}".format(x))
            self.values['PAR'] = 0
            self.values['Team'] = '---'
            self.values['P/G'] = self.values['P/G'].apply(self.convert_rates)
            self.values['P/IP'] = self.values['P/IP'].apply(self.convert_rates)
            self.values = self.values[['Blank col 0', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G', 'P/IP']]
            if self.id_type == IdType.OTTONEU:
                #Leif doesn't have teams, need to merge here
                self.values = self.values.merge(self.positions[['Org']], how='left', left_index=True, right_index=True, sort=False).fillna('---')
                self.values['Team'] = self.values['Org']
                self.values = self.values.drop('Org', axis=1)            

        self.values['Search_Name'] = self.values['Name'].apply(lambda x: util.string_util.normalize(x))
        #TODO: data validation here
        self.pos_values = {}
        for pos in bat_pos:
            pos_path = os.path.join(self.value_dir.get(), f'{pos}_values.csv')
            if os.path.exists(pos_path):
                self.pos_values[pos] = pd.read_csv(pos_path, index_col=0)
                #self.pos_values[pos].set_index('playerid', inplace=True)
                #TODO data validation here
            else:
                if pos == 'MI':
                    self.pos_values[pos] = self.values.loc[self.values['Position(s)'].str.contains("2B|SS", case=False, regex=True)].sort_values(by=['P/G'], ascending=[False])
                elif pos == 'Util':
                    self.pos_values[pos] = self.values.loc[self.values['P/G'] > 0].sort_values(by=['P/G'], ascending=[False])
                else:
                    self.pos_values[pos] = self.values.loc[self.values['Position(s)'].str.contains(pos)].sort_values(by=['P/G'], ascending=[False])
        for pos in pitch_pos:
            pos_path = os.path.join(self.value_dir.get(), f'{pos}_values.csv')
            if os.path.exists(pos_path):
                self.pos_values[pos] = pd.read_csv(pos_path, index_col=0)
                #self.pos_values[pos].set_index('playerid', inplace=True)
                #TODO data validation here
            else:
                self.pos_values[pos] = self.values.loc[self.values['Position(s)'].str.contains(pos)].sort_values(by=['P/IP'], ascending=[False])
                self.pos_values[pos] = self.pos_values[pos].drop('P/G', axis=1)
        return True

def main():
    try:
        #tool = DraftTool(demo_source='C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Demo\\recent_transactions.csv')
        run_event = threading.Event()
        tool = DraftTool(run_event)
    except Exception:
        if run_event.is_set:
            run_event.clear()
    finally:
        if run_event.is_set:
            run_event.clear()

if __name__ == '__main__':
    main()
