from __future__ import annotations
from enum import Enum
from typing import List, Dict
import re

class ProjectionType(int,Enum):
    '''Enumeration of the available types of projections for the system, including name and url information.'''
    id:int
    type_name:str
    url: str

    def __new__(
        cls, id: int, name: str = "", url: str = ""
    ) -> ProjectionType:
        obj = int.__new__(cls,id)
        obj._value_ = id

        obj.type_name = name
        obj.url = url
        return obj

    STEAMER = (0, 'Steamer', 'steamer')
    ZIPS = (1, 'ZiPs', 'zips')
    DEPTH_CHARTS = (2, 'FG Depth Charts', 'fangraphsdc')
    ATC = (3, 'ATC', 'atc')
    THE_BAT = (4, 'THE BAT', 'thebat')
    THE_BATX = (5, 'THE BATX', 'thebatx')
    CUSTOM = (6, 'Custom')
    VALUE_DERIVED = (7, 'Derived')
    DAVENPORT = (8, 'Davenport')

    @classmethod
    def get_fg_downloadable(self) -> List[ProjectionType]:
        '''Returns list of ProjectionType that are downloadable from FanGraphs'''
        return [self.STEAMER, self.ZIPS, self.DEPTH_CHARTS, self.ATC, self.THE_BAT, self.THE_BATX]
    
    @classmethod
    def get_downloadable(self) -> List[ProjectionType]:
        '''Returns list of ProjectionType that are downloadable'''
        return [self.DAVENPORT, self.STEAMER, self.ZIPS, self.DEPTH_CHARTS, self.ATC, self.THE_BAT, self.THE_BATX]

    @classmethod
    def get_enum_by_name(self, name:str)->ProjectionType:
        '''Gets the enum with the argument name. Returns None if no matches'''
        for pt in ProjectionType:
            if pt.type_name == name:
                return pt
        return None

class CalculationDataType(Enum):
    '''Enumeration of the data types available for and created by ValueCalculations'''
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
    H2H_WEEKS = 46
    CUSTOM_SCORING_FORMAT = 47

    @classmethod
    def pos_to_num_rostered(self) -> Dict[Position, CalculationDataType]:
        '''Returns a Dict that maps player positions to the CalculationDataType for number of rostered players at the position'''
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
    def pos_to_rep_level(self) -> Dict[Position, CalculationDataType]:
        '''Returns a Dict that maps player positions to the CalculationDataType for replacement level at the position'''
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
        '''Returns the list of CalculationDataType that are available as advanced inputs'''
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
    '''Enumeration of the available replacement level schemes for ValueCalculations'''
    NUM_ROSTERED = 0
    STATIC_REP_LEVEL = 1
    FILL_GAMES = 2
    TOTAL_ROSTERED = 3

    @classmethod
    def get_enum_by_num(self, id:int) -> RepLevelScheme:
        '''Gets the enumeration matching the RepLevelScheme number. None if no match'''
        for rls in RepLevelScheme:
            if rls._value_ == id:
                return rls
        return None

class RankingBasis(int, Enum):
    '''Enumeration of bases for ranking players'''

    id:int
    display:str

    def __new__(
        cls, id: int, display: str = ""
    ) -> RankingBasis:
        obj = int.__new__(cls, id)
        obj._value_ = id

        obj.display = display
        return obj

    PPG = (0, 'P/G')
    PPPA = (1, 'P/PA')
    PIP  = (2, 'P/IP')
    ZSCORE = (3, 'zScore')
    SGP = (4, 'SGP')
    FG_AC = (5, 'FG AC')
    ZSCORE_PER_G = (6, 'zScore/G')
    ZSCORE_PER_IP = (7, 'zScore/IP')

    @classmethod
    def get_enum_by_id(self, id:int) -> RankingBasis:
        '''Returns the RankingBasis that matches the argument id. None if no match'''
        for rb in RankingBasis:
            if rb.id == id:
                return rb
        return None
    
    @classmethod
    def get_enum_by_display(self, display:str) -> RankingBasis:
        '''Returns the RankingBasis that matches the arguement display. None if no match'''
        for rb in RankingBasis:
            if rb.display == display:
                return rb
        return None

    @classmethod
    def is_zscore(self, basis:RankingBasis) -> bool:
        '''Returns if RankingBasis is a zScore type basis'''
        return basis in [self.ZSCORE, self.ZSCORE_PER_G, self.ZSCORE_PER_IP]
    
    @classmethod
    def is_roto_fractional(self, basis:RankingBasis) -> bool:
        '''Returns if ranking basis is for a roto league and is a rate basis'''
        return basis in [self.ZSCORE_PER_G, self.ZSCORE_PER_IP]
    
