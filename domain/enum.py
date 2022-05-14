from enum import Enum

class ProjectionType(Enum):
    STEAMER = 0
    ZIPS = 1
    DEPTH_CHARTS = 2
    ATC = 3
    THE_BAT = 4
    THE_BATX = 5
    CUSTOM = 6

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
