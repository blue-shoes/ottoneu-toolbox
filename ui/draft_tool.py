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

from enum import Enum

bat_pos = ['C','1B','2B','3B','SS','MI','OF','Util']
pitch_pos = ['SP','RP']

class IdType(Enum):
    OTTONEU = 0
    FG = 1

class DraftTool:
    def __init__(self):
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

        ttk.Label(main_frame, text = 'Player Search: ', font='bold').grid(column=0,row=1,pady=5)

        sv = tk.StringVar()
        sv.trace("w", lambda name, index, mode, sv=sv: self.player_search(sv))
        ttk.Entry(main_frame, textvariable=sv).grid(column=1,row=1)

        main_frame.pack()

    def player_search(self, sv):
        text = sv.get().upper()
        if text == '':
            res = pd.DataFrame()
            return
        res = self.values.loc[self.values['Search_Name'].str.contains(text, case=False, regex=True)]
        print(res.head())

    
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
        positions = scraper.get_avg_salary_ds()

        self.lg_id = self.league_num_entry.get()
        self.rosters = scraper.scrape_roster_export(self.lg_id)

        self.setup_win.destroy()

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
                #TODO data validation here
        for pos in pitch_pos:
            pos_path = os.path.join(self.value_dir.get(), f'{pos}_values.csv')
            if os.path.exists(pos_path):
                self.pos_values[pos] = pd.read_csv(pos_path)
                #TODO data validation here

def main():
    tool = DraftTool()

if __name__ == '__main__':
    main()
