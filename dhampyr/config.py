from collections.abc import Callable
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, fields, field
from functools import wraps
from typing import Any, Optional, Union, TypeVar, TypedDict, cast, overload, TYPE_CHECKING
from typing_extensions import Self, TypeAlias, Unpack, NotRequired


T = TypeVar('T')


if TYPE_CHECKING:
    class Configurable(TypedDict):
        name: NotRequired[str]
        key_filter: NotRequired[Optional[Callable[[str], str]]]
        skip_null: NotRequired[bool]
        skip_empty: NotRequired[bool]
        allow_null: NotRequired[bool]
        allow_empty: NotRequired[bool]
        empty_specs: NotRequired[list[tuple[type, Callable[[type], bool]]]]
        isinstance_builtin: NotRequired[bool]
        isinstance_any: NotRequired[bool]
        join_on_fail: NotRequired[bool]
        ignore_remainders: NotRequired[bool]
        share_context: NotRequired[bool]
else:
    Configurable: TypeAlias = dict


@dataclass
class ValidationConfiguration:
    """
    Configurations for validation.
    """
    name: str = "default"
    """Name of this configuration. This value has no effect on any behavior of modules."""
    key_filter: Optional[Callable[[str], str]] = None
    """A function which maps attribute names in validatable type to keys of input dictionary."""
    skip_null: bool = True
    """If true, validator not prepended by `+` skips when the input is `None`."""
    skip_empty: bool = True
    """If true, validator not prepended by `+` skips when the input is empty."""
    allow_null: bool = False
    """If true, `+` prepended validator skips when the input is `None`."""
    allow_empty: bool = False
    """If true, `+` prepended validator skips when the input is empty."""
    empty_specs: list[tuple[type, Callable[[type], bool]]] = field(default_factory=list)
    """Functions to check the value of specific type is empty or not."""
    isinstance_builtin: bool = False
    """If true, `Converter` declared by builtin type checks that the input is instance of the type instead of applying constructor."""
    isinstance_any: bool = False
    """If true, `Converter` declared by any type checks that the input is instance of the type instead of applying constructor."""
    join_on_fail: bool = True
    """If true, failed iterable values are joined into single `None`."""
    ignore_remainders: bool = False
    """If true, not validated values are simply discarded."""
    share_context: bool = False
    """If true, `ValidationContext` is shared in an invocation of `validate_dict()`."""

    def _copy_to(self, other: Self, **kwargs: Any):
        for f in fields(self):
            val = kwargs[f.name] if f.name in kwargs else deepcopy(getattr(self, f.name))
            setattr(other, f.name, val)

    def _check_fields(self, **kwargs: Any):
        names = {f.name for f in fields(self)}
        invalid = [k for k in kwargs.keys() if k not in names]
        if len(invalid) > 0:
            raise KeyError(f"Invalid configuration keys are found: {', '.join(invalid)}")

    def derive(self, **settings: Unpack[Configurable]) -> Self:
        """
        Creates new configuration instance deriving this configuration.

        Args:
            settings: Configuration parameters which overwrites values in this instance.
        Returns:
            Derived configuration object.
        """
        self._check_fields(**settings)
        derived = ValidationConfiguration()
        self._copy_to(derived, **settings)
        return derived

    def set(self, **settings: Unpack[Configurable]) -> None:
        self._check_fields(**settings)
        for k, v in settings.items():
            setattr(self, k, v)

    def __enter__(self) -> Self:
        derived = self.derive()
        return derived

    def __exit__(self, exc_type, exc_value, traceback):
        pass


def contextualConfiguration(
    config_var: Callable[[], ContextVar[ValidationConfiguration]],
    base: Optional[ValidationConfiguration] = None
) -> ValidationConfiguration:
    @dataclass
    class contextual(ValidationConfiguration):
        def __enter__(self) -> Self:
            derived = contextual()
            self._copy_to(derived)
            config_var().set(derived)
            return derived

        def __exit__(self, exc_type, exc_value, traceback):
            config_var().set(self)

    cfg = contextual()
    if base:
        base._copy_to(cfg)
    return cfg


config: ContextVar[ValidationConfiguration] = ContextVar('config', default=contextualConfiguration(lambda: config))


