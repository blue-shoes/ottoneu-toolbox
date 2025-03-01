from __future__ import annotations
from enum import Enum
from typing import List

class ProjectionType(Enum):
    STEAMER = 0
    ZIPS = 1
    DEPTH_CHARTS = 2
    ATC = 3
    THE_BAT = 4
    THE_BATX = 5
    CUSTOM = 6
    VALUE_DERIVED = 7
    OOPSY = 9

    fg_downloadable = [STEAMER, ZIPS, DEPTH_CHARTS, ATC, THE_BAT, THE_BATX, OOPSY]

    @classmethod
    def enum_to_name_dict(self):
        return {
        self.STEAMER : "Steamer",
        self.ZIPS : "ZiPS",
        self.DEPTH_CHARTS : "FG Depth Charts",
        self.ATC : "ATC",
        self.THE_BAT : "THE BAT",
        self.THE_BATX : "THE BATX",
        self.CUSTOM : "Custom",
        self.VALUE_DERIVED: "Derived",
        self.OOPSY: "OOPSY"
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
        "Custom" : self.CUSTOM,
        "Derived" : self.VALUE_DERIVED,
        "OOPSY" : self.OOPSY
    }

    @classmethod
    def enum_to_url(self):
        return {
        self.STEAMER : "steamer",
        self.ZIPS : "zips",
        self.DEPTH_CHARTS : "fangraphsdc",
        self.ATC : "atc",
        self.THE_BAT : "thebat",
        self.THE_BATX : "thebatx",
        self.OOPSY : "oopsy"
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
    ROSTERED_C = 10
    ROSTERED_1B = 11
    ROSTERED_2B = 12
    ROSTERED_3B = 13
    ROSTERED_SS = 14
    ROSTERED_OF = 15
    ROSTERED_UTIL = 16
    ROSTERED_SP = 17
    ROSTERED_RP = 18
    REP_LEVEL_SCHEME = 19
    NUM_TEAMS = 20
    HITTER_SPLIT = 21
    NON_PRODUCTIVE_DOLLARS = 22
    HITTER_RANKING_BASIS = 23
    PA_TO_RANK = 24
    SP_IP_TO_RANK = 25
    RP_IP_TO_RANK = 26
    COMBINE_TWO_WAY_PLAYERS = 27
    PITCHER_RANKING_BASIS = 28
    HITTER_DOLLAR_PER_FOM = 29
    PITCHER_DOLLAR_PER_FOM = 30
    TOTAL_HITTERS_ROSTERED = 31
    TOTAL_PITCHERS_ROSTERED = 32
    TOTAL_GAMES_PLAYED = 33
    TOTAL_INNINGS_PITCHED = 34
    TOTAL_FOM_ABOVE_REPLACEMENT = 35
    GS_LIMIT = 36
    RP_G_TARGET = 37
    RP_IP_TARGET = 38
    IP_TARGET = 39
    SP_MULTIPLIER = 40
    RP_MULTIPLIER = 41
    INCLUDE_SVH = 42
    SP_WITH_ALL_IP = 43
    RP_WITH_ALL_IP = 44
    BATTER_G_TARGET = 45

    @classmethod
    def pos_to_num_rostered(self):
        return {
            Position.POS_C : self.ROSTERED_C,
            Position.POS_1B : self.ROSTERED_1B,
            Position.POS_2B : self.ROSTERED_2B,
            Position.POS_3B : self.ROSTERED_3B,
            Position.POS_SS : self.ROSTERED_SS,
            Position.POS_OF : self.ROSTERED_OF,
            Position.POS_UTIL : self.ROSTERED_UTIL,
            Position.POS_SP : self.ROSTERED_SP,
            Position.POS_RP : self.ROSTERED_RP
        }
    
    @classmethod
    def pos_to_rep_level(self):
        return {
            Position.POS_C : self.REP_LEVEL_C,
            Position.POS_1B : self.REP_LEVEL_1B,
            Position.POS_2B : self.REP_LEVEL_2B,
            Position.POS_3B : self.REP_LEVEL_3B,
            Position.POS_SS : self.REP_LEVEL_SS,
            Position.POS_OF : self.REP_LEVEL_OF,
            Position.POS_UTIL : self.REP_LEVEL_UTIL,
            Position.POS_SP : self.REP_LEVEL_SP,
            Position.POS_RP : self.REP_LEVEL_RP
        }
    
    @classmethod
    def get_adv_inputs(self) -> List[CalculationDataType]:
        return [
            self.BATTER_G_TARGET,
            self.GS_LIMIT,
            self.RP_G_TARGET,
            self.RP_IP_TARGET,
            self.IP_TARGET,
            self.SP_MULTIPLIER,
            self.RP_MULTIPLIER,
            self.SP_WITH_ALL_IP,
            self.RP_WITH_ALL_IP
        ]

class RepLevelScheme(Enum):
    NUM_ROSTERED = 0
    STATIC_REP_LEVEL = 1
    FILL_GAMES = 2
    TOTAL_ROSTERED = 3

    @classmethod
    def num_to_enum_map(self):
        return {
            0: self.NUM_ROSTERED,
            1: self.STATIC_REP_LEVEL,
            2: self.FILL_GAMES,
            3: self.TOTAL_ROSTERED
        }

class RankingBasis(Enum):
    PPG = 0
    PPPA = 1
    PIP  = 2
    ZSCORE = 3
    SGP = 4,
    FG_AC = 5,
    ZSCORE_PER_G = 6

    @classmethod
    def num_to_enum_map(self):
        return {
            0 : self.PPG,
            1 : self.PPPA,
            2 : self.PIP,
            3 : self.ZSCORE,
            4 : self.SGP,
            5 : self.FG_AC,
            6 : self.ZSCORE_PER_G
        }
    
    @classmethod
    def display_to_enum_map(self):
        return {
            'P/G' : self.PPG,
            'P/PA' : self.PPPA,
            'P/IP' : self.PIP,
            'zScore' : self.ZSCORE,
            'zScore/G' : self.ZSCORE_PER_G,
            'SGP' : self.SGP
        }
    
    @classmethod
    def enum_to_display_dict(self):
        return {
            self.PPG : 'P/G',
            self.PPPA : 'P/PA',
            self.PIP : 'P/IP',
            self.ZSCORE : 'zScore',
            self.ZSCORE_PER_G : 'zScore/G',
            self.SGP : 'SGP',
            self.FG_AC : 'FG AC'
            
        }

    
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
    BABIP_H = 40
    BABIP_P = 41
    HR_PER_9 = 42
    POINTS = 43
    PPG = 44
    PIP = 45

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
        'SO'  : self.K,
        'HBP' : self.HBP,
        'SB' : self.SB,
        'CS' : self.CS,
        'AVG' : self.AVG,
        'OBP' : self.OBP,
        'SLG' : self.SLG,
        'OPS' : self.OPS,
        'wOBA' : self.WOBA,
        'wRC+' : self.WRC_PLUS,
        'BABIP' : self.BABIP_H
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
        'SO' : self.SO,
        'BB' : self.BB_ALLOWED,
        'HBP' : self.HBP_ALLOWED,
        'WHIP' : self.WHIP,
        'K/9' : self.K_PER_9,
        'BB/9' : self.BB_PER_9,
        'ERA' : self.ERA,
        'FIP' : self.FIP,
        'BABIP' : self.BABIP_P,
        'HR/9' : self.HR_PER_9
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
        self.WRC_PLUS: 'wRC+',
        self.BABIP_H : 'BABIP',
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
        self.FIP : 'FIP',
        self.BABIP_P : 'BABIP',
        self.HR_PER_9 : 'HR/9',
        self.POINTS: 'Points',
        self.PPG: 'PPG',
        self.PIP: 'PIP'
    }

    @classmethod
    def get_stat_format(self):
        zero_decimal = "{:.0f}"
        one_decimal = "{:.1f}"
        two_decimal = "{:.2f}"
        three_decimal = "{:.3f}"
        return {
            self.G_HIT: zero_decimal,
            self.GS_HIT : zero_decimal,
            self.PA : zero_decimal,
            self.AB : zero_decimal,
            self.H : zero_decimal,
            self.DOUBLE : zero_decimal,
            self.TRIPLE : zero_decimal, 
            self.HR : zero_decimal,
            self.R : zero_decimal,
            self.RBI : zero_decimal,
            self.BB : zero_decimal,
            self.SO : zero_decimal,
            self.HBP : zero_decimal,
            self.SB : zero_decimal,
            self.CS : zero_decimal,
            self.AVG : three_decimal,
            self.OBP : three_decimal,
            self.SLG : three_decimal,
            self.OPS : three_decimal,
            self.WOBA : three_decimal,
            self.WRC_PLUS: zero_decimal,
            self.G_PIT : zero_decimal,
            self.GS_PIT : zero_decimal,
            self.IP : one_decimal,
            self.W : zero_decimal,
            self.L : zero_decimal,
            self.QS : zero_decimal,
            self.SV : zero_decimal,
            self.HLD : zero_decimal,
            self.H_ALLOWED : zero_decimal,
            self.ER : zero_decimal,
            self.HR_ALLOWED : zero_decimal,
            self.K : zero_decimal,
            self.BB_ALLOWED : zero_decimal,
            self.HBP_ALLOWED : zero_decimal,
            self.WHIP : two_decimal,
            self.K_PER_9 : two_decimal,
            self.BB_PER_9 : two_decimal,
            self.ERA : two_decimal,
            self.FIP : two_decimal,
            self.BABIP_H : three_decimal,
            self.BABIP_P : three_decimal,
            self.HR_PER_9 : two_decimal, 
            self.POINTS: one_decimal,
            self.PPG: two_decimal,
            self.PIP: two_decimal
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
    def is_points_type(self, format):
        return format in [self.FG_POINTS, self.H2H_FG_POINTS, self.SABR_POINTS, self.H2H_SABR_POINTS]
    
    @classmethod
    def is_sabr(self, format):
        return format in [self.SABR_POINTS, self.H2H_SABR_POINTS]
    
    @classmethod
    def is_h2h(self, format:ScoringFormat) -> bool:
        return format in [self.H2H_FG_POINTS, self.H2H_SABR_POINTS]

    @classmethod
    def name_to_enum_map(self):
        return {'All' : self.ALL,
                        'Ottoneu Classic (4x4)': self.CLASSIC_4X4, 
                        'Old School (5x5)': self.OLD_SCHOOL_5X5,
                        'FanGraphs Points': self.FG_POINTS,
                        'SABR Points': self.SABR_POINTS,
                        'H2H FanGraphs Points': self.H2H_FG_POINTS,
                        'H2H SABR Points': self.H2H_SABR_POINTS}
    
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
    
    @classmethod 
    def get_discrete_types(self):
        return [self.CLASSIC_4X4,
                self.OLD_SCHOOL_5X5,
                self.FG_POINTS,
                self.SABR_POINTS,
                self.H2H_FG_POINTS,
                self.H2H_SABR_POINTS] 

class Position(Enum):
    POS_C = 'C'
    POS_1B = '1B'
    POS_2B = '2B'
    POS_3B = '3B'
    POS_SS = 'SS'
    POS_MI = 'MI'
    POS_OF = 'OF'
    POS_UTIL = 'Util'
    POS_SP = 'SP'
    POS_RP = 'RP'    
    POS_TWO_WAY = 'Two-Way'
    OFFENSE = "Offense"
    PITCHER = "Pitcher"
    OVERALL = 'Overall'

    @classmethod
    def get_display_order(self):
        return [self.OVERALL,
            self.OFFENSE,
            self.PITCHER,
            self.POS_C,
            self.POS_1B,
            self.POS_2B,
            self.POS_SS,
            self.POS_3B,
            self.POS_OF,
            self.POS_UTIL,
            self.POS_SP,
            self.POS_RP]

    @classmethod
    def get_offensive_pos(self):
        return [self.OFFENSE,
            self.POS_C, 
            self.POS_1B,
            self.POS_2B,
            self.POS_SS,
            self.POS_MI,
            self.POS_OF,
            self.POS_3B,
            self.POS_UTIL]
    
    @classmethod
    def get_discrete_offensive_pos(self):
        return [self.POS_C, 
            self.POS_1B,
            self.POS_2B,
            self.POS_SS,
            self.POS_3B,
            self.POS_OF,
            self.POS_UTIL]
    
    @classmethod
    def get_pitching_pos(self):
        return [self.PITCHER,
            self.POS_SP,
            self.POS_RP]

    @classmethod
    def get_discrete_pitching_pos(self):
        return [self.POS_SP, self.POS_RP]

class IdType(Enum):
    OTTONEU = 'Ottoneu'
    FANGRAPHS = 'FanGraphs'

class PropertyType(Enum):
    DB_VERSION = 'db.version'

class AvgSalaryFom(str, Enum):
    MEAN = 'Mean',
    MEDIAN = 'Median'

class Preference(str, Enum):
    SALARY_REFRESH_FREQUENCY = 'sal_refresh_freq',
    AVG_SALARY_FOM = 'avg_sal_fom',
    DOCK_DRAFT_TARGETS = 'dock_draft_targets',
    DOCK_DRAFT_PLAYER_SEARCH = 'dock_draft_player_search',
    DEFAULT_BROWSER = 'default_proj_browser'

class Browser(str, Enum):
    CHROME = 'ChromeHTML',
    FIREFOX = 'FirefoxURL',
    EDGE = 'MSEdgeHTM'

    @classmethod
    def get_display(self, enum):
        return {
            self.CHROME: 'Chrome',
            self.FIREFOX: 'Firefox',
            self.EDGE: 'Microsoft Edge'}.get(enum, None)
    
    @classmethod
    def get_enum_from_display(self, display):
        return {
            'Chrome': self.CHROME,
            'Firefox': self.FIREFOX,
            'Microsoft Edge': self.EDGE
        }.get(display, None)