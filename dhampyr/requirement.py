from enum import Enum, auto
from .failures import ValidationFailure


def _fails(error):
    return error(), False

def _skips(error):
    return None, False

def _continue(error):
    return None, True


class RequirementPolicy(Enum):
    FAIL = _fails
    SKIP = _skips
    CONTINUE = _continue


VALUE_MISSING = object()


class Requirement:
    """
    Represents the method which requires a value from dictionary-like object.
    """
    def __init__(self, missing=RequirementPolicy.SKIP, null=RequirementPolicy.SKIP, empty=RequirementPolicy.SKIP, predicates=None):
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
        self.predicates = predicates or []

    def _check_empty(self, value):
        if isinstance(value, str) and value == "":
            return True

        if isinstance(value, bytes) and len(value) == 0:
            return True

        return False

    def validate(self, value):
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
            The flag notifying the caller to continue to successive methods.
        """
        if value == VALUE_MISSING:
            return self.missing(lambda: MissingFailure())
        elif value is None:
            return self.null(lambda: NullFailure())
        else:
            if self._check_empty(value):
                return self.empty(lambda: EmptyFailure())

            for f, p in self.predicates:
                if callable(f) and f(v):
                    return p(lambda: EmptyFailure())
                elif f == v:
                    return p(lambda: EmptyFailure())

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