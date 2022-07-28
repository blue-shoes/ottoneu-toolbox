import logging
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import messagebox as mb
from ui.base import BaseUi
from domain.domain import ValueData, ValueCalculation
from services import projection_services
from ui.dialog import proj_download, selection_projection

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
        self.game_type = StringVar()
        self.game_type.set('FGP')
        gt_combo = ttk.Combobox(inpf, textvariable=self.game_type)
        gt_combo.bind("<<ComboboxSelected>>", self.update_game_type)
        # TODO: Don't hardcode game types, include other types
        gt_combo['values'] = ('FGP', 'SABR')
        gt_combo.grid(column=1,row=2,pady=5)

        ttk.Label(inpf, text="Number of Teams:").grid(column=0, row=3,pady=5)
        self.num_teams_str = StringVar()
        self.num_teams_str.set("12")
        ttk.Entry(inpf, textvariable=self.num_teams_str).grid(column=1,row=3,pady=5)

        ttk.Label(inpf, text="Manually assign hitter/pitcher split?").grid(column=0, row=4,pady=5)
        self.manual_split = BooleanVar()
        self.manual_split.set(False)
        ttk.Checkbutton(inpf, variable=self.manual_split, command=self.toggle_manual_split).grid(column=1, row=4, pady=5)

        self.hitter_aloc_lbl = ttk.Label(inpf, text="Hitter allocation (%):")
        self.hitter_aloc_lbl.grid(column=0, row=5,pady=5)
        self.hitter_aloc_lbl.configure(state='disable')
        self.hitter_allocation = StringVar()
        self.hitter_allocation.set("60")
        self.hitter_aloc_entry = ttk.Entry(inpf, textvariable=self.hitter_allocation)
        self.hitter_aloc_entry.grid(column=1,row=5,pady=5)
        self.hitter_aloc_entry.configure(state='disable')

        ttk.Label(inpf, text="Non-productive salaries (e.g. prospects):").grid(column=0, row=6,pady=5)
        self.non_prod_dollars_str = StringVar()
        self.non_prod_dollars_str.set("48")
        ttk.Entry(inpf, textvariable=self.non_prod_dollars_str).grid(column=1,row=6,pady=5)

        ttk.Label(inpf, text="Hitter Value Basis:").grid(column=0,row=7,pady=5)
        self.hitter_basis = StringVar()
        self.hitter_basis.set('P/G')
        self.hitter_basis_cb = hbcb = ttk.Combobox(inpf, textvariable=self.hitter_basis)
        hbcb['values'] = ('P/G','P/PA')
        hbcb.grid(column=1,row=7,pady=5)

        ttk.Label(inpf, text="Pitcher Value Basis:").grid(column=0,row=8,pady=5)
        self.pitcher_basis = StringVar()
        self.pitcher_basis.set('P/IP')
        self.pitcher_basis_cb = pbcb = ttk.Combobox(inpf, textvariable=self.pitcher_basis)
        pbcb['values'] = ('P/IP','P/G')
        pbcb.grid(column=1,row=8,pady=5)
    
    def update_game_type(self):
        i = 1
        #TODO: Update input fields for unique game types

    def select_projection(self):
        count = projection_services.get_projection_count()
        if count == 0:
            dialog = proj_download.Dialog(self.main_win)
        else:
            dialog = selection_projection.Dialog(self.main_win)
        self.projection = dialog.projection
        self.sel_proj.set(self.projection.name)

    
    def create_output_frame(self):
        self.create_output_frame = outf = ttk.Frame(self.main_win)
        outf.grid(column=2,row=0, padx=5, sticky=tk.N, pady=17)

    def toggle_manual_split(self):
        if self.manual_split.get():
            self.hitter_aloc_lbl.configure(state='active')
            self.hitter_aloc_entry.configure(state='active')
        else:
            self.hitter_aloc_lbl.configure(state='disable')
            self.hitter_aloc_entry.configure(state='disable')

def main(preferences):
    try:
        win = ValuesCalculation(preferences)
    except Exception as e:
        logging.exception("Error encountered")
        mb.showerror("Error", f'Fatal program error. See ./logs/toolbox.log')

if __name__ == '__main__':
    main()