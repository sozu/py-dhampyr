from collections import OrderedDict
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

    Contexts are generated for each validating value respectively and they are managed under root context in tree structure.

    Attributes
    ----------
    remainders: {str: object}
        Dictionary holding values which was not validated.
    """
    def __init__(self, path=None, joint_failure=None, parent=None):
        self._contexts = {}
        self.remainders = {}
        self.path = path or ValidationPath([])
        self.joint_failure = joint_failure if joint_failure is not None else  parent.joint_failure if parent else True
        self._attributes = ContextAttributes(parent._attributes if parent else None)

    def __contains__(self, key):
        return key in self._contexts

    def put(self, **attributes):
        for k, v in attributes.items():
            self._attributes._attributes[k] = v
        return self

    def __getattr__(self, key):
        return getattr(self._attributes, key)

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
        return self._contexts.setdefault(key, ValidationContext(
            self.path + key,
            joint_failure=self.joint_failure,
            parent=self,
        ))


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
