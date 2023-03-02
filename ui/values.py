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

from ui.table import Table
from domain.domain import ValueCalculation
from domain.enum import CalculationDataType as CDT, RankingBasis, RepLevelScheme, StatType, Position, ProjectionType, ScoringFormat
from services import projection_services, calculation_services, adv_calc_services
from ui.dialog import projection_select, progress, name_desc, advanced_calc
from ui.dialog.wizard import projection_import
from ui.tool.tooltip import CreateToolTip
from util import string_util

player_columns = ('Value', 'Name', 'Team', 'Pos')
#fom_columns = ('P/G', 'HP/G', 'P/PA', 'P/IP', 'PP/G', 'Points', 'zScore', 'SGP')
h_fom_columns = ('P/G', 'HP/G', 'P/PA')
p_fom_columns = ('P/IP', 'PP/G', 'SABR P/IP', 'SABR PP/G', 'NSH P/IP', 'NSH PP/G', 'NSH SABR P/IP', 'NSH SABR PP/G')
point_cols = ('FG Pts', 'SABR Pts', 'NSH FG Pts', 'NSH SABR Pts')
points_hitting_columns = ('G', 'PA', 'AB', 'H', '2B', '3B', 'HR', 'BB', 'HBP', 'SB','CS')
points_pitching_columns = ('G', 'GS', 'IP', 'SO','H','BB','HBP','HR','SV','HLD')
old_school_hitting_columns = ('G', 'PA', 'AB', 'R', 'HR', 'RBI', 'SB', 'AVG')
old_school_pitching_columns = ('G', 'GS', 'IP', 'W', 'SV', 'SO', 'ERA', 'WHIP')
classic_hitting_columns = ('G', 'PA', 'AB', 'OBP', 'SLG', 'HR', 'R')
classic_pitching_columns = ('G', 'GS', 'IP', 'ERA', 'WHIP', 'HR/9', 'SO')
all_hitting_stats = ('G', 'PA', 'AB', 'H', '2B', '3B', 'HR', 'BB', 'HBP', 'SB','CS', 'R', 'RBI', 'SB', 'AVG', 'OBP', 'SLG')
all_pitching_stats = ('G', 'GS', 'IP', 'SO','H','BB','HBP','HR','SV','HLD', 'W', 'ERA', 'WHIP', 'HR/9')

