from dhampyr.requirement import RequirementPolicy


class ValidationConfiguration:
    def __init__(self):
        self.inquires_null = True
        self.inquires_empty = True
        self.empty_checkers = []


def default_config(config=ValidationConfiguration()):
    return config