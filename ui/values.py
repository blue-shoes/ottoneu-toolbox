import logging
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import messagebox as mb
from ui.base import BaseUi

class ValuesCalculation(BaseUi):
    def __init__(self, preferences):
        super().__init__(preferences=preferences)
        
        self.create_input_frame()
        self.create_output_frame()

    def create_input_frame(self):
        self.input_frame = inpf = ttk.Frame(self.main_win)
        inpf.grid(column=0,row=0, padx=5, sticky=tk.N, pady=17)

        ttk.Label(inpf, text="Game Type:").grid(column=0,row=0,pady=5)
        gt_combo = ttk.Combobox(inpf, textvariable=format)
        # TODO: Don't hardcode game types, included other types
        gt_combo['values'] = ('FGP', 'SABR')
        gt_combo.grid(column=1,row=0,pady=5)
    
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