import pytest
from dhampyr.failures import ValidationPath


class TestParse:
    def test_parse_1(self):
        p = ValidationPath.of("a")
        assert p.path == ["a"]

    def test_parse_2(self):
        p = ValidationPath.of("a.b")
        assert p.path == ["a", "b"]

    def test_parse_3(self):
        p = ValidationPath.of("a[1]")
        assert p.path == ["a", 1]

    def test_parse_4(self):
        p = ValidationPath.of("[1]")
        assert p.path == [1]

    def test_parse(self):
        p = ValidationPath.of("a.b[1].c[1][2][3].d")
        assert p.path == ["a", "b", 1, "c", 1, 2, 3, "d"]


class TestRepr:
    def test_repr(self):
        p = ValidationPath(["a", "b", 1, "c", 1, 2, 3, "d"])
        assert str(p) == "a.b[1].c[1][2][3].d"