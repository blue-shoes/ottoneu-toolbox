import tkinter as tk  
from tkinter import ttk 
from ui.dialog import preferences
   
__version__ = '0.9.0'

class BaseUi():

    def __init__(self, preferences=None):
        self.preferences = preferences
        self.main_win = tk.Tk() 
        self.main_win.title(f"Ottoneu Tool Box v{__version__}") 

        self.create_menu()
    
    def create_menu(self):
        self.menubar = mb = tk.Menu(self.main_win)
        self.main_menu = mm = tk.Menu(mb, tearoff=0)
        mm.add_command(label="Preferences", command=self.open_preferences)
        mm.add_separator()
        mm.add_command(label="Exit", command=self.exit)
        mb.add_cascade(label="Menu", menu=mm)
        self.main_win.config(menu=mb)
    
    def exit(self):
        if(self.exit_tasks()):
            self.main_win.destroy()

    def exit_tasks(self):
        #To be implemented in child classes
        return True

    def open_preferences(self):
        preferences.Dialog(self.preferences)
    
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
