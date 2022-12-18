import tkinter as tk  
from tkinter import ttk 
from ui.dialog import preferences, progress
from domain.domain import ValueCalculation, League
from ui.start import Start
from ui.draft_tool import DraftTool
from ui.values import ValuesCalculation
import logging
import os
from ui.dialog import progress, league_select, value_select
import datetime
from services import player_services, salary_services, league_services
   
__version__ = '0.9.0'

class Main(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.title(f"Ottoneu Tool Box v{__version__}") 
        self.preferences = preferences
        
        self.setup_logging()
        logging.info('Starting session')

        self.startup_tasks()

        self.create_menu()
        self.value_calculation = None
        self.league = None

        # the container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        self.container = tk.Frame(self)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        self.create_frame(Start)
        self.create_frame(ValuesCalculation)

        logging.debug('Starting main window')
        self.show_start_page()
    
    def create_frame(self, frame : tk.Frame):
        page_name = frame.__name__
        frame = frame(parent=self.container, controller=self)
        self.frames[page_name] = frame

        # put all of the pages in the same location;
        # the one on the top of the stacking order
        # will be the one that is visible.
        frame.grid(row=0, column=0, sticky="nsew")

    def startup_tasks(self):
        progress_dialog = progress.ProgressDialog(self, "Startup Tasks")
        #Check that database has players in it, and populate if it doesn't
        if not player_services.is_populated():
            progress_dialog.set_task_title("Populating Player Database")
            salary_services.update_salary_info()
            progress_dialog.increment_completion_percent(33)
        refresh = salary_services.get_last_refresh()
        if refresh is None or (datetime.datetime.now() - refresh.last_refresh).days > 30:
            progress_dialog.set_task_title("Updating Player Database")
            salary_services.update_salary_info()
            progress_dialog.increment_completion_percent(33)

        progress_dialog.set_completion_percent(100)
        #TODO: Destroying this pushes the whole window to the background for some reason
        #progress_dialog.destroy()
    
    def create_menu(self):
        self.menubar = mb = tk.Menu(self)
        self.main_menu = mm = tk.Menu(mb, tearoff=0)
        mm.add_command(label="Select League", command=self.select_league)
        mm.add_command(label="Load Player Values", command=self.select_value_set)
        mm.add_separator()
        mm.add_command(label="Preferences", command=self.open_preferences)
        mm.add_separator()
        mm.add_command(label="Exit", command=self.exit)
        mb.add_cascade(label="Menu", menu=mm)
        self.config(menu=mb)
    
    def exit(self):
        if(self.current_frame.exit_tasks()):
            self.destroy()

    def exit_tasks(self):
        #To be implemented in child classes
        return True

    def open_preferences(self):
        preferences.Dialog(self.preferences)
    
    def setup_logging(self, config=None):
        if config != None and 'log_level' in config:
            level = logging.getLevelName(config['log_level'].upper())
        else:
            level = logging.INFO
        if not os.path.exists('.\\logs'):
            os.mkdir('.\\logs')
        logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=level, filename='.\\logs\\toolbox.log')
    
    def show_frame(self, page_name):
        '''Show a frame for the given page name'''
        frame = self.frames[page_name]
        frame.on_show()
        frame.tkraise()
    
    def show_start_page(self):
        self.show_frame(Start.__name__)

    def show_player_values(self):
        self.show_frame(ValuesCalculation.__name__)

    def show_draft_tracker(self):
        self.show_frame(DraftTool.__name__)

    def show_league_analysis(self):
        # TODO:Implement league analysis
        a = 1
    
    def select_league(self):
        dialog = league_select.Dialog(self)
        if dialog.league is not None:
            pd = progress.ProgressDialog(self, title='Updating League')
            self.league = league_services.refresh_league(dialog.league.index, pd=pd)
            pd.set_completion_percent(100)
            pd.destroy()
    
    def select_value_set(self):
        dialog = value_select.Dialog(self)
        if dialog.value is not None:
            self.value = dialog.value

    def exit(self):
        self.destroy()    

    def initialize_treeview_style(self):
        #Fix for Tkinter version issue found here: https://stackoverflow.com/a/67141755
        s = ttk.Style()

        #from os import name as OS_Name
        if self.getvar('tk_patchLevel')=='8.6.9': #and OS_Name=='nt':
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
