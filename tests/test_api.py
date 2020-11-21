import pytest
from enum import Enum
from functools import partial
from datetime import datetime, date, timezone
from dhampyr.failures import ValidationFailure, CompositeValidationFailure
from dhampyr.context import ValidationContext
from dhampyr.api import v, converter, verifier, analyze_specifier


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

    def test_context_arg(self):
        def conv(val, cxt:ValidationContext):
            return int(val) + cxt.val
        c = converter(conv)
        r, f = c.convert("3", ValidationContext().put(val=2))
        assert c.name == "conv"
        assert not c.is_iter
        assert c.accepts is None
        assert c.returns is None
        assert r == 5
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

    def test_context_arg(self):
        def ver(val, cxt:ValidationContext):
            return val > cxt.val
        vf = verifier(ver)
        f = vf.verify(4, ValidationContext().put(val=3))
        assert vf.name == "ver"
        assert vf.func is ver
        assert not vf.is_iter
        assert f is None
        f = vf.verify(3)
        assert f is not None


class TestAnalyzeSpecifier:
    def test_builtin_type(self):
        f, n, it, ot, args, kwargs = analyze_specifier(int, (), {})

        assert f is int
        assert n == "int"
        assert it is int
        assert ot is int
        assert args == ()
        assert kwargs == {}

    def test_user_type(self):
        class C:
            def __init__(self, v):
                self.v = v
        f, n, it, ot, args, kwargs = analyze_specifier(C, (), {})

        assert f is C
        assert n == "C"
        assert it is None
        assert ot is C
        assert args == ()
        assert kwargs == {}

    def test_user_type_sig(self):
        class C:
            def __init__(self, v:str):
                self.v = v
        f, n, it, ot, args, kwargs = analyze_specifier(C, (), {})

        assert f is C
        assert n == "C"
        assert it is str
        assert ot is C
        assert args == ()
        assert kwargs == {}

    def test_builtin_method(self):
        f, n, it, ot, args, kwargs = analyze_specifier(date.fromisoformat, (), {})

        assert f == date.fromisoformat
        assert n == "fromisoformat"
        assert it is None
        assert ot is None
        assert args == ()
        assert kwargs == {}

    def test_builtin_callable(self):
        f, n, it, ot, args, kwargs = analyze_specifier(abs, (), {})

        assert f is abs
        assert n == "abs"
        assert it is None
        assert ot is None
        assert args == ()
        assert kwargs == {}

    def test_user_callable(self):
        def func(v):
            return int(v)
        f, n, it, ot, args, kwargs = analyze_specifier(func, (), {})

        assert f is func
        assert n == "func"
        assert it is None
        assert ot is None
        assert args == ()
        assert kwargs == {}

    def test_user_callable_sig(self):
        def func(v:str) -> int:
            return int(v)
        f, n, it, ot, args, kwargs = analyze_specifier(func, (), {})

        assert f is func
        assert n == "func"
        assert it is str
        assert ot is int
        assert args == ()
        assert kwargs == {}

    def test_partial_builtin_type(self):
        func = partial(int, base=2)
        f, n, it, ot, args, kwargs = analyze_specifier(func, (), {})

        assert f is func
        assert n == "int"
        assert it is int
        assert ot is int
        assert args == ()
        assert kwargs == {"base": 2}

    def test_partial_builtin_method(self):
        func = partial(datetime.fromtimestamp, tz=timezone.utc)
        f, n, it, ot, args, kwargs = analyze_specifier(func, (), {})

        assert f is func
        assert n == "fromtimestamp"
        assert it is None
        assert ot is None
        assert args == ()
        assert kwargs == {"tz": timezone.utc}

    def test_partial_builtin_callable(self):
        func = partial(min, 1)
        f, n, it, ot, args, kwargs = analyze_specifier(func, (), {})

        assert f is func
        assert n == "min"
        assert it is None
        assert ot is None
        assert args == (1,)
        assert kwargs == {}

    def test_partial_user_type(self):
        class C:
            def __init__(self, v:str, w:int):
                self.v = v
                self.w = w
        func = partial(C, v="a")
        f, n, it, ot, args, kwargs = analyze_specifier(func, (), {})

        assert f is func
        assert n == "C"
        assert it is int
        assert ot is C
        assert args == ()
        assert kwargs == {"v": "a"}

    def test_partial_user_callable(self):
        def inner(v, w):
            return 0
        func = partial(inner, v="a")
        f, n, it, ot, args, kwargs = analyze_specifier(func, (), {})

        assert f is func
        assert n == "inner"
        assert it is None
        assert ot is None
        assert args == ()
        assert kwargs == {"v": "a"}

    def test_partial_user_callable_sig(self):
        def inner(v:str, w:int) -> float:
            return 0
        func = partial(inner, v="a")
        f, n, it, ot, args, kwargs = analyze_specifier(func, (), {})

        assert f is func
        assert n == "inner"
        assert it is int
        assert ot is float
        assert args == ()
        assert kwargs == {"v": "a"}