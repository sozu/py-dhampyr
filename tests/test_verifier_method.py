import pytest
from dhampyr.api import v, validate_dict, validate, validatable
from dhampyr.context import ValidationContext


class TestNoDependency:
    @validatable()
    class V:
        v1: int = +v()
        v2: str = +v()

        @validate()
        def ver1(self):
            return len(self.v2) > self.v1

        @validate()
        def ver2(self, context:ValidationContext):
            context.put(ver2=True)
            return self.v1 > context.value

    def test_not_invoked(self):
        cxt = ValidationContext().put(ver1=False, ver2=False, value=0)
        r = validate_dict(TestNoDependency.V, dict(
            v1 = "abc",
            v2 = "abc",
        ), cxt)

        assert not bool(r)
        assert not cxt.ver1
        assert not cxt.ver2

    def test_success(self):
        cxt = ValidationContext().put(ver1=False, ver2=False, value=0)
        r = validate_dict(TestNoDependency.V, dict(
            v1 = "2",
            v2 = "abc",
        ), cxt)

        assert bool(r)
        assert not cxt.ver1
        assert cxt.ver2

    def test_fail(self):
        cxt = ValidationContext().put(ver1=False, ver2=False, value=2)
        r = validate_dict(TestNoDependency.V, dict(
            v1 = "2",
            v2 = "abc",
        ), cxt)

        assert not bool(r)
        assert not cxt.ver1
        assert cxt.ver2
        assert r.failures['ver1'] is None
        assert r.failures['ver2'] is not None

    def test_invoke(self):
        cxt = ValidationContext().put(ver1=False, ver2=False, value=0)
        val = validate_dict(TestNoDependency.V, dict(
            v1 = "2",
            v2 = "abc",
        ), cxt).get()

        assert val.ver1() is True
        assert val.ver2(ValidationContext().put(value=3)) is False


class TestDependency:
    class V:
        v1: +v(int)
        v2: +v(int)
        v3: +v(int)

        @validate()
        def ver1(self):
            return self.v1 > 0

        @validate(v1=True)
        def ver2(self):
            return self.v1 > 0

        @validate(v1=True, v2=True)
        def ver3(self):
            return self.v1 > 0

        @validate(v1=True, v3=False)
        def ver4(self):
            return self.v1 > 0

    def test_no_failure(self):
        r = validate_dict(TestDependency.V, dict(v1=1, v2=1, v3=1))
        assert bool(r)

    def test_all_failed(self):
        r = validate_dict(TestDependency.V, dict(v1="a", v2="a", v3="a"))
        assert not bool(r)
        assert {str(p) for p, _ in r.failures} == {"v1", "v2", "v3"}

    def test_all_method_failed(self):
        r = validate_dict(TestDependency.V, dict(v1=0, v2=0, v3=0))
        assert not bool(r)
        assert {str(p) for p, _ in r.failures} == {"ver1", "ver2", "ver3", "ver4"}

    def test_positive(self):
        r = validate_dict(TestDependency.V, dict(v1=0, v2="a", v3=0))
        assert not bool(r)
        assert {str(p) for p, _ in r.failures} == {"v2", "ver2", "ver4"}

    def test_negative(self):
        r = validate_dict(TestDependency.V, dict(v1=0, v2="a", v3="a"))
        assert not bool(r)
        assert {str(p) for p, _ in r.failures} == {"v2", "v3", "ver2"}

    def test_multiple_positive(self):
        r = validate_dict(TestDependency.V, dict(v1=0, v2=0, v3="a"))
        assert not bool(r)
        assert {str(p) for p, _ in r.failures} == {"v3", "ver2", "ver3"}

