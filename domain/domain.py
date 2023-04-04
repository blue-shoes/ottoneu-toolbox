from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import Integer, String, Boolean, Float, Date, Enum, TIMESTAMP

from sqlalchemy.orm import relationship, reconstructor, registry
import re
from domain.enum import CalculationDataType, ProjectionType, RankingBasis, ScoringFormat, StatType, Position, IdType
from typing import List, Dict

mapper_registry = registry()

@mapper_registry.mapped
@dataclass
class Property:
    __tablename__ = "properties"
    __sa_dataclass_metadata_key__ = "sa"
    name:str = field(default=None, metadata={"sa": Column(String, primary_key=True)})
    value:str = field(default=None, metadata={"sa":Column(String)})

@mapper_registry.mapped
@dataclass
class Player:
    __tablename__ = "player"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})
    ottoneu_id:int = field(default=None, metadata={"sa":Column('Ottoneu ID', Integer, index=True)})
    fg_major_id:str = field(default=None, metadata={"sa":Column('FG MajorLeagueID', String)}, repr=False)
    fg_minor_id:str = field(default=None, metadata={"sa":Column('FG MinorLeagueID', String)}, repr=False)
    name:str = field(default=None, metadata={"sa":Column("Name",String)})
    search_name:str = field(default=None, metadata={"sa":Column(String)}, repr=False)
    team:str = field(default=None, metadata={"sa":Column("Org",String(7))})
    position:str = field(default=None, metadata={"sa":Column("Position(s)",String)})

    roster_spots:List[Roster_Spot] = field(default_factory=list, metadata={"sa":relationship("Roster_Spot", back_populates="player", cascade="all, delete")}, repr=False)
    salary_info:List[Salary_Info] = field(default_factory=list, metadata={"sa":relationship("Salary_Info", back_populates="player", cascade="all, delete", lazy="joined")}, repr=False)
    values:List[PlayerValue] = field(default_factory=list, metadata={"sa":relationship("PlayerValue", back_populates="player", cascade="all, delete")}, repr=False)
    projections:List[PlayerProjection] = field(default_factory=list, metadata={"sa":relationship("PlayerProjection", back_populates="player", cascade="all, delete")}, repr=False)

    __table_args__ = (Index('idx_fg_id','FG MajorLeagueID','FG MinorLeagueID'),)

    def __hash__(self) -> int:
        return hash(self.index)

    def get_fg_id(self) -> object:
        '''Returns the FanGraphs Major League id, if available, otherwise returns the FanGraphs Minor League id.'''
        if self.fg_major_id != None:
            return self.fg_major_id
        else:
            return self.fg_minor_id
    
    def pos_eligible(self, pos: Position) -> bool:
        '''Returns if the Player is eligible at the input Position.'''
        if pos == Position.OVERALL:
            return True
        elif pos == Position.OFFENSE or pos == Position.POS_UTIL:
            for p in Position.get_discrete_offensive_pos():
                if p.value in self.position:
                    return True
            return False
        elif pos == Position.POS_MI:
            return bool(re.search('2B|SS', self.position))
        elif pos == Position.PITCHER:
            for p in Position.get_discrete_pitching_pos():
                if p.value in self.position:
                    return True
            return False
        return pos.value in self.position
    
    def is_two_way(self) -> bool:
        '''Returns if the player is eligible at both hitting and pitching positions.'''
        hit = False
        pitch = False
        for pos in Position.get_discrete_offensive_pos():
            if pos.value in self.position:
                hit = True
                continue
        for pos in Position.get_discrete_pitching_pos():
            if pos.value in self.position:
                pitch = True
        return hit and pitch
    
    def get_salary_info_for_format(self, format=ScoringFormat.ALL) -> Salary_Info:
        '''Gets the Player's Salary_Info for the input ScoringFormat'''
        for si in self.salary_info:
            if si.format == format:
                return si
        si = Salary_Info()
        si.format = format
        si.avg_salary = 0.0
        si.last_10 = 0.0
        si.max_salary = 0.0
        si.min_salary = 0.0
        si.med_salary = 0.0
        si.roster_percentage = 0.0
        return si

