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

__version__ = '0.8.2'

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
        self.setup_win.title(f"Ottoneu Draft Tool v{__version__}") 
        self.extra_cost = 0
        self.lg_id = None
        self.sort_cols = {}
        self.show_drafted_players = tk.BooleanVar()
        self.show_drafted_players.set(False)

        setup_tab = ttk.Frame(self.setup_win)
        
        logging.debug('Creating setup tab')
        self.create_setup_tab(setup_tab)

        logging.debug('Starting setup window')
        self.setup_win.mainloop()   

        if self.lg_id == None:
            return

        logging.info(f'League id = {self.lg_id}; Values Directory: {self.value_dir.get()}')
        try:
            self.create_main()

            logging.debug('Starting main loop')

            self.main_win.mainloop()
        except Exception as e:
            logging.exception('Error running draft')
            mb.showerror("Draft Error", f'Error running draft, see ./logs/draft.log')
    
    def setup_logging(self, config=None):
        if config != None and 'log_level' in config:
            level = logging.getLevelName(config['log_level'].upper())
        else:
            level = logging.INFO
        if not os.path.exists('.\\logs'):
            os.mkdir('.\\logs')
        logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=level, filename='.\\logs\\draft.log')

    def initialize_treeview_style(self):
        #Fix for Tkinter version issue found here: https://stackoverflow.com/a/67141755
        s = ttk.Style()

        #from os import name as OS_Name
        if self.main_win.getvar('tk_patchLevel')=='8.6.9': #and OS_Name=='nt':
            def fixed_map(option):
                # Fix for setting text colour for Tkinter 8.6.9
                # From: https://core.tcl.tk/tk/info/509cafafae
                #
                # Returns the style map for 'option' with any styles starting with
                # ('!disabled', '!selected', ...) filtered out.
                #
                # style.map() returns an empty list for missing options, so this
                # should be future-safe.
                return [elm for elm in s.map('Treeview', query_opt=option) if elm[:2] != ('!disabled', '!selected')]
            s.map('Treeview', foreground=fixed_map('foreground'), background=fixed_map('background'))

    def create_main(self):
        
        self.main_win = tk.Tk()

        self.initialize_treeview_style()

        self.main_win.title(f'Ottoneu Draft Tool v{__version__}')
        main_frame = ttk.Frame(self.main_win)
        lg_lbl = ttk.Label(main_frame, text = f"League {self.lg_id} Draft", font='bold')
        lg_lbl.config(anchor="center")
        lg_lbl.grid(column=0,row=0, pady=5)

        search_frame = ttk.Frame(main_frame)
        search_frame.grid(column=0,row=1, padx=5)
        ttk.Label(search_frame, text = 'Player Search: ', font='bold').grid(column=0,row=1,pady=5)

        self.search_string = sv = tk.StringVar()
        sv.trace("w", lambda name, index, mode, sv=sv: self.update_player_search())
        ttk.Entry(search_frame, textvariable=sv).grid(column=1,row=1)

        self.start_monitor = ttk.Button(search_frame, text='Start Draft Monitor', command=self.start_draft_monitor).grid(column=0,row=2)
        self.monitor_status = tk.StringVar()
        self.monitor_status.set('Monitor not started')
        self.monitor_status_lbl = tk.Label(search_frame, textvariable=self.monitor_status, fg='red')
        self.monitor_status_lbl.grid(column=1,row=2)
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
        self.search_view.grid(column=0,row=0, padx=5)   
        self.search_view.bind('<<TreeviewSelect>>', self.on_select)
        sv.column("# 1",anchor=W, stretch=NO, width=175)
        sv.column("# 2",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 3",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 4",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 5",anchor=CENTER, stretch=NO, width=75)
        sv.column("# 6",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 7",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 8",anchor=CENTER, stretch=NO, width=50)
        sv.column("# 9",anchor=CENTER, stretch=NO, width=50)

        running_list_frame = ttk.Frame(main_frame)
        running_list_frame.grid(row=2, column=0, columnspan=2, pady=5)

        show_drafted_btn = ttk.Checkbutton(running_list_frame, text="Show drafted players?", variable=self.show_drafted_players, command=self.toggle_drafted)
        show_drafted_btn.grid(row=0, column=1, sticky=tk.N, pady=20)
        show_drafted_btn.state(['!alternate'])

        self.tab_control = ttk.Notebook(running_list_frame, width=570, height=300)
        self.tab_control.grid(row=0, column=0)

        self.pos_view = {}
        self.scroll_bars = {}

        overall_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(overall_frame, text='Overall')
        cols = ('Name','Value','Inf. Cost','Pos','Team','Points','P/G','P/IP')
        sortable_cols = ('Value', 'Points', 'P/G', 'P/IP')
        self.overall_view = ov = ttk.Treeview(overall_frame, columns=cols, show='headings')
        ov.grid(column=0)
        ov.column("# 1",anchor=W, stretch=NO, width=175)
        ov.column("# 2",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 3",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 4",anchor=CENTER, stretch=NO, width=75)
        ov.column("# 5",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 6",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 7",anchor=CENTER, stretch=NO, width=50)
        ov.column("# 8",anchor=CENTER, stretch=NO, width=50)
        for col in cols:
            if col in sortable_cols:
                self.overall_view.heading(col, text=col, command=lambda _col=col: self.sort_treeview(self.overall_view, _col) )
            else:
                self.overall_view.heading(col, text=col)
        self.overall_view.bind('<<TreeviewSelect>>', self.on_select)
        self.overall_view.tag_configure('rostered', background='#A6A6A6')
        self.overall_view.tag_configure('rostered', foreground='#5A5A5A')
        self.overall_view.pack(side='left', fill='both', expand=1)
        vsb = ttk.Scrollbar(ov, orient="vertical", command=self.overall_view.yview)
        ov.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.scroll_bars[ov] = vsb
        self.sort_cols[self.overall_view] = None

        for pos in self.pos_values:
            pos_frame = ttk.Frame(self.tab_control)
            self.tab_control.add(pos_frame, text=pos) 
            if pos in bat_pos:
                cols = ('Name','Value','Inf. Cost','Pos','Team','Points','P/G')
            else:
                cols = ('Name','Value','Inf. Cost','Pos','Team','Points','P/IP')
            self.pos_view[pos] = pv = ttk.Treeview(pos_frame, columns=cols, show='headings')
            pv.column("# 1",anchor=W, stretch=NO, width=175)
            pv.column("# 2",anchor=CENTER, stretch=NO, width=50)
            pv.column("# 3",anchor=CENTER, stretch=NO, width=50)
            pv.column("# 4",anchor=CENTER, stretch=NO, width=75)
            pv.column("# 5",anchor=CENTER, stretch=NO, width=50)
            pv.column("# 6",anchor=CENTER, stretch=NO, width=50)
            pv.column("# 7",anchor=CENTER, stretch=NO, width=50)
            for col in cols:
                if col in sortable_cols:
                    pv.heading(col, text=col, command=lambda _pv=pv, _col=col, _pos=pos: self.sort_treeview(_pv, _col, _pos))
                else:
                    pv.heading(col, text=col)
            self.pos_view[pos].bind('<<TreeviewSelect>>', self.on_select)
            self.pos_view[pos].tag_configure('rostered', background='#A6A6A6', foreground='#5A5A5A')
            self.pos_view[pos].pack(side='left', fill='both', expand=1)
            vsb = ttk.Scrollbar(pv, orient="vertical", command=self.pos_view[pos].yview)
            pv.configure(yscrollcommand=vsb.set)
            vsb.pack(side='right', fill='y')
            self.scroll_bars[pv] = vsb
            #vsb = ttk.Scrollbar(pos_frame, orient="vertical", command=self.pos_view[pos].yview)
            #vsb.pack(side='right', fill='y')
            self.sort_cols[pv] = None

        self.refresh_views()

        main_frame.pack()

    def toggle_drafted(self):
        self.show_drafted_players.set(not self.show_drafted_players.get())
        self.refresh_views()

    def sort_treeview(self, treeview, col, pos=None):
        if self.sort_cols[treeview] == col:
            self.sort_cols[treeview] = None
        else:
            self.sort_cols[treeview] = col
        if pos != None:
            self.refresh_pos_table(pos)
        else:
            self.refresh_overall_view()

    def on_select(self, event):
        if len(event.widget.selection()) == 1:
            print(f'Selection is {event.widget.item(event.widget.selection()[0])["text"]}')

    def start_draft_monitor(self):
        logging.info('---Starting Draft Monitor---')
        self.run_event.set()
        self.monitor_thread = threading.Thread(target = self.refresh_thread)
        self.monitor_thread.start()
        self.monitor_status.set('Monitor enabled')
        self.monitor_status_lbl.config(fg='green')
        self.main_win.update_idletasks()
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
        self.monitor_status.set('Monitor stopped')
        self.monitor_status_lbl.config(fg='red')
        self.main_win.update_idletasks()
    
    def refresh_thread(self):
        last_time = datetime.now() - timedelta(minutes=30)
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
                        if self.id_type == IdType.FG:
                            if self.positions.loc[otto_id]['FG MajorLeagueID'] == '':
                                playerid = self.positions.loc[otto_id]['FG MinorLeagueID']
                            else:
                                playerid = self.positions.loc[otto_id]['FG MajorLeagueID']
                        else:
                            playerid = otto_id
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

    def sort_df_by(self, df, col):
        if col == 'Value':
            if 'Blank col 0' in df:
                return df.sort_values(by=['Blank col 0'], ascending=[False])
            else:
                return df.sort_values(by=['PAR'], ascending=[False])
        if col == 'Points':
            return df.sort_values(by=['Points'], ascending=[False])
        if col == 'P/G':
            return df.sort_values(by=['P/G'], ascending=[False])
        if col == 'P/IP':
            return df.sort_values(by=['P/IP'], ascending=[False])

    def refresh_views(self, pos_keys=None):
        pos_df = self.values.loc[self.values['Salary'] == '$0']
        pos_val = pos_df.loc[~pos_df['Value'].str.contains("-")]
        self.remaining_value = pos_val['Value'].apply(lambda x: int(x.split('$')[1])).sum()
        self.calc_inflation()
        self.refresh_overall_view()
        if pos_keys == None:
            for pos in self.pos_values:
                self.refresh_pos_table(pos)
        else:
            for pos in pos_keys:
                logging.debug(f'updating {pos}')
                self.refresh_pos_table(pos)
        
        self.update_player_search()
    
    def refresh_overall_view(self):
        self.overall_view.delete(*self.overall_view.get_children())
        if self.show_drafted_players.get() == 1:
            pos_df = self.values
        else:
            pos_df = self.values.loc[self.values['Salary'] == '$0']
        if self.sort_cols[self.overall_view] != None:
            pos_df = self.sort_df_by(pos_df, self.sort_cols[self.overall_view])
        for i in range(len(pos_df)):
            id = pos_df.iat[i, 0]
            name = pos_df.iat[i, 2]
            value = pos_df.iat[i, 1]
            inf_cost = '$' + "{:.0f}".format(int(value.split('$')[1]) * self.inflation)
            position = pos_df.iat[i, 4]
            team = pos_df.iat[i, 3]
            pts = "{:.1f}".format(pos_df.iat[i, 5])
            ppg = "{:.2f}".format(pos_df.iat[i, 7])
            pip = "{:.2f}".format(pos_df.iat[i, 8])
            salary = pos_df.iat[i, 10]
            #This text currently doesn't work for TypeId.OTTONEU
            if salary == '$0':
                self.overall_view.insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts, ppg, pip))
            else:
                self.overall_view.insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts, ppg, pip), tags=('rostered',))
        self.scroll_bars[self.overall_view].pack()

    def refresh_pos_table(self, pos):
        self.pos_view[pos].delete(*self.pos_view[pos].get_children())
        if self.show_drafted_players.get() == 1:
            pos_df = self.pos_values[pos]
        else:
            pos_df = self.pos_values[pos].loc[self.pos_values[pos]['Salary'] == '$0']
        if self.sort_cols[self.pos_view[pos]] != None:
            pos_df = self.sort_df_by(pos_df, self.sort_cols[self.pos_view[pos]])
        for i in range(len(pos_df)):
            id = pos_df.iat[i, 0]
            name = pos_df.iat[i, 2]
            value = pos_df.iat[i, 1]
            inf_cost = '$' + "{:.0f}".format(int(value.split('$')[1]) * self.inflation)
            position = pos_df.iat[i, 4]
            team = pos_df.iat[i, 3]
            pts = "{:.1f}".format(pos_df.iat[i, 5])
            rate = "{:.2f}".format(pos_df.iat[i, 7])
            salary = pos_df.iat[i, 8]
            #This text currently doesn't work for TypeId.OTTONEU
            if salary == '$0':
                self.pos_view[pos].insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts, rate))
            else:
                self.pos_view[pos].insert('', tk.END, text=id, values=(name, value, inf_cost, position, team, pts, rate), tags=('rostered',))
        self.scroll_bars[self.pos_view[pos]].pack()

    def update_player_search(self):
        text = self.search_string.get().upper()
        if text == '' or len(text) == 1:
            df = pd.DataFrame() 
        else:
            df = self.values.loc[self.values['Search_Name'].str.contains(text, case=False, regex=True)]
        #from https://stackoverflow.com/a/27068344
        self.search_view.delete(*self.search_view.get_children())
        for i in range(len(df)):
            id = df.iat[i, 0]
            name = df.iat[i, 2]
            value = df.iat[i, 1]
            inf_cost = '$' + "{:.0f}".format(int(value.split('$')[1]) * self.inflation)
            salary = df.iat[i,10]
            pos = df.iat[i, 4]
            team = df.iat[i, 3]
            pts = "{:.1f}".format(df.iat[i, 5])
            ppg = "{:.2f}".format(df.iat[i, 7])
            pip = "{:.2f}".format(df.iat[i, 8])
            self.search_view.insert('', tk.END, values=(name, value, salary, inf_cost,pos, team, pts, ppg, pip))

    
    def create_setup_tab(self, tab):
        try:
            ttk.Label(tab, text = "Enter League #:").grid(column=0,row=0, pady=5, sticky=tk.E)
            #width is in text units, not pixels
            self.league_num_entry = ttk.Entry(tab, width = 10)
            self.league_num_entry.grid(column=1,row=0, sticky=tk.W, padx=5)
            ttk.Label(tab, text = "Player Values Directory:").grid(column=0,row=1, pady=5, stick=tk.E)
            self.dir_button = ttk.Button(tab, textvariable = self.value_dir, command=self.select_dir)
            self.dir_button.grid(column=1,row=1, padx=5)

            ttk.Button(tab, text='Initialize Session', command=self.initialize_draft).grid(column=1,row=2, pady=5, sticky=tk.W, padx=5)

            tab.pack()
        except Exception as e:
            logging.exception('Error creating draft')
            mb.showerror("Draft Error", f'Error creating draft, see ./logs/draft.log')

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
        self.popup = tk.Toplevel()
        tk.Label(self.popup, text='Draft Initializing').grid(row=0,column=0)
        progress = 0
        self.progress_var = tk.DoubleVar()
        self.progress_var.set(0)
        ttk.Progressbar(self.popup, variable=self.progress_var, maximum=100).grid(row=1, column=0)
        self.popup.pack_slaves()

        self.progress_step = sv = tk.StringVar()
        self.progress_label = ttk.Label(self.popup, textvariable=self.progress_step)
        self.progress_label.grid(column=0,row=2)

        try:
            self.value_file_path = os.path.join(self.value_dir.get(), 'values.csv')

            if not os.path.exists(self.value_file_path):
                self.value_file_path = os.path.join(self.value_dir.get(), 'ottoneu_values.csv')
                if not os.path.exists(self.value_file_path):
                    mb.showinfo('Bad Directory', f'The directory {self.value_dir.get()} does not contain a values.csv or ottoneu_values.csv file. Please select a different directory.')
                    return
            self.progress_step.set('Getting Ottoneu Player Universe...')
            self.popup.update()
            scraper = Scrape_Ottoneu()
            self.positions = scraper.get_avg_salary_ds()
            progress += 30
            self.progress_var.set(progress)
            self.popup.update()

            self.progress_step.set('Loading Player Values...')
            try:
                result = self.load_values()
            except KeyError as ke:
                logging.exception('Error initializing draft')
                mb.showerror("Initialization Error", f"There was an error initializing the draft. Columns missing in one or more *values.csv files.")
                self.progress_var.set(100)
                self.popup.destroy()
                return
            except Exception as e:
                logging.exception('Error initializing draft')
                mb.showerror("Initialization Error", f"There was an error initializing the draft, see ./logs/draft.log")
                self.progress_var.set(100)
                self.popup.destroy()
                return

            if not result:
                mb.showinfo('Bad Player Ids', f'The player ids did not match Ottoneu or FanGraphs ids. Please use one of these player id types.')
                self.progress_var.set(100)
                self.popup.destroy()
                return

            self.lg_id = self.league_num_entry.get()
            self.progress_step.set(f'Getting League {self.lg_id} Rosters...')
            progress += 30
            self.progress_var.set(progress)
            self.popup.update()
            self.rosters = scraper.scrape_roster_export(self.lg_id)
            #Below used for api testing
            #self.rosters = pd.read_csv('C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Test\\rosters.csv')
            #self.rosters.set_index("ottoneu ID", inplace=True)
            #self.rosters.index = self.rosters.index.astype(str, copy=False)

            progress += 15
            self.progress_var.set(progress)
            self.popup.update()
            self.progress_step.set('Updating Values With Roster Info...')
            self.update_rostered_players()
            if 'Blank col 0' in self.values.columns:
                self.values.sort_values(by=['Blank col 0'], ascending=[False], inplace=True)
                for pos in bat_pos:
                    self.pos_values[pos].sort_values(by=['P/G'], ascending=[False], inplace=True)
                for pos in pitch_pos:
                    self.pos_values[pos].sort_values(by=['P/IP'], ascending=[False], inplace=True)
            
            self.progress_step.set('Initialization Complete')
            self.progress_var.set(100)
            self.setup_win.destroy()
        
        except Exception as e:
            logging.exception('Error initializing draft')
            mb.showerror("Initialization Error", f"There was an error initializing the draft, see ./logs/draft.log")
            self.popup.destroy()
            return
    
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
        elif type(value) == float:
            return value
        else:
            return float(value)

    def load_values(self):
        self.values = pd.read_csv(self.value_file_path, index_col=0)
        self.values.index = self.values.index.astype(str, copy = False)
        soto_id = self.values.index[self.values['Name'] == "Juan Soto"].tolist()[0]
        if soto_id == '23717':
            self.id_type = IdType.OTTONEU
        elif soto_id == '20123':
            self.id_type = IdType.FG
            self.values = self.values.astype({'OttoneuID': 'str'})
        else:
            return False
        #Leif output. Remap columns
        self.values.rename(columns={'price': 'Value', 'Pos':'Position(s)', 'FGPts':'Points', 'FGPtspIP':'P/IP', 'FGPtspG':'P/G', 'FGPts_G':'P/G', 'SABRPts' : 'Points', 'SABRPtspIP' : 'P/IP', 'SABRPtspG':'P/G'}, inplace=True)
        
        self.values['P/G'] = self.values['P/G'].apply(self.convert_rates)
        self.values['P/IP'] = self.values['P/IP'].apply(self.convert_rates)

        if not 'PAR' in self.values:
            self.values['PAR'] = 0
        
        if not 'Team' in self.values:
            self.values = self.values.merge(self.positions[['Org']], how='left', left_index=True, right_index=True, sort=False).fillna('---')
            self.values['Team'] = self.values['Org']
            self.values = self.values.drop('Org', axis=1)

        if self.id_type == IdType.OTTONEU:
            if self.values['Value'].dtype == object:
                self.values['Blank col 0'] = self.values['Value'].apply(lambda x: float(x.split('$')[1]))
            else:
                self.values['Blank col 0'] = self.values['Value']
            #Leif doesn't have teams, need to merge here
            self.values = self.values[['Blank col 0', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G', 'P/IP']]    
        else:
            self.values =  self.values[['OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G', 'P/IP']]   

        if not self.values['Value'].dtype == object:
            self.values['Value'] = self.values['Value'].apply(lambda x: "${:.0f}".format(x)) 

        #TODO: data validation here
        self.pos_values = {}
        for pos in bat_pos:
            pos_path = os.path.join(self.value_dir.get(), f'{pos}_values.csv')
            if os.path.exists(pos_path):
                self.pos_values[pos] = pd.read_csv(pos_path, index_col=0)
                self.pos_values[pos] = self.pos_values[pos].astype({'OttoneuID': 'str'})
                if not 'PAR' in self.pos_values[pos]:
                        self.pos_values[pos]['PAR'] = 0
                if not 'Team' in self.pos_values[pos]:
                    self.pos_values[pos] = self.pos_values[pos].merge(self.positions[['Org']], how='left', left_index=True, right_index=True, sort=False).fillna('---')
                    self.pos_values[pos]['Team'] = self.pos_values[pos]['Org']
                    self.pos_values[pos] = self.pos_values[pos].drop('Org', axis=1)
                if self.id_type == IdType.OTTONEU:
                    self.pos_values[pos]['Blank col 0'] = 0
                    self.pos_values[pos] = self.pos_values[pos][['Blank col 0', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G']]
                else:
                    self.pos_values[pos] =  self.pos_values[pos][['OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/G']]
                #self.pos_values[pos].set_index('playerid', inplace=True)
                #TODO data validation here
            else:
                if pos == 'MI':
                    self.pos_values[pos] = self.values.loc[self.values['Position(s)'].str.contains("2B|SS", case=False, regex=True)].sort_values(by=['P/G'], ascending=[False])
                elif pos == 'Util':
                    self.pos_values[pos] = self.values.loc[self.values['P/G'] > 0].sort_values(by=['P/G'], ascending=[False])
                else:
                    self.pos_values[pos] = self.values.loc[self.values['Position(s)'].str.contains(pos)].sort_values(by=['P/G'], ascending=[False])
                self.pos_values[pos] = self.pos_values[pos].drop('P/IP', axis=1)
        for pos in pitch_pos:
            pos_path = os.path.join(self.value_dir.get(), f'{pos}_values.csv')
            if os.path.exists(pos_path):
                self.pos_values[pos] = pd.read_csv(pos_path, index_col=0)
                self.pos_values[pos] = self.pos_values[pos].astype({'OttoneuID': 'str'})
                if not 'PAR' in self.pos_values[pos]:
                        self.pos_values[pos]['PAR'] = 0
                if not 'Team' in self.pos_values[pos]:
                    self.pos_values[pos] = self.pos_values[pos].merge(self.positions[['Org']], how='left', left_index=True, right_index=True, sort=False).fillna('---')
                    self.pos_values[pos]['Team'] = self.pos_values[pos]['Org']
                    self.pos_values[pos] = self.pos_values[pos].drop('Org', axis=1)
                if self.id_type == IdType.OTTONEU:
                    self.pos_values[pos]['Blank col 0'] = 0
                    self.pos_values[pos] = self.pos_values[pos][['Blank col 0', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/IP']]
                else:
                    self.pos_values[pos] =  self.pos_values[pos][['OttoneuID', 'Value', 'Name', 'Team', 'Position(s)', 'Points', 'PAR', 'P/IP']]
                #self.pos_values[pos].set_index('playerid', inplace=True)
                #TODO data validation here
            else:
                self.pos_values[pos] = self.values.loc[self.values['Position(s)'].str.contains(pos)].sort_values(by=['P/IP'], ascending=[False])
                self.pos_values[pos] = self.pos_values[pos].drop('P/G', axis=1)
        
        self.values['Search_Name'] = self.values['Name'].apply(lambda x: util.string_util.normalize(x))

        return True

def main():
    try:
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
