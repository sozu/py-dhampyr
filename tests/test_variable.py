import pytest
import math
from dhampyr.variable import x


class TestSingle:
    def test_len(self):
        assert x.len._id("abc") == 3

    def test_in(self):
        assert x.in_(1,2,3)._id(1) is True
        assert x.in_(2,3)._id(1) is False

    def test_inv(self):
        assert x.inv()._id(False) is True
        assert x.inv()._id(True) is False

    def test_not(self):
        assert (x.not_)(False) is True
        assert (x.not_)(True) is False

    def test_getattr(self):
        class C:
            def __init__(self, p, q):
                self.p = p
                self.q = q

        c = C(1, 2)
        assert x.p._id(c) == 1
        assert x.q._id(c) == 2

    def test_getitem(self):
        d = dict(p=1, q=2)
        assert x['p']._id(d) == 1
        assert x['q']._id(d) == 2

    def test_eq(self):
        assert (x == 1)._id(1) is True
        assert (x == 1)._id(2) is False

    def test_neq(self):
        assert (x != 1)._id(2) is True
        assert (x != 1)._id(1) is False

    def test_lt(self):
        assert (x < 1)._id(0) is True
        assert (x < 1)._id(1) is False

    def test_le(self):
        assert (x <= 1)._id(0) is True
        assert (x <= 1)._id(1) is True
        assert (x <= 1)._id(2) is False

    def test_gt(self):
        assert (x > 1)._id(2) is True
        assert (x > 1)._id(1) is False

    def test_ge(self):
        assert (x >= 1)._id(2) is True
        assert (x >= 1)._id(1) is True
        assert (x >= 1)._id(0) is False

    def test_has(self):
        assert (x.has(1))._id([1,2,3]) is True
        assert (x.has(1))._id([2,3]) is False

    def test_add(self):
        assert (x + 1)._id(3) == 4

    def test_sub(self):
        assert (x - 1)._id(3) == 2

    def test_mul(self):
        assert (x * 2)._id(3) == 6

    def test_truediv(self):
        assert (x / 2)._id(3) == 1.5

    def test_floordiv(self):
        assert (x // 2)._id(3) == 1

    def test_mod(self):
        assert (x % 2)._id(3) == 1

    def test_divmod(self):
        assert (divmod(x, 2))._id(3) == (1, 1)

    def test_pow(self):
        assert (pow(x, 2))._id(3) == 9

    def test_lshift(self):
        assert (x << 2)._id(3) == 12

    def test_rshift(self):
        assert (x >> 2)._id(13) == 3

    def test_and(self):
        assert (x & 2)._id(7) == 2

    def test_xor(self):
        assert (x ^ 3)._id(5) == 6

    def test_or(self):
        assert (x | 3)._id(5) == 7

    def test_neg(self):
        assert (-x)._id(1) == -1

    def test_pos(self):
        assert (+x)._id(1) == 1

    def test_abs(self):
        assert (abs(x))._id(-1) == 1

    def test_invert(self):
        assert (~x)._id(0) == -1

    def test_round(self):
        assert (round(x))._id(1.5) == 2

    def test_trunc(self):
        assert (math.trunc(x))._id(1.5) == 1

    def test_floor(self):
        assert (math.floor(x))._id(1.5) == 1

    def test_ceil(self):
        assert (math.ceil(x))._id(1.5) == 2


class TestBoolean:
    def test_and(self):
        x1 = (x + 1) < 4
        x2 = x > 1
        xx = x1.and_(x2)
        assert xx._names == ["x", "add", "lt", "and", "gt"]
        assert xx._id(2) is True
        assert xx._id(1) is False

    def test_or(self):
        x1 = (x + 1) > 4
        x2 = x < 1
        xx = x1.or_(x2)
        assert xx._names == ["x", "add", "gt", "or", "lt"]
        assert xx._id(0) is True
        assert xx._id(3) is False


class TestCombination:
    def test_attr_combination(self):
        class C:
            def __init__(self, a):
                self.a = a

        f = (x.a.len * 3 > 5)._verifier(False).verify(C("abc"))
        assert f is None

        f = (x.a.len * 3 > 5)._verifier(False).verify(C("a"))
        assert f is not None
        assert (f.name, f.kwargs) == ("x.@a.len.mul.gt", {"gt.value": 5, "mul.value": 3})

    def test_not_attr_combination(self):
        class C:
            def __init__(self, a):
                self.a = a

        f = (x.not_.a.len * 3 > 5)._verifier(False).verify(C("a"))
        assert f is None

        f = (x.not_.a.len * 3 > 5)._verifier(False).verify(C("abc"))
        assert f is not None
        assert (f.name, f.kwargs) == ("x.not.@a.len.mul.gt", {"gt.value": 5, "mul.value": 3})

    def test_index_combination(self):
        f = (x['a'].len * 3 > 5)._verifier(False).verify(dict(a="abc"))
        assert f is None

        f = (x['a'].len * 3 > 5)._verifier(False).verify(dict(a="a"))
        assert f is not None
        assert (f.name, f.kwargs) == ("x.[a].len.mul.gt", {"gt.value": 5, "mul.value": 3})

    def test_not_index_combination(self):
        f = (x.not_['a'].len * 3 > 5)._verifier(False).verify(dict(a="a"))
        assert f is None

        f = (x.not_['a'].len * 3 > 5)._verifier(False).verify(dict(a="abc"))
        assert f is not None
        assert (f.name, f.kwargs) == ("x.not.[a].len.mul.gt", {"gt.value": 5, "mul.value": 3})