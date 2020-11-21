import pytest
from dhampyr.validator import ValidationResult
from dhampyr.failures import *


class TestOrElse:
    def test_no_failures(self):
        f = CompositeValidationFailure()

        r = ValidationResult("abc", f, None)

        def handler(e):
            pytest.fail("Error handler is invoked")
        assert r.or_else(handler) == "abc"

    def test_with_failures(self):
        f = CompositeValidationFailure()
        f.add("a", ValidationFailure("a"))

        r = ValidationResult("abc", f, None)

        ok = False
        def handler(e):
            nonlocal ok
            ok = True
            return "ng"
        assert r.or_else(handler) == "ng"
        assert ok is True

    def test_single_allows(self):
        f = CompositeValidationFailure()
        a = CompositeValidationFailure()
        ab = CompositeValidationFailure()
        ab.add("c", ValidationFailure("abc"))
        ab.add("d", ValidationFailure("abd"))
        a.add("b", ab)
        f.add("a", a)

        assert [str(p) for p, _ in f] == ["a.b.c", "a.b.d"]

        r = ValidationResult("abc", f, None)

        def handler(e):
            return "ng"
        assert r.or_else(handler) == "ng"
        assert r.or_else(handler, ["a"]) == "abc"
        assert r.or_else(handler, ["a.b"]) == "abc"
        assert r.or_else(handler, ["a.b.c"]) == "ng"
