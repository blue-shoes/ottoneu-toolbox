normalMap = {'À': 'A', 'Á': 'A', 'Â': 'A', 'Ã': 'A', 'Ä': 'A',
             'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'ª': 'A',
             'È': 'E', 'É': 'E', 'Ê': 'E', 'Ë': 'E',
             'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
             'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
             'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
             'Ò': 'O', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ö': 'O',
             'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o', 'º': 'O',
             'Ù': 'U', 'Ú': 'U', 'Û': 'U', 'Ü': 'U',
             'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
             'Ñ': 'N', 'ñ': 'n',
             'Ç': 'C', 'ç': 'c',
             '§': 'S',  '³': '3', '²': '2', '¹': '1'}


def normalize(value:str) -> str:
    """Function that removes most diacritics from strings and returns value in all caps"""
    normalize = str.maketrans(normalMap)
    try:
        val = value.translate(normalize)
    except AttributeError:
        raise AttributeError
    return val.upper()

def parse_dollar(value) -> float:
    '''Returns the float value of the input. If input is float or int, returns the float representation of it. If the input
    is a string, strips the $ symbol if necessary and returns the float value.'''
    if isinstance(value, float) or isinstance(value, int):
        return float(value)
    if '$' in value:
        vals = value.split('$')
        if len(vals[0]) > 0 and '-' in vals[0]:
            return -float(vals[1])
        else:
            return float(vals[1])
    return float(value)

def int_validation(input) -> bool:
    '''Returns true if the value is an integer or blank. False otherwise.'''
    if input.isdigit():
        return True
    if input == "":
        return True
    return False