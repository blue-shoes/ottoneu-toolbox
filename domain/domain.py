from __future__ import annotations
from datetime import datetime
from dataclasses import field
from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship, registry, Mapped, mapped_column, reconstructor
from domain.enum import CalculationDataType, ProjectionType, RankingBasis, ScoringFormat, StatType, Position, IdType, Platform
from typing import List, Dict, Tuple

reg = registry()

@reg.mapped_as_dataclass
class Property:
    __tablename__ = "properties"
    name:Mapped[str] = mapped_column(default=None, primary_key=True)
    value:Mapped[str] = mapped_column(default=None)

@reg.mapped_as_dataclass
class Player:
    __tablename__ = "player"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    ottoneu_id:Mapped[int] = mapped_column("Ottoneu ID", default=None, index=True, nullable=True)
    fg_major_id:Mapped[str] = mapped_column("FG MajorLeagueID", default=None, repr=False, nullable=True)
    fg_minor_id:Mapped[str] = mapped_column("FG MinorLeagueID", default=None, repr=False, nullable=True)
    name:Mapped[str] = mapped_column("Name", default=None)
    search_name:Mapped[str] = mapped_column(default=None, repr=False)
    team:Mapped[str] = mapped_column("Org", default=None, nullable=True)
    position:Mapped[str] = mapped_column("Position(s)", default=None)
    yahoo_id:Mapped[int] = mapped_column(default=None, repr=False, nullable=True)

    salary_info:Mapped[List["Salary_Info"]] = relationship(default_factory=list, back_populates="player", cascade="all, delete", lazy="joined", repr=False)

    # Transient fields
    custom_positions:str = field(default=None,)

    __table_args__ = (Index('idx_fg_id','FG MajorLeagueID','FG MinorLeagueID'),)

    def __hash__(self) -> int:
        return hash(self.id)
    
    @reconstructor
    def init_on_load(self):
        self.__is_eligible = {}

    def get_fg_id(self) -> object:
        '''Returns the FanGraphs Major League id, if available, otherwise returns the FanGraphs Minor League id.'''
        if self.fg_major_id:
            return self.fg_major_id
        else:
            return self.fg_minor_id
    
    def pos_eligible(self, pos: Position) -> bool:
        '''Returns if the Player is eligible at the input Position.'''
        if self.__is_eligible:
            eligible = self.__is_eligible.get(pos, None)
            if eligible:
                return eligible 
        if self.custom_positions:
            test_pos = self.custom_positions
        else:
            test_pos = self.position
        eligible = Position.eligible(test_pos, pos)
        self.__is_eligible[pos] = eligible
        return eligible
    
    def is_two_way(self) -> bool:
        '''Returns if the player is eligible at both hitting and pitching positions.'''
        hit = False
        pitch = False
        for pos in Position.get_offensive_pos():
            if pos.value in self.position:
                hit = True
                continue
        for pos in Position.get_discrete_pitching_pos():
            if pos.value in self.position:
                pitch = True
        return hit and pitch
    
    def get_salary_info_for_format(self, s_format=ScoringFormat.ALL) -> Salary_Info:
        '''Gets the Player's Salary_Info for the input ScoringFormat'''
        for si in self.salary_info:
            if si.s_format == s_format:
                return si
        si = Salary_Info()
        si.s_format = s_format
        si.avg_salary = 0.0
        si.last_10 = 0.0
        si.max_salary = 0.0
        si.min_salary = 0.0
        si.med_salary = 0.0
        si.roster_percentage = 0.0
        return si

