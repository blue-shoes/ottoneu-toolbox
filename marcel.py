import pandas as pd
def createLeagueAvgPos(dataset, y1, y2, y3):
    avg_dict = pd.DataFrame()
    y1_pa = dataset.loc[2, "PA"]
    y2_pa = dataset.loc[1, "PA"]
    y3_pa = dataset.loc[0, "PA"]

    print(f"PAs - {y1_pa}, {y2_pa}, {y3_pa}")

    #avg_dict["H"] = (dataset[y1, "H"] / * 5 + dataset[y2, "H"] * 4

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

print(f"{pos_league_dataset}")

pos_avg_dict = createLeagueAvgPos(pos_league_dataset, year1, year2, year3)

#pos_y1_dict = pos_year1_dataset.set_index('playerid', drop=False)
#pos_y2_dict = pos_year2_dataset.set_index('playerid', drop=False)
#pos_y3_dict = pos_year3_dataset.set_index('playerid', drop=False)

print("We ran")