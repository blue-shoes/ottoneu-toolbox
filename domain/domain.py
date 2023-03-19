from __future__ import annotations
from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import Integer, String, Boolean, Float, Date, Enum, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import re
from domain.enum import CalculationDataType, ProjectionType, RankingBasis, ScoringFormat, StatType, Position, IdType

from typing import List, Dict

Base = declarative_base()

class Property(Base):
    __tablename__ = "properties"
    name = Column(String, primary_key=True)
    value = Column(String)

class Player(Base):
    __tablename__ = "player"
    index = Column(Integer, primary_key=True)
    ottoneu_id = Column('Ottoneu ID', Integer, index=True)
    fg_major_id = Column('FG MajorLeagueID', String)
    fg_minor_id = Column('FG MinorLeagueID', String)
    name = Column("Name",String)
    search_name = Column(String)
    team = Column("Org",String(7))
    position = Column("Position(s)",String)

    roster_spots = relationship("Roster_Spot", back_populates="player", cascade="all, delete")
    salary_info = relationship("Salary_Info", back_populates="player", cascade="all, delete", lazy="joined")
    values = relationship("PlayerValue", back_populates="player", cascade="all, delete")
    projections = relationship("PlayerProjection", back_populates="player", cascade="all, delete")

    __table_args__ = (Index('idx_fg_id','FG MajorLeagueID','FG MinorLeagueID'),)

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

class League(Base):
    __tablename__ = "league"
    index = Column(Integer, primary_key=True)
    ottoneu_id = Column(Integer, nullable=False)
    name = Column(String)
    # Corresponds to ScoringFormat enum
    format = Column(Enum(ScoringFormat), nullable=False)
    num_teams = Column(Integer, nullable=False)
    last_refresh = Column(TIMESTAMP, nullable=False)
    active = Column(Boolean, nullable = False)

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

class Team(Base):
    __tablename__ = "team"
    index = Column(Integer, primary_key=True)
    site_id = Column(Integer, nullable=False)

    league_id = Column(Integer, ForeignKey("league.index"))
    league = relationship("League", back_populates="teams")

    name = Column(String)
    users_team = Column(Boolean)
    
    roster_spots = relationship("Roster_Spot", back_populates="team", cascade="all, delete")

    num_players = Column(Integer)
    spots = Column(Integer)
    salaries = Column(Integer)
    penalties = Column(Integer)
    loans_in = Column(Integer)
    loans_out = Column(Integer)
    free_cap = Column(Integer)

    rs_map:Dict[Player,Roster_Spot] = None
    points:float=0
    

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

class Roster_Spot(Base):
    __tablename__ = "roster_spot"
    index = Column(Integer, primary_key=True)

    team_id = Column(Integer, ForeignKey("team.index"))
    team = relationship("Team", back_populates="roster_spots")

    player_id = Column(Integer, ForeignKey("player.index"))
    player = relationship("Player", back_populates="roster_spots")

    salary = Column(Integer)

    g_h:int = 0
    ip:int = 0

class Salary_Info(Base):
    __tablename__ = "salary_info"
    index = Column(Integer, primary_key=True)

    player_id = Column(Integer, ForeignKey("player.index"))
    player = relationship("Player", back_populates="salary_info")

    format = Column(Enum(ScoringFormat))
    
    avg_salary = Column("Avg Salary",Float)
    med_salary = Column("Median Salary",Float)
    min_salary = Column("Min Salary",Float)
    max_salary = Column("Max Salary",Float)
    last_10 = Column("Last 10",Float)
    roster_percentage = Column("Roster %",Float)

class PlayerValue(Base):
    __tablename__ = "player_value"
    index = Column(Integer, primary_key=True)

    player_id = Column(Integer, ForeignKey("player.index"))
    player = relationship("Player", back_populates="values", lazy="joined")

    position = Column(Enum(Position))

    calculation_id = Column(Integer, ForeignKey("value_calculation.index"))
    calculation = relationship("ValueCalculation", back_populates="values")

    value = Column(Float)

class ValueCalculation(Base):
    __tablename__ = "value_calculation"
    index = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    timestamp = Column(Date, nullable=False)

    projection_id = Column(Integer, ForeignKey("projection.index"))
    projection = relationship("Projection", back_populates="calculations")
    # Corresponds to ScoringFormat enum
    format = Column(Enum(ScoringFormat))
    hitter_basis = Column(Enum(RankingBasis))
    pitcher_basis = Column(Enum(RankingBasis))

    inputs = relationship("CalculationInput", back_populates="calculation", cascade="all, delete", lazy='joined')
    values = relationship("PlayerValue", back_populates="calculation", cascade="all, delete")
    data = relationship("ValueData", back_populates="calculation", cascade="all, delete", lazy='joined')

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

class CalculationInput(Base):

    __tablename__ = "calculation_input"
    index = Column(Integer, primary_key=True)

    # This corresponds to the CalculationInput enum
    data_type = Column(Enum(CalculationDataType), nullable=False)

    value = Column(Float, nullable=False)

    calculation_id = Column(Integer, ForeignKey("value_calculation.index"))
    calculation = relationship("ValueCalculation", back_populates="inputs")

