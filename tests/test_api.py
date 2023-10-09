import pytest
from decimal import Decimal
from enum import Enum
from functools import partial
from datetime import datetime, date, timezone
from typing import Any, Union, Optional
from dhampyr.failures import ValidationFailure, CompositeValidationFailure
from dhampyr.context import ValidationContext
from dhampyr.requirement import RequirementPolicy
from dhampyr.api import v, converter, verifier, validatable, parse_validators


class TestConverter:
    def test_func(self):
        def conv(v):
            return int(v)
        c = converter(conv).create(ValidationContext())
        r, f = c.convert("1")
        assert c.name == "conv"
        assert not c.is_iter
        assert c.accepts is Any
        assert c.returns is Any
        assert r == 1
        assert f is None

    def test_func_annotated(self):
        def conv(v: str) -> int:
            return int(v)
        c = converter(conv).create(ValidationContext())
        r, f = c.convert("1")
        assert c.name == "conv"
        assert not c.is_iter
        assert c.accepts is str
        assert c.returns is int
        assert r == 1
        assert f is None

    def test_builtin(self):
        c = converter(int).create(ValidationContext())
        r, f = c.convert("1")
        assert c.name == "int"
        assert not c.is_iter
        assert c.accepts == Union[str, int, float, Decimal]
        assert c.returns is int
        assert r == 1
        assert f is None

    def test_enum(self):
        class E(Enum):
            e1 = 0
            e2 = 1
        c = converter(E).create(ValidationContext())
        r, f = c.convert("e2")
        assert c.name == "E"
        assert not c.is_iter
        assert c.accepts == Union[E, str]
        assert c.returns is E
        assert r == E.e2
        assert f is None

    def test_partial(self):
        c = converter(partial(int, base=2)).create(ValidationContext())
        r, f = c.convert("100")
        assert c.name == "int"
        assert not c.is_iter
        assert c.accepts == Union[str, int, float, Decimal]
        assert c.returns is int
        assert c.kwargs == dict(base=2)
        assert r == 4
        assert f is None

    def test_nested_partial(self):
        def p0(v: str, base, inc) -> int:
            return int(v, base) + inc
        p1 = partial(p0, base=2)
        p2 = partial(p1, inc=3)
        c = converter(p2).create(ValidationContext())
        r, f = c.convert("100")
        assert c.name == "p0"
        assert not c.is_iter
        assert c.accepts is str
        assert c.returns is int
        assert c.kwargs == dict(inc=3, base=2)
        assert r == 7
        assert f is None

    #def test_nested_convert(self):
    #    class C:
    #        c1: v(int)
    #        c2: v(str)
    #    c = converter({C})
    #    r, f = c.convert(dict(c1=1, c2="a"))
    #    assert c.name == "C"
    #    assert not c.is_iter
    #    assert c.accepts is dict
    #    assert c.returns is C
    #    assert isinstance(r, C)
    #    assert r.c1 == 1
    #    assert r.c2 == "a"
    #    assert f is None

    def test_iter(self):
        c = converter([int]).create(ValidationContext())
        r, f = c.convert("123")
        assert c.name == "int"
        assert c.is_iter
        assert c.accepts == Union[str, int, float, Decimal]
        assert c.returns is int
        assert r == [1,2,3]
        assert f is None

    def test_name(self):
        c = converter(("conv", int)).create(ValidationContext())
        r, f = c.convert("1")
        assert c.name == "conv"
        assert not c.is_iter
        assert c.accepts == Union[str, int, float, Decimal]
        assert c.returns is int
        assert r == 1
        assert f is None

    def test_iter_name(self):
        c = converter([("conv", int)]).create(ValidationContext())
        r, f = c.convert("123")
        assert c.name == "conv"
        assert c.is_iter
        assert c.accepts == Union[str, int, float, Decimal]
        assert c.returns is int
        assert r == [1,2,3]
        assert f is None

    def test_context_arg(self):
        def conv(val, cxt:ValidationContext):
            return int(val) + cxt.val
        cxt = ValidationContext().put(val=2)
        c = converter(conv).create(cxt)
        r, f = c.convert("3", cxt)
        assert c.name == "conv"
        assert not c.is_iter
        assert c.accepts is Any
        assert c.returns is Any
        assert r == 5
        assert f is None


