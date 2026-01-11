from collections.abc import Callable
from typing import Any, TypeVar, Generic, Optional
from .context import ValidationContext, ContextualCallable, analyze_callable
from .failures import ValidationFailure, CompositeValidationFailure, PartialFailure


V = TypeVar('V')


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


class Verifier(Generic[V]):
    """
    This class provides the interface to verify if the value satisfies some conditions.

    `func` is the function to verify the value which should work as follows.

    - Takes at least an argument where the value will be passed.
    - Optional one more argument for `ValidationContext` is available, which should be annotated the type.
    - `args` and `kwargs` are also passed to the function.
    - Returns `True` when the verification succeeds.
    - Otherwise, returns `False` or throw `Exception` .
    """
    def __init__(self, name: str, func: Callable, is_iter: bool, message: Optional[str] = None, *args, **kwargs):
        #: The name of the verifier used for error message.
        self.name = name
        #: Function verifying a value.
        self.func = func
        #: Flag to interpret input value as iterable object and verify each value respectively.
        self.is_iter = is_iter
        #: Default error message.
        self.message = message
        self.args = args
        self.kwargs = kwargs
        self._cc = self.func if isinstance(self.func, ContextualCallable) else analyze_callable(self.func)

    def verify(self, value: Any, context: Optional[ValidationContext] = None) -> Optional[ValidationFailure]:
        """
        Verifies a value with verification function.

        Args:
            value: A value to verify.
            context: Context for the value.
        Returns:
            A failure which arised in the verification. When it succeeded, `None`.
        """
        if self.is_iter:
            failures = [(i, f) for i, f in [(i, _verify(context, self, v, i)) for i, v in enumerate(value)] if f is not None]
            if len(failures) == 0:
                return None
            else:
                composite = CompositeValidationFailure()
                for i, f in failures:
                    composite.add(i, f)
                return composite
        else:
            return _verify(context, self, value)


def _verify(context: Optional[ValidationContext], verifier: Verifier, v: Any, i=None):
    try:
        if context and i is not None:
            with context.child(i, True) as c:
                r = verifier._cc(v, c)
        else:
            # REVIEW: How to generate empty context?
            r = verifier._cc(v, context or ValidationContext())
        return None if r else VerificationFailure(f"Verification by {verifier.name} failed.", verifier)
    except PartialFailure as e:
        return e.create(verifier=verifier)
    except ValidationFailure as e:
        return e
    except Exception as e:
        return VerificationFailure(str(e), verifier)
