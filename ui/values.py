import logging
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import messagebox as mb
from ui.base import BaseUi
from domain.domain import ValueData, ValueCalculation
from services import projection_services
from ui.dialog import proj_download, proj_selection

class ValuesCalculation(BaseUi):
    def __init__(self, preferences):
        super().__init__(preferences=preferences)
        
        self.value_calc = ValueCalculation()

        self.create_input_frame()
        self.create_output_frame()

    def create_input_frame(self):
        self.input_frame = inpf = ttk.Frame(self.main_win)
        inpf.grid(column=0,row=0, padx=5, sticky=tk.N, pady=17)

        ttk.Label(inpf, text="Selected Projections:").grid(column=0,row=0, pady=5)
        self.sel_proj = tk.StringVar()
        self.sel_proj.set("None")
        self.projection = None
        ttk.Label(inpf, textvariable=self.sel_proj).grid(column=1,row=0)
        ttk.Button(inpf, text="Select...", command=self.select_projection).grid(column=2,row=0)


        ttk.Label(inpf, text="Game Type:").grid(column=0,row=2,pady=5)
        gt_combo = ttk.Combobox(inpf, textvariable=format)
        # TODO: Don't hardcode game types, include other types
        gt_combo['values'] = ('FGP', 'SABR')
        gt_combo.grid(column=1,row=2,pady=5)

    def select_projection(self):
        count = projection_services.get_projection_count()
        if count == 0:
            dialog = proj_download.Dialog(self.main_win)
        else:
            dialog = proj_selection.Dialog()
        self.projection = dialog.projection
        self.sel_proj.set(self.projection.name)

    
    def create_output_frame(self):
        self.create_output_frame = outf = ttk.Frame(self.main_win)
        outf.grid(column=2,row=0, padx=5, sticky=tk.N, pady=17)

def main(preferences):
    try:
        win = ValuesCalculation(preferences)
    except Exception as e:
        logging.exception("Error encountered")
        mb.showerror("Error", f'Fatal program error. See ./logs/toolbox.log')

if __name__ == '__main__':
    main()