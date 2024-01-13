from collections.abc import Callable, Iterable
from functools import cached_property
import inspect
from typing import Any, TypeVar, Generic, Optional, Union, Protocol
from dhampyr.builtins import Any
from .context import ValidationContext, analyze_callable, ContextualCallable
from .failures import ValidationFailure, CompositeValidationFailure, PartialFailure
from .builtins import *
from .util import get_self_args, isinstance_safe


T = TypeVar('T')
V = TypeVar('V')


class ConversionFailure(ValidationFailure):
    """
    Represents a failure which arised in conversion phase.
    """
    def __init__(self, message, converter):
        super().__init__(
            name=converter.name,
            message=message,
            args=converter.args,
            kwargs=converter.kwargs,
        )
        self.converter = converter


class Converter(Generic[T, V]):
    """
    This class provides the interface to convert the value into specified type.

    Do not create the instance directly, use `ConverterFactory` instead
    because available input which determines validation schema can be changed by configurations in context.
    """
    def __init__(self, name: str, func: Callable, is_iter: bool, *args, **kwargs):
        #: The name of the converter used for error message.
        self.name = name
        #: Function converting a value.
        self.func = func
        #: Flag to interpret input value as iterable object and convert each value respectively.
        self.is_iter = is_iter
        self.args = args
        self.kwargs = kwargs

    @cached_property
    def accepts(self) -> Any:
        """
        Returns a type hint for the value this converter accepts.
        """
        args = get_self_args(self)
        return args and args[0] or Any

    @cached_property
    def returns(self) -> Any:
        """
        Returns a type hint for the value this converter returns.
        """
        args = get_self_args(self)
        return args[1] if len(args) > 0 else Any

    def convert(self, value: Any, context: Optional[ValidationContext] = None) -> tuple[Optional[Any], Optional[ValidationFailure]]:
        """
        Converts a value with conversion function.

        Args:
            value: A value to convert.
            context: Context for the value.
        Returns:
            If conversion succeeds, converted value and `None`, otherwise, `None` and failure object.
        """
        def conv(v, i=None):
            try:
                cc = self.func if isinstance(self.func, ContextualCallable) else analyze_callable(self.func)
                if context and i is not None:
                    with context[i, True] as c:
                        return cc(v, c), None
                else:
                    # REVIEW: How to generate empty context?
                    return cc(v, context or ValidationContext()), None
            except PartialFailure as e:
                return None, e.create(converter=self)
            except ValidationFailure as e:
                return None, e
            except Exception as e:
                return None, ConversionFailure(str(e), self)

        if self.is_iter:
            results = [conv(v, i) for i, v in enumerate(value)]
            failures = [(i, f) for i, (v, f) in enumerate(results) if f is not None]
            if len(failures) == 0:
                return [v for v,f in results], None
            else:
                composite = CompositeValidationFailure()
                for i, f in failures:
                    composite.add(i, f)
                if context and not context.config.join_on_fail:
                    return [None if f else v for v, f in results], composite
                else:
                    return None, composite
        else:
            return conv(value)


class ConverterFactory(Protocol):
    args: Any
    kwargs: Any
    def create(self, context: ValidationContext) -> Converter:
        ...


class SingleValueFactory(ConverterFactory):
    def __init__(
        self,
        name: str,
        func: Callable[[ValidationContext], Callable],
        *args,
        **kwargs,
    ) -> None:
        self.name = name
        self.func = func
        self.args = args
        self.kwargs: Any = kwargs

    def create(self, context: ValidationContext) -> Converter:
        call = self.func(context)
        cc = call if isinstance(call, ContextualCallable) else analyze_callable(call)
        return Converter[cc.in_type, cc.out_type](self.name, cc, False, *self.args, **self.kwargs)


class ListFactory(ConverterFactory):
    def __init__(self, base: ConverterFactory) -> None:
        self.base = base

    @property
    def args(self) -> Any:
        return self.base.args

    @property
    def kwargs(self) -> Any:
        return self.base.kwargs

    def create(self, context: ValidationContext) -> Converter:
        converter = self.base.create(context)
        in_type = list[converter.accepts]
        out_type = list[converter.returns]
        return Converter[in_type, out_type](converter.name, converter.func, True, *self.base.args, **self.base.kwargs)


class OptionalFactory(ConverterFactory):
    def __init__(self, base: ConverterFactory) -> None:
        self.base = base

    @property
    def args(self) -> Any:
        return self.base.args

    @property
    def kwargs(self) -> Any:
        return self.base.kwargs

    def _create(self, conv: Converter, in_type: Any, out_type: Any) -> Callable:
        def _conv(v: in_type, cxt: ValidationContext) -> out_type:
            if v is None:
                return None
            else:
                return conv.func(v, cxt)
        return _conv

    def create(self, context: ValidationContext) -> Converter:
        converter = self.base.create(context)
        in_type = Optional[converter.accepts]
        out_type = Optional[converter.returns]
        return Converter[in_type, out_type](
            converter.name,
            self._create(converter, in_type, out_type),
            converter.is_iter,
            *self.base.args, **self.base.kwargs,
        )


def get_factory(
    name: str,
    func: Callable,
    *args,
    **kwargs,
) -> ConverterFactory:
    return SingleValueFactory(name, lambda cxt: func, *args, **kwargs)


def get_user_factory(t: type, name: Optional[str], create: Callable[[Any, ValidationContext], Any]) -> ConverterFactory:
    """
    Creates a factory for user defined type.

    Args:
        t: User defined type.
        name: Name of the converter. If `None` , type name is used.
        is_iter: Flag to interpret input value as iterable object.
        is_optional: Whether the converter can return `None` .
        create: Callable to generate the instance. The signature of this is used for type parameters of the converter.
    Returns:
        Created factory.
    """
    def _create(t: Any, union: Any, create: Callable[[Any, ValidationContext], Any]) -> Callable:
        def conv(v: union, cxt: ValidationContext) -> t:
            if isinstance_safe(v, t):
                return v
            return create(v, cxt)
        return conv

    def conv(cxt: ValidationContext) -> Callable:
        if cxt.config.strict:
            def check(v: t, cxt: ValidationContext) -> t:
                if isinstance_safe(v, t):
                    return v
                else:
                    raise PartialFailure(lambda converter: ConversionFailure(f"Input must be a instance of {t} but {type(v)}.", converter))
            return check
        else:
            union = t
            in_t = next(iter(inspect.signature(create).parameters.values())).annotation
            if in_t != inspect.Parameter.empty:
                union = Union[t, in_t]
            return _create(t, union, create)
    return SingleValueFactory(name or t.__name__, conv)


def get_builtin_factory(t: Any, name: Optional[str]) -> Optional[ConverterFactory]:
    """
    Creates a factory for a builtin type.

    Args:
        t: A builtin type.
        name: Name of the converter. If `None` , type name is used.
        is_iter: Flag to interpret input value as iterable object.
        is_optional: Whether the converter can return `None` .
    Returns:
        Created factory.
    """
    if t not in builtin_conversions:
        return None

    n, func = builtin_conversions[t]

    def conv(cxt: ValidationContext) -> Callable:
        if cxt.config.strict_builtin:
            return convert_strict(t, False)
        else:
            sig = inspect.signature(func)
            _, in_t = next(iter(sig.parameters.items()))
            return func

    return SingleValueFactory(name or n, conv)