class StatType(int, Enum):
    '''Enumeration of the available stat types for Projections'''

    id:int
    display:str
    stat_list:List[str]
    rank:int
    hitter: bool
    format: str
    higher_better: bool

    def __new__(
        cls, id: int, stat_list: List[str], rank:int, hitter: bool, format:str = "{:.0f}", higher_better:bool = True
    ) -> StatType:
        obj = int.__new__(cls, id)
        obj._value_ = id

        obj.display = stat_list[0]
        obj.stat_list = stat_list
        obj.rank = rank
        obj.hitter = hitter
        obj.format = format
        obj.higher_better = higher_better
        return obj

    G_HIT = (0, ['G', 'G_C', 'G_FB', 'G_SB', 'G_3B', 'G_SS', 'G_LF', 'G_CF', 'G_RF', 'G_DH'], 1, True)
    GS_HIT = (1, ['GS'], 2, True)
    PA = (2, ['PA'], 3, True)
    AB = (3, ['AB'], 4, True)
    H = (4, ['H'], 7, True)
    DOUBLE = (5, ['2B'], 8, True)
    TRIPLE = (6, ['3B'], 9, True)
    HR = (7, ['HR'], 10, True)
    R = (8, ['R'], 5, True)
    RBI = (9, ['RBI'], 6, True)
    BB = (10, ['BB'], 11, True)
    SO = (11, ['SO'], 12, False)
    HBP = (12, ['HBP'], 13, True)
    SB = (13, ['SB'], 14, True)
    CS = (14, ['CS'], 15, True, "{:.0f}", False)
    AVG = (15, ['AVG', 'BA'], 17, True, "{:.3f}")
    OBP = (16, ['OBP'], 18, True, "{:.3f}")
    SLG = (17, ['SLG'], 19, True, "{:.3f}")
    OPS = (18, ['OPS'], 20, True, "{:.3f}")
    WOBA = (19, ['wOBA'], 22, True, "{:.3f}")
    WRC_PLUS = (20, ['wRC+'], 23, True, "{:.0f}")
    G_PIT = (21, ['G'], 1, False)
    GS_PIT = (22, ['GS'], 2, False)
    IP = (23, ['IP'], 3, False, "{:.1f}")
    W = (24, ['W'], 4, False)
    L = (25, ['L'], 5, False, "{:.0f}", False)
    QS = (26, ['QS'], 6, False)
    SV = (27, ['SV'], 12, False)
    HLD = (28, ['HLD', 'Holds'], 13, False)
    H_ALLOWED = (29, ['H'], 8, False, "{:.0f}", False)
    ER = (30, ['ER'], 18, False, "{:.0f}", False)
    HR_ALLOWED = (31, ['HR', 'HRA'], 11, False, "{:.0f}", False)
    K = (32, ['SO'], 7, True)
    BB_ALLOWED = (33, ['BB'], 9, False, "{:.0f}", False)
    HBP_ALLOWED = (34, ['HBP'], 10, False, "{:.0f}", False)
    WHIP = (35, ['WHIP'], 20, False, "{:.2f}", False)
    K_PER_9 = (36, ['K/9'], 21, False, "{:.2f}")
    BB_PER_9 = (37, ['BB/9'], 22, False, "{:.2f}", False)
    ERA = (38, ['ERA'], 19, False, "{:.2f}", False)
    FIP = (39, ['FIP'], 25, False, "{:.2f}", False)
    BABIP_H = (40, ['BABIP'], 21, True, "{:.3f}")
    BABIP_P = (41, ['BABIP'], 24, False, "{:.3f}", False)
    HR_PER_9 = (42, ['HR/9'], 23, False, "{:.2f}", False)
    POINTS = (43, ['Points'], -1, True, "{:.1f}")
    PPG = (44, ['PPG'], -1, True, "{:.2f}", True)
    PIP = (45, ['PIP'], -1, True, "{:.2f}", True)
    NET_SB = (46, ['Net SB', 'NSB'], 16, True)
    NET_SAVES = (47, ['Net SV', 'NSV'], 16, False)
    NET_SVH = (48, ['Net SVH', 'NSVH'], 17, False)
    BS = (49, ['BS'], 14, False)
    SVH = (50, ['SVH'], 15, False)

    @property
    def rate_denom(self) -> StatType:
        lookup = {
            StatType.AVG: StatType.AB,
            StatType.OBP: StatType.PA,
            StatType.SLG: StatType.AB,
            StatType.OPS: StatType.PA,
            StatType.WOBA: StatType.PA,
            StatType.WRC_PLUS: StatType.PA,
            StatType.WHIP: StatType.IP,
            StatType.ERA: StatType.IP,
            StatType.K_PER_9: StatType.IP,
            StatType.BB_PER_9: StatType.IP,
            StatType.FIP: StatType.IP,
            StatType.HR_PER_9: StatType.IP,
            StatType.BABIP_H: StatType.AB,
            StatType.BABIP_P:StatType.IP
        }
        return lookup.get(self, None)

    @classmethod
    def get_hit_stattype(self, display:str) -> StatType:
        '''Returns the hitter StatType for the given display. None if no match'''
        for st in StatType:
            if st.hitter and display in st.stat_list:
                return st
        return None

    @classmethod
    def get_pitch_stattype(self, display:str) -> StatType:
        '''Returns the pitcher StatType for the given display. None if no match'''
        for st in StatType:
            if not st.hitter and display in st.stat_list:
                return st
        return None

    @classmethod
    def get_all_hit_stattype(self, no_rates:bool = False) -> List[StatType]:
        '''Returns a list of all StatTypes for hitters. If no_rates is True, any rate stats are excluded'''
        sts = []
        for st in StatType:
            if st.hitter:
                if no_rates and st.rate:
                    continue
                if st.rank < 0:
                    continue
                sts.append(st)
        return sorted(sts, key=lambda st: st.rank)
    
    @classmethod
    def get_all_pitch_stattype(self, no_rates:bool = False) -> List[StatType]:
        '''Returns a list of all StatTypes for pitchers. If no_rates is True, any rate stats are excluded'''
        sts = []
        for st in StatType:
            if not st.hitter:
                if no_rates and st.rate_denom is not None:
                    continue
                if st.rank < 0:
                    continue
                sts.append(st)
        return sorted(sts, key=lambda st: st.rank)

