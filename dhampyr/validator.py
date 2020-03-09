from enum import Enum
from collections import OrderedDict
from functools import reduce, partial
from .requirement import Requirement, RequirementPolicy, MissingFailure
from .config import default_config

from .failures import ValidationFailure, MalformedFailure, CompositeValidationFailure
from .converter import Converter, ConversionFailure
from .verifier import Verifier, VerificationFailure
from .context import ValidationContext


# for compatibility
v = None
validate_dict = None
converter = None
verifier = None


__all__ = [
    "ValidationResult",
    "Validator",
    "Requirement",
    "RequirementPolicy",
    "MissingFailure",
    "v",
    "validate_dict",
    "converter",
    "verifier",
    "ValidationFailure",
    "MalformedFailure",
    "CompositeValidationFailure",
    "Converter",
    "ConversionFailure",
    "Verifier",
    "VerificationFailure",
    "ValidationContext",
]


class ValidationResult:
    """
    A type of returning value of `validate_dict`.

    Attributes
    ----------
    failures: CompositeValidationfailure
        An object providing accessor of validation failures.
    context: ValidtionContext
        An object storing contextual values in an execution of `validate_dict`.
    """
    def __init__(self, validated, failures, context):
        self.validated = validated
        self.failures = failures
        self.context = context

    def get(self):
        """
        Returns an instance created in `validate_dict`

        Returns
        -------
        object
            Created instance of type determined by first argument of `validate_dict`.
        """
        return self.validated

    def or_else(self, handler):
        """
        Returns an instance created in `validate_dict` if the validation succeeded, otherwise executes `handler`.

        Parameters
        ----------
        handler: CompositeValidationFailure -> any
            A function which takes validation failures.
        """
        if len(self.failures.failures) == 0:
            return self.validated
        else:
            return handler(self.failures)


class Validator:
    """
    Validator provides a functionality to apply validation rules to a value.

    Validation is classified into 3 phases each of which corresponds to an attribute of `Validator` object.
    """
    def __init__(self, converter, verifiers, config=None):
        self.config = config or default_config()
        self.requirement = Requirement(
            missing=RequirementPolicy.SKIP,
            null=RequirementPolicy.SKIP if self.config.inquires_null else RequirementPolicy.CONTINUE,
            empty=RequirementPolicy.SKIP if self.config.inquires_empty else RequirementPolicy.CONTINUE,
        )
        self.converter = converter
        self.verifiers = verifiers

    def __pos__(self):
        self.requirement.missing = RequirementPolicy.FAIL
        if self.config.inquires_null:
            self.requirement.null = RequirementPolicy.FAIL
        if self.config.inquires_empty:
            self.requirement.empty = RequirementPolicy.FAIL
        return self

    def __and__(self, null_empty):
        if null_empty is None:
            self.requirement.null = RequirementPolicy.FAIL
        elif null_empty is Ellipsis:
            self.requirement.empty = RequirementPolicy.FAIL
        else:
            raise ValueError(f"Only None or Ellipsis(...) is available with bit-wise operation to Validator.")
        return self

    def __or__(self, null_empty):
        if null_empty is None:
            self.requirement.null = RequirementPolicy.CONTINUE
        elif null_empty is Ellipsis:
            self.requirement.empty = RequirementPolicy.CONTINUE
        else:
            raise ValueError(f"Only None or Ellipsis(...) is available with bit-wise operation to Validator.")
        return self

    def __xor__(self, null_empty):
        if null_empty is None:
            self.requirement.null = RequirementPolicy.SKIP
        elif null_empty is Ellipsis:
            self.requirement.empty = RequirementPolicy.SKIP
        else:
            raise ValueError(f"Only None or Ellipsis(...) is available with bit-wise operation to Validator.")
        return self

    @property
    def accept_list(self):
        """
        Returns whether this validator accepts an input value as a list.

        Returns
        -------
        bool
            `True` if this validator accepts an input value as a list, otherwise `False`.
        """
        return self.converter.is_iter

    def validate(self, value, context=None):
        """
        Converts and verfies a value.

        Parameters
        ----------
        value: object
            An input value.
        context: ValidationContext
            Context for this value.

        Returns
        -------
        object
            Validated value if validation succeeded, otherwise `None`.
        ValidationFailure
            `ValidationFailure` if validation failed, otherwise `None`.
        bool
            A flag to notify caller to use alternative value.
        """
        joint_failure = not context or context.joint_failure

        failure, to_continue = self.requirement.validate(value)

        if not to_continue:
            return None, failure, True

        val, failure = self.converter.convert(value, context)

        if failure:
            if not joint_failure and self.converter.is_iter:
                return val, failure, False
            else:
                return None, failure, True

        for verifier in self.verifiers:
            f = verifier.verify(val, context)
            if f is not None:
                if not joint_failure and verifier.is_iter:
                    return [None if (i in f) else v for i, v in enumerate(val)], f, False
                else:
                    return None, f, True

        return val, None, False