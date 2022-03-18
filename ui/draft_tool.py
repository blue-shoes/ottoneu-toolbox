from re import search
import tkinter as tk                     
from tkinter import ttk 
from tkinter import filedialog as fd
from tkinter import messagebox as mb
from tkinter.messagebox import showinfo
import os
import os.path
import pandas as pd
import util.string_util

from scrape.scrape_ottoneu import Scrape_Ottoneu 

from pathlib import Path
import threading
from time import sleep
from datetime import datetime

from enum import Enum

bat_pos = ['C','1B','2B','3B','SS','MI','OF','Util']
pitch_pos = ['SP','RP']

class IdType(Enum):
    OTTONEU = 0
    FG = 1

class DraftTool:
    def __init__(self):
        self.demo_source = None
        self.setup_win = tk.Tk() 
        self.value_dir = tk.StringVar()
        self.value_dir.set(Path.home())
        self.setup_win.title("FBB Draft Tool v0.1") 

        setup_tab = ttk.Frame(self.setup_win)

        self.create_setup_tab(setup_tab)

        self.setup_win.mainloop()   

        self.create_main()

        self.main_win.mainloop()

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

        f = ttk.Frame(main_frame)
        f.grid(column=1,row=1)

        cols = ('Name','Value','Salary','Pos','Team','Points','P/G','P/IP')
        self.search_view = ttk.Treeview(f, columns=cols, show='headings')    
        for col in cols:
            self.search_view.heading(col, text=col) 
        self.search_view.grid(column=0,row=0)   
        self.search_view.bind('<<TreeviewSelect>>', self.on_select)

        tab_control = ttk.Notebook(main_frame)
        tab_control.grid(row=2, column=0, columnspan=2)

        self.pos_view = {}

        overall_frame = ttk.Frame(tab_control)
        tab_control.add(overall_frame, text='Overall')
        self.overall_view = ttk.Treeview(overall_frame, columns=cols, show='headings')
        for col in cols:
            self.overall_view.heading(col, text=col)
        self.overall_view.bind('<<TreeviewSelect>>', self.on_select)
        self.overall_view.pack()
        vsb = ttk.Scrollbar(overall_frame, orient="vertical", command=self.overall_view.yview)
        vsb.pack(side='right', fill='y')
        pos_df = self.values.loc[self.values['Salary'] == '$0']
        for i in range(len(pos_df)):
            id = pos_df.iloc[i, 0]
            name = pos_df.iloc[i, 2]
            value = pos_df.iloc[i, 1]
            pos = pos_df.iloc[i, 4]
            team = pos_df.iloc[i, 3]
            pts = "{:.1f}".format(pos_df.iloc[i, 5])
            ppg = "{:.2f}".format(pos_df.iloc[i, 7])
            pip = "{:.2f}".format(pos_df.iloc[i, 8])
            self.overall_view.insert('', tk.END, text=id, values=(name, value, pos, team, pts, ppg, pip))

        for pos in self.pos_values:
            pos_frame = ttk.Frame(tab_control)
            tab_control.add(pos_frame, text=pos) 
            if pos in bat_pos:
                cols = ('Name','Value','Salary','Pos','Team','Points','P/G')
            else:
                cols = ('Name','Value','Salary','Pos','Team','Points','P/IP')
            self.pos_view[pos] = ttk.Treeview(pos_frame, columns=cols, show='headings')
            for col in cols:
                self.pos_view[pos].heading(col, text=col)
            self.pos_view[pos].bind('<<TreeviewSelect>>', self.on_select)
            self.pos_view[pos].pack()
            vsb = ttk.Scrollbar(pos_frame, orient="vertical", command=self.pos_view[pos].yview)
            vsb.pack(side='right', fill='y')
            pos_df = self.pos_values[pos].loc[self.pos_values[pos]['Salary'] == '$0']
            for i in range(len(pos_df)):
                id = pos_df.iloc[i, 0]
                name = pos_df.iloc[i, 2]
                value = pos_df.iloc[i, 1]
                position = pos_df.iloc[i, 4]
                team = pos_df.iloc[i, 3]
                pts = "{:.1f}".format(pos_df.iloc[i, 5])
                rate = "{:.2f}".format(pos_df.iloc[i, 7])
                self.pos_view[pos].insert('', tk.END, text=id, values=(name, value, position, team, pts, rate))

        main_frame.pack()

    def on_select(self, event):
        if len(event.widget.selection()) == 1:
            print(f'Selection is {event.widget.item(event.widget.selection()[0])["text"]}')

    def start_draft_monitor(self):
        self.run_event = threading.Event()
        self.run_event.set()
        t1 = threading.Thread(target = self.refresh_thread)
        t1.start()
        try:
            while 1:
                sleep(5)
        except KeyboardInterrupt:
            self.run_event.clear()
            t1.join()
    
    def stop_draft_monitor(self):
        self.run_event.clear()
    
    def refresh_thread(self):
        last_time = datetime.now()
        while(self.run_event.is_set()):
            sleep(60)
            if self.demo_source == None:
                last_trans = Scrape_Ottoneu().scrape_recent_trans_api(self.lg_id)
            else:
                last_trans = pd.read_csv(self.demo_source)
            most_recent = last_trans[0]['Date']
            if most_recent > last_time:
                index = len(last_trans)
                while index >= 0:
                    if last_trans[index]['Date'] > last_time:
                        if last_trans[index]['Type'] == 'Add':
                            row = []
                            row.append(last_trans[index]['Team ID'])
                            #team name unimportant
                            row.append('')
                            otto_id = last_trans[index]['Ottoneu ID']
                            row.append(otto_id)
                            row.append(self.positions[otto_id]['FG MajorLeagueID'])
                            row.append(self.positions[otto_id]['FG MinorLeagueID'])
                            #name, team, position, unimportant
                            row.append('')
                            row.append('')
                            row.append('')
                            row.append(last_trans[index]['Salary'])
                            self.rosters.append(row, ignore_index=True)
                        elif last_trans[index] == 'Cut':
                            self.rosters.drop(last_trans[index]['Ottoneu ID'])
                    index -= index
                last_time = most_recent
                self.refresh_views()

    def update_player_search(self):
        text = self.search_string.get().upper()
        if text == '':
            df = pd.DataFrame()
        else:
            df = self.values.loc[self.values['Search_Name'].str.contains(text, case=False, regex=True)]
        #from https://stackoverflow.com/a/27068344
        self.search_view.delete(*self.search_view.get_children())
        for i in range(len(df)):
            id = df.iloc[i, 0]
            name = df.iloc[i, 2]
            value = df.iloc[i, 1]
            salary = df.iloc[i,10]
            pos = df.iloc[i, 4]
            team = df.iloc[i, 3]
            pts = "{:.1f}".format(df.iloc[i, 5])
            ppg = "{:.2f}".format(df.iloc[i, 7])
            pip = "{:.2f}".format(df.iloc[i, 8])
            self.search_view.insert('', tk.END, values=(name, value, salary, pos, team, pts, ppg, pip))

    
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
            mb.showinfo('Bad Directory', f'The directory {dir} does not contain a values.csv file. Please select a different directory.')
            return

        self.value_dir.set(dir)
        
    def initialize_draft(self):
        self.value_file_path = os.path.join(self.value_dir.get(), 'values.csv')

        if not os.path.exists(self.value_file_path):
            mb.showinfo('Bad Directory', f'The directory {self.value_dir.get()} does not contain a values.csv file. Please select a different directory.')
            return

        self.load_values()

        scraper = Scrape_Ottoneu()
        self.positions = scraper.get_avg_salary_ds()

        self.lg_id = self.league_num_entry.get()
        self.rosters = scraper.scrape_roster_export(self.lg_id)

        self.update_rostered_players()

        self.setup_win.destroy()

    def update_rostered_players(self):
        self.values = self.values.merge(self.rosters[['Salary']], how='left', left_on='OttoneuID', right_index=True).fillna('$0')
        for pos in self.pos_values:
            self.pos_values[pos] = self.pos_values[pos].merge(self.rosters[['Salary']], how='left', left_on='OttoneuID', right_index=True).fillna('$0')

    def load_values(self):
        self.values = pd.read_csv(self.value_file_path)
        self.values.set_index('playerid', inplace=True)
        self.values['Search_Name'] = self.values['Name'].apply(lambda x: util.string_util.normalize(x))
        self.id_type = IdType.FG
        #TODO: data validation here
        self.pos_values = {}
        for pos in bat_pos:
            pos_path = os.path.join(self.value_dir.get(), f'{pos}_values.csv')
            if os.path.exists(pos_path):
                self.pos_values[pos] = pd.read_csv(pos_path)
                self.pos_values[pos].set_index('playerid', inplace=True)
                #TODO data validation here
        for pos in pitch_pos:
            pos_path = os.path.join(self.value_dir.get(), f'{pos}_values.csv')
            if os.path.exists(pos_path):
                self.pos_values[pos] = pd.read_csv(pos_path)
                self.pos_values[pos].set_index('playerid', inplace=True)
                #TODO data validation here

def main():
    tool = DraftTool()

if __name__ == '__main__':
    main()
