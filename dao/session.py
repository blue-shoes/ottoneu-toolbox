from sqlalchemy import create_engine
from sqlalchemy.orm import  sessionmaker
import os
from domain.domain import reg

db_dir = 'db'
if not os.path.exists(db_dir):
    os.mkdir(db_dir)
db_loc = os.path.join('db', 'otto_toolbox.db')
engine = create_engine(f"sqlite:///{db_loc}")
reg.generate_base().metadata.create_all(engine)
Session = sessionmaker(bind=engine)
