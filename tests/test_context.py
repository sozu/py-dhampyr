import pytest
from functools import partial as p
from dhampyr.config import typed_config
from dhampyr.context import ValidationContext, analyze_callable
from dhampyr.api import validatable


class TestPath:
    def test_root(self):
        c = ValidationContext()
        assert str(c.path) == ""

    def test_key(self):
        c = ValidationContext()["abc"]
        assert str(c.path) == "abc"

    def test_keys(self):
        c = ValidationContext()["abc"]["def"]["ghi"]
        assert str(c.path) == "abc.def.ghi"

    def test_index(self):
        c = ValidationContext()[0]
        assert str(c.path) == "[0]"

    def test_indexes(self):
        c = ValidationContext()[0][1][2]
        assert str(c.path) == "[0][1][2]"

    def test_mixed(self):
        c = ValidationContext()["abc"][0]["def"]["ghi"][1]
        assert str(c.path) == "abc[0].def.ghi[1]"


class TestAttribute:
    def test_root(self):
        c = ValidationContext().put(
            a1=1, a2="a",
        )
        assert c.a1 == 1
        assert c.a2 == "a"

    def test_inherit(self):
        c = ValidationContext().put(
            a1=1, a2="a",
        )[0].put(
            a3 = 3,
        )
        assert c.a1 == 1
        assert c.a2 == "a"
        assert c.a3 == 3

    def test_overwrite(self):
        c = ValidationContext().put(
            a1=1, a2="a",
        )[0].put(
            a1=2, a3=3,
        )
        assert c.a1 == 2
        assert c.a2 == "a"
        assert c.a3 == 3


@pytest.mark.parametrize("share", [True, False])
class TestConfig:
    def test_root(self, share: bool):
        c = ValidationContext().configure(share_context=share)
        assert c.config.name == "default"

    def test_each(self, share: bool):
        c = ValidationContext().configure(share_context=share)
        c0 = c[0]
        c1 = c[1]
        c2 = c[2]
        c0.configure(name="c0")
        c1.configure(name="c1")
        c00 = c[0][0]
        c00.configure(name="c00")
        c10 = c[1][0]
        if share:
            assert c.config.name == "c00"
            assert c0.config.name == "c00"
            assert c1.config.name == "c00"
            assert c2.config.name == "c00"
            assert c00.config.name == "c00"
            assert c10.config.name == "c00"
        else:
            assert c.config.name == "default"
            assert c0.config.name == "c0"
            assert c1.config.name == "c1"
            assert c2.config.name == "default"
            assert c00.config.name == "c00"
            assert c10.config.name == "c1"

    def test_typed(self, share: bool):
        try:
            typed_config().clear()

            @validatable(name="D")
            class D:
                pass
            @validatable(name="C")
            class C:
                pass

            c = ValidationContext().configure(share_context=share)
            assert c.config.name == "default"
            with c.on(C):
                assert c.config.name == "C"
                with c.on(D):
                    assert c.config.name == "D"
                assert c.config.name == "C"
            assert c.config.name == "default"
        finally:
            typed_config().clear()

    def test_each_typed(self, share: bool):
        try:
            typed_config().clear()

            @validatable(name="D")
            class D:
                pass
            @validatable(name="C")
            class C:
                pass

            c = ValidationContext().configure(share_context=share)
            c0 = c[0]
            with c0.on(C):
                assert c0.config.name == "C"
                with c0.on(D):
                    assert c0.config.name == "D"
            c0.configure(name = "c0")
            with c0.on(C):
                assert c0.config.name == "c0"
            c00 = c0[0]
            with c00.on(C):
                assert c00.config.name == "c0"
        finally:
            typed_config().clear()


def func(a: int) -> str:
    return f"{a}"

def func_multi(a: int, b: float) -> str:
    return f"{a+b}"

def func_default(a: int, b: float, c: int = 3) -> str:
    return f"{a+b+c}"

def func_var_positional(a: int, b: float, *args: int) -> str:
    return f"{a+b+sum(args)}"

def func_var_keyword(a: int, b: float, **kwargs: int) -> str:
    return f"{a+b+sum(v for v in kwargs.values())}"


def cfunc(a: int, cxt: ValidationContext) -> str:
    return f"{a+cxt.x}"

def cfunc_multi(a: int, cxt: ValidationContext, b: float) -> str:
    return f"{a+b+cxt.x}"

def cfunc_positional(a: int, cxt: ValidationContext, b: float, /) -> str:
    return f"{a+b+cxt.x}"

def cfunc_keyword(a: int, b: float, /, cxt: ValidationContext) -> str:
    return f"{a+b+cxt.x}"

