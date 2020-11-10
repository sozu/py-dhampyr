from functools import wraps


class ValidationConfiguration:
    """
    Configurations for validation.

    Attributes
    ----------
    skip_null: bool
        If true, validator not prepended by `+` skips when the input is `None`.
    skip_empty: bool
        If true, validator not prepended by `+` skips when the input is empty.
    allow_null: bool
        If true, `+` prepended validator skips when the input is `None`.
    allow_empty: bool
        If true, `+` prepended validator skips when the input is empty.
    empty_specs: [(type, T -> bool)]
        Functions to check the value of specific type is empty or not.
    isinstance_buitin: bool
        If true, `Converter` declared by builtin type checks that the input is instance of the type instead of applying constructor.
    isinstance_any: bool
        If true, `Converter` declared by any type checks that the input is instance of the type instead of applying constructor.
    join_on_fail: bool
        If true, failed iterable values are joined into single `None`.
    ignore_remainders: bool
        If true, not validated values are simply discarded.
    share_context: bool
        If true, `ValidationContext` is shared in an invocation of `validate_dict()`.
    """
    def __init__(
        self,
        name = None,
        skip_null = None,
        skip_empty = None,
        allow_null = None,
        allow_empty = None,
        empty_specs = None,
        isinstance_builtin = None,
        isinstance_any = None,
        join_on_fail = None,
        ignore_remainders = None,
        share_context = None,
    ):
        self.name = name
        self.skip_null = skip_null
        self.skip_empty = skip_empty
        self.allow_null = allow_null
        self.allow_empty = allow_empty
        self.empty_specs = empty_specs
        self.isinstance_builtin = isinstance_builtin
        self.isinstance_any = isinstance_any
        self.join_on_fail = join_on_fail
        self.ignore_remainders = ignore_remainders
        self.share_context = share_context

    def derive(self, **kwargs):
        #kwargs.setdefault('empty_specs', [])
        return DerivingConfiguration(self, **kwargs)


class DerivingConfiguration(ValidationConfiguration):
    def __init__(self, base, **kwargs):
        super().__init__(**kwargs)
        self.base = base

    def __getattribute__(self, key):
        value = object.__getattribute__(self, key)
        return value if value is not None else getattr(self.base, key)

    def set(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.base, k):
                setattr(self, k, v)
            else:
                raise KeyError(f"Unknown configuration key: {k}")
        return self


class ConfigurationStack:
    """
    Stack of configurations which mocks `ValidationConfiguration`.
    """
    def __init__(self, base, stack=None):
        self.base = base
        self.stack = stack or []

    def __getattr__(self, key):
        for config in self.stack[::-1]:
            value = getattr(config, key)
            if value is not None:
                return value

        return getattr(self.base, key)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, stacktrace):
        if self.stack:
            self.pop()

    def on(self, t):
        config = type_config(t)
        if config:
            self.push(config)
        return self

    def derive(self, **kwargs):
        return DerivingConfiguration(self, **kwargs)

    def push(self, config):
        self.stack.append(config)
        return self

    def pop(self):
        self.stack.pop()
        return self


def default_config(config=ValidationConfiguration(
    name = "default",
    skip_null = True,
    skip_empty = True,
    allow_null = False,
    allow_empty = False,
    empty_specs = [],
    isinstance_builtin = False,
    isinstance_any = False,
    join_on_fail = True,
    ignore_remainders = False,
    share_context = False,
)):
    return config


def type_config(t, config=None, holder={}):
    if isinstance(config, ValidationConfiguration):
        holder[t] = config
    return holder.get(t, None)


def dhampyr(**kwargs):
    """
    Starts `with` context to modify default configuration or decorates a class to be applied certain configurations.

    When invoked alone, this function returns a context manager object.
    Updates done to attributes of the object in the context is applied to default configuration when exiting the context.

    >>> with dhampyr() as cfg:
    >>>     cfg.skip_null = False
    >>>     cfg.join_on_fail = False
    >>>     cfg.isinstance_builtin = True

    When used as decorator, validations for decorated class will be done under the given configurations.

    >>> @dhampyr(skip_null=False, join_on_fail=False, isinstance_builtin=True)
    >>> class V:
    >>>     v1: v(int)
    >>>     v2: v([str])

    This function also works as meta decorator which gives another decorator the ability to apply configurations to decorated type.

    >>> @dhampyr(skip_null=False, join_on_fail=False, isinstance_builtin=True)
    >>> def meta(t):
    >>>     return t
    >>>
    >>> @meta
    >>> class V:
    >>>     v1: v(int)
    >>>     v2: v([str])

    Parameters
    ----------
    kwargs: {str:object}
        Effective only when this function is used as a decorator. Attributes declared in `ValidationConfig` are available.
    """
    class Configurable:
        def __init__(self, **kw):
            self.kwargs = kw.copy()
            self.target = None
            self.config = ValidationConfiguration()

        def __call__(self, arg):
            if isinstance(arg, type):
                self.target = ValidationConfiguration(**self.kwargs)
                #from .validator import Validator
                #for k, v in [(k, v) for k, v in (arg.__annotations__ or {}).items() if isinstance(v, Validator)]:
                #    v.config = self.target
                type_config(arg, self.target)
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
                raise ValueError("The target of @dhampyr decorator must be a type or another decorator function.")

        def __enter__(self):
            if not self.target:
                self.target = default_config()
            return self.config

        def __exit__(self, exc_type, exc_value, traceback):
            if not exc_value:
                values = {}
                for k in vars(self.target):
                    v = getattr(self.config, k)
                    if v is not None:
                        values[k] = v
                        setattr(self.target, k, v)
            return False

    return Configurable(**kwargs)
