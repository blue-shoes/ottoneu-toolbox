from datetime import datetime
import logging
import pathlib
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import filedialog as fd
from tkinter import messagebox as mb
from pathlib import Path
import pandas as pd
from typing import Dict, List

from ui.app_controller import Controller
from ui.toolbox_view import ToolboxView
from ui.table.table import Table
from domain.domain import ValueCalculation, PlayerProjection, CustomScoring, PositionSet, PlayerValue, StartingPositionSet
from domain.enum import CalculationDataType as CDT, RankingBasis, RepLevelScheme, StatType, Position, ProjectionType, ScoringFormat
from services import projection_services, calculation_services, adv_calc_services, custom_scoring_services, position_set_services, starting_positions_services
from ui.dialog import projection_select, progress, name_desc, advanced_calc, format_select, position_set_select, starting_select
from ui.dialog.wizard import projection_import, custom_scoring, starting_position
from ui.tool.tooltip import CreateToolTip
from util import string_util

player_columns = ('Value', 'Name', 'Team', 'Pos')
#fom_columns = ('P/G', 'HP/G', 'P/PA', 'P/IP', 'PP/G', 'Points', 'zScore', 'SGP')
h_fom_columns = ('P/G', 'HP/G', 'P/PA')
p_fom_columns = ('P/IP', 'PP/G', 'SABR P/IP', 'SABR PP/G', 'NSH P/IP', 'NSH PP/G', 'NSH SABR P/IP', 'NSH SABR PP/G')
point_cols = ('FG Pts', 'SABR Pts', 'NSH FG Pts', 'NSH SABR Pts')
points_hitting_columns = ('H', '2B', '3B', 'HR', 'BB', 'HBP', 'SB','CS')
points_pitching_columns = ('K','HA','BBA','HBPA','HRA','SV','HLD')
old_school_hitting_columns = ('R', 'HR', 'RBI', 'SB', 'AVG')
old_school_pitching_columns = ('W', 'SV', 'K', 'ERA', 'WHIP')
classic_hitting_columns = ('OBP', 'SLG', 'HR', 'R')
classic_pitching_columns = ('ERA', 'WHIP', 'HR/9', 'K')
all_hitting_stats = tuple([st.display for st in StatType.get_all_hit_stattype()])
all_pitching_stats = tuple([st.display for st in StatType.get_all_pitch_stattype()])
pt_hitter_columns = ('G', 'PA', 'AB')
pt_pitcher_columns = ('GP', 'GS', 'IP')
rev_cols = ('Name', 'Team', 'Pos') + tuple([st.display for st in StatType if not st.higher_better]) 
num_rost_rl_default = {'C':'24', '1B':'40', '2B':'38', 'SS':'42', '3B':'24', 'MI':'60', 'CI':'55', 'INF':'100', 'LF':'24', 'CF':'24', 'RF':'24', 'OF':'95', 'Util':'200', 'SP':'85', 'RP':'70'}

