from datetime import datetime

def get_current_ottoneu_year():
    """Gets the current year for projections. Assumes October and later is next year, otherwise current year"""
    now = datetime.now()
    if now.month > 9:
        return now.year + 1
    else:
        return now.year