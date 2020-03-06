import pandas as pd
def createLeagueAvgPos(dataset):
    avg_dict = pd.DataFrame()

    #y1 is last year, which is the last row in the table
    y1_pa = dataset.loc[2, "PA"]
    y2_pa = dataset.loc[1, "PA"]
    y3_pa = dataset.loc[0, "PA"]

    for (cat_name, cat_data)  in dataset.iteritems():
        if cat_name in ["PA", "Season", "G"]:
            continue
        y1_stat = cat_data[2]
        y2_stat = cat_data[1]
        y3_stat = cat_data[0]

        if(cat_name == "AVG"):
            avg = (3*y3_stat + 4*y2_stat + 5*y1_stat)/12
        else:
            avg = (3*y3_stat/y3_pa + 4*y2_stat/y2_pa + 5*y1_stat/y1_pa)/12

        avg_dict[cat_name] = avg

    return avg_dict

def createLeagueAvgPitch(dataset):
    avg_dict = pd.DataFrame()

    y1_ip = dataset.loc[2, "IP"]
    y2_ip = dataset.loc[1, "IP"]
    y3_ip = dataset.loc[0, "IP"]

    for (cat_name, cat_data)  in dataset.iteritems():
        if cat_name in ["IP", "Season", "G"]:
            continue
        y1_stat = cat_data[2]
        y2_stat = cat_data[1]
        y3_stat = cat_data[0]

        if cat_name == "ERA":
            avg = (5*y3_stat + 4*y2_stat + 3*y1_stat)/12
        else:
            avg = (5*y3_stat/y3_ip + 4*y2_stat/y2_ip + 3*y1_stat/y1_ip)/12

        avg_dict[cat_name] = avg

    return avg_dict

import scrape_fg as scrape

year1 = int(input("Enter last year: "))
year2 = year1 - 1
year3 = year2 - 1

try:
    driver = scrape.setupDriver()

    # Get position player data
    pos_year1_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=0&season={year1}&month=0&season1={year1}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pos_{year1}.csv")
    pos_year2_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=0&season={year2}&month=0&season1={year2}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pos_{year2}.csv")
    pos_year3_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=0&season={year3}&month=0&season1={year3}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pos_{year3}.csv")
    pos_age_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=c,3&season={year1}&month=0&season1={year1}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pos_{year1}_age.csv")
    pos_league_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=np&stats=bat&lg=all&qual=0&type=0&season={year1}&month=0&season1={year3}&ind=0&team=0,ss&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pos_league_avg_{year3}-{year1}.csv")

    pitch_year1_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=0&type=0&season={year1}&month=0&season1={year1}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pitch_{year1}.csv")
    pitch_year2_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=0&type=0&season={year2}&month=0&season1={year2}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pitch_{year2}.csv")
    pitch_year3_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=0&type=0&season={year3}&month=0&season1={year3}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pitch_{year3}.csv")
    pitch_age_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=0&type=c,3&season={year1}&month=0&season1={year1}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pitch_{year1}_age.csv") 
    pitch_league_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=0&type=0&season={year1}&month=0&season1={year3}&ind=0&team=0,ss&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pitch_league_avg_{year3}-{year1}.csv")
finally:
    driver.close()

pos_avg_dict = createLeagueAvgPos(pos_league_dataset)
pitch_avg_dict = createLeagueAvgPitch(pitch_league_dataset)

print("We ran")