import tkinter as tk

from domain.enum import ScoringFormat, RepLevelScheme, RankingBasis
from util import string_util

class Dialog(tk.Toplevel):
    def __init__(self, controller, format:ScoringFormat, rep_scheme:RepLevelScheme, hit_basis:RankingBasis, pitch_basis:RankingBasis):
        super().__init__(controller)
        self.controller = controller
        self.title("Advanced Inputs")
        frm = tk.Frame(self, borderwidth=4)

        frm.pack(fill='both', expand=True)

        validation = frm.register(string_util.int_validation)