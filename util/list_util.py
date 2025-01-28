from typing import List, Dict, Tuple
from collections import OrderedDict


def rank_list_with_ties(vals: List[object], reverse: bool = True, max_rank: int = 12) -> Dict[object, float]:
    """Ranks the argument list. If ties occur, average the rank"""
    count = {}
    none_vals = False
    for val in vals:
        if val is None:
            none_vals = True
            if reverse:
                val = 0
            else:
                val = 9e9
        count[val] = count.get(val, 0) + 1
    sorted_list = OrderedDict(sorted(count.items(), key=lambda t: t[0], reverse=reverse))

    rank_map = {}
    rank = max_rank
    for val, num in sorted_list.items():
        if num == 1:
            rank_map[val] = rank
            rank = rank - 1
        else:
            min_rank = rank - (num - 1)
            rank_map[val] = (rank + min_rank) / 2
            rank = rank - num
    if none_vals:
        if reverse:
            rank_map[None] = rank_map[0]
        else:
            rank_map[None] = rank_map[9e9]
    return rank_map


def weighted_average(vals: List[Tuple[float, float]]) -> float:
    """Returns a weighted average of the input list. List is a set of Tuples with the weights as the first
    value and the value to be weighted as the second value"""
    num = 0
    denom = 0
    for val in vals:
        num = num + val[0] * val[1]
        denom = denom + val[0]
    return num / denom
