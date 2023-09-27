from datetime import datetime

def get_current_ottoneu_year():
    """Gets the current year for projections. Assumes October and later is next year, otherwise current year"""
    now = datetime.now()
    if now.month > 9:
        return now.year + 1
    else:
        return now.year

def is_offseason():
    '''Returns if it is currently the offseason. Offseason is defined as October through January.'''
    now = datetime.now()
    if now.month > 9:
        return True
    if now.month < 2:
        return True
    return False