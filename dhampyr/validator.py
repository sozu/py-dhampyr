from collections.abc import Sequence, Callable
from dataclasses import MISSING
from typing import Any, TypeVar, Generic, Optional, Union, cast
from typing_extensions import Self
from .requirement import Requirement, RequirementPolicy, MissingFailure

from .failures import ValidationPath, ValidationFailure, MalformedFailure, CompositeValidationFailure
from .converter import Converter, ConversionFailure, ConverterFactory
from .verifier import Verifier, VerificationFailure
from .context import ValidationContext


T = TypeVar('T')


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


class ValidationResult(Generic[T]):
    """
    The result of a validation suite.

    Args:
        T: Type of the validated object.
    """
    def __init__(self, validated: Optional[T], failures: ValidationFailure, context: ValidationContext):
        #: Validation result.
        self.validated = validated
        #: Failures raised in validation suite.
        self.failures = failures
        #: Base context used in validation suite.
        self.context = context

    def __bool__(self) -> bool:
        """
        Checks this result represents success.
        """
        return len(self.failures) == 0

    def get(self) -> T:
        """
        Returns an instance created by the suite.

        Returns:
            An instance created by the suite.
        """
        return cast(T, self.validated)

    def or_else(self, handler: Callable[[ValidationFailure], Any], allows: list[str] = []) -> T:
        """
        Returns an instance created by the suite if the validation succeeded, otherwise executes `handler` .

        Args:
            handler: A function which takes validation failures.
            allows: A list of validation paths. When all failures are located under them, `handler` is not invoked even if the validation failed.
        Returns:
            An instance created by the suite if the validation succeeded, otherwise the result of `handler`.
        """
        if len(self.failures) == 0:
            return cast(T, self.validated)
        elif all([any([p.under(a) for a in map(ValidationPath.of, allows)]) for p, _ in self.failures]):
            return cast(T, self.validated)
        else:
            return handler(self.failures)


