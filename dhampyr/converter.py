import builtins
from .context import ValidationContext, contextual_invoke
from .failures import ValidationFailure, CompositeValidationFailure, PartialFailure


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


def is_builtin(t):
    return isinstance(t, type) and hasattr(builtins, t.__qualname__)


class Converter:
    def __init__(self, name, func, is_iter, accepts=None, returns=None, *args, **kwargs):
        self.name = name
        self.func = func
        self.is_iter = is_iter
        self.accepts = accepts
        self.returns = returns
        self.args = args
        self.kwargs = kwargs

    def convert(self, value, context=None):
        """
        Converts a value with conversion function.

        Parameters
        ----------
        value: object
            A value to convert.
        context: ValidationContext
            Context for the value.

        Returns
        -------
        object
            Converted value or `None` when conversion failed.
        ValidationFailure
            A failure in conversion or `None` when it succeeded.
        """
        def conv(v, i=None):
            if context:
                if context.config.isinstance_any:
                    return (v, None) if isinstance(v, self.func) else (None, ConversionFailure("Type unmatched.", self))
                elif context.config.isinstance_builtin:
                    if is_builtin(self.func):
                        return (v, None) if isinstance(v, self.func) else (None, ConversionFailure("Type unmatched.", self))

            try:
                if context and i is not None:
                    with context[i, True] as c:
                        return contextual_invoke(self.func, v, c), None
                else:
                    return contextual_invoke(self.func, v, context), None
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