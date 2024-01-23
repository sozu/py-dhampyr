import pytest
from enum import Enum, auto
from functools import partial as p
from typing import Optional
from dhampyr import *


class TestDeclaration:
    def test_declaration(self):
        class C:
            a: int = +v(..., lambda x: x < 5, lambda x: x > 2, default=0)

        r = validate_dict(C, dict(a = "3"))
        d = r.get()

        assert type(d) == C
        assert d.a == 3


class TestComposite:
    def test_composite(self):
        class D:
            a: int = v()

        class C:
            a: D = v()

        r = validate_dict(C, dict(a = dict(a = "3")))
        d = r.get()

        assert type(d) == C
        assert type(d.a) == D
        assert d.a.a == 3

    def test_iterable(self):
        class D:
            a: int = v()

        class C:
            a: list[int] = v(..., [lambda x: x > 0])
            b: list[D] = v()

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
            a: int = v(default=0)
            b: int = v(..., lt3, default=0)
            c: int = v(..., lt3, gt1, default=0)

        r = validate_dict(C, dict(a = "a", b = "3", c = "1"))

        assert bool(r) is False
        assert len(r.failures) == 3
        assert "a" in r.failures
        assert r.failures["a"].name == "int"
        assert dict([(str(k), f.name) for k, f in r.failures]) == {"a": "int", "b": "lt3", "c": "gt1"}

    def test_composite(self):
        class D:
            b: list[int] = v(default_factory=lambda: [])

        class C:
            a: list[D] = v(default_factory=lambda: [])

        r = validate_dict(C, dict(a = [dict(b = "123"), dict(b = "45a"), dict(b = "789")]))

        assert r.failures["a"][1]["b"][2].name == "int"
        assert [(str(p), list(p)) for p, f in r.failures] == [("a[1].b[2]", ["a", 1, "b", 2])]


class TestRequirementPhase:
    def test_requirement(self):
        class C:
            a: int = +v(default=0)

        r = validate_dict(C, dict())

        assert r.failures["a"].name == "missing"

    def test_operators(self):
        def longer5(x):
            return len(x) > 5

        class C:
            a: str = +v(default="a")
            b: str = +v(..., longer5, default="b") ^ None
            c: str = +v(..., longer5, default="c") / ...
            d: str = +v(..., longer5, default="d") ^ ...

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
            a: int = v(default=0)

        class E(Enum):
            E1 = auto()
            E2 = auto()

        class C:
            a: int = v(int, default=0)
            b: int = v(p(int, base=2), default=0)
            c: Optional[int] = v(("first", lambda x: x.split(",")[0]), default=None)
            d: Optional[D] = v(default=None)
            e: E = v(E, default=E.E1)

        r = validate_dict(C, dict(a = "3", b = "101", c = "a,b,c", d = dict(a = "4"), e = "E2"))
        d = r.get()

        assert d.a == 3
        assert d.b == 5
        assert d.c == "a"
        assert d.d.a == 4
        assert d.e == E.E2

    def test_iterable(self):
        class C:
            a: int = v(default=0)
            b: list[int] = v(default_factory=lambda: [])

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
            a: int = v(..., lt3, default=0)
            b: int = v(..., p(lt, threshold = 3))
            c: int = v(..., ("less_than_3", lambda x: x < 3), default=0)
            d: list[int] = v(..., [lt3], lambda x: len(x) < 5, default_factory=lambda: [])

        r = validate_dict(C, dict(a = 3, b = 3, c = 3, d = [1, 1, 1, 1, 1]))
        assert {str(p) for p, _ in r.failures} == {"a", "b", "c", "d"}

        r = validate_dict(C, dict(a = 2, b = 2, c = 2, d = [1, 1, 1, 1]))
        assert {str(p) for p, _ in r.failures} == set()


class TestVerifierMethod:
    def test_verifier_method(self):
        class C:
            a: int = +v()
            b: int = +v()
            c: int = +v()

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
            a: int = v(..., x > 0)
            b: str = v(..., x.len % 2 == 0)
            c: int = v(..., x.in_(1, 2, 3))
            d: int = v(..., x.not_.in_(1, 2, 3))

        r = validate_dict(C, dict(a = 0, b = "abc", c = 0, d = 1))

        fa, fb, fc, fd = (r.failures[k] for k in ("a", "b", "c", "d"))
        assert fa and fb and fc and fd
        assert fa.name == "x.gt"
        assert fa.kwargs == {"gt.value": 0}
        assert fb.name == "x.len.mod.eq"
        assert fb.kwargs == {"mod.value": 2, "eq.value": 0}
        assert fc.name == "x.in"
        assert fc.kwargs == {"in.value": (1, 2, 3)}
        assert fd.name == "x.not.in"
        assert fd.kwargs == {"in.value": (1, 2, 3)}


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
            a: list[int] = v(..., [lt])
            b: int = v(..., lt)

        r = validate_dict(C, dict(a = ["2", "2"], b = "2"), context)

        assert {str(p) for p, _ in r.failures} == {"a[0]", "b"}


class TestUndeclaredKeys:
    def test_remainders(self):
        class D:
            d: int = v(default=0)

        class C:
            a: int = v(default=0)
            b: D = v(default=None)
            c: list[D] = v(default_factory=lambda: [])

        r = validate_dict(C, dict(a = "1", b = dict(d = "2", e = "a"), c = [dict(d = "3", e1 = "b"), dict(d = "4", e2 = "c")], d = "d"))
        cxt = r.context

        assert cxt.remainders == dict(d = "d")
        assert cxt["b"].remainders == dict(e = "a")
        assert cxt["c"][0].remainders == dict(e1 = "b")
        assert cxt["c"][1].remainders == dict(e2 = "c")


class TestConfigurations:
    def test_configurations(self):
        with default_config() as cfg:
            cfg.name = "global"
            cfg.join_on_fail = False

            def add_name(x, cxt:ValidationContext):
                return f"{x}.{cxt.config.name}"

            @validatable(name="static", join_on_fail=False)
            class D:
                a: str = v(add_name)

            class C:
                a: str = v(add_name)
                b: D = v(D)
                c: str = v(add_name)

            context = ValidationContext()
            context["c"].configure(name="runtime", join_on_fail=False)

            d = validate_dict(C, dict(a = "a", b = dict(a = "b"), c = "c"), context).get()

            assert d.a == "a.global"
            assert d.b.a == "b.static"
            assert d.c == "c.runtime"