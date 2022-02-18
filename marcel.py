import pandas as pd
import scrape_fg as scrape

age_dictionary = {20: 1.054, 21: 1.048, 22: 1.042, 23: 1.036, 24: 1.03, 25: 1.024,
                26: 1.018, 27: 1.012, 28: 1.006, 29: 1.000, 30: 0.997,
                31: 0.994, 32: 0.991, 33: 0.988, 34: 0.985, 35: 0.982,
                36: 0.979, 37: 0.976, 38: 0.973, 39: 0.970, 40: 0.967, 
                41: 0.964, 42: 0.961, 43: 0.958, 44: 0.955}

def createLeagueAvgPos(dataset):
    avg_dict = {}

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
    avg_dict = {}

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

def createPositionPlayerProj(pos_year1, pos_year2, pos_year3, pos_age, pos_avg_dict, depth_chart):
    proj_dict = pd.DataFrame()

    print(depth_chart.index.dtype)
    print(pos_year1.index.dtype)

    count = 0
    for (playerid, y1_stats) in pos_year1.iterrows():
        print(playerid)
        if(playerid in depth_chart.index):
            print('found playerid')
            player_dict = {}
            pa_proj = depth_chart.loc[playerid]["PA"]
            name = y1_stats["Name"]
            print("name = " + name)
            player_dict["PA"] = pa_proj
            player_dict["Name"] = name
            player_dict["playerid"] = playerid
            
            
            y1_pa = y1_stats["PA"]
            denom = 5
            y2_pres = False
            y3_pres = False
            if playerid in pos_year2.index:
                y2_stats = pos_year2.loc[playerid]
                y2_pa = y2_stats["PA"]
                y2_pres = True
                denom = denom + 4
            else:
                y2_pa = 0
            if playerid in pos_year3.index:
                y3_stats = pos_year3.loc[playerid]
                y3_pa = y3_stats["PA"]
                y3_pres = True
                denom = denom + 3
            else :
                y3_pa = 0
            age = pos_age.loc[playerid, "Age"]
            age = age + 1
            multiplier = age_dictionary[age]

            weighted_pa = 5*y1_pa + 4*y2_pa + 3*y3_pa
            rscore = weighted_pa/(weighted_pa + 1200)

            for category, value in y1_stats.items():
                if category in ["playerid", "Name", "Team", "G", "PA"]:
                    continue
                y1 = value
                if y2_pres:
                    y2 = y2_stats[category]
                else :
                    y2 = 0
                if y3_pres:
                    y3 = y3_stats[category]
                else:
                    y3 = 0
                avg = pos_avg_dict[category]

                if category == "AVG":
                    player_rate = (5*y1 + 4*y2 + 3*y3)/denom
                else:
                    player_rate = (5*y1 + 4*y2 + 3*y3)/weighted_pa
                stat_rate = ((rscore*player_rate) + ((1.0-rscore)*avg))*multiplier

                proj = pa_proj * stat_rate

                player_dict[category] = proj
            proj_dict = proj_dict.append(player_dict, ignore_index=True)    
        #if count > 10:
         #   break
        #count = count + 1
    print(proj_dict.head(10))
    proj_dict = proj_dict.set_index("playerid")
    proj_dict.index = proj_dict.index.astype(str, copy = False)

    return proj_dict



year1 = int(input("Enter last year: "))
year2 = year1 - 1
year3 = year2 - 1

force = (input("Force update (y/n): ")) == 'y'

try:
    driver = scrape.setupDriver()

    # Get position player data
    pos_year1_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=0&season={year1}&month=0&season1={year1}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pos_{year1}.csv")
    pos_year2_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=0&season={year2}&month=0&season1={year2}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pos_{year2}.csv")
    pos_year3_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=0&season={year3}&month=0&season1={year3}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pos_{year3}.csv")
    pos_age_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=bat&lg=all&qual=0&type=c,3&season={year1}&month=0&season1={year1}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pos_{year1}_age.csv")
    pos_league_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=np&stats=bat&lg=all&qual=0&type=0&season={year1}&month=0&season1={year3}&ind=0&team=0,ss&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pos_league_avg_{year3}-{year1}.csv", player=False)
    pos_league_depthchart = scrape.getProjectionDataset(driver, "https://www.fangraphs.com/projections.aspx?pos=all&stats=bat&type=fangraphsdc", f"pos_player_depth_chart.csv", force)

    print("Got pos")
    pitch_year1_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=0&type=0&season={year1}&month=0&season1={year1}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pitch_{year1}.csv")
    pitch_year2_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=0&type=0&season={year2}&month=0&season1={year2}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pitch_{year2}.csv")
    pitch_year3_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=0&type=0&season={year3}&month=0&season1={year3}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pitch_{year3}.csv")
    pitch_age_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=0&type=c,3&season={year1}&month=0&season1={year1}&ind=0&team=0&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pitch_{year1}_age.csv") 
    pitch_league_dataset = scrape.getLeaderboardDataset(driver, f"https://www.fangraphs.com/leaders.aspx?pos=all&stats=pit&lg=all&qual=0&type=0&season={year1}&month=0&season1={year3}&ind=0&team=0,ss&rost=0&age=0&filter=&players=0&startdate=&enddate=", f"pitch_league_avg_{year3}-{year1}.csv", player=False)
    pitch_league_depthchart = scrape.getProjectionDataset(driver, "https://www.fangraphs.com/projections.aspx?pos=all&stats=pit&type=fangraphsdc", f"pitcher_depth_chart.csv", force)
    print("got pitch")
finally:
    driver.close()

pos_avg_dict = createLeagueAvgPos(pos_league_dataset)

position_player_marcels = createPositionPlayerProj(pos_year1_dataset, pos_year2_dataset, pos_year3_dataset, pos_age_dataset, pos_avg_dict, pos_league_depthchart)

pitch_avg_dict = createLeagueAvgPitch(pitch_league_dataset)

print("We ran")