@mapper_registry.mapped
@dataclass
class League:
    __tablename__ = "league"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})
    ottoneu_id:int = field(default=None, metadata={"sa":Column(Integer, nullable=False)})
    name:str = field(default=None, metadata={"sa":Column(String)})
  
    format:ScoringFormat = field(default=None, metadata={"sa":Column(Enum(ScoringFormat), nullable=False)})
    num_teams:int = field(default=None, metadata={"sa":Column(Integer, nullable=False)})
    last_refresh:datetime = field(default=None, metadata={"sa":Column(TIMESTAMP, nullable=False)})
    active:bool = field(default=True, metadata={"sa":Column(Boolean, nullable = False)})

    teams = relationship("Team", back_populates="league", cascade="all, delete")

    def get_user_team(self):
        '''Returns the user\'s team for the league. None if no team is specified'''
        for team in self.teams:
            if team.users_team:
                return team
        return None
    
    def get_team_by_index(self, team_id:int) -> Team:
        '''Returns the team from the league by OTB index'''
        for team in self.teams:
            if team.index == team_id:
                return team
        return None

    def get_team_by_site_id(self, site_id:int) -> Team:
        '''Returns the team from the league by site Id'''
        for team in self.teams:
            if team.site_id == site_id:
                return team
        return None

@mapper_registry.mapped
@dataclass
class Team:
    __tablename__ = "team"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})
    site_id:int = field(default=None, metadata={"sa":Column(Integer, nullable=False)})

    league_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("league.index"))})
    league:League = field(default=None, metadata={"sa":relationship("League", back_populates="teams")})

    name:str = field(default=None, metadata={"sa":Column(String)})
    users_team:bool = field(default=False, metadata={"sa":Column(Boolean)})
    
    roster_spots:List[Roster_Spot] = field(default_factory=list, metadata={"sa":relationship("Roster_Spot", back_populates="team", cascade="all, delete")}, repr=False)

    num_players:int = field(default=None, metadata={"sa":Column(Integer)})
    spots:int = field(default=None, metadata={"sa":Column(Integer)})
    salaries:int = field(default=None, metadata={"sa":Column(Integer)})
    penalties:int = field(default=None, metadata={"sa":Column(Integer)})
    loans_in:int = field(default=None, metadata={"sa":Column(Integer)})
    loans_out:int = field(default=None, metadata={"sa":Column(Integer)})
    free_cap:int = field(default=None, metadata={"sa":Column(Integer)})

    rs_map:Dict[Player,Roster_Spot] = None
    points:float=0
    lg_rank:int=0
    cat_stats:Dict[StatType,float]=None
    cat_ranks:Dict[StatType,int]=None

    @reconstructor
    def init_on_load(self):
        self.cat_stats = {}
        self.cat_ranks = {}

    def get_rs_by_player(self, player:Player) -> Roster_Spot:
        '''Returns the team's Roster_Spot for the input player'''
        if player is None:
            return None
        return self.get_rs_by_player_id(player.index)

    def get_rs_by_player_id(self, player_id:int) -> Roster_Spot:
        '''Returns the team's Roster_Spot for the input player id'''
        if self.rs_map is None:
            for rs in self.roster_spots:
                if rs.player.index == player_id:
                    return rs
            return None
        else:
            return self.rs_map.get(player_id, None)

    def index_rs(self) -> None:
        self.rs_map = {}
        for rs in self.roster_spots:
            self.rs_map[rs.player.index] = rs

@mapper_registry.mapped
@dataclass
class Roster_Spot:
    __tablename__ = "roster_spot"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})

    team_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("team.index"))})
    team:Team = field(default=None, metadata={"sa":relationship("Team", back_populates="roster_spots")})

    player_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("player.index"))})
    player:Player = field(default=None, metadata={"sa":relationship("Player", back_populates="roster_spots")})

    salary:int = field(default=None, metadata={"sa":Column(Integer)})

    g_h:int = 0
    ip:int = 0

