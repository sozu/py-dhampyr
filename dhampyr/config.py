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
    """
    def __init__(
        self,
        skip_null = None,
        skip_empty = None,
        allow_null = None,
        allow_empty = None,
        empty_specs = None,
        isinstance_builtin = None,
        isinstance_any = None,
        join_on_fail = None,
    ):
        self.skip_null = skip_null
        self.skip_empty = skip_empty
        self.allow_null = allow_null
        self.allow_empty = allow_empty
        self.empty_specs = empty_specs
        self.isinstance_builtin = isinstance_builtin
        self.isinstance_any = isinstance_any
        self.join_on_fail = join_on_fail

    def derive(self, **kwargs):
        kwargs.setdefault('empty_specs', self.empty_specs.copy())
        return DerivingConfiguration(self, **kwargs)


class DerivingConfiguration(ValidationConfiguration):
    def __init__(self, base, **kwargs):
        super().__init__(**kwargs)
        self.base = base

    def __getattribute__(self, key):
        value = object.__getattribute__(self, key)
        return value if value is not None else object.__getattribute__(self.base, key)

    def set(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.base, k):
                setattr(self, k, v)
            else:
                raise KeyError(f"Unknown configuration key: {k}")
        return self


def default_config(config=ValidationConfiguration(
    skip_null = True,
    skip_empty = True,
    allow_null = False,
    allow_empty = False,
    empty_specs = [],
    isinstance_builtin = False,
    isinstance_any = False,
    join_on_fail = True,
)):
    return config


def dhampyr(**kwargs):
    class Configurable:
        def __init__(self, **kw):
            self.kwargs = kw.copy()
            self.target = None
            self.config = ValidationConfiguration()

        def __call__(self, typ=None):
            if typ:
                self.target = default_config().derive(**self.kwargs)
                from .validator import Validator
                for k, v in [(k, v) for k, v in (typ.__annotations__ or {}).items() if isinstance(v, Validator)]:
                    v.config = self.target
            else:
                self.target = default_config()
            return typ

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
