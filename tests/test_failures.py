import pytest
from dhampyr.failures import *


class TestValidationFailure:
    def test_failure(self):
        f = ValidationFailure("test", "test error", [1, 2, 3], dict(a=1, b=2))
        assert len(f) == 1
        p, v = next(iter(f))
        assert str(p) == ""
        assert v == f
        assert not ("" in f)
        assert f[""] is None
        assert f.name == "test"
        assert f.message == "test error"
        assert f.args == [1, 2, 3]
        assert f.kwargs == dict(a=1, b=2)

    def test_abort(self):
        try:
            ValidationFailure.abort("test", "test error", [1, 2, 3], dict(a=1, b=2))
        except PartialFailure as e:
            f = e.create()
            assert len(f) == 1
            p, v = next(iter(f))
            assert str(p) == ""
            assert v == f
            assert not ("" in f)
            assert f[""] is None
            assert f.name == "test"
            assert f.message == "test error"
            assert f.args == [1, 2, 3]
            assert f.kwargs == dict(a=1, b=2)
        else:
            pytest.fail("Exception was not raised")


class TestCompositeValidationFailure:
    def test_add(self):
        f = CompositeValidationFailure()
        f.add('a', ValidationFailure("a"), None)
        f.add('b', ValidationFailure("b"), None)

        assert f.failures['a'].name == "a"
        assert f.failures['b'].name == "b"

    def test_get_by_key(self):
        f = CompositeValidationFailure()

        a0 = CompositeValidationFailure()
        a0.failures = {'A': ValidationFailure("a0A")}
        a1 = CompositeValidationFailure()
        a1.failures = {'A': ValidationFailure("a1A")}

        a = CompositeValidationFailure()
        a.failures = {0: a0, 1: a1}

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


class TestActualKeys:
    def test_iter(self):
        f = CompositeValidationFailure()

        a1 = CompositeValidationFailure()
        a1.add('A', ValidationFailure("a0A"), None)
        a2 = CompositeValidationFailure()
        a2.add('A', ValidationFailure("a1A"), 'aaa')

        a = CompositeValidationFailure()
        a.add(0, a1)
        a.add(1, a2)

        b = CompositeValidationFailure()
        b.add('c', ValidationFailure("bc"), None)
        b.add('d', ValidationFailure("bd"), 'DDD')

        f.add('a', a)
        f.add('b', b, 'BBB')

        assert [(str(p), v.name) for p, v in f.__iter__(as_input=True)] \
            == [('a[0].A', "a0A"), ('a[1].aaa', "a1A"), ('BBB.c', "bc"), ('BBB.DDD', "bd")]