@mapper_registry.mapped
@dataclass
class Salary_Info:
    __tablename__ = "salary_info"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})

    player_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("player.index"))})
    player:Player = field(default=None, metadata={"sa":relationship("Player", back_populates="salary_info")})

    format:ScoringFormat = field(default=None, metadata={"sa":Column(Enum(ScoringFormat))})
    
    avg_salary:float = field(default=None, metadata={"sa":Column("Avg Salary",Float)})
    med_salary:float = field(default=None, metadata={"sa":Column("Median Salary",Float)})
    min_salary:float = field(default=None, metadata={"sa":Column("Min Salary",Float)})
    max_salary:float = field(default=None, metadata={"sa":Column("Max Salary",Float)})
    last_10:float = field(default=None, metadata={"sa":Column("Last 10",Float)})
    roster_percentage:float = field(default=None, metadata={"sa":Column("Roster %",Float)})

@mapper_registry.mapped
@dataclass
class PlayerValue:
    __tablename__ = "player_value"
    __sa_dataclass_metadata_key__ = "sa"
    index = Column(Integer, primary_key=True)

    player_id:int = field(init=False, metadata={"sa":Column(Integer, ForeignKey("player.index"))})
    player:Player = field(default=None, metadata={"sa":relationship("Player", back_populates="values", lazy="joined")})

    position:Position = field(default=None, metadata={"sa":Column(Enum(Position))})

    calculation_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("value_calculation.index"))})
    calculation:ValueCalculation = field(default=None, metadata={"sa":relationship("ValueCalculation", back_populates="values")}, repr=False)

    value:float = Column(Float)

@mapper_registry.mapped
@dataclass
class ValueCalculation:
    __tablename__ = "value_calculation"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})
    name:str = field(default=None, metadata={"sa":Column(String)})
    description:str = field(default=None,metadata={"sa":Column(String)})
    timestamp:datetime = field(default=datetime.now(), metadata={"sa":Column(Date, nullable=False)})

    projection_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("projection.index"))})
    projection:Projection = field(default=None, metadata={"sa":relationship("Projection", back_populates="calculations")})
    # Corresponds to ScoringFormat enum
    format:ScoringFormat = field(default=None, metadata={"sa":Column(Enum(ScoringFormat))})
    hitter_basis:RankingBasis = field(default=None, metadata={"sa":Column(Enum(RankingBasis))})
    pitcher_basis:RankingBasis = field(default=None, metadata={"sa":Column(Enum(RankingBasis))})

    inputs:List[CalculationInput] = field(default_factory=list, metadata={"sa":relationship("CalculationInput", back_populates="calculation", cascade="all, delete", lazy='joined')}, repr=False)
    values:List[PlayerValue] = field(default_factory=list, metadata={"sa":relationship("PlayerValue", back_populates="calculation", cascade="all, delete")}, repr=False)
    data:List[ValueData] = field(default_factory=list, metadata={"sa":relationship("ValueData", back_populates="calculation", cascade="all, delete", lazy='joined')}, repr=False)

    value_dict = {}

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
        pv = PlayerValue()
        pv.player_id = player_id
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

    def get_rep_level_map(self) -> List[Dict[Position, Float]]:
        '''Returns the output replacement level values for the ValueCalclution with position as the key'''
        rl_map = {}
        for pos in Position.get_discrete_offensive_pos() + Position.get_discrete_pitching_pos():
            rl_map[pos] = self.get_output(CalculationDataType.pos_to_rep_level().get(pos))
        rl_map[Position.POS_MI] = min(rl_map[Position.POS_2B], rl_map[Position.POS_SS])
        return rl_map

@mapper_registry.mapped
@dataclass
class CalculationInput:

    __tablename__ = "calculation_input"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})

    data_type:CalculationDataType = field(default=None, metadata={"sa":Column(Enum(CalculationDataType), nullable=False)})

    value:float = field(default=None, metadata={"sa":Column(Float, nullable=False)})

    calculation_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("value_calculation.index"))})
    calculation:ValueCalculation = field(default=None, metadata={"sa":relationship("ValueCalculation", back_populates="inputs")}, repr=False)

@mapper_registry.mapped
@dataclass
class ValueData:
    __tablename__ = "value_data"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})

    data_type:CalculationDataType = field(default=None, metadata={"sa":Column(Enum(CalculationDataType), nullable=False)})

    value:float = field(default=None, metadata={"sa":Column(Float, nullable=False)})

    calculation_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("value_calculation.index"))})
    calculation:ValueCalculation = field(default=None, metadata={"sa":relationship("ValueCalculation", back_populates="data")}, repr=False)