class ScoringFormat(int, Enum):
    '''Enumeration of all Ottoneu Scoring Formats'''

    id:int
    full_name:str
    short_name:str

    def __new__(
        cls, id: int, full_name: str, short_name:str
    ) -> ScoringFormat:
        obj = int.__new__(cls, id)
        obj._value_ = id

        obj.full_name = full_name
        obj.short_name = short_name
        return obj

    ALL = (0, 'All', 'All')
    CLASSIC_4X4 = (1, 'Ottoneu Classic (4x4)', '4x4')
    OLD_SCHOOL_5X5 = (2, 'Old School (5x5)', '5x5')
    FG_POINTS = (3, 'FanGraphs Points', 'FGP')
    SABR_POINTS = (4, 'SABR Points', 'SABR')
    H2H_FG_POINTS = (5, 'H2H FanGraphs Points', 'H2H FGP')
    H2H_SABR_POINTS = (6, 'H2H SABR Points', 'H2H SABR')
    CUSTOM = (7, 'Custom', 'Custom')

    @classmethod
    def get_format_stat_categories(self, format:ScoringFormat) -> List[StatType]:
        if format == ScoringFormat.OLD_SCHOOL_5X5:
            cats = [StatType.R, StatType.HR, StatType.RBI, StatType.SB, StatType.AVG,
                    StatType.W, StatType.SV, StatType.SO, StatType.ERA, StatType.WHIP]
        elif format == ScoringFormat.CLASSIC_4X4:
            cats = [StatType.R, StatType.HR, StatType.OBP, StatType.SLG,
                    StatType.SO, StatType.ERA, StatType.WHIP, StatType.HR_PER_9]
        else:
            cats = [StatType.POINTS]
        return cats

    @classmethod
    def is_points_type(self, format:ScoringFormat) -> bool:
        '''Returns if the argument format is a points format'''
        return format in [self.FG_POINTS, self.H2H_FG_POINTS, self.SABR_POINTS, self.H2H_SABR_POINTS]
    
    @classmethod
    def is_sabr(self, format:ScoringFormat) -> bool:
        '''Returns if the argument format is a SABR points format'''
        return format in [self.SABR_POINTS, self.H2H_SABR_POINTS]
    
    @classmethod
    def is_h2h(self, format:ScoringFormat) -> bool:
        '''Returns if the argument format is a head-to-head format'''
        return format in [self.H2H_FG_POINTS, self.H2H_SABR_POINTS]

    @classmethod
    def get_format_by_full_name(self, full_name:str) -> ScoringFormat:
        '''Returns the ScoringFormat matching the argument full name. None if no match'''
        for sf in ScoringFormat:
            if sf.full_name == full_name:
                return sf
        return None
    
    @classmethod 
    def get_discrete_types(self) -> List[ScoringFormat]:
        '''Returns a list of discrete ScoringFormats'''
        return [self.CLASSIC_4X4,
                self.OLD_SCHOOL_5X5,
                self.FG_POINTS,
                self.SABR_POINTS,
                self.H2H_FG_POINTS,
                self.H2H_SABR_POINTS,
                self.CUSTOM] 

