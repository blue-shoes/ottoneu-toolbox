from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import os
from scrape import scrape_ottoneu
from domain.domain import Base, Player, Salary_Info
from dao.session import Session
from services import player_services
import logging
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import filedialog as fd
from tkinter import messagebox as mb
from tkinter.messagebox import showinfo
from ui import draft_tool, values
from ui.base import BaseUi

class OttoneuToolBox(BaseUi):
    def __init__(self):
        super().__init__(preferences={})  
        self.setup_logging()
        logging.info('Starting session')

        self.create_main_win()

    def create_main_win(self):
        main_frame = ttk.Frame(self.main_win)
        main_lbl = ttk.Label(main_frame, text = "Select a module", font='bold')
        main_lbl.grid(column=0,row=0, pady=5, columnspan=2)

        ttk.Button(main_frame, text='Create Player Values', command=self.create_player_values_click).grid(column=0,row=1)
        ttk.Button(main_frame, text='Run Draft Tracker', command=self.run_draft_tracker).grid(column=1,row=1)
        ttk.Button(main_frame, text='League Analysis', command=self.open_league_analysis).grid(column=0,row=2)
        ttk.Button(main_frame, text='Exit', command=self.exit).grid(column=1,row=2)

        main_frame.pack()

        logging.debug('Starting main window')
        self.main_win.mainloop()

    def create_player_values_click(self):
        # TODO: Move to Create Player Values Module
        self.main_win.destroy()
        values.main(self.preferences)
        #self.create_main_win()

    def run_draft_tracker(self):
        self.main_win.destroy()
        draft_tool.main()
        #self.create_main_win()

    def open_league_analysis(self):
        # TODO: Move to league analysis
        self.main_win.destroy()
        a = 1
        #self.create_main_win()
    
    def exit(self):
        self.main_win.destroy()

    def setup_logging(self, config=None):
        if config != None and 'log_level' in config:
            level = logging.getLevelName(config['log_level'].upper())
        else:
            level = logging.INFO
        if not os.path.exists('.\\logs'):
            os.mkdir('.\\logs')
        logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=level, filename='.\\logs\\toolbox.log')

def main():
    try:
        program = OttoneuToolBox()
    except Exception as e:
        logging.exception("Error encountered")
        mb.showerror("Error", f'Fatal program error. See ./logs/toolbox.log')

if __name__ == '__main__':
    main()