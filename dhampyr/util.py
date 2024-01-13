import builtins
from functools import partial
from collections.abc import Sequence, Callable
from typing import Any, Optional, Union, get_args, get_origin
from typing_extensions import TypeGuard
try:
    from types import UnionType # type: ignore
except:
    UnionType = None


def get_self_args(self: Any) -> Sequence[Any]:
    generics = getattr(self, '__orig_class__', None)
    return get_args(generics)


def is_builtin(t) -> TypeGuard[type]:
    return isinstance(t, type) and hasattr(builtins, t.__qualname__)


def isinstance_safe(v: Any, t: Any) -> bool:
    origin = get_origin(t)
    return isinstance(v, origin) if origin else isinstance(v, t)


def parse_optional(t) -> Optional[type]:
    org = get_origin(t)
    if org is Optional:
        return get_args(t)[0]
    elif org is Union or org == UnionType:
        args = get_args(t)
        if len(args) == 2:
            if args[1] is get_args(Optional[Any])[1]:
                return args[0]
    return None


def alt_partial(func: partial, alternate: Callable[[Any], Optional[Any]]) -> partial:
    seq_args = []
    base = func
    while True:
        seq_args.insert(0, (base.args, base.keywords))
        if isinstance(base.func, partial):
            base = base.func
        else:
            break
    alt = alternate(base.func)
    if alt:
        for args, keywords in seq_args:
            alt = partial(alt, *args, **keywords)
        return alt
    else:
        return func
