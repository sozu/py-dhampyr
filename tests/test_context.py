import pytest
from dhampyr.context import ValidationContext


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