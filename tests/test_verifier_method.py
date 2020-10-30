import pytest
from dhampyr.api import v, validate_dict, verifier
from dhampyr.context import ValidationContext


class V:
    v1: +v(int)
    v2: +v(str)

    @verifier
    def ver1(self):
        return len(self.v2) > self.v1

    @verifier
    def ver2(self, context:ValidationContext):
        context.put(ver2=True)
        return self.v1 > context.value


def test_not_invoked():
    cxt = ValidationContext().put(ver1=False, ver2=False, value=0)
    r = validate_dict(V, dict(
        v1 = "abc",
        v2 = "abc",
    ), cxt)

    assert not bool(r)
    assert not cxt.ver1
    assert not cxt.ver2


def test_success():
    cxt = ValidationContext().put(ver1=False, ver2=False, value=0)
    r = validate_dict(V, dict(
        v1 = "2",
        v2 = "abc",
    ), cxt)

    assert bool(r)
    assert not cxt.ver1
    assert cxt.ver2


def test_fail():
    cxt = ValidationContext().put(ver1=False, ver2=False, value=2)
    r = validate_dict(V, dict(
        v1 = "2",
        v2 = "abc",
    ), cxt)

    assert not bool(r)
    assert not cxt.ver1
    assert cxt.ver2
    assert r.failures['ver1'] is None
    assert r.failures['ver2'] is not None


def test_invoke():
    cxt = ValidationContext().put(ver1=False, ver2=False, value=0)
    val = validate_dict(V, dict(
        v1 = "2",
        v2 = "abc",
    ), cxt).get()

    assert val.ver1() is True
    assert val.ver2(ValidationContext().put(value=3)) is False