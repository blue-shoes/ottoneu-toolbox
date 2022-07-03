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
from ui import draft_tool

__version__ = '0.9.0'

class OttoneuToolBox():
    def __init__(self):  
        self.setup_logging()
        logging.info('Starting session')
        self.main_win = tk.Tk() 
        self.main_win.title(f"Ottoneu Tool Box v{__version__}") 
        main_frame = ttk.Frame(self.main_win)
        main_lbl = ttk.Label(main_frame, text = "Select a module", font='bold')
        main_lbl.grid(column=0,row=0, pady=5, columnspan=2)

        values_btn = ttk.Button(main_frame, text='Create Player Values', command=self.create_player_values_click).grid(column=0,row=1)
        draft_btn = ttk.Button(main_frame, text='Run Draft Tracker', command=self.run_draft_tracker).grid(column=1,row=1)

        main_frame.pack()

        logging.debug('Starting main window')
        self.main_win.mainloop()   

    def create_player_values_click(self):
        # Move to Create Player Values Module
        a = 1

    def run_draft_tracker(self):
        draft_tool.main()

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