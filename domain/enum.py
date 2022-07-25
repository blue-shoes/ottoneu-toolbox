from enum import Enum

class ProjectionType(Enum):
    STEAMER = 0
    ZIPS = 1
    DEPTH_CHARTS = 2
    ATC = 3
    THE_BAT = 4
    THE_BATX = 5
    CUSTOM = 6

    fg_downloadable = [STEAMER, ZIPS, DEPTH_CHARTS, ATC, THE_BAT, THE_BATX]

    @classmethod
    def enum_to_name_dict(self):
        return {
        self.STEAMER : "Steamer",
        self.ZIPS : "ZiPS",
        self.DEPTH_CHARTS : "FG Depth Charts",
        self.ATC : "ATC",
        self.THE_BAT : "THE BAT",
        self.THE_BATX : "THE BATX",
        self.CUSTOM : "Custom"
    }

    @classmethod
    def name_to_enum_dict(self):
        return {
        "Steamer" : self.STEAMER,
        "ZiPS" : self.ZIPS,
        "FG Depth Charts" : self.DEPTH_CHARTS,
        "ATC" : self.ATC,
        "THE BAT" : self.THE_BAT,
        "THE BATX" : self.THE_BATX,
        "Custom" : self.CUSTOM
    }

    @classmethod
    def enum_to_url(self):
        return {
        self.STEAMER : "steamer",
        self.ZIPS : "zips",
        self.DEPTH_CHARTS : "fangraphsdc",
        self.ATC : "atc",
        self.THE_BAT : "thebat",
        self.THE_BATX : "thebatx"
    }

class CalculationDataType(Enum):
    DOLLARS_PER_FOM = 0
    REP_LEVEL_C = 1
    REP_LEVEL_1B = 2
    REP_LEVEL_2B = 3
    REP_LEVEL_3B = 4
    REP_LEVEL_SS = 5
    REP_LEVEL_OF = 6
    REP_LEVEL_UTIL = 7
    REP_LEVEL_SP = 8
    REP_LEVEL_RP = 9

class CalculationInput(Enum):
    FILL_GAMES = 0
    NUM_TEAMS = 1
    HITTER_SPLIT = 2
    ROSTERED_C = 3
    ROSTERED_1B = 4
    ROSTERED_2B = 5
    ROSTERED_3B = 6
    ROSTERED_SS = 7
    ROSTERED_OF = 8
    ROSTERED_UTIL = 9
    ROSTERED_SP = 10
    ROSTERED_RP = 11
    NON_PRODUCTIVE_DOLLARS = 12
    REP_LEVEL_C = 13
    REP_LEVEL_1B = 14
    REP_LEVEL_2B = 15
    REP_LEVEL_3B = 16
    REP_LEVEL_SS = 17
    REP_LEVEL_OF = 18
    REP_LEVEL_UTIL = 19
    REP_LEVEL_SP = 20
    REP_LEVEL_RP = 21
    RANKING_BASIS = 22
    PA_TO_RANK = 23
    SP_IP_TO_RANK = 24
    RP_IP_TO_RANK = 25
    COMBINE_TWO_WAY_PLAYERS = 26
    
