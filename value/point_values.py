from cmath import pi
import pandas as pd
import numpy as np
from scrape import scrape_fg
import os
from os import path
import value.bat_points
import value.arm_points

from scrape import scrape_ottoneu

pd.options.mode.chained_assignment = None # from https://stackoverflow.com/a/20627316

bat_pos = ['C','1B','2B','3B','SS','MI','OF','Util']
pitch_pos = ['SP','RP']
target_innings = 1500.0*12.0
#replacement_positions = {"C":24,"1B":40,"2B":38,"3B":40,"SS":42,"OF":95,"Util":200,"SP":85,"RP":70}
#These are essentially minimums for the positions. I would really not expect to go below these. C and Util are unaffected by the algorithm
replacement_positions = {"C":24,"1B":12,"2B":18,"3B":12,"SS":18,"OF":60,"Util":200,"SP":60,"RP":60}
replacement_levels = {}

class PointValues():

    def __init__(self, projection='steamer', depthchart_pt=False, ros=False, debug=False, rostered_hitters=244, rostered_pitchers=196,
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

    def calculate_values(self, rank_pos):
        if self.ros:
            self.force = True
            if self.projection == 'steamer':
                #steamer has a different convention for reasons
                self.projection = 'steamerr'
            else:
                self.projection = 'r' + self.projection
        try:
            fg_scraper = scrape_fg.Scrape_Fg()
            pos_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type={self.projection}&team=0&lg=all&players=0", f'{self.projection}_pos.csv', self.force)
            #THE BAT X does not have pitcher projections, so revert them to simply THE BAT
            if self.projection == 'thebatx':
                pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type=thebat&team=0&lg=all&players=0", f'thebat_pitch.csv', self.force)     
            elif self.projection == 'thebatxr':
                fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type=thebatr&team=0&lg=all&players=0", f'thebatr_pitch.csv', self.force)
            else:
                pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type={self.projection}&team=0&lg=all&players=0", f'{self.projection}_pitch.csv', self.force)

            if self.depthchart_pt:
                if self.ros:
                    dc_set = 'rfangraphsdc'
                else:
                    dc_set = 'fangraphsdc'
                dc_pos_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type={dc_set}&team=0&lg=all&players=0", f'{dc_set}_pos.csv', self.force)
                dc_pitch_proj = fg_scraper.getProjectionDataset(f"https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type={dc_set}&team=0&lg=all&players=0", f'{dc_set}_pitch.csv', self.force)

        finally:
            fg_scraper.close()

        if self.depthchart_pt:
            pos_proj = self.convertToDcPlayingTime(pos_proj, dc_pos_proj, True)
            pitch_proj = self.convertToDcPlayingTime(pitch_proj, dc_pitch_proj, False)

            if self.intermediate_calculations:
                filepath = os.path.join(self.intermed_subdirpath, f"{self.projection}_dc_conv_pos.csv")
                pos_proj.to_csv(filepath, encoding='utf-8-sig')
                filepath = os.path.join(self.intermed_subdirpath, f"{self.projection}_dc_conv_pitch.csv")
                pitch_proj.to_csv(filepath, encoding='utf-8-sig')

        try:
            otto_scraper = scrape_ottoneu.Scrape_Ottoneu()
            positions = otto_scraper.get_player_position_ds(self.force)
        finally:
            otto_scraper.close()

        #Set position data from Ottoneu
        pos_proj = self.set_positions(pos_proj, positions)
        pitch_proj = self.set_positions(pitch_proj, positions)

        print('Calculating batters')
        pos_points = value.bat_points.BatPoint(intermediate_calc=self.intermediate_calculations, calc_using_games=True)
        pos_150pa = pos_points.calc_par(pos_proj)

        print('Calculating pitchers')
        pitch_points = value.arm_points.ArmPoint(intermediate_calc=self.intermediate_calculations, force_innings=True)
        real_pitchers = pitch_points.calc_par(pitch_proj)

        print(f"Replacment level numbers are: {pos_points.replacement_positions} and {pitch_points.replacement_positions}")
        print(f"Replacement levels are: {pos_points.replacement_levels} and {pitch_points.replacement_levels}")

        rosterable_pos = pos_150pa.loc[pos_150pa['Max PAR'] >= 0]
        print(f"total games = {rosterable_pos['G'].sum()}")
        rosterable_pitch = real_pitchers.loc[real_pitchers['PAR'] >= 0]
        print(f"total innings = {rosterable_pitch['IP'].sum()}")

        total_par = rosterable_pos['Max PAR'].sum() + rosterable_pitch['PAR'].sum()
        #I had to put the 1 in the args because otherwise it treats "SP" like two arguments "S" and "P" for some reason
        total_usable_par = rosterable_pos['Max PAR'].sum() + rosterable_pitch.apply(pitch_points.usable_par_calc, args=('SP',1), axis=1).sum() + rosterable_pitch.apply(pitch_points.usable_par_calc, args=('RP',1), axis=1).sum()
        print(f'Total PAR: {total_par}; Total Usable PAR: {total_usable_par}')
        total_players = len(rosterable_pos) + len(rosterable_pitch)

        dollars = 400*12
        #TODO: Make prospect number an input
        dollars -= 48 #estimate $4 for prospects per team on top of $1
        dollars -= 12*40 #remove a dollar per player at or above replacement
        self.dol_per_par = dollars / total_usable_par
        print(f'Dollar/PAR = {self.dol_per_par}')

        if rank_pos:
            for pos in bat_pos:
                if pos == 'MI':
                    pos_value = pd.DataFrame(pos_150pa.loc[pos_150pa['Position(s)'].str.contains("2B|SS", case=False, regex=True)])
                elif pos == 'Util':
                    pos_value = pd.DataFrame(pos_150pa)
                else:
                    pos_value = pd.DataFrame(pos_150pa.loc[pos_150pa['Position(s)'].str.contains(pos)])
                pos_value['Value'] = pos_value[f'{pos}_PAR'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
                pos_value.sort_values(by=['Value','P/G'], inplace=True, ascending=[False,False])
                pos_value['Value'] = pos_value['Value'].apply(lambda x : "${:.0f}".format(x))
                pos_value = pos_value[['OttoneuID', 'Value', 'Name','Team','Position(s)','Points',f'{pos}_PAR','P/G']]
                pos_value.to_csv(f"C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Staging\\{pos}_values.csv", encoding='utf-8-sig')

        pos_150pa['Value'] = pos_150pa['Max PAR'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
        pos_150pa.sort_values('Max PAR', inplace=True)

        if rank_pos:
            for pos in pitch_pos:
                pos_value = pd.DataFrame(real_pitchers.loc[real_pitchers['Position(s)'].str.contains(pos)])
                pos_value['Value'] = pos_value[f'PAR {pos}'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
                pos_value.sort_values(by=['Value','P/IP'], inplace=True, ascending=[False,False])
                pos_value['Value'] = pos_value['Value'].apply(lambda x : "${:.0f}".format(x))
                pos_value = pos_value[['OttoneuID', 'Value', 'Name','Team','Position(s)','Points',f'PAR {pos}','P/IP']]
                pos_value.to_csv(f"C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Staging\\{pos}_values.csv", encoding='utf-8-sig')

        real_pitchers['Value'] = real_pitchers['PAR'].apply(lambda x: x*self.dol_per_par + 1.0 if x >= 0 else 0)
        real_pitchers.sort_values('PAR', inplace=True)

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_value_detail.csv")
            pos_150pa.to_csv(filepath, encoding='utf-8-sig')
            filepath = os.path.join(self.intermed_subdirpath, f"pitch_value_detail.csv")
            real_pitchers.to_csv(filepath, encoding='utf-8-sig')
        
        pos_results = pos_150pa[['OttoneuID', 'Value', 'Name','Team','Position(s)','Points','Max PAR','P/G']]
        pos_results.rename(columns={'Max PAR':'PAR'}, inplace=True)
        pitch_results = real_pitchers[['OttoneuID', 'Value', 'Name','Team','Position(s)','Points','PAR','P/IP']]

        if self.intermediate_calculations:
            filepath = os.path.join(self.intermed_subdirpath, f"pos_result.csv")
            pos_results.to_csv(filepath, encoding='utf-8-sig')
            filepath = os.path.join(self.intermed_subdirpath, f"pitch_result.csv")
            pitch_results.to_csv(filepath, encoding='utf-8-sig')

        pos_index = pos_results.index
        pitch_index = pitch_results.index
        intersect = pos_index.intersection(pitch_index)

        results = pos_results
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
        results = results[['OttoneuID', 'Value', 'Name','Team','Position(s)','Points','PAR','P/G','P/IP']]
        results.sort_values('PAR', inplace=True, ascending=False)
        #filepath = os.path.join(self.intermed_subdirpath, f"results.csv")
        #results.to_csv(filepath, encoding='utf-8-sig')
        return results

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