class Position(Enum):
    '''Enumeration of Ottoneu positions'''
    POS_C = 'C'
    POS_1B = '1B'
    POS_2B = '2B'
    POS_3B = '3B'
    POS_SS = 'SS'
    POS_CI = 'CI'
    POS_MI = 'MI'
    POS_INF = 'INF'
    POS_OF = 'OF'
    POS_LF = 'LF'
    POS_CF = 'CF'
    POS_RF = 'RF'
    POS_UTIL = 'Util'
    POS_SP = 'SP'
    POS_RP = 'RP'    
    POS_P = 'P'
    POS_TWO_WAY = 'Two-Way'
    OFFENSE = "Offense"
    PITCHER = "Pitcher"
    OVERALL = 'Overall'

    @classmethod
    def get_display_order(self) -> List[Position]:
        '''Returns the ordered list of Positions for display in tables'''
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
    def get_offensive_pos(self) -> List[Position]:
        '''Returns list of all offensive positions, including general offense'''
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
    def get_discrete_offensive_pos(self) -> List[Position]:
        '''Returns list of offensive positions that does not include overall offense or MI'''
        return [self.POS_C, 
            self.POS_1B,
            self.POS_2B,
            self.POS_SS,
            self.POS_3B,
            self.POS_OF,
            self.POS_UTIL]
    
    @classmethod
    def __get_all_offensive_pos(self) -> List[Position]:
        return [
            self.POS_C,
            self.POS_1B,
            self.POS_2B,
            self.POS_SS,
            self.POS_3B,
            self.POS_CI,
            self.POS_MI,
            self.POS_INF,
            self.POS_LF,
            self.POS_CF,
            self.POS_RF,
            self.POS_OF,
            self.POS_UTIL
        ]
    
    @classmethod
    def get_pitching_pos(self) -> List[Position]:
        '''Returns list of all pitching positions, including all pitchers'''
        return [self.PITCHER,
            self.POS_SP,
            self.POS_RP]

    @classmethod
    def get_discrete_pitching_pos(self) -> List[Position]:
        '''Returns list of pitching positions, not including general pitchers'''
        return [self.POS_SP, self.POS_RP]
    
    def eligible(test_pos:str, pos:Position) -> bool:
        '''Returns if the position string is eligible for the given position'''
        if pos == Position.OVERALL:
            return True
        elif pos == Position.OFFENSE or pos == Position.POS_UTIL:
            for p in Position.__get_all_offensive_pos():
                if p.value in test_pos:
                    return True
            return False
        elif pos == Position.POS_C:
            #Need to change C eligibility search because of potential CI or CF positions
            return 'C/' in test_pos or 'C' == test_pos
        elif pos == Position.POS_MI:
            return bool(re.search('2B|SS|MI', test_pos))
        elif pos == Position.POS_CI:
            return bool(re.search('1B|3B|CI', test_pos))
        elif pos == Position.POS_INF:
            return bool(re.search('1B|2B|SS|3B|CI|MI|INF', test_pos))
        elif pos == Position.POS_OF:
            return bool(re.search('OF|LF|CF|RF', test_pos))
        elif pos == Position.PITCHER:
            for p in Position.get_discrete_pitching_pos():
                if p.value in test_pos:
                    return True
            return False
        return pos.value in test_pos

