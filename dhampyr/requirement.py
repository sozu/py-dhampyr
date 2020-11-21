from enum import Enum, auto
from .failures import ValidationFailure
from .context import ValidationContext


def _fails(error, skip, allow):
    return error(), False

def _skips(error, skip, allow):
    return None, False

def _continue(error, skip, allow):
    return None, True

def _contextual(error, skip, allow):
    return None, not skip

def _requires(error, skip, allow):
    return (None, False) if allow else (error(), False)


class RequirementPolicy(Enum):
    FAIL = _fails
    SKIP = _skips
    CONTINUE = _continue
    CONTEXTUAL = _contextual
    REQUIRES = _requires


VALUE_MISSING = object()


class Requirement:
    """
    Represents the method which requires a value from dictionary-like object.
    """
    def __init__(self, missing=RequirementPolicy.SKIP, null=RequirementPolicy.SKIP, empty=RequirementPolicy.SKIP):
        """
        Initializes the object with requirement policies.

        Parameters
        ----------
        missing: RequirementPolicy
            A policy applied when the value is absent.
        null: RequirementPolicy
            A policy applied when the value is `None`.
        empty: RequirementPolicy
            A policy applied when the value is empty.
        """
        self.missing = missing
        self.null = null
        self.empty = empty
        self._requires = False

    @property
    def requires(self):
        """
        Checks one of the policies is `FAIL`.

        Returns
        -------
        bool
            `True` when one of policies is `FAIL`.
        """
        return any(map(lambda r: r == RequirementPolicy.FAIL, (self.missing, self.null, self.empty)))

    def _check_empty(self, value):
        if isinstance(value, str) and value == "":
            return True

        if isinstance(value, bytes) and len(value) == 0:
            return True

        return False

    def validate(self, value, context=None):
        """
        Apply requirement policies to a value.

        Parameters
        ----------
        value: object
            A value to validate

        Returns
        -------
        ValidationFailure
            A failure returned from requirement policy or continuation function.
        bool
            The flag notifying the caller to continue to subsequent phases.
        """
        context = context or ValidationContext.default()

        if value == VALUE_MISSING:
            return self.missing(lambda: MissingFailure(), False, False)
        elif value is None:
            skip, allow = context.config.skip_null, context.config.allow_null

            return self.null(lambda: NullFailure(), skip, allow)
        else:
            skip, allow = context.config.skip_empty, context.config.allow_empty

            if self._check_empty(value):
                return self.empty(lambda: EmptyFailure(), skip, allow)

            for t, f in context.config.empty_specs:
                if isinstance(value, t):
                    if callable(f) and f(value):
                        return self.empty(lambda: EmptyFailure(), skip, allow)
                    elif f == value:
                        return self.empty(lambda: EmptyFailure(), skip, allow)

            return None, True


class MissingFailure(ValidationFailure):
    """
    Validation failure representing that a required attribute is not found.
    """
    def __init__(self):
        super().__init__("missing", "This value is required.")


class NullFailure(ValidationFailure):
    """
    Represents a failure that the target values is None.
    """
    def __init__(self):
        super().__init__("null", "This value must not be null.")


class EmptyFailure(ValidationFailure):
    """
    Represents a failure that the target values is empty.
    """
    def __init__(self):
        super().__init__("empty", "This value must not be empty.")