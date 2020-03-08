from collections import OrderedDict
from .failures import CompositeValidationFailure, ValidationPath


class ValidationContext:
    """
    Represents execution context for a validation suite.

    Contexts are generated for each validating value respectively and they are managed under root context in tree structure.

    TODO Enable assigning arbitrary values as an attribute to use runtime values in validation suite.

    Attributes
    ----------
    remainders: {str: object}
        Dictionary holding values which was not validated.
    """
    def __init__(self, path=None):
        self._contexts = {}
        self._remainders = {}
        self.path = path or ValidationPath([])
        self.joint_failure = True

    @property
    def remainders(self):
        return self._remainders

    def __getitem__(self, key):
        """
        Returns child context by its key.

        Parameters
        ----------
        key: str
            Key of a child context.

        Returns
        -------
        ValidationContext
            Child context if exists, otherwise `KeyError` is raised.
        """
        return self._contexts[key]

    def descend(self, key, is_iter):
        """
        Add a child context by its key if it does not exist.

        Parameters
        ----------
        key: str | [str]
            Key of a child context.
        is_iter: bool
            `True` if the child is iterative, otherwise `False`.

        Returns
        -------
        ValidationContext
            Added or found child context.
        """
        if is_iter:
            return self._contexts.setdefault(key, IterativeContext(self.path + key))
        else:
            return self._contexts.setdefault(key, ValidationContext(self.path + key))


class IterativeContext(ValidationContext):
    def __init__(self):
        super().__init__()
        self._item_contexts = []

    @property
    def remainders(self):
        return [c.remainders for c in self._item_contexts]

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._item_contexts[key]
        else:
            return [c[key] for c in self._item_contexts]

    def append(self):
        c = ValidationContext(self.path + len(self._item_contexts))
        self._item_contexts.append(c)
        return c


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
