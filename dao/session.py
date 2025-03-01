from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from domain.domain import reg
from domain.enum import as_enum
import json

Session = sessionmaker()

def init_sessionmaker(connnection_string:str) -> None:
    engine = create_engine(connnection_string, json_deserializer=lambda text: json.loads(text, object_hook=as_enum))
    reg.generate_base().metadata.create_all(engine)
    global Session
    Session.configure(bind=engine)
