from collections import OrderedDict
from .config import default_config, ValidationConfiguration, ConfigurationStack
from .failures import CompositeValidationFailure, ValidationPath


class ContextAttributes:
    def __init__(self, parent):
        self._parent = parent
        self._attributes = {}

    def __getattr__(self, key):
        if key in self._attributes:
            return self._attributes[key]
        elif self._parent:
            return self._parent.__getattr__(key)
        else:
            raise AttributeError(f"This context has no attribute '{key}'.")


class ValidationContext:
    """
    Represents execution context for a validation suite.

    A context is generated and works for each input which is dictionary-like object.
    Each key in the object has its own context and the nested validation produces context hierarchy.

    The context is available to pass informations to validation logics via its attributes set beforehand by `put()`.

    >>> context = ValidationContext()
    >>> context.put(a=1, b=2)
    >>> context.a
    1

    Those attributes are also accessible from child contexts and able to be overwritten also.

    >>> child = context["child"]
    >>> child.put(a=3)
    >>> (child.a, child.b)
    (3, 2)

    Each context works on its own `ValidationConfiguration` which is set to be global configuration by default.
    The configuration controls the behavior of validation logics internally.
    It can be overwritten by `configure()` without any effect to global or parent configuration.

    Additionally, each context stores values which are not validated but exist in the input as a result of validation.
    The context returned by `validate_dict()` has `remainders` property holding those values.
    Be aware that this dictionary is not cleared automatically when a context instance is reused.

    Attributes
    ----------
    path: ValidationPath
        Validation path where this context works.
    remainders: {str: object}
        Dictionary holding values which were not validated.
    """
    @classmethod
    def default(cls, holder=[]):
        """
        Returns shared context instance which contains no attributes and refer default configuration.

        Do not call this method from application code.
        """
        if not holder:
            holder.append(cls(config = default_config().derive()))
        return holder[0]

    def __init__(self, path=None, parent=None, config=None):
        self._contexts = {}
        self.path = path or ValidationPath([])
        self.remainders = {}
        self._parent = parent
        self._config_stack = parent._config_stack if parent else ConfigurationStack(default_config())
        self._config = config or (None if parent else self._config_stack.derive())
        self._attributes = ContextAttributes(parent._attributes if parent else None)

    def __contains__(self, key):
        return key in self._contexts

    def __getitem__(self, key):
        """
        Returns child context by its key.

        Parameters
        ----------
        key: str | int
            Key or index of a child context.

        Returns
        -------
        ValidationContext
            Child context. If context does not exist on the key yet, new context is created and returned.
        """
        key, internal_call = key if isinstance(key, tuple) else (key, False)

        if self.config.share_context:
            if internal_call:
                self.path += key
            return self
        else:
            return self._contexts.setdefault(key, ValidationContext(
                self.path + key,
                parent=self,
            ))

    def __getattr__(self, key):
        return getattr(self._attributes, key)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, stacktrace):
        if self.config.share_context and (not self._parent or self._parent.config.share_context):
            self.path.pop()

    def on(self, type_):
        """
        Starts context validating a dictionary for given type.

        Parameters
        ----------
        type_: type
            Type to assign values by validate_dict().

        Returns
        -------
        ConfigurationStack.TypeContext
            A context object.
        """
        return self._config_stack.on(type_)

    def put(self, **attributes):
        """
        Put arbitrary attributes to this context.

        Parameters
        ----------
        attributes: {str:object}
            Key-values pairs of attributes.

        Returns
        -------
        ValidationContext
            This instance.
        """
        for k, v in attributes.items():
            self._attributes._attributes[k] = v
        return self

    @property
    def config(self):
        """
        Configuration used in this context.

        Don't modify this object directly, use `configure()` instead.

        Returns
        -------
        ValidationConfiguration
            Configuration used in this context.
        """
        return self._config if self._config else self._parent.config

    def configure(self, **kwargs):
        """
        Set this context's own configuration parameters.

        Parameters
        ----------
        kwargs: {str:object}
            Attributes declared in `ValidationConfig` are available. Unknown key raises `KeyError`.

        Returns
        -------
        ValidationContext
            This instance.
        """
        if self._config:
            self._config.set(**kwargs)
        else:
            self._config = self._parent.config.derive() 
            self._config.set(**kwargs)
        return self


def contextual_invoke(f, v, context):
    """
    Invokes a function which takes one positional argument.

    Given context is passed if the function takes `ValidationContext` via an annotated keyword argument.

    Parameters
    ----------
    f: Callable[T] -> U
        A function which takes on positional argument.
    v: T
        An object passed to the function.
    context: ValidationContext
        A context passed to the function if it takes `ValidationContext` via an annotated keyword argument.

    Returns
    -------
    U
        Returned value from the function.
    """
    anns = f.__annotations__ if hasattr(f, "__annotations__") else {}
    c = next(filter(lambda a: a[1] is ValidationContext, anns.items()), None)
    return f(v, **{c[0]: context or ValidationContext()}) if c else f(v)
