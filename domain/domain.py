from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy import Integer, String, Boolean, Float, Date, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from domain.enum import CalculationDataType, ProjectionType, ScoringFormat, StatType, Position

Base = declarative_base()

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

class League(Base):
    __tablename__ = "league"
    index = Column(Integer, primary_key=True)
    name = Column(String)
    # Corresponds to ScoringFormat enum
    format = Column(Enum(ScoringFormat), nullable=False)
    num_teams = Column(Integer, nullable=False)
    last_refresh = Column(Date, nullable=False)

    teams = relationship("Team", back_populates="league", cascade="all, delete")

class Team(Base):
    __tablename__ = "team"
    index = Column(Integer, primary_key=True)

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

    ottoneu_id = Column(Integer, ForeignKey("player.index"))
    player = relationship("Player", back_populates="roster_spots")

    salary = Column(Integer)

class Salary_Info(Base):
    __tablename__ = "salary_info"
    index = Column(Integer, primary_key=True)

    ottoneu_id = Column("Ottoneu ID",Integer, ForeignKey("player.index"))
    player = relationship("Player", back_populates="salary_info")

    format = Column(Enum(ScoringFormat))
    
    avg_salary = Column("Avg Salary",Float)
    med_salary = Column("Median Salary",Float)
    min_salary = Column("Min Salary",Float)
    max_salary = Column("Max Salary",Float)
    last_10 = Column("Last 10",Float)
    roster_percentage = Column("Roster %",Float)

class PlayerValue(Base):
    __tablename__ = "point_value"
    index = Column(Integer, primary_key=True)

    ottoneu_id = Column(Integer, ForeignKey("player.index"))
    player = relationship("Player", back_populates="values")

    position = Column(Enum(Position))

    calculation_id = Column(Integer, ForeignKey("value_calculation.index"))
    calculation = relationship("ValueCalculation", back_populates="values")

    value = Column(Float)

class ValueCalculation(Base):
    __tablename__ = "value_calculation"
    index = Column(Integer, primary_key=True)

    projection_id = Column(Integer, ForeignKey("projection.index"))
    projection = relationship("Projection", back_populates="calculations")
    # Corresponds to ScoringFormat enum
    format = Column(Enum(ScoringFormat))

    inputs = relationship("CalculationInput", back_populates="calculation", cascade="all, delete")
    values = relationship("PlayerValue", back_populates="calculation", cascade="all, delete")
    data = relationship("ValueData", back_populates="calculation", cascade="all, delete")

    def set_input(self, data_type, value):
        for inp in self.inputs:
            if inp.data_type == data_type:
                inp.value = value
                return
        ci = CalculationInput()
        ci.data_type = data_type
        ci.value = value
        self.inputs.append(ci)

    def get_input(self, data_type):
        for inp in self.inputs:
            if inp.data_type == data_type:
                return inp.value
        return None
    
    def set_output(self, data_type, value):
        for data in self.data:
            if data.data_type == data_type:
                data.value = value
                return
        vd = ValueData()
        vd.data_type = data_type
        vd.value = value
        self.data.append(vd)

    def get_output(self, data_type):
        for data in self.data:
            if data.data_type == data_type:
                return data.value
        return None

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
    player_projections = relationship("PlayerProjection", back_populates="projection", cascade="all, delete")
    calculations = relationship("ValueCalculation", back_populates="projection", cascade="all, delete")

class PlayerProjection(Base):
    __tablename__ = "player_projection"
    index = Column(Integer, primary_key=True)

    player_id = Column(Integer, ForeignKey("player.index"))
    player = relationship("Player", back_populates="projections")

    projection_id = Column(Integer, ForeignKey("projection.index"))
    projection = relationship("Projection", back_populates="player_projections")

    projection_data = relationship("ProjectionData", back_populates="player_projection", cascade="all, delete")

    pitcher = Column(Boolean)

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
    # Class to track how recently the Ottoverse average values have been refrehsed
    __tablename__ = "salary_refresh"
    format = Column(Enum(ScoringFormat), primary_key=True)
    last_refresh = Column(Date, nullable=False)