class TestVerifier:
    def test_func(self):
        def ver(v):
            return True
        vf = verifier(ver)
        f = vf.verify(1)
        assert vf.name == "ver"
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
        assert vf.is_iter
        assert isinstance(f, CompositeValidationFailure)
        assert len(f) == 1
        assert f[2].name == "ver" # type: ignore

    def test_name(self):
        def ver(v):
            return True
        vf = verifier(("v", ver))
        f = vf.verify(1)
        assert vf.name == "v"
        assert not vf.is_iter
        assert f is None

    def test_iter_name(self):
        def ver(v):
            return v < 3
        vf = verifier([("v", ver)])
        f = vf.verify([1,2,3])
        assert vf.name == "v"
        assert vf.is_iter
        assert isinstance(f, CompositeValidationFailure)
        assert len(f) == 1
        assert f[2].name == "v" # type: ignore

    def test_context_arg(self):
        def ver(val, cxt:ValidationContext):
            return val > cxt.val
        vf = verifier(ver)
        f = vf.verify(4, ValidationContext().put(val=3))
        assert vf.name == "ver"
        assert not vf.is_iter
        assert f is None
        f = vf.verify(3)
        assert f is not None


class TestParseValidators:
    def test_annotation(self):
        @validatable()
        class V:
            v1: int = v(..., lambda x: x > 0)
            v2: int = v(None, lambda x: x > 0)
            v3: int = v(int, lambda x: x > 0, lambda x: x < 10)
            v4: float = v(int, lambda x: x > 0, lambda x: x < 10)
            v5: float = v([int], lambda x: x > 0, lambda x: x < 10)
            v6: float = v(("test", int), lambda x: x > 0, lambda x: x < 10)
            v7: float = v([("test", int)], lambda x: x > 0, lambda x: x < 10)
            v8: int = v(..., alias="E")
            v9: Optional[int] = v(..., default=3)
            v10: Optional[int] = v(..., default_factory=lambda: 3)
            v11: int = +v()
            v12: int = v() & None
            v13: int = v() & ...
            v14: int = v() / None
            v15: int = v() / ...

        vals = parse_validators(V)

        cxt = ValidationContext()

        vv = vals['v1'].create(cxt)
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 1
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is False

        vv = vals['v2'].create(cxt)
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 1
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is False

        vv = vals['v3'].create(cxt)
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 2
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is False

        vv = vals['v4'].create(cxt)
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 2
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is False

        vv = vals['v5'].create(cxt)
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 2
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is True

        vv = vals['v6'].create(cxt)
        assert vv.converter.name == "test"
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 2
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is False

        vv = vals['v7'].create(cxt)
        assert vv.converter.name == "test"
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 2
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is True

        vv = vals['v8'].create(cxt)
        assert vv.key == "E"
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 0
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is False

        vv = vals['v9'].create(cxt)
        assert vals['v9'].default == 3
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 0
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is False

        vv = vals['v10'].create(cxt)
        assert vals['v10'].default_factory and vals['v10'].default_factory() == 3
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 0
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is False

        vv = vals['v11'].create(cxt)
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 0
        assert vv.requires is True
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.FAIL, RequirementPolicy.REQUIRES, RequirementPolicy.REQUIRES)
        assert vv.accept_list is False

        vv = vals['v12'].create(cxt)
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 0
        assert vv.requires is True
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.FAIL, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is False

        vv = vals['v13'].create(cxt)
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 0
        assert vv.requires is True
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.FAIL)
        assert vv.accept_list is False

        vv = vals['v14'].create(cxt)
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 0
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTINUE, RequirementPolicy.CONTEXTUAL)
        assert vv.accept_list is False

        vv = vals['v15'].create(cxt)
        assert vv.converter.accepts == Union[str, int, float, Decimal]
        assert vv.converter.returns is int
        assert len(vv.verifiers) == 0
        assert vv.requires is False
        assert (vv.requirement.missing, vv.requirement.null, vv.requirement.empty) \
            == (RequirementPolicy.SKIP, RequirementPolicy.CONTEXTUAL, RequirementPolicy.CONTINUE)
        assert vv.accept_list is False