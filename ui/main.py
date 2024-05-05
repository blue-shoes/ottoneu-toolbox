import tkinter as tk  
from tkinter import ttk 
import logging
import os
import configparser
import webbrowser
from distutils.version import StrictVersion
from tkinter import messagebox as mb
import datetime
import threading
import requests
import sys

from ui.dialog import preferences, progress, league_select, value_select, help, update
from ui.start import Start
from ui.draft_tool import DraftTool
from ui.values import ValuesCalculation
from services import player_services, salary_services, league_services, property_service
from domain.domain import Property
from domain.enum import Preference as Pref, PropertyType
from dao import db_update
   
__version__ = '1.2.8'

class Main(tk.Tk):

    def __init__(self, debug=False, demo_source=False, resource_path=None, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.resource_path = resource_path
        if resource_path is None:
            self.iconbitmap("otb_icon.ico")
            self.iconbitmap(bitmap='otb_icon.ico')
            self.iconbitmap(default='otb_icon.ico')
        else:
            iconbitmap = resource_path('otb_icon.ico')
            self.iconbitmap(iconbitmap)
            self.iconbitmap(bitmap=iconbitmap)
            self.iconbitmap(default=iconbitmap)

        self.title(f"Ottoneu Tool Box v{__version__}") 
        #self.preferences = preferences
        self.debug = debug
        self.demo_source = demo_source
        self.setup_logging()
        logging.info('Starting session')

        self.load_preferences()

        self.create_menus()
        self.value_calculation = None
        self.league = None
        self.run_event = threading.Event()

        # the container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        self.container = tk.Frame(self)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        self.frame_type = {}
        self.current_page = None
        self.create_frame(Start)
        self.create_frame(ValuesCalculation)
        self.create_frame(DraftTool)

        logging.debug('Starting main window')
        self.show_start_page()
        self.current_page = Start.__name__

        if self.startup_tasks():
            sys.exit(0)

        self.lift()
        self.focus_force()

        self.protocol("WM_DELETE_WINDOW", self.exit)
    
    def create_frame(self, frame : tk.Frame):
        page_name = frame.__name__
        self.frame_type[page_name] = frame
        frame = frame(parent=self.container, controller=self)
        self.frames[page_name] = frame

    def startup_tasks(self) -> bool:
        progress_dialog = progress.ProgressDialog(self.container, "Startup Tasks")
        db_vers = property_service.get_db_version()
        sql_dir = self.resource_path('scripts')
        if db_vers is None:
            db_vers = Property()
            db_vers.name = PropertyType.DB_VERSION.value
            db_vers.value = __version__
            db_vers = property_service.save_property(db_vers)
        if '-beta' in db_vers.value:
            db_strict_vers = StrictVersion(db_vers.value.split('-beta')[0])
        else:
            db_strict_vers = StrictVersion(db_vers.value)
        if '-beta' in __version__:
            v = __version__.split('-beta')[0]
        else:
            v = __version__
        if db_strict_vers < StrictVersion(v):
            progress_dialog.set_task_title('Updating Database Structure...')
            progress_dialog.increment_completion_percent(5)
            to_run = []
            for filename in os.listdir(sql_dir):
                try:
                    vers = StrictVersion(filename.split('.sql')[0])
                    if vers > db_strict_vers and vers <= StrictVersion(v):
                        to_run.append(os.path.join(sql_dir, filename))
                except ValueError:
                    continue
            if len(to_run) > 0:
                db_update.run_db_updates(to_run)
            db_vers.value = __version__
            property_service.save_property(db_vers)
        progress_dialog.increment_completion_percent(10)
        progress_dialog.set_task_title('Checking for updates')
        #Check if we have the latest version
        try:
            response = requests.get("https://api.github.com/repos/blue-shoes/ottoneu-toolbox/releases/latest")
            latest_version = response.json()["name"]
            if 'v' in latest_version:
                latest_version = latest_version.split('v')[1]
            if StrictVersion(latest_version) > StrictVersion(v):
                dialog = update.Dialog(self, response)
                if dialog.status:
                    progress_dialog.complete()
                    return True
            #Check that database has players in it, and populate if it doesn't
            if not player_services.is_populated():
                progress_dialog.set_task_title("Populating Player Database")
                salary_services.update_salary_info(pd=progress_dialog)
                progress_dialog.increment_completion_percent(33)
                # We also put values into the advanced calc options table
                db_update.run_db_updates([os.path.join(sql_dir, 'adv_calc_setup.sql')])
            refresh = salary_services.get_last_refresh()
            if refresh is None or (datetime.datetime.now() - refresh.last_refresh).days > self.preferences.getint('General', Pref.SALARY_REFRESH_FREQUENCY, fallback=30):
                progress_dialog.set_task_title("Updating Player Database")
                salary_services.update_salary_info()
                progress_dialog.increment_completion_percent(33)
        except requests.ConnectionError:
            mb.showinfo('No Internet Connection', 'There appears to be no internet connection. Connectivity functions will be unavailable.')

        progress_dialog.complete()
        return False
    
    def get_resource_path(self, resource):
        return self.resource_path(resource)
    
    def load_preferences(self):
        self.preferences = configparser.ConfigParser()
        config_path = 'conf/otb.conf'
        if not os.path.exists('conf'):
            os.mkdir('conf')
        if os.path.exists(config_path):
            self.preferences.read(config_path)
    
    def create_menus(self):
        self.menubar = mb = tk.Menu(self)
        self.main_menu = mm = tk.Menu(mb, tearoff=0)
        self.view_menu = vm = tk.Menu(mm, tearoff=0)
        vm.add_command(label="Value Calculator", command=self.show_player_values)
        vm.add_command(label="Draft Tool", command=self.show_draft_tracker)
        mm.add_cascade(label="Open Window...", menu=vm)
        mm.add_separator()
        mm.add_command(label="Select League", command=self.select_league)
        mm.add_command(label="Load Player Values", command=self.select_value_set)
        mm.add_separator()
        mm.add_command(label="Preferences", command=self.open_preferences)
        mm.add_separator()
        mm.add_command(label="Exit", command=self.exit)
        mb.add_cascade(label="Menu", menu=mm)
        self.help_menu = hm = tk.Menu(mb, tearoff=0)
        hm.add_command(label='Project Wiki', command=self.open_project_wiki)
        hm.add_command(label='Visit Project Home', command=self.open_project_home)
        hm.add_command(label='Release Notes', command=self.open_release_notes)
        hm.add_separator()
        hm.add_command(label='View License', command=self.show_license)
        hm.add_command(label='Acknowledgements', command=self.show_acknowledgements)
        hm.add_separator()
        hm.add_command(label='Contact', command=self.show_contact)
        mb.add_cascade(label="Help", menu=hm)
        self.config(menu=mb)
    
    def open_project_wiki(self):
        webbrowser.open_new_tab('https://github.com/blue-shoes/ottoneu-toolbox/wiki')
    
    def open_project_home(self):
        webbrowser.open_new_tab('https://github.com/blue-shoes/ottoneu-toolbox')
    
    def open_release_notes(self):
        webbrowser.open_new_tab('https://github.com/blue-shoes/ottoneu-toolbox/wiki/Release-Notes')
    
    def show_license(self):
        help.Dialog(self, 'LICENSE')
    
    def show_acknowledgements(self):
        help.Dialog(self, 'THIRDPARTYLICENSE')
    
    def show_contact(self):
        help.Dialog(self, 'contact.txt')

    def exit(self):
        if(self.current_page.exit_tasks()):
            self.destroy()

    def exit_tasks(self):
        #To be implemented in child classes
        return True

    def open_preferences(self):
        preferences.Dialog(self)
    
    def reload_ui(self):
        for name in self.frames:
            if name == Start.__name__:
                continue
            frame = self.frames.get(name)
            frame.destroy()
            self.frames[name] = self.frame_type.get(name)(parent=self.container, controller=self)
        self.show_frame(self.current_page, ignore_forget=True)

    
    def setup_logging(self, config=None):
        if config != None and 'log_level' in config:
            level = logging.getLevelName(config['log_level'].upper())
        elif self.debug:
            level = logging.DEBUG
        else:
            level = logging.INFO
        if not os.path.exists('.\\logs'):
            os.mkdir('.\\logs')
        logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=level, filename='.\\logs\\toolbox.log')
    
    def show_frame(self, page_name, ignore_forget=False):
        '''Show a frame for the given page name'''
        if self.current_page is None or self.frames[self.current_page].leave_page():
            frame = self.frames[page_name]
            if frame.on_show():
                if self.current_page is not None and not ignore_forget:
                    self.frames[self.current_page].pack_forget()
                frame.pack(fill="both", expand=True)
                frame.tkraise()
                self.current_page = page_name
    
    def show_start_page(self):
        self.show_frame(Start.__name__)

    def show_player_values(self):
        self.show_frame(ValuesCalculation.__name__)

    def show_draft_tracker(self):
        self.show_frame(DraftTool.__name__)

    def show_league_analysis(self):
        # TODO:Implement league analysis
        mb.showwarning("League analysis not currently supported")
    
    def select_league(self):
        dialog = league_select.Dialog(self)
        if dialog.league is not None:
            pd = progress.ProgressDialog(self, title='Updating League')
            self.league = league_services.refresh_league(dialog.league.index, pd=pd)
            pd.set_completion_percent(100)
            pd.destroy()
            if self.current_page == DraftTool.__name__:
                self.frames[DraftTool.__name__].league_change()
    
    def select_value_set(self):
        dialog = value_select.Dialog(self.container, self)
        if dialog.value is not None:
            self.value_calculation = dialog.value
            if self.current_page == ValuesCalculation.__name__:
                self.frames[ValuesCalculation.__name__].on_show()
            elif self.current_page == DraftTool.__name__:
                self.frames[DraftTool.__name__].value_change()

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
