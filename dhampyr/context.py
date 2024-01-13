from collections.abc import Callable, Sequence
from functools import cached_property, partial
import inspect
from typing import Any, TypeVar, Optional, Union, Generic
from typing_extensions import Self, Unpack
from .config import default_config, Configurable, ValidationConfiguration, ConfigurationStack
from .failures import ValidationPath
from .util import get_self_args, is_builtin, alt_partial
from .builtins import builtin_conversions


T = TypeVar('T')
V = TypeVar('V')


class ContextAttributes:
    """
    Set of attributes in a context built in hierarchical form.
    """
    def __init__(self, parent: Optional[Self]):
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

    ```python
    >>> context = ValidationContext()
    >>> context.put(a=1, b=2)
    >>> context.a
    1
    ```

    Those attributes are also accessible from child contexts and able to be overwritten also.

    ```python
    >>> child = context["child"]
    >>> child.put(a=3)
    >>> (child.a, child.b)
    (3, 2)
    ```

    Each context works on its own `ValidationConfiguration` which is set to be global configuration by default.
    The configuration controls the behavior of validation logics internally.
    It can be overwritten by `configure()` without any effect on global or parent configuration.

    Additionally, each context stores values which are not validated but exist in the input as a result of validation.
    The context returned by `validate_dict()` has `remainders` property holding those values.
    Be aware that this dictionary is not cleared automatically when a context instance is reused.
    """
    @classmethod
    def default(cls, holder=[]):
        """
        Returns shared context instance which contains no attributes and refer default configuration.

        Do not call this method from application code.
        """
        if not holder:
            holder.append(cls())
        return holder[0]

    class Stack(ConfigurationStack):
        """
        Configuration stack in context.

        Priority of configuration is context specific > typed > base.
        """
        def __init__(self, base: ValidationConfiguration) -> None:
            super().__init__(base)
            self.contextual: Configurable = {}

        def set(self, settings: Configurable):
            self.contextual.update(settings)

        def __getattr__(self, key: str) -> Any:
            if key in self.contextual:
                return self.contextual[key]
            base = self.base
            while isinstance(base, ValidationContext.Stack):
                if key in base.contextual:
                    return base.contextual[key]
                base = base.base

            return super().__getattr__(key)

        def __enter__(self):
            pass

        def __exit__(self, exc_type, exc_value, stacktrace):
            self.pop()

    def __init__(
        self,
        path: Optional[ValidationPath] = None,
        parent: Optional[Self] = None,
        config: Optional[ValidationConfiguration] = None,
    ) -> None:
        #: Path where this context is used.
        self.path = path or ValidationPath([])
        #: Input values which were not used in the validation.
        self.remainders = {}
        self._contexts = {}
        self._parent = parent
        self._attributes = ContextAttributes(parent._attributes if parent else None)

        # parent or config is exclusive. parent is prior if both are passed.
        self._config: ValidationContext.Stack
        if parent is not None:
            self._config = parent._config.derive()
        else:
            self._config = ValidationContext.Stack(config or default_config().derive())

    def __contains__(self, key: Union[int, str]) -> bool:
        """
        Checks if the context of passed child key exists.

        Args:
            key: Key or index of a child context.
        Returns
            Child context. If context does not exist on the key yet, new context is created and returned.
        """
        return key in self._contexts

    def __getitem__(self, key: Union[int, str, tuple[Union[int, str], bool]]) -> Self:
        """
        Returns child context by its key.

        Args:
            key: Key or index of a child context.
        Returns
            Child context. If context does not exist on the key yet, new context is created and returned.
        """
        # Tuple can be passed only by internal call.
        key, internal_call = key if isinstance(key, tuple) else (key, False)

        if self.config.share_context:
            if internal_call:
                self.path += key
            return self
        else:
            return self._contexts.setdefault(key, ValidationContext(self.path + key, parent=self))

    def __getattr__(self, key: str) -> Any:
        """
        Returns contextual attribute for the key.

        Args:
            key: Attribute key.
        Returns:
            Attribute value.
        Raises:
            AttributeError: When contextual value for the key is not found.
        """
        return getattr(self._attributes, key)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, stacktrace):
        if self.config.share_context and (not self._parent or self._parent.config.share_context):
            self.path.pop()

    def on(self, t: type) -> ValidationConfiguration:
        """
        Starts context validating a dictionary for given type.

        Args:
            t: Type for validation.
        Returns:
            This instance.
        """
        return self._config.on(t)

    def put(self, **attributes: Any) -> Self:
        """
        Put arbitrary attributes to this context.

        Args:
            attributes: Key-values pairs of attributes.
        Returns:
            This instance.
        """
        for k, v in attributes.items():
            self._attributes._attributes[k] = v
        return self

    @property
    def config(self) -> ValidationConfiguration:
        """
        Configuration used in this context.

        Don't modify this object directly, use `configure()` instead.

        Returns:
            Configuration used in this context.
        """
        return self._config # type: ignore

    def configure(self, **settings: Unpack[Configurable]) -> Self:
        """
        Set this context's own configuration parameters.

        Args:
            settings: Attributes `ValidationConfiguration` .
        Returns:
            This instance.
        """
        self._config.set(settings)
        return self


class ContextualCallable(Generic[T, V]):
    def __init__(
        self,
        func: Callable,
        param: inspect.Parameter,
        context_params: Sequence[inspect.Parameter],
    ) -> None:
        self.func = func
        self.signature = _signature(func)
        self.param = param
        self.context_params = context_params

    @cached_property
    def in_type(self) -> Any:
        args = get_self_args(self)
        return args and args[0] or Any

    @cached_property
    def out_type(self) -> Any:
        args = get_self_args(self)
        return args[1] if len(args) > 0 else Any

    def __call__(self, value: T, context: ValidationContext) -> V:
        ba = self.signature.bind_partial()
        ba.apply_defaults()

        if self.param.kind is inspect.Parameter.VAR_POSITIONAL:
            var_args = list(ba.arguments.get(self.param.name, []))
            ba.arguments[self.param.name] = tuple(var_args + [value])
        else:
            ba.arguments[self.param.name] = value

        for p in self.context_params:
            ba.arguments[p.name] = context

        return self.func(*ba.args, **ba.kwargs)


def analyze_callable(func: Callable) -> ContextualCallable:
    """
    Analyzes a callable into the objects designed for the invocation in convertion / verification phase.

    `func` is a callable which has at least an argument for the input value.
    Optionally, it can have one more argument for `ValidationContext` which must be annotated with the type.

    Args:
        func: Callable object.
    Returns:
        Wrapper of passed callable.
    """
    sig = _signature(func)

    no_context = sig.replace(parameters=[p for p in sig.parameters.values() if p.annotation != ValidationContext])

    value_cands = [p for p in no_context.parameters.values() if p.default is inspect.Parameter.empty and p.kind != inspect.Parameter.VAR_KEYWORD]

    num = len(value_cands)
    if num == 0:
        raise TypeError(f"Given callable does not have parameter for an input value.")
    elif num == 1:
        input_param = value_cands[0]
    elif len(value_cands) == 2:
        if value_cands[0].kind != inspect.Parameter.VAR_POSITIONAL:
            if value_cands[1].kind != inspect.Parameter.VAR_POSITIONAL:
                raise TypeError(f"Arguments of the callable are not fulfilled by preset arguments: {[p.name for p in value_cands]}")
            else:
                input_param = value_cands[0]
        else:
            input_param = value_cands[1]
    else:
        raise TypeError(f"Arguments of the callable are not fulfilled by preset arguments: {[p.name for p in value_cands]}")

    # Find arguments for context.
    context_params = [p for p in sig.parameters.values() if p.name not in no_context.parameters]

    in_type = input_param.annotation if input_param.annotation != inspect.Signature.empty else Any
    out_type = sig.return_annotation if sig.return_annotation != inspect.Signature.empty else Any

    # TypeError will raise when arguments don't match.
    return ContextualCallable[in_type, out_type](func, input_param, context_params)


def _signature(func) -> inspect.Signature:
    # workaround for partial which raises ValueError if it wraps builtin type such as int.
    if isinstance(func, partial):
        def alternate(f: Any) -> Any:
            conv = builtin_conversions.get(f)
            if conv:
                return conv[1]
            elif is_builtin(f):
                return f.__init__
            else:
                return None
        func = alt_partial(func, alternate)
        return inspect.signature(func)
    else:
        return inspect.signature(func.__init__ if is_builtin(func) else func)