import tkinter as tk  
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

        mb.add_cascade(label="Menu", menu=mm)
        self.main_win.config(menu=mb)
    
    def open_preferences(self):
        preferences.Dialog(self.preferences)
