from unittest import result
import pandas as pd
from random import randint
from time import sleep
import datetime
import threading

demo_trans= '.\\demo\\data\\output\\draft_list.csv'

def demo_draft(league, run_event: threading.Event, player_source='.\\demo\\data\\input\\draft_list.csv'):
    results = pd.read_csv(player_source)
    results.set_index('PlayerID', inplace=True)
    rosters = get_rostered_ottoneu_ids(league)
    results = results[~results.index.isin(rosters)]
    #debug
    #results.to_csv('C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Demo\\valid_draft.csv',  encoding='utf-8-sig')
    index = 0

    df = pd.DataFrame()

    while index < 5:
        df = df.append(load_player_from_source(results, index, old=True), ignore_index=True)
        index += 1

    df.to_csv(demo_trans, encoding='utf-8-sig')

    index = 0
    print('---BEGINNING DRAFT---')
    while index < len(results) and run_event.is_set:
        sleep(randint(5,10))
        print('!!!Getting player!!!')
        df = df.append(load_player_from_source(results, index), ignore_index=True)
        recent = pd.DataFrame()
        recent = recent.append(copy_to_recent_trans(df,-1), ignore_index=True)
        recent = recent.append(copy_to_recent_trans(df,-2), ignore_index=True)
        recent = recent.append(copy_to_recent_trans(df,-3), ignore_index=True)
        recent = recent.append(copy_to_recent_trans(df,-4), ignore_index=True)
        recent = recent.append(copy_to_recent_trans(df,-5), ignore_index=True)

        recent.set_index('Ottoneu ID', inplace=True)
        recent.to_csv(demo_trans, encoding='utf-8-sig')
        index += 1
    print('---DRAFT COMPLETE---')
        
def load_player_from_source(results, index, old=False):
    row = {}
    if old:
        row['Ottoneu ID'] = index
        row['Date']= (datetime.datetime.now() - datetime.timedelta(minutes=10))
    else:
        print(results.iloc[index])
        row['Ottoneu ID'] = results.index[index]
        row['Date']= datetime.datetime.now()
    row['Team ID'] = (results['TeamID'].iloc[index])
    
    row['Salary'] = (results['Price'].iloc[index])
    if row['Salary'] == '$0':
        row['Type'] = 'Cut'
    else:
        row['Type'] = 'Add'
    print(row)
    return row

def copy_to_recent_trans(loaded, index):
    row = {}
    row['Ottoneu ID'] = loaded['Ottoneu ID'].iloc[index]
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

if __name__ == '__main__':
    demo_draft()

