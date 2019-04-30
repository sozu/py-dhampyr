from enum import Enum
from functools import reduce, partial

try:
    from werkzeug.datastructure import MultiDict
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
    c = converter(conv)
    vs = list(map(verifier, vers))
    return Validator(c, vs)

def validate_dict(cls, values, *args, **kwargs):
    """
    Creates an instance of `cls` from dictionary-like object.

    Names of attributes declared in `cls` and annotated with `Validator` are used as keys of `values`.
    Each `Validator` converts and verifies a value obtained from `values` with the key and, if valid, assigns the converted value to craated instance of `cls` as an attribute.
    In case the validation fails, declared value of the attribute is assigned instead.

    Parameters
    ----------
    cls: type
        Type of instance to create.
    values: dict
        Dictionay-like object.
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
    instance = cls(*args, *kwargs)
    failures = CompositeValidationFailure()

    def get(d, k, as_list):
        if as_list:
            return d.getlist(k) if is_multidict(d) else d[k]
        else:
            return d[k]

    for k, v in filter(lambda kv: isinstance(kv[1], Validator), cls.__annotations__.items()):
        if k in values:
            validated, failure = v.validate(get(values, k, v.accept_list))
            if failure:
                failures.add(k, failure)
                setattr(instance, k, getattr(cls, k))
            else:
                setattr(instance, k, validated)
        else:
            if v.requires:
                failures.add(k, MissingFailure())
            setattr(instance, k, getattr(cls, k))

    return ValidationResult(instance, failures)

class ValidationResult:
    """
    A type of returning value of `validate_dict`.

    Attributes
    ----------
    failures: CompositeValidationfailure
        An object providing accessor of validation failures.
    """
    def __init__(self, validated, failures):
        self.validated = validated
        self.failures = failures

    def get(self):
        """
        Returns an instance created in `validate_dict`

        Returns
        -------
        object
            Created instance of type determined by first argument of `validate_dict`.
        """
        return self.validated

    def or_else(self, handler):
        """
        Returns an instance created in `validate_dict` if the validation succeeded, otherwise executes `handler`.

        Parameters
        ----------
        handler: CompositeValidationFailure -> any
            A function which takes validation failures.
        """
        if len(self.failures.failures) == 0:
            return self.validated
        else:
            return handler(self.failures)

class ValidationFailure(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def args(self):
        return []

    @property
    def kwargs(self):
        return {}

def at(positions):
    def exp(i, p):
        if isinstance(p, str):
            return p if i == 0 else f".{p}"
        elif isinstance(p, int):
            return f"[{p}]"
        else:
            return ""
    return ''.join([exp(i, p) for i, p in enumerate(positions)])

class ValidationPath:
    def __init__(self, path):
        self.path = path

    def __iter__(self):
        return iter(self.path)

    def __repr__(self):
        return at(self.path)

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

    def __iter__(self, pos=[]):
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
        return self.failures[key]

    def __contains__(self, key):
        return key in self.failures

    def add(self, key, f):
        self.failures[key] = f

class MissingFailure(ValidationFailure):
    """
    Validation failure representing that a required attribute is not found.
    """
    def __init__(self):
        super().__init__("This value is required.")

    @property
    def name(self):
        return "missing"

class Validator:
    def __init__(self, converter, verifiers, requires=False):
        self.converter = converter
        self.verifiers = verifiers
        self.requires = requires

    def __pos__(self):
        self.requires = True
        return self

    @property
    def accept_list(self):
        return self.converter.is_iter

    def validate(self, value):
        """
        Converts and verfies a value.

        Parameters
        ----------
        value: object
            An input value.

        Returns
        -------
        (object, Exception)
            The pair of converted value (``None`` if the validation fails) and validation failure (``None`` if the validation succeeds).
        """
        val, failure = self.converter.convert(value)
        if failure:
            return None, failure

        for verifier in self.verifiers:
            f = verifier.verify(val)
            if f is not None:
                return None, f

        return val, None

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
            def g(v):
                r = validate_dict(t, v)
                return r.or_else(throw)
            return Converter(name or t.__name__, g, it)
        elif isinstance(f, partial):
            return Converter(f.func.__name__, f, it, *f.args, **f.keywords)
        elif isinstance(f, type) and issubclass(f, Enum):
            # uses item access of the Enum.
            return Converter(name or f.__name__, f.__getitem__, it)
        elif isinstance(f, type):
            # invokes constructor.
            return Converter(name or f.__name__, f, it)
        elif callable(f):
            # invokes function.
            return Converter(name or f.__name__, f, it)
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
        return Verifier(func.func.__name__, func, is_iter, *func.args, **func.keywords)
    elif callable(func):
        return Verifier(func.__name__, func, is_iter)
    elif isinstance(func, tuple):
        return Verifier(func[0], func[1], is_iter)
    else:
        raise TypeError("Given value is not valid Verifier specifier.")

class ConversionFailure(ValidationFailure):
    def __init__(self, message, converter=None):
        super().__init__(message)
        self.message = message
        self.converter = converter

    @property
    def name(self):
        return self.converter.name

    @property
    def args(self):
        return self.converter.args

    @property
    def kwargs(self):
        return self.converter.kwargs

class Converter:
    def __init__(self, name, func, is_iter, *args, **kwargs):
        self.name = name
        self.func = func
        self.is_iter = is_iter
        self.args = args
        self.kwargs = kwargs

    def convert(self, value):
        def conv(v):
            try:
                return self.func(v), None
            except ConversionFailure as e:
                e.converter = e.converter or self
                return None, e
            except ValidationFailure as e:
                return None, e
            except Exception as e:
                return None, ConversionFailure(str(e), self)

        if self.is_iter:
            vs = [conv(v) for v in value]
            failures = [(i, f) for i, (v, f) in enumerate(vs) if f is not None]
            if len(failures) == 0:
                return [v for v,f in vs], None
            else:
                composite = CompositeValidationFailure()
                for i, f in failures:
                    composite.add(i, f)
                return None, composite
        else:
            return conv(value)

class VerificationFailure(ValidationFailure):
    def __init__(self, message, verifier=None):
        super().__init__(message)
        self.message = message
        self.verifier = verifier

    @property
    def name(self):
        return self.verifier.name

    @property
    def args(self):
        return self.verifier.args

    @property
    def kwargs(self):
        return self.verifier.kwargs

class Verifier:
    def __init__(self, name, func, is_iter, *args, **kwargs):
        self.name = name
        self.func = func
        self.is_iter = is_iter
        self.args = args
        self.kwargs = kwargs

    def verify(self, value):
        def ver(v):
            try:
                return None if self.func(v) else VerificationFailure(f"Verification by {self.name} failed.", self)
            except VerificationFailure as e:
                e.verifier = e.verifier or self
                return e
            except ValidationFailure as e:
                return e
            except Exception as e:
                return VerificationFailure(str(e), self)

        if self.is_iter:
            failures = [(i, f) for i, f in enumerate(map(ver, value)) if f is not None]
            if len(failures) == 0:
                return None
            else:
                composite = CompositeValidationFailure()
                for i, f in failures:
                    composite.add(i, f)
                return composite
        else:
            return ver(value)