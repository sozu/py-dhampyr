import pytest
from dhampyr.requirement import RequirementPolicy, VALUE_MISSING, MissingFailure, NullFailure, EmptyFailure
from dhampyr.context import ValidationContext
from dhampyr.converter import Converter, ConverterFactory, SingleValueFactory
from dhampyr.verifier import Verifier
from dhampyr.validator import Validator, ValidatorFactory


class TestPositive:
    def test_positive(self):
        v = Validator(Converter("test", lambda x:x, False), [])
        assert v.requirement.missing == RequirementPolicy.SKIP
        assert v.requirement.null == RequirementPolicy.CONTEXTUAL
        assert v.requirement.empty == RequirementPolicy.CONTEXTUAL
        v = +v
        assert v.requirement.missing == RequirementPolicy.FAIL
        assert v.requirement.null == RequirementPolicy.REQUIRES
        assert v.requirement.empty == RequirementPolicy.REQUIRES


class TestRequirement:
    def _validator(self):
        return Validator(
            Converter("conv", lambda x:x, False),
            [],
        )

    def test_missing_fail(self):
        v = +(self._validator())
        r, f, b = v.validate(VALUE_MISSING)
        assert v.requires
        assert r is None
        assert isinstance(f, MissingFailure)
        assert b

    def test_missing_skip(self):
        v = self._validator()
        r, f, b = v.validate(VALUE_MISSING)
        assert not v.requires
        assert r is None
        assert f is None
        assert b

    def test_missing_silent(self):
        v = ~+(self._validator())
        r, f, b = v.validate(VALUE_MISSING)
        assert v.requires
        assert r is None
        assert f is None
        assert b

    def test_null_fail(self):
        v = self._validator() & None
        r, f, b = v.validate(None)
        assert v.requires
        assert r is None
        assert isinstance(f, NullFailure)
        assert b

    def test_null_skip(self):
        v = self._validator() ^ None
        r, f, b = v.validate(None)
        assert not v.requires
        assert r is None
        assert f is None
        assert b

    def test_null_continue(self):
        v = self._validator() / None
        r, f, b = v.validate(None)
        assert not v.requires
        assert r is None
        assert f is None
        assert not b

    def test_empty_fail(self):
        v = self._validator() & ...
        r, f, b = v.validate("")
        assert v.requires
        assert r is None
        assert isinstance(f, EmptyFailure)
        assert b

    def test_empty_skip(self):
        v = self._validator() ^ ...
        r, f, b = v.validate("")
        assert not v.requires
        assert r is None
        assert f is None
        assert b

    def test_empty_continue(self):
        v = self._validator() / ...
        r, f, b = v.validate("")
        assert not v.requires
        assert r == ""
        assert f is None
        assert not b

    def test_exist(self):
        v = self._validator()
        r, f, b = v.validate("1")
        assert not v.requires
        assert r == "1"
        assert f is None
        assert not b


class TestConvert:
    def _validator(self):
        return Validator(
            Converter("conv", int, False),
            [],
        )

    def test_convert(self):
        v = self._validator()
        r, f, b = v.validate("1")
        assert r == 1
        assert f is None
        assert not b

    def test_fail(self):
        v = self._validator()
        r, f, b = v.validate("a")
        assert r is None
        assert f and f.name == "conv"
        assert b

    def test_silent(self):
        v = ~self._validator()
        r, f, b = v.validate("a")
        assert r is None
        assert f is None
        assert b


class TestIterativeConvert:
    def _validator(self):
        return Validator(
            Converter("conv", int, True),
            [],
        )

    def test_convert(self):
        v = self._validator()
        r, f, b = v.validate(["1", "2", "3"])
        assert r == [1, 2, 3]
        assert f is None
        assert not b

    def test_fail(self):
        v = self._validator()
        r, f, b = v.validate(["1", "a", "3"])
        assert r is None
        assert f and f[1] and len(f) == 1
        assert f[1].name == "conv" # type: ignore
        assert b

    def test_fail_silent(self):
        v = ~self._validator()
        r, f, b = v.validate(["1", "a", "3"])
        assert r is None
        assert f is None
        assert b

    def test_fail_unjointed(self):
        v = self._validator()
        cxt = ValidationContext()
        cxt.configure(join_on_fail = False)
        r, f, b = v.validate(["1", "a", "3"], cxt)
        assert r == [1, None, 3]
        assert f and f[1] and len(f) == 1
        assert f[1].name == "conv" # type: ignore
        assert not b