@reg.mapped_as_dataclass
class League:
    __tablename__ = "league"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    site_id:Mapped[int] = mapped_column(default=None, nullable=False)
    name:Mapped[str] = mapped_column(default=None)
  
    s_format:Mapped[ScoringFormat] = mapped_column(default=None, nullable=False)
    num_teams:Mapped[int] = mapped_column(default=None, nullable=False)
    last_refresh:Mapped[datetime] = mapped_column(default=None, nullable=False)
    active:Mapped[bool] = mapped_column(default=True, nullable = False)
    roster_spots:Mapped[int] = mapped_column(default=40, nullable=False)

    platform:Mapped[Platform] = mapped_column(default=Platform.OTTONEU, nullable=False)
    team_salary_cap:Mapped[float] = mapped_column(default=400, nullable=False)

    teams:Mapped[List["Team"]] = relationship(default_factory=list, back_populates="league", cascade="all, delete", repr=False)
    projected_keepers:Mapped[List["Projected_Keeper"]] = relationship(default_factory=list, cascade="all, delete", repr=False)

    position_set_id:Mapped[int] = mapped_column(ForeignKey("position_set.id"), default=None, nullable=True)
    position_set:Mapped["PositionSet"] = relationship(default=None)

    starting_set_id:Mapped[int] = mapped_column(ForeignKey("starting_position_set.id"), default=None, nullable=True)
    starting_set:Mapped["StartingPositionSet"] = relationship(default=None)

    # Transient inflation values
    inflation:float = field(default=0, repr=False)    
    total_salary:float = field(default=0, repr=False)
    total_value:float = field(default=0, repr=False)
    num_rostered:int = field(default=0, repr=False)
    num_valued_rostered:int = field(default=0, repr=False)
    captured_marginal_value:float = field(default=0, repr=False)
    npp_spent:float = field(default=0, repr=False)
    max_npp:float = field(default=0, repr=False)
    salary_cap:int = field(default=team_salary_cap*num_teams, repr=False)

    # Transient draft information
    draft_results:Dict[Tuple, int] = field(default_factory=dict, repr=False)
    team_drafts:List[TeamDraft] = field(default_factory=list, repr=False)

    @reconstructor
    def init_on_load(self):
        self.draft_results = {}
        self.__starting_positions = []
        self.__starting_slots = {}

    def is_salary_cap(self) -> bool:
        return self.team_salary_cap != -1

    def get_user_team(self):
        '''Returns the user\'s team for the league. None if no team is specified'''
        for team in self.teams:
            if team.users_team:
                return team
        return None
    
    def get_team_by_id(self, team_id:int) -> Team:
        '''Returns the team from the league by OTB id'''
        for team in self.teams:
            if team.id == team_id:
                return team
        return None

    def get_team_by_site_id(self, site_id:int) -> Team:
        '''Returns the team from the league by site Id'''
        for team in self.teams:
            if team.site_id == site_id:
                return team
        return None

    def is_keeper(self, player_id:int) -> bool:
        if self.projected_keepers is None:
            return False
        for keeper in self.projected_keepers:
            if keeper.player_id == player_id:
                return self.is_rostered(player_id=player_id)
        return False

    def is_rostered(self, player_id:int) -> bool:
        for team in self.teams:
            for rs in team.roster_spots:
                if rs.player_id == player_id:
                    return True
        return False
    
    def get_player_salary(self, player_id:int) -> int:
        for team in self.teams:
            for rs in team.roster_spots:
                if rs.player.id == player_id:
                    return rs.salary
        return 0
    
    def is_rostered_by_ottoneu_id(self, ottoneu_id:int) -> bool:
        '''Determines if player is rostered based on ottoneu id'''
        for team in self.teams:
            for rs in team.roster_spots:
                if rs.player.ottoneu_id == ottoneu_id:
                    return True
        return False
    
    def init_inflation_calc(self):
        '''Initialized the required fields to begin an inflation calculation for the league'''
        self.total_salary = 0
        self.total_value = 0
        self.num_rostered = 0
        self.num_valued_rostered = 0
        self.captured_marginal_value = 0
        self.npp_spent = 0
        self.max_npp = 0
    
    def is_linked(self):
        return self.site_id != -1

    def get_starting_positions(self) -> List[Position]:
        if self.__starting_positions:
            return self.__starting_positions
        self.__starting_positions = [p.position for p in self.starting_set.positions]

        return self.__starting_positions
    
    def get_starting_slots(self) -> Dict[Position, int]:
        if self.__starting_slots:
            return self.__starting_slots
        for pos in self.get_starting_positions():
            self.__starting_slots[pos] = self.starting_set.get_count_for_position(pos)
        return self.__starting_slots

