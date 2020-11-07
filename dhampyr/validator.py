from enum import Enum
from collections import OrderedDict
from functools import reduce, partial
from .requirement import Requirement, RequirementPolicy, MissingFailure
from .config import default_config

from .failures import ValidationPath, ValidationFailure, MalformedFailure, CompositeValidationFailure
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

    def __bool__(self):
        """
        Checks this result represents success.

        Returns
        -------
        bool
            `True` if the validation which generates this result has succeeded.
        """
        return len(self.failures) == 0

    def get(self):
        """
        Returns an instance created by `validate_dict`.

        Returns
        -------
        object
            Created instance of type determined by first argument of `validate_dict`.
        """
        return self.validated

    def or_else(self, handler, allows=[]):
        """
        Returns an instance created in `validate_dict` if the validation succeeded, otherwise executes `handler`.

        Parameters
        ----------
        handler: CompositeValidationFailure -> any
            A function which takes validation failures.
        allows: [str]
            Paths. When all failures are located under them, `handler` is not invoked.
        """
        if len(self.failures.failures) == 0:
            return self.validated
        elif all([any([p.under(a) for a in map(ValidationPath.of, allows)]) for p, _ in self.failures]):
            return self.validated
        else:
            return handler(self.failures)


class Validator:
    """
    Validator provides a functionality to apply validation rules to a value.

    Validation can be devided into 3 phases each of which corresponds to an attribute of `Validator` object.

    Requirements phase
    -------------------
    This phase checks whether the input object *exists* or not.
    Prepending `+` operator makes validator fail when the input object does not exist.

    There are 3 strategies to determine the input *exists* or not; *missing*, *null* and *empty*.

    - The input is *missing* when no value exists on the key where the validator is declared.
    - The input is *null* when it is `None`.
    - The input is *empty* when it satisfies emptiness condition defined by its type.

    By default, `+` prepended validator fails when one of those strategies holds.
    Use bitwise operators and strategy symbols to control the behavior of the validator for each strategy.

    - `&` makes the validator fail, that is, expose the failure.
    - `^` makes the validator skip the subsequent phases and set the default value without failure.
    - `|` makes the validator continue the subsequent phases.
    - `None` is a symbol of *null* and `...` is a symbol of *empty*.

    >>> class V:
    >>>     # None is set without failure when the input does not exist.
    >>>     v1: v(int) = None
    >>>     # Fails when the input does not exist.
    >>>     v2: +v(int)
    >>>     # Fails when the input is missing whereas 0 is set when the input is None.
    >>>     v3: +v(int) ^ None = 0
    >>>     # Fails when the input is missing whereas 0 is set when the input is None.
    >>>     v4: +v(lambda x: x or 0) | None

    Conversion phase
    ----------------
    This phase converts the input value into another object by a `Converter`.
    Validator must contain only one conversion phase.

    Verification phase
    ------------------
    This phase verifies converted object by a sequence of `Verifier`s.
    Validator can have 0 or multiple verification phases.
    """
    def __init__(self, converter, verifiers, key=None):
        self.requirement = Requirement(
            missing = RequirementPolicy.SKIP,
            null = RequirementPolicy.CONTEXTUAL,
            empty = RequirementPolicy.CONTEXTUAL,
        )
        self.converter = converter
        self.verifiers = verifiers
        self.key = key

    def __pos__(self):
        self.requirement._requires = True
        self.requirement.missing = RequirementPolicy.FAIL
        self.requirement.null = RequirementPolicy.REQUIRES
        self.requirement.empty = RequirementPolicy.REQUIRES
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
    def requires(self):
        """
        Checks if this validator fails for the missing, null or empty input.

        Returns
        -------
        bool
            `True` when one of this validator's requirement policies is `FAIL`.
        """
        return self.requirement.requires

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
        context = context or ValidationContext.default()

        join_on_fail = context.config.join_on_fail

        failure, to_continue = self.requirement.validate(value, context)

        if not to_continue:
            return None, failure, True

        val, failure = self.converter.convert(value, context)

        if failure:
            if not join_on_fail and self.converter.is_iter:
                return val, failure, False
            else:
                return None, failure, True

        for verifier in self.verifiers:
            f = verifier.verify(val, context)
            if f is not None:
                if not join_on_fail and verifier.is_iter:
                    return [None if (i in f) else v for i, v in enumerate(val)], f, False
                else:
                    return None, f, True

        return val, None, False