class IdType(Enum):
    '''Enumeration of player id types'''
    OTTONEU = 'Ottoneu'
    FANGRAPHS = 'FanGraphs'
    MLB = 'MLBID'

class PropertyType(Enum):
    '''Enumeration of Ottoneu Toolbox propery types'''
    DB_VERSION = 'db.version'

class AvgSalaryFom(str, Enum):
    '''Enumeration of average salary statistic types'''
    MEAN = 'Mean',
    MEDIAN = 'Median'

class Preference(str, Enum):
    '''Enumeration of Ottoneu Toolbox preferences'''
    SALARY_REFRESH_FREQUENCY = 'sal_refresh_freq',
    AVG_SALARY_FOM = 'avg_sal_fom',
    DOCK_DRAFT_TARGETS = 'dock_draft_targets',
    DOCK_DRAFT_PLAYER_SEARCH = 'dock_draft_player_search',
    DEFAULT_BROWSER = 'default_proj_browser'
    INFLATION_METHOD = 'inflation_methodology'

class Browser(str, Enum):
    '''Enumeration of available browser types for projection download'''

    name:str
    display: str

    def __new__(
        cls, name: str, display: str = ""
    ) -> Browser:
        obj = str.__new__(cls, name)
        obj._value_ = name

        obj.display = display
        return obj

    CHROME = ('ChromeHTML', 'Chrome')
    FIREFOX = ('FirefoxURL', 'Firefox')
    EDGE = ('MSEdgeHTM', 'Microsoft Edge')
    '''Enumeration of available browser types for projection download'''

    @classmethod
    def get_enum_from_display(self, display:str) -> Browser:
        '''Returns the Browser for the argument display name. None if no match'''
        for b in Browser:
            if b.display == display:
                return b
        return None

class InflationMethod(str, Enum):
    CONVENTIONAL = 'Conventional'
    ROSTER_SPOTS_ONLY = 'Roster Spots Only'
    MARGINAL_VALUE = 'Marginal Value'

class Platform(str, Enum):
    OTTONEU = 'Ottoneu'
    YAHOO = 'Yahoo'
    OTHER = 'Other'