@reg.mapped_as_dataclass
class Team:
    __tablename__ = "team"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    site_id:Mapped[int] = mapped_column(default=None, nullable=False)

    league_id:Mapped[int] = mapped_column(ForeignKey("league.id"), default=None)
    league:Mapped["League"] = relationship(default=None, back_populates="teams", repr=False)

    name:Mapped[str] = mapped_column(default=None)
    users_team:Mapped[bool] = mapped_column(default=False)
    
    roster_spots:Mapped[List["Roster_Spot"]] = relationship(default_factory=list, back_populates="team", cascade="all, delete", repr=False)

    num_players:Mapped[int] = mapped_column(default=None, repr=False, nullable=True)
    spots:Mapped[int] = mapped_column(default=None, repr=False, nullable=True)
    salaries:Mapped[int] = mapped_column(default=None, repr=False, nullable=True)
    penalties:Mapped[int] = mapped_column(default=None, repr=False, nullable=True)
    loans_in:Mapped[int] = mapped_column(default=None, repr=False, nullable=True)
    loans_out:Mapped[int] = mapped_column(default=None, repr=False, nullable=True)
    free_cap:Mapped[int] = mapped_column(default=None, repr=False, nullable=True)

    # Transient values
    rs_map:Dict[int,Roster_Spot] = field(default_factory=dict, repr=False)
    points:float=field(default=0, repr=False)
    lg_rank:int=field(default=0, repr=False)
    cat_stats:Dict[StatType,float]= field(default_factory=dict, repr=False)
    cat_ranks:Dict[StatType,int]= field(default_factory=dict, repr=False)

    @reconstructor
    def init_on_load(self):
        self.cat_stats = {}
        self.cat_ranks = {}

    def get_rs_by_player(self, player:Player) -> Roster_Spot:
        '''Returns the team's Roster_Spot for the input player'''
        if player is None:
            return None
        return self.get_rs_by_player_id(player.id)

    def get_rs_by_player_id(self, player_id:int) -> Roster_Spot:
        '''Returns the team's Roster_Spot for the input player id'''
        if self.rs_map is None:
            for rs in self.roster_spots:
                if rs.player.id == player_id:
                    return rs
            return None
        else:
            return self.rs_map.get(player_id, None)

    def index_rs(self) -> None:
        self.rs_map = {}
        for rs in self.roster_spots:
            self.rs_map[rs.player_id] = rs
            rs.g_h = 0
            rs.ip = 0

@reg.mapped_as_dataclass
class Roster_Spot:
    __tablename__ = "roster_spot"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)

    team_id:Mapped[int] = mapped_column(ForeignKey("team.id"), default=None)
    team:Mapped["Team"] = relationship(default=None, back_populates="roster_spots", repr=False)

    player_id:Mapped[int] = mapped_column(ForeignKey("player.id"), default=None)
    player:Mapped["Player"] = relationship(default=None, lazy="joined")

    salary:Mapped[int] = mapped_column(default=None, nullable=True)

    g_h:int = 0
    ip:int = 0

@reg.mapped_as_dataclass
class Projected_Keeper:
    __tablename__ = "projected_keeper"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    league_id:Mapped[int] = mapped_column(ForeignKey("league.id"), default=None, nullable=False)
    
    player_id:Mapped[int] = mapped_column(ForeignKey("player.id"), default=None, nullable=False)
    player:Mapped[Player] = relationship(default=None, lazy="joined")

    season:Mapped[int] = mapped_column(default=None)

    def __hash__(self) -> int:
        return hash(self.id)

