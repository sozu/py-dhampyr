from .requirement import Requirement, RequirementPolicy, MissingFailure
from .config import dhampyr
from .failures import ValidationFailure, MalformedFailure, CompositeValidationFailure
from .converter import Converter, ConversionFailure
from .verifier import Verifier, VerificationFailure
from .context import ValidationContext
from .validator import Validator, ValidationResult
from .api import v, validate_dict, converter, verifier, validate
from .variable import x

__all__ = [
    "dhampyr",
    "ValidationResult",
    "Validator",
    "Requirement",
    "RequirementPolicy",
    "MissingFailure",
    "v",
    "validate_dict",
    "validate",
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
    "x",
]

# for compatibility
from . import validator
from . import api
validator.v = api.v
validator.validate_dict = api.validate_dict
validator.converter = api.converter
validator.verifier = api.verifier