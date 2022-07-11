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

    enum_to_name_dict = {
        STEAMER : "Steamer",
        ZIPS : "ZiPS",
        DEPTH_CHARTS : "FG Depth Charts",
        ATC : "ATC",
        THE_BAT : "THE BAT",
        THE_BATX : "THE BATX",
        CUSTOM : "Custom"
    }

    name_to_enum_dict = {
        "Steamer" : STEAMER,
        "ZiPS" : ZIPS,
        "FG Depth Charts" : DEPTH_CHARTS,
        "ATC" : ATC,
        "THE BAT" : THE_BAT,
        "THE BATX" : THE_BATX,
        "Custom" : CUSTOM
    }

    enum_to_url = {
        STEAMER : "steamer",
        ZIPS : "zips",
        DEPTH_CHARTS : "fangraphsdc",
        ATC : "atc",
        THE_BAT : "thebat",
        THE_BATX : "thebatx"
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

    hit_to_enum_dict = {
        'G' : G_HIT,
        'GS' : GS_HIT,
        'PA': PA,
        'AB' : AB,
        'H' : H,
        '2B' : DOUBLE,
        '3B' : TRIPLE, 
        'HR' : HR,
        'R' : R,
        'RBI' : RBI,
        'BB' : BB,
        'SO'  : SO,
        'HBP' : HBP,
        'SB' : SB,
        'CS' : CS,
        'AVG' : AVG,
        'OBP' : OBP,
        'SLG' : SLG,
        'OPS' : OPS,
        'wOBA' : WOBA
    }

    pitch_to_enum_dict = {
        'G': G_PIT,
        'GS': GS_PIT,
        'IP' : IP,
        'W' : W,
        'L' : L,
        'QS' : QS,
        'SV' : SV,
        'HLD' : HLD,
        'H' : H_ALLOWED,
        'ER' : ER,
        'HR' : HR_ALLOWED,
        'K' : K,
        'BB' : BB_ALLOWED,
        'HBP' : HBP_ALLOWED,
        'WHIP' : WHIP,
        'K/9' : K_PER_9,
        'BB/9' : BB_PER_9,
        'ERA' : ERA,
        'FIP' : FIP
    }

    enum_to_display_dict = {
        G_HIT: 'G',
        GS_HIT : 'GS',
        PA : 'PA',
        AB : 'AB',
        H : 'H',
        DOUBLE : '2B',
        TRIPLE : '3B', 
        HR : 'HR',
        R : 'R',
        RBI : 'RBI',
        BB : 'BB',
        SO : 'SO',
        HBP : 'HBP',
        SB : 'SB',
        CS : 'CS',
        AVG : 'AVG',
        OBP : 'OBP',
        SLG : 'SLG',
        OPS : 'OPS',
        WOBA : 'wOBA',
        G_PIT : 'G',
        GS_PIT : 'GS',
        IP : 'IP',
        W : 'W',
        L : 'L',
        QS : 'QS',
        SV : 'SV',
        HLD : 'HLD',
        H_ALLOWED : 'H',
        ER : 'ER',
        HR_ALLOWED : 'HR',
        K : 'K',
        BB_ALLOWED : 'BB',
        HBP_ALLOWED : 'HBP',
        WHIP : 'WHIP',
        K_PER_9 : 'K/9',
        BB_PER_9 : 'BB/9',
        ERA : 'ERA',
        FIP : 'FIP'
    }

class ScoringFormat(Enum):
    ALL = 0
    CLASSIC_4X4 = 1
    OLD_SCHOOL_5X5 = 2
    FG_POINTS = 3
    SABR_POINTS = 4
    H2H_FG_POINTS = 5
    H2H_SABR_POINTS = 6

    name_to_enum_map = {'All' : ALL,
                        'Ottoneu Classic (4x4)': CLASSIC_4X4, 
                        'Old School (5x5)': OLD_SCHOOL_5X5,
                        'FanGraphs Points': FG_POINTS,
                        'SABR Points': SABR_POINTS,
                        'H2H FanGraphs Points': H2H_FG_POINTS,
                        'H2H SABR Points': H2H_FG_POINTS}
    
    enum_to_full_name_map = {ALL : "All",
                            CLASSIC_4X4: 'Ottoneu Classic (4x4)',
                            OLD_SCHOOL_5X5: 'Old School (5x5)',
                            FG_POINTS: 'FanGraphs Points',
                            SABR_POINTS: 'SABR Points',
                            H2H_FG_POINTS: 'H2H FanGraphs Points',
                            H2H_SABR_POINTS: 'H2H SABR Points'}

    enum_to_short_name_map = {ALL : "All",
                            CLASSIC_4X4: '4x4',
                            OLD_SCHOOL_5X5: '5x5',
                            FG_POINTS: 'FGP',
                            SABR_POINTS: 'SABR',
                            H2H_FG_POINTS: 'H2H FGP',
                            H2H_SABR_POINTS: 'H2H SABR'}