@reg.mapped_as_dataclass
class Salary_Info:
    __tablename__ = "salary_info"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)

    player_id:Mapped[int] = mapped_column(ForeignKey("player.id"), default=None)
    player:Mapped["Player"] = relationship(default=None, back_populates="salary_info", repr=False)

    s_format:Mapped["ScoringFormat"] = mapped_column(default=None)
    
    avg_salary:Mapped[float] = mapped_column("Avg Salary", default=None)
    med_salary:Mapped[float] = mapped_column("Median Salary", default=None)
    min_salary:Mapped[float] = mapped_column("Min Salary", default=None)
    max_salary:Mapped[float] = mapped_column("Max Salary", default=None)
    last_10:Mapped[float] = mapped_column("Last 10",default=None)
    roster_percentage:Mapped[float] = mapped_column("Roster %", default=None)

@reg.mapped_as_dataclass
class PlayerValue:
    __tablename__ = "player_value"
    id:Mapped[int] = mapped_column(primary_key=True, init=False)

    player_id:Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    player:Mapped["Player"] = relationship(default=None, lazy="joined")

    position:Mapped["Position"] = mapped_column(default=None)

    calculation_id:Mapped[int] = mapped_column(ForeignKey("value_calculation.id"), default=None)
    calculation:Mapped["ValueCalculation"] = relationship(default=None, back_populates="values", repr=False)

    value:Mapped[float] = mapped_column(default=None)

    rank:int = field(repr=False, default=None)

