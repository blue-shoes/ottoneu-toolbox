from dao.session import Session
from domain.domain import Property
from domain.enum import PropertyType

def get_db_version():
    with Session() as session:
        return session.query(Property).filter(Property.name == PropertyType.DB_VERSION.value).first()

def save_property(prop: Property):
    with Session() as session:
        old_prop = session.query(Property).filter(Property.name == prop.name).first()
        if old_prop is None:
            session.add(prop)
        else:
            old_prop.value = prop.value
        session.commit()
        prop = get_property(prop.name)
    return prop

def get_property(name):
    with Session() as session:
        return session.query(Property).filter(Property.name == name).first()

def save_db_version(version):
    prop = Property()
    
    save_property(prop)
    return prop