def cfunc_var_positional(a: int, b: float, *args: int, cxt: ValidationContext) -> str:
    return f"{a+b+sum(args)+cxt.x}"

def cfunc_var_keyword(a: int, cxt: ValidationContext, b: float, **kwargs: int) -> str:
    return f"{a+b+sum(v for v in kwargs.values())+cxt.x}"


class TestAnalyzeCallable:
    def test_call(self):
        cc = analyze_callable(func)
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, ValidationContext.default()) == "1"

    def test_multi(self):
        with pytest.raises(TypeError):
            analyze_callable(func_multi)

        cc = analyze_callable(p(func_multi, 3))
        assert (cc.in_type, cc.out_type) == (float, str)
        assert cc(1, ValidationContext.default()) == "4"

        cc = analyze_callable(p(func_multi, b=3))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, ValidationContext.default()) == "4"

    def test_default(self):
        with pytest.raises(TypeError):
            analyze_callable(func_default)

        cc = analyze_callable(p(func_default, 3))
        assert (cc.in_type, cc.out_type) == (float, str)
        assert cc(1, ValidationContext.default()) == "7"

        cc = analyze_callable(p(func_default, b=3))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, ValidationContext.default()) == "7"

    def test_var_positional(self):
        with pytest.raises(TypeError):
            analyze_callable(func_var_positional)

        cc = analyze_callable(p(func_var_positional, 3, 4, 5, 6))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, ValidationContext.default()) == "19"

        cc = analyze_callable(p(func_var_positional, 3))
        assert (cc.in_type, cc.out_type) == (float, str)
        assert cc(1, ValidationContext.default()) == "4"

        cc = analyze_callable(p(func_var_positional, b=3))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, ValidationContext.default()) == "4"

    def test_var_keyword(self):
        with pytest.raises(TypeError):
            analyze_callable(func_var_keyword)

        with pytest.raises(TypeError):
            analyze_callable(p(func_var_keyword, 3, 4, c=5, d=6))

        cc = analyze_callable(p(func_var_keyword, 3))
        assert (cc.in_type, cc.out_type) == (float, str)
        assert cc(1, ValidationContext.default()) == "4"

        cc = analyze_callable(p(func_var_keyword, b=3))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, ValidationContext.default()) == "4"

        cc = analyze_callable(p(func_var_keyword, b=3, c=5, d=6))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, ValidationContext.default()) == "15"

    def test_cxt_call(self):
        cxt = ValidationContext().put(x=10)
        cc = analyze_callable(cfunc)
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, cxt) == "11"

    def test_cxt_multi(self):
        cxt = ValidationContext().put(x=10)
        with pytest.raises(TypeError):
            analyze_callable(cfunc_multi)

        cc = analyze_callable(p(cfunc_multi, 3))
        assert (cc.in_type, cc.out_type) == (float, str)
        assert cc(1, cxt) == "14"

        cc = analyze_callable(p(cfunc_multi, b=3))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, cxt) == "14"

    def test_cxt_default(self):
        cxt = ValidationContext().put(x=10)
        with pytest.raises(TypeError):
            analyze_callable(cfunc_positional)

        cc = analyze_callable(p(cfunc_positional, 3))
        assert (cc.in_type, cc.out_type) == (float, str)
        assert cc(1, cxt) == "14"

    def test_cxt_var_positional(self):
        cxt = ValidationContext().put(x=10)
        with pytest.raises(TypeError):
            analyze_callable(cfunc_var_positional)

        cc = analyze_callable(p(cfunc_var_positional, 3, 4, 5, 6))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, cxt) == "29"

        cc = analyze_callable(p(cfunc_var_positional, 3))
        assert (cc.in_type, cc.out_type) == (float, str)
        assert cc(1, cxt) == "14"

        cc = analyze_callable(p(cfunc_var_positional, b=3))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, cxt) == "14"

    def test_cxt_var_keyword(self):
        cxt = ValidationContext().put(x=10)
        with pytest.raises(TypeError):
            analyze_callable(cfunc_var_keyword)

        with pytest.raises(TypeError):
            analyze_callable(p(cfunc_var_keyword, a=3, b=4, c=5, d=6))

        cc = analyze_callable(p(cfunc_var_keyword, 3))
        assert (cc.in_type, cc.out_type) == (float, str)
        assert cc(1, cxt) == "14"

        cc = analyze_callable(p(cfunc_var_keyword, b=3))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, cxt) == "14"

        cc = analyze_callable(p(cfunc_var_keyword, b=3, c=5, d=6))
        assert (cc.in_type, cc.out_type) == (int, str)
        assert cc(1, cxt) == "25"