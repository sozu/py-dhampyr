from collections.abc import Callable, Iterable, Sequence
from dataclasses import is_dataclass, fields, MISSING
from decimal import Decimal
from enum import Enum
from functools import partial, wraps
from typing import Any, Annotated, Optional, Protocol, Union, TypeVar, overload, get_type_hints, get_origin, get_args
from typing_extensions import dataclass_transform, TypeAlias, Unpack
from .config import Configurable, typed_config
from .validator import Validator, ValidationResult, ValidatorFactory
from .converter import ConverterFactory, ListFactory, OptionalFactory, get_enum_conversion, get_factory, get_builtin_factory, get_user_factory
from .verifier import Verifier
from .variable import Variable
from .context import ValidationContext, analyze_callable
from .failures import MalformedFailure, CompositeValidationFailure
from .requirement import VALUE_MISSING
from .util import parse_optional


D = TypeVar('D', contravariant=True)
T = TypeVar('T', covariant=True)


#------------------------------------------------------------
# Input parser
#------------------------------------------------------------
class DictLike(Protocol[D]):
    """
    An interface providing ways to interpret an object as dictionary.

    Args:
        D: Type of object bo be used as dictionary.
    """
    def get(self, values: D, key: str, as_list: bool) -> Any:
        """
        Extracts value(s) by key.

        Args:
            values: A dictionary-like object.
            key: Key.
            as_list: Whether caller requires a list.
        Returns:
            Value for the key.
        """
        ...

    def keys(self, values: D) -> Iterable[str]:
        """
        Returns keys.

        Args:
            values: A dictionary-like object.
        Returns:
            Keys.
        """
        ...


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
            org: Any = get_origin(fld.type) or fld.type
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
                return values.getlist(key)
            else:
                return values[key]

        def keys(self, values: MultiDict) -> Iterable[str]:
            return values.keys()
    _by_multidict = ByMultiDict()
except ImportError:
    is_multidict = lambda d: False
    _by_multidict: DictLike = NotImplemented


