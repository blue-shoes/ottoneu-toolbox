from sqlalchemy import Column, ForeignKey
from sqlalchemy import Integer, String, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Player(Base):
    __tablename__ = "player"
    index = Column(Integer, primary_key=True)
    ottoneu_id = Column('Ottoneu ID', Integer)
    fg_major_id = Column('FG MajorLeagueID', String)
    fg_minor_id = Column('FG MinorLeagueID', String)
    name = Column("Name",String)
    team = Column("Org",String(7))
    position = Column("Position(s)",String)

    roster_spots = relationship("Roster_Spot", back_populates="player", cascade="all, delete")
    salary_info = relationship("Salary_Info", back_populates="player", cascade="all, delete")
    values = relationship("PlayerValue", back_populates="player", cascade="all, delete")
    projections = relationship("PlayerProjection", back_populates="player", cascade="all, delete")

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
    format = Column(Integer)
    num_teams = Column(Integer)

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

    # Corresponds to ScoringFormat enum
    format = Column(Integer)
    
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

    calculation_id = Column(Integer, ForeignKey("value_calculation.index"))
    calculation = relationship("ValueCalculation", back_populates="values")

    value = Column(Float)

class ValueCalculation(Base):
    __tablename__ = "value_calculation"
    index = Column(Integer, primary_key=True)

    projection_id = Column(Integer, ForeignKey("projection.index"))
    projection = relationship("Projection", back_populates="calculations")
    # Corresponds to ScoringFormat enum
    format = Column(Integer)

    inputs = relationship("CalculationInput", back_populates="calculation", cascade="all, delete")
    values = relationship("PlayerValue", back_populates="calculation", cascade="all, delete")
    data = relationship("ValueData", back_populates="calculation", cascade="all, delete")

class CalculationInput(Base):
    __tablename__ = "calculation_input"
    index = Column(Integer, primary_key=True)

    # This corresponds to the CalculationInput enum
    data_type = Column(Integer, nullable=False)

    value = Column(Float, nullable=False)

    calculation_id = Column(Integer, ForeignKey("value_calculation.index"))
    calculation = relationship("ValueCalculation", back_populates="inputs")

class ValueData(Base):
    __tablename__ = "value_data"
    index = Column(Integer, primary_key=True)

    # This corresponds to the CalculationDataType
    data_type = Column(Integer, nullable=False)

    value = Column(Float, nullable=False)

    calculation_id = Column(Integer, ForeignKey("value_calculation.index"))
    calculation = relationship("ValueCalculation", back_populates="data")
    
class Projection(Base):
    __tablename__ = "projection"
    index = Column(Integer, primary_key=True)
    
    # This corresponds to the ProjectionType enum
    type = Column(Integer)
    # Timestamp must be converted to Text
    timestamp = Column(String)
    name = Column(String)
    detail = Column(String)

    ros = Column(Boolean)
    dc_pt = Column(Boolean)
    hide = Column(Boolean)
    player_projections = relationship("PlayerProjection", back_populates="projection", cascade="all, delete")
    calculations = relationship("ValueCalculation", back_populates="projection", cascade="all, delete")

class PlayerProjection(Base):
    __tablename__ = "player_projection"
    index = Column(Integer, primary_key=True)

    ottoneu_id = Column(Integer, ForeignKey("player.index"))
    player = relationship("Player", back_populates="projections")

    projection_id = Column(Integer, ForeignKey("projection.index"))
    projection = relationship("Projection", back_populates="player_projections")

    projection_data = relationship("ProjectionData", back_populates="player_projection", cascade="all, delete")

class ProjectionData(Base):
    __tablename__ = "projection_data"
    index = Column(Integer, primary_key=True)

    player_projection_id = Column(Integer, ForeignKey("player_projection.index"))
    player_projection = relationship("PlayerProjection", back_populates="projection_data")

    # Corresponds to StatType enum
    stat_type = Column(Integer, nullable=False) 
    stat_value = Column(Float)