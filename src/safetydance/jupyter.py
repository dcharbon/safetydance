import builtins
from functools import lru_cache


@lru_cache
def is_jupyter():
    return hasattr(builtins, '__IPYTHON__')
