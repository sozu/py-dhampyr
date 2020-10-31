import pytest
from enum import Enum
from functools import partial
from dhampyr.failures import ValidationFailure, CompositeValidationFailure
from dhampyr.api import v, converter, verifier


class TestConverter:
    def test_func(self):
        def conv(v):
            return int(v)
        c = converter(conv)
        r, f = c.convert("1")
        assert c.name == "conv"
        assert c.func is conv
        assert not c.is_iter
        assert c.accepts is None
        assert c.returns is None
        assert r == 1
        assert f is None

    def test_func_annotated(self):
        def conv(v) -> str:
            return int(v)
        c = converter(conv)
        r, f = c.convert("1")
        assert c.name == "conv"
        assert c.func is conv
        assert not c.is_iter
        assert c.accepts is None
        assert c.returns is str
        assert r == 1
        assert f is None

    def test_type(self):
        c = converter(int)
        r, f = c.convert("1")
        assert c.name == "int"
        assert c.func is int
        assert not c.is_iter
        assert c.accepts is int
        assert c.returns is int
        assert r == 1
        assert f is None

    def test_enum(self):
        class E(Enum):
            e1 = 0
            e2 = 1
        c = converter(E)
        r, f = c.convert("e2")
        assert c.name == "E"
        assert not c.is_iter
        assert c.accepts is str
        assert c.returns is E
        assert r == E.e2
        assert f is None

    def test_partial(self):
        c = converter(partial(int, base=2))
        r, f = c.convert("100")
        assert c.name == "int"
        assert not c.is_iter
        assert c.accepts is int
        assert c.returns is int
        assert c.kwargs == dict(base=2)
        assert r == 4
        assert f is None

    def test_nested_partial(self):
        def p0(v, base, inc) -> int:
            return int(v, base) + inc
        p1 = partial(p0, base=2)
        p2 = partial(p1, inc=3)
        c = converter(p2)
        r, f = c.convert("100")
        assert c.name == "p0"
        assert not c.is_iter
        assert c.accepts is None
        assert c.returns is int
        assert c.kwargs == dict(inc=3, base=2)
        assert r == 7
        assert f is None

    def test_nested_convert(self):
        class C:
            c1: v(int)
            c2: v(str)
        c = converter({C})
        r, f = c.convert(dict(c1=1, c2="a"))
        assert c.name == "C"
        assert not c.is_iter
        assert c.accepts is dict
        assert c.returns is C
        assert isinstance(r, C)
        assert r.c1 == 1
        assert r.c2 == "a"
        assert f is None

    def test_iter(self):
        c = converter([int])
        r, f = c.convert("123")
        assert c.name == "int"
        assert c.is_iter
        assert c.accepts is int
        assert c.returns is int
        assert r == [1,2,3]
        assert f is None

    def test_name(self):
        c = converter(("conv", int))
        r, f = c.convert("1")
        assert c.name == "conv"
        assert not c.is_iter
        assert c.accepts is int
        assert c.returns is int
        assert r == 1
        assert f is None

    def test_iter_name(self):
        c = converter([("conv", int)])
        r, f = c.convert("123")
        assert c.name == "conv"
        assert c.is_iter
        assert c.accepts is int
        assert c.returns is int
        assert r == [1,2,3]
        assert f is None


class TestVerifier:
    def test_func(self):
        def ver(v):
            return True
        vf = verifier(ver)
        f = vf.verify(1)
        assert vf.name == "ver"
        assert vf.func is ver
        assert not vf.is_iter
        assert f is None

    def test_partial(self):
        def p0(v, th):
            return v > th
        p1 = partial(p0, th=1)
        vf = verifier(p1)
        f = vf.verify(2)
        assert vf.name == "p0"
        assert vf.kwargs == dict(th=1)
        assert not vf.is_iter
        assert f is None

    def test_nested_partial(self):
        def p0(v, th, mul):
            return (v * mul) > th
        p1 = partial(p0, th=5)
        p2 = partial(p1, mul=3)
        vf = verifier(p2)
        f = vf.verify(2)
        assert vf.name == "p0"
        assert vf.kwargs == dict(th=5, mul=3)
        assert not vf.is_iter
        assert f is None

    def test_iter(self):
        def ver(v):
            return v < 3
        vf = verifier([ver])
        f = vf.verify([1,2,3])
        assert vf.name == "ver"
        assert vf.func is ver
        assert vf.is_iter
        assert isinstance(f, CompositeValidationFailure)
        assert len(f) == 1
        assert f[2].name == "ver"

    def test_name(self):
        def ver(v):
            return True
        vf = verifier(("v", ver))
        f = vf.verify(1)
        assert vf.name == "v"
        assert vf.func is ver
        assert not vf.is_iter
        assert f is None

    def test_iter_name(self):
        def ver(v):
            return v < 3
        vf = verifier([("v", ver)])
        f = vf.verify([1,2,3])
        assert vf.name == "v"
        assert vf.func is ver
        assert vf.is_iter
        assert isinstance(f, CompositeValidationFailure)
        assert len(f) == 1
        assert f[2].name == "v"