import logging
import pandas as pd
import os
from os import path
import value.bat_points
import value.arm_points

from services import projection_services, calculation_services
from domain.enum import CalculationDataType, Position, RepLevelScheme, RankingBasis, ScoringFormat
from domain.domain import PlayerValue

from scrape import scrape_ottoneu

pd.options.mode.chained_assignment = None # from https://stackoverflow.com/a/20627316

class PointValues():

    bat_pos = ['C','1B','2B','3B','SS','MI','OF','Util']
    pitch_pos = ['SP','RP']
    target_innings = 1500.0*12.0
    #replacement_positions = {"C":24,"1B":40,"2B":38,"3B":40,"SS":42,"OF":95,"Util":200,"SP":85,"RP":70}
    #These are essentially minimums for the positions. I would really not expect to go below these. C and Util are unaffected by the algorithm
    replacement_positions = {"C":24,"1B":12,"2B":18,"3B":12,"SS":18,"OF":60,"Util":200,"SP":60,"RP":60}
    replacement_levels = {}

    def __init__(self, value_calc = None, projection='steamer', depthchart_pt=False, ros=False, debug=False, rostered_hitters=244, rostered_pitchers=196,
                    rp_limit=999, SABR_points=False, force_proj_download=False):
        self.projection = projection
        self.depthchart_pt = depthchart_pt
        self.ros = ros
        self.intermediate_calculations = debug
        self.target_bat = rostered_hitters
        self.target_pitch = rostered_pitchers
        self.rp_limit = rp_limit
        self.SABR = SABR_points
        self.force = force_proj_download
        self.value_calc = value_calc

        #Initialize directory for intermediate calc files if required
        self.dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
        self.data_dir = os.path.join(self.dirname, 'data_dirs')
        if not path.exists(self.data_dir):
            os.mkdir(self.data_dir)
        self.intermed_subdirpath = os.path.join(self.dirname, 'data_dirs','intermediate')
        if not path.exists(self.intermed_subdirpath):
            os.mkdir(self.intermed_subdirpath)


    def set_positions(self, df, positions):
        df = df.merge(positions[['Position(s)', 'OttoneuID']], how='left', left_index=True, right_index=True)
        #Some projections can be not in the Otto-verse, so set their Ottoneu ID to -1
        df['OttoneuID'] = df['OttoneuID'].fillna(-1) 
        df['OttoneuID'] = df['OttoneuID'].astype(int)
        #Players not in the Otto-verse need a position
        df['Position(s)'] = df['Position(s)'].fillna('Util')
        df['Team'] = df['Team'].fillna('---')
        return df

    def convertToDcPlayingTime(self, proj, dc_proj, position):
        #String and rate columns that are unaffected
        static_columns = ['playerid', 'Name', 'Team','-1','AVG','OBP','SLG','OPS','wOBA','wRC+','ADP','WHIP','K/9','BB/9','ERA','FIP']
        #Columns directly taken from DC
        dc_columns = ['G','PA','GS','IP']
        #Filter projection to only players present in the DC projection and then drop the temp DC column
        proj = proj.assign(DC=proj.index.isin(dc_proj.index).astype(bool))
        proj = proj[proj['DC'] == True]
        proj.drop('DC', axis=1, inplace=True)
        if position:
            denom = 'PA'
        else:
            denom = 'IP'
        for column in proj.columns:
            if column in static_columns:
                continue
            elif column in dc_columns:
                #take care of this later so we can do the rate work first
                continue
            else:
                #Ration the counting stat
                proj[column] = proj[column] / proj[denom] * dc_proj[denom]
        #We're done with the original projection denominator columns, so now set them to the DC values
        for column in dc_columns:
            if column in proj.columns:
                proj[column] = dc_proj[column]
        return proj
    
    def set_up_calc(self):
        projs = projection_services.download_projections(self.projection, self.ros, self.depthchart_pt)
        pos_proj = projs[0]
        pitch_proj = projs[1]
        
        try:
            otto_scraper = scrape_ottoneu.Scrape_Ottoneu()
            positions = otto_scraper.get_player_position_ds(self.force)
        finally:
            otto_scraper.close()

        #Set position data from Ottoneu
        self.pos_proj = self.set_positions(pos_proj, positions)
        self.pitch_proj = self.set_positions(pitch_proj, positions)

    def calculate_values(self, rank_pos, progress=None):

        if self.value_calc is None:
            self.set_up_calc()
            rep_level_scheme = RepLevelScheme.FILL_GAMES
            hitter_rank_basis = RankingBasis.PPG
            num_teams = 12
            sabr = False
            non_prod_salary = 48
            surplus_pos = {}
        else:
            projs = projection_services.convert_to_df(self.value_calc.projection)
            self.pos_proj = projs[0]
            self.pitch_proj = projs[1]
            self.intermediate_calculations = False
            rep_level_scheme = RepLevelScheme._value2member_map_[int(self.value_calc.get_input(CalculationDataType.REP_LEVEL_SCHEME))]
            hitter_rank_basis = self.value_calc.get_input(CalculationDataType.HITTER_RANKING_BASIS)
            pitcher_rank_basis = self.value_calc.get_input(CalculationDataType.PITCHER_RANKING_BASIS)
            num_teams = int(self.value_calc.get_input(CalculationDataType.NUM_TEAMS))
            sabr = self.value_calc.format == ScoringFormat.SABR_POINTS or self.value_calc.format == ScoringFormat.H2H_SABR_POINTS
            non_prod_salary = self.value_calc.get_input(CalculationDataType.NON_PRODUCTIVE_DOLLARS)
            rep_nums = None
            rep_levels = None
            if rep_level_scheme == RepLevelScheme.NUM_ROSTERED:
                rep_nums = calculation_services.get_num_rostered_rep_levels(self.value_calc)
            elif rep_level_scheme == RepLevelScheme.STATIC_REP_LEVEL:
                rep_levels = calculation_services.get_rep_levels(self.value_calc)
            elif rep_level_scheme == RepLevelScheme.FILL_GAMES:
                surplus_pos = calculation_services.get_num_rostered_rep_levels(self.value_calc)
            logging.debug(f'rep_level_scheme = {rep_level_scheme.value}')
        
        self.update_progress(progress, 'Calculating Batters', 10)
        pos_points = value.bat_points.BatPoint(
            intermediate_calc=self.intermediate_calculations, 
            rep_level_scheme=rep_level_scheme,
            rank_basis=hitter_rank_basis,
            num_teams=num_teams
        )
        if self.value_calc is not None:
            if rep_nums is not None:
                pos_points.replacement_positions = rep_nums
            if rep_levels is not None:
                pos_points.replacement_levels = rep_levels
            if surplus_pos is not None:
                pos_points.surplus_pos = surplus_pos
        pos_min_pa = pos_points.calc_par(self.pos_proj, self.value_calc.get_input(CalculationDataType.PA_TO_RANK))

        self.update_progress(progress, 'Calculating pitchers', 40)
        #TODO Might need to add usable RP innings as argument
        pitch_points = value.arm_points.ArmPoint(
            intermediate_calc=self.intermediate_calculations, 
            rep_level_scheme=rep_level_scheme,
            num_teams=num_teams,
            rank_basis=pitcher_rank_basis,
            SABR=sabr
            )
        if self.value_calc is not None:
            if rep_nums is not None:
                pitch_points.replacement_positions = rep_nums
            if rep_levels is not None:
                pitch_points.replacement_levels = rep_levels
            if surplus_pos is not None:
                pitch_points.surplus_pos = surplus_pos
        real_pitchers = pitch_points.calc_par(self.pitch_proj)

        if self.value_calc is None:
            print(f"Replacment level numbers are: {pos_points.replacement_positions} and {pitch_points.replacement_positions}")
            print(f"Replacement levels are: {pos_points.replacement_levels} and {pitch_points.replacement_levels}")
        else:
            #TODO: write replacement level info to ValueCalculation.data
            self.value_calc.set_output(CalculationDataType.REP_LEVEL_C, pos_points.replacement_levels[Position.POS_C.value])
            self.value_calc.set_output(CalculationDataType.REP_LEVEL_1B, pos_points.replacement_levels[Position.POS_1B.value])
            self.value_calc.set_output(CalculationDataType.REP_LEVEL_2B, pos_points.replacement_levels[Position.POS_2B.value])
            self.value_calc.set_output(CalculationDataType.REP_LEVEL_SS, pos_points.replacement_levels[Position.POS_SS.value])
            self.value_calc.set_output(CalculationDataType.REP_LEVEL_3B, pos_points.replacement_levels[Position.POS_3B.value])
            self.value_calc.set_output(CalculationDataType.REP_LEVEL_OF, pos_points.replacement_levels[Position.POS_OF.value])
            self.value_calc.set_output(CalculationDataType.REP_LEVEL_UTIL, pos_points.replacement_levels[Position.POS_UTIL.value])
            self.value_calc.set_output(CalculationDataType.REP_LEVEL_SP, pitch_points.replacement_levels[Position.POS_SP.value])
            self.value_calc.set_output(CalculationDataType.REP_LEVEL_RP, pitch_points.replacement_levels[Position.POS_RP.value])

            self.value_calc.set_output(CalculationDataType.ROSTERED_C, pos_points.replacement_positions[Position.POS_C.value])
            self.value_calc.set_output(CalculationDataType.ROSTERED_1B, pos_points.replacement_positions[Position.POS_1B.value])
            self.value_calc.set_output(CalculationDataType.ROSTERED_2B, pos_points.replacement_positions[Position.POS_2B.value])
            self.value_calc.set_output(CalculationDataType.ROSTERED_SS, pos_points.replacement_positions[Position.POS_SS.value])
            self.value_calc.set_output(CalculationDataType.ROSTERED_3B, pos_points.replacement_positions[Position.POS_3B.value])
            self.value_calc.set_output(CalculationDataType.ROSTERED_OF, pos_points.replacement_positions[Position.POS_OF.value])
            self.value_calc.set_output(CalculationDataType.ROSTERED_UTIL, pos_points.replacement_positions[Position.POS_UTIL.value])
            self.value_calc.set_output(CalculationDataType.ROSTERED_SP, pitch_points.replacement_positions[Position.POS_SP.value])
            self.value_calc.set_output(CalculationDataType.ROSTERED_RP, pitch_points.replacement_positions[Position.POS_RP.value])

        self.update_progress(progress, 'Calculating $/PAR and applying', 30)
        rosterable_pos = pos_min_pa.loc[pos_min_pa['Max PAR'] >= 0]
        rosterable_pitch = real_pitchers.loc[real_pitchers['PAR'] >= 0]

        total_par = rosterable_pos['Max PAR'].sum() + rosterable_pitch['PAR'].sum()
        #I had to put the 1 in the args because otherwise it treats "SP" like two arguments "S" and "P" for some reason
        total_usable_par = rosterable_pos['Max PAR'].sum() + rosterable_pitch.apply(pitch_points.usable_par_calc, args=('SP',1), axis=1).sum() + rosterable_pitch.apply(pitch_points.usable_par_calc, args=('RP',1), axis=1).sum()
        total_players = len(rosterable_pos) + len(rosterable_pitch)

        dollars = 400*num_teams
        dollars -= non_prod_salary
        dollars -= num_teams*40 #remove a dollar per player at or above replacement
        self.dol_per_par = dollars / total_usable_par

        if self.value_calc is None:
            print(f"total games = {rosterable_pos['G'].sum()}")
            print(f"total innings = {rosterable_pitch['IP'].sum()}")
            print(f'Total PAR: {total_par}; Total Usable PAR: {total_usable_par}')
            print(f'Dollar/PAR = {self.dol_per_par}')
        else:
            self.value_calc.set_output(CalculationDataType.TOTAL_GAMES_PLAYED, rosterable_pos['G'].sum())
            self.value_calc.set_output(CalculationDataType.TOTAL_INNINGS_PITCHED, rosterable_pitch['IP'].sum())
            self.value_calc.set_output(CalculationDataType.TOTAL_FOM_ABOVE_REPLACEMENT, total_usable_par)
            self.value_calc.set_output(CalculationDataType.DOLLARS_PER_FOM, self.dol_per_par)

        if self.value_calc is not None:
            self.value_calc.values= [] 

        if rank_pos:
            for pos in self.bat_pos:
                if pos == 'MI':
                    pos_value = pd.DataFrame(pos_min_pa.loc[pos_min_pa['Position(s)'].str.contains("2B|SS", case=False, regex=True)])
                elif pos == 'Util':
                    pos_value = pd.DataFrame(pos_min_pa)
                else:
                    pos_value = pd.DataFrame(pos_min_pa.loc[pos_min_pa['Position(s)'].str.contains(pos)])
                pos_value['Value'] = pos_value[f'{pos}_PAR'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
                pos_value.sort_values(by=['Value','P/G'], inplace=True, ascending=[False,False])
                pos_value['Value'] = pos_value['Value'].apply(lambda x : "${:.0f}".format(x))
                if self.value_calc is None:
                    pos_value = pos_value[['OttoneuID', 'Value', 'Name','Team','Position(s)','Points',f'{pos}_PAR','P/G']]
                    pos_value.to_csv(f"C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Staging\\{pos}_values.csv", encoding='utf-8-sig')
                else:
                    for index, row in pos_value.iterrows():
                        self.value_calc.set_player_value(index, pos, row['Value'])

        pos_min_pa['Value'] = pos_min_pa['Max PAR'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
        pos_min_pa.sort_values('Max PAR', inplace=True)

        if rank_pos:
            for pos in self.pitch_pos:
                pos_value = pd.DataFrame(real_pitchers.loc[real_pitchers['Position(s)'].str.contains(pos)])
                pos_value['Value'] = pos_value[f'PAR {pos}'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
                pos_value.sort_values(by=['Value','P/IP'], inplace=True, ascending=[False,False])
                pos_value['Value'] = pos_value['Value'].apply(lambda x : "${:.0f}".format(x))
                
                if self.value_calc is None:
                    pos_value = pos_value[['OttoneuID', 'Value', 'Name','Team','Position(s)','Points',f'PAR {pos}','P/IP']]
                    pos_value.to_csv(f"C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Staging\\{pos}_values.csv", encoding='utf-8-sig')
                else:
                    for index, row in pos_value.iterrows():
                        self.value_calc.set_player_value(index, pos, row['Value'])

        real_pitchers['Value'] = real_pitchers['PAR'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
        real_pitchers.sort_values('PAR', inplace=True)

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_value_detail.csv")
            pos_min_pa.to_csv(filepath, encoding='utf-8-sig')
            filepath = os.path.join(self.intermed_subdirpath, f"pitch_value_detail.csv")
            real_pitchers.to_csv(filepath, encoding='utf-8-sig')
        
        if self.value_calc is None:
            pos_results = pos_min_pa[['OttoneuID', 'Value', 'Name','Team','Position(s)','Points','Max PAR','P/G']]
            pos_results.rename(columns={'Max PAR':'PAR'}, inplace=True)
        else:
            pos_min_pa.rename(columns={'Max PAR':'PAR'}, inplace=True)
            for index, row in pos_min_pa.iterrows():
                self.value_calc.set_player_value(index, Position.OFFENSE, row['Value'])

        if self.value_calc is None:
            pitch_results = real_pitchers[['OttoneuID', 'Value', 'Name','Team','Position(s)','Points','PAR','P/IP']]
        else:
            pitch_results = real_pitchers
            for index, row in pitch_results.iterrows():
                self.value_calc.set_player_value(index, Position.PITCHER, row['Value'])

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_result.csv")
            pos_results.to_csv(filepath, encoding='utf-8-sig')
            filepath = os.path.join(self.intermed_subdirpath, f"pitch_result.csv")
            pitch_results.to_csv(filepath, encoding='utf-8-sig')

        pos_index = pos_min_pa.index
        pitch_index = pitch_results.index
        intersect = pos_index.intersection(pitch_index)

        if self.value_calc is None:
            results = pos_results
        else:
            results = pos_min_pa
        results['P/IP'] = 0
        pitch_results['P/G'] = 0
        for index in intersect:
            results.loc[index, 'Value'] = results.loc[index]['Value'] + pitch_results.loc[index]['Value']
            results.loc[index, 'Points'] = results.loc[index]['Points'] + pitch_results.loc[index]['Points']
            results.loc[index, 'PAR'] = results.loc[index]['PAR'] + pitch_results.loc[index]['PAR']
            results.loc[index, 'P/IP'] = pitch_results.loc[index]['P/IP']
            pitch_results = pitch_results.drop(index=index)

        results = results.append(pitch_results)
        results['Value'] = results['Value'].apply(lambda x : "${:.0f}".format(x))
        
        #filepath = os.path.join(self.intermed_subdirpath, f"results.csv")
        #results.to_csv(filepath, encoding='utf-8-sig')
        if self.value_calc is None:
            results = results[['OttoneuID', 'Value', 'Name','Team','Position(s)','Points','PAR','P/G','P/IP']]
            results.sort_values('PAR', inplace=True, ascending=False)
            return results
        else:
            for index, row in results.iterrows():
                self.value_calc.set_player_value(index, Position.OVERALL, row['Value'])

    
    def update_progress(self, progress, task, increment):
        if progress is not None:
            progress.set_task_title(f"{task}...")
            progress.increment_completion_percent(increment)
        else:
            print(task)

#--------------------------------------------------------------------------------
#Begin main program

def main():

    proj_set = input("Pick projection system (steamer, zips, fangraphsdc, atc, thebat, thebatx: ")
    #Peform value calc based on Rest of Season projections
    ros = input("RoS? (y/n): ") == 'y'

    if proj_set == 'zips':
        if ros:
            dc_pt = True
        else:
            proj_set = 'zipsdc'
            dc_pt = False
    elif proj_set != 'fangraphsdc':
        dc_pt = (input("Use DC playing time (y/n): ")) == 'y'

    if not ros:
        force = (input("Force update (y/n): ")) == 'y'

    rank_pos = (input("Rank individual positions (y/n): ")) != 'n'

    print_intermediate = (input("Print intermediate datasets (y/n): ")) == 'y'
    value_calc = PointValues(projection=proj_set, depthchart_pt=dc_pt, ros=ros, debug=print_intermediate, rp_limit=84,force_proj_download=force)
    results = value_calc.calculate_values(rank_pos)
    results.to_csv("C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Staging\\values.csv", encoding='utf-8-sig')

if __name__ == '__main__':
    main()
