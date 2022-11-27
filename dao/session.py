from sqlalchemy import create_engine
from sqlalchemy.orm import  sessionmaker
import os
from domain.domain import Base

dirname = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))
db_dir = os.path.join(dirname, 'db')
if not os.path.exists(db_dir):
    os.mkdir(db_dir)
db_loc = os.path.join(dirname, 'db', 'otto_toolbox.db')
engine = create_engine(f"sqlite:///{db_loc}")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
