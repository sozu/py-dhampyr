from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import is_dataclass, fields, MISSING
from enum import Enum
from functools import partial, wraps
from typing import Any, Annotated, Optional, Literal, Protocol, NamedTuple, Union, TypeVar, cast, overload, get_type_hints, get_origin, get_args
from typing_extensions import dataclass_transform, TypeAlias, Unpack
from .config import Configurable, typed_config
from .validator import Validator, ValidationResult, ValidatorFactory
from .converter import Converter, ConverterFactory, get_enum_conversion, get_factory, get_builtin_factory, get_user_factory
from .verifier import Verifier
from .variable import Variable
from .context import ValidationContext, analyze_callable
from .failures import ValidationFailure, MalformedFailure, CompositeValidationFailure
from .requirement import Requirement, VALUE_MISSING
from .util import alt_partial, parse_optional


D = TypeVar('D', contravariant=True)
T = TypeVar('T', covariant=True)


#------------------------------------------------------------
# Input parser
#------------------------------------------------------------
class DictLike(Protocol[D]):
    def get(self, values: D, key: str, as_list: bool) -> Any: ...

    def keys(self, values: D) -> Iterable[str]: ...


class ByDict(DictLike[dict]):
    def get(self, values: dict, key: str, as_list: bool) -> Any:
        return values[key]

    def keys(self, values: dict) -> Iterable[str]:
        return values.keys()


class ByDataclass(DictLike[D]):
    def __init__(self, cls: D) -> None:
        if is_dataclass(cls):
            self.fields = {f.name: f for f in fields(cls)}
        else:
            raise TypeError(f"{cls} is not a dataclass")

    def get(self, values: D, key: str, as_list: bool) -> Any:
        val = getattr(values, key)
        if as_list:
            fld = self.fields[key]
            org = get_origin(fld.type) or fld.type
            if issubclass(org, Iterable):
                return val
            else:
                raise TypeError(f"Type of the field '{key}' is not Iterable.")
        else:
            return val

    def keys(self, values: D) -> Iterable[str]:
        return self.fields.keys()


try:
    from werkzeug.datastructures import MultiDict # type: ignore
    is_multidict = lambda d: isinstance(d, MultiDict)

    class ByMultiDict(DictLike[MultiDict]):
        def get(self, values: MultiDict, key: str, as_list: bool):
            if as_list:
                return values.getlist(k) # type: ignore
            else:
                return values[k] # type: ignore

        def keys(self, values: MultiDict) -> Iterable[str]:
            return values.keys()
    _by_multidict = ByMultiDict()
except ImportError:
    is_multidict = lambda d: False
    _by_multidict: DictLike = NotImplemented


def dict_like(values: D, _by_dict=ByDict(), _by_multidict=_by_multidict) -> DictLike[D]:
    if is_multidict(values):
        return _by_multidict
    elif is_dataclass(values):
        return ByDataclass(type(values))
    elif isinstance(values, dict):
        return _by_dict # type: ignore
    else:
        raise ValueError(f"The instance of {type(values)} can not be represented as dict.")


#------------------------------------------------------------
# Output generator
#------------------------------------------------------------
class Modeller(Protocol[T]):
    def create(self, attributes: dict[str, Any], *args, **kwargs) -> T: ...


class ToObject(Modeller[T]):
    def __init__(self, target: type[T]) -> None:
        self.target = target

    def create(self, attributes: dict[str, Any], *args, **kwargs) -> T:
        value = self.target(*args, **kwargs)

        for k, v in attributes.items():
            setattr(value, k, v)

        return value


class ToDataclass(Modeller[T]):
    def __init__(self, target: type[T]) -> None:
        if is_dataclass(target):
            self.target = target
            self.fields = {f.name: f for f in fields(target)}
        else:
            raise TypeError(f"{target} is not a type of dataclass.")

    def create(self, attributes: dict[str, Any], *args, **kwargs) -> T:
        return self.target(**attributes)


