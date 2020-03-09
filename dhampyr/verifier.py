from .context import ValidationContext, contextual_invoke
from .failures import ValidationFailure, CompositeValidationFailure, PartialFailure


class VerificationFailure(ValidationFailure):
    """
    Represents a failure which arised in verification phase.
    """
    def __init__(self, message, verifier):
        super().__init__(
            name=verifier.name,
            message=message,
            args=verifier.args,
            kwargs=verifier.kwargs,
        )
        self.verifier = verifier


class Verifier:
    def __init__(self, name, func, is_iter, *args, **kwargs):
        self.name = name
        self.func = func
        self.is_iter = is_iter
        self.args = args
        self.kwargs = kwargs

    def verify(self, value, context=None):
        """
        Verifies a value with verification function.

        Parameters
        ----------
        value: object
            A value to verify.
        context: ValidationContext
            Context for the value.

        Returns
        -------
        ValidationFailure
            A failure which arised in the verification. When it succeeded, `None`.
        """
        def ver(v, i=None):
            try:
                c = context
                if c and i is not None:
                    c = c[i]
                r = contextual_invoke(self.func, v, c)
                return None if r else VerificationFailure(f"Verification by {self.name} failed.", self)
            except PartialFailure as e:
                return e.create(verifier=self)
            except ValidationFailure as e:
                return e
            except Exception as e:
                return VerificationFailure(str(e), self)

        if self.is_iter:
            failures = [(i, f) for i, f in [(i, ver(v, i)) for i, v in enumerate(value)] if f is not None]
            if len(failures) == 0:
                return None
            else:
                composite = CompositeValidationFailure()
                for i, f in failures:
                    composite.add(i, f)
                return composite
        else:
            return ver(value)