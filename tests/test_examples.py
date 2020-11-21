import pytest
from enum import Enum, auto
from functools import partial as p
from dhampyr import *


class TestDeclaration:
    def test_declaration(self):
        class C:
            a: +v(int, lambda x: x < 5, lambda x: x > 2) = 0

        r = validate_dict(C, dict(a = "3"))
        d = r.get()

        assert type(d) == C
        assert d.a == 3


class TestComposite:
    def test_composite(self):
        class D:
            a: v(int)

        class C:
            a: v({D})

        r = validate_dict(C, dict(a = dict(a = "3")))
        d = r.get()

        assert type(d) == C
        assert type(d.a) == D
        assert d.a.a == 3

    def test_iterable(self):
        class D:
            a: v(int)

        class C:
            a: v([int], [lambda x: x > 0])
            b: v([{D}])

        r = validate_dict(C, dict(a = [1, 2, 3], b = [dict(a = 4), dict(a = 5), dict(a = 6)]))
        d = r.get()

        assert d.a == [1, 2, 3]
        assert [b.a for b in d.b] == [4, 5, 6]


class TestErrorHandling:
    def test_errors(self):
        def lt3(x):
            return x < 3
        def gt1(x):
            return x > 1

        class C:
            a: v(int) = 0
            b: v(int, lt3) = 0
            c: v(int, lt3, gt1) = 0

        r = validate_dict(C, dict(a = "a", b = "3", c = "1"))

        assert bool(r) is False
        assert len(r.failures) == 3
        assert "a" in r.failures
        assert r.failures["a"].name == "int"
        assert dict([(str(k), f.name) for k, f in r.failures]) == {"a": "int", "b": "lt3", "c": "gt1"}

    def test_composite(self):
        class D:
            b: v([int]) = []

        class C:
            a: v([{D}]) = []

        r = validate_dict(C, dict(a = [dict(b = "123"), dict(b = "45a"), dict(b = "789")]))

        assert r.failures["a"][1]["b"][2].name == "int"
        assert [(str(p), list(p)) for p, f in r.failures] == [("a[1].b[2]", ["a", 1, "b", 2])]


class TestRequirementPhase:
    def test_requirement(self):
        class C:
            a: +v(int) = 0

        r = validate_dict(C, dict())

        assert r.failures["a"].name == "missing"

    def test_operators(self):
        def longer5(x):
            return len(x) > 5

        class C:
            a: +v(str) = "a"
            b: +v(str, longer5) ^ None = "b"
            c: +v(str, longer5) | ... = "c"
            d: +v(str, longer5) ^ ... = "d"

        r = validate_dict(C, dict(a = "", b = None, c = "", d = ""))
        d = r.get()

        assert r.failures["a"].name == "empty"
        assert r.failures["b"] is None
        assert r.failures["c"].name == "longer5"
        assert r.failures["d"] is None
        assert d.b == "b"
        assert d.d == "d"


class TestConversionPhase:
    def test_conversion(self):
        class D:
            a: v(int) = 0

        class E(Enum):
            E1 = auto()
            E2 = auto()

        class C:
            a: v(int) = 0
            b: v(p(int, base=2)) = 0
            c: v(("first", lambda x: x.split(",")[0])) = None
            d: v({D}) = None
            e: v(E) = E.E1

        r = validate_dict(C, dict(a = "3", b = "101", c = "a,b,c", d = dict(a = "4"), e = "E2"))
        d = r.get()

        assert d.a == 3
        assert d.b == 5
        assert d.c == "a"
        assert d.d.a == 4
        assert d.e == E.E2

    def test_iterable(self):
        class C:
            a: v(int) = 0
            b: v([int]) = []

        r = validate_dict(C, dict(a = "123", b = "123"))

        assert r.get().a == 123
        assert r.get().b == [1, 2, 3]


class TestVerificationPhase:
    def test_verification(self):
        def lt3(x):
            return x < 3

        def lt(x, threshold):
            return x < threshold

        class C:
            a: v(int, lt3) = 0
            b: v(int, p(lt, threshold = 3))
            c: v(int, ("less_than_3", lambda x: x < 3)) = 0
            d: v([int], [lt3], lambda x: len(x) < 5) = []

        r = validate_dict(C, dict(a = 3, b = 3, c = 3, d = [1, 1, 1, 1, 1]))
        assert {str(p) for p, _ in r.failures} == {"a", "b", "c", "d"}

        r = validate_dict(C, dict(a = 2, b = 2, c = 2, d = [1, 1, 1, 1]))
        assert {str(p) for p, _ in r.failures} == set()


