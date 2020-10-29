from functools import wraps
from .validator import Validator


def strict(item):
    """
    A decoorator function to execute strict type check in conversion phase.

    Parameters
    ----------
    item: type | callable
        If type, converters of validators declared in it become strict.
        If function, types decorated by it are considered to be decorated by `strict`.
    """
    if isinstance(item, type):
        for v in [v for k, v in item.__annotations__.items() if isinstance(v, Validator)]:
            v.converter.strict = True
        return item
    elif callable(item):
        @wraps(item)
        def inner(*args, **kwargs):
            decorated = item(*args, **kwargs)
            return strict(decorated)
        return inner
    else:
        raise ValueError("The target of @strict decorator must be a type or another decorator function.")