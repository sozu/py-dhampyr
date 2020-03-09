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


class Converter:
    def __init__(self, name, func, is_iter, inferred=None, *args, **kwargs):
        self.name = name
        self.func = func
        self.is_iter = is_iter
        self.inferred = inferred
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
            try:
                c = context
                if c and i is not None:
                    c = c[i]
                return contextual_invoke(self.func, v, c), None
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
                if context and not context.joint_failure:
                    return [None if f else v for v, f in results], composite
                else:
                    return None, composite
        else:
            return conv(value)