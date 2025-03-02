from domain.domain import PlayerProjection, CustomScoring
from domain.enum  import RankingBasis

class points_cache():
    def __init__(self, function):
        #ic('init ing')
        self.cache = {}
        self.function = function
    
    def __call__(self, *args, **kwargs):
        #ic(*args)
        keyset = set()
        for a in args:
            if a:
                if isinstance(a, PlayerProjection):
                    keyset.add(f"pp{a.id}")
                elif isinstance(a, CustomScoring):
                    keyset.add(f"cs{a.id}")
                #elif isinstance(a, RankingBasis):
                #    keyset.add(f"rb{a.value}")
                else:
                    keyset.add(a)
        #ic(keyset)
        #ic(self)
        key = str(keyset)
        if key in self.cache:
            return self.cache[key]
        
        value = self.function(*args, **kwargs)
        self.cache[key] = value
        return value