@reg.mapped_as_dataclass
class ValueCalculation:
    __tablename__ = "value_calculation"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    name:Mapped[str] = mapped_column(default=None)
    description:Mapped[str] = mapped_column(default=None, nullable=True)
    timestamp:Mapped[datetime] = mapped_column(default=datetime.now(), nullable=False)

    projection_id:Mapped[int] = mapped_column(ForeignKey("projection.id"), default=None, nullable=True)
    projection:Mapped["Projection"] = relationship(default=None, back_populates="calculations", repr=False)
    # Corresponds to ScoringFormat enum
    s_format:Mapped["ScoringFormat"] = mapped_column(default=None)
    hitter_basis:Mapped["RankingBasis"] = mapped_column(default=None, nullable=True)
    pitcher_basis:Mapped["RankingBasis"] = mapped_column(default=None, nullable=True)

    inputs:Mapped[List["CalculationInput"]] = relationship(default_factory=list, back_populates="calculation", cascade="all, delete", lazy='joined', repr=False)
    values:Mapped[List["PlayerValue"]] = relationship(default_factory=list, back_populates="calculation", cascade="all, delete", repr=False)
    data:Mapped[List["ValueData"]] = relationship(default_factory=list, back_populates="calculation", cascade="all, delete", lazy='joined', repr=False)

    position_set_id:Mapped[int] = mapped_column(ForeignKey("position_set.id"), default=None, nullable=True)
    position_set:Mapped["PositionSet"] = relationship(default=None)

    starting_set_id:Mapped[int] = mapped_column(ForeignKey("starting_position_set.id"), default=None, nullable=True)
    starting_set:Mapped["StartingPositionSet"] = relationship(default=None)

    value_dict:Dict[int, Dict[Position, PlayerValue]] = field(default_factory=dict, repr=False)

    @reconstructor
    def init_on_load(self):
        self.value_dict = {}

    def init_value_dict(self) -> None:
        '''Initializes a dictionary that is keyed off of player_id, then off of Position with a value of the PlayerValue'''
        for pv in self.values:
            if pv.player_id not in self.value_dict:
                player_dict = {}
                self.value_dict[pv.player_id] = player_dict
            player_dict = self.value_dict[pv.player_id]
            player_dict[pv.position] = pv

    def set_input(self, data_type:CalculationDataType, value:object) -> None:
        '''Sets the CalculationInput. Sanitizes so that the value is always a float. Adds it to the ValueCalculation.inputs list if it doesn't exist, otherwise updates
        the existing value.'''
        if value == '--':
            value = -999
        if isinstance(value, str):
            value = float(value)
        for inp in self.inputs:
            if inp.data_type == data_type:
                inp.value = value
                return
        ci = CalculationInput()
        ci.data_type = data_type
        ci.value = value
        self.inputs.append(ci)

    def get_input(self, data_type:CalculationDataType, default:float=None) -> float:
        '''Gets the value for the given data type. Returns the default if None exists in the calculation.'''
        for inp in self.inputs:
            if inp.data_type == data_type:
                return inp.value
        return default
    
    def set_output(self, data_type:CalculationDataType, value:object):
        '''Sets the ValueData. Sanitizes so that the value is always a float. Adds it to the ValueCalculation.data list if it doesn't exist, otherwise updates
        the existing value.'''
        if value == '--':
            value = -999
        if isinstance(value, str):
            value = float(value)
        for data in self.data:
            if data.data_type == data_type:
                data.value = value
                return
        vd = ValueData()
        vd.data_type = data_type
        vd.value = value
        self.data.append(vd)

    def get_output(self, data_type:CalculationDataType, default=None) -> ValueData:
        '''Gets the ValueData for the given data type. Returns the default if None exists in the calculation.'''
        for data in self.data:
            if data.data_type == data_type:
                return data.value
        return default
    
    def set_player_value(self, player_id:int, pos:Position, value:float) -> None:
        '''Sets the value of the given player at the given position. If the player/position combination doesn't exist, adds it to the ValueCalculation.values list.
        Otherwise updates the existing value.'''
        for pv in self.values:
            if pv.player_id == player_id and pv.position == pos:
                pv.value = value
                return
        pv = PlayerValue(player_id=player_id)
        #pv.player_id = player_id
        pv.position = pos
        pv.value = value
        self.values.append(pv)

        if player_id not in self.value_dict:
            player_dict = {}
            self.value_dict[player_id] = player_dict
        player_dict = self.value_dict[player_id]
        player_dict[pos] = pv
    
    def get_player_value(self, player_id:int, pos=None) -> PlayerValue:
        '''Gets the PlayerValue for the given player_id and position.'''
        if player_id not in self.value_dict:
            if pos is None:
                return {}
            return None
        if pos is None:
            #Get all positions
            return self.value_dict[player_id]
        else:
            return self.value_dict[player_id].get(pos, None)
    
    def get_position_values(self, pos:Position) -> list[PlayerValue]:
        '''Gets all player values at the given position.'''
        values = []
        for pv in self.values:
            if pv.position == pos:
                values.append(pv)
        return values

    def get_rep_level_map(self) -> List[Dict[Position, float]]:
        '''Returns the output replacement level values for the ValueCalclution with position as the key'''
        rl_map = {}
        for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
            rl_map[pos] = self.get_output(CalculationDataType.pos_to_rep_level().get(pos))
        rl_map[Position.POS_MI] = min(rl_map[Position.POS_2B], rl_map[Position.POS_SS])
        return rl_map

@reg.mapped_as_dataclass
class CustomScoring:

    __tablename__ = "custom_scoring"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    name:Mapped[str] = mapped_column(default=None)
    description:Mapped[str] = mapped_column(default=None)
    points_format:Mapped[bool] = mapped_column(default=False)
    head_to_head:Mapped[bool] = mapped_column(default=False)

    stats:Mapped[List["CustomScoringCategory"]] = relationship(default_factory=list, cascade="all, delete", repr=False, lazy="joined")

@reg.mapped_as_dataclass
class CustomScoringCategory:

    __tablename__ = "custom_scoring_categories"

    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    category:Mapped[StatType] = mapped_column(default=None)
    points:Mapped[float] = mapped_column(default=0)
    
    scoring_set_id:Mapped[int] = mapped_column(ForeignKey("custom_scoring.id"), default=None)
    scoring_set:Mapped["CustomScoring"] = relationship(default=None, back_populates="stats", repr=False)

