from collections.abc import Callable
from enum import Enum
from typing import Any, Optional
from typing_extensions import TypeAlias
from .failures import ValidationFailure
from .context import ValidationContext


Policy: TypeAlias = Callable[[Callable[[], ValidationFailure], bool, bool], tuple[Optional[ValidationFailure], bool]]


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
    """
    Set of requirement policies.
    """
    FAIL = _fails
    """A policy to abort validation with a failure."""
    SKIP = _skips
    """A policy to skip subsequent phases without a failure."""
    CONTINUE = _continue
    """A policy to continue validation."""
    CONTEXTUAL = _contextual
    """A policy that configuration parameters determine to skip or continue."""
    REQUIRES = _requires
    """A policy that configuration parameters determine to skip or abort."""


VALUE_MISSING = object()


class Requirement:
    """
    Specification whether the validator requires the existence of input value.
    """
    def __init__(
        self,
        missing: Policy = RequirementPolicy.SKIP,
        null: Policy = RequirementPolicy.SKIP,
        empty: Policy = RequirementPolicy.SKIP,
    ) -> None:
        """
        Initializes the object with requirement policies.

        Args:
            missing: A policy applied when the value is absent.
            null: A policy applied when the value is `None`.
            empty: A policy applied when the value is empty.
        """
        self.missing = missing
        self.null = null
        self.empty = empty
        self._requires = False

    @property
    def requires(self) -> bool:
        """
        Checks one of policies is `FAIL`, that is, requires value exist.
        """
        return any(map(lambda r: r == RequirementPolicy.FAIL, (self.missing, self.null, self.empty)))

    def _check_empty(self, value):
        if isinstance(value, str) and value == "":
            return True

        if isinstance(value, bytes) and len(value) == 0:
            return True

        if isinstance(value, (list, set)) and len(value) == 0:
            return True

        return False

    def validate(self, value: Any, context: Optional[ValidationContext] = None) -> tuple[Optional[ValidationFailure], bool]:
        """
        Apply requirement policies to a value.

        Args:
            value: A value to validate
        Returns:
            Failure and a flag to continue subsequenct phases.
        """
        context = context or ValidationContext.default()

        if value == VALUE_MISSING:
            return self.missing(lambda: MissingFailure(), False, False)
        elif value is None:
            return self.null(
                lambda: NullFailure(),
                context.config.skip_null,
                context.config.allow_null,
            )
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
    Represents a failure that a required attribute is not found.
    """
    def __init__(self):
        super().__init__("missing", "This value is required.")


class NullFailure(ValidationFailure):
    """
    Represents a failure that the target values is `None` .
    """
    def __init__(self):
        super().__init__("null", "This value must not be null.")


class EmptyFailure(ValidationFailure):
    """
    Represents a failure that the target value is considered empty.
    """
    def __init__(self):
        super().__init__("empty", "This value must not be empty.")