class ToDict(Modeller[dict]):
    def create(self, attributes: dict[str, Any], *args, **kwargs) -> dict[str, Any]:
        return dict(attributes, **kwargs)


class LazyValidatorFactory(ValidatorFactory):
    def __init__(
        self,
        converter: Any,
        verifiers: Sequence[Verifier],
        alias: Optional[str] = None,
        default: Optional[Any] = MISSING,
        default_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        super().__init__(converter, verifiers, alias, default, default_factory)
        self.conversion_spec = None

    def create(self, cxt: ValidationContext) -> Validator:
        self.converter = converter(self.conversion_spec)
        return super().create(cxt)


def modeller(cls: type[T], _to_dict=ToDict()) -> Modeller[T]:
    if is_dataclass(cls):
        return ToDataclass(cls)
    elif isinstance(cls, dict):
        return _to_dict # type: ignore
    else:
        return ToObject(cls)


def v(
    conv: Any = ...,
    *vers: Any,
    alias: Optional[str] = None,
    default: Optional[Any] = MISSING,
    default_factory: Optional[Callable[[], Any]] = None,
) -> Any:
    """
    Creates a `ValidatorFactory` which generates a `Validator` for passed context.

    This function works as dataclass field specifier, see `dataclass_transform` or PEP681 to know the meanings of optional keyword arguments.

    Args:
        conv: Converter specifier. See `converter()` to know what kind of values are available.
        vers: Verifier specifiers. See `verifier()` to know what kind of values are available.
        alias: Key of the target value is the input dictionary. If `None`, declared attribute name is used to obtain the value.
    Returns:
        Validator factory.
    """
    if conv is ... or conv is None:
        return LazyValidatorFactory(..., [verifier(v) for v in vers], alias, default, default_factory)
    else:
        return ValidatorFactory(converter(conv), [verifier(v) for v in vers], alias, default, default_factory)


#@dataclass_transform(kw_only_default=True, field_specifiers=(v,))
#def validatable():
#    """
#    A decorator for types where validating fields are declared by assigning validator.
#    """
#    return lambda x: x
@dataclass_transform(kw_only_default=True, field_specifiers=(v,))
def validatable(**settings: Unpack[Configurable]) -> Callable[[T], T]:
    """
    A decorator for class to validate its instance under the given configurations.

    ```python
    >>> @validatable(skip_null=False, join_on_fail=False, isinstance_builtin=True)
    >>> class V:
    >>>     v1: v(int)
    >>>     v2: v([str])
    ```

    This function also works as meta decorator which gives another decorator the ability to apply configurations to decorated type.

    ```python
    >>> @validatable(skip_null=False, join_on_fail=False, isinstance_builtin=True)
    >>> def meta(t):
    >>>     return t
    >>>
    >>> @meta
    >>> class V:
    >>>     v1: v(int)
    >>>     v2: v([str])
    ```

    Args:
        settings: Partial settings of `ValidationConfig` .
    """
    class Decorator:
        def __init__(self, **kwargs: Unpack[Configurable]):
            self.settings = kwargs.copy()

        @overload
        def __call__(self, arg: type) -> type: ...
        @overload
        def __call__(self, arg: Callable) -> Callable: ...
        def __call__(self, arg: Union[type, Callable]) -> Union[type, Callable]:
            if isinstance(arg, type):
                typed_config().put(arg, self.settings)
                return arg
            elif callable(arg): 
                @wraps(arg)
                def inner(*args, **kw):
                    decorated = arg(*args, **kw)
                    if isinstance(decorated, type):
                        return self(decorated)
                    else:
                        # When decorator target is not a type, do nothing.
                        return decorated
                return inner
            else:
                raise ValueError("The target of @validatable decorator must be a type or another decorator function.")

    return Decorator(**settings) # type: ignore


class VerifierMethod(Verifier):
    def __init__(self, name, func, dependencies):
        super().__init__(name, func, False)
        self.positive = {k for k, v in dependencies.items() if v is True}
        self.negative = {k for k, v in dependencies.items() if v is False}

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            def call(*args, **kwargs):
                return self.func(instance, *args, **kwargs)
            return call

    def fulfill_dependencies(self, failures):
        keys = failures.failures.keys()

        if self.negative & keys:
            return False
        elif self.positive and not (self.positive & keys):
            return True
        else:
            return not bool(keys)


def validate(_name_: Optional[str] = None, **dependencies: bool) -> Callable[[Callable], VerifierMethod]:
    """
    A decorator for methods which works as verifier for validated instance.

    ```python
    class V:
        a: int = v(...)
        b: int = v(...)
        c: int = v(...)

        @validate("check_a", a=True, c=False)
        def check(self):
            ...
    ```

    Each key in `dependencies` corresponds to a field of the same name
    and its value determines whether the method is invoked or not when validation failure is reported from the field.

    The method is invoked when:

    - If there are `False` dependencies, the method is not invoked if validations on some of them failed.
    - If There are `True` dependencies, the method is invoked if validations on all of them succeeded.
    - Otherwise, the method is invoked only when validations of all fields succeeded.

    In case of above example code:

    - If validation on `c` fails, `check` is not invoked.
    - If validation on `a` succeeds, `check` is invoked in spite of the result of `b` .

    Args:
        _name_: Name of the verifier. If not set, method name is used.
        dependencies: Dependencies to fields.
    Returns:
    """
    def decorate(f: Callable):
        return VerifierMethod(_name_ or f.__name__, f, dependencies)
    return decorate


def parse_validators(cls: type) -> dict[str, ValidatorFactory]:
    """
    Parse a class and extract validators for its attributes.

    For backward compatibility, validators can be defined in 3 forms.

    ```python
    # 1. With dataclass transform decorator.
    @validatable
    class V:
        a: int = v(..., default=0)

    # 2. With Annoteted, which is available in dataclasses.
    @dataclass
    class V:
        a: Annotated[int, v(...)] = 0

    # 3. Style in previous version which is not correct python convention.
    class V:
        a: v(...) = 0
    ```

    Args:
        cls: Class to parse.
    Returns:
        Mapping of validator factories by their attribute names.
    """
    def supply_converter(factory: ValidatorFactory, spec: Any) -> ValidatorFactory:
        if factory and isinstance(factory, LazyValidatorFactory):
            factory.conversion_spec = spec
        return factory

    def get_validator(ann: Any) -> Optional[ValidatorFactory]:
        if isinstance(ann, ValidatorFactory):
            return ann
        elif get_origin(ann) is Annotated:
            factory = next(filter(lambda a: isinstance(a, ValidatorFactory), get_args(ann)), None)
            if factory:
                factory = supply_converter(factory, get_args(ann)[0])
            return factory
        else:
            return None

    type_hints = get_type_hints(cls, include_extras=True)

    validators = {k: val for k, val in [(k, get_validator(ann)) for k, ann in type_hints.items()] if val is not None}

    attr_validators = {}
    for k, attr in vars(cls).items():
        if isinstance(attr, ValidatorFactory):
            attr_validators[k] = supply_converter(attr, type_hints.get(k, Any))

    return validators | attr_validators


def fetch_verifier_methods(cls, failures) -> Iterable[VerifierMethod]:
    def to_vm(k):
        if not k.startswith("__"):
            value = getattr(cls, k)
            return value if isinstance(value, VerifierMethod) and value.fulfill_dependencies(failures) else None
        return None

    return filter(None, [to_vm(k) for k in dir(cls)])


def validate_dict(cls: type[T], values: Any, context: Optional[ValidationContext] = None, *args, **kwargs) -> ValidationResult[T]:
    """
    Creates an instance of `cls` from dictionary-like object.

    `values` must be an object which can be dumped into dictionary.
    Each key-value pair is validated by validator of the same key which is parsed from passed `cls` .
    If validations on all keys succeeds, the instance of the class is generated and returned within `ValidationResult` ,
    otherwise, observed errors are set within it instead.

    If `values` is not a valid dictionary-like object, `MalformedFailure` is set to the result.

    Args:
        cls: Type of the instance to create.
        values: Dictionay-like object.
        context: Root context of this validation suite.
        args: Positional arguments passed to the constructor of `cls` .
        kwargs: Keyword arguments passed to the constructor of `cls` .
    Returns:
        An object which contains created instance or error informations.

    Examples:

    ```python
    --------
    >>> class C:
    ...     a: +v(int) = 0
    ...     b: +v(int) = 1
    ...     c: v(int) = 2
    ...     d: v(int, lambda x: x < 0) = 3
    ...
    >>> r = validate_dict(C, dict(a = "1", c = "a", d = "1"))
    >>> x = r.get()
    >>> type(x)
    <class '__main__.C'>
    >>> (x.a, x.b, x.c, x.d)
    (1, 1, 2, 3)
    ```
    """
    context = context or ValidationContext()

    with context.on(cls):
        try:
            accessor = dict_like(values)
        except:
            return ValidationResult(None, MalformedFailure(), context)

        # Validated values.
        attributes: dict[str, Any] = {}
        # Observed errors.
        failures = CompositeValidationFailure()
        # Keys where validators are applied.
        validated_keys = set()

        validators = parse_validators(cls)
        key_filter = context.config.key_filter or (lambda x: x)

        for k, vf in validators.items():
            key = key_filter(vf.alias or k)

            validated_keys.add(key)

            with context[k, True] as cxt:
                v = vf.create(cxt)
                val = accessor.get(values, key, v.accept_list) if key in values else VALUE_MISSING
                validated, f, use_alt = v.validate(val, cxt)

            # Validated value can be non-None even when the validation failed.
            if validated is not None:
                attributes[k] = validated
            if f:
                failures.add(k, f)
            if use_alt:
                if vf.default != MISSING:
                    attributes[k] = vf.default
                elif vf.default_factory:
                    attributes[k] = vf.default_factory()
                elif hasattr(cls, k):
                    alt = getattr(cls, k)
                    attributes[k] = alt if not isinstance(alt, ValidatorFactory) else None

        if not context.config.ignore_remainders:
            for k in accessor.keys(values):
                if k not in validated_keys:
                    if context.config.share_context:
                        holder = _holder_for_path(context.remainders, context.path + k)
                        holder[k] = values[k]
                    else:
                        context.remainders[k] = values[k]

        instance = modeller(cls).create(attributes, *args, **kwargs)

        for m in fetch_verifier_methods(cls, failures):
            f = m.verify(instance, context)
            if f is not None:
                failures.add(m.name, f)

    return ValidationResult(instance, failures, context)


#def _like_dictionary(values):
#    return is_multidict(values) or is_dataclass(values) or (
#        hasattr(values, '__contains__') \
#            and hasattr(values, '__getitem__') \
#            and hasattr(values, '__iter__') \
#            and not isinstance(values, (list, str))
#    )


def _holder_for_path(holder, path):
    for key in path.path[:-1]:
        if key not in holder:
            holder[key] = {}
        holder = holder[key]

    return holder


ConverterSpec: TypeAlias = Any
VerifierSpec: TypeAlias = Any


def converter(
    func: Union[ConverterSpec, list[ConverterSpec], tuple[str, ConverterSpec], list[tuple[str, ConverterSpec]]],
) -> ConverterFactory:
    """
    Creates a `ConverterFactory` by given specifier.

    Roughly speaking, `ConverterSpec` is a function which converts input value into another value, or a type of the converted value.
    It can be passed by being paired with a string which specifies the name of the `Converter` .
    Besides, it can be passed in the form of a list to apply it to each item in iterable input respectively.

    ```python
    converter(int) # Input value is converted to int by applying builtin int function.
    converter(lambda x: x+1) # Add 1 to input value.
    converter(("test", int)) # Set converter name to 'test'
    converter([int]) # Apply builtin int function to each item in input iterable values.
    ```

    When the specifier is user-defined type, it expects input as dict-like object and validation suite for the type will be applied.
    `Enum` type is a special case, for which the converter search a enum item by matching its name to input string.

    ```python
    class E(Enum):
        e1 = auto()
        e2 = auto()
    converter(E) # If input is 'e1' or 'e2', it is converted into E.e1 or E.e2. Otherwise, conversion fails.
    ```

    Note that specifier should have correct type hints to get correct schema of input/output of the `Converter` .

    Args:
        func: Converter specifier.
    Returns:
        Created `ConverterFactory` .
    """
    def throw(e):
        raise e

    is_iter = False
    if isinstance(func, list):
        # [int]
        func, is_iter = func[0], True
    elif get_origin(func) is list:
        # list[int]
        func, is_iter = get_args(func)[0], True

    def user_defined(t: type, it, name, optional) -> ConverterFactory:
        def create(v: Any, cxt: ValidationContext) -> t:
            return validate_dict(t, v, cxt).or_else(throw)
        return get_user_factory(t, name, it, optional, create)

    def to_converter(fn, it, opt, name=None) -> ConverterFactory:
        opt_type = parse_optional(fn)

        if opt_type is not None:
            return to_converter(opt_type, it, True, name)

        builtin = get_builtin_factory(fn, name, it, opt)
        if builtin:
            return builtin
        elif isinstance(fn, partial):
            return get_factory(name or fn.func.__name__, it, opt, analyze_callable(fn), *fn.args, **fn.keywords)
        elif isinstance(fn, type):
            if issubclass(fn, Enum):
                n, call = get_enum_conversion(fn)
                return get_factory(name or n, it, opt, analyze_callable(call))
            else:
                return user_defined(fn, it, name, opt)
        elif isinstance(fn, set):
            # Backward compatibility.
            t = next(iter(fn), None)
            if not isinstance(t, type):
                raise TypeError(f"Set specifier must contain only a type.")
            return user_defined(t, it, name, opt)
        elif callable(fn):
            cc = analyze_callable(fn)
            name = name or getattr(fn, '__name__', 'Unknown')
            return get_factory(name, it, opt, cc)
        else:
            raise TypeError(f"Given value is not valid Converter specifier: {fn}")

    if isinstance(func, ConverterFactory):
        return func
    elif isinstance(func, tuple) and len(func) == 2:
        name, fn = func
        return to_converter(fn, is_iter, False, name)
    else:
        return to_converter(func, is_iter, False)


def verifier(
    func: Union[VerifierSpec, list[VerifierSpec], tuple[str, VerifierSpec], list[tuple[str, VerifierSpec]]],
) -> Verifier:
    """
    Creates a `Verifier` by given specifier.

    `func` is the specifier of a `Verifier` which is interpreted similarly to `ConverterSpec` as detailed in `converter` .

    Args:
        func: Verifier specifier.
    Returns:
        Created `Verifier` .
    """
    func, is_iter = (func[0], True) if isinstance(func, list) else (func, False)

    def to_verifier(fn, it, name=None) -> Verifier:
        if isinstance(fn, Variable):
            return fn._verifier
        elif isinstance(fn, partial):
            cc = analyze_callable(fn)
            return Verifier[cc.in_type](name or fn.func.__name__, cc, it, *fn.args, **fn.keywords)
        elif callable(fn):
            cc = analyze_callable(fn)
            return Verifier(name or fn.__name__, cc, it)
        else:
            raise TypeError(f"Given value is not valid Verifier specifier: {fn}")

    if isinstance(func, Verifier):
        return func
    elif isinstance(func, tuple) and len(func) == 2:
        name, fn = func
        return to_verifier(fn, is_iter, name)
    else:
        return to_verifier(func, is_iter)