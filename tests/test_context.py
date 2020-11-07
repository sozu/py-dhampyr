import pytest
from dhampyr.context import ValidationContext
from dhampyr.config import dhampyr
from dhampyr.api import v


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


class TestAttribute:
    def test_root(self):
        c = ValidationContext().put(
            a1 = 1,
            a2 = "a",
        )
        assert c.a1 == 1
        assert c.a2 == "a"

    def test_inherit(self):
        c = ValidationContext().put(
            a1 = 1,
            a2 = "a",
        )[0].put(
            a3 = 3,
        )
        assert c.a1 == 1
        assert c.a2 == "a"
        assert c.a3 == 3

    def test_overwrite(self):
        c = ValidationContext().put(
            a1 = 1,
            a2 = "a",
        )[0].put(
            a1 = 2,
            a3 = 3,
        )
        assert c.a1 == 2
        assert c.a2 == "a"
        assert c.a3 == 3


class TestConfig:
    def test_root(self):
        c = ValidationContext()
        assert c.config.name == "default"

    def test_each(self):
        c = ValidationContext()
        c0 = c[0]
        c1 = c[1]
        c2 = c[2]
        c0.configure(name = "c0")
        c1.configure(name = "c1")
        c00 = c[0][0]
        c00.configure(name = "c00")
        c10 = c[1][0]
        assert c.config.name == "default"
        assert c0.config.name == "c0"
        assert c1.config.name == "c1"
        assert c2.config.name == "default"
        assert c00.config.name == "c00"
        assert c10.config.name == "c1"

    def test_typed(self):
        @dhampyr(name = "D")
        class D:
            v2: v(int)
        @dhampyr(name = "C")
        class C:
            v1: v({D})

        c = ValidationContext()
        assert c.config.name == "default"
        with c.on(C):
            assert c.config.name == "C"
            with c.on(D):
                assert c.config.name == "D"
            assert c.config.name == "C"
        assert c.config.name == "default"

    def test_each_typed(self):
        @dhampyr(name = "D")
        class D:
            v2: v(int)
        @dhampyr(name = "C")
        class C:
            v1: v({D})

        c = ValidationContext()
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


class TestSharedContext:
    def test_root(self):
        c = ValidationContext().configure(share_context = True)
        assert c.config.name == "default"

    def test_each(self):
        c = ValidationContext().configure(share_context = True)
        c0 = c[0]
        c1 = c[1]
        c2 = c[2]
        c0.configure(name = "c0")
        c1.configure(name = "c1")
        c00 = c[0][0]
        c00.configure(name = "c00")
        c10 = c[1][0]
        assert c.config.name == "c00"
        assert c0.config.name == "c00"
        assert c1.config.name == "c00"
        assert c2.config.name == "c00"
        assert c00.config.name == "c00"
        assert c10.config.name == "c00"

    def test_typed(self):
        @dhampyr(name = "D")
        class D:
            v2: v(int)
        @dhampyr(name = "C")
        class C:
            v1: v({D})

        c = ValidationContext().configure(share_context = True)
        assert c.config.name == "default"
        with c.on(C):
            assert c.config.name == "C"
            with c.on(D):
                assert c.config.name == "D"
            assert c.config.name == "C"
        assert c.config.name == "default"

    def test_each_typed(self):
        @dhampyr(name = "D")
        class D:
            v2: v(int)
        @dhampyr(name = "C")
        class C:
            v1: v({D})

        c = ValidationContext().configure(share_context = True)
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