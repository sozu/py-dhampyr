import pytest
from dhampyr.failures import *


class TestCompositeValidationFailure:
    def test_add(self):
        f = CompositeValidationFailure()
        f.add('a', ValidationFailure("a"))
        f.add('b', ValidationFailure("b"))

        assert f.failures['a'].name == "a"
        assert f.failures['b'].name == "b"

    def test_get_by_key(self):
        f = CompositeValidationFailure()

        a1 = CompositeValidationFailure()
        a1.failures['A'] = ValidationFailure("a0A")
        a2 = CompositeValidationFailure()
        a2.failures['A'] = ValidationFailure("a1A")

        a = CompositeValidationFailure()
        a.failures = {0: a1, 1: a2}

        b = CompositeValidationFailure()
        b.failures = {'c': ValidationFailure("bc"), 'd': ValidationFailure("bd")}

        f.failures['a'] = a
        f.failures['b'] = b

        assert f['a'][0]['A'].name == "a0A" # type: ignore
        assert f['a'][1]['A'].name == "a1A" # type: ignore
        assert f['b']['c'].name == "bc" # type: ignore
        assert f['b']['d'].name == "bd" # type: ignore
        assert f['c'] is None
        with pytest.raises(TypeError):
            f['c'][0] # type: ignore

        assert f['a[0].A'].name == "a0A" # type: ignore
        assert f['a[1].A'].name == "a1A" # type: ignore
        assert f['b.c'].name == "bc" # type: ignore
        assert f['b.d'].name == "bd" # type: ignore
        assert f['c'] is None
        assert f['c[0]'] is None

    def test_contains(self):
        f = CompositeValidationFailure()

        a1 = CompositeValidationFailure()
        a1.failures['A'] = ValidationFailure("a0A")
        a2 = CompositeValidationFailure()
        a2.failures['A'] = ValidationFailure("a1A")

        a = CompositeValidationFailure()
        a.failures = {0: a1, 1: a2}

        b = CompositeValidationFailure()
        b.failures = {'c': ValidationFailure("bc"), 'd': ValidationFailure("bd")}

        f.failures['a'] = a
        f.failures['b'] = b

        assert ('a' in f) is True
        assert ('b' in f) is True
        assert ('c' in f) is False
        assert ('a[0].A' in f) is True
        assert ('a[1].A' in f) is True
        assert ('a[2].A' in f) is False
        assert ('b.c' in f) is True
        assert ('b.d' in f) is True
        assert ('b.e' in f) is False
        assert ('c[0]' in f) is False