def dict_like(values: D, /, _by_dict=ByDict(), _by_multidict=_by_multidict) -> DictLike[D]:
    """
    Get a `DictLike` object available for given value.

    Args:
        values: A dictionary-like object.
    Returns:
        A `DictLike` object.
    """
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
    """
    An interface to construct an instance from validated values.

    Args:
        T: Type of the instance to construct.
    """
    def create(self, attributes: dict[str, Any], *args, **kwargs) -> T:
        """
        Creates an instance of `T` .

        Args:
            attributes: Validated values.
            args: Positional arguments passed to `validate_dict` .
            kwargs: Keyword arguments passed to `validate_dict` .
        Returns:
            Created instance.
        """
        ...


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
    """
    Validator factory generated by `v` function where the converter specifier is not given.

    In this case, the type of the converter is inferred from type hint of the target attribute.
    This class enables such deferred creation of converter.
    """
    def __init__(
        self,
        converter: Any,
        verifiers: Sequence[Verifier],
        alias: Optional[str] = None,
        default: Optional[Any] = MISSING,
        default_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        super().__init__(converter, verifiers, alias, default, default_factory)
        self._converter: Optional[ConverterFactory] = None

    def supply_conversion_spec(self, spec: Optional[type]) -> None:
        # Cache the converter factory to avoid creating multiple times.
        self._converter = converter(spec)

    def create(self, cxt: ValidationContext) -> Validator:
        if self._converter is None:
            self._converter = converter(None)
        self.converter = self._converter
        return super().create(cxt)


def modeller(cls: type[T], /, _to_dict=ToDict()) -> Modeller[T]:
    """
    Get a modeller for given type.

    Args:
        cls: Type to find a modeller.
    Returns:
        A modeller for the type.
    """
    if is_dataclass(cls):
        return ToDataclass(cls)
    elif issubclass(cls, dict):
        return _to_dict # type: ignore
    else:
        return ToObject(cls)


#------------------------------------------------------------
# API
#------------------------------------------------------------
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
    if default is not MISSING and default_factory is not None:
        raise ValueError(f"Either default or default_factory must not be set.")

    if conv is ... or conv is None:
        return LazyValidatorFactory(..., [verifier(v) for v in vers], alias, default, default_factory)
    else:
        return ValidatorFactory(converter(conv), [verifier(v) for v in vers], alias, default, default_factory)


@dataclass_transform(kw_only_default=True, field_specifiers=(v,))
def validatable(**settings: Unpack[Configurable]) -> Callable[[T], T]:
    """
    A decorator for class to validate its instance under the given configurations.

    ```python
    >>> @validatable(skip_null=False, join_on_fail=False, strict_builtin=True)
    >>> class V:
    >>>     v1: int = v()
    >>>     v2: list[str] = v()
    ```

    This function also works as meta decorator which gives another decorator the ability to apply configurations to decorated type.

    ```python
    >>> @validatable(skip_null=False, join_on_fail=False, strict_builtin=True)
    >>> def meta(t):
    >>>     return t
    >>>
    >>> @meta
    >>> class V:
    >>>     v1: int = v()
    >>>     v2: list[str] = v()
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


def is_validatable(t: type) -> bool:
    """
    Check the type is validatable.

    Args:
        t: Type.
    Returns:
        Whether the type is decorated by `validatable` or its meta decorator.
    """
    return typed_config().get(t) is not None


class VerifierMethod(Verifier):
    """
    Wrapper of a method used as verifier.
    """
    def __init__(self, name: str, func: Callable, dependencies: dict[str, bool]):
        """
        Constructor.

        Args:
            name: Name of the verifier. If `None` , method name is used.
            func: Method to be used as verifier.
            dependencies: Dependencies to other fields. See `validate` decorator for details.
        """
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

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    def fulfill_dependencies(self, failures: CompositeValidationFailure) -> bool:
        """
        Check whether dependencies are fulfilled against given failures.

        Args:
            failures: Observed failures.
        Returns:
            Whether dependencies are fulfilled.
        """
        keys = failures.failures.keys()

        if self.negative & keys:
            return False
        elif self.positive and not (self.positive & keys):
            return True
        else:
            return not bool(keys)


def validate(_name_: Optional[str] = None, **dependencies: bool) -> Callable[[Callable], VerifierMethod]:
    """
    A decorator for method which works as verifier for validated instance.

    ```python
    class V:
        a: int = v(...)
        b: int = v(...)
        c: int = v(...)

        @validate("check_a", a=True, c=False)
        def check(self):
            ...
    ```

    Each key in `dependencies` specifies a field of the same name
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


class ParsedValidators:
    """
    Represents parsed validators from a class.

    The instance of this class can be passed to `validate_dict` instead of a class.
    In this case, parsing of validators is skipped.
    """
    def __init__(self, cls: type, validators: dict[str, ValidatorFactory]) -> None:
        #: The class from which validators are parsed.
        self.cls = cls
        #: Mapping of validator factories by their attribute names.
        self.validators = validators


def parse_validators(cls: type) -> ParsedValidators:
    """
    Parses a class and extracts validators for each attribute.

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

    # 3. Style in previous version which is no longer correct python code.
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
            factory.supply_conversion_spec(spec)
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

    return ParsedValidators(cls, validators | attr_validators)


def fetch_verifier_methods(cls, failures: CompositeValidationFailure) -> Iterable[VerifierMethod]:
    def to_vm(k):
        if not k.startswith("__"):
            value = getattr(cls, k)
            return value if isinstance(value, VerifierMethod) and value.fulfill_dependencies(failures) else None
        return None

    return filter(None, [to_vm(k) for k in dir(cls)])


def validate_dict(cls: Union[type[T], ParsedValidators], values: Any, context: Optional[ValidationContext] = None, *args, **kwargs) -> ValidationResult[T]:
    """
    Creates an instance of `cls` from dictionary-like object.

    `values` must be an object which can be interpreted as dictionary, that is, dict-like object.
    Each key-value pair is validated by a validator of the same key which is parsed from passed `cls` .

    If all validations succeed, the instance of `cls` is created with validated values.
    Otherwise, observed failures are collected into `CompositeValidationFailure` .
    This function returns `ValidationResult` which contains these values.

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
    ...     a: Annotated[int, +v()] = 0
    ...     b: Annotated[int, +v()] = 1
    ...     c: Annotated[int, v()] = 2
    ...     d: Annotated[int, v(lambda x: x < 0)] = 3
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
    validators = cls if isinstance(cls, ParsedValidators) else parse_validators(cls)

    with context.on(validators.cls):
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

        key_filter = context.config.key_filter or (lambda x: x)

        exsiting_keys = set(accessor.keys(values))

        for k, vf in validators.validators.items():
            key = key_filter(vf.alias or k)

            validated_keys.add(key)

            with context.child(k, True) as cxt:
                v = vf.create(cxt)
                val = accessor.get(values, key, v.accept_list) if key in exsiting_keys else VALUE_MISSING
                validated, f, use_alt = v.validate(val, cxt)

            # Validated value can be non-None even when the validation failed.
            if validated is not None:
                attributes[k] = validated
            if f:
                failures.add(k, f, key)
            if use_alt:
                _put_default(attributes, k, v, vf, validators.cls, cxt)

        if not context.config.ignore_remainders:
            share_context = context.config.share_context
            for k in accessor.keys(values):
                if k not in validated_keys:
                    if share_context:
                        holder = _holder_for_path(context.remainders, context.path + k)
                        holder[k] = values[k]
                    else:
                        context.remainders[k] = values[k]

        instance = modeller(validators.cls).create(attributes, *args, **kwargs)

        for m in fetch_verifier_methods(cls, failures):
            f = m.verify(instance, context)
            if f is not None:
                failures.add(m.name, f, None)

    return ValidationResult(instance, failures, context)


def _holder_for_path(holder, path):
    for key in path.path[:-1]:
        if key not in holder:
            holder[key] = {}
        holder = holder[key]

    return holder


def _put_default(attrs: dict[str, Any], key: str, validator: Validator, vf: ValidatorFactory, cls: type, context: ValidationContext) -> None:
    field = getattr(cls, key, MISSING)

    def put():
        if vf.default is not MISSING:
            attrs[key] = vf.default
        elif vf.default_factory:
            attrs[key] = vf.default_factory()
        elif context.config.implicit_default:
            rt = validator.converter.returns
            if rt is bool:
                attrs[key] = False
            elif rt in (int, float, Decimal):
                attrs[key] = 0
            elif rt is str:
                attrs[key] = ""
            elif rt is bytes:
                attrs[key] = b""
            elif rt is Any or parse_optional(rt) is not None:
                attrs[key] = None
            else:
                org = get_origin(rt)
                if org:
                    if issubclass(org, list):
                        attrs[key] = []
                else:
                    if issubclass(rt, list):
                        attrs[key] = []

    if field is not MISSING and not isinstance(field, ValidatorFactory):
        attrs[key] = field
    elif field is not MISSING:
        put()
        if is_dataclass(cls):
            # In dataclass, all fields will be initialized by its own scheme.
            # Thus no value should be supplied.
            pass
        elif key not in attrs:
            # To prevent instance attribute from referring class field, some value must be set.
            attrs[key] = None
    else:
        put()


ConverterSpec: TypeAlias = Any
VerifierSpec: TypeAlias = Any


def converter(
    func: Union[ConverterSpec, list[ConverterSpec], tuple[str, ConverterSpec]],
) -> ConverterFactory:
    """
    Creates a `ConverterFactory` by given specifier.

    Roughly speaking, `ConverterSpec` is a function which converts input value into another value,
    e.g., builtin type constructors like `int` or `float` can be a specifier because they work as such functions.

    When the specifier is paired with a string into a tuple, the string is used as the name of the created `Converter` .
    Besides, it can be passed in the form of a list to apply it to each item in iterable input values respectively.

    ```python
    converter(int)           # Input value is converted to int by applying builtin int function.
    converter(lambda x: x+1) # Add 1 to input value.
    converter(("test", int)) # Set converter name to 'test'
    converter([int])         # Apply builtin int function to each item in input iterable values.
    ```

    If the specifier is user-defined type, the converter expects dict-like input and calls `validate_dict()` with the type and the input,
    that is, it works as a nested validation.

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

    wrapper: Callable[[ConverterFactory], ConverterFactory] = lambda x: x

    def wrap(
        new: Callable[[ConverterFactory], ConverterFactory],
        cur: Callable[[ConverterFactory], ConverterFactory],
    ) -> Callable[[ConverterFactory], ConverterFactory]:
        return lambda x: cur(new(x))

    def is_list(v) -> tuple[bool, Any]:
        if isinstance(v, list):
            # [int]
            return True, v[0]
        elif get_origin(v) is list:
            # list[int]
            args = get_args(v)
            return True, (args[0] if args else Any)
        else:
            return False, v

    def is_opt(v) -> tuple[bool, Any]:
        opt = parse_optional(v)
        if opt is not None:
            return True, opt
        else:
            return False, v

    # Expand tuple specifier into name and function.
    name = None
    if isinstance(func, tuple) and len(func) == 2:
        name, func = func

    # Check iterable and optional.
    check = True
    while check:
        check, fn = is_list(func)
        if check:
            func = fn
            wrapper = wrap(ListFactory, wrapper)
            continue
        check, fn = is_opt(func)
        if check:
            wrapper = wrap(OptionalFactory, wrapper)
            func = fn
            continue

    # Get base factory.
    def user_defined(t: type, name) -> ConverterFactory:
        def create(v: Any, cxt: ValidationContext) -> t: # type: ignore
            return validate_dict(t, v, cxt).or_else(throw)
        return get_user_factory(t, name, create)

    def to_converter(fn, name=None) -> ConverterFactory:
        builtin = get_builtin_factory(fn, name)
        if builtin:
            return builtin
        elif isinstance(fn, partial):
            return get_factory(name or fn.func.__name__, analyze_callable(fn), *fn.args, **fn.keywords)
        elif isinstance(fn, type):
            if issubclass(fn, Enum):
                n, call = get_enum_conversion(fn)
                return get_factory(name or n, analyze_callable(call))
            else:
                return user_defined(fn, name)
        elif isinstance(fn, set):
            # Backward compatibility.
            t = next(iter(fn), None)
            if not isinstance(t, type):
                raise TypeError(f"Set specifier must contain only a type.")
            return user_defined(t, name)
        elif callable(fn):
            cc = analyze_callable(fn)
            name = name or getattr(fn, '__name__', 'Unknown')
            return get_factory(name, cc)
        else:
            raise TypeError(f"Given value is not valid Converter specifier: {fn}")

    base = to_converter(func, name)

    return wrapper(base)


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
            return fn._verifier(it)
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