@mapper_registry.mapped
@dataclass    
class Projection:
    __tablename__ = "projection"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})
    
    # This corresponds to the ProjectionType enum
    type:ProjectionType = field(default=None, metadata={"sa":Column(Enum(ProjectionType))})
    timestamp:datetime = field(default=datetime.now(), metadata={"sa":Column(Date, nullable=False)})
    name:str = field(default=None, metadata={"sa":Column(String, nullable=False)})
    detail:str = field(default=None, metadata={"sa":Column(String)})
    season:int = field(default=None, metadata={"sa":Column(Integer, nullable=False)})

    ros:bool = field(default=False, metadata={"sa":Column(Boolean, nullable=False)})
    dc_pt:bool = field(default=False, metadata={"sa":Column(Boolean, nullable=False)})
    hide:bool = field(default=False, metadata={"sa":Column(Boolean, nullable=False)})

    valid_points:bool = field(default=False, metadata={"sa":Column(Boolean, nullable=False)})
    valid_5x5:bool = field(default=False, metadata={"sa":Column(Boolean, nullable=False)})
    valid_4x4:bool = field(default=False, metadata={"sa":Column(Boolean, nullable=False)})

    player_projections:List[PlayerProjection] = field(default_factory=list, metadata={"sa":relationship("PlayerProjection", back_populates="projection", cascade="all, delete")}, repr=False)
    calculations:List[ValueCalculation] = field(default_factory=list, metadata={"sa":relationship("ValueCalculation", back_populates="projection", cascade="all, delete")}, repr=False)

    def get_player_projection(self, player_id:int, idx:str=None, id_type:IdType=IdType.FANGRAPHS) -> PlayerProjection:
        '''Gets the PlayerProjection for the given player_id'''
        if player_id is None:
            for pp in self.player_projections:
                if id_type == IdType.FANGRAPHS:
                    if idx.isnumeric():
                        for pp in self.player_projections:
                            if pp.player.fg_major_id == idx:
                                return pp
                    else:
                        for pp in self.player_projections:
                            if pp.player.fg_minor_id == idx:
                                return pp
                else:
                    for pp in self.player_projections:
                        if pp.player.ottoneu_id == idx:
                            return pp
        else:
            for pp in self.player_projections:
                if pp.player_id == player_id or pp.player.index == player_id:
                    return pp
        return None

@mapper_registry.mapped
@dataclass        
class PlayerProjection:
    __tablename__ = "player_projection"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})

    player_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("player.index"))})
    player:Player = field(default=None, metadata={"sa":relationship("Player", back_populates="projections", lazy="joined")})

    projection_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("projection.index"))})
    projection:Projection = field(default=None, metadata={"sa":relationship("Projection", back_populates="player_projections")}, repr=False)

    projection_data:List[ProjectionData] = field(default_factory=list, metadata={"sa":relationship("ProjectionData", back_populates="player_projection", cascade="all, delete", lazy="joined")}, repr=False)

    pitcher:bool = field(default=False, metadata={"sa":Column(Boolean)})
    two_way:bool = field(default=False, metadata={"sa":Column(Boolean)})

    def get_stat(self, stat_type:StatType) -> float:
        '''Gets the stat value associated with the input StatType'''
        pd = self.get_projection_data(stat_type)
        if pd is None:
            return None
        return pd.stat_value

    def get_projection_data(self, stat_type:StatType) -> ProjectionData:
        '''Gets the ProjectionData object associated with the input StatType'''
        for pd in self.projection_data:
            if pd.stat_type == stat_type:
                return pd
        return None

@mapper_registry.mapped
@dataclass
class ProjectionData:
    __tablename__ = "projection_data"
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})

    player_projection_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("player_projection.index"))})
    player_projection:PlayerProjection = field(default=None, metadata={"sa":relationship("PlayerProjection", back_populates="projection_data")}, repr=False)

    stat_type:StatType = field(default=None, metadata={"sa":Column(Enum(StatType), nullable=False) })
    stat_value:float = field(default=None, metadata={"sa":Column(Float, nullable=False)})

