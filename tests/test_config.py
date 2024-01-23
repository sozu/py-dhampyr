import pytest
from dhampyr.config import Configurable, ValidationConfiguration, ConfigurationStack, default_config, typed_config
from dhampyr.api import validatable


class TestDerive:
    def test_derive(self):
        cfg = ValidationConfiguration(name="test", skip_null=False)
        drv = cfg.derive()

        assert (drv.name, drv.skip_null) == ("test", False)

        drv.name = "derived"

        assert (cfg.name, cfg.skip_null) == ("test", False)
        assert (drv.name, drv.skip_null) == ("derived", False)

    def test_derive_overwrite(self):
        cfg = ValidationConfiguration(name="test", skip_null=False)
        drv = cfg.derive(name="derived")

        assert (cfg.name, cfg.skip_null) == ("test", False)
        assert (drv.name, drv.skip_null) == ("derived", False)


class TestDefault:
    def test_default(self):
        with default_config() as cfg:
            cfg.name = "modified"
            cfg.skip_null = False

            assert default_config().name is "modified"
            assert default_config().skip_null is False

        assert default_config().name is "default"
        assert default_config().skip_null is True

    def test_type_decorator(self):
        try:
            typed_config().clear()

            @validatable(name="V", skip_null=False)
            class V:
                pass

            cfg = typed_config().get(V)
            assert cfg is not None
            assert cfg.get('name') == 'V'
            assert cfg.get('skip_null') is False
        finally:
            typed_config().clear()

    def test_meta_decorator(self):
        try:
            typed_config().clear()

            @validatable(name="meta", skip_null=False)
            def meta(t):
                return t

            @meta
            class V:
                pass

            cfg = typed_config().get(V)
            assert cfg is not None
            assert cfg.get('name') == 'meta'
            assert cfg.get('skip_null') is False
        finally:
            typed_config().clear()


class TestStack:
    def test_attr(self):
        stack = ConfigurationStack(default_config())
        assert stack.name == "default"

        stack.push(Configurable(name="one"))
        assert stack.name == "one"

        stack.push(Configurable(name="two"))
        assert stack.name == "two"

        stack.pop()
        assert stack.name == "one"

        stack.pop()
        assert stack.name == "default"

        stack.pop()
        assert stack.name == "default"

    def test_on(self):
        try:
            typed_config().clear()

            stack = ConfigurationStack(default_config())
            assert stack.name == "default"

            @validatable(name="V", skip_null=False)
            class V:
                pass
            @validatable(name="W", skip_null=False)
            class W:
                pass
            class X:
                pass

            cfg = stack.on(V)
            assert cfg.name == "V"
            cfg = stack.on(W)
            assert cfg.name == "W"
            cfg = stack.on(X)
            assert cfg.name == "W"

            stack.pop()
            assert stack.name == "V"
            stack.pop()
            assert stack.name == "default"
        finally:
            typed_config().clear()