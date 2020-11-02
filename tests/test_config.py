import pytest
from dhampyr.config import dhampyr, default_config
from dhampyr.api import v


class TestDhampyr:
    def test_default(self):
        try:
            with dhampyr() as cfg:
                cfg.skip_null = False
                cfg.join_on_fail = False
            config = default_config()

            assert config.skip_null is False
            assert config.join_on_fail is False
        finally:
            config = default_config()
            config.skip_null = True
            config.skip_empty = True
            config.allow_null = False
            config.allow_empty = False
            config.empty_specs = []
            config.isinstance_builtin = False
            config.isinstance_any = False
            config.join_on_fail = True

    def test_decorator(self):
        @dhampyr(skip_null=False, join_on_fail=False)
        class V:
            v1: v(int)
            v2: v(str)

        v1v = V.__annotations__['v1']
        assert v1v.config.skip_null == False
        assert v1v.config.join_on_fail == False

