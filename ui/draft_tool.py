import tkinter as tk                     
from tkinter import ttk 
from tkinter import filedialog as fd
from tkinter.messagebox import showinfo

from scrape.scrape_ottoneu import Scrape_Ottoneu 

from pathlib import Path

class DraftTool:
    def __init__(self):
        self.value_dir = Path.home()
        root = tk.Tk() 
        root.title("FBB Draft Tool v0.1") 

        tabControl = ttk.Notebook(root) 

        setup_tab = ttk.Frame(tabControl)
        #tab1 = ttk.Frame(tabControl) 

        tabControl.add(setup_tab, text = "Setup")
        #tabControl.add(tab1, text ='Dashboard') 
        tabControl.pack(expand = 1, fill ="both") 

        self.create_setup_tab(setup_tab)

        #self.search = ttk.Entry(tab1, width=300, command=self.update_search)

        #ttk.Label(tab1,  
        #        text ="Welcome to GeeksForGeeks").grid(column = 0,  
        #                            row = 0, 
        #                            padx = 30, 
        #                            pady = 30)   
        
        root.mainloop()   

    def create_setup_tab(self, tab):
        league_num_lbl = ttk.Label(tab, text = "Enter League #:")
        self.league_num_entry = ttk.Entry(tab, width = 300)
        value_directory_lbl = ttk.Label(tab, text = "Select Directory with Player Values:")
        value_directory_button = ttk.Button(tab, text = self.value_dir, command=self.select_dir)

        ttk.Button(tab, text='Continue', command=self.initialize_draft)

    def select_dir(self):
        filetypes = (
            ('csv files', '*.csv'),
            ('All files', '*.*')
        )
        self.value_dir = fd.askdirectory(
            title='Choose a directory',
            initialdir=self.value_dir)

        showinfo(
            title='Selected Directory',
            message=self.value_dir
        )

    def initialize_draft(self):
        scraper = Scrape_Ottoneu()
        positions = scraper.get_player_position_ds(True)

    def update_search(self):
        name = self.search.get()

    def __main__(self):
        self.__init__()
