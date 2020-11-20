from enum import Enum
import inspect
from functools import partial, wraps
from typing import get_type_hints
from .config import type_config
from .validator import Validator, ValidationResult
from .converter import Converter, is_builtin
from .verifier import Verifier
from .variable import Variable
from .converter import ValidationContext
from .failures import ValidationFailure, MalformedFailure, CompositeValidationFailure
from .requirement import Requirement, VALUE_MISSING

try:
    from werkzeug.datastructures import MultiDict
    is_multidict = lambda d: isinstance(d, MultiDict)
except ImportError:
    is_multidict = lambda d: False


def v(conv, *vers, key=None):
    """
    Creates a `Validator`.

    Parameters
    ----------
    conv: Converter
        Converter specifier. See `converter()` to know what kind of values are available.
    vers: [Verifier]
        Verifier specifiers. See `verifier()` to know what kind of values are available.
    key: str
        Key of the target value is the input dictionary. If `None`, declared attribute name is used to obtain the value.

    Returns
    -------
    Validator
        Created `Validator`.
    """
    c = converter(conv)
    vs = list(map(verifier, vers))
    return Validator(c, vs, key=key)


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


def validate(__name = None, **dependencies):
    def decorate(f):
        return VerifierMethod(__name or f.__name__, f, dependencies)
    return decorate


def parse_validators(cls):
    return {k:v for k, v in cls.__annotations__.items() if isinstance(v, Validator)}


def fetch_verifier_methods(cls, failures):
    def to_vm(k):
        if not k.startswith("__"):
            value = getattr(cls, k)
            return value if isinstance(value, VerifierMethod) and value.fulfill_dependencies(failures) else None
        return None

    return filter(None, [to_vm(k) for k in dir(cls)])


def validate_dict(cls, values, context=None, *args, **kwargs):
    """
    Creates an instance of `cls` from dictionary-like object.

    Names of attributes declared in `cls` and annotated with `Validator` are used as keys of `values`.
    Each `Validator` validates a value taken from `values` and, if valid, set the result to the attribute of created instance.
    Attributes where the validation fails are set to a value declared in `cls`.

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

    with context.on(cls):
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

        validated_keys = set()

        for k, v in validators.items():
            key = v.key or k

            validated_keys.add(key)

            val = get(values, key, v.accept_list) if key in values else VALUE_MISSING

            with context[k, True] as cxt:
                validated, f, use_alt = v.validate(val, cxt)

            if validated is not None:
                setattr(instance, k, validated)
            if f:
                failures.add(k, f)

            if use_alt and hasattr(cls, k):
                setattr(instance, k, getattr(cls, k))

        if not context.config.ignore_remainders:
            for k in values:
                # TODO: items() of MultiDict returns only first element associated with each key respectively.
                if k not in validated_keys:
                    if context.config.share_context:
                        holder = _holder_for_path(context.remainders, context.path + k)
                        holder[k] = values[k]
                    else:
                        context.remainders[k] = values[k]

        for m in fetch_verifier_methods(cls, failures):
            f = m.verify(instance, context)
            if f is not None:
                failures.add(m.name, f)

    return ValidationResult(instance, failures, context)


def _like_dictionary(values):
    return is_multidict(values) or (
        hasattr(values, '__contains__') \
            and hasattr(values, '__getitem__') \
            and hasattr(values, '__iter__') \
            and not isinstance(values, (list, str))
    )


def _holder_for_path(holder, path):
    for key in path.path[:-1]:
        if key not in holder:
            holder[key] = {}
        holder = holder[key]

    return holder


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
            t = next(iter(f), None)
            if not isinstance(t, type):
                raise TypeError(f"Set specifier must contain only a type.")
            def g(v, cxt: ValidationContext):
                r = validate_dict(t, v, cxt)
                return r.or_else(throw)
            return Converter(name or t.__name__, g, it, dict, t)
        elif isinstance(f, partial):
            ff, n, t_in, t_out, args, kwargs = analyze_specifier(f, (), {})
            return Converter(name or n, ff, it, t_in, t_out, False, *args, **kwargs)
        elif isinstance(f, type) and issubclass(f, Enum):
            # uses item access of the Enum.
            return Converter(name or f.__name__, f.__getitem__, it, str, f)
        elif isinstance(f, type):
            ff, n, t_in, t_out, args, kwargs = analyze_specifier(f, (), {})
            return Converter(name or n, ff, it, t_in, t_out, False, *args, **kwargs)
        elif callable(f):
            ff, n, t_in, t_out, args, kwargs = analyze_specifier(f, (), {})
            return Converter(name or n, ff, it, t_in, t_out, False, *args, **kwargs)
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
    elif isinstance(func, Variable):
        return func._verifier
    elif isinstance(func, partial):
        ff, n, t_in, t_out, args, kwargs = analyze_specifier(func, (), {})
        return Verifier(n, func, is_iter, *args, **kwargs)
    elif callable(func):
        return Verifier(func.__name__, func, is_iter)
    elif isinstance(func, tuple):
        ff, n, t_in, t_out, args, kwargs = analyze_specifier(func[1], (), {})
        return Verifier(func[0], func[1], is_iter, *args, **kwargs)
    else:
        raise TypeError("Given value is not valid Verifier specifier.")


def analyze_specifier(f, args, kwargs):
    """
    Extract informations from a specifier for `Converter` or `Verifier`.

    Parameters
    ----------
    f: type | partial | callable
        Specifier.
    args: (object)
        Accumulated indexed arguments.
    kwargs: {str:object}
        Accumulated keyword arguments.

    Returns
    -------
    callable
        Callable object to perform its specification by taking a value.
    str
        Name of the specifier.
    type
        Inferred input type, or `None` if no information is found.
    type
        Inferred output type, or `None` if no information is found.
    [object]
        Indexed arguments to pass to `Converter` or `Verifier`.
    {str:object}
        Keyword arguments to pass to `Converter` or `Verifier`.
    """
    if is_builtin(f):
        return f, f.__name__, f, f, args, kwargs
    elif isinstance(f, type):
        # check the second argument of constructor.
        params = _args_remains(f.__init__, args, kwargs)
        if params is None:
            # No signature is found. use as it is.
            return f, f.__name__, None, f, args, kwargs
        elif len(params) == 2:
            t_in = get_type_hints(f.__init__).get(params[1].name, None)
            return f, f.__name__, t_in, f, args, kwargs
        else:
            raise TypeError(f"Constructor of {f} must have an unassigned arguments.")
    elif isinstance(f, partial):
        # check the first argument of original function that is not assigned value.
        p_args = f.args
        p_kwargs = f.keywords

        args = args + p_args
        kwargs = dict(kwargs, **p_kwargs)

        r = analyze_specifier(f.func, args, kwargs)

        return (f, ) + r[1:]
    elif callable(f):
        # check the first argument.
        params = _args_remains(f, args, kwargs)
        if params is None:
            # No signature is found. use as it is.
            return f, f.__name__, None, None, args, kwargs
        elif len(params) == 1:
            hints = get_type_hints(f)
            return f, f.__name__, hints.get(params[0].name, None), hints.get('return', None), args, kwargs
        else:
            raise TypeError(f"Function {f} must have an unassigned arguments.")
    else:
        # unknown.
        raise TypeError(f"{f} is not available for the specifier of Converter or Verifier.")


def _args_remains(f, args, kwargs):
    try:
        params = list(inspect.signature(f).parameters.items())[len(args):]
    except Exception:
        return None
    params = [p for n, p in params if n not in kwargs and p.annotation != ValidationContext]
    no_defaults = [p for p in params if p.default is inspect.Parameter.empty]
    return params