class TestVerifierMethod:
    def test_verifier_method(self):
        class C:
            a: +v(int)
            b: +v(int)
            c: +v(int)

            @validate()
            def v1(self):
                return self.a > 0

            @validate(a=True)
            def v2(self):
                return self.a > 0

            @validate(a=True, b=False)
            def v3(self):
                return self.a > 0

        r = validate_dict(C, dict(a = "0", b = "0", c = "0"))
        assert {str(p) for p, _ in r.failures} == {"v1", "v2", "v3"}

        r = validate_dict(C, dict(a = "0", b = "a", c = "a"))
        assert {str(p) for p, _ in r.failures} == {"b", "c", "v2"}
        assert r.failures["v2"].name == "v2"

        r = validate_dict(C, dict(a = "0", b = "0", c = "a"))
        assert {str(p) for p, _ in r.failures} == {"c", "v2", "v3"}
        assert r.failures["v3"].name == "v3"


class TestVariable:
    def test_variable(self):
        class C:
            a: v(int, x > 0)
            b: v(str, x.len % 2 == 0)
            c: v(int, x.in_(1, 2, 3))
            d: v(int, x.not_.in_(1, 2, 3))

        r = validate_dict(C, dict(a = 0, b = "abc", c = 0, d = 1))

        assert r.failures["a"].name == "x.gt"
        assert r.failures["a"].kwargs == {"gt.value": 0}
        assert r.failures["b"].name == "x.len.mod.eq"
        assert r.failures["b"].kwargs == {"mod.value": 2, "eq.value": 0}
        assert r.failures["c"].name == "x.in"
        assert r.failures["c"].kwargs == {"in.value": (1, 2, 3)}
        assert r.failures["d"].name == "x.not.in"
        assert r.failures["d"].kwargs == {"in.value": (1, 2, 3)}


class TestValidationContext:
    def test_context(self):
        context = ValidationContext()

        context["a"].put(value = 1)
        context["b"].put(value = 2)
        context["a"][0].put(value = 3)

        def lt(x, cxt:ValidationContext):
            print(cxt.value)
            return x > cxt.value

        class C:
            a: v([int], [lt])
            b: v(int, lt)

        r = validate_dict(C, dict(a = ["2", "2"], b = "2"), context)

        assert {str(p) for p, _ in r.failures} == {"a[0]", "b"}


class TestUndeclaredKeys:
    def test_remainders(self):
        class D:
            d: v(int) = 0

        class C:
            a: v(int) = 0
            b: v({D}) = None
            c: v([{D}]) = []

        r = validate_dict(C, dict(a = "1", b = dict(d = "2", e = "a"), c = [dict(d = "3", e1 = "b"), dict(d = "4", e2 = "c")], d = "d"))
        cxt = r.context

        assert cxt.remainders == dict(d = "d")
        assert cxt["b"].remainders == dict(e = "a")
        assert cxt["c"][0].remainders == dict(e1 = "b")
        assert cxt["c"][1].remainders == dict(e2 = "c")


class TestConfigurations:
    def test_configurations(self):
        try:
            with dhampyr() as cfg:
                cfg.name = "global"
                cfg.join_on_fail = False

            def add_name(x, cxt:ValidationContext):
                return f"{x}.{cxt.config.name}"

            @dhampyr(name="static", join_on_fail=False)
            class D:
                a: v(add_name)

            class C:
                a: v(add_name)
                b: v({D})
                c: v(add_name)

            context = ValidationContext()
            context["c"].configure(name="runtime", join_on_fail=False)

            d = validate_dict(C, dict(a = "a", b = dict(a = "b"), c = "c"), context).get()

            assert d.a == "a.global"
            assert d.b.a == "b.static"
            assert d.c == "c.runtime"
        finally:
            with dhampyr() as cfg:
                cfg.name = "default"
                cfg.join_on_fail = True