class ValuesCalculation(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        self.value_calc = self.controller.value_calculation
        self.rep_level_dict = {}
        self.tables = {}
        self.input_svs = []

        self.create_input_frame()
        self.create_proj_val_frame()
        self.create_output_frame()
    
    def on_show(self):
        self.value_calc = self.controller.value_calculation
        self.refresh_ui()
        if self.controller.value_calculation is None:
            self.controller.value_calculation = ValueCalculation()
            self.value_calc = self.controller.value_calculation
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
            self.game_type.set(ScoringFormat.enum_to_full_name_map()[ScoringFormat.FG_POINTS])
            self.sel_proj.set("None")
            self.projection = None
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
            self.game_type.set(ScoringFormat.enum_to_full_name_map()[v.format])
            if v.projection is None:
                self.sel_proj.set("No Projection")
            else:
                self.sel_proj.set(v.projection.name)
            self.projection = v.projection
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
            self.hitter_basis.set(RankingBasis.enum_to_display_dict()[v.hitter_basis])
            self.safe_set_input_value(CDT.PA_TO_RANK, self.min_pa, True)
            self.pitcher_basis.set(RankingBasis.enum_to_display_dict()[v.pitcher_basis])
            self.safe_set_input_value(CDT.SP_IP_TO_RANK, self.min_sp_ip, True)
            self.safe_set_input_value(CDT.RP_IP_TO_RANK, self.min_rp_ip, True)
            self.safe_set_input_value(CDT.REP_LEVEL_SCHEME, self.rep_level_scheme, True, RepLevelScheme.STATIC_REP_LEVEL.value)
            self.update_rep_level_scheme()
            if self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
                for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
                    self.safe_set_input_value(CDT.pos_to_rep_level().get(pos), self.rep_level_dict[pos.value])
            else:
                for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
                    self.safe_set_input_value(CDT.pos_to_num_rostered().get(pos), self.rep_level_dict[pos.value], True)
            for adv_inp in CDT.get_adv_inputs():
                inp = self.value_calc.get_input(adv_inp)
                if inp is not None:
                    adv_calc_services.set_advanced_option(adv_inp, inp)
            self.update_calc_output_frame()
        pd.set_completion_percent(33)
        if len(self.tables) > 0:
            for table in self.tables.values():
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

        gt_map = ScoringFormat.enum_to_full_name_map()
        ttk.Label(inpf, text="Game Type:").grid(column=0,row=2,pady=5)
        self.game_type = StringVar()
        self.game_type.set(gt_map[ScoringFormat.FG_POINTS])
        gt_combo = ttk.Combobox(inpf, textvariable=self.game_type)
        gt_combo.bind("<<ComboboxSelected>>", self.update_game_type)
        # TODO: Don't hardcode game types, include other types

        gt_combo['values'] = (gt_map[ScoringFormat.FG_POINTS], gt_map[ScoringFormat.SABR_POINTS], gt_map[ScoringFormat.H2H_FG_POINTS], gt_map[ScoringFormat.H2H_SABR_POINTS], gt_map[ScoringFormat.OLD_SCHOOL_5X5], gt_map[ScoringFormat.CLASSIC_4X4])
        gt_combo.grid(column=1,row=2,pady=5)

        ttk.Label(inpf, text="Number of Teams:").grid(column=0, row=3,pady=5)
        self.num_teams_str = StringVar()
        self.num_teams_str.set("12")
        team_entry = ttk.Entry(inpf, textvariable=self.num_teams_str)
        team_entry.grid(column=1,row=3,pady=5)
        team_entry.config(validate="key", validatecommand=(validation, '%P'))
        self.input_svs.append(self.num_teams_str)

        lbl = ttk.Label(inpf, text="Manual hitter/pitcher split?")
        lbl.grid(column=0, row=4,pady=5)
        CreateToolTip(lbl, 'Indicate if value calculations should calculate hitter/pitcher value\nabove replacement intrinsically or by user percentage.')
        self.manual_split = BooleanVar()
        self.manual_split.set(False)
        cb = ttk.Checkbutton(inpf, variable=self.manual_split, command=self.toggle_manual_split)
        cb.grid(column=1, row=4, pady=5)
        CreateToolTip(cb, 'Indicate if value calculations should calculate hitter/pitcher value\nabove replacement intrinsically or by user percentage.')

        self.hitter_aloc_lbl = ttk.Label(inpf, text="Hitter allocation (%):")
        self.hitter_aloc_lbl.grid(column=0, row=5,pady=5)
        self.hitter_aloc_lbl.configure(state='disable')
        self.hitter_allocation = StringVar()
        self.hitter_allocation.set("60")
        self.hitter_aloc_entry = ttk.Entry(inpf, textvariable=self.hitter_allocation)
        self.hitter_aloc_entry.grid(column=1,row=5,pady=5)
        self.hitter_aloc_entry.configure(state='disable')
        self.input_svs.append(self.hitter_allocation)

        lbl = ttk.Label(inpf, text="Excess salaries:")
        lbl.grid(column=0, row=6,pady=5)
        CreateToolTip(lbl, text='Cap space set aside for below replacement level player salaries, such as prospects, or unspent cap space.')
        self.non_prod_dollars_str = StringVar()
        self.non_prod_dollars_str.set("300")
        non_prod = ttk.Entry(inpf, textvariable=self.non_prod_dollars_str)
        non_prod.grid(column=1,row=6,pady=5)
        non_prod.config(validate="key", validatecommand=(validation, '%P'))
        CreateToolTip(non_prod, text='Cap space set aside for below replacement level player salaries, such as prospects, or unspent cap space.')
        self.input_svs.append(self.non_prod_dollars_str)

        ttk.Label(inpf, text="Hitter Value Basis:").grid(column=0,row=7,pady=5)
        self.hitter_basis = StringVar()
        self.hitter_basis.set('P/G')
        self.hitter_basis_cb = hbcb = ttk.Combobox(inpf, textvariable=self.hitter_basis)
        hbcb['values'] = ('P/G','P/PA')
        hbcb.grid(column=1,row=7,pady=5)
        hbcb.bind("<<ComboboxSelected>>", self.update_ranking_basis)

        ttk.Label(inpf, text="Min PA to Rank:").grid(column=0, row= 8, pady=5)
        self.min_pa = StringVar()
        self.min_pa.set("150")
        pa_entry = ttk.Entry(inpf, textvariable=self.min_pa)
        pa_entry.grid(column=1,row=8, pady=5)
        pa_entry.config(validate="key", validatecommand=(validation, '%P'))
        CreateToolTip(pa_entry, 'The minimum number of plate appearances required to be considered for valuation.')
        self.input_svs.append(self.min_pa)
        
        ttk.Label(inpf, text="Pitcher Value Basis:").grid(column=0,row=9,pady=5)
        self.pitcher_basis = StringVar()
        self.pitcher_basis.set('P/IP')
        self.pitcher_basis_cb = pbcb = ttk.Combobox(inpf, textvariable=self.pitcher_basis)
        pbcb['values'] = ('P/IP','P/G')
        pbcb.grid(column=1,row=9,pady=5)
        pbcb.bind("<<ComboboxSelected>>", self.update_ranking_basis)

        ttk.Label(inpf, text="Min SP IP to Rank:").grid(column=0, row= 10, pady=5)
        self.min_sp_ip = StringVar()
        self.min_sp_ip.set("70")
        entry = ttk.Entry(inpf, textvariable=self.min_sp_ip)
        entry.grid(column=1,row=10, pady=5)
        CreateToolTip(entry, 'The minimum number of innings required by a full-time starter to be considered for valuation.')
        self.input_svs.append(self.min_sp_ip)

        ttk.Label(inpf, text="Min RP IP to Rank:").grid(column=0, row= 11, pady=5)
        self.min_rp_ip = StringVar()
        self.min_rp_ip.set("30")
        entry = ttk.Entry(inpf, textvariable=self.min_rp_ip)
        entry.grid(column=1,row=11, pady=5)
        CreateToolTip(entry, 'The minimum number of innings required by a full-time reliever to be considered for valuation.')
        self.input_svs.append(self.min_rp_ip)

        self.sv_hld_lbl = ttk.Label(inpf, text="Include SV/HLD?")
        self.sv_hld_lbl.grid(column=0, row=12, pady=5)
        CreateToolTip(self.sv_hld_lbl, 'Calculate reliever values with or without projected save and hold values.')
        self.sv_hld_bv = BooleanVar()
        self.sv_hld_bv.set(True)
        self.sv_hld_entry = ttk.Checkbutton(inpf, variable=self.sv_hld_bv, command=self.set_display_columns)
        self.sv_hld_entry.grid(column=1, row=12, pady=5)
        CreateToolTip(self.sv_hld_entry, 'Calculate reliever values with or without projected save and hold values.')
        
        # This is its own method to make the __init__ more readable
        row = self.set_replacement_level_ui(inpf, start_row=13)

        ttk.Button(inpf, text="Calculate", command=self.calculate_values).grid(row=row, column=0)
        self.advanced_btn = ttk.Button(inpf, text='Advanced', command=self.advanced_options)
        CreateToolTip(self.advanced_btn, 'Set advanced input options for the Value Calculation.')
        self.advanced_btn['state'] = DISABLED
        self.advanced_btn.grid(row=row, column=1)

        inpf.update()

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
        self.overall_table = ot = Table(overall_frame, cols, column_widths=col_width, column_alignments=col_align, sortable_columns=cols)
        self.tables[Position.OVERALL] = ot
        ot.set_refresh_method(self.refresh_overall)
        ot.grid(row=0, column=0)
        ot.add_scrollbar()

        hit_cols = player_columns + h_fom_columns + point_cols + all_hitting_stats

        self.bat_table = Table(bat_frame, hit_cols, column_widths=col_width, column_alignments=col_align, sortable_columns=hit_cols)
        self.tables[Position.OFFENSE] = self.bat_table
        self.bat_table.set_refresh_method(lambda: self.refresh_hitters(Position.OFFENSE))
        self.bat_table.grid(row=0, column=0)
        self.bat_table.add_scrollbar()

        pitch_cols = player_columns + p_fom_columns + point_cols + all_pitching_stats

        self.arm_table = Table(arm_frame, pitch_cols, column_widths=col_width, column_alignments=col_align, sortable_columns=pitch_cols)
        self.tables[Position.PITCHER] = self.arm_table
        self.arm_table.set_refresh_method(lambda: self.refresh_pitchers(Position.PITCHER))
        self.arm_table.grid(row=0,column=0)
        self.arm_table.add_scrollbar()

        for pos in Position.get_discrete_offensive_pos():
            frame = ttk.Frame(self.tab_control)
            self.tab_control.add(frame, text=pos.value)
            pt = Table(frame, hit_cols, column_widths=col_width, column_alignments=col_align, sortable_columns=hit_cols)
            self.tables[pos] = pt
            pt.set_refresh_method(lambda _pos=pos: self.refresh_hitters(_pos))
            pt.grid(row=0, column=0)
            pt.add_scrollbar()

        for pos in Position.get_discrete_pitching_pos():
            frame = ttk.Frame(self.tab_control)
            self.tab_control.add(frame, text=pos.value)
            pt = Table(frame, pitch_cols, column_widths=col_width, column_alignments=col_align, sortable_columns=pitch_cols)
            self.tables[pos] = pt
            pt.set_refresh_method(lambda _pos=pos: self.refresh_pitchers(_pos))
            pt.grid(row=0, column=0)
            pt.add_scrollbar()
    
    def update_ranking_basis(self, event: Event):
        self.set_display_columns()
        self.set_advanced_button_status()

    def update_game_type(self, event: Event):
        self.set_display_columns()
        self.set_advanced_button_status()
        if ScoringFormat.is_points_type(ScoringFormat.name_to_enum_map().get(self.game_type.get())):
            self.hitter_basis_cb['values'] = ('P/G','P/PA')
            if self.hitter_basis.get() not in self.hitter_basis_cb['values']:
                self.hitter_basis.set('P/G')
            self.pitcher_basis_cb['values'] = ('P/IP', 'P/G')
            if self.pitcher_basis.get() not in self.pitcher_basis_cb['values']:
                self.pitcher_basis.set('P/IP')
            self.static_rl_btn['state'] = ACTIVE
        else:
            self.hitter_basis_cb['values'] = ('zScore', 'zScore/G')
            if self.hitter_basis.get() not in self.hitter_basis_cb['values']:
                self.hitter_basis.set('zScore')
            #TODO: Reimplement zScore/G for pitchers once the games rationing is figured out
            #self.pitcher_basis_cb['values'] = ('zScore', 'zScore/G')
            self.pitcher_basis_cb['values'] = ('zScore')
            if self.pitcher_basis.get() not in self.pitcher_basis_cb['values']:
                self.pitcher_basis.set('zScore')
            self.static_rl_btn['state'] = DISABLED
            if self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
                self.rep_level_scheme.set(RepLevelScheme.NUM_ROSTERED.value)
                self.update_rep_level_scheme()

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
        fresh_pd = False
        if pd is None:
            fresh_pd = True
            pd = progress.ProgressDialog(self, title='Refreshing Table')
            pd.set_completion_percent(25)
        delta = 75 / len(self.tables)
        for table in self.tables.values():
            table.refresh()
            pd.increment_completion_percent(delta)
        self.set_display_columns()
        if fresh_pd:
            pd.set_completion_percent(100)
            pd.destroy()
    
    def append_player_column_data(self, val, pp, pos):
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
            o_points = calculation_services.get_points(pp, Position.OFFENSE, sabr=(self.game_type.get() == ScoringFormat.enum_to_full_name_map()[ScoringFormat.SABR_POINTS]))
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
            
            p_points = calculation_services.get_points(pp, Position.PITCHER, sabr=False)
            s_p_points = calculation_services.get_points(pp, Position.PITCHER, sabr=True)
            nsh_p_points = calculation_services.get_points(pp, Position.PITCHER, sabr=False, no_svh=True)
            nsh_s_p_points = calculation_services.get_points(pp, Position.PITCHER, sabr=True, no_svh=True)
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
        val.append(pv.player.position)
        return val

    def get_player_row(self, pp, enum_dict, cols, pos):
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
        val.append(pp.player.position)
        
        if pos in Position.get_offensive_pos():
            if self.projection.type == ProjectionType.VALUE_DERIVED:
                val.append(pp.get_stat(StatType.PPG)) # p/g
                val.append(pp.get_stat(StatType.PPG)) # hp/g
                val.append(pp.get_stat(StatType.PPG)) # p/pa
                f_points = pp.get_stat(StatType.POINTS)
                s_points = f_points
                nsh_f_points = f_points
                nsh_s_points = f_points
            else:
                f_points = calculation_services.get_points(pp, pos, sabr=False)
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
                    val.append("{:.2f}".format(f_points / pp.get_stat(StatType.PA))) # p/pa
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
                f_points = calculation_services.get_points(pp, pos, sabr=False)
                s_points = calculation_services.get_points(pp, pos, sabr=True)
                nsh_f_points = calculation_services.get_points(pp, pos, sabr=False, no_svh=True)
                nsh_s_points = calculation_services.get_points(pp, pos, sabr=True, no_svh=True)
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
                    val.append("{:.2f}".format(f_points/ip))
                    val.append("{:.2f}".format(f_points/games))
                    val.append("{:.2f}".format(s_points/ip))
                    val.append("{:.2f}".format(s_points/games))
                    val.append("{:.2f}".format(nsh_f_points/ip))
                    val.append("{:.2f}".format(nsh_f_points/games))
                    val.append("{:.2f}".format(nsh_s_points/ip))
                    val.append("{:.2f}".format(nsh_s_points/games))
        val.append("{:.1f}".format(f_points))
        val.append("{:.1f}".format(s_points))
        val.append("{:.1f}".format(nsh_f_points))
        val.append("{:.1f}".format(nsh_s_points))
        if self.projection.type != ProjectionType.VALUE_DERIVED:
            for col in cols:
                if col in enum_dict:
                    stat = pp.get_stat(enum_dict[col])
                    fmt = StatType.get_stat_format()[enum_dict[col]]
                    if stat is None:
                        val.append(fmt.format(0))
                    else:
                        val.append(fmt.format(stat))
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
                if pp.player.pos_eligible(pos):
                    if self.projection.type == ProjectionType.VALUE_DERIVED:
                        val = self.get_player_row(pp, StatType.hit_to_enum_dict(), all_hitting_stats, pos)
                    elif pp.get_stat(StatType.AB) is not None:
                        val = self.get_player_row(pp, StatType.hit_to_enum_dict(), all_hitting_stats, pos)
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
                    if pp.player.pos_eligible(pos):
                        val = self.get_player_row(pp, StatType.pitch_to_enum_dict(), all_pitching_stats, pos)
                        self.tables[pos].insert('', tk.END, text=str(pp.player_id), values=val)
                elif pp.get_stat(StatType.IP) is not None:
                    if  pos == Position.PITCHER \
                        or (pos == Position.POS_RP and pp.get_stat(StatType.G_PIT) > pp.get_stat(StatType.GS_PIT)) \
                        or (pos == Position.POS_SP and pp.get_stat(StatType.GS_PIT) > 0):
                            val = self.get_player_row(pp, StatType.pitch_to_enum_dict(), all_pitching_stats, pos)
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

        ttk.Label(outf, text="Position", font='bold').grid(row=3, column=0)
        ttk.Label(outf, text="# Rostered", font='bold').grid(row=3, column=1)
        self.bat_rep_level_lbl = StringVar()
        self.bat_rep_level_lbl.set("Rep. Level")
        ttk.Label(outf, textvariable=self.bat_rep_level_lbl, font='bold').grid(row=3, column=2)

        row = 4
        self.pos_rostered_sv = {}
        self.pos_rep_lvl_sv = {}
        for pos in Position.get_discrete_offensive_pos():
            ttk.Label(outf, text=pos.value).grid(row=row, column=0)
            pos_rep = StringVar()
            pos_rep.set("--")
            self.pos_rostered_sv[pos] = pos_rep
            ttk.Label(outf, textvariable=pos_rep).grid(row=row, column=1)
            rep_lvl = StringVar()
            rep_lvl.set("--")
            self.pos_rep_lvl_sv[pos] = rep_lvl
            ttk.Label(outf, textvariable=rep_lvl).grid(row=row, column=2)
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
        
        ttk.Label(outf, text="Position", font='bold').grid(row=row, column=0)
        ttk.Label(outf, text="# Rostered", font='bold').grid(row=row, column=1)
        self.pitch_rep_level_lbl = StringVar()
        self.pitch_rep_level_lbl.set("Rep. Level")
        ttk.Label(outf, textvariable=self.pitch_rep_level_lbl, font='bold').grid(row=row, column=2)

        for pos in Position.get_discrete_pitching_pos():
            row += 1
            ttk.Label(outf, text=pos.value).grid(row=row, column=0)
            pos_rep = StringVar()
            pos_rep.set("--")
            self.pos_rostered_sv[pos] = pos_rep
            ttk.Label(outf, textvariable=pos_rep).grid(row=row, column=1)
            rep_lvl = StringVar()
            rep_lvl.set("--")
            self.pos_rep_lvl_sv[pos] = rep_lvl
            ttk.Label(outf, textvariable=rep_lvl).grid(row=row, column=2)
            
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
        CreateToolTip(eb, 'Export the last set of calculated values to a csv ro xlsx file.')

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
        hitter_rb = RankingBasis.enum_to_display_dict()[self.value_calc.hitter_basis]
        self.bat_rep_level_lbl.set(f"Rep. Level ({hitter_rb})")
        pitcher_rb = RankingBasis.enum_to_display_dict()[self.value_calc.pitcher_basis]
        self.pitch_rep_level_lbl.set(f"Rep. Level ({pitcher_rb})")

        for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
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
                for pos in Position.get_display_order():
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
            h_basis = RankingBasis.display_to_enum_map().get(self.hitter_basis.get())
            p_basis = RankingBasis.display_to_enum_map().get(self.pitcher_basis.get())
            scoring_format = ScoringFormat.name_to_enum_map().get(self.game_type.get())
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
                if ScoringFormat.is_points_type(scoring_format):
                    if ScoringFormat.is_sabr(scoring_format):
                        overall.append(f"{prefix}SABR Pts")
                        pitch.append(f"{prefix}SABR Pts")
                    else:
                        overall.append(f"{prefix}FG Pts")
                        pitch.append(f"{prefix}FG Pts")
                    hit.append("FG Pts")
                    if self.projection.type != ProjectionType.VALUE_DERIVED:
                        hit.extend(points_hitting_columns)
                        pitch.extend(points_pitching_columns)
            elif scoring_format == ScoringFormat.OLD_SCHOOL_5X5:
                for col in old_school_hitting_columns:
                    hit.append(col)
                for col in old_school_pitching_columns:
                    pitch.append(col)
            elif scoring_format == ScoringFormat.CLASSIC_4X4:
                for col in classic_hitting_columns:
                    hit.append(col)
                for col in classic_pitching_columns:
                    pitch.append(col)
        self.overall_table.set_display_columns(tuple(overall))
        for pos in self.tables:
            if pos in Position.get_offensive_pos():
                self.tables[pos].set_display_columns(tuple(hit))
            elif pos in Position.get_pitching_pos():
                self.tables[pos].set_display_columns(tuple(pitch))
    
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

        for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
            ttk.Label(inpf, text=pos.value).grid(row=row, column=0)
            self.rep_level_dict[pos.value] = StringVar()
            ttk.Entry(inpf, textvariable=self.rep_level_dict[pos.value]).grid(row=row,column=1)
            row = row+1

        return row
    
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
        advanced_calc.Dialog(self, ScoringFormat.name_to_enum_map()[self.game_type.get()], RepLevelScheme.num_to_enum_map()[self.rep_level_scheme.get()],
            RankingBasis.display_to_enum_map().get(self.hitter_basis.get()), RankingBasis.display_to_enum_map().get(self.pitcher_basis.get()))

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
        self.value_calc.format = ScoringFormat.name_to_enum_map()[self.game_type.get()]
        self.value_calc.inputs = []
        self.value_calc.set_input(CDT.NUM_TEAMS, float(self.num_teams_str.get()))
        if self.manual_split.get():
            self.value_calc.set_input(CDT.HITTER_SPLIT, float(self.hitter_allocation.get()))
        self.value_calc.set_input(CDT.NON_PRODUCTIVE_DOLLARS, int(self.non_prod_dollars_str.get()))
        self.value_calc.hitter_basis = RankingBasis.display_to_enum_map()[self.hitter_basis.get()]
        self.value_calc.set_input(CDT.PA_TO_RANK, float(self.min_pa.get()))
        self.value_calc.pitcher_basis = RankingBasis.display_to_enum_map()[self.pitcher_basis.get()]
        self.value_calc.set_input(CDT.SP_IP_TO_RANK, float(self.min_sp_ip.get()))
        self.value_calc.set_input(CDT.RP_IP_TO_RANK, float(self.min_rp_ip.get()))
        self.value_calc.set_input(CDT.INCLUDE_SVH, float(self.sv_hld_bv.get()))
        self.value_calc.set_input(CDT.REP_LEVEL_SCHEME, float(self.rep_level_scheme.get()))
        if self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
            for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
                self.value_calc.set_input(CDT.pos_to_rep_level().get(pos), float(self.rep_level_dict[pos.value].get()))
        else:
            for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
                self.value_calc.set_input(CDT.pos_to_num_rostered().get(pos), int(self.rep_level_dict[pos.value].get()))
        self.get_advanced_inputs()
        
        logging.debug("About to perform point_calc")
        pd = progress.ProgressDialog(self, title='Performing Calculation')
        try:
            calculation_services.perform_point_calculation(self.value_calc, pd)
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
            if RankingBasis.is_roto_per_game(self.value_calc.hitter_basis):
                #TODO: Something for pitcher zScore/G
                self.value_calc.set_input(CDT.BATTER_G_TARGET, adv_calc_services.get_advanced_option(CDT.BATTER_G_TARGET).value)
        if self.value_calc.get_input(CDT.REP_LEVEL_SCHEME) == RepLevelScheme.FILL_GAMES.value:
            self.value_calc.set_input(CDT.BATTER_G_TARGET, adv_calc_services.get_advanced_option(CDT.BATTER_G_TARGET).value)
            if ScoringFormat.is_h2h(self.value_calc.format):
                ##Fill Games
                self.value_calc.set_input(CDT.GS_LIMIT, adv_calc_services.get_advanced_option(CDT.GS_LIMIT).value)
                self.value_calc.set_input(CDT.RP_G_TARGET, adv_calc_services.get_advanced_option(CDT.RP_G_TARGET).value)
            else:
                #Fill IP
                self.value_calc.set_input(CDT.IP_TARGET, adv_calc_services.get_advanced_option(CDT.IP_TARGET).value)
                self.value_calc.set_input(CDT.RP_IP_TARGET, adv_calc_services.get_advanced_option(CDT.RP_IP_TARGET).value)
    
    def set_default_rep_level(self, scheme):
        if scheme == RepLevelScheme.NUM_ROSTERED:
            self.rep_level_dict["C"].set("24")
            self.rep_level_dict["1B"].set("40")
            self.rep_level_dict["2B"].set("38")
            self.rep_level_dict["SS"].set("42")
            self.rep_level_dict["3B"].set("24")
            self.rep_level_dict["OF"].set("95")
            self.rep_level_dict["Util"].set("200")
            self.rep_level_dict["SP"].set("85")
            self.rep_level_dict["RP"].set("70")
        elif scheme == RepLevelScheme.FILL_GAMES:
            for sv in self.rep_level_dict.values():
                sv.set('0')
        elif scheme == RepLevelScheme.STATIC_REP_LEVEL:
            if RankingBasis.display_to_enum_map()[self.hitter_basis.get()] == RankingBasis.PPG:
                for pos in Position.get_discrete_offensive_pos():
                    self.rep_level_dict[pos.value].set("4.5")
            elif RankingBasis.display_to_enum_map()[self.hitter_basis.get()] == RankingBasis.PPPA:
                for pos in Position.get_discrete_offensive_pos():
                    self.rep_level_dict[pos.value].set("1.0")
            if RankingBasis.display_to_enum_map()[self.pitcher_basis.get()] == RankingBasis.PIP:
                self.rep_level_dict["SP"].set("3.5")
                self.rep_level_dict["RP"].set("6.0")
            elif RankingBasis.display_to_enum_map()[self.pitcher_basis.get()] == RankingBasis.PPG:
                self.rep_level_dict["SP"].set("20")
                self.rep_level_dict["RP"].set("6.0")

    def update_values(self):
        for pos, table in self.tables.items():
            for index in table.get_children():
                pv = self.value_calc.get_player_value(int(table.item(index)['text']), pos)
                if pv is None:
                    table.set(index, 0, "$0.0")
                else:
                    table.set(index, 0, "${:.1f}".format(pv.value))
            table.resort()
    
    def set_advanced_button_status(self):
        if self.rep_level_scheme.get() == RepLevelScheme.FILL_GAMES.value:
            self.advanced_btn.configure(state='enable')
        elif not ScoringFormat.is_points_type(ScoringFormat.name_to_enum_map().get(self.game_type.get())):
            h_basis = RankingBasis.display_to_enum_map().get(self.hitter_basis.get())
            p_basis = RankingBasis.display_to_enum_map().get(self.pitcher_basis.get())
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

        game_type = ScoringFormat.name_to_enum_map().get(self.game_type.get())
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
                except:
                    bad_rep_level.append(key)
        else:
            for key, value in self.rep_level_dict.items():
                try:
                    f_val = float(value.get())
                    if f_val > 10.0:
                        if self.pitcher_basis.get() == RankingBasis.PPG and key == 'SP' and f_val < 40.0:
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
    
    def exit_tasks(self):
        return True

def main(preferences):
    try:
        win = ValuesCalculation(preferences)
    except Exception as e:
        logging.exception("Error encountered")
        mb.showerror("Error", f'Fatal program error. See ./logs/toolbox.log')

if __name__ == '__main__':
    main()