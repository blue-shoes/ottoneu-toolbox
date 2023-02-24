from pandas import DataFrame

def weighted_avg(df:DataFrame, vals:str, weights:str) -> float:
        '''Returns the weighted average of the vals StatType with weights weighting'''
        d = df[vals]
        w = df[weights]
        return (d * w).sum() / w.sum()