import pandas as pd
from random import randint
from time import sleep
import datetime
import threading
import os

from domain.enum import Platform
from domain.exception import InputException

demo_trans= '.\\demo\\data\\output\\draft_list.csv'
yahoo_demo_trans = '.\\demo\\data\\output\\yahoo_draft_list.csv'

def demo_draft(league, run_event: threading.Event, player_source='.\\demo\\data\\input\\draft_list.csv'):
    if league.platform == Platform.OTTONEU:
        results = pd.read_csv(player_source)
        results.set_index('PlayerID', inplace=True)
        rosters = get_rostered_ottoneu_ids(league)
        results = results[~results.index.isin(rosters)]
        #debug
        #results.to_csv('C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Demo\\valid_draft.csv',  encoding='utf-8-sig')
        index = 0

        df = pd.DataFrame()

        rows = []
        while index < 5:
            rows.append(load_player_from_source(results, index, old=True))
            index += 1
        
        df = pd.DataFrame(rows)
        df.set_index('Ottoneu ID', inplace=True)
        df.to_csv(demo_trans, encoding='utf-8-sig')

        index = 0
        print('---BEGINNING DRAFT---')
        while index < len(results) and not run_event.is_set():
            run_event.wait(randint(5,10))
            print('!!!Getting player!!!')
            df.loc[results.index[index]] = load_player_from_source(results, index)
            #df = df.append(load_player_from_source(results, index), ignore_index=True)
            rows = []
            rows.append(copy_to_recent_trans(df,-1))
            rows.append(copy_to_recent_trans(df,-2))
            rows.append(copy_to_recent_trans(df,-3))
            rows.append(copy_to_recent_trans(df,-4))
            rows.append(copy_to_recent_trans(df,-5))

            recent = pd.DataFrame(rows)

            recent.set_index('Ottoneu ID', inplace=True)
            recent.to_csv(demo_trans, encoding='utf-8-sig')
            index += 1
        print('---DRAFT COMPLETE---')
        if os.path.exists(demo_trans):
                os.remove(demo_trans)
    elif league.platform == Platform.YAHOO:
        results = pd.read_csv('.\\demo\\data\\input\\yahoo_draft_results.csv')
        #Generate random keepers
        print('---Selecting Keepers---')
        keepers = results.sample(n=75)
        for _, keeper in keepers.iterrows():
            print(f'\tPick: {keeper["pick"]}, key: {keeper["player_key"]}')
        index = 0
        print('---BEGINNING DRAFT---')
        while index < len(results) and not run_event.is_set():
            run_event.wait(randint(2,8))
            picked = results.iloc[:index]
            print(results.iloc[index])
            pick_df = pd.concat([picked, keepers]).drop_duplicates().reset_index(drop=True)
            pick_df.to_csv(yahoo_demo_trans, encoding='utf-8-sig')
            index += 1
        print('---DRAFT COMPLETE---')
        if os.path.exists(yahoo_demo_trans):
            os.remove(yahoo_demo_trans)

    else:
        raise InputException('Did not recognize the league platform for a demo')
        
def load_player_from_source(results, index, old=False):
    row = {}
    if old:
        row['Ottoneu ID'] = results.index[index]
        row['Date']= (datetime.datetime.now() - datetime.timedelta(minutes=10))
    else:
        row['Ottoneu ID'] = results.index[index]
        row['Date']= datetime.datetime.now()
    row['Team ID'] = (results['TeamID'].iloc[index])
    
    row['Salary'] = (results['Price'].iloc[index])
    if row['Salary'] == '$0':
        row['Type'] = 'CUT'
    else:
        row['Type'] = 'ADD'
    print(f'{results["Player Name"].iloc[index]}, {row["Salary"]}')
    return row

def copy_to_recent_trans(loaded, index):
    row = {}
    row['Ottoneu ID'] = loaded.index[index]
    row['Team ID'] = (loaded['Team ID'].iloc[index])
    row['Date']= loaded['Date'].iloc[index]
    row['Salary'] = loaded['Salary'].iloc[index]
    row['Type'] = loaded['Type'].iloc[index]
    return row

def get_rostered_ottoneu_ids(league):
    rostered = []
    for team in league.teams:
        for rs in team.roster_spots:
            rostered.append(rs.player.ottoneu_id)
    return rostered