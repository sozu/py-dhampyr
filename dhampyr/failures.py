import re
from functools import partial
from itertools import chain


class ValidationFailure(Exception):
    """
    Base exception type for every validation failure.
    """
    def __init__(self, name="invalid", message="Validation failed", args=None, kwargs=None):
        super().__init__(message)
        self._name = name
        self._message = message
        self._args = args or []
        self._kwargs = kwargs or {}

    def __iter__(self):
        yield ValidationPath([]), self

    @property
    def name(self):
        return self._name

    @property
    def message(self):
        return self._message

    @property
    def args(self):
        return self._args

    @property
    def kwargs(self):
        return self._kwargs

    @classmethod
    def abort(cls, *args, **kwargs):
        raise PartialFailure(partial(cls, *args, **kwargs))


class MalformedFailure(ValidationFailure):
    def __init__(self):
        super().__init__("malformed", "Input of the validation suite is not like dictinoary.")


class ValidationPath:
    """
    Represents a path to a validated element.

    Each item in path is either a key of dictionary or an index of iterable values.

    The path provides the textual representaion where
    the key is concatenated by `.` like object attribute, whereas the index is enclosed with square bracket like list index.
    """
    PATH_ITEM_REGEXP = re.compile(r"^([a-zA-Z_][0-9a-zA-Z_]*)?((\[[0-9]+\])+)?")

    def __init__(self, path):
        self.path = path

    def __iter__(self):
        return iter(self.path)

    def __repr__(self):
        return at(self.path)

    def __add__(self, other):
        if isinstance(other, (str, int)):
            return ValidationPath(self.path + [other])
        elif isinstance(other, ValidationPath):
            return ValidationPath(self.path + other.path)
        else:
            raise ValueError(f"Unsupported operand type(s) for +: 'ValidationPath' and '{type(other)}'")

    def __iadd__(self, other):
        if isinstance(other, (str, int)):
            self.path.append(other)
        elif isinstance(other, ValidationPath):
            self.path += other.path
        else:
            raise ValueError(f"Unsupported operand type(s) for +: 'ValidationPath' and '{type(other)}'")

    @classmethod
    def of(cls, path):
        items = path.split(".")
        def parse_index(s):
            m = ValidationPath.PATH_ITEM_REGEXP.match(s)
            if not m:
                raise ValueError(f"'{path}' is not valid validation path.")
            key = m.group(1)
            indexes = m.group(2)
            if indexes:
                return chain([key] if key else [], map(int, indexes[1:-1].split("][")))
            else:
                return [key] if key else []
        return ValidationPath(list(chain(*map(parse_index, items), [])))


def at(positions):
    def exp(i, p):
        if isinstance(p, str):
            return p if i == 0 else f".{p}"
        elif isinstance(p, int):
            return f"[{p}]"
        else:
            return ""
    return ''.join([exp(i, p) for i, p in enumerate(positions)])


class CompositeValidationFailure(ValidationFailure):
    """
    This type stores validation failures and provides ways to access them.

    Examples
    --------
    >>> class C:
    ...     a: +v(int) = 0
    ...     b: +v(int) = 0
    ...
    >>> r = validate_dict(C, dict(a = "a"))

    You can get a `ValidationFailure` by accessing with attribute name.

    >>> r.failures['a'].name
    'int'
    >>> r.failures['b'].name
    'missing'

    Failures are traversable in iteration context.

    >>> dict(map(lambda f: (f[0], f[1].name), r))
    {'a': 'int', 'b': 'missing'}
    """
    def __init__(self):
        super().__init__()
        self.failures = {}

    @property
    def message(self):
        return f"{len(self.failures)} validation failures arised."

    def __iter__(self, pos=None):
        pos = pos or []
        for k, f in self.failures.items():
            p = pos + [k]
            if isinstance(f, CompositeValidationFailure):
                for g in f.__iter__(p):
                    yield g
            else:
                yield (ValidationPath(p), f)

    def __len__(self):
        return len(self.failures)

    def __getitem__(self, key):
        if isinstance(key, str):
            f = self.failures
            for p in ValidationPath.of(key):
                f = f[p]
            return f
        else:
            return self.failures[key]

    def __contains__(self, key):
        return key in self.failures

    def add(self, key, f):
        self.failures[key] = f


class PartialFailure(Exception):
    def __init__(self, builder):
        super().__init__()
        self.builder = builder

    def create(self, **kwargs):
        return self.builder(**kwargs)