class ValueData(Base):
    __tablename__ = "value_data"
    index = Column(Integer, primary_key=True)

    # This corresponds to the CalculationDataType
    data_type = Column(Enum(CalculationDataType), nullable=False)

    value = Column(Float, nullable=False)

    calculation_id = Column(Integer, ForeignKey("value_calculation.index"))
    calculation = relationship("ValueCalculation", back_populates="data")
    
class Projection(Base):
    __tablename__ = "projection"
    index = Column(Integer, primary_key=True)
    
    # This corresponds to the ProjectionType enum
    type = Column(Enum(ProjectionType))
    timestamp = Column(Date, nullable=False)
    name = Column(String, nullable=False)
    detail = Column(String)
    season = Column(Integer, nullable=False)

    ros = Column(Boolean, nullable=False)
    dc_pt = Column(Boolean, nullable=False)
    hide = Column(Boolean, nullable=False)

    valid_points = Column(Boolean)
    valid_5x5 = Column(Boolean)
    valid_4x4 = Column(Boolean)

    player_projections = relationship("PlayerProjection", back_populates="projection", cascade="all, delete")
    calculations = relationship("ValueCalculation", back_populates="projection", cascade="all, delete")

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
        
class PlayerProjection(Base):
    __tablename__ = "player_projection"
    index = Column(Integer, primary_key=True)

    player_id = Column(Integer, ForeignKey("player.index"))
    player = relationship("Player", back_populates="projections", lazy="joined")

    projection_id = Column(Integer, ForeignKey("projection.index"))
    projection = relationship("Projection", back_populates="player_projections")

    projection_data = relationship("ProjectionData", back_populates="player_projection", cascade="all, delete", lazy="joined")

    pitcher = Column(Boolean)
    two_way = Column(Boolean)

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

class ProjectionData(Base):
    __tablename__ = "projection_data"
    index = Column(Integer, primary_key=True)

    player_projection_id = Column(Integer, ForeignKey("player_projection.index"))
    player_projection = relationship("PlayerProjection", back_populates="projection_data")

    # Corresponds to StatType enum
    stat_type = Column(Enum(StatType), nullable=False) 
    stat_value = Column(Float, nullable=False)

class Salary_Refresh(Base):
    # Class to track how recently the Ottoverse average values have been refreshed
    __tablename__ = "salary_refresh"
    format = Column(Enum(ScoringFormat), primary_key=True)
    last_refresh = Column(TIMESTAMP, nullable=False)

class Draft(Base):
    '''Class to hold user draft inputs'''
    __tablename__ = 'draft'
    index = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("league.index"))
    league = relationship("League")

    targets = relationship("Draft_Target", back_populates="draft", cascade="all, delete", lazy="joined")
    cm_draft = relationship("CouchManagers_Draft", uselist=False, back_populates='draft', cascade="all, delete", lazy="joined")

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

class Draft_Target(Base):
    '''Class to hold user draft target information'''
    __tablename__ = 'draft_target'
    index = Column(Integer, primary_key=True)
    draft_id = Column(Integer, ForeignKey("draft.index"), nullable=False)
    draft = relationship("Draft", back_populates='targets')

    player_id = Column(Integer, ForeignKey("player.index"), nullable=False)
    player = relationship("Player", lazy="joined")

    price = Column(Integer, nullable=True)

class CouchManagers_Draft(Base):
    '''Class to hold CouchManagers Draft Data'''
    __tablename__ = 'cm_draft'
    index = Column(Integer, primary_key=True)
    cm_draft_id = Column(Integer, nullable=False)
    draft_id = Column(Integer, ForeignKey("draft.index"), nullable=False)
    draft = relationship("Draft", back_populates='cm_draft')
    setup = Column(Boolean)

    teams = relationship("CouchManagers_Team", back_populates="cm_draft", cascade="all, delete", lazy="joined")

    def get_toolbox_team_index_by_cm_team_id(self, cm_team_id:int) -> int:
        '''Gets the linked Ottoneu Toolbox Team index associated with the input CouchManagers team id'''
        for team in self.teams:
            if team.cm_team_id == cm_team_id:
                return team.ottoneu_team_id
        return 0

class CouchManagers_Team(Base):
    '''Class that maps CouchManagers draft team numbers'''
    __tablename__ = 'cm_teams'
    index = Column(Integer, primary_key=True)
    cm_draft_id = Column(Integer, ForeignKey("cm_draft.index"), nullable=False)
    cm_draft = relationship("CouchManagers_Draft", back_populates='teams')

    cm_team_id = Column(Integer, nullable=False)
    cm_team_name = Column(String)
    ottoneu_team_id = Column(Integer, nullable=False)

class Adv_Calc_Option(Base):
    '''Class to hold advanced calculation inputs'''
    __tablename__ = 'adv_calc_option'
    index = Column(Enum(CalculationDataType), primary_key=True)
    value = Column(Float)