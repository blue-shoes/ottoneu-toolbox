# Ottoneu Toolbox

## Project Description
The Ottoneu Toolbox project is a package of python-based UI tools for playing Ottoneu Fantasy Baseball. As a player of Ottoneu Fantasy Baseball for many years, I've found 
myself often creating side tools to accomplish various tasks to give me an edge in the game, almost always using Excel spreadsheets. Once these became too bulky
to be useful, I began creating robust tools in Python with a GUI to facilitate these tasks. I am now sharing these tools with the public at large.

## Installation Instructions
Users may clone the repo with 
```git clone https://github.com/blue-shoes/ottoneu-toolbox```

Alternatively, periodic tool releases will contain executable files that can be downloaded and run by the user. Note that currently these executables are unsigned and 
will likely trigger a Windows Defender warning stating so the first time they are executed.

## Execution Instructions
Periodic releases will be directly runnable from an executable file.

Running the full GUI from the command lines requires use of the -m flag as such (from the base directory for the repository):

```python.exe -m ottoneu_tool_box```

## Build Instructions
A single executable file may be compiled for the program using the PyInstaller module. A .spec file has already been generated, so the executable may be created with simply the following:

```python -m PyInstaller .\ottoneu_tool_box.spec```

## Current Tools

### Create Player Values
The Toolbox provides a user-friendly interface to create player values based on publically available projections. A sample interface is shown below:
![image](https://user-images.githubusercontent.com/61890211/210104765-a7d5998c-3309-428c-9bbd-022517cff0ff.png)

The Toolbox allows for headless download of the projections available on fangraphs.com on demand and stores them locally for use and later retrieval. Projections may 
also be uploaded from a csv file provided they contain the required stat columns for the game type. Uploaded projections must include an id column the corresponds to either
the player's Ottoneu id or FanGraphs id.

Player values are calculated based on a selected projection and various user inputs to help determine the size of the player pool, including number of teams in the league, playing time thresholds for ranking, and method
for assigning replacement level. These values are then calculated and stored for later use in other Toolbox modules. They can also be exported for use in other tools, including the Surplus
Calculator developed by Justin Vibber (https://www.patreon.com/vibbot). Player values may also be uploaded from a csv file provided they contain at minimum a player
id column (either Ottoneu or FanGraphs) and a value column. Additional columns containing points, points per game or inning, and games played or innings pitched may
be included if the value set was created from a projection that is not in the Toolbox. When uploading overall values, the Toolbox will perform addtional calculations
to determine position-specific values for offensive positions based on either the included data columns or a selected projeciton set in the Toolbox.

The format of the file produced by https://ottovalues.shinyapps.io/FGPts and https://ottovalues.shinyapps.io/SABR_Points/ is designed to conform to the requirements 
of the value upload. 

### Draft Tool
The Draft Tool allows users to monitor available players in near-real-time in an Ottoneu draft. The ability to search for players within the Ottoneu universe is 
given at the top, including partial matching and handling of diacritics. Tables of the top available overall players and by Ottoneu position are provided below. 
The tables are updated in-draft at a rate of once a minute when the user begins draft monitoring using the available start button, removing players and update the 
league inflation rate.

![image](https://user-images.githubusercontent.com/61890211/160003776-1a0b6d03-1fd7-40c4-a19c-3ebf1eca3c2e.png)

## Work in Progress
Potential feature expansions for the Ottoneu Toolbox include:
- Addition of 4x4 and 5x5 formats for value calculations
- Ability to view stats/projections for individual players on-demand
- Expansion to in-season league analysis of rosters, trades, free agents, etc.
- Addition of Davenport Projections

## Framework details
The Toolbox is backed by a SQLite database using SQLAlchemy ORM mappings. Graphics provided via Tkinter. Web scraping with BeautifulSoup and Selenium.

<a href='https://ko-fi.com/V7V6FA3HI' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi2.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>