@reg.mapped_as_dataclass
class CalculationInput:

    __tablename__ = "calculation_input"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)

    data_type:Mapped["CalculationDataType"] = mapped_column(default=None, nullable=False)

    value:Mapped[float] = mapped_column(default=None, nullable=False)

    calculation_id:Mapped[int] = mapped_column(ForeignKey("value_calculation.id"), default=None)
    calculation:Mapped["ValueCalculation"] = relationship(default=None, back_populates="inputs", repr=False)

@reg.mapped_as_dataclass
class ValueData:
    __tablename__ = "value_data"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)

    data_type:Mapped["CalculationDataType"] = mapped_column(default=None, nullable=False)

    value:Mapped[float] = mapped_column(default=None, nullable=False)

    calculation_id:Mapped[int] = mapped_column(ForeignKey("value_calculation.id"), default=None)
    calculation:Mapped["ValueCalculation"] = relationship(default=None, back_populates="data", repr=False)

@reg.mapped_as_dataclass   
class Projection:
    __tablename__ = "projection"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    
    # This corresponds to the ProjectionType enum
    type:Mapped[ProjectionType] = mapped_column(default=None, nullable=False)
    #type = ProjectionType.STEAMER
    timestamp:Mapped[datetime] = mapped_column(default=datetime.now(), nullable=False)
    name:Mapped[str] = mapped_column(default=None, nullable=False)
    detail:Mapped[str] = mapped_column(default=None, nullable=True)
    season:Mapped[int] = mapped_column(default=None, nullable=False)

    ros:Mapped[bool] = mapped_column(default=False, nullable=False)
    dc_pt:Mapped[bool] = mapped_column(default=False, nullable=False)
    hide:Mapped[bool] = mapped_column(default=False, nullable=False)

    valid_points:Mapped[bool] = mapped_column(default=False, nullable=False)
    valid_5x5:Mapped[bool] = mapped_column(default=False, nullable=False)
    valid_4x4:Mapped[bool] = mapped_column(default=False, nullable=False)

    player_projections:Mapped[List["PlayerProjection"]] = relationship(default_factory=list, back_populates="projection", cascade="all, delete", repr=False)
    calculations:Mapped[List["ValueCalculation"]] = relationship(default_factory=list, back_populates="projection", cascade="all, delete", repr=False)

    def get_player_projection(self, player_id:int, idx:str=None, id_type:IdType=IdType.FANGRAPHS) -> PlayerProjection:
        '''Gets the PlayerProjection for the given player_id'''
        if player_id is None:
            if idx is None:
                return None
            for pp in self.player_projections:
                if id_type == IdType.FANGRAPHS:
                    if idx.isnumeric():
                        if pp.player.fg_major_id == idx:
                            print('returning pp')
                            return pp
                    else:
                        if pp.player.fg_minor_id == idx:
                            return pp
                else:
                    for pp in self.player_projections:
                        if pp.player.ottoneu_id == idx:
                            return pp
        else:
            for pp in self.player_projections:
                if pp.player_id == player_id or pp.player.id == player_id:
                    return pp
        return None

@reg.mapped_as_dataclass   
class PlayerProjection:
    __tablename__ = "player_projection"
    id:Mapped[int] = mapped_column(init=False, primary_key=True)

    player_id:Mapped[int] = mapped_column(ForeignKey("player.id"), default=None, nullable=False)
    player:Mapped["Player"] = relationship(default=None, lazy="joined")

    projection_id:Mapped[int] = mapped_column(ForeignKey("projection.id"), default=None)
    projection:Mapped["Projection"] = relationship(default=None, back_populates="player_projections", repr=False)

    projection_data:Mapped[dict[StatType, float]] = mapped_column(JSON(), default_factory=dict, repr=False)

    pitcher:Mapped[bool] = mapped_column(default=False)
    two_way:Mapped[bool] = mapped_column(default=False)

    def get_stat(self, stat_type:StatType) -> float:
        '''Gets the stat value associated with the input StatType'''
        return self.projection_data.get(stat_type, None)