def default_config() -> ValidationConfiguration:
    """
    Returns a global configuration.

    Global configuration is managed in *context* provided by `contextvars` module.
    Update on the returned object will change the behaviors of library modules globally.

    The object works as a context manager by `with` block where another object can be used as global configuration.

    ```python
    >>> with default_config() as cfg:
    >>>     # Updates to cfg are reflected to global configurations.
    >>>     cfg.name = "another"
    >>>     assert default_config().name == "another"
    >>> # Updates inside with block is no longer valid.
    >>> assert default_config().name == "default"
    ```
    """
    return config.get()


class ConfigurationStack:
    """
    Stack of configurations which mocks `ValidationConfiguration`.
    """
    def __init__(self, base: ValidationConfiguration) -> None:
        #: Base configuration supplying default values.
        self.base = base
        #: Configuration stack.
        self.stack: list[Configurable] = [{}]

    def __getattr__(self, key: str) -> Any:
        """
        Returns configuration of passed key found first in stack.
        """
        for config in self.stack[::-1]:
            if key in config:
                return config[key]
        return getattr(self.base, key)

    def on(self, t: type) -> ValidationConfiguration:
        """
        Returns configuration for passed type.

        If specific configuration for the type is registered,
        it is pushed at the top of the stack for later validations in propagated types.

        Args:
            t: Type to validate.
        Returns:
            Configuration for the type.
        """
        config = typed_config().get(t)
        if config:
            self.push(config)
        return cast(ValidationConfiguration, self)

    def derive(self, **settings: Unpack[Configurable]) -> Self:
        """
        Creates new configuration instance deriving this configuration.

        Args:
            settings: Configuration parameters which overwrites values in this instance.
        Returns:
            Derived configuration object.
        """
        derived = type(self)(self) # type: ignore
        derived.push(settings)
        return derived

    def push(self, config: Configurable) -> Self:
        """
        Push a partial configuration values to the stack.

        Args:
            config: Partial configuration values.
        Returns:
            This instance.
        """
        self.stack.append(config)
        return self

    def pop(self) -> Self:
        """
        Pop a partial configuration values from the stack.

        Returns:
            This instance.
        """
        if len(self.stack) > 1:
            self.stack.pop()
        return self


class TypedConfiguration:
    def __init__(self) -> None:
        self.holder = {}

    def put(self, t: type, settings: Configurable) -> Self:
        self.holder[t] = settings
        return self

    def get(self, t: type) -> Optional[Configurable]:
        return self.holder.get(t)

    def clear(self):
        self.holder = {}


def typed_config(config: TypedConfiguration = TypedConfiguration()) -> TypedConfiguration:
    return config


#def validatable(**settings: Unpack[Configurable]) -> Callable[[T], T]:
#    """
#    A decorator for class to validate its instance under the given configurations.
#
#    ```python
#    >>> @validatable(skip_null=False, join_on_fail=False, isinstance_builtin=True)
#    >>> class V:
#    >>>     v1: v(int)
#    >>>     v2: v([str])
#    ```
#
#    This function also works as meta decorator which gives another decorator the ability to apply configurations to decorated type.
#
#    ```python
#    >>> @validatable(skip_null=False, join_on_fail=False, isinstance_builtin=True)
#    >>> def meta(t):
#    >>>     return t
#    >>>
#    >>> @meta
#    >>> class V:
#    >>>     v1: v(int)
#    >>>     v2: v([str])
#    ```
#
#    Args:
#        settings: Partial settings of `ValidationConfig` .
#    """
#    class Decorator:
#        def __init__(self, **kwargs: Unpack[Configurable]):
#            self.settings = kwargs.copy()
#
#        @overload
#        def __call__(self, arg: type) -> type: ...
#        @overload
#        def __call__(self, arg: Callable) -> Callable: ...
#        def __call__(self, arg: Union[type, Callable]) -> Union[type, Callable]:
#            if isinstance(arg, type):
#                typed_config().put(arg, self.settings)
#                return arg
#            elif callable(arg): 
#                @wraps(arg)
#                def inner(*args, **kw):
#                    decorated = arg(*args, **kw)
#                    if isinstance(decorated, type):
#                        return self(decorated)
#                    else:
#                        # When decorator target is not a type, do nothing.
#                        return decorated
#                return inner
#            else:
#                raise ValueError("The target of @validatable decorator must be a type or another decorator function.")
#
#    return Decorator(**settings) # type: ignore