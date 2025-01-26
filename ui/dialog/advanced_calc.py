import tkinter as tk
from tkinter import StringVar

from domain.enum import ScoringFormat, RepLevelScheme, RankingBasis, CalculationDataType as CDT
from services import adv_calc_services
from util import string_util

class Dialog(tk.Toplevel):
    def __init__(self, controller, s_format:ScoringFormat, rep_scheme:RepLevelScheme, hit_basis:RankingBasis, pitch_basis:RankingBasis):
        super().__init__(controller)
        self.controller = controller
        self.title("Advanced Inputs")
        self.frm = frm = tk.Frame(self, borderwidth=4)

        frm.pack(fill='both', expand=True)

        _ = frm.register(string_util.int_validation)

        self.option_dict = adv_calc_services.get_adv_option_dict()
        self.value_dict = {}

        row=0

        tk.Label(frm, text='Set Advanced Inputs', font='bold').grid(row=row, column=0, columnspan=2)

        row = row + 1

        if not ScoringFormat.is_points_type(s_format):
            if RankingBasis.is_roto_fractional(hit_basis):
                row = self.add_row('Target games filled by hitter:', CDT.BATTER_G_TARGET, row)
            if RankingBasis.is_roto_fractional(pitch_basis):
                row = self.add_row('Target IP filled:', CDT.IP_TARGET, row)
            #TODO: SGP info

        if rep_scheme == RepLevelScheme.FILL_GAMES:
            row = self.add_row('Target games filled by hitter:', CDT.BATTER_G_TARGET, row)
            if ScoringFormat.is_h2h(s_format):
                ##Fill Games
                row = self.add_row('SP Games per Week:', CDT.GS_LIMIT, row)
                row = self.add_row('Est. RP Games per Week:', CDT.RP_G_TARGET, row)
            else:
                #Fill IP
                row = self.add_row('Target IP filled:', CDT.IP_TARGET, row)
                row = self.add_row('Est. RP IP per team:', CDT.RP_IP_TARGET, row)
        
        tk.Button(frm, command=self.ok, text='OK', width=7).grid(row=row, column=0, padx=5)
        tk.Button(frm, command=self.cancel, text='Cancel', width=7).grid(row=row, column=1, padx=5)
    
    def add_row(self, label_txt:str, data_type:CDT, row:int) -> int:
        if self.value_dict.get(data_type, None) is None:
            tk.Label(self.frm, text=label_txt).grid(row=row, column=0)
            self.value_dict[data_type] = textvar = StringVar()
            tk.Entry(self.frm, textvariable=textvar).grid(row=row, column=1)
            textvar.set(self.option_dict.get(data_type).value)
            return row+1
        else:
            return row
    
    def ok(self):
        for cdt in self.value_dict:
            adv_calc_services.set_advanced_option(cdt, self.value_dict[cdt].get())
        self.destroy()

    def cancel(self):
        self.destroy()