class TestVerify:
    def _validator(self):
        return Validator(
            Converter("conv", lambda x:x, False),
            [Verifier("gt", lambda x: x > 0, False), Verifier("lt", lambda x: x < 10, False)],
        )

    def test_verify(self):
        v = self._validator()
        r, f, b = v.validate(1)
        assert r == 1
        assert f is None
        assert not b

    def test_fail_gt(self):
        v = self._validator()
        r, f, b = v.validate(-1)
        assert r is None
        assert f and f.name == "gt"
        assert b

    def test_fail_lt(self):
        v = self._validator()
        r, f, b = v.validate(10)
        assert r is None
        assert f and f.name == "lt"
        assert b

    def test_fail_silent(self):
        v = ~self._validator()
        r, f, b = v.validate(-1)
        assert r is None
        assert f is None
        assert b


class TestIterativeVerify:
    def _validator(self):
        return Validator(
            Converter("conv", lambda x:x, False),
            [Verifier("gt", lambda x: x > 0, True), Verifier("lt", lambda x: x < 10, True)],
        )

    def test_verify(self):
        v = self._validator()
        r, f, b = v.validate([1, 2, 3])
        assert r == [1, 2, 3]
        assert f is None
        assert not b

    def test_fail_gt(self):
        v = self._validator()
        r, f, b = v.validate([1, -1, 3])
        assert r is None
        assert f and f[1] and len(f) == 1
        assert f[1].name == "gt" # type: ignore
        assert b

    def test_fail_lt(self):
        v = self._validator()
        r, f, b = v.validate([1, 10, 3])
        assert r is None
        assert f and f[1] and len(f) == 1
        assert f[1].name == "lt" # type: ignore
        assert b

    def test_fail_silent(self):
        v = ~self._validator()
        r, f, b = v.validate([1, -1, 3])
        assert r is None
        assert f is None
        assert b

    def test_fail_gt_unjointed(self):
        v = self._validator()
        cxt = ValidationContext()
        cxt.configure(join_on_fail = False)
        r, f, b = v.validate([1, -1, 3], cxt)
        assert r == [1, None, 3]
        assert f[1].name == "gt" # type: ignore
        assert not b

    def test_fail_lt_unjointed(self):
        v = self._validator()
        cxt = ValidationContext()
        cxt.configure(join_on_fail = False)
        r, f, b = v.validate([1, 10, 3], cxt)
        assert r == [1, None, 3]
        assert f[1].name == "lt" # type: ignore
        assert not b


class TestFactory:
    def _factory(self):
        return ValidatorFactory(SingleValueFactory("test", lambda cxt: lambda x: 0, False), [])

    def test_factory(self):
        f = self._factory()
        v = f.create(ValidationContext())
        assert v.requires is False
        assert (v.requirement.missing, v.requirement.null, v.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert v.accept_list is False
        assert not v.silent

    def test_pos(self):
        f = +self._factory()
        v = f.create(ValidationContext())
        assert v.requires is True
        assert (v.requirement.missing, v.requirement.null, v.requirement.empty) \
            == (RequirementPolicy.FAIL, RequirementPolicy.REQUIRES, RequirementPolicy.REQUIRES)
        assert v.accept_list is False
        assert not v.silent

    def test_invert(self):
        f = ~self._factory()
        v = f.create(ValidationContext())
        assert v.requires is False
        assert (v.requirement.missing, v.requirement.null, v.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert v.accept_list is False
        assert v.silent

    def test_and_none(self):
        f = self._factory() & None
        v = f.create(ValidationContext())
        assert v.requires is True
        assert (v.requirement.missing, v.requirement.null, v.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.FAIL, RequirementPolicy.CONTEXTUAL)
        assert v.accept_list is False
        assert not v.silent

    def test_truediv_none(self):
        f = self._factory() / None
        v = f.create(ValidationContext())
        assert v.requires is False
        assert (v.requirement.missing, v.requirement.null, v.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTINUE, RequirementPolicy.CONTEXTUAL)
        assert v.accept_list is False
        assert not v.silent

    def test_xor_none(self):
        f = self._factory() ^ None
        v = f.create(ValidationContext())
        assert v.requires is False
        assert (v.requirement.missing, v.requirement.null, v.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL)
        assert v.accept_list is False
        assert not v.silent

    def test_and_ellipsis(self):
        f = self._factory() & ...
        v = f.create(ValidationContext())
        assert v.requires is True
        assert (v.requirement.missing, v.requirement.null, v.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.FAIL)
        assert v.accept_list is False
        assert not v.silent

    def test_truediv_ellipsis(self):
        f = self._factory() / ...
        v = f.create(ValidationContext())
        assert v.requires is False
        assert (v.requirement.missing, v.requirement.null, v.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTINUE)
        assert v.accept_list is False
        assert not v.silent

    def test_xor_ellipsis(self):
        f = self._factory() ^ ...
        v = f.create(ValidationContext())
        assert v.requires is False
        assert (v.requirement.missing, v.requirement.null, v.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.SKIP)
        assert v.accept_list is False
        assert not v.silent