class Validator:
    """
    Validator provides a functionality to apply validation rules to a value.

    Validation can be devided into 3 phases each of which corresponds to an attribute of `Validator` object.

    **Requirements phase**

    This phase checks whether the input object *exists* or not.
    Prepending `+` operator makes validator fail when the input object does not exist.

    There are 3 strategies to determine the input *exists* or not; *missing*, *null* and *empty*.

    - The input is *missing* when no value exists on the key where the validator is declared.
    - The input is *null* when it is `None`.
    - The input is *empty* when it satisfies emptiness condition defined by its type.

    By default, `+` prepended validator fails when one of those strategies holds.
    Use bitwise operators and strategy symbols to control the behavior of the validator for each strategy.

    - `&` makes the validator fail.
    - `^` makes the validator skip the subsequent phases and set the default value without failure.
    - `/` makes the validator continue the subsequent phases.
    - `None` is a symbol of *null* and `...` is a symbol of *empty*.

    ```python
    class V:
        # None is set without failure when the input does not exist.
        v1: Any = v(default=None)
        # Fails when the input does not exist.
        v2: int = +v()
        # Fails when the input is missing whereas 0 is set when the input is None.
        v3: int = +v(default=0) ^ None
        # Fails when the input is missing whereas 0 is set when the input is None.
        v4: Any = +v(lambda x: x or 0) / None
    ```

    **Conversion phase**

    This phase converts the input value into another object by a `Converter`.
    Validator must contain only one conversion phase.

    **Verification phase**

    This phase verifies converted object by a sequence of `Verifier`s.
    Validator can have 0 or multiple verification phases.
    """
    def __init__(self, converter: Converter, verifiers: Sequence[Verifier], key: Optional[str] = None):
        self.requirement = Requirement(
            missing = RequirementPolicy.SKIP,
            null = RequirementPolicy.CONTEXTUAL,
            empty = RequirementPolicy.CONTEXTUAL,
        )
        self.converter = converter
        self.verifiers = verifiers
        self.key = key
        self.silent = False

    def __pos__(self) -> Self:
        self.requirement._requires = True
        self.requirement.missing = RequirementPolicy.FAIL
        self.requirement.null = RequirementPolicy.REQUIRES
        self.requirement.empty = RequirementPolicy.REQUIRES
        return self

    def __invert__(self) -> Self:
        self.silent = True
        return self

    def __and__(self, null_empty: Any) -> Self:
        if null_empty is None:
            self.requirement.null = RequirementPolicy.FAIL
        elif null_empty is Ellipsis:
            self.requirement.empty = RequirementPolicy.FAIL
        else:
            raise ValueError(f"Only None or Ellipsis(...) is available with bit-wise operation to Validator.")
        return self

    def __truediv__(self, null_empty: Any) -> Self:
        if null_empty is None:
            self.requirement.null = RequirementPolicy.CONTINUE
        elif null_empty is Ellipsis:
            self.requirement.empty = RequirementPolicy.CONTINUE
        else:
            raise ValueError(f"Only None or Ellipsis(...) is available with bit-wise operation to Validator.")
        return self

    def __xor__(self, null_empty: Any) -> Self:
        if null_empty is None:
            self.requirement.null = RequirementPolicy.SKIP
        elif null_empty is Ellipsis:
            self.requirement.empty = RequirementPolicy.SKIP
        else:
            raise ValueError(f"Only None or Ellipsis(...) is available with bit-wise operation to Validator.")
        return self

    @property
    def requires(self) -> bool:
        """
        Checks if this validator fails for the missing, null or empty input.
        """
        return self.requirement.requires

    @property
    def accept_list(self) -> bool:
        """
        Returns whether this validator accepts an input value as a list.
        """
        return self.converter.is_iter

    def validate(self, value: Any, context: Optional[ValidationContext] = None) -> tuple[Any, Optional[ValidationFailure], bool]:
        """
        Validates a value.

        Args:
            value: An input value.
            context: Context used for the validation.
        Returns:
            A tuple of validated value, observed failure and a flag to notify caller to use alternative value.
        """
        context = context or ValidationContext.default()

        def fail_or(v, f, b):
            return v, None if self.silent else f, b

        def exec():
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
                        return [None if (i in f) else v for i, v in enumerate(val)], f, False # type: ignore
                    else:
                        return None, f, True

            return val, None, False

        return fail_or(*exec())


class ValidatorFactory:
    """
    Factory class to generate a `Validator` for passed context.

    Operators available for `Validator` are also available for this class and they modify the `Validator` to create.
    """
    def __init__(
        self,
        converter: ConverterFactory,
        verifiers: Sequence[Verifier],
        alias: Optional[str] = None,
        default: Optional[Any] = MISSING,
        default_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.converter = converter
        self.verifiers = verifiers
        self.operations = lambda v: v
        self.alias = alias
        self.default = default
        self.default_factory = default_factory

    def __pos__(self) -> Self:
        ops = self.operations
        self.operations = lambda v: +ops(v)
        return self

    def __invert__(self) -> Self:
        ops = self.operations
        self.operations = lambda v: ~ops(v)
        return self

    def __and__(self, null_empty: Any) -> Self:
        ops = self.operations
        self.operations = lambda v: ops(v) & null_empty
        return self

    def __truediv__(self, null_empty: Any) -> Self:
        ops = self.operations
        self.operations = lambda v: ops(v) / null_empty
        return self

    def __xor__(self, null_empty: Any) -> Self:
        ops = self.operations
        self.operations = lambda v: ops(v) ^ null_empty
        return self

    def create(self, cxt: ValidationContext) -> Validator:
        """
        Createsa a `Validator` working on the passed context.

        Args:
            cxt: A context object.
        Returns:
            Created `Validator` .
        """
        return self.operations(Validator(self.converter.create(cxt), self.verifiers, key=self.alias))