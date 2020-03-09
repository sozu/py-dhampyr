from enum import Enum
from functools import partial
from typing import get_type_hints
from .validator import Validator, ValidationResult
from .converter import Converter
from .verifier import Verifier
from .config import default_config
from .converter import ValidationContext
from .failures import ValidationFailure, MalformedFailure, CompositeValidationFailure
from .requirement import Requirement, VALUE_MISSING

try:
    from werkzeug.datastructures import MultiDict
    is_multidict = lambda d: isinstance(d, MultiDict)
except ImportError:
    is_multidict = lambda d: False


def v(conv, *vers):
    """
    Creates a `Validator`.

    Parameters
    ----------
    conv: Converter equivalent
        Value available for the argument of `converter`.
    vers: [Verifier equivalents]
        Values available for the argument of `verifier`.

    Returns
    -------
    Validator
        Created `Validator`.
    """
    config = default_config()
    c = converter(conv)
    vs = list(map(verifier, vers))
    return Validator(c, vs)


def parse_validators(cls):
    return {k:v for k, v in cls.__annotations__.items() if isinstance(v, Validator)}


def validate_dict(cls, values, context=None, *args, **kwargs):
    """
    Creates an instance of `cls` from dictionary-like object.

    Names of attributes declared in `cls` and annotated with `Validator` are used as keys of `values`.
    Each `Validator` converts and verifies a value obtained from `values` with the key and, if valid, assigns the converted value to craated instance of `cls` as an attribute.
    In case the validation fails, declared value of the attribute is assigned instead.

    `values` must be a dictionary-like object whose type fulfills following conditions.

    - It is `werkzeug.datastructures.MultiDict`.
    - or
        - it is neither `list` nor `str`
        - and it declares `__contains__`, `__getitem__`, `__iter__` correctly.

    Giving `values` which is not dictionary-like causes `MalformedFailure` as a result.
    Additionary, all keys iterated by `__iter__` must be safely available for the argument of `__getitem__`, otherwise runtime exception will occur.

    Parameters
    ----------
    cls: type
        Type of the instance to create.
    values: dict
        Dictionay-like object.
    context: ValidationContext
        Root context of this validation suite.
    args, kwargs: list, dict
        Optional arguments which are propagated to the constructor of `cls`.

    Returns
    -------
    ValidationResult
        An object having created instance and error informations.

    Examples
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
    """
    context = context or ValidationContext()

    if not _like_dictionary(values):
        return ValidationResult(None, MalformedFailure(), context)

    instance = cls(*args, *kwargs)

    def get(d, k, as_list):
        if as_list:
            return d.getlist(k) if is_multidict(d) else d[k]
        else:
            return d[k]

    failures = CompositeValidationFailure()

    validators = parse_validators(cls)

    for k, v in validators.items():
        cxt = context[k]

        val = get(values, k, v.accept_list) if k in values else VALUE_MISSING

        validated, f, use_alt = v.validate(val, cxt)

        if validated:
            setattr(instance, k, validated)
        if f:
            failures.add(k, f)

        if use_alt and hasattr(cls, k):
            setattr(instance, k, getattr(cls, k))

    # TODO: items() of MultiDict returns only first element associated with each key respectively.
    for k in values:
        if k not in validators:
            context.remainders[k] = values[k]

    return ValidationResult(instance, failures, context)


def _like_dictionary(values):
    return is_multidict(values) or (
        hasattr(values, '__contains__') \
            and hasattr(values, '__getitem__') \
            and hasattr(values, '__iter__') \
            and not isinstance(values, (list, str))
    )


def _unpack_partial(p, args, kwargs):
    args += p.args
    kwargs.update(p.keywords)
    if isinstance(p.func, partial):
        return _unpack_partial(p.func, args, kwargs)
    else:
        return p.func


def converter(func):
    """
    Creates a `Converter` by given specifier.

    Parameters
    ----------
    func: spec, [spec], (str, spec), [(str, spec)]
        The specifier of `Converter` which can take various forms and determines the attributes and behaviors of `Converter`.
        When it is declared as a list having a specifier,
        the `Converter` deals with an input as iterable object and tries to apply inner converting function to each value.
        If a tuple of string and specifier is given, the string is used as the name of the `Converter`. 
        Otherwise, its name is determined by `__name__` attribute of the specifier object.
        The specifier object which corresponds to a converting function also can take various forms as follows.
        - If `Enum`, the `Converter` converts a value to the `Enum` type via item access.
        - If `callable`, it is used as the converting function of the `Converter`.
        - If a `set` of a type, the `Converter` invokes `validate_dict` with the type and input value, that is, executes nested validation.

    Returns
    -------
    Converter
        Created `Converter`.
    """
    def throw(e):
        raise e

    def to_converter(f, it, name=None):
        if isinstance(f, set):
            # runs nested validation with a type in the set.
            t = next(iter(f))
            def g(v, cxt: ValidationContext):
                r = validate_dict(t, v, cxt)
                return r.or_else(throw)
            return Converter(name or t.__name__, g, it, t)
        elif isinstance(f, partial):
            args = []
            kwargs = {}
            origin = _unpack_partial(f, args, kwargs)
            inferred = None
            if isinstance(origin, type):
                inferred = origin
            else:
                inferred = get_type_hints(origin).get('return', None)
            return Converter(origin.__name__, f, it, inferred, *args, **kwargs)
        elif isinstance(f, type) and issubclass(f, Enum):
            # uses item access of the Enum.
            return Converter(name or f.__name__, f.__getitem__, it, f)
        elif isinstance(f, type):
            # invokes constructor.
            return Converter(name or f.__name__, f, it, f)
        elif callable(f):
            # invokes function.
            return Converter(name or f.__name__, f, it, get_type_hints(f).get('return', None))
        else:
            raise TypeError("Given value is not valid Converter specifier.")

    func, is_iter = (func[0], True) if isinstance(func, list) else (func, False)

    if isinstance(func, Converter):
        return func
    elif isinstance(func, tuple) and len(func) == 2:
        return to_converter(func[1], is_iter, name=func[0])
    else:
        return to_converter(func, is_iter)


def verifier(func):
    """
    Creates a `Verifier` by given specifier.

    Parameters
    ----------
    func: callable, [callable], (str, callable), [(str, callable)]
        The specifier of `Verifier` which can take various forms and determines the attributes and behaviors of `Verifier`.
        When it is declared as a list having a specifier,
        the `Verifier` deals with an input as iterable object and tries to apply inner verifying function to each value.
        If a tuple of string and callable is given, the string is used as the name of the `Verifier`. 
        Otherwise, its name is determined by `__name__` attribute of the callable object.
        The callable should be a function taking an input and returns boolean value representing the result of the verification.

    Returns
    -------
    Verifier
        Created `Verifier`.
    """
    func, is_iter = (func[0], True) if isinstance(func, list) else (func, False)

    if isinstance(func, Verifier):
        return func
    elif isinstance(func, partial):
        args = []
        kwargs = {}
        origin = _unpack_partial(func, args, kwargs)
        return Verifier(origin.__name__, func, is_iter, *args, **kwargs)
    elif callable(func):
        return Verifier(func.__name__, func, is_iter)
    elif isinstance(func, tuple):
        return Verifier(func[0], func[1], is_iter)
    else:
        raise TypeError("Given value is not valid Verifier specifier.")