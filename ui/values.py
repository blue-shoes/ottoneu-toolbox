from datetime import datetime
import logging
import pathlib
from re import I
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import filedialog as fd
from tkinter import messagebox as mb
from pathlib import Path
import os
import os.path
import pandas as pd

from ui.table import Table
from domain.domain import ValueCalculation, ScoringFormat
from domain.enum import CalculationDataType as CDT, RankingBasis, RepLevelScheme, StatType, Position
from services import projection_services, calculation_services
from ui.dialog import proj_download, selection_projection, progress, name_desc


class ValuesCalculation(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.controller = controller
        self.value_calc = self.controller.value_calculation
        self.rep_level_dict = {}
        self.tables = {}

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

    def refresh_ui(self):
        pd = progress.ProgressDialog(self.parent, 'Updating Value Calculator Window...')
        pd.set_completion_percent(10)
        if self.value_calc is None:
            self.game_type.set(ScoringFormat.enum_to_full_name_map()[ScoringFormat.FG_POINTS])
            self.sel_proj.set("None")
            self.projection = None
            self.num_teams_str.set("12")
            self.manual_split.set(False)
            self.hitter_allocation.set("60")
            self.non_prod_dollars_str.set("48")
            self.hitter_basis.set('P/G')
            self.min_pa.set("150")
            self.pitcher_basis.set('P/IP')
            self.min_sp_ip.set("70")
            self.min_rp_ip.set("30")
            self.rep_level_scheme.set(RepLevelScheme.NUM_ROSTERED.value)
            self.rep_level_dict["C"].set("24")
            self.rep_level_dict["1B"].set("40")
            self.rep_level_dict["2B"].set("38")
            self.rep_level_dict["SS"].set("42")
            self.rep_level_dict["3B"].set("24")
            self.rep_level_dict["OF"].set("95")
            self.rep_level_dict["Util"].set("200")
            self.rep_level_dict["SP"].set("85")
            self.rep_level_dict["RP"].set("70")
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
        else:
            v = self.value_calc
            self.game_type.set(ScoringFormat.enum_to_full_name_map()[v.format])
            self.sel_proj.set(v.projection.name)
            self.projection = v.projection
            self.num_teams_str.set(int(v.get_input(CDT.NUM_TEAMS)))
            if v.get_input(CDT.HITTER_SPLIT) is None:
                self.manual_split.set(False)
                self.hitter_allocation.set("60")
            else:
                self.manual_split.set(True)
                self.hitter_allocation.set(int(v.get_input(CDT.HITTER_SPLIT)))
            self.non_prod_dollars_str.set(int(v.get_input(CDT.NON_PRODUCTIVE_DOLLARS)))
            self.hitter_basis.set(RankingBasis.enum_to_display_dict()[v.hitter_basis])
            self.min_pa.set(int(v.get_input(CDT.PA_TO_RANK)))
            self.pitcher_basis.set(RankingBasis.enum_to_display_dict()[v.pitcher_basis])
            self.min_sp_ip.set(int(v.get_input(CDT.SP_IP_TO_RANK)))
            self.min_rp_ip.set(int(v.get_input(CDT.RP_IP_TO_RANK)))
            self.rep_level_scheme.set(int(v.get_input(CDT.REP_LEVEL_SCHEME)))
            if self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
                for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
                    self.rep_level_dict[pos.value].set(self.value_calc.get_input(CDT.pos_to_rep_level().get(pos)))
            else:
                for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
                    self.rep_level_dict[pos.value].set(self.value_calc.get_input(CDT.pos_to_num_rostered().get(pos)))
            self.update_calc_output_frame()
        pd.set_completion_percent(33)
        if len(self.tables) > 0:
            for table in self.tables.values():
                table.refresh()
                pd.increment_completion_percent(5)
        pd.set_completion_percent(100)
        pd.destroy()

    def create_input_frame(self):

        self.input_frame = inpf = ttk.Frame(self)
        inpf.grid(column=0,row=0, padx=5, sticky=tk.N, pady=17)

        validation = inpf.register(self.int_validation)

        ttk.Label(inpf, text="Selected Projections:").grid(column=0,row=0, pady=5)
        self.sel_proj = tk.StringVar()
        self.sel_proj.set("None")
        self.projection = None
        ttk.Label(inpf, textvariable=self.sel_proj).grid(column=1,row=0)
        ttk.Button(inpf, text="Select...", command=self.select_projection).grid(column=2,row=0)

        gt_map = ScoringFormat.enum_to_full_name_map()
        ttk.Label(inpf, text="Game Type:").grid(column=0,row=2,pady=5)
        self.game_type = StringVar()
        self.game_type.set(gt_map[ScoringFormat.FG_POINTS])
        gt_combo = ttk.Combobox(inpf, textvariable=self.game_type)
        gt_combo.bind("<<ComboboxSelected>>", self.update_game_type)
        # TODO: Don't hardcode game types, include other types

        gt_combo['values'] = (gt_map[ScoringFormat.FG_POINTS], gt_map[ScoringFormat.SABR_POINTS])
        gt_combo.grid(column=1,row=2,pady=5)

        ttk.Label(inpf, text="Number of Teams:").grid(column=0, row=3,pady=5)
        self.num_teams_str = StringVar()
        self.num_teams_str.set("12")
        team_entry = ttk.Entry(inpf, textvariable=self.num_teams_str)
        team_entry.grid(column=1,row=3,pady=5)
        team_entry.config(validate="key", validatecommand=(validation, '%P'))

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
        non_prod = ttk.Entry(inpf, textvariable=self.non_prod_dollars_str)
        non_prod.grid(column=1,row=6,pady=5)
        non_prod.config(validate="key", validatecommand=(validation, '%P'))

        ttk.Label(inpf, text="Hitter Value Basis:").grid(column=0,row=7,pady=5)
        self.hitter_basis = StringVar()
        self.hitter_basis.set('P/G')
        self.hitter_basis_cb = hbcb = ttk.Combobox(inpf, textvariable=self.hitter_basis)
        hbcb['values'] = ('P/G','P/PA')
        hbcb.grid(column=1,row=7,pady=5)

        ttk.Label(inpf, text="Min PA to Rank:").grid(column=0, row= 8, pady=5)
        self.min_pa = StringVar()
        self.min_pa.set("150")
        pa_entry = ttk.Entry(inpf, textvariable=self.min_pa)
        pa_entry.grid(column=1,row=8, pady=5)
        pa_entry.config(validate="key", validatecommand=(validation, '%P'))
        
        ttk.Label(inpf, text="Pitcher Value Basis:").grid(column=0,row=9,pady=5)
        self.pitcher_basis = StringVar()
        self.pitcher_basis.set('P/IP')
        self.pitcher_basis_cb = pbcb = ttk.Combobox(inpf, textvariable=self.pitcher_basis)
        pbcb['values'] = ('P/IP','P/G')
        pbcb.grid(column=1,row=9,pady=5)

        ttk.Label(inpf, text="Min SP IP to Rank:").grid(column=0, row= 10, pady=5)
        self.min_sp_ip = StringVar()
        self.min_sp_ip.set("70")
        ttk.Entry(inpf, textvariable=self.min_sp_ip).grid(column=1,row=10, pady=5)

        ttk.Label(inpf, text="Min RP IP to Rank:").grid(column=0, row= 11, pady=5)
        self.min_rp_ip = StringVar()
        self.min_rp_ip.set("30")
        ttk.Entry(inpf, textvariable=self.min_rp_ip).grid(column=1,row=11, pady=5)
        
        # This is its own method to make the __init__ more readable
        self.set_replacement_level_ui(inpf)

        ttk.Button(inpf, text="Calculate", command=self.calculate_values).grid(row=24, column=0)

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

        self.player_columns = ('Value', 'Name', 'Team', 'Pos')
        self.overall_columns = ('P/G', 'P/IP', 'Points')
        self.hitting_columns = ('P/G', 'Points', 'G', 'PA', 'AB', 'H', '2B', '3B', 'HR', 'BB', 'HBP', 'SB','CS')
        self.pitching_columns = ('P/IP', 'Points', 'G', 'GS', 'IP', 'SO','H','BB','HBP','HR','SV','HLD')
        
        col_align = {}
        col_align['Name'] = W
        col_width = {}
        col_width['Name'] = 125

        self.overall_table = ot = Table(overall_frame, self.player_columns + self.overall_columns, column_widths=col_width, column_alignments=col_align, sortable_columns=self.player_columns + self.overall_columns)
        self.tables[Position.OVERALL] = ot
        ot.set_refresh_method(self.refresh_overall)
        ot.grid(row=0, column=0)
        ot.add_scrollbar()

        self.bat_table = Table(bat_frame, self.player_columns + self.hitting_columns, column_widths=col_width, column_alignments=col_align, sortable_columns=self.player_columns + self.hitting_columns)
        self.tables[Position.OFFENSE] = self.bat_table
        self.bat_table.set_refresh_method(lambda: self.refresh_hitters(Position.OFFENSE))
        self.bat_table.grid(row=0, column=0)
        self.bat_table.add_scrollbar()

        self.arm_table = Table(arm_frame, self.player_columns + self.pitching_columns, column_widths=col_width, column_alignments=col_align, sortable_columns=self.player_columns + self.pitching_columns)
        self.tables[Position.PITCHER] = self.arm_table
        self.arm_table.set_refresh_method(lambda: self.refresh_pitchers(Position.PITCHER))
        self.arm_table.grid(row=0,column=0)
        self.arm_table.add_scrollbar()

        for pos in Position.get_discrete_offensive_pos():
            frame = ttk.Frame(self.tab_control)
            self.tab_control.add(frame, text=pos.value)
            pt = Table(frame, self.player_columns + self.hitting_columns, column_widths=col_width, column_alignments=col_align, sortable_columns=self.player_columns + self.hitting_columns)
            self.tables[pos] = pt
            pt.set_refresh_method(lambda _pos=pos: self.refresh_hitters(_pos))
            pt.grid(row=0, column=0)
            pt.add_scrollbar()

        for pos in Position.get_discrete_pitching_pos():
            frame = ttk.Frame(self.tab_control)
            self.tab_control.add(frame, text=pos.value)
            pt = Table(frame, self.player_columns + self.pitching_columns, column_widths=col_width, column_alignments=col_align, sortable_columns=self.player_columns + self.pitching_columns)
            self.tables[pos] = pt
            pt.set_refresh_method(lambda _pos=pos: self.refresh_pitchers(_pos))
            pt.grid(row=0, column=0)
            pt.add_scrollbar()

    def update_game_type(self, event):
        pd = progress.ProgressDialog(self, title='Updating Game Type')
        pd.increment_completion_percent(33)
        self.populate_projections(pd)
        #TODO: other actions
        pd.set_completion_percent(100)
        pd.destroy()

    def select_projection(self):
        count = projection_services.get_projection_count()
        if count == 0:
            dialog = proj_download.Dialog(self)
            self.projection = dialog.projection
        else:
            dialog = selection_projection.Dialog(self)
        if dialog.projection is not None:
            pd = progress.ProgressDialog(self, title='Loading Projection')
            pd.increment_completion_percent(15)
            self.projection = projection_services.get_projection(dialog.projection.index)
            pd.set_completion_percent(100)
            pd.destroy()
            self.sel_proj.set(self.projection.name)
        else:
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
        #self.bat_table.refresh()
        #pd.increment_completion_percent(25)
        #self.arm_table.refresh()
        #pd.increment_completion_percent(25)
        if fresh_pd:
            pd.set_completion_percent(100)
            pd.destroy()
    
    def get_overall_row(self, pp):
        val = []
        if len(self.value_calc.values) > 0:
            pv = self.value_calc.get_player_value(pp.player.index, Position.OVERALL)
            if pv is None:
                val.append("$0.0")
            else:
                val.append("${:.1f}".format(pv.value))
        else:
            val.append('-')
        val.append(pp.player.name)
        val.append(pp.player.team)
        val.append(pp.player.position)
        o_points = calculation_services.get_points(pp, Position.OFFENSE, sabr=(self.game_type.get() == ScoringFormat.enum_to_full_name_map()[ScoringFormat.SABR_POINTS]))
        games = pp.get_stat(StatType.G_HIT)
        if games is None or games == 0:
            val.append("0.00")
        else:
            val.append("{:.2f}".format(o_points / games))
        
        p_points = calculation_services.get_points(pp, Position.PITCHER, sabr=(self.game_type.get() == ScoringFormat.enum_to_full_name_map()[ScoringFormat.SABR_POINTS]))
        ip = pp.get_stat(StatType.IP)
        if ip is None or ip == 0:
            val.append("0.00")
        else:
            val.append("{:.2f}".format(p_points/ip))
        val.append("{:.1f}".format(p_points + o_points))
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
        points = calculation_services.get_points(pp, pos, sabr=(self.game_type.get() == ScoringFormat.enum_to_full_name_map()[ScoringFormat.SABR_POINTS]))
        if pos in Position.get_offensive_pos():
            games = pp.get_stat(StatType.G_HIT)
            if games is None or games == 0:
                val.append("0.00")
            else:
                val.append("{:.2f}".format(points / games))
        else:
            ip = pp.get_stat(StatType.IP)
            if ip is None or ip == 0:
                val.append("0.00")
            else:
                val.append("{:.2f}".format(points/ip))
        val.append("{:.1f}".format(points))
        for col in cols:
            if col in enum_dict:
                stat = pp.get_stat(enum_dict[col])
                fmt = StatType.get_stat_format()[enum_dict[col]]
                if stat is None:
                    val.append(fmt.format(0))
                else:
                    val.append(fmt.format(stat))
        return val
    
    def refresh_overall(self):
        if self.projection is not None:
            for pp in self.projection.player_projections:
                val = self.get_overall_row(pp)
                self.tables[Position.OVERALL].insert('', tk.END, text=str(pp.player_id), values=val)

    def refresh_hitters(self, pos):
        if self.projection is not None:
            for pp in self.projection.player_projections:
                if pp.player.pos_eligible(pos) and pp.get_stat(StatType.AB) is not None:
                    val = self.get_player_row(pp, StatType.hit_to_enum_dict(), self.hitting_columns, pos)
                    self.tables[pos].insert('', tk.END, text=str(pp.player_id), values=val)
    
    def refresh_pitchers(self, pos):
        if self.projection is not None:
            for pp in self.projection.player_projections:
                if pp.player.pos_eligible(pos) and pp.get_stat(StatType.IP) is not None:
                    val = self.get_player_row(pp, StatType.pitch_to_enum_dict(), self.pitching_columns, pos)
                    self.tables[pos].insert('', tk.END, text=str(pp.player_id), values=val)
    
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

        self.export_btn = eb = ttk.Button(outf, text="Export Values", command=self.export_values)
        eb.grid(row=row, column=1)
        eb['state'] = DISABLED

    def update_calc_output_frame(self):
        self.output_title.set("Value Calculation Results")
        if self.manual_split.get():
            self.dollars_per_fom_val.set('$' + "{:.3f}".format(self.value_calc.get_output(CDT.HITTER_DOLLAR_PER_FOM)) + '(Bat), $' + "{:.3f}".format(self.value_calc.get_output(CDT.PITCHER_DOLLAR_PER_FOM)) + '(Arm)')
        else:
            self.dollars_per_fom_val.set('$' + "{:.3f}".format(self.value_calc.get_output(CDT.DOLLARS_PER_FOM)))
        self.total_fom_sv.set("{:.0f}".format(self.value_calc.get_output(CDT.TOTAL_FOM_ABOVE_REPLACEMENT)))
        self.total_bat_rostered_sv.set(int(self.value_calc.get_output(CDT.TOTAL_HITTERS_ROSTERED)))
        self.total_pitch_rostered_sv.set(int(self.value_calc.get_output(CDT.TOTAL_PITCHERS_ROSTERED)))
        self.total_games_rostered_sv.set("{:.0f}".format(self.value_calc.get_output(CDT.TOTAL_GAMES_PLAYED)))
        self.total_ip_rostered_sv.set("{:.0f}".format(self.value_calc.get_output(CDT.TOTAL_INNINGS_PITCHED)))
        hitter_rb = RankingBasis.enum_to_display_dict()[self.value_calc.hitter_basis]
        self.bat_rep_level_lbl.set(f"Rep. Level ({hitter_rb})")
        pitcher_rb = RankingBasis.enum_to_display_dict()[self.value_calc.pitcher_basis]
        self.pitch_rep_level_lbl.set(f"Rep. Level ({pitcher_rb})")

        for pos in Position.get_discrete_offensive_pos():
            self.pos_rostered_sv[pos].set(int(self.value_calc.get_output(CDT.pos_to_num_rostered()[pos])))
            self.pos_rep_lvl_sv[pos].set("{:.2f}".format(self.value_calc.get_output(CDT.pos_to_rep_level()[pos])))
        
        for pos in Position.get_discrete_pitching_pos():
            self.pos_rostered_sv[pos].set(int(self.value_calc.get_output(CDT.pos_to_num_rostered()[pos])))
            self.pos_rep_lvl_sv[pos].set("{:.2f}".format(self.value_calc.get_output(CDT.pos_to_rep_level()[pos])))
        
        self.save_btn['state'] = ACTIVE
        self.export_btn['state'] = ACTIVE
    
    def save_values(self):
        dialog = name_desc.Dialog(self, 'Save Values')
        #print("dialog.state = " + dialog.state)
        if dialog.status == mb.OK:
            pd = progress.ProgressDialog(self, title='Saving Calculation')
            pd.increment_completion_percent(5)
            self.value_calc.index = None
            self.value_calc.name = dialog.name_tv.get()
            self.value_calc.description = dialog.desc_tv.get()
            self.value_calc.timestamp = datetime.now()
            self.value_calc = calculation_services.save_calculation(self.value_calc)
            self.projection = self.value_calc.projection
            #calculation_services.save_calculation(self.value_calc)
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
    
    def set_replacement_level_ui(self, inpf):
        ttk.Label(inpf, text="Select Replacement Level Scheme").grid(column=0,row=12,columnspan=2,pady=5)

        self.rep_level_scheme = IntVar()
        self.rep_level_scheme.set(RepLevelScheme.NUM_ROSTERED.value)

        ttk.Radiobutton(inpf, text="Number Rostered", value=RepLevelScheme.NUM_ROSTERED.value, command=self.update_rep_level_scheme, variable=self.rep_level_scheme).grid(column=0,row=13,pady=5)
        ttk.Radiobutton(inpf, text="Replacment Level", value=RepLevelScheme.STATIC_REP_LEVEL.value, command=self.update_rep_level_scheme, variable=self.rep_level_scheme).grid(column=1,row=13,pady=5)
        ttk.Radiobutton(inpf, text="Fill Games", value=RepLevelScheme.FILL_GAMES.value, command=self.update_rep_level_scheme, variable=self.rep_level_scheme).grid(column=2,row=13,pady=5)
    
        self.rep_level_txt = StringVar()
        self.rep_level_txt.set("Set number of rostered players at each position:")
        ttk.Label(inpf, textvariable=self.rep_level_txt).grid(column=0, row=14, columnspan=2, pady=5)
        
        ttk.Label(inpf, text="C").grid(row=15, column=0)
        self.rep_level_dict["C"] = StringVar()
        self.rep_level_dict["C"].set("24")
        ttk.Entry(inpf, textvariable=self.rep_level_dict["C"]).grid(row=15,column=1)

        ttk.Label(inpf, text="1B").grid(row=16, column=0)
        self.rep_level_dict["1B"] = StringVar()
        self.rep_level_dict["1B"].set("40")
        ttk.Entry(inpf, textvariable=self.rep_level_dict["1B"]).grid(row=16,column=1)

        ttk.Label(inpf, text="2B").grid(row=17, column=0)
        self.rep_level_dict["2B"] = StringVar()
        self.rep_level_dict["2B"].set("38")
        ttk.Entry(inpf, textvariable=self.rep_level_dict["2B"]).grid(row=17,column=1)

        ttk.Label(inpf, text="SS").grid(row=18, column=0)
        self.rep_level_dict["SS"] = StringVar()
        self.rep_level_dict["SS"].set("42")
        ttk.Entry(inpf, textvariable=self.rep_level_dict["SS"]).grid(row=18,column=1)

        ttk.Label(inpf, text="3B").grid(row=19, column=0)
        self.rep_level_dict["3B"] = StringVar()
        self.rep_level_dict["3B"].set("24")
        ttk.Entry(inpf, textvariable=self.rep_level_dict["3B"]).grid(row=19,column=1)

        ttk.Label(inpf, text="OF").grid(row=20, column=0)
        self.rep_level_dict["OF"] = StringVar()
        self.rep_level_dict["OF"].set("95")
        ttk.Entry(inpf, textvariable=self.rep_level_dict["OF"]).grid(row=20,column=1)

        ttk.Label(inpf, text="Util").grid(row=21, column=0)
        self.rep_level_dict["Util"] = StringVar()
        self.rep_level_dict["Util"].set("200")
        ttk.Entry(inpf, textvariable=self.rep_level_dict["Util"]).grid(row=21,column=1)

        ttk.Label(inpf, text="SP").grid(row=22, column=0)
        self.rep_level_dict["SP"] = StringVar()
        self.rep_level_dict["SP"].set("85")
        ttk.Entry(inpf, textvariable=self.rep_level_dict["SP"]).grid(row=22,column=1)

        ttk.Label(inpf, text="RP").grid(row=23, column=0)
        self.rep_level_dict["RP"] = StringVar()
        self.rep_level_dict["RP"].set("70")
        ttk.Entry(inpf, textvariable=self.rep_level_dict["RP"]).grid(row=23,column=1)
    
    def update_rep_level_scheme(self):
        if self.rep_level_scheme.get() == RepLevelScheme.NUM_ROSTERED.value:
            self.rep_level_txt.set("Set number of rostered players for each position:")
        elif self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
            self.rep_level_txt.set("Set replacement level production for each position:")
        else:
            self.rep_level_txt.set("Set number of rostered players beyond games filled for each position:")
    
    def calculate_values(self):
        if self.has_errors():
            logging.warning("Input errors")
            return
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
        self.value_calc.set_input(CDT.REP_LEVEL_SCHEME, float(self.rep_level_scheme.get()))
        if self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
            for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
                self.value_calc.set_input(CDT.pos_to_rep_level().get(pos), float(self.rep_level_dict[pos.value].get()))
        else:
            for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
                self.value_calc.set_input(CDT.pos_to_num_rostered().get(pos), float(self.rep_level_dict[pos.value].get()))
        
        logging.debug("About to perform point_calc")
        calculation_services.perform_point_calculation(self.value_calc, progress.ProgressDialog(self, title='Performing Calculation'))
        logging.debug("Performed calc")
        self.update_values()
        #self.populate_projections()
        self.update_calc_output_frame()

    def update_values(self):
        for pos, table in self.tables.items():
            for index in table.get_children():
                pv = self.value_calc.get_player_value(int(table.item(index)['text']), pos)
                if pv is None:
                    table.set(index, 0, "$0.0")
                else:
                    table.set(index, 0, "${:.1f}".format(pv.value))
    
    def int_validation(self, input):
        if input.isdigit():
            return True
        if input == "":
            return True
        return False
        
    def has_errors(self):
        errors = []
        bad_rep_level = []
        if self.rep_level_scheme.get() == RepLevelScheme.NUM_ROSTERED.value or self.rep_level_scheme.get() == RepLevelScheme.FILL_GAMES.value:
            for key, value in self.rep_level_dict.items():
                if not value.get().isnumeric():
                    bad_rep_level.append(key)
        else:
            for key, value in self.rep_level_dict.items():
                if float(value.get()) > 10.0:
                    if self.pitcher_basis.get() == RankingBasis.PPG and key == 'SP' and float(value.get()) < 40.0:
                        continue
                    bad_rep_level.append(key)
        
        if len(bad_rep_level) > 0:
            errors.append(f'The following positions have bad replacement level inputs (check scheme): {", ".join(bad_rep_level)}')

        #TODO Other validations

        if len(errors) > 0:
            delim = "\n\t-"
            mb.showerror("Input Error(s)", f'Errors in inputs. Please correct: \n\t-{delim.join(errors)}')

        return len(errors) != 0
    
    def exit_tasks(self):
        print('This is inherited')
        return True

def main(preferences):
    try:
        win = ValuesCalculation(preferences)
    except Exception as e:
        logging.exception("Error encountered")
        mb.showerror("Error", f'Fatal program error. See ./logs/toolbox.log')

if __name__ == '__main__':
    main()