@reg.mapped_as_dataclass
class Salary_Refresh:
    '''Class to track how recently the Ottoverse average values have been refreshed'''
    __tablename__ = "salary_refresh"
    s_format:Mapped["ScoringFormat"] = mapped_column(default=ScoringFormat.ALL, primary_key=True)
    last_refresh:Mapped[datetime] = mapped_column(default=datetime.now(), nullable=False)

@reg.mapped_as_dataclass
class Draft:
    '''Class to hold user draft inputs'''
    __tablename__ = 'draft'
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    league_id:Mapped[int] = mapped_column(ForeignKey("league.id"), default=None)
    league:Mapped["League"] = relationship(default=None, repr=False)

    targets:Mapped[List["Draft_Target"]] = relationship(default_factory=list, cascade="all, delete", lazy="joined", repr=False)
    #targets:Mapped[List["Draft_Target"]] = relationship(default_factory=list, back_populates='draft', cascade="all, delete", lazy="joined")
    cm_draft:Mapped["CouchManagers_Draft"] = relationship(default=None, uselist=False, back_populates='draft', cascade="all, delete", lazy="joined", repr=False)

    year:Mapped[int] = mapped_column(nullable=False, default=None)

    team_drafts:Mapped[List[TeamDraft]] = relationship(default_factory=list, cascade="all, delete", lazy="joined", repr=False)

    def get_target_by_player(self, player_id:int) -> Draft_Target:
        '''Gets the Draft_Target for the input player_id. If none exists, return None'''
        if self.targets is not None:
            for target in self.targets:
                if target.player.id == player_id:
                    return target
        return None

    def set_target(self, player_id:int, price=None) -> None:
        '''Sets the Draft_Target for the given player_id and price. If a target exists for the input player, the price is updated. Otherwise a new target is created
        and added to the Draft.targets list.'''
        target = self.get_target_by_player(player_id)
        if target is None:
            target = Draft_Target()
            target.player_id = player_id
            self.targets.append(target)
        target.price = price

@reg.mapped_as_dataclass
class Draft_Target:
    '''Class to hold user draft target information'''
    __tablename__ = 'draft_target'
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    draft_id:Mapped[int] = mapped_column(ForeignKey("draft.id"), default=None, nullable=False)
    #draft:Mapped["Draft"] = relationship(default=None, back_populates='targets')

    player_id:Mapped[int] = mapped_column(ForeignKey("player.id"), default=None, nullable=False)
    player:Mapped["Player"] = relationship(default=None, lazy="joined")

    price:Mapped[int] = mapped_column(default=None, nullable=True)

@reg.mapped_as_dataclass
class CouchManagers_Draft:
    '''Class to hold CouchManagers Draft Data'''
    __tablename__ = 'cm_draft'
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    cm_draft_id:Mapped[int] = mapped_column(default=None, nullable=False)
    draft_id:Mapped[int] = mapped_column(ForeignKey("draft.id"), default=None, nullable=False)
    draft:Mapped["Draft"] = relationship(default=None, back_populates='cm_draft', repr=False)
    setup:Mapped[bool] = mapped_column(default=False)

    teams:Mapped[List["CouchManagers_Team"]] = relationship(default_factory=list, back_populates="cm_draft", cascade="all, delete", lazy="joined", repr=False)

    def get_toolbox_team_id_by_cm_team_id(self, cm_team_id:int) -> int:
        '''Gets the linked Ottoneu Toolbox Team id associated with the input CouchManagers team id'''
        for team in self.teams:
            if team.cm_team_id == cm_team_id:
                return team.ottoneu_team_id
        return 0

