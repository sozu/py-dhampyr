import pytest
from enum import Enum, auto
from functools import partial
from dhampyr.failures import ValidationFailure, CompositeValidationFailure
from dhampyr.requirement import Requirement, RequirementPolicy, VALUE_MISSING, MissingFailure, NullFailure, EmptyFailure
from dhampyr.config import default_config
from dhampyr.context import ValidationContext
from dhampyr.converter import Converter, ConversionFailure
from dhampyr.verifier import Verifier, VerificationFailure
from dhampyr.validator import Validator


class TestPositive:
    def test_ignore_null(self):
        config = default_config().derive()
        config.allow_empty = True
        v = +Validator(Converter("conv", lambda x:x, False), [], config)
        assert v.requirement.missing == RequirementPolicy.FAIL
        assert v.requirement.null == RequirementPolicy.REQUIRES
        assert v.requirement.empty == RequirementPolicy.REQUIRES

    def test_ignore_empty(self):
        config = default_config().derive()
        config.allow_empty = True
        v = +Validator(Converter("conv", lambda x:x, False), [], config)
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
        v = self._validator() | None
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
        v = self._validator() | ...
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
        assert f.name == "conv"
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
        assert f[1].name == "conv"
        assert b

    def test_fail_unjointed(self):
        v = self._validator()
        cxt = ValidationContext()
        cxt.configure(join_on_fail = False)
        r, f, b = v.validate(["1", "a", "3"], cxt)
        assert r == [1, None, 3]
        assert f[1].name == "conv"
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
        assert f.name == "gt"
        assert b

    def test_fail_lt(self):
        v = self._validator()
        r, f, b = v.validate(10)
        assert r is None
        assert f.name == "lt"
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
        assert f[1].name == "gt"
        assert b

    def test_fail_lt(self):
        v = self._validator()
        r, f, b = v.validate([1, 10, 3])
        assert r is None
        assert f[1].name == "lt"
        assert b

    def test_fail_gt_unjointed(self):
        v = self._validator()
        cxt = ValidationContext()
        cxt.configure(join_on_fail = False)
        r, f, b = v.validate([1, -1, 3], cxt)
        assert r == [1, None, 3]
        assert f[1].name == "gt"
        assert not b

    def test_fail_lt_unjointed(self):
        v = self._validator()
        cxt = ValidationContext()
        cxt.configure(join_on_fail = False)
        r, f, b = v.validate([1, 10, 3], cxt)
        assert r == [1, None, 3]
        assert f[1].name == "lt"
        assert not b