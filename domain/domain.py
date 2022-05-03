from sqlalchemy import Column, PrimaryKeyConstraint
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy import Float
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
from tables import StringCol

Base = declarative_base()

class Player(Base):
    __tablename__ = "player"
    ottoneu_id = Column('Ottoneu ID', Integer, primary_key=True)
    fg_major_id = Column('FG MajorLeagueID', Integer)
    fg_minor_id = Column('FG MinorLeagueID', String)
    name = Column("Name",String)
    team = Column("Org",String(7))
    position = Column("Position(s)",String)

    roster_spots = relationship("Roster_Spot", back_populates="player")
    salary_info = relationship("Salary_Info", back_populates="player")
    values = relationship("Value", back_populates="player")

class League(Base):
    __tablename__ = "league"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    format = Column(Integer)

    teams = relationship("Team", back_populates="league")

class Team(Base):
    __tablename__ = "team"
    id = Column(Integer, primary_key=True)

    league_id = Column(Integer, ForeignKey("league.id"))
    league = relationship("League", back_populates="teams")

    name = Column(String)
    users_team = Column(Boolean)
    
    roster_spots = relationship("Roster_Spot", back_populates="team")

class Roster_Spot(Base):
    __tablename__ = "roster_spot"
    id = Column(Integer, primary_key=True)

    team_id = Column(Integer, ForeignKey="team.id")
    team = relationship("Team", back_populates="roster_spots")

    ottoneu_id = Column(Integer, ForeignKey="player.ottoneu_id")
    player = relationship("Player", back_populates="roster_spots")

    salary = Column(Integer)

class Salary_Info(Base):
    __tablename__ = "salary_info"
    id = Column(Integer, primary_key=True)

    ottoneu_id = Column("Ottoneu ID",Integer, ForeignKey="player.ottoneu_id")
    player = relationship("Player", back_populates="salary_info")

    game_type = Column(Integer)
    
    avg_salary = Column("Avg Salary",Float)
    med_salary = Column("Median Salary",Float)
    min_salary = Column("Min Salary",Float)
    max_salary = Column("Max Salary",Float)
    last_10 = Column("Last 10",Float)
    roster_percentage = Column("Roster %",Float)

class Value(Base):
    __tablename__ = "point_value"
    id = Column(Integer, primary_key=True)

    ottoneu_id = Column(Integer, ForeignKey="player.ottoneu_id")
    player = relationship("Player", back_populates="values")

    value = Column(Float)
    game_type = Column(Integer)
    
