from .validator import *


# for compatibility
from . import validator
from . import api
validator.v = api.v
validator.validate_dict = api.validate_dict
validator.converter = api.converter
validator.verifier = api.verifier