class StatType(Enum):
    G_HIT = 0
    GS_HIT = 1
    PA = 2
    AB = 3
    H = 4
    DOUBLE = 5
    TRIPLE = 6
    HR = 7
    R = 8
    RBI = 9
    BB = 10
    SO = 11
    HBP = 12
    SB = 13
    CS = 14
    AVG = 15
    OBP = 16
    SLG = 17
    OPS = 18
    WOBA = 19
    WRC_PLUS = 20
    G_PIT = 21
    GS_PIT = 22
    IP = 23
    W = 24
    L = 25
    QS = 26
    SV = 27
    HLD = 28
    H_ALLOWED = 29
    ER = 30
    HR_ALLOWED = 31
    K = 32
    BB_ALLOWED = 33
    HBP_ALLOWED = 34
    WHIP = 35
    K_PER_9 = 36
    BB_PER_9 = 37
    ERA = 38
    FIP = 39

    @classmethod
    def hit_to_enum_dict(self):
        return {
        'G' : self.G_HIT,
        'GS' : self.GS_HIT,
        'PA': self.PA,
        'AB' : self.AB,
        'H' : self.H,
        '2B' : self.DOUBLE,
        '3B' : self.TRIPLE, 
        'HR' : self.HR,
        'R' : self.R,
        'RBI' : self.RBI,
        'BB' : self.BB,
        'SO'  : self.SO,
        'HBP' : self.HBP,
        'SB' : self.SB,
        'CS' : self.CS,
        'AVG' : self.AVG,
        'OBP' : self.OBP,
        'SLG' : self.SLG,
        'OPS' : self.OPS,
        'wOBA' : self.WOBA
    }

    @classmethod
    def pitch_to_enum_dict(self):
        return {
        'G': self.G_PIT,
        'GS': self.GS_PIT,
        'IP' : self.IP,
        'W' : self.W,
        'L' : self.L,
        'QS' : self.QS,
        'SV' : self.SV,
        'HLD' : self.HLD,
        'H' : self.H_ALLOWED,
        'ER' : self.ER,
        'HR' : self.HR_ALLOWED,
        'K' : self.K,
        'BB' : self.BB_ALLOWED,
        'HBP' : self.HBP_ALLOWED,
        'WHIP' : self.WHIP,
        'K/9' : self.K_PER_9,
        'BB/9' : self.BB_PER_9,
        'ERA' : self.ERA,
        'FIP' : self.FIP
    }

    @classmethod
    def enum_to_display_dict(self):
        return {
        self.G_HIT: 'G',
        self.GS_HIT : 'GS',
        self.PA : 'PA',
        self.AB : 'AB',
        self.H : 'H',
        self.DOUBLE : '2B',
        self.TRIPLE : '3B', 
        self.HR : 'HR',
        self.R : 'R',
        self.RBI : 'RBI',
        self.BB : 'BB',
        self.SO : 'SO',
        self.HBP : 'HBP',
        self.SB : 'SB',
        self.CS : 'CS',
        self.AVG : 'AVG',
        self.OBP : 'OBP',
        self.SLG : 'SLG',
        self.OPS : 'OPS',
        self.WOBA : 'wOBA',
        self.G_PIT : 'G',
        self.GS_PIT : 'GS',
        self.IP : 'IP',
        self.W : 'W',
        self.L : 'L',
        self.QS : 'QS',
        self.SV : 'SV',
        self.HLD : 'HLD',
        self.H_ALLOWED : 'H',
        self.ER : 'ER',
        self.HR_ALLOWED : 'HR',
        self.K : 'K',
        self.BB_ALLOWED : 'BB',
        self.HBP_ALLOWED : 'HBP',
        self.WHIP : 'WHIP',
        self.K_PER_9 : 'K/9',
        self.BB_PER_9 : 'BB/9',
        self.ERA : 'ERA',
        self.FIP : 'FIP'
    }

class ScoringFormat(Enum):
    ALL = 0
    CLASSIC_4X4 = 1
    OLD_SCHOOL_5X5 = 2
    FG_POINTS = 3
    SABR_POINTS = 4
    H2H_FG_POINTS = 5
    H2H_SABR_POINTS = 6

    @classmethod
    def name_to_enum_map(self):
        return {'All' : self.ALL,
                        'Ottoneu Classic (4x4)': self.CLASSIC_4X4, 
                        'Old School (5x5)': self.OLD_SCHOOL_5X5,
                        'FanGraphs Points': self.FG_POINTS,
                        'SABR Points': self.SABR_POINTS,
                        'H2H FanGraphs Points': self.H2H_FG_POINTS,
                        'H2H SABR Points': self.H2H_FG_POINTS}
    
    @classmethod
    def enum_to_full_name_map(self):
        return {self.ALL : "All",
                            self.CLASSIC_4X4: 'Ottoneu Classic (4x4)',
                            self.OLD_SCHOOL_5X5: 'Old School (5x5)',
                            self.FG_POINTS: 'FanGraphs Points',
                            self.SABR_POINTS: 'SABR Points',
                            self.H2H_FG_POINTS: 'H2H FanGraphs Points',
                            self.H2H_SABR_POINTS: 'H2H SABR Points'}

    @classmethod
    def enum_to_short_name_map(self): 
        return {self.ALL : "All",
                            self.CLASSIC_4X4: '4x4',
                            self.OLD_SCHOOL_5X5: '5x5',
                            self.FG_POINTS: 'FGP',
                            self.SABR_POINTS: 'SABR',
                            self.H2H_FG_POINTS: 'H2H FGP',
                            self.H2H_SABR_POINTS: 'H2H SABR'}
