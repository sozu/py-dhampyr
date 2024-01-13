from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from enum import Enum
import re
from typing import Any, Union, Optional
from decimal import Decimal
from uuid import UUID
from .util import isinstance_safe


#----------------------------------------------------------------
# Builtin converters.
#----------------------------------------------------------------
def _noop(x: Any) -> Any:
    return x

def str_bytes(v: str, **kwargs) -> bytes:
    return v.encode(**kwargs)

def any_decimal(v: Any, **kwargs) -> Decimal:
    return Decimal(v, **kwargs)


strict_conversions: dict[type, dict[type, Callable[[Any], Any]]] = {
    bytes: {
        str: str_bytes,
    },
    float: {
        int: float,
    },
    Decimal: {
        str: any_decimal,
        int: any_decimal,
        float: any_decimal,
    },
    UUID: {
        str: UUID,
        bytes: lambda x: UUID(bytes=x),
    },
}


def _strict(t: Any, union: Any, is_optional: bool, conversions: dict[type, Callable]) -> Callable:
    def conv(v: (Optional[union] if is_optional else union)) -> (Optional[t] if is_optional else t):
        if isinstance_safe(v, t):
            return v
        elif v is None and is_optional:
            return v
        else:
            for u, f in conversions.items():
                if isinstance_safe(v, u):
                    return f(v)
            raise ValueError(f"{type(v)} is not {t}.")
    return conv


def convert_strict(t: Any, is_optional: bool) -> Callable:
    if t is Any:
        return _noop
    elif not isinstance(t, type):
        raise TypeError(f"{t} is not a convertible type.")
    else:
        union = t
        conversions = strict_conversions.get(t, {})

        other_types = list(conversions.keys())
        if other_types:
            o = other_types[0]
            union = Union[t, o]
            for u in other_types[1:]:
                union = Union[union, u]

        return _strict(t, union, is_optional, conversions)


def convert_bool() -> Callable:
    def conv(v: Union[bool, str, int]) -> bool:
        return bool(v)
    return conv


def convert_int() -> Callable:
    def conv(v: Union[str, int, float, Decimal], base: int = 10) -> int:
        if isinstance(v, int):
            return v
        elif isinstance(v, str):
            return int(v, base=base)
        else:
            return int(v)
    return conv


def convert_float() -> Callable:
    def conv(v: Union[str, int, float, Decimal]) -> float:
        if isinstance(v, float):
            return v
        elif isinstance(v, str):
            return float(v)
        else:
            return float(v)
    return conv


def convert_decimal() -> Callable:
    def conv(v: Union[str, int, float, Decimal]) -> Decimal:
        if isinstance(v, Decimal):
            return v
        else:
            return Decimal(v)
    return conv


def convert_bytes() -> Callable:
    def conv(v: Union[str, bytes, bytearray], encoding: str = 'utf-8') -> bytes:
        if isinstance(v, bytes):
            return v
        elif isinstance(v, bytearray):
            return bytes(v)
        else:
            return v.encode(encoding) # type: ignore
    return conv


def convert_str() -> Callable:
    def conv(v: Union[str, bytes, bytearray], encoding: str = 'utf-8') -> str:
        if isinstance(v, str):
            return v
        else:
            return str(v, encoding=encoding)
    return conv


def convert_date() -> Callable:
    def conv(v: Union[str, date], format: Optional[str] = None) -> date:
        if isinstance(v, date):
            return v
        elif format is None:
            return date.fromisoformat(v)
        else:
            return datetime.strptime(v, format).date()
    return conv


def convert_datetime() -> Callable:
    def conv(v: Union[str, date, datetime], format: Optional[str] = None) -> datetime:
        if isinstance(v, datetime):
            return v
        elif isinstance(v, date):
            return datetime(v.year, v.month, v.day)
        elif format is None:
            return datetime.fromisoformat(v)
        else:
            return datetime.strptime(v, format)
    return conv


def convert_time() -> Callable:
    def conv(v: Union[str, time], format: Optional[str] = None) -> time:
        if isinstance(v, time):
            return v
        elif format is None:
            return time.fromisoformat(v)
        else:
            return datetime.strptime(v, format).time()
    return conv


def convert_timedelta() -> Callable:
    numexp = r'[\d]+([\.\,][\d]+)?'
    pattern = re.compile(
        fr'^P(?P<year>{numexp}Y)?(?P<month>{numexp}M)?(?P<day>{numexp}D)?(T(?P<hour>{numexp}H)?(?P<minute>{numexp}M)?(?P<second>{numexp}S)?)?$',
    )
    week_pattern = re.compile(fr'^P(?P<week>{numexp}W)$')

    def delta(gd: dict[str, str], key: str) -> int:
        value = gd.get(key)
        return int(value[:-1]) if value else 0

    def conv(v: Union[str, timedelta]) -> timedelta:
        if isinstance(v, timedelta):
            return v
        else:
            m = pattern.match(v)
            m = m or week_pattern.match(v)
            print(m)
            if m:
                gd = m.groupdict()

                if gd.get('year') or gd.get('month'):
                    raise ValueError(f"Year or month is not available for timedelta.")

                return timedelta(
                    weeks=delta(gd, 'week'),
                    days=delta(gd, 'day'),
                    hours=delta(gd, 'hour'),
                    minutes=delta(gd, 'minute'),
                    seconds=delta(gd, 'second'),
                )
            else:
                raise ValueError(f"{v} can not be converted to timedelta.")
    return conv


def convert_uuid() -> Callable:
    def conv(v: Union[UUID, str, bytes]) -> UUID:
        if isinstance(v, UUID):
            return v
        elif isinstance(v, bytes):
            return UUID(bytes=v)
        else:
            return UUID(v) # type: ignore
    return conv


def get_enum_conversion(t: type, holder: dict[type, Callable] = {}) -> tuple[str, Callable[[Any], Any]]:
    key = t

    if key in holder:
        return t.__name__, holder[key]
    else:
        def conv(v: Union[t, str]) -> t:
            if isinstance_safe(v, t):
                return v
            else:
                return t.__getitem__(v) # type: ignore
        return t.__name__, holder.setdefault(key, conv)


builtin_conversions: dict[type, tuple[str, Callable[[Any], Any]]] = {
    Any: ('any', _noop),
    bool: ('bool', convert_bool()),
    int: ('int', convert_int()),
    float: ('float', convert_float()),
    Decimal: ('decimal', convert_decimal()),
    bytes: ('bytes', convert_bytes()),
    str: ('str', convert_str()),
    date: ('date', convert_date()),
    datetime: ('datetime', convert_datetime()),
    time: ('time', convert_time()),
    timedelta: ('timedelta', convert_timedelta()),
    UUID: ('uuid', convert_uuid()),
}