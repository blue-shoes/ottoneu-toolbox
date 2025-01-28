from typing import Dict

from dao.session import Session
from domain.domain import Adv_Calc_Option
from domain.enum import CalculationDataType as CDT


def get_advanced_option(data_type: CDT, default: float = None) -> Adv_Calc_Option:
    """Gets the advanced calculation option based on the data type"""
    with Session() as session:
        adv_opt = session.query(Adv_Calc_Option).filter(Adv_Calc_Option.id == data_type).first()
    if adv_opt is None:
        adv_opt = Adv_Calc_Option()
        adv_opt.id = data_type
        adv_opt.value = default
    return adv_opt


def set_advanced_option(data_type: CDT, value: float) -> Adv_Calc_Option:
    """Sets the input value for the advance calculation optino based on the data type"""
    with Session() as session:
        adv_opt = session.query(Adv_Calc_Option).filter(Adv_Calc_Option.id == data_type).first()
        if adv_opt is None:
            adv_opt = Adv_Calc_Option()
            adv_opt.id = data_type
            adv_opt.value = value
            session.add(adv_opt)
        else:
            adv_opt.value = value
        session.commit()
    return adv_opt


def get_adv_option_dict() -> Dict[CDT, Adv_Calc_Option]:
    """Gets all advanced options in the database and returns a dictionary of the advanced option index (i.e. the CalculationDataType) to the advanced option"""
    with Session() as session:
        adv_list = session.query(Adv_Calc_Option).all()
    adv_dict = {}
    for adv in adv_list:
        adv_dict[adv.id] = adv
    return adv_dict
