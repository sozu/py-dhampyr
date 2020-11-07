import pytest
from dhampyr.config import dhampyr, default_config
from dhampyr.api import v, validate_dict


class TestDhampyr:
    def test_default(self):
        try:
            with dhampyr() as cfg:
                cfg.skip_null = False
                cfg.join_on_fail = False
                cfg.isinstance_builtin = True

            config = default_config()

            assert config.skip_null is False
            assert config.join_on_fail is False
            assert config.isinstance_builtin is True

            class V:
                v1: v(lambda x: 0 if x is None else 1)
                v2: v([int])

            r = validate_dict(V, dict(v1 = None, v2 = ["a", 1, "2"]))
            assert not r
            assert r.failures['v1'] is None
            assert r.get().v1 == 0
            assert r.failures['v2'] is not None
            assert r.get().v2 == [None, 1, None]

        finally:
            config = default_config()
            config.skip_null = True
            config.skip_empty = True
            config.allow_null = False
            config.allow_empty = False
            config.isinstance_builtin = False
            config.isinstance_any = False
            config.join_on_fail = True

    def test_decorator(self):
        @dhampyr(skip_null=False, join_on_fail=False, isinstance_builtin=True)
        class V:
            v1: v(lambda x: 0 if x is None else 1)
            v2: v([int])

        r = validate_dict(V, dict(v1 = None, v2 = ["a", 1, "2"]))
        assert not r
        assert r.failures['v1'] is None
        assert r.get().v1 == 0
        assert r.failures['v2'] is not None
        assert r.get().v2 == [None, 1, None]

    def test_meta_decorator(self):
        @dhampyr(skip_null=False, join_on_fail=False, isinstance_builtin=True)
        def meta(t):
            return t

        @meta
        class V:
            v1: v(lambda x: 0 if x is None else 1)
            v2: v([int])

        r = validate_dict(V, dict(v1 = None, v2 = ["a", 1, "2"]))
        assert not r
        assert r.failures['v1'] is None
        assert r.get().v1 == 0
        assert r.failures['v2'] is not None
        assert r.get().v2 == [None, 1, None]