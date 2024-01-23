import  pytest
from dhampyr.requirement import RequirementPolicy, Requirement, VALUE_MISSING, MissingFailure, NullFailure, EmptyFailure
from dhampyr.context import ValidationContext


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

    def test_requires(self):
        r = Requirement(RequirementPolicy.REQUIRES)
        f, b = r.validate(VALUE_MISSING)
        assert isinstance(f, MissingFailure)
        assert f.name == "missing"
        assert not b


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

    def test_contextual_skip(self):
        r = Requirement(null=RequirementPolicy.CONTEXTUAL)
        f, b = r.validate(None)
        assert f is None
        assert not b

    def test_contextual_continue(self):
        r = Requirement(null=RequirementPolicy.CONTEXTUAL)
        f, b = r.validate(None, ValidationContext().configure(skip_null=False))
        assert f is None
        assert b

    def test_requires_deny(self):
        r = Requirement(null=RequirementPolicy.REQUIRES)
        f, b = r.validate(None)
        assert isinstance(f, NullFailure)
        assert f.name == "null"
        assert not b

    def test_requires_allow(self):
        r = Requirement(null=RequirementPolicy.REQUIRES)
        f, b = r.validate(None, ValidationContext().configure(allow_null=True))
        assert f is None
        assert not b


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

    def test_contextual_skip(self):
        r = Requirement(empty=RequirementPolicy.CONTEXTUAL)
        f, b = r.validate("")
        assert f is None
        assert not b

    def test_contextual_continue(self):
        r = Requirement(empty=RequirementPolicy.CONTEXTUAL)
        f, b = r.validate("", ValidationContext().configure(skip_empty=False))
        assert f is None
        assert b

    def test_requires_deny(self):
        r = Requirement(empty=RequirementPolicy.REQUIRES)
        f, b = r.validate("")
        assert isinstance(f, EmptyFailure)
        assert f.name == "empty"
        assert not b

    def test_requires_allow(self):
        r = Requirement(empty=RequirementPolicy.REQUIRES)
        f, b = r.validate("", ValidationContext().configure(allow_empty=True))
        assert f is None
        assert not b

    def test_bytes(self):
        r = Requirement(empty=RequirementPolicy.FAIL)
        f, b = r.validate(b"")
        assert isinstance(f, EmptyFailure)
        assert f.name == "empty"
        assert not b

    def test_list(self):
        r = Requirement(empty=RequirementPolicy.FAIL)
        f, b = r.validate([])
        assert isinstance(f, EmptyFailure)
        assert f.name == "empty"
        assert not b

    def test_empty_specs(self):
        r = Requirement(empty=RequirementPolicy.FAIL)
        f, b = r.validate("a", ValidationContext().configure(empty_specs=[(str, lambda x: x == "a")]))
        assert isinstance(f, EmptyFailure)
        assert f.name == "empty"
        assert not b
        f, b = r.validate("a", ValidationContext().configure(empty_specs=[(str, lambda x: x == "b")]))
        assert f is None
        assert b