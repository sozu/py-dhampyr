from collections.abc import Callable
from functools import cached_property
import inspect
from typing import Any, TypeVar, Generic, Optional, Union
from .context import ValidationContext, analyze_callable, ContextualCallable
from .failures import ValidationFailure, CompositeValidationFailure, PartialFailure
from .builtins import *
from .util import get_self_args


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
        #: Flag to interpret input value as iterable object and verify each value respectively.
        self.is_iter = is_iter
        self.args = args
        self.kwargs = kwargs

    @cached_property
    def accepts(self) -> Any:
        args = get_self_args(self)
        return args and args[0] or Any

    @cached_property
    def returns(self) -> Any:
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


class ConverterFactory:
    def __init__(
        self,
        name: str,
        is_iter: bool,
        is_optional: bool,
        func: Callable[[ValidationContext], Callable],
        *args,
        **kwargs,
    ) -> None:
        self.name = name
        self.is_iter = is_iter
        self.func = func
        self.is_optional = is_optional
        self.args = args
        self.kwargs = kwargs

    def create(self, context: ValidationContext) -> Converter:
        call = self.func(context)
        cc = call if isinstance(call, ContextualCallable) else analyze_callable(call)
        return Converter[cc.in_type, cc.out_type](self.name, cc, self.is_iter, *self.args, **self.kwargs)


def get_factory(
    name: str,
    is_iter: bool,
    is_optional: bool,
    func: Callable,
    *args,
    **kwargs,
) -> ConverterFactory:
    return ConverterFactory(name, is_iter, is_optional, lambda cxt: func, *args, **kwargs)


def _create(t: Any, union: Any, create: Callable[[Any, ValidationContext], Any]) -> Callable:
    def conv(v: union, cxt: ValidationContext) -> t:
        if isinstance(v, t):
            return v
        return create(v, cxt)
    return conv


def get_user_factory(t: type, name: Optional[str], is_iter: bool, is_optional: bool, create: Callable[[Any, ValidationContext], Any]) -> ConverterFactory:
    def conv(cxt: ValidationContext) -> Callable:
        if cxt.config.isinstance_any:
            def check(v: t, cxt: ValidationContext) -> t:
                if isinstance(v, t):
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
    return ConverterFactory(name or t.__name__, is_iter, is_optional, conv)


def get_builtin_factory(t: Any, name: Optional[str], is_iter: bool, is_optional: bool) -> Optional[ConverterFactory]:
    if t not in builtin_conversions:
        return None

    n, func = builtin_conversions[t]

    def conv(cxt: ValidationContext) -> Callable:
        return convert_strict(t) if cxt.config.isinstance_builtin else func

    return ConverterFactory(name or n, is_iter, is_optional, conv)