@reg.mapped_as_dataclass
class CouchManagers_Team:
    '''Class that maps CouchManagers draft team numbers'''
    __tablename__ = 'cm_teams'
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    cm_draft_id:Mapped[int] = mapped_column(ForeignKey("cm_draft.id"), default=None, nullable=False)
    cm_draft:Mapped["CouchManagers_Draft"] = relationship(default=None, back_populates='teams', repr=False)

    cm_team_id:Mapped[int] = mapped_column(nullable=False, default=None)
    cm_team_name:Mapped[str] = mapped_column(default=None, nullable=True)
    ottoneu_team_id:Mapped[int] = mapped_column(nullable=False, default=None)

    def __hash__(self) -> int:
        return hash(self.id)

@reg.mapped_as_dataclass
class Adv_Calc_Option:
    '''Class to hold advanced calculation inputs'''
    __tablename__ = 'adv_calc_option'
    id:Mapped["CalculationDataType"] = mapped_column(default=None, primary_key=True)
    value:Mapped[float] = mapped_column(default=None)

@reg.mapped_as_dataclass
class PositionSet:
    '''Class to hold non-Ottoneu or custom positional information for players'''
    __tablename__ = 'position_set'
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    name:Mapped[str] = mapped_column(default='')
    detail:Mapped[str] = mapped_column(default='', nullable=True)

    positions:Mapped[List["PlayerPositions"]] = relationship(default_factory=list, back_populates='position_set', repr=False, lazy='joined')

    def get_player_positions(self, player_id:int) -> str:
        '''Gets the position string for the player'''
        for pp in self.positions:
            if pp.player_id == player_id:
                return pp.position
        return None

@reg.mapped_as_dataclass
class PlayerPositions:
    __tablename__ = 'player_positions'
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    
    player_id:Mapped[int] = mapped_column(ForeignKey("player.id"), default=None)

    position_set_id:Mapped[int] = mapped_column(ForeignKey("position_set.id"), default=None)
    position_set:Mapped["PositionSet"] = relationship(default=None, cascade="all, delete")

    position:Mapped[str] = mapped_column(default='')

@reg.mapped_as_dataclass
class StartingPositionSet:
    __tablename__ = 'starting_position_set'
    id:Mapped[int] = mapped_column(init=False, primary_key=True)

    name:Mapped[str] = mapped_column(default='')
    detail:Mapped[str] = mapped_column(default='', nullable=True)

    positions:Mapped[List["StartingPosition"]] = relationship(default_factory=list, back_populates='starting_position_set', repr=False, lazy='joined')

    def get_count_for_position(self, pos:Position) -> int:
        '''Gets the number of starting spots for the position'''
        for sp in self.positions:
            if sp.position == pos:
                return sp.count
        return 0
    
    def get_base_positions(self, include_util=False) -> List[Position]:
        '''Returns the list of base positions for the starting set. Will include the Util position if include_util is true.'''
        positions = [pos.position for pos in self.positions]
        return [pos for pos in positions if Position.position_is_base(pos, positions) or (include_util and pos == Position.POS_UTIL)]

@reg.mapped_as_dataclass
class StartingPosition:
    __tablename__ = 'starting_position'
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    
    position:Mapped[Position] = mapped_column(default=None)
    count:Mapped[int] = mapped_column(default=1)

    starting_position_set_id:Mapped[int] = mapped_column(ForeignKey("starting_position_set.id"), default=None)
    starting_position_set:Mapped["StartingPositionSet"] = relationship(default=None, cascade="all, delete")

@reg.mapped_as_dataclass
class TeamDraft:
    __tablename__ = 'team_draft'
    id:Mapped[int] = mapped_column(init=False, primary_key=True)
    team_id:Mapped[int] = mapped_column(ForeignKey("team.id"), default=None, nullable=False)

    draft_id:Mapped[int] = mapped_column(ForeignKey("draft.id"), default=None, nullable=False)

    custom_draft_budget:Mapped[int] = mapped_column(default=None, nullable=True)