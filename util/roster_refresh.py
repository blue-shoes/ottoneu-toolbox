from time import sleep
import scrape.scrape_ottoneu
import pandas as pd
from datetime import datetime
import threading

def refresh_thread(self, lg_id, rosters, rosters_file, ottoneu_pos, run_event):
    last_time = datetime.now()
    while(run_event.is_set()):
        sleep(60)
        last_trans = scrape.scrape_ottoneu.Scrape_Ottoneu().scrape_recent_trans_api(lg_id)
        most_recent = last_trans[0]['Date']
        if most_recent > last_time:
            index = 0
            while last_trans[index]['Date'] > last_time:
                if last_trans[index]['Type'] == 'Add':
                    row = []
                    row.append(last_trans[index]['Team ID'])
                    #team name unimportant
                    row.append('')
                    otto_id = last_trans[index]['Ottoneu ID']
                    row.append(otto_id)
                    row.append(ottoneu_pos[otto_id]['FG MajorLeagueID'])
                    row.append(ottoneu_pos[otto_id]['FG MinorLeagueID'])
                    #name, team, position, unimportant
                    row.append('')
                    row.append('')
                    row.append('')
                    row.append(last_trans[index]['Salary'])
                    rosters.append(row)
                elif last_trans[index] == 'Cut':
                    rosters.drop(last_trans[index]['Ottoneu ID'])
            rosters.to_csv(rosters_file, encoding='utf-8-sig')
            last_time = most_recent

def roster_refresh_setup(lg_id):
    scraper = scrape.scrape_ottoneu.Scrape_Ottoneu()
    rosters = scraper.scrape_roster_export(lg_id)
    rosters_file = "C:\\Users\\adam.scharf\\Documents\\Personal\\FFB\\Staging\\rosters.csv"
    #Potential to get specific league type here
    ottoneu_pos = scraper.get_avg_salary_ds(True)
    rosters.to_csv(rosters_file, encoding='utf-8-sig')
    run_event = threading.Event()
    run_event.set()
    t1 = threading.Thread(target = refresh_thread, args = (lg_id,rosters,rosters_file,ottoneu_pos, run_event))
    t1.start()
    try:
        while 1:
            sleep(5)
    except KeyboardInterrupt:
        run_event.clear()
        t1.join()

def main():
    lg_id = input("Enter league id: ")
    roster_refresh_setup(lg_id)

if __name__ == '__main__':
    main()