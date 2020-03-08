import  pytest
from dhampyr.requirement import RequirementPolicy, Requirement, VALUE_MISSING, MissingFailure, NullFailure, EmptyFailure


class TestMissing:
    def test_fail(self):
        r = Requirement(RequirementPolicy.FAIL)
        f, b = r.validate(VALUE_MISSING)
        assert isinstance(f, MissingFailure)
        assert f.name == "missing"
        assert not b

    def test_skip(self):
        r = Requirement(RequirementPolicy.SKIP)
        f, b = r.validate(VALUE_MISSING)
        assert f is None
        assert not b

    def test_continue(self):
        r = Requirement(RequirementPolicy.CONTINUE)
        f, b = r.validate(VALUE_MISSING)
        assert f is None
        assert b


class TestNull:
    def test_fail(self):
        r = Requirement(null=RequirementPolicy.FAIL)
        f, b = r.validate(None)
        assert isinstance(f, NullFailure)
        assert f.name == "null"
        assert not b

    def test_skip(self):
        r = Requirement(null=RequirementPolicy.SKIP)
        f, b = r.validate(None)
        assert f is None
        assert not b

    def test_continue(self):
        r = Requirement(null=RequirementPolicy.CONTINUE)
        f, b = r.validate(None)
        assert f is None
        assert b


class TestEmpty:
    def test_fail(self):
        r = Requirement(empty=RequirementPolicy.FAIL)
        f, b = r.validate("")
        assert isinstance(f, EmptyFailure)
        assert f.name == "empty"
        assert not b

    def test_skip(self):
        r = Requirement(empty=RequirementPolicy.SKIP)
        f, b = r.validate("")
        assert f is None
        assert not b

    def test_continue(self):
        r = Requirement(empty=RequirementPolicy.CONTINUE)
        f, b = r.validate("")
        assert f is None
        assert b

