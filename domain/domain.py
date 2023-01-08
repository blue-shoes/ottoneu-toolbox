from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import Integer, String, Boolean, Float, Date, Enum, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from domain.enum import CalculationDataType, ProjectionType, RankingBasis, ScoringFormat, StatType, Position

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
    team = Column("Org",String(7))
    position = Column("Position(s)",String)

    roster_spots = relationship("Roster_Spot", back_populates="player", cascade="all, delete")
    salary_info = relationship("Salary_Info", back_populates="player", cascade="all, delete")
    values = relationship("PlayerValue", back_populates="player", cascade="all, delete")
    projections = relationship("PlayerProjection", back_populates="player", cascade="all, delete")

    __table_args__ = (Index('idx_fg_id','FG MajorLeagueID','FG MinorLeagueID'),)

    def get_fg_id(self):
        if self.fg_major_id != None:
            return self.fg_major_id
        else:
            return self.fg_minor_id
    
    def pos_eligible(self, pos: Position):
        if pos == Position.OVERALL:
            return True
        elif pos == Position.OFFENSE or pos == Position.POS_UTIL:
            for p in Position.get_discrete_offensive_pos():
                if p.value in self.position:
                    return True
            return False
        elif pos == Position.PITCHER:
            for p in Position.get_discrete_pitching_pos():
                if p.value in self.position:
                    return True
            return False
        return pos.value in self.position
    
    def is_two_way(self):
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

class Team(Base):
    __tablename__ = "team"
    index = Column(Integer, primary_key=True)
    site_id = Column(Integer, nullable=False)

    league_id = Column(Integer, ForeignKey("league.index"))
    league = relationship("League", back_populates="teams")

    name = Column(String)
    users_team = Column(Boolean)
    
    roster_spots = relationship("Roster_Spot", back_populates="team", cascade="all, delete")

class Roster_Spot(Base):
    __tablename__ = "roster_spot"
    index = Column(Integer, primary_key=True)

    team_id = Column(Integer, ForeignKey("team.index"))
    team = relationship("Team", back_populates="roster_spots")

    player_id = Column(Integer, ForeignKey("player.index"))
    player = relationship("Player", back_populates="roster_spots")

    salary = Column(Integer)

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

    def init_value_dict(self):
        for pv in self.values:
            if pv.player_id not in self.value_dict:
                player_dict = {}
                self.value_dict[pv.player_id] = player_dict
            player_dict = self.value_dict[pv.player_id]
            player_dict[pv.position] = pv

    def set_input(self, data_type, value):
        for inp in self.inputs:
            if inp.data_type == data_type:
                inp.value = value
                return
        ci = CalculationInput()
        ci.data_type = data_type
        ci.value = value
        self.inputs.append(ci)

    def get_input(self, data_type, default=None):
        for inp in self.inputs:
            if inp.data_type == data_type:
                return inp.value
        return default
    
    def set_output(self, data_type, value):
        for data in self.data:
            if data.data_type == data_type:
                data.value = value
                return
        vd = ValueData()
        vd.data_type = data_type
        vd.value = value
        self.data.append(vd)

    def get_output(self, data_type, default=None):
        for data in self.data:
            if data.data_type == data_type:
                return data.value
        return default
    
    def set_player_value(self, player_id, pos, value):
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
    
    def get_player_value(self, player_id, pos=None):
        if player_id not in self.value_dict:
            if pos is None:
                return {}
            return None
        if pos is None:
            #Get all positions
            return self.value_dict[player_id]
        else:
            return self.value_dict[player_id][pos]
    
    def get_position_values(self, pos) -> list[PlayerValue]:
        values = []
        for pv in self.values:
            if pv.position == pos:
                values.append(pv)
        return values


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

    proj_dict = {}

    def init_proj_dict(self):
        for pp in self.player_projections:
            self.proj_dict[pp.player.index] = pp

    def get_player_projection(self, player_id):
        if len(self.proj_dict) == 0:
            for pp in self.player_projections:
                if pp.player_id == player_id or pp.player.index == player_id:
                    return pp
        else:
            return self.proj_dict.get(player_id)
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

    def get_stat(self, stat_type):
        for pd in self.projection_data:
            if pd.stat_type == stat_type:
                return pd.stat_value
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

    targets = relationship("Draft_Target", back_populates="draft", cascade="all, delete")

    year = Column(Integer, nullable=False)

    def get_target_by_player(self, player_id):
        if self.targets is not None:
            for target in self.targets:
                if target.player.index == player_id:
                    return target
        return None

    def set_target(self, player_id, price=None):
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