@mapper_registry.mapped
@dataclass
class Salary_Refresh:
    '''Class to track how recently the Ottoverse average values have been refreshed'''
    __tablename__ = "salary_refresh"
    __sa_dataclass_metadata_key__ = "sa"
    format:ScoringFormat = field(default=ScoringFormat.ALL, metadata={"sa":Column(Enum(ScoringFormat), primary_key=True)})
    last_refresh:datetime = field(default=datetime.now(), metadata={"sa":Column(TIMESTAMP, nullable=False)})

@mapper_registry.mapped
@dataclass
class Draft:
    '''Class to hold user draft inputs'''
    __tablename__ = 'draft'
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False,metadata={"sa":Column(Integer, primary_key=True)})
    league_id:int = field(default=None,metadata={"sa":Column(Integer, ForeignKey("league.index"))})
    league:League = field(default=None, metadata={"sa":relationship("League")}, repr=False)

    targets:List[Draft_Target] = field(default_factory=list, metadata={"sa":relationship("Draft_Target", back_populates="draft", cascade="all, delete", lazy="joined")}, repr=False)
    cm_draft:CouchManagers_Draft = field(default=None, metadata={"sa":relationship("CouchManagers_Draft", uselist=False, back_populates='draft', cascade="all, delete", lazy="joined")}, repr=False)

    year = Column(Integer, nullable=False)

    def get_target_by_player(self, player_id:int) -> Draft_Target:
        '''Gets the Draft_Target for the input player_id. If none exists, return None'''
        if self.targets is not None:
            for target in self.targets:
                if target.player.index == player_id:
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

@mapper_registry.mapped
@dataclass
class Draft_Target:
    '''Class to hold user draft target information'''
    __tablename__ = 'draft_target'
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})
    draft_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("draft.index"), nullable=False)})
    draft:Draft = field(default=None, metadata={"sa":relationship("Draft", back_populates='targets')}, repr=False)

    player_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("player.index"), nullable=False)})
    player:Player = field(default=None, metadata={"sa":relationship("Player", lazy="joined")})

    price:int = field(default=None, metadata={"sa":Column(Integer, nullable=True)})

@mapper_registry.mapped
@dataclass
class CouchManagers_Draft:
    '''Class to hold CouchManagers Draft Data'''
    __tablename__ = 'cm_draft'
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})
    cm_draft_id:int = field(default=None, metadata={"sa":Column(Integer, nullable=False)})
    draft_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("draft.index"), nullable=False)})
    draft:Draft = field(default=None, metadata={"sa":relationship("Draft", back_populates='cm_draft')}, repr=False)
    setup = Column(Boolean)

    teams:List[CouchManagers_Team] = field(default_factory=list, metadata={"sa":relationship("CouchManagers_Team", back_populates="cm_draft", cascade="all, delete", lazy="joined")}, repr=False)

    def get_toolbox_team_index_by_cm_team_id(self, cm_team_id:int) -> int:
        '''Gets the linked Ottoneu Toolbox Team index associated with the input CouchManagers team id'''
        for team in self.teams:
            if team.cm_team_id == cm_team_id:
                return team.ottoneu_team_id
        return 0

@mapper_registry.mapped
@dataclass
class CouchManagers_Team:
    '''Class that maps CouchManagers draft team numbers'''
    __tablename__ = 'cm_teams'
    __sa_dataclass_metadata_key__ = "sa"
    index:int = field(init=False, metadata={"sa":Column(Integer, primary_key=True)})
    cm_draft_id:int = field(default=None, metadata={"sa":Column(Integer, ForeignKey("cm_draft.index"), nullable=False)})
    cm_draft:CouchManagers_Draft = field(default=None, metadata={"sa":relationship("CouchManagers_Draft", back_populates='teams')}, repr=False)

    cm_team_id = Column(Integer, nullable=False)
    cm_team_name = Column(String)
    ottoneu_team_id = Column(Integer, nullable=False)

@mapper_registry.mapped
@dataclass
class Adv_Calc_Option:
    '''Class to hold advanced calculation inputs'''
    __tablename__ = 'adv_calc_option'
    __sa_dataclass_metadata_key__ = "sa"
    index:CalculationDataType = field(default=None, metadata={"sa":Column(Enum(CalculationDataType), primary_key=True)})
    value:float = field(default=None, metadata={"sa":Column(Float)})