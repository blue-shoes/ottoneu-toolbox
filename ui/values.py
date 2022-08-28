import logging
import tkinter as tk     
from tkinter import *              
from tkinter import ttk 
from tkinter import messagebox as mb
from ui.table import Table
from ui.base import BaseUi
from domain.domain import CalculationInput, ValueData, ValueCalculation, ScoringFormat
from domain.enum import CalculationDataType, RankingBasis, RepLevelScheme, StatType, Position
from services import projection_services, calculation_services
from ui.dialog import proj_download, selection_projection, progress

class ValuesCalculation(BaseUi):
    def __init__(self, preferences):
        super().__init__(preferences=preferences)
        
        self.value_calc = ValueCalculation()
        self.rep_level_dict = {}

        self.create_input_frame()
        self.create_proj_val_frame()
        self.create_output_frame()

    def create_input_frame(self):

        self.input_frame = inpf = ttk.Frame(self.main_win)
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

    def create_proj_val_frame(self):
        self.proj_val_frame = pvf = ttk.Frame(self.main_win)
        pvf.grid(column=1,row=0,padx=5, sticky=tk.N, pady=17)

        self.tab_control = ttk.Notebook(pvf, width=570, height=300)
        self.tab_control.grid(row=0, column=0)

        bat_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(bat_frame, text='Hitters')

        arm_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(arm_frame, text='Pitchers')

        self.player_columns = ('Value', 'Name', 'Team', 'Pos')
        self.hitting_columns = ('P/G', 'Points', 'G', 'PA', 'AB', 'H', '2B', '3B', 'HR', 'BB', 'HBP', 'SB','CS')
        self.pitching_columns = ('P/IP', 'Points', 'G', 'GS', 'IP', 'SO','H','BB','HBP','HR','SV','HLD')
        
        col_align = {}
        col_align['Name'] = W

        self.bat_table = Table(bat_frame, self.player_columns + self.hitting_columns, column_alignments=col_align, sortable_columns=self.player_columns + self.hitting_columns)
        self.bat_table.set_refresh_method(self.refresh_hitters)
        self.bat_table.grid(row=0, column=0)
        self.bat_table.add_scrollbar()

        self.arm_table = Table(arm_frame, self.player_columns + self.pitching_columns, column_alignments=col_align, sortable_columns=self.player_columns + self.pitching_columns)
        self.arm_table.set_refresh_method(self.refresh_pitchers)
        self.arm_table.grid(row=0,column=0)
        self.arm_table.add_scrollbar()

    def update_game_type(self):
        i = 1
        #TODO: Update input fields for unique game types

    def select_projection(self):
        count = projection_services.get_projection_count()
        if count == 0:
            dialog = proj_download.Dialog(self.main_win)
            self.projection = dialog.projection
        else:
            dialog = selection_projection.Dialog(self.main_win)
        if dialog.projection is not None:
            pd = progress.ProgressDialog(self.main_win, title='Loading Projection')
            pd.increment_completion_percent(15)
            self.projection = projection_services.get_projection(dialog.projection.index)
            pd.set_completion_percent(100)
            pd.destroy()
            self.sel_proj.set(self.projection.name)
        else:
            self.projection = None
            self.sel_proj.set("No Projection Selected")

        self.populate_projections()
    
    def populate_projections(self):
        self.bat_table.refresh()
        self.arm_table.refresh()
    
    def get_player_row(self, pp, enum_dict, cols, pos):
        val = []
        if len(self.value_calc.values) > 0:
            pv = self.value_calc.get_player_value(pp.player.index, pos)
            if pv is None:
                val.append("$0")
            else:
                val.append(f"${pv.value}")
        else:
            val.append('-')
        val.append(pp.player.name)
        val.append(pp.player.team)
        val.append(pp.player.position)
        if len(self.value_calc.values) > 0:
            points = calculation_services.get_points(pp, pos)
            if pos in Position.get_offensive_pos():
                games = pp.get_stat(StatType.G_HIT)
                if games is None or games == 0:
                    val.append(0)
                else:
                    val.append(points / games)
            else:
                ip = pp.get_stat(StatType.IP)
                if ip is None or ip == 0:
                    val.append(0)
                else:
                    val.append(points/ip)
            val.append(points)
        else:
            val.append('-')
            val.append('-')
        for col in cols:
            if col in enum_dict:
                stat = pp.get_stat(enum_dict[col])
                if stat is None:
                    val.append(0)
                else:
                    val.append(stat)
        return val

    def refresh_hitters(self):
        print('in refresh hitters')
        for pp in self.projection.player_projections:
            if pp.get_stat(StatType.AB) is not None:
                val = self.get_player_row(pp, StatType.hit_to_enum_dict(), self.hitting_columns, Position.OFFENSE)
                self.bat_table.insert('', tk.END, text=str(pp.index), values=val)
    
    def refresh_pitchers(self):
        print('in refresh pitchers')
        for pp in self.projection.player_projections:
            if pp.get_stat(StatType.IP) is not None:
                val = self.get_player_row(pp, StatType.pitch_to_enum_dict(), self.pitching_columns, Position.PITCHER)
                self.arm_table.insert('', tk.END, text=str(pp.index), values=val)
    
    def create_output_frame(self):
        self.output_frame = outf = ttk.Frame(self.main_win)
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
        
        ttk.Label(outf, text="Total Rostered:").grid(row=row, column=0)
        self.total_bat_rostered_sv = StringVar()
        self.total_bat_rostered_sv.set("--")
        ttk.Label(outf, textvariable=self.total_bat_rostered_sv).grid(row=row, column=1)
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
        ttk.Label(outf, text="Total Rostered:").grid(row=row, column=0)
        self.total_pitch_rostered_sv = StringVar()
        self.total_pitch_rostered_sv.set("--")
        ttk.Label(outf, textvariable=self.total_pitch_rostered_sv).grid(row=row, column=1)
        row += 1

    def update_calc_output_frame(self):
        self.output_title.set("Value Calculation Results")
        self.dollars_per_fom_val.set('$' + "{:.3f}".format(self.value_calc.get_output(CalculationDataType.DOLLARS_PER_FOM)))
        self.total_fom_sv.set("{:.0f}".format(self.value_calc.get_output(CalculationDataType.TOTAL_FOM_ABOVE_REPLACEMENT)))
        self.total_bat_rostered_sv.set(self.value_calc.get_output(CalculationDataType.TOTAL_HITTERS_ROSTERED))
        self.total_pitch_rostered_sv.set(self.value_calc.get_output(CalculationDataType.TOTAL_PITCHERS_ROSTERED))
        hitter_rb = RankingBasis.enum_to_display_dict()[self.value_calc.get_input(CalculationDataType.HITTER_RANKING_BASIS)]
        self.bat_rep_level_lbl.set(f"Rep. Level ({hitter_rb})")
        pitcher_rb = RankingBasis.enum_to_display_dict()[self.value_calc.get_input(CalculationDataType.PITCHER_RANKING_BASIS)]
        self.pitch_rep_level_lbl.set(f"Rep. Level ({pitcher_rb})")

        for pos in Position.get_discrete_offensive_pos():
            self.pos_rostered_sv[pos].set(self.value_calc.get_output(CalculationDataType.pos_to_num_rostered()[pos]))
            self.pos_rep_lvl_sv[pos].set("{:.2f}".format(self.value_calc.get_output(CalculationDataType.pos_to_rep_level()[pos])))
        
        for pos in Position.get_discrete_pitching_pos():
            self.pos_rostered_sv[pos].set(self.value_calc.get_output(CalculationDataType.pos_to_num_rostered()[pos]))
            self.pos_rep_lvl_sv[pos].set("{:.2f}".format(self.value_calc.get_output(CalculationDataType.pos_to_rep_level()[pos])))

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
        self.value_calc.set_input(CalculationDataType.NUM_TEAMS, float(self.num_teams_str.get()))
        if self.manual_split.get():
            self.value_calc.set_input(CalculationDataType.HITTER_SPLIT, float(self.hitter_allocation.get()))
        self.value_calc.set_input(CalculationDataType.NON_PRODUCTIVE_DOLLARS, int(self.non_prod_dollars_str.get()))
        self.value_calc.set_input(CalculationDataType.HITTER_RANKING_BASIS, RankingBasis.display_to_enum_map()[self.hitter_basis.get()])
        self.value_calc.set_input(CalculationDataType.PA_TO_RANK, float(self.min_pa.get()))
        self.value_calc.set_input(CalculationDataType.PITCHER_RANKING_BASIS, RankingBasis.display_to_enum_map()[self.pitcher_basis.get()])
        self.value_calc.set_input(CalculationDataType.SP_IP_TO_RANK, float(self.min_sp_ip.get()))
        self.value_calc.set_input(CalculationDataType.RP_IP_TO_RANK, float(self.min_rp_ip.get()))
        self.value_calc.set_input(CalculationDataType.REP_LEVEL_SCHEME, float(self.rep_level_scheme.get()))
        if self.rep_level_scheme.get() == RepLevelScheme.STATIC_REP_LEVEL.value:
            self.value_calc.set_input(CalculationDataType.REP_LEVEL_C, float(self.rep_level_dict['C'].get()))
            self.value_calc.set_input(CalculationDataType.REP_LEVEL_1B, float(self.rep_level_dict['1B'].get()))
            self.value_calc.set_input(CalculationDataType.REP_LEVEL_2B, float(self.rep_level_dict['2B'].get()))
            self.value_calc.set_input(CalculationDataType.REP_LEVEL_SS, float(self.rep_level_dict['SS'].get()))
            self.value_calc.set_input(CalculationDataType.REP_LEVEL_3B, float(self.rep_level_dict['3B'].get()))
            self.value_calc.set_input(CalculationDataType.REP_LEVEL_OF, float(self.rep_level_dict['OF'].get()))
            self.value_calc.set_input(CalculationDataType.REP_LEVEL_UTIL, float(self.rep_level_dict['Util'].get()))
            self.value_calc.set_input(CalculationDataType.REP_LEVEL_SP, float(self.rep_level_dict['SP'].get()))
            self.value_calc.set_input(CalculationDataType.REP_LEVEL_RP, float(self.rep_level_dict['RP'].get()))
        else:
            self.value_calc.set_input(CalculationDataType.ROSTERED_C, int(self.rep_level_dict['C'].get()))
            self.value_calc.set_input(CalculationDataType.ROSTERED_1B, int(self.rep_level_dict['1B'].get()))
            self.value_calc.set_input(CalculationDataType.ROSTERED_2B, int(self.rep_level_dict['2B'].get()))
            self.value_calc.set_input(CalculationDataType.ROSTERED_SS, int(self.rep_level_dict['SS'].get()))
            self.value_calc.set_input(CalculationDataType.ROSTERED_3B, int(self.rep_level_dict['3B'].get()))
            self.value_calc.set_input(CalculationDataType.ROSTERED_OF, int(self.rep_level_dict['OF'].get()))
            self.value_calc.set_input(CalculationDataType.ROSTERED_UTIL, int(self.rep_level_dict['Util'].get()))
            self.value_calc.set_input(CalculationDataType.ROSTERED_SP, int(self.rep_level_dict['SP'].get()))
            self.value_calc.set_input(CalculationDataType.ROSTERED_RP, int(self.rep_level_dict['RP'].get()))
        
        logging.debug("About to perform point_calc")
        calculation_services.perform_point_calculation(self.value_calc, progress.ProgressDialog(self.main_win, title='Performing Calculation'))
        logging.debug("Performed calc")
        self.populate_projections()
        self.update_calc_output_frame()

    
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
                if not value.get().isnumeric() or float(value.get()) > 10.0:
                    bad_rep_level.append(key)
        
        if len(bad_rep_level) > 0:
            errors.append(f'The following positions have bad replacement level inputs (check scheme): {", ".join(bad_rep_level)}')

        #TODO Other validations

        if len(errors) > 0:
            delim = "\n\t-"
            mb.showerror("Input Error(s)", f'Errors in inputs. Please correct: \n\t-{delim.join(errors)}')

        return len(errors) != 0

def main(preferences):
    try:
        win = ValuesCalculation(preferences)
    except Exception as e:
        logging.exception("Error encountered")
        mb.showerror("Error", f'Fatal program error. See ./logs/toolbox.log')

if __name__ == '__main__':
    main()