class ValuesCalculation(ToolboxView):

    value_calc:ValueCalculation
    custom_scoring:CustomScoring
    position_set:PositionSet
    starting_set:StartingPositionSet

    def __init__(self, parent:tk.Frame, controller:Controller):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        self.value_calc:ValueCalculation = self.controller.value_calculation
        self.rep_level_dict:Dict[Position, StringVar] = {}
        self.tables:Dict[Position, Table] = {}
        self.input_svs:List[StringVar] = []
        self.position_set = position_set_services.get_ottoneu_position_set()
        self.starting_set = starting_positions_services.get_ottoneu_position_set()

        self.create_input_frame()
        self.create_proj_val_frame()
        self.create_output_frame()
    
    def value_change(self):
        self.on_show()

    def on_show(self):
        self.value_calc = self.controller.value_calculation
        if self.controller.value_calculation is None:
            self.controller.value_calculation = ValueCalculation()
            self.value_calc = self.controller.value_calculation
            self.position_set = position_set_services.get_ottoneu_position_set()
            self.starting_set = starting_positions_services.get_ottoneu_position_set()
        else:
            self.position_set = self.value_calc.position_set
            self.starting_set = self.value_calc.starting_set
        if self.value_calc.format == ScoringFormat.CUSTOM:
            self.custom_scoring = custom_scoring_services.get_scoring_format(int(self.value_calc.get_input(CDT.CUSTOM_SCORING_FORMAT)))
            self.custom_scoring_button.grid(column=2, row=2)
        else:
            self.custom_scoring_button.grid_forget()
        self.refresh_ui()
        self.last_game_type.set(self.game_type.get())
        return True
    
    def leave_page(self):
        if self.value_calc.index is None and len(self.value_calc.values) > 0:
            ret = mb.askyesnocancel('Save Calculation', 'Do you want to save the last run value calculation?')
            if ret is None:
                return False
            if ret:
                self.save_values()
            else:
                self.controller.value_calculation = None
        return True
    
    def refresh_ui(self):
        pd = progress.ProgressDialog(self.parent, 'Updating Value Calculator Window...')
        pd.set_completion_percent(10)
        if self.value_calc is None or self.value_calc.format is None:
            self.game_type.set(ScoringFormat.FG_POINTS.full_name)
            self.sel_proj.set("None")
            self.projection = None
            self.custom_scoring = None
            self.custom_scoring_lbl.set("")
            self.position_set = position_set_services.get_ottoneu_position_set()
            self.position_set_lbl.set(self.position_set.name)
            self.starting_set = starting_positions_services.get_ottoneu_position_set()
            self.starting_set_lbl.set(self.starting_set.name)
            self.num_teams_str.set("12")
            self.manual_split.set(False)
            self.hitter_allocation.set("60")
            self.non_prod_dollars_str.set("300")
            self.hitter_basis.set('P/G')
            self.min_pa.set("150")
            self.pitcher_basis.set('P/IP')
            self.min_sp_ip.set("70")
            self.min_rp_ip.set("30")
            self.rep_level_scheme.set(RepLevelScheme.NUM_ROSTERED.value)
            self.set_default_rep_level(RepLevelScheme.NUM_ROSTERED)
            self.dollars_per_fom_val.set('$--')
            self.total_fom_sv.set("--")
            self.bat_rep_level_lbl.set("Rep. Level")
            for pos in Position.get_discrete_offensive_pos():
                self.pos_rostered_sv[pos].set('--')
                self.pos_rep_lvl_sv[pos].set('--')
            self.total_bat_rostered_sv.set('--')
            self.total_games_rostered_sv.set('--')
            self.pitch_rep_level_lbl.set("Rep. Level")
            for pos in Position.get_discrete_pitching_pos():
                self.pos_rostered_sv[pos].set('--')
                self.pos_rep_lvl_sv[pos].set('--')
            self.total_pitch_rostered_sv.set('--')
            self.total_ip_rostered_sv.set('--')
            self.set_display_columns()
        else:
            v = self.value_calc
            self.game_type.set(v.format.full_name)
            if v.projection is None:
                self.sel_proj.set("No Projection")
            else:
                self.sel_proj.set(v.projection.name)
            self.projection = v.projection
            if v.get_input(CDT.CUSTOM_SCORING_FORMAT) is not None:
                self.custom_scoring = custom_scoring_services.get_scoring_format(v.get_input(CDT.CUSTOM_SCORING_FORMAT))
                self.custom_scoring_lbl.set(self.custom_scoring.name)
            else:
                self.custom_scoring = None
                self.custom_scoring_lbl.set('')
            self.position_set = v.position_set
            self.position_set_lbl.set(self.position_set.name)
            self.starting_set = v.starting_set
            self.starting_set_lbl.set(self.starting_set.name)
            self.num_teams_str.set(int(v.get_input(CDT.NUM_TEAMS)))
            if v.get_input(CDT.HITTER_SPLIT) is None:
                self.manual_split.set(False)
                self.hitter_allocation.set("60")
            else:
                self.manual_split.set(True)
                self.hitter_allocation.set(int(v.get_input(CDT.HITTER_SPLIT)))
            include_svh = v.get_input(CDT.INCLUDE_SVH)
            if include_svh is None or include_svh == 1:
                self.sv_hld_bv.set(True)
            else:
                self.sv_hld_bv.set(False)
            self.safe_set_input_value(CDT.NON_PRODUCTIVE_DOLLARS, self.non_prod_dollars_str, True)
            self.hitter_basis.set(v.hitter_basis.display)
            self.safe_set_input_value(CDT.PA_TO_RANK, self.min_pa, True)
            self.pitcher_basis.set(v.pitcher_basis.display)
            self.safe_set_input_value(CDT.SP_IP_TO_RANK, self.min_sp_ip, True)
            self.safe_set_input_value(CDT.RP_IP_TO_RANK, self.min_rp_ip, True)
            neg_vals = v.get_input(CDT.NEGATIVE_VALUES)
            if neg_vals is None or neg_vals == 0:
                self.neg_dollar_values.set(False)
            else:
                self.neg_dollar_values.set(True)
            self.safe_set_input_value(CDT.REP_LEVEL_SCHEME, self.rep_level_scheme, True, RepLevelScheme.STATIC_REP_LEVEL.value)
            self.update_rep_level_scheme()
            off_pos = [p.position for p in self.starting_set.positions if p.position.offense]
            off_pos = [p for p in off_pos if Position.position_is_base(p, off_pos) or p == Position.POS_UTIL]

            if self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
                for pos in off_pos + Position.get_discrete_pitching_pos():
                    if pos.value not in self.rep_level_dict:
                        self.rep_level_dict[pos.value] = StringVar()
                    self.safe_set_input_value(CDT.pos_to_rep_level().get(pos), self.rep_level_dict[pos.value])
            else:
                for pos in off_pos + Position.get_discrete_pitching_pos():
                    if pos.value not in self.rep_level_dict:
                        self.rep_level_dict[pos.value] = StringVar()
                    self.safe_set_input_value(CDT.pos_to_num_rostered().get(pos), self.rep_level_dict[pos.value], True)
            for adv_inp in CDT.get_adv_inputs():
                inp = self.value_calc.get_input(adv_inp)
                if inp is not None:
                    adv_calc_services.set_advanced_option(adv_inp, inp)
            self.update_calc_output_frame()
        pd.set_completion_percent(33)
        if len(self.tables) > 0:
            for table in self.tables.values():
                if table:
                    table.refresh()
                    pd.increment_completion_percent(5)
        self.set_display_columns()
        pd.set_completion_percent(100)
        pd.destroy()

    def safe_set_input_value(self, data_type, string_var, integer=False, default='--', format='{:.3f}'):
        val = self.value_calc.get_input(data_type)
        self.safe_set_value(val, string_var, integer, default, format)
    
    def safe_set_output_value(self, data_type, string_var, integer=False, default='--', format='{:.3f}'):
        val = self.value_calc.get_output(data_type)
        self.safe_set_value(val, string_var, integer, default, format)
    
    def safe_set_value(self, val, string_var, integer=False, default='--', format='{:.3f}'):
        if val is None or val == -999:
            string_var.set(default)
        elif integer:
            string_var.set(int(val))
        else:
            string_var.set(format.format(val))

    def create_input_frame(self):

        self.input_frame = inpf = ttk.Frame(self)
        inpf.grid(column=0,row=0, padx=5, sticky=tk.N, pady=17)

        validation = inpf.register(string_util.int_validation)

        ttk.Label(inpf, text="Selected Projections:").grid(column=0,row=0, pady=5)
        self.sel_proj = tk.StringVar()
        self.sel_proj.set("None")
        self.projection = None
        ttk.Label(inpf, textvariable=self.sel_proj).grid(column=1,row=0)
        btn = ttk.Button(inpf, text="Select...", command=self.select_projection)
        btn.grid(column=2,row=0)
        CreateToolTip(btn, "Select a stored projection to use for value calculations or import a new one.")

        ttk.Label(inpf, text="Scoring Format:").grid(column=0,row=2,pady=5)
        self.game_type = StringVar()
        self.game_type.set(ScoringFormat.FG_POINTS.full_name)
        gt_combo = ttk.Combobox(inpf, textvariable=self.game_type)
        gt_combo.bind("<<ComboboxSelected>>", self.update_game_type)
        self.last_game_type = StringVar()
        self.last_game_type.set(self.game_type.get())

        gt_combo['values'] = (ScoringFormat.FG_POINTS.full_name, ScoringFormat.SABR_POINTS.full_name, ScoringFormat.H2H_FG_POINTS.full_name, ScoringFormat.H2H_SABR_POINTS.full_name, ScoringFormat.OLD_SCHOOL_5X5.full_name, ScoringFormat.CLASSIC_4X4.full_name, ScoringFormat.CUSTOM.full_name)
        gt_combo.grid(column=1,row=2,pady=5)

        self.custom_scoring_lbl = StringVar()
        self.custom_scoring_lbl.set("")
        self.custom_scoring = None
        self.custom_scoring_button = csb = ttk.Button(inpf, textvariable=self.custom_scoring_lbl, command=self.set_custom_scoring_format)
        csb.grid(column=2, row=2)
        CreateToolTip(csb, 'Select a non-Ottoneu scoring format for value creation')

        ttk.Label(inpf, text='Position Elig.').grid(column=0, row=3, pady=5)
        self.position_set_lbl = StringVar()
        self.position_set_lbl.set("")
        btn = ttk.Button(inpf, textvariable=self.position_set_lbl, command=self.set_position_set)
        btn.grid(column=1, row=3, pady=5)
        CreateToolTip(btn, 'Select a set of positional eligibilities for value creation')

        ttk.Label(inpf, text='Starting Positions').grid(column=0, row=4, pady=5)
        self.starting_set_lbl = StringVar()
        self.starting_set_lbl.set("")
        btn = ttk.Button(inpf, textvariable=self.starting_set_lbl, command=self.set_starting_set)
        btn.grid(column=1, row=4, pady=5)
        CreateToolTip(btn, 'Select a Starting Position Player Set for value creation')

        ttk.Label(inpf, text="Number of Teams:").grid(column=0, row=5,pady=5)
        self.num_teams_str = StringVar()
        self.num_teams_str.set("12")
        team_entry = ttk.Entry(inpf, textvariable=self.num_teams_str)
        team_entry.grid(column=1,row=5,pady=5)
        team_entry.config(validate="key", validatecommand=(validation, '%P'))
        self.input_svs.append(self.num_teams_str)

        lbl = ttk.Label(inpf, text="Manual hitter/pitcher split?")
        lbl.grid(column=0, row=6,pady=5)
        CreateToolTip(lbl, 'Indicate if value calculations should calculate hitter/pitcher value\nabove replacement intrinsically or by user percentage.')
        self.manual_split = BooleanVar()
        self.manual_split.set(False)
        self.manual_split_cb = cb = ttk.Checkbutton(inpf, variable=self.manual_split, command=self.toggle_manual_split)
        cb.grid(column=1, row=6, pady=5)
        CreateToolTip(cb, 'Indicate if value calculations should calculate hitter/pitcher value\nabove replacement intrinsically or by user percentage.')

        self.hitter_aloc_lbl = ttk.Label(inpf, text="Hitter allocation (%):")
        self.hitter_aloc_lbl.grid(column=0, row=7,pady=5)
        self.hitter_aloc_lbl.configure(state='disable')
        self.hitter_allocation = StringVar()
        self.hitter_allocation.set("60")
        self.hitter_aloc_entry = ttk.Entry(inpf, textvariable=self.hitter_allocation)
        self.hitter_aloc_entry.grid(column=1,row=7,pady=5)
        self.hitter_aloc_entry.configure(state='disable')
        self.input_svs.append(self.hitter_allocation)

        lbl = ttk.Label(inpf, text="Excess salaries:")
        lbl.grid(column=0, row=8,pady=5)
        CreateToolTip(lbl, text='Cap space set aside for below replacement level player salaries, such as prospects, or unspent cap space.')
        self.non_prod_dollars_str = StringVar()
        self.non_prod_dollars_str.set("300")
        non_prod = ttk.Entry(inpf, textvariable=self.non_prod_dollars_str)
        non_prod.grid(column=1,row=8,pady=5)
        non_prod.config(validate="key", validatecommand=(validation, '%P'))
        CreateToolTip(non_prod, text='Cap space set aside for below replacement level player salaries, such as prospects, or unspent cap space.')
        self.input_svs.append(self.non_prod_dollars_str)

        ttk.Label(inpf, text="Hitter Value Basis:").grid(column=0,row=9,pady=5)
        self.hitter_basis = StringVar()
        self.hitter_basis.set('P/G')
        self.hitter_basis_cb = hbcb = ttk.Combobox(inpf, textvariable=self.hitter_basis)
        hbcb['values'] = ('P/G','P/PA')
        hbcb.grid(column=1,row=9,pady=5)
        hbcb.bind("<<ComboboxSelected>>", self.update_ranking_basis)

        ttk.Label(inpf, text="Min PA to Rank:").grid(column=0, row=10, pady=5)
        self.min_pa = StringVar()
        self.min_pa.set("150")
        pa_entry = ttk.Entry(inpf, textvariable=self.min_pa)
        pa_entry.grid(column=1, row=10, pady=5)
        pa_entry.config(validate="key", validatecommand=(validation, '%P'))
        CreateToolTip(pa_entry, 'The minimum number of plate appearances required to be considered for valuation.')
        self.input_svs.append(self.min_pa)
        
        ttk.Label(inpf, text="Pitcher Value Basis:").grid(column=0, row=11, pady=5)
        self.pitcher_basis = StringVar()
        self.pitcher_basis.set('P/IP')
        self.pitcher_basis_cb = pbcb = ttk.Combobox(inpf, textvariable=self.pitcher_basis)
        pbcb['values'] = ('P/IP','P/G')
        pbcb.grid(column=1, row=11, pady=5)
        pbcb.bind("<<ComboboxSelected>>", self.update_ranking_basis)

        ttk.Label(inpf, text="Min SP IP to Rank:").grid(column=0, row=12, pady=5)
        self.min_sp_ip = StringVar()
        self.min_sp_ip.set("70")
        entry = ttk.Entry(inpf, textvariable=self.min_sp_ip)
        entry.grid(column=1, row=12, pady=5)
        CreateToolTip(entry, 'The minimum number of innings required by a full-time starter to be considered for valuation.')
        self.input_svs.append(self.min_sp_ip)

        ttk.Label(inpf, text="Min RP IP to Rank:").grid(column=0, row=13, pady=5)
        self.min_rp_ip = StringVar()
        self.min_rp_ip.set("30")
        entry = ttk.Entry(inpf, textvariable=self.min_rp_ip)
        entry.grid(column=1, row=13, pady=5)
        CreateToolTip(entry, 'The minimum number of innings required by a full-time reliever to be considered for valuation.')
        self.input_svs.append(self.min_rp_ip)

        self.sv_hld_lbl = ttk.Label(inpf, text="Include SV/HLD?")
        self.sv_hld_lbl.grid(column=0, row=14, pady=5)
        CreateToolTip(self.sv_hld_lbl, 'Calculate reliever values with or without projected save and hold values.')
        self.sv_hld_bv = BooleanVar()
        self.sv_hld_bv.set(True)
        self.sv_hld_entry = ttk.Checkbutton(inpf, variable=self.sv_hld_bv, command=self.set_display_columns)
        self.sv_hld_entry.grid(column=1, row=14, pady=5)
        CreateToolTip(self.sv_hld_entry, 'Calculate reliever values with or without projected save and hold values.')

        ttk.Label(inpf, text='Negative Dollar Values?').grid(row=15, column=0, pady=5)
        self.neg_dollar_values = BooleanVar()
        self.neg_dollar_values.set(False)
        self.neg_dollar_entry = ttk.Checkbutton(inpf, variable=self.neg_dollar_values)
        self.neg_dollar_entry.grid(column=1, row=15, pady=5)
        CreateToolTip(self.neg_dollar_entry, 'If not checked, all players at or below replacement level are valued at $0.')

        # This is its own method to make the __init__ more readable
        row = self.set_replacement_level_ui(inpf, start_row=16)

        ttk.Button(inpf, text="Calculate", command=self.calculate_values).grid(row=row, column=0, pady=3)
        self.advanced_btn = ttk.Button(inpf, text='Advanced', command=self.advanced_options)
        CreateToolTip(self.advanced_btn, 'Set advanced input options for the Value Calculation.')
        self.advanced_btn['state'] = DISABLED
        self.advanced_btn.grid(row=row, column=1, pady=3)

        inpf.update()
        csb.grid_forget()

    def create_proj_val_frame(self):
        self.proj_val_frame = pvf = ttk.Frame(self)
        pvf.grid(column=1,row=0,padx=5, sticky=tk.N, pady=17)

        self.tab_control = ttk.Notebook(pvf, width=570, height=self.input_frame.winfo_height())
        self.tab_control.grid(row=0, column=0)

        overall_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(overall_frame, text='Overall')

        bat_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(bat_frame, text='Hitters')

        arm_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(arm_frame, text='Pitchers')
        
        col_align = {}
        col_align['Name'] = W
        col_width = {}
        col_width['Name'] = 125

        #self.overall_table = ot = Table(overall_frame, self.player_columns + self.overall_columns, column_widths=col_width, column_alignments=col_align, sortable_columns=self.player_columns + self.overall_columns)
        cols = player_columns + h_fom_columns + p_fom_columns + point_cols
        self.overall_table = ot = Table(overall_frame, cols, column_widths=col_width, column_alignments=col_align, sortable_columns=cols, reverse_col_sort=rev_cols)
        self.tables[Position.OVERALL] = ot
        ot.set_refresh_method(self.refresh_overall)
        ot.grid(row=0, column=0)
        ot.add_scrollbar()

        hit_cols = player_columns + h_fom_columns + point_cols + all_hitting_stats

        self.bat_table = Table(bat_frame, hit_cols, column_widths=col_width, column_alignments=col_align, sortable_columns=hit_cols, reverse_col_sort=rev_cols)
        self.tables[Position.OFFENSE] = self.bat_table
        self.bat_table.set_refresh_method(lambda: self.refresh_hitters(Position.OFFENSE))
        self.bat_table.grid(row=0, column=0)
        self.bat_table.add_scrollbar()

        pitch_cols = player_columns + p_fom_columns + point_cols + all_pitching_stats

        self.arm_table = Table(arm_frame, pitch_cols, column_widths=col_width, column_alignments=col_align, sortable_columns=pitch_cols, reverse_col_sort=rev_cols)
        self.tables[Position.PITCHER] = self.arm_table
        self.arm_table.set_refresh_method(lambda: self.refresh_pitchers(Position.PITCHER))
        self.arm_table.grid(row=0,column=0)
        self.arm_table.add_scrollbar()

        self.create_position_tables()
    
    def create_position_tables(self):
        hit_cols = player_columns + h_fom_columns + point_cols + all_hitting_stats
        pitch_cols = player_columns + p_fom_columns + point_cols + all_pitching_stats

        col_align = {}
        col_align['Name'] = W
        col_width = {}
        col_width['Name'] = 125

        pos_list = Position.get_ordered_list([pos.position for pos in self.starting_set.positions])

        for pos in pos_list:
            if pos.offense:
                frame = ttk.Frame(self.tab_control)
                self.tab_control.add(frame, text=pos.value)
                pt = Table(frame, hit_cols, column_widths=col_width, column_alignments=col_align, sortable_columns=hit_cols, reverse_col_sort=rev_cols)
                self.tables[pos] = pt
                pt.set_refresh_method(lambda _pos=pos: self.refresh_hitters(_pos))
                pt.grid(row=0, column=0)
                pt.add_scrollbar()
            else:
                frame = ttk.Frame(self.tab_control)
                self.tab_control.add(frame, text=pos.value)
                pt = Table(frame, pitch_cols, column_widths=col_width, column_alignments=col_align, sortable_columns=pitch_cols, reverse_col_sort=rev_cols)
                self.tables[pos] = pt
                pt.set_refresh_method(lambda _pos=pos: self.refresh_pitchers(_pos))
                pt.grid(row=0, column=0)
                pt.add_scrollbar()
    
    def update_ranking_basis(self, event: Event):
        if RankingBasis.is_roto_fractional(RankingBasis.get_enum_by_display(self.hitter_basis.get()))\
            or RankingBasis.is_roto_fractional(RankingBasis.get_enum_by_display(self.pitcher_basis.get())):
            self.manual_split.set(True)
            self.manual_split_cb.configure(state='disable')
            self.toggle_manual_split()
        else:
            self.manual_split_cb.configure(state='active')
        self.set_display_columns()
        self.set_advanced_button_status()

    def set_starting_set(self) -> None:
        count = starting_positions_services.get_starting_set_count()
        if count == 0:
            dialog = starting_position.Dialog(self)
        else:
            dialog = starting_select.Dialog(self)
        if not dialog.starting_set:
            return
        reload = self.starting_set != dialog.starting_set
        self.starting_set = dialog.starting_set

        self.starting_set_lbl.set(dialog.starting_set.name)

        if reload:
            for pos, table in self.tables.items():
                if pos == Position.OVERALL or pos == Position.OFFENSE or pos == Position.PITCHER: continue
                if not table: continue
                for tab_id in self.tab_control.tabs():
                    item = self.tab_control.tab(tab_id)
                    if item['text']==pos.value:
                        self.tab_control.hide(tab_id)
                    self.tables[pos] = None 
            self.create_position_tables()
            pd = progress.ProgressDialog(self, title='Reloading Player Tables')
            pd.increment_completion_percent(15)
            for pos, table in self.tables.items():
                if pos == Position.OVERALL or pos == Position.OFFENSE or pos == Position.PITCHER: continue
                if table:
                    table.refresh()
                    pd.increment_completion_percent(5)
            self.set_display_columns()
            pd.complete()
            for widget in self.rep_level_frm.winfo_children():
                widget.destroy()
            self.create_replacement_level_rows()
            self.set_default_rep_level(RepLevelScheme._value2member_map_.get(self.rep_level_scheme.get()), update_only=True)
            for widget in self.offensive_par_frm.winfo_children():
                widget.destroy()
            self.set_offensive_par_outputs()

    def set_position_set(self) -> None:
        count = position_set_services.get_position_set_count()
        if count == 0:
            mb.showinfo('No available position sets', 'No non-standard position sets available.')
            return
        else:
            dialog = position_set_select.Dialog(self)
        reload = (dialog.pos_set != self.position_set)
        if dialog.pos_set is None:
            return
        else:
            self.position_set = dialog.pos_set
            self.position_set_lbl.set(dialog.pos_set.name)
        if reload:
            self.reload_player_positions()

    def reload_player_positions(self):
        if self.projection is None:
            return
        pd = progress.ProgressDialog(self, title='Reloading Player Positions')
        pd.increment_completion_percent(15)
        for pp in self.projection.player_projections:
            pp.player.custom_positions = self.position_set.get_player_positions(pp.player_id)
        pd.increment_completion_percent(20)
        if len(self.tables) > 0:
            for table in self.tables.values():
                if table:
                    table.refresh()
                    pd.increment_completion_percent(5)
        pd.complete()

    def set_custom_scoring_format(self) -> None:
        count = custom_scoring_services.get_format_count()
        if count == 0:
            dialog = custom_scoring.Dialog(self)
        else:
            dialog = format_select.Dialog(self)
        if dialog.scoring is None:
            self.game_type.set(self.last_game_type.get())
            return
        self.custom_scoring = dialog.scoring
        self.custom_scoring_lbl.set(dialog.scoring.name)
        self.custom_scoring_button.grid(column=2, row=2)

    def update_game_type(self, _:Event):
        if ScoringFormat.get_format_by_full_name(self.game_type.get()) == ScoringFormat.CUSTOM:
            self.set_custom_scoring_format()
        else:
            self.custom_scoring = None
            self.custom_scoring_lbl.set('')
            self.custom_scoring_button.grid_forget()
        sf = ScoringFormat.get_format_by_full_name(self.game_type.get())
        self.set_display_columns()
        self.set_advanced_button_status()
        if (sf == ScoringFormat.CUSTOM and self.custom_scoring is not None and self.custom_scoring.points_format) or ScoringFormat.is_points_type(sf):
            self.hitter_basis_cb['values'] = ('P/G','P/PA')
            if self.hitter_basis.get() not in self.hitter_basis_cb['values']:
                self.hitter_basis.set('P/G')
            self.pitcher_basis_cb['values'] = ('P/IP', 'P/G')
            if self.pitcher_basis.get() not in self.pitcher_basis_cb['values']:
                self.pitcher_basis.set('P/IP')
            self.static_rl_btn['state'] = ACTIVE
            self.sv_hld_entry['state'] = ACTIVE
            self.sv_hld_lbl['state'] = ACTIVE
        else:
            self.hitter_basis_cb['values'] = ('zScore', 'zScore/G')
            if self.hitter_basis.get() not in self.hitter_basis_cb['values']:
                self.hitter_basis.set('zScore')
            self.pitcher_basis_cb['values'] = ('zScore', 'zScore/IP')
            if self.pitcher_basis.get() not in self.pitcher_basis_cb['values']:
                self.pitcher_basis.set('zScore')
            self.static_rl_btn['state'] = DISABLED
            if self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
                self.rep_level_scheme.set(RepLevelScheme.NUM_ROSTERED.value)
                self.update_rep_level_scheme()
            self.sv_hld_entry['state'] = DISABLED
            self.sv_hld_lbl['state'] = DISABLED
        self.last_game_type.set(self.game_type.get())

    def select_projection(self):
        count = projection_services.get_projection_count()
        if count == 0:
            dialog = projection_import.Dialog(self)
            self.projection = dialog.projection
        else:
            dialog = projection_select.Dialog(self)
        if dialog.projection is not None:
            pd = progress.ProgressDialog(self, title='Loading Projection')
            pd.increment_completion_percent(15)
            self.projection = projection_services.get_projection(dialog.projection.index)
            pd.set_completion_percent(100)
            pd.destroy()
            self.sel_proj.set(self.projection.name)
            self.populate_projections()
        elif len(dialog.deleted_proj_ids) > 0:
                if self.projection is not None and self.projection.index in dialog.deleted_proj_ids:
                    self.projection = None
                    self.sel_proj.set("No Projection Selected")
                    self.populate_projections()
    
    def populate_projections(self, pd=None):
        if self.position_set and self.projection:
            for pp in self.projection.player_projections:
                pp.player.custom_positions = self.position_set.get_player_positions(pp.player_id)
        fresh_pd = False
        if pd is None:
            fresh_pd = True
            pd = progress.ProgressDialog(self, title='Refreshing Table')
            pd.set_completion_percent(25)
        delta = 75 / len(self.tables)
        for table in self.tables.values():
            if table:
                table.refresh()
                pd.increment_completion_percent(delta)
        self.set_display_columns()
        if fresh_pd:
            pd.set_completion_percent(100)
            pd.destroy()
    
    def append_player_column_data(self, val:PlayerValue, pp:PlayerProjection, pos:Position):
        if len(self.value_calc.values) > 0:
            pv = self.value_calc.get_player_value(pp.player.index, pos)
            if pv is None:
                val.append("$0.0")
            else:
                val.append("${:.1f}".format(pv.value))
        else:
            pv = None
            val.append('-')
        val.append(pp.player.name)
        val.append(pp.player.team)
        if pp.player.custom_positions:
            val.append(pp.player.custom_positions)
        else:
            val.append(pp.player.position)

    def get_overall_row(self, pp, derived):
        val = []
        self.append_player_column_data(val, pp, Position.OVERALL)
        
        if derived:
            val.append("{:.2f}".format(pp.get_stat(StatType.PPG)))
            val.append("{:.2f}".format(pp.get_stat(StatType.PPG)))
            val.append("{:.2f}".format(pp.get_stat(StatType.PPG)))
            val.append("{:.2f}".format(pp.get_stat(StatType.PIP)))
            val.append("{:.2f}".format(pp.get_stat(StatType.PIP)))
            val.append("{:.2f}".format(pp.get_stat(StatType.PIP)))
            val.append("{:.2f}".format(pp.get_stat(StatType.PIP)))
            val.append("{:.1f}".format(pp.get_stat(StatType.POINTS)))
            val.append("{:.1f}".format(pp.get_stat(StatType.POINTS)))
        else:
            o_points = calculation_services.get_points(pp, Position.OFFENSE, sabr=ScoringFormat.is_sabr(ScoringFormat.get_format_by_full_name(self.game_type.get())), custom_format=self.custom_scoring)
            games = pp.get_stat(StatType.G_HIT)
            if games is None or games == 0:
                val.append("0.00")
                val.append("0.00")
            else:
                val.append("{:.2f}".format(o_points / games))
                val.append("{:.2f}".format(o_points / games))
            pa = pp.get_stat(StatType.PA)
            if pa is None or pa == 0:
                val.append("0.00")
            else:
                val.append("{:.2f}".format(o_points / pa))
            
            p_points = calculation_services.get_points(pp, Position.PITCHER, sabr=False, custom_format=self.custom_scoring)
            s_p_points = calculation_services.get_points(pp, Position.PITCHER, sabr=True, custom_format=self.custom_scoring)
            nsh_p_points = calculation_services.get_points(pp, Position.PITCHER, sabr=False, no_svh=True, custom_format=self.custom_scoring)
            nsh_s_p_points = calculation_services.get_points(pp, Position.PITCHER, sabr=True, no_svh=True, custom_format=self.custom_scoring)
            ip = pp.get_stat(StatType.IP)
            games = pp.get_stat(StatType.G_PIT)
            if ip is None or ip == 0 or games is None or games == 0:
                val.append("0.00")
                val.append("0.00")
                val.append("0.00")
                val.append("0.00")
                val.append("0.00")
                val.append("0.00")
                val.append("0.00")
                val.append("0.00")
            else:
                val.append("{:.2f}".format(p_points/ip))
                val.append("{:.2f}".format(p_points/games))
                val.append("{:.2f}".format(s_p_points/ip))
                val.append("{:.2f}".format(s_p_points/games))
                val.append("{:.2f}".format(nsh_p_points/ip))
                val.append("{:.2f}".format(nsh_p_points/games))
                val.append("{:.2f}".format(nsh_s_p_points/ip))
                val.append("{:.2f}".format(nsh_s_p_points/games))

            val.append("{:.1f}".format(p_points + o_points))
            val.append("{:.1f}".format(s_p_points + o_points))
            val.append("{:.1f}".format(nsh_p_points + o_points))
            val.append("{:.1f}".format(nsh_s_p_points + o_points))
        return val
    
    def get_overall_row_no_proj(self, player_id):
        val = []
        pv = self.value_calc.get_player_value(player_id, Position.OVERALL)
        if pv is None:
            val.append("$0.0")
        else:
            val.append("${:.1f}".format(pv.value))
        val.append(pv.player.name)
        val.append(pv.player.team)
        if pv.player.custom_positions:
            val.append(pv.player.custom_positions)
        else:
            val.append(pv.player.position)
        return val

    def get_player_row(self, pp:PlayerProjection, hitter:bool, cols, pos):
        val = []
        if len(self.value_calc.values) > 0:
            pv = self.value_calc.get_player_value(pp.player.index, pos)
            if pv is None:
                val.append("$0.0")
            else:
                val.append("${:.1f}".format(pv.value))
        else:
            val.append('-')
        val.append(pp.player.name)
        val.append(pp.player.team)
        if pp.player.custom_positions:
            val.append(pp.player.custom_positions)
        else:
            val.append(pp.player.position)
        
        if pos.offense:
            if self.projection.type == ProjectionType.VALUE_DERIVED:
                val.append(pp.get_stat(StatType.PPG)) # p/g
                val.append(pp.get_stat(StatType.PPG)) # hp/g
                val.append(pp.get_stat(StatType.PPG)) # p/pa
                f_points = pp.get_stat(StatType.POINTS)
                s_points = f_points
                nsh_f_points = f_points
                nsh_s_points = f_points
            else:
                f_points = calculation_services.get_points(pp, pos, sabr=False, custom_format=self.custom_scoring)
                s_points = f_points
                nsh_f_points = f_points
                nsh_s_points = f_points
                games = pp.get_stat(StatType.G_HIT)
                if games is None or games == 0:
                    val.append("0.00") # p/g
                    val.append("0.00") # hp/g
                    val.append("0.00") # p/pa
                else:
                    val.append("{:.2f}".format(f_points / games)) # p/g
                    val.append("{:.2f}".format(f_points / games)) # hp/g
                    try:
                        val.append("{:.2f}".format(f_points / pp.get_stat(StatType.PA))) # p/pa
                    except ZeroDivisionError:
                        val.append(0)
        else:
            if self.projection.type == ProjectionType.VALUE_DERIVED:
                val.append(pp.get_stat(StatType.PIP)) # p/ip
                val.append(pp.get_stat(StatType.PIP)) # pp/g
                val.append(pp.get_stat(StatType.PIP)) # s_p/ip
                val.append(pp.get_stat(StatType.PIP)) # s_pp/g
                val.append(pp.get_stat(StatType.PIP)) # p/ip
                val.append(pp.get_stat(StatType.PIP)) # pp/g
                val.append(pp.get_stat(StatType.PIP)) # s_p/ip
                val.append(pp.get_stat(StatType.PIP)) # s_pp/g
                f_points = pp.get_stat(StatType.POINTS)
                s_points = f_points
                nsh_f_points = f_points
                nsh_s_points = f_points
            else:
                f_points = calculation_services.get_points(pp, pos, sabr=False, custom_format=self.custom_scoring)
                s_points = calculation_services.get_points(pp, pos, sabr=True, custom_format=self.custom_scoring)
                nsh_f_points = calculation_services.get_points(pp, pos, sabr=False, no_svh=True, custom_format=self.custom_scoring)
                nsh_s_points = calculation_services.get_points(pp, pos, sabr=True, no_svh=True, custom_format=self.custom_scoring)
                ip = pp.get_stat(StatType.IP)
                games = pp.get_stat(StatType.G_PIT)
                if ip is None or ip == 0 or games is None or games == 0:
                    val.append("0.00") # p/ip
                    val.append("0.00") # pp/g
                    val.append("0.00") # s_p/ip
                    val.append("0.00") # s_pp/g
                    val.append("0.00") # p/ip
                    val.append("0.00") # pp/g
                    val.append("0.00") # s_p/ip
                    val.append("0.00") # s_pp/g
                else:
                    try:
                        val.append("{:.2f}".format(f_points/ip))
                    except ZeroDivisionError:
                        val.append(0)
                    val.append("{:.2f}".format(f_points/games))
                    try:
                        val.append("{:.2f}".format(s_points/ip))
                    except ZeroDivisionError:
                        val.append(0)
                    val.append("{:.2f}".format(s_points/games))
                    try:
                        val.append("{:.2f}".format(nsh_f_points/ip))
                    except ZeroDivisionError:
                        val.append(0)
                    val.append("{:.2f}".format(nsh_f_points/games))
                    try:
                        val.append("{:.2f}".format(nsh_s_points/ip))
                    except ZeroDivisionError:
                        val.append(0)
                    val.append("{:.2f}".format(nsh_s_points/games))
        val.append("{:.1f}".format(f_points))
        val.append("{:.1f}".format(s_points))
        val.append("{:.1f}".format(nsh_f_points))
        val.append("{:.1f}".format(nsh_s_points))
        if self.projection.type != ProjectionType.VALUE_DERIVED:
            for col in cols:
                if hitter:
                    stat_type = StatType.get_hit_stattype(col)
                else:
                    stat_type = StatType.get_pitch_stattype(col)
                if stat_type is not None:
                    stat = pp.get_stat(stat_type)
                    if stat is None:
                        val.append(stat_type.format.format(0))
                    else:
                        val.append(stat_type.format.format(stat))
        return val
    
    def get_player_row_no_proj(self, player_id, pos, cols):
        val = []
        pv = self.value_calc.get_player_value(player_id, pos)
        if pv is None:
            return None
        else:
            val.append("${:.1f}".format(pv.value))
        val.append(pv.player.name)
        val.append(pv.player.team)
        if pv.player.custom_positions:
            val.append(pv.player.custom_positions)
        else:
            val.append(pv.player.position)
        val.append('0.00') # rate
        val.append('0.0') # points
        for col in cols:
            val.append('0.0')
        return val
    
    def refresh_overall(self):
        if self.projection is not None:
            for pp in self.projection.player_projections:
                val = self.get_overall_row(pp, self.projection.type == ProjectionType.VALUE_DERIVED)
                self.tables[Position.OVERALL].insert('', tk.END, text=str(pp.player_id), values=val)
        elif self.value_calc is not None and self.value_calc.values is not None and len(self.value_calc.values) > 0:
            for player_id in self.value_calc.value_dict:
                val = self.get_overall_row_no_proj(player_id)
                self.tables[Position.OVERALL].insert('',  tk.END, text=str(player_id), values=val)

    def refresh_hitters(self, pos):
        if self.projection is not None:
            for pp in self.projection.player_projections:
                if pp.player.pos_eligible(pos) and not pp.pitcher:
                    if self.projection.type == ProjectionType.VALUE_DERIVED:
                        val = self.get_player_row(pp, True, all_hitting_stats, pos)
                    elif pp.get_stat(StatType.AB) is not None:
                        val = self.get_player_row(pp, True, all_hitting_stats, pos)
                    self.tables[pos].insert('', tk.END, text=str(pp.player_id), values=val)
        elif self.value_calc is not None and self.value_calc.values is not None and len(self.value_calc.values) > 0:
            hit_col = player_columns + h_fom_columns + point_cols + all_hitting_stats
            for player_id in self.value_calc.value_dict:
                val = self.get_player_row_no_proj(player_id, pos, hit_col)
                if val is not None:
                    self.tables[pos].insert('',  tk.END, text=str(player_id), values=val)
    
    def refresh_pitchers(self, pos):
        if self.projection is not None:
            for pp in self.projection.player_projections:
                if self.projection.type == ProjectionType.VALUE_DERIVED:
                    if pp.player.pos_eligible(pos) and pp.pitcher:
                        val = self.get_player_row(pp, False, all_pitching_stats, pos)
                        self.tables[pos].insert('', tk.END, text=str(pp.player_id), values=val)
                elif pp.get_stat(StatType.IP) is not None:
                    if  pos == Position.PITCHER \
                        or (pos == Position.POS_RP and pp.get_stat(StatType.G_PIT) > pp.get_stat(StatType.GS_PIT)) \
                        or (pos == Position.POS_SP and pp.get_stat(StatType.GS_PIT) > 0):
                            val = self.get_player_row(pp, False, all_pitching_stats, pos)
                            self.tables[pos].insert('', tk.END, text=str(pp.player_id), values=val)
        elif self.value_calc is not None and self.value_calc.values is not None and len(self.value_calc.values) > 0:
            pitch_cols = player_columns + p_fom_columns + point_cols + all_pitching_stats
            for player_id in self.value_calc.value_dict:
                val = self.get_player_row_no_proj(player_id, pos, pitch_cols)
                if val is not None:
                    self.tables[pos].insert('',  tk.END, text=str(player_id), values=val)
    
    def create_output_frame(self):
        self.output_frame = outf = ttk.Frame(self)
        outf.grid(column=2,row=0, padx=5, sticky=tk.N, pady=17)

        self.output_title = StringVar()
        self.output_title.set('Create or Load Player Value Set')
        ttk.Label(outf, textvariable=self.output_title).grid(row=0, column=0)

        self.dollars_per_fom_lbl = StringVar()
        self.dollars_per_fom_lbl.set('Calculated $/PAR')
        ttk.Label(outf, textvariable=self.dollars_per_fom_lbl).grid(row=1, column=0)

        self.dollars_per_fom_val = StringVar()
        self.dollars_per_fom_val.set('$--')
        ttk.Label(outf, textvariable=self.dollars_per_fom_val).grid(row=1,column=1)

        self.total_fom_lbl_sv = StringVar()
        self.total_fom_lbl_sv.set("Total PAR:")
        ttk.Label(outf, textvariable=self.total_fom_lbl_sv).grid(row=2, column=0)
        self.total_fom_sv = StringVar()
        self.total_fom_sv.set("--")
        ttk.Label(outf, textvariable=self.total_fom_sv).grid(row=2, column=1)

        row = 3
        self.pos_rostered_sv = {}
        self.pos_rep_lvl_sv = {}

        self.offensive_par_frm = ttk.Frame(outf)
        self.offensive_par_frm.grid(row=row, column=0, columnspan=3)

        self.set_offensive_par_outputs()
        row += 1
        
        ttk.Label(outf, text="Total Batters Rostered:").grid(row=row, column=0)
        self.total_bat_rostered_sv = StringVar()
        self.total_bat_rostered_sv.set("--")
        ttk.Label(outf, textvariable=self.total_bat_rostered_sv).grid(row=row, column=1)
        row += 1
        
        ttk.Label(outf, text="Total Games Rostered:").grid(row=row, column=0)
        self.total_games_rostered_sv = StringVar()
        self.total_games_rostered_sv.set("--")
        ttk.Label(outf, textvariable=self.total_games_rostered_sv).grid(row=row, column=1)
        row += 1
        
        pitching_par_frm = ttk.Frame(outf)
        pitching_par_frm.grid(row=row, column=0, columnspan=3)

        ttk.Label(pitching_par_frm, text="Position", font='bold').grid(row=0, column=0, padx=6)
        ttk.Label(pitching_par_frm, text="# Rostered", font='bold').grid(row=0, column=1, padx=6)
        self.pitch_rep_level_lbl = StringVar()
        self.pitch_rep_level_lbl.set("Rep. Level")
        ttk.Label(pitching_par_frm, textvariable=self.pitch_rep_level_lbl, font='bold').grid(row=0, column=2, padx=6)

        row2 = 0

        for pos in Position.get_discrete_pitching_pos():
            row2 += 1
            ttk.Label(pitching_par_frm, text=pos.value).grid(row=row2, column=0)
            pos_rep = StringVar()
            pos_rep.set("--")
            self.pos_rostered_sv[pos] = pos_rep
            ttk.Label(pitching_par_frm, textvariable=pos_rep).grid(row=row2, column=1)
            rep_lvl = StringVar()
            rep_lvl.set("--")
            self.pos_rep_lvl_sv[pos] = rep_lvl
            ttk.Label(pitching_par_frm, textvariable=rep_lvl).grid(row=row2, column=2)
            
        row += 1
        
        ttk.Label(outf, text="Total Pitchers Rostered:").grid(row=row, column=0)
        self.total_pitch_rostered_sv = StringVar()
        self.total_pitch_rostered_sv.set("--")
        ttk.Label(outf, textvariable=self.total_pitch_rostered_sv).grid(row=row, column=1)
        row += 1
        
        ttk.Label(outf, text="Total IP Rostered:").grid(row=row, column=0)
        self.total_ip_rostered_sv = StringVar()
        self.total_ip_rostered_sv.set("--")
        ttk.Label(outf, textvariable=self.total_ip_rostered_sv).grid(row=row, column=1)
        row += 1

        self.save_btn = sb = ttk.Button(outf, text="Save Values", command=self.save_values)
        sb.grid(row=row, column=0)
        sb['state'] = DISABLED
        CreateToolTip(sb, 'Save the last set of calculated values to the database.')

        self.export_btn = eb = ttk.Button(outf, text="Export Values", command=self.export_values)
        eb.grid(row=row, column=1)
        eb['state'] = DISABLED
        CreateToolTip(eb, 'Export the last set of calculated values to a csv or xlsx file.')

    def set_offensive_par_outputs(self) -> None:
        positions = [p.position for p in self.starting_set.positions if p.position.offense]
        positions = Position.get_ordered_list([p for p in positions if Position.position_is_base(p, positions) or p == Position.POS_UTIL])

        row = 0

        ttk.Label(self.offensive_par_frm, text="Position", font='bold').grid(row=row, column=0, padx=6)
        ttk.Label(self.offensive_par_frm, text="# Rostered", font='bold').grid(row=row, column=1, padx=6)
        self.bat_rep_level_lbl = StringVar()
        self.bat_rep_level_lbl.set("Rep. Level")
        ttk.Label(self.offensive_par_frm, textvariable=self.bat_rep_level_lbl, font='bold').grid(row=row, column=2, padx=6)
        row += 1

        for pos in positions:
            if Position.position_is_base(pos, positions) or pos == Position.POS_UTIL:
                ttk.Label(self.offensive_par_frm, text=pos.value).grid(row=row, column=0)
                pos_rep = self.pos_rostered_sv.get(pos, None)
                if not pos_rep:
                    pos_rep = StringVar()
                    pos_rep.set('--')
                    self.pos_rostered_sv[pos] = pos_rep
                pos_rep = StringVar()
                pos_rep.set("--")
                self.pos_rostered_sv[pos] = pos_rep
                ttk.Label(self.offensive_par_frm, textvariable=pos_rep).grid(row=row, column=1)
                rep_lvl = self.pos_rep_lvl_sv.get(pos, None)
                if not rep_lvl:
                    rep_lvl = StringVar()
                    rep_lvl.set("--")
                    self.pos_rep_lvl_sv[pos] = rep_lvl
                ttk.Label(self.offensive_par_frm, textvariable=rep_lvl).grid(row=row, column=2)
                row += 1

    def update_calc_output_frame(self):
        self.output_title.set("Value Calculation Results")
        if self.manual_split.get():
            self.dollars_per_fom_val.set('$' + "{:.3f}".format(self.value_calc.get_output(CDT.HITTER_DOLLAR_PER_FOM)) + '(Bat), $' + "{:.3f}".format(self.value_calc.get_output(CDT.PITCHER_DOLLAR_PER_FOM)) + '(Arm)')
        else:
            dol_per = self.value_calc.get_output(CDT.DOLLARS_PER_FOM)
            if dol_per is None:
                self.dollars_per_fom_val.set('---')
            else:
                self.dollars_per_fom_val.set('$' + "{:.3f}".format(dol_per))
        
        self.safe_set_output_value(CDT.TOTAL_FOM_ABOVE_REPLACEMENT, self.total_fom_sv, format="{:.0f}")
        self.safe_set_output_value(CDT.TOTAL_HITTERS_ROSTERED, self.total_bat_rostered_sv, integer=True)
        self.safe_set_output_value(CDT.TOTAL_PITCHERS_ROSTERED, self.total_pitch_rostered_sv, integer=True)
        self.safe_set_output_value(CDT.TOTAL_GAMES_PLAYED, self.total_games_rostered_sv, format="{:.0f}")
        self.safe_set_output_value(CDT.TOTAL_INNINGS_PITCHED, self.total_ip_rostered_sv, format="{:.0f}")
        hitter_rb = self.value_calc.hitter_basis.display
        self.bat_rep_level_lbl.set(f"Rep. Level ({hitter_rb})")
        pitcher_rb = self.value_calc.pitcher_basis.display
        self.pitch_rep_level_lbl.set(f"Rep. Level ({pitcher_rb})")

        off_pos = [p.position for p in self.starting_set.positions if p.position.offense]
        off_pos = [p for p in off_pos if Position.position_is_base(p, off_pos) or p == Position.POS_UTIL]

        for pos in off_pos + Position.get_discrete_pitching_pos():
            if pos not in self.pos_rostered_sv:
                self.pos_rostered_sv[pos] = StringVar()
                self.pos_rep_lvl_sv[pos] = StringVar()
            self.safe_set_output_value(CDT.pos_to_num_rostered()[pos], self.pos_rostered_sv[pos], integer=True, default='--')
            self.safe_set_output_value(CDT.pos_to_rep_level()[pos], self.pos_rep_lvl_sv[pos], format="{:.2f}")
        
        self.save_btn['state'] = ACTIVE
        self.export_btn['state'] = ACTIVE
    
    def save_values(self):
        dialog = name_desc.Dialog(self, 'Save Values')
        if dialog.status == mb.OK:
            pd = progress.ProgressDialog(self, title='Saving Calculation')
            pd.increment_completion_percent(5)
            self.value_calc.name = dialog.name_tv.get()
            self.value_calc.description = dialog.desc_tv.get()
            self.value_calc.timestamp = datetime.now()
            self.value_calc = calculation_services.save_calculation(self.value_calc)
            self.controller.value_calculation = self.value_calc
            self.projection = self.value_calc.projection
            pd.set_completion_percent(100)
            pd.destroy()
    
    def export_values(self):
        filetypes = (
            ('csv files', '*.csv'),
            ('Excel Workbook', '*.xlsx'),
            ('All files', '*.*')
        )

        file = fd.asksaveasfilename(
            title='Save As...',
            initialdir=Path.home(),
            filetypes=filetypes
            )

        if file is None:
            return

        if pathlib.Path(file).suffix == '.xlsx':
            #Output full value set to Excel sheet
            with pd.ExcelWriter(file, engine='xlsxwriter') as writer:
                dol_fmt = writer.book.add_format({'num_format': '$##0.0'})
                positions = []
                positions.append(Position.OVERALL)
                positions.append(Position.OFFENSE)
                positions.append(Position.PITCHER)
                positions.extend(Position.get_ordered_list([p.position for p in self.starting_set.positions]))

                for pos in positions:
                    df = calculation_services.get_dataframe_with_values(self.value_calc, pos, text_values=False)
                    df.to_excel(writer, sheet_name=pos.value)
                    if pos == Position.OVERALL:
                        
                        writer.sheets[pos.value].set_column(4, 4, None, dol_fmt)
                    else:
                        writer.sheets[pos.value].set_column(1, 1, None, dol_fmt)
        else:
            #Output just overall values in csv format
            df = calculation_services.get_dataframe_with_values(self.value_calc, Position.OVERALL)
            df.to_csv(file, encoding='utf-8-sig')

    def toggle_manual_split(self):
        if self.manual_split.get():
            self.hitter_aloc_lbl.configure(state='active')
            self.hitter_aloc_entry.configure(state='active')
        else:
            self.hitter_aloc_lbl.configure(state='disable')
            self.hitter_aloc_entry.configure(state='disable')
    
    def set_display_columns(self, event=None):
        overall = []
        hit = []
        pitch = []
        overall.extend(player_columns)
        hit.extend(player_columns)
        pitch.extend(player_columns)
        if self.projection is not None:
            h_basis = RankingBasis.get_enum_by_display(self.hitter_basis.get())
            p_basis = RankingBasis.get_enum_by_display(self.pitcher_basis.get())
            scoring_format = ScoringFormat.get_format_by_full_name(self.game_type.get())
            if ScoringFormat.is_points_type(scoring_format):
                if self.sv_hld_bv.get():
                    prefix = ''
                else:
                    prefix = 'NSH '
                if h_basis == RankingBasis.PPG:
                    if p_basis == RankingBasis.PPG:
                        overall.append('HP/G')
                    else:
                        overall.append("P/G")
                    hit.append("P/G")
                elif h_basis == RankingBasis.PPPA:
                    overall.append("P/PA")
                    hit.append("P/PA")
                if p_basis == RankingBasis.PPG:
                    if ScoringFormat.is_sabr(scoring_format):
                        overall.append(f"{prefix}SABR PP/G")
                        pitch.append(f"{prefix}SABR PP/G")
                    else:
                        overall.append(f"{prefix}PP/G")
                        pitch.append(f"{prefix}PP/G")
                elif p_basis == RankingBasis.PIP:
                    if ScoringFormat.is_sabr(scoring_format):
                        overall.append(f"{prefix}SABR P/IP")
                        pitch.append(f"{prefix}SABR P/IP")
                    else:
                        overall.append(f"{prefix}P/IP")
                        pitch.append(f"{prefix}P/IP")
                if ScoringFormat.is_sabr(scoring_format):
                    overall.append(f"{prefix}SABR Pts")
                    pitch.append(f"{prefix}SABR Pts")
                else:
                    overall.append(f"{prefix}FG Pts")
                    pitch.append(f"{prefix}FG Pts")
                hit.append("FG Pts")
                if self.projection.type != ProjectionType.VALUE_DERIVED:
                    hit.extend(pt_hitter_columns)
                    hit.extend(points_hitting_columns)
                    pitch.extend(pt_pitcher_columns)
                    pitch.extend(points_pitching_columns)
            elif scoring_format == ScoringFormat.OLD_SCHOOL_5X5:
                hit.extend(pt_hitter_columns)
                hit.extend(old_school_hitting_columns)
                pitch.extend(pt_pitcher_columns)
                pitch.extend(old_school_pitching_columns)
            elif scoring_format == ScoringFormat.CLASSIC_4X4:
                hit.extend(pt_hitter_columns)
                hit.extend(classic_hitting_columns)
                pitch.extend(pt_pitcher_columns)
                pitch.extend(classic_pitching_columns)
            elif scoring_format == ScoringFormat.CUSTOM and self.custom_scoring is not None:
                hit.extend(pt_hitter_columns)
                pitch.extend(pt_pitcher_columns)
                hit_cats = []
                pitch_cats = []
                for cat in self.custom_scoring.stats:
                    stat = cat.category
                    if stat.hitter and stat.display not in pt_hitter_columns:
                        hit_cats.append(stat)
                    if not stat.hitter and stat.display not in pt_pitcher_columns:
                        pitch_cats.append(stat)
                hit_cats = sorted(hit_cats, key=lambda s: s.rank)
                hit.extend([s.display for s in hit_cats])
                pitch_cats = sorted(pitch_cats, key=lambda s: s.rank)
                pitch.extend([s.display for s in pitch_cats])
        self.overall_table.set_display_columns(tuple(overall))
        for pos, table in self.tables.items():
            if pos == Position.OVERALL: continue
            if table:
                if pos.offense:
                    table.set_display_columns(tuple(hit))
                else:
                    table.set_display_columns(tuple(pitch))
    
    def set_replacement_level_ui(self, inpf, start_row:int):
        row = start_row
        ttk.Label(inpf, text="Select Replacement Level Scheme").grid(column=0,row=row,columnspan=3,pady=5)

        self.rep_level_scheme = IntVar()
        self.rep_level_scheme.set(RepLevelScheme.NUM_ROSTERED.value)
        row = row+1
        btn = ttk.Radiobutton(inpf, text="Number Rostered", value=RepLevelScheme.NUM_ROSTERED.value, command=self.update_rep_level_scheme, variable=self.rep_level_scheme)
        btn.grid(column=0,row=row,pady=5)
        CreateToolTip(btn, 'Sets the number of players eligible at the given position that are at or above replacement level.')
        self.static_rl_btn = btn = ttk.Radiobutton(inpf, text="Replacement Level", value=RepLevelScheme.STATIC_REP_LEVEL.value, command=self.update_rep_level_scheme, variable=self.rep_level_scheme)
        btn.grid(column=1,row=row,pady=5)
        CreateToolTip(btn, 'Sets the static replacement level value (in units corresponding to the selected basis) to use for calculations.')
        btn = ttk.Radiobutton(inpf, text="Fill Games", value=RepLevelScheme.FILL_GAMES.value, command=self.update_rep_level_scheme, variable=self.rep_level_scheme)
        btn.grid(column=2,row=row,pady=5)
        CreateToolTip(btn, 'Determines the number of players required to be rostered at each position to reach game\nand inning thresholds and adds or subtracts the user-entered number from that positon.\nSee "Advanced" for more inputs.')
    
        row = row+1
        self.rep_level_txt = StringVar()
        self.rep_level_txt.set("Set number of rostered players at each position:")
        ttk.Label(inpf, textvariable=self.rep_level_txt).grid(column=0, row=row, columnspan=3, pady=5)
        
        row = row+1

        self.rep_level_frm = rlf = ttk.Frame(inpf)
        rlf.grid(row=row, column = 0, columnspan=3)

        self.create_replacement_level_rows()

        row += 1

        return row
    
    def create_replacement_level_rows(self) -> None:
        count = 0
        positions = [p.position for p in self.starting_set.positions if p.position.offense]
        positions = Position.get_ordered_list(positions)
        for pos in positions + Position.get_discrete_pitching_pos():
            if Position.position_is_base(pos, positions) or pos == Position.POS_UTIL:
                ttk.Label(self.rep_level_frm, text=pos.value).grid(row=int(count/2), column=count%2*2, pady=2, padx=5)
                rl = self.rep_level_dict.get(pos.value, None)
                if not rl:
                    rl = StringVar()
                    self.rep_level_dict[pos.value] = rl

                ttk.Entry(self.rep_level_frm, textvariable=rl).grid(row=int(count/2),column=count%2*2+1, pady=2, padx=5)
                count += 1

    def update_rep_level_scheme(self):
        if self.rep_level_scheme.get() == RepLevelScheme.NUM_ROSTERED.value:
            self.rep_level_txt.set("Set number of rostered players for each position:")
            self.set_default_rep_level(RepLevelScheme.NUM_ROSTERED)
        elif self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
            self.rep_level_txt.set("Set replacement level production for each position:")
            self.set_default_rep_level(RepLevelScheme.STATIC_REP_LEVEL)
        else:
            self.rep_level_txt.set("Set number of rostered players beyond games filled for each position:")
            self.set_default_rep_level(RepLevelScheme.FILL_GAMES)
        self.set_advanced_button_status()
    
    def advanced_options(self):
        advanced_calc.Dialog(self, ScoringFormat.get_format_by_full_name(self.game_type.get()), RepLevelScheme.get_enum_by_num(self.rep_level_scheme.get()),
            RankingBasis.get_enum_by_display(self.hitter_basis.get()), RankingBasis.get_enum_by_display(self.pitcher_basis.get()))

    def calculate_values(self):
        try:
            if self.has_errors():
                logging.warning("Input errors")
                return
        except Exception as Argument:
            mb.showerror("Error starting calculation", 'There was an error checking inputs. Please see the logs.')
            logging.exception("Errors validating calculation inputs")
            return
        self.value_calc = ValueCalculation()
        self.value_calc.projection = self.projection
        self.value_calc.position_set = self.position_set
        self.value_calc.starting_set = self.starting_set
        self.value_calc.format = ScoringFormat.get_format_by_full_name(self.game_type.get())
        self.value_calc.inputs = []
        if self.value_calc.format == ScoringFormat.CUSTOM:
            self.value_calc.set_input(CDT.CUSTOM_SCORING_FORMAT, int(self.custom_scoring.id))
        self.value_calc.set_input(CDT.NUM_TEAMS, float(self.num_teams_str.get()))
        if self.manual_split.get():
            self.value_calc.set_input(CDT.HITTER_SPLIT, float(self.hitter_allocation.get()))
        self.value_calc.set_input(CDT.NON_PRODUCTIVE_DOLLARS, int(self.non_prod_dollars_str.get()))
        self.value_calc.hitter_basis = RankingBasis.get_enum_by_display(self.hitter_basis.get())
        self.value_calc.set_input(CDT.PA_TO_RANK, float(self.min_pa.get()))
        self.value_calc.pitcher_basis = RankingBasis.get_enum_by_display(self.pitcher_basis.get())
        self.value_calc.set_input(CDT.SP_IP_TO_RANK, float(self.min_sp_ip.get()))
        self.value_calc.set_input(CDT.RP_IP_TO_RANK, float(self.min_rp_ip.get()))
        self.value_calc.set_input(CDT.INCLUDE_SVH, float(self.sv_hld_bv.get()))
        self.value_calc.set_input(CDT.REP_LEVEL_SCHEME, float(self.rep_level_scheme.get()))
        self.value_calc.set_input(CDT.NEGATIVE_VALUES, self.neg_dollar_values.get())
        if not self.starting_set:
            #Safety
            self.starting_set = starting_positions_services.get_ottoneu_position_set()
        off_pos = [p.position for p in self.starting_set.positions if p.position.offense]
        off_pos = [p for p in off_pos if Position.position_is_base(p, off_pos) or p == Position.POS_UTIL]
        if self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
            for pos in off_pos + Position.get_discrete_pitching_pos():
                self.value_calc.set_input(CDT.pos_to_rep_level().get(pos), float(self.rep_level_dict[pos.value].get()))
        else:
            for pos in off_pos + Position.get_discrete_pitching_pos():
                self.value_calc.set_input(CDT.pos_to_num_rostered().get(pos), int(self.rep_level_dict[pos.value].get()))
        self.get_advanced_inputs()
        
        logging.debug("About to perform point_calc")
        pd = progress.ProgressDialog(self, title='Performing Calculation')
        try:
            calculation_services.perform_point_calculation(self.value_calc, pd, self.controller.debug)
            logging.debug("Performed calc")
            self.update_values()
            #self.populate_projections()
            self.update_calc_output_frame()
        except Exception as Argument:
            logging.exception('Error creating player values')
            mb.showerror('Error creating player values',  'See log for details')
        finally:
            pd.complete()
    
    def get_advanced_inputs(self):
        if not ScoringFormat.is_points_type(self.value_calc.format):
            #TODO: SGP info
            if RankingBasis.is_roto_fractional(self.value_calc.hitter_basis):
                self.value_calc.set_input(CDT.BATTER_G_TARGET, adv_calc_services.get_advanced_option(CDT.BATTER_G_TARGET).value)
        if self.value_calc.get_input(CDT.REP_LEVEL_SCHEME) == RepLevelScheme.FILL_GAMES.value:
            self.value_calc.set_input(CDT.BATTER_G_TARGET, adv_calc_services.get_advanced_option(CDT.BATTER_G_TARGET, default=162).value)
            if ScoringFormat.is_h2h(self.value_calc.format):
                ##Fill Games
                self.value_calc.set_input(CDT.GS_LIMIT, adv_calc_services.get_advanced_option(CDT.GS_LIMIT, default=10).value)
                self.value_calc.set_input(CDT.RP_G_TARGET, adv_calc_services.get_advanced_option(CDT.RP_G_TARGET, default=10).value)
            else:
                #Fill IP
                self.value_calc.set_input(CDT.IP_TARGET, adv_calc_services.get_advanced_option(CDT.IP_TARGET, default=1500).value)
                self.value_calc.set_input(CDT.RP_IP_TARGET, adv_calc_services.get_advanced_option(CDT.RP_IP_TARGET, default=300).value)
    
    def set_default_rep_level(self, scheme, update_only:bool=False):
        if scheme == RepLevelScheme.NUM_ROSTERED:
            for pos, sv in self.rep_level_dict.items():
                if update_only and sv.get() != '': continue
                sv.set(num_rost_rl_default[pos])
        elif scheme == RepLevelScheme.FILL_GAMES:
            for sv in self.rep_level_dict.values():
                if update_only and sv.get() != '': continue
                sv.set('0')
        elif scheme == RepLevelScheme.STATIC_REP_LEVEL:
            off_pos = [p.position for p in self.starting_set.positions if p.position.offense]
            off_pos = [p for p in off_pos if Position.position_is_base(p, off_pos) or p == Position.POS_UTIL]

            if RankingBasis.get_enum_by_display(self.hitter_basis.get()) == RankingBasis.PPG:
                for pos in off_pos:
                    sv = self.rep_level_dict[pos.value]
                    if update_only and sv.get() != '': continue
                    sv.set("4.5")
            elif RankingBasis.get_enum_by_display(self.hitter_basis.get()) == RankingBasis.PPPA:
                for pos in off_pos:
                    sv = self.rep_level_dict[pos.value]
                    if update_only and sv.get() != '': continue
                    sv.set("1.0")
            if RankingBasis.get_enum_by_display(self.pitcher_basis.get()) == RankingBasis.PIP:
                self.rep_level_dict["SP"].set("3.5")
                self.rep_level_dict["RP"].set("6.0")
            elif RankingBasis.get_enum_by_display(self.pitcher_basis.get()) == RankingBasis.PPG:
                self.rep_level_dict["SP"].set("20")
                self.rep_level_dict["RP"].set("6.0")

    def update_values(self):
        for pos, table in self.tables.items():
            if table:
                for index in table.get_children():
                    pv = self.value_calc.get_player_value(int(table.item(index)['text']), pos)
                    if pv is None:
                        table.set(index, 0, "NR")
                    else:
                        table.set(index, 0, "${:.1f}".format(pv.value))
                table.resort()
    
    def set_advanced_button_status(self):
        if self.rep_level_scheme.get() == RepLevelScheme.FILL_GAMES.value:
            self.advanced_btn.configure(state='enable')
        elif not ScoringFormat.is_points_type(ScoringFormat.get_format_by_full_name(self.game_type.get())):
            h_basis = RankingBasis.get_enum_by_display(self.hitter_basis.get())
            p_basis = RankingBasis.get_enum_by_display(self.pitcher_basis.get())
            if h_basis == RankingBasis.ZSCORE_PER_G or h_basis == RankingBasis.SGP:
                self.advanced_btn.configure(state='enable')
            elif p_basis == RankingBasis.ZSCORE_PER_G or p_basis == RankingBasis.SGP:
                self.advanced_btn.configure(state='enable')
            else:
                self.advanced_btn.configure(state='disable')    
        else:
            self.advanced_btn.configure(state='disable')

    def has_errors(self):
        errors = []
        bad_rep_level = []

        game_type = ScoringFormat.get_format_by_full_name(self.game_type.get())
        #if not ScoringFormat.is_points_type(game_type):
        #    errors.append(f"Calculations for {self.game_type.get()} not currently supported.")
        
        if self.projection is None:
            errors.append("No projection selected. Please select a projection before calculating.")
        elif self.projection.type == ProjectionType.VALUE_DERIVED:
            errors.append(f"Projection created from value upload cannot be used for calculations. Select a different projetion.")
        elif ScoringFormat.is_points_type(game_type) and not self.projection.valid_points:
            errors.append(f'Selected projection does not have required columns for points calculations. Please select another projection')
        elif game_type == ScoringFormat.OLD_SCHOOL_5X5 and not self.projection.valid_5x5:
            errors.append(f'Selected projection does not have required columns for 5x5 calculations. Please select another projection')
        elif game_type == ScoringFormat.CLASSIC_4X4 and not self.projection.valid_4x4:
            errors.append(f'Selected projection does not have required columns for 4x4 calculations. Please select another projection')
        
        if self.projection is not None:
            if self.projection.ros and self.rep_level_scheme.get() == RepLevelScheme.FILL_GAMES.value:
                errors.append(f'Fill Games option not currently supported for RoS projection sets. Please pick another replacement level scheme.')

        if self.rep_level_scheme.get() == RepLevelScheme.NUM_ROSTERED.value:
            for key, value in self.rep_level_dict.items():
                if not value.get().isnumeric():
                    bad_rep_level.append(key)
        elif self.rep_level_scheme.get() == RepLevelScheme.FILL_GAMES.value:
            for key, value in self.rep_level_dict.items():
                try:
                    val = int(value.get())
                except ValueError:
                    bad_rep_level.append(key)
        else:
            for key, value in self.rep_level_dict.items():
                try:
                    f_val = float(value.get())
                    if f_val > 10.0:
                        if RankingBasis.get_enum_by_display(self.pitcher_basis.get()) == RankingBasis.PPG and key == 'SP' and f_val < 40.0:
                            continue
                        bad_rep_level.append(key)
                except ValueError:
                    bad_rep_level.append(key)

        if len(bad_rep_level) > 0:
            errors.append(f'The following positions have bad replacement level inputs (check scheme): {", ".join(bad_rep_level)}')

        for sv in self.input_svs:
            if not sv.get().isdigit():
                errors.append('Required input fields have non-numeric values')
                break

        if len(errors) > 0:
            delim = "\n\t-"
            mb.showerror("Input Error(s)", f'Errors in inputs. Please correct: \n\t-{delim.join(errors)}')

        return len(errors) != 0
    
    def league_change(self) -> bool:
        return True