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

def save_db_version(version):
    prop = Property()
    prop.name = PropertyType.DB_VERSION.value
    prop.value = version
    save_property(prop)