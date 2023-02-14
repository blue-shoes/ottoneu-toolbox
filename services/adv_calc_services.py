from dao.session import Session
from domain.domain import Adv_Calc_Option
from domain.enum import CalculationDataType as CDT

def get_advanced_option(data_type:CDT) -> Adv_Calc_Option:
    '''Gets the advanced calculation option based on the data type'''
    with Session() as session:
        adv_opt = session.query(Adv_Calc_Option).filter(Adv_Calc_Option.index == data_type).first()
    return adv_opt

def set_advanced_option(data_type:CDT, value:float) -> Adv_Calc_Option:
    '''Sets the input value for the advance calculation optino based on the data type'''
    adv_opt = get_advanced_option(data_type)
    if adv_opt == None:
        adv_opt = Adv_Calc_Option()
        adv_opt.index = data_type
        adv_opt.value = value
    with Session() as session:
        session.add(adv_opt)
        session.commit()
    return adv_opt
