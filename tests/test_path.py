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


class TestAdd:
    def test_none(self):
        p = ValidationPath.of("a[0].b")
        pp = p + None
        assert p.path == ["a", 0, "b"]
        assert pp.path == ["a", 0, "b"]

    def test_empty(self):
        p = ValidationPath.of("a[0].b")
        pp = p + ""
        assert p.path == ["a", 0, "b"]
        assert pp.path == ["a", 0, "b"]

    def test_str(self):
        p = ValidationPath.of("a[0].b")
        pp = p + "c[1].d"
        assert p.path == ["a", 0, "b"]
        assert pp.path == ["a", 0, "b", "c", 1, "d"]

    def test_int(self):
        p = ValidationPath.of("a[0].b")
        pp = p + 1
        assert p.path == ["a", 0, "b"]
        assert pp.path == ["a", 0, "b", 1]

    def test_path(self):
        p = ValidationPath.of("a[0].b")
        pp = p + ValidationPath.of("c[1].d")
        assert p.path == ["a", 0, "b"]
        assert pp.path == ["a", 0, "b", "c", 1, "d"]


class TestIadd:
    def test_none(self):
        p = ValidationPath.of("a[0].b")
        p += None
        assert p.path == ["a", 0, "b"]

    def test_empty(self):
        p = ValidationPath.of("a[0].b")
        p += ""
        assert p.path == ["a", 0, "b"]

    def test_str(self):
        p = ValidationPath.of("a[0].b")
        p += "c[1].d"
        assert p.path == ["a", 0, "b", "c", 1, "d"]

    def test_int(self):
        p = ValidationPath.of("a[0].b")
        p += 1
        assert p.path == ["a", 0, "b", 1]

    def test_path(self):
        p = ValidationPath.of("a[0].b")
        p += ValidationPath.of("c[1].d")
        assert p.path == ["a", 0, "b", "c", 1, "d"]


class TestUnder:
    def test_under(self):
        p1 = ValidationPath.of("a[0].b.c[1]")

        assert p1.under(ValidationPath.of("a"))
        assert p1.under(ValidationPath.of("a[0]"))
        assert p1.under(ValidationPath.of("a[0].b"))
        assert p1.under(ValidationPath.of("a[0].b.c"))
        assert p1.under(ValidationPath.of("a[0].b.c[1]"))
        assert not p1.under(ValidationPath.of("a[0].b.c[2]"))
        assert not p1.under(ValidationPath.of("a[0].c"))
        assert not p1.under(ValidationPath.of("a[1]"))