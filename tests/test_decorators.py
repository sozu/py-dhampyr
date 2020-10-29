import pytest
from dhampyr.decorators import strict
from dhampyr.converter import ConversionFailure
from dhampyr.api import v, validate_dict


class TestStrictType:
    @strict
    class A:
        v1: +v(int)
        v2: +v(lambda v: int(v))

    def test_success(self):
        r = validate_dict(TestStrictType.A, dict(
            v1 = 1,
            v2 = "2",
        ))

        assert bool(r) is True
        assert r.get().v1 == 1
        assert r.get().v2 == 2

    def test_unmatch(self):
        r = validate_dict(TestStrictType.A, dict(
            v1 = "1",
            v2 = "2",
        ))

        assert bool(r) is False
        assert r.get().v2 == 2
        assert isinstance(r.failures['v1'], ConversionFailure)
        assert r.failures['v1'].name == 'int'


class TestStrictFunction:
    @strict
    def another(cls):
        return cls

    @another
    class A:
        v1: +v(int)
        v2: +v(lambda v: int(v))

    def test_success(self):
        r = validate_dict(TestStrictType.A, dict(
            v1 = 1,
            v2 = "2",
        ))

        assert bool(r) is True
        assert r.get().v1 == 1
        assert r.get().v2 == 2

    def test_unmatch(self):
        r = validate_dict(TestStrictType.A, dict(
            v1 = "1",
            v2 = "2",
        ))

        assert bool(r) is False
        assert r.get().v2 == 2
        assert isinstance(r.failures['v1'], ConversionFailure)
        assert r.failures['v1'].name == 'int'