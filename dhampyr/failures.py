from collections.abc import Generator, Iterator
import re
from functools import partial
from itertools import chain
from typing import Any, Optional, Union
from typing_extensions import Self


class ValidationFailure(Exception):
    """
    Base exception type for every validation failure.
    """
    def __init__(self, name: str = "invalid", message: str = "Validation failed", args=None, kwargs=None) -> None:
        """
        Constructor of the failure.

        Args:
            name: The name to distinguish the type of failure.
            message: Error message format.
            args: Values being used as positional arguments to build error message.
            kwargs: Values being used as keyword arguments to build error message.
        """
        super().__init__(message)
        self._name = name
        self._message = message
        self._args = args or []
        self._kwargs = kwargs or {}

    def __len__(self) -> int:
        return 1

    def __iter__(self) -> Generator[tuple['ValidationPath', Self], None, None]:
        yield ValidationPath([]), self

    def __contains__(self, key: Union[str, int]) -> bool:
        return False

    def __getitem__(self, key: Union[str, int]) -> Optional[Self]:
        return None

    @property
    def name(self):
        """
        Returns the name to distinguish the type of failure.
        """
        return self._name

    @property
    def message(self):
        """
        Returns the error message format.
        """
        return self._message

    @property
    def args(self):
        """
        Returns the positional arguments to build error message.
        """
        return self._args

    @property
    def kwargs(self):
        """
        Returns the keyword arguments to build error message.
        """
        return self._kwargs

    @classmethod
    def abort(cls, *args, **kwargs):
        """
        Utility method to raise a failure from custom converter/verifier function.

        By invokiing this method on appropriate failure type, `ConversionFailure` or `VerificationFailure`,
        correct failure object of the type is constructed and raised.

        Parameters
        ----------
        args: [object]
            Arguments for error message.
        kwargs: {str:object}
            Keyword arguments for error message.
        """
        raise PartialFailure(partial(cls, *args, **kwargs))


class MalformedFailure(ValidationFailure):
    """
    Validation failure raised when the input object is not dictionary-like.
    """
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

    def __init__(self, path: list[Union[str, int]]):
        self.path = path

    def __iter__(self) -> Iterator[Union[str, int]]:
        return iter(self.path)

    def __repr__(self) -> str:
        return at(self.path)

    def __add__(self, other: Union[str, int, Self, None]) -> Self:
        """
        Creates new path by appending another path or a path segment to this path.
        """
        if other == "" or other is None:
            return ValidationPath(self.path)
        elif isinstance(other, (str, int)):
            return ValidationPath(self.path + [other])
        elif isinstance(other, ValidationPath):
            return ValidationPath(self.path + other.path)
        else:
            raise ValueError(f"Unsupported operand type(s) for +: 'ValidationPath' and '{type(other)}'")

    def __iadd__(self, other: Union[str, int, Self, None]):
        """
        Append another path or a path segment to this path.
        """
        if other == "" or other is None:
            pass
        elif isinstance(other, (str, int)):
            self.path.append(other)
        elif isinstance(other, ValidationPath):
            self.path += other.path
        else:
            raise ValueError(f"Unsupported operand type(s) for +: 'ValidationPath' and '{type(other)}'")
        return self

    def pop(self):
        """
        Pop the last path segment.
        """
        self.path.pop()

    def under(self, other: Self) -> bool:
        """
        Checks whether this path is under given path.

        Args:
            other: Another path.
        Returns:
            `True` when this path is under given path.
        """
        return len(self.path) >= len(other.path) and all([s == o for s, o in zip(self.path, other.path)])

    @classmethod
    def of(cls, path: str) -> Self:
        """
        Create an instance of this class by textual representation of a path.

        Args:
            path: Textual representation of a path.
        """
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
    The instance of this class stores validation failures and provides ways to access them.

    ```python
    >>> class C:
    ...     a: +v(int) = 0
    ...     b: +v(int) = 0
    ...
    >>> r = validate_dict(C, dict(a = "a"))
    ```

    You can get a `ValidationFailure` by accessing with attribute name.

    ```python
    >>> r.failures['a'].name
    'int'
    >>> r.failures['b'].name
    'missing'
    ```

    Failures are traversable in iteration context.

    ```python
    >>> dict(map(lambda f: (str(f[0]), f[1].name), r))
    {'a': 'int', 'b': 'missing'}
    ```

    `in` operator is available to know whether the error exists or not at a path.

    ```python
    >>> [p in r.failures for p in ('a', 'b', 'c')]
    [True, True, False]
    ```
    """
    def __init__(self):
        super().__init__()
        #: Failures by path strings.
        self.failures: dict[Union[str, int], ValidationFailure] = {}

    @property
    def message(self) -> str:
        """
        Returns default mesasge of composite failures.
        """
        return f"{len(self.failures)} validation failures arised."

    def __iter__(self, pos: Optional[list[Union[str, int]]] = None) -> Generator[tuple[ValidationPath, ValidationFailure], None, None]:
        """
        Iterates failures and yields each with its path.

        Args:
            pos: Root path where iteration starts.
        """
        pos = pos or []
        for k, f in self.failures.items():
            p = pos + [k]
            if isinstance(f, CompositeValidationFailure):
                for g in f.__iter__(p):
                    yield g
            else:
                yield (ValidationPath(p), f)

    def __len__(self) -> int:
        """
        Counts the number of failures.
        """
        return len(self.failures)

    def __getitem__(self, key: Union[str, int]) -> Optional[ValidationFailure]:
        if isinstance(key, str):
            f = self.failures
            for p in ValidationPath.of(key):
                f = f and (f[p] if p in f else None)
            return self if isinstance(f, dict) else f
        else:
            return self.failures.get(key, None)

    def __contains__(self, key: Union[str, int]) -> bool:
        if isinstance(key, str):
            cf = self
            for p in ValidationPath.of(key):
                if not isinstance(cf, CompositeValidationFailure):
                    return False
                if p not in cf.failures:
                    return False
                cf = cf.failures[p]
            return True
        else:
            return key in self.failures

    def add(self, key: Union[str, int], f: ValidationFailure):
        self.failures[key] = f


class PartialFailure(Exception):
    def __init__(self, builder):
        super().__init__()
        self.builder = builder

    def create(self, **kwargs):
        return self.builder(**kwargs)