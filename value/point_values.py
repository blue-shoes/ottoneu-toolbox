import logging
import pandas as pd
import os
from os import path
import value.bat_points
import value.arm_points

from services import projection_services, calculation_services
from domain.domain import ValueCalculation
from domain.enum import CalculationDataType, Position, RepLevelScheme, ScoringFormat

pd.options.mode.chained_assignment = None # from https://stackoverflow.com/a/20627316

class PointValues():

    bat_pos = ['C','1B','2B','3B','SS','MI','OF','Util']
    pitch_pos = ['SP','RP']
    target_innings = 1500.0*12.0
    #replacement_positions = {"C":24,"1B":40,"2B":38,"3B":40,"SS":42,"OF":95,"Util":200,"SP":85,"RP":70}
    #These are essentially minimums for the positions. I would really not expect to go below these. C and Util are unaffected by the algorithm
    replacement_positions = {"C":24,"1B":12,"2B":18,"3B":12,"SS":18,"OF":60,"Util":200,"SP":60,"RP":60}
    replacement_levels = {}

    def __init__(self, value_calc:ValueCalculation, debug=False, rostered_hitters=244, rostered_pitchers=196,
                    rp_limit=999):
        self.intermediate_calculations = debug
        self.target_bat = rostered_hitters
        self.target_pitch = rostered_pitchers
        self.rp_limit = rp_limit
        self.SABR = ScoringFormat.is_sabr(value_calc.format)
        self.value_calc = value_calc

        #Initialize directory for intermediate calc files if required
        self.dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
        self.data_dir = os.path.join(self.dirname, 'data_dirs')
        if not path.exists(self.data_dir):
            os.mkdir(self.data_dir)
        self.intermed_subdirpath = os.path.join(self.dirname, 'data_dirs','intermediate')
        if not path.exists(self.intermed_subdirpath):
            os.mkdir(self.intermed_subdirpath)

    def calculate_values(self, progress=None) -> None:
        '''Sets up and performs the player value calculations inplace for the passed ValueCalculation'''
        projs = projection_services.convert_to_df(self.value_calc.projection)
        self.pos_proj = projs[0]
        self.pitch_proj = projs[1]
        rep_level_scheme = RepLevelScheme._value2member_map_[int(self.value_calc.get_input(CalculationDataType.REP_LEVEL_SCHEME))]
        hitter_rank_basis = self.value_calc.hitter_basis
        pitcher_rank_basis = self.value_calc.pitcher_basis
        num_teams = int(self.value_calc.get_input(CalculationDataType.NUM_TEAMS))
        sabr = self.value_calc.format == ScoringFormat.SABR_POINTS or self.value_calc.format == ScoringFormat.H2H_SABR_POINTS
        non_prod_salary = self.value_calc.get_input(CalculationDataType.NON_PRODUCTIVE_DOLLARS)
        rep_nums = None
        rep_levels = None
        surplus_pos = None
        if rep_level_scheme == RepLevelScheme.NUM_ROSTERED:
            rep_nums = calculation_services.get_num_rostered_rep_levels(self.value_calc)
        elif rep_level_scheme == RepLevelScheme.STATIC_REP_LEVEL:
            rep_levels = calculation_services.get_rep_levels(self.value_calc)
        elif rep_level_scheme == RepLevelScheme.FILL_GAMES:
            surplus_pos = calculation_services.get_num_rostered_rep_levels(self.value_calc)
        logging.debug(f'rep_level_scheme = {rep_level_scheme.value}')
        min_sp_ip = self.value_calc.get_input(CalculationDataType.SP_IP_TO_RANK)
        min_rp_ip = self.value_calc.get_input(CalculationDataType.RP_IP_TO_RANK)
        
        progress.set_task_title('Calculating Batters')
        progress.increment_completion_percent(10)

        pos_points = value.bat_points.BatPoint(
            self.value_calc,
            intermediate_calc=self.intermediate_calculations
        )
        if rep_nums is not None:
            pos_points.replacement_positions = rep_nums
        if rep_levels is not None:
            pos_points.replacement_levels = rep_levels
        if surplus_pos is not None:
            pos_points.surplus_pos = surplus_pos
        pos_min_pa = pos_points.calc_par(self.pos_proj, self.value_calc.get_input(CalculationDataType.PA_TO_RANK))

        progress.set_task_title('Calculating pitchers')
        progress.increment_completion_percent(40)
        #TODO Might need to add usable RP innings as argument
        pitch_points = value.arm_points.ArmPoint(
            self.value_calc,
            intermediate_calc=self.intermediate_calculations
            )
        if rep_nums is not None:
            pitch_points.replacement_positions = rep_nums
        if rep_levels is not None:
            pitch_points.replacement_levels = rep_levels
        if surplus_pos is not None:
            pitch_points.surplus_pos = surplus_pos
            
        real_pitchers = pitch_points.calc_par(self.pitch_proj)

        #TODO: write replacement level info to ValueCalculation.data
        for pos in Position.get_discrete_offensive_pos():
            self.value_calc.set_output(CalculationDataType.pos_to_rep_level().get(pos), pos_points.replacement_levels[pos.value])
            self.value_calc.set_output(CalculationDataType.pos_to_num_rostered().get(pos), pos_points.replacement_positions[pos.value])
        for pos in Position.get_discrete_pitching_pos():
            self.value_calc.set_output(CalculationDataType.pos_to_rep_level().get(pos), pitch_points.replacement_levels[pos.value])
            self.value_calc.set_output(CalculationDataType.pos_to_num_rostered().get(pos), pitch_points.replacement_positions[pos.value])

        progress.set_task_title('Calculating $/FOM and applying')
        progress.increment_completion_percent(30)
        rosterable_pos = pos_min_pa.loc[pos_min_pa['Max FOM'] >= 0]
        rosterable_pitch = real_pitchers.loc[real_pitchers['FOM'] >= 0]

        bat_par = rosterable_pos['Max FOM'].sum()
        total_par = bat_par + rosterable_pitch['FOM'].sum()
        arm_par = rosterable_pitch.apply(pitch_points.usable_par_calc, args=('SP',), axis=1).sum() + rosterable_pitch.apply(pitch_points.usable_par_calc, args=('RP',), axis=1).sum()
        total_usable_par = bat_par + arm_par
        total_players = len(rosterable_pos) + len(rosterable_pitch)
        self.value_calc.set_output(CalculationDataType.TOTAL_HITTERS_ROSTERED, len(rosterable_pos))
        self.value_calc.set_output(CalculationDataType.TOTAL_PITCHERS_ROSTERED, len(rosterable_pitch))

        dollars = 400*num_teams
        dollars -= non_prod_salary
        dollars -= num_teams*40 #remove a dollar per player at or above replacement
        self.dol_per_par = dollars / total_usable_par

        self.value_calc.set_output(CalculationDataType.TOTAL_GAMES_PLAYED, rosterable_pos['G'].sum())
        self.value_calc.set_output(CalculationDataType.TOTAL_INNINGS_PITCHED, rosterable_pitch['IP'].sum())
        self.value_calc.set_output(CalculationDataType.TOTAL_FOM_ABOVE_REPLACEMENT, total_usable_par)
        self.value_calc.set_output(CalculationDataType.DOLLARS_PER_FOM, self.dol_per_par)

        if self.value_calc.get_input(CalculationDataType.HITTER_SPLIT) is not None:
            bat_dollars = dollars * self.value_calc.get_input(CalculationDataType.HITTER_SPLIT) / 100
            arm_dollars = dollars - bat_dollars
            self.bat_dol_per_fom = bat_dollars / bat_par
            self.arm_dol_per_fom = arm_dollars / arm_par
            self.value_calc.set_output(CalculationDataType.HITTER_DOLLAR_PER_FOM, self.bat_dol_per_fom)
            self.value_calc.set_output(CalculationDataType.PITCHER_DOLLAR_PER_FOM, self.arm_dol_per_fom)
        else:
            self.bat_dol_per_fom = 0
            self.arm_dol_per_fom = 0

        self.value_calc.values = [] 

        for pos in self.bat_pos:
            if pos == 'MI':
                pos_value = pd.DataFrame(pos_min_pa.loc[pos_min_pa['Position(s)'].str.contains("2B|SS", case=False, regex=True)])
            elif pos == 'Util':
                pos_value = pd.DataFrame(pos_min_pa)
            else:
                pos_value = pd.DataFrame(pos_min_pa.loc[pos_min_pa['Position(s)'].str.contains(pos)])
            if self.bat_dol_per_fom > 0:
                pos_value['Value'] = pos_value[f'{pos}_FOM'].apply(lambda x: x*self.bat_dol_per_fom + 1.0 if x >= 0 else 0)
            else:
                pos_value['Value'] = pos_value[f'{pos}_FOM'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
            pos_value.sort_values(by=['Value','P/G'], inplace=True, ascending=[False,False])
            pos_value['Dol_Value'] = pos_value['Value'].apply(lambda x : "${:.0f}".format(x))
            if self.value_calc is None:
                pos_value = pos_value[['OttoneuID', 'Dol_Value', 'Name','Team','Position(s)','Points',f'{pos}_FOM','P/G']]
                pos_value.to_csv(f"C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Staging\\{pos}_values.csv", encoding='utf-8-sig')
            else:
                for index, row in pos_value.iterrows():
                    self.value_calc.set_player_value(index, Position._value2member_map_[pos], row['Value'])
        if self.bat_dol_per_fom > 0:
            pos_min_pa['Value'] = pos_min_pa['Max FOM'].apply(lambda x: x*self.bat_dol_per_fom + 1.0 if x >= 0 else 0)
        else:
            pos_min_pa['Value'] = pos_min_pa['Max FOM'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
        pos_min_pa.sort_values('Max FOM', inplace=True)

        for pos in self.pitch_pos:
            pos_value = pd.DataFrame(real_pitchers.loc[real_pitchers[f'IP {pos}'] > 0])
            if self.arm_dol_per_fom > 0:
                pos_value['Value'] = pos_value[f'FOM {pos}'].apply(lambda x: x*self.arm_dol_per_fom + 1.0 if x >= 0 else 0)
            else:
                pos_value['Value'] = pos_value[f'FOM {pos}'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
            pos_value.sort_values(by=['Value','P/IP'], inplace=True, ascending=[False,False])
            pos_value['Dol_Value'] = pos_value['Value'].apply(lambda x : "${:.0f}".format(x))
            
            if self.value_calc is None:
                pos_value = pos_value[['OttoneuID', 'Dol_Value', 'Name','Team','Position(s)','Points',f'FOM {pos}','P/IP']]
                pos_value.to_csv(f"C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Staging\\{pos}_values.csv", encoding='utf-8-sig')
            else:
                for index, row in pos_value.iterrows():
                    self.value_calc.set_player_value(index, Position._value2member_map_[pos], row['Value'])
        if self.arm_dol_per_fom > 0:
            real_pitchers['Value'] = real_pitchers['FOM'].apply(lambda x: x*self.arm_dol_per_fom + 1.0 if x >= 0 else 0)
        else:
            real_pitchers['Value'] = real_pitchers['FOM'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
        real_pitchers.sort_values('FOM', inplace=True)

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_value_detail.csv")
            pos_min_pa.to_csv(filepath, encoding='utf-8-sig')
            filepath = os.path.join(self.intermed_subdirpath, f"pitch_value_detail.csv")
            real_pitchers.to_csv(filepath, encoding='utf-8-sig')
        
        pos_min_pa.rename(columns={'Max FOM':'FOM'}, inplace=True)
        for index, row in pos_min_pa.iterrows():
            self.value_calc.set_player_value(index, Position.OFFENSE, row['Value'])

        pitch_results = real_pitchers
        for index, row in pitch_results.iterrows():
            self.value_calc.set_player_value(index, Position.PITCHER, row['Value'])

        pos_index = pos_min_pa.index
        pitch_index = pitch_results.index
        intersect = pos_index.intersection(pitch_index)

        results = pos_min_pa
        results['P/IP'] = 0
        pitch_results['P/G'] = 0
        for index in intersect:
            results.loc[index, 'Value'] = results.loc[index]['Value'] + pitch_results.loc[index]['Value']
            results.loc[index, 'Points'] = results.loc[index]['Points'] + pitch_results.loc[index]['Points']
            results.loc[index, 'FOM'] = results.loc[index]['FOM'] + pitch_results.loc[index]['FOM']
            results.loc[index, 'P/IP'] = pitch_results.loc[index]['P/IP']
            pitch_results = pitch_results.drop(index=index)

        results = results.append(pitch_results)
        results['Dol_Value'] = results['Value'].apply(lambda x : "${:.0f}".format(x))
        
        for index, row in results.iterrows():
            self.value_calc.set_player_value(index, Position.OVERALL, row['Value'])
