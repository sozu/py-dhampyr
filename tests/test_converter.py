import pytest
from dhampyr.failures import ValidationFailure, CompositeValidationFailure
from dhampyr.context import ValidationContext
from dhampyr.converter import Converter, ConversionFailure


class TestConvert:
    def test_convert(self):
        c = Converter("test", int, False)
        v, f = c.convert("1")
        assert v == 1
        assert f is None

    def test_exception(self):
        c = Converter("test", int, False)
        v, f = c.convert("a")
        assert v is None
        assert isinstance(f, ConversionFailure)
        assert f.converter is c
        assert f.name == "test"

    def test_conversion_failure(self):
        def fail(v):
            ConversionFailure.abort("conversion failed")
        c = Converter("test", fail, False)
        v, f = c.convert("1")
        assert v is None
        assert isinstance(f, ConversionFailure)
        assert f.converter is c
        assert f.name == "test"

    def test_validation_failure(self):
        def fail(v):
            raise ValidationFailure()
        c = Converter("test", fail, False)
        v, f = c.convert("1")
        assert v is None
        assert isinstance(f, ValidationFailure)
        assert not isinstance(f, ConversionFailure)
        assert f.name == "invalid"

    def test_context(self):
        def fail(v, cxt:ValidationContext):
            raise ValidationFailure(name=cxt.name)
        c = Converter("test", fail, False)
        cxt = ValidationContext().put(
            name = "context",
        )
        v, f = c.convert("1", cxt)
        assert v is None
        assert f.name == "context"

    def test_isinstance_builtin(self):
        c = Converter("test", int, False)
        cxt = ValidationContext().configure(isinstance_builtin=True)
        v, f = c.convert("1", cxt)
        assert v is None
        assert isinstance(f, ConversionFailure)
        assert f.converter is c
        assert f.name == "test"
        v, f = c.convert(1, cxt)
        assert v == 1
        assert f is None

    def test_isinstance_any(self):
        class T:
            def __init__(self, t):
                self.t = t
        c = Converter("test", T, False)
        cxt = ValidationContext().configure(isinstance_any=True)
        v, f = c.convert("1", cxt)
        assert v is None
        assert isinstance(f, ConversionFailure)
        assert f.converter is c
        assert f.name == "test"
        v, f = c.convert(T("1"), cxt)
        assert v.t == "1"
        assert f is None


class TestIterativeConvert:
    def test_convert(self):
        c = Converter("test", int, True)
        v, f = c.convert(["1", "2", "3"])
        assert v == [1, 2, 3]
        assert f is None

    def test_exception(self):
        c = Converter("test", int, True)
        v, f = c.convert(["1", "a", "3"])
        assert v is None
        assert isinstance(f, CompositeValidationFailure)
        assert isinstance(f[1], ConversionFailure)

    def test_exception_unjointed(self):
        c = Converter("test", int, True)
        cxt = ValidationContext()
        cxt.config.join_on_fail = False
        v, f = c.convert(["1", "a", "3"], cxt)
        assert v == [1, None, 3]
        assert isinstance(f, CompositeValidationFailure)
        assert isinstance(f[1], ConversionFailure)

    def test_context(self):
        def fail(v, cxt:ValidationContext):
            raise ValidationFailure(name=str(cxt.path))
        c = Converter("test", fail, True)
        v, f = c.convert(["1", "2", "3"], ValidationContext())
        assert v is None
        assert [f[i].name for i in range(3)] == ["[0]", "[1]", "[2]"]

    def test_isinstance_builtin(self):
        c = Converter("test", int, True)
        cxt = ValidationContext().configure(isinstance_builtin=True, join_on_fail=False)
        v, f = c.convert(["1", 2, "3"], cxt)
        assert v == [None, 2, None]
        assert isinstance(f, CompositeValidationFailure)
        assert isinstance(f[0], ConversionFailure)
        assert f[1] is None
        assert isinstance(f[2], ConversionFailure)

    def test_isinstance_any(self):
        class T:
            def __init__(self, t):
                self.t = t
        c = Converter("test", T, True)
        cxt = ValidationContext().configure(isinstance_any=True, join_on_fail=False)
        v, f = c.convert(["1", T(2), "3"], cxt)
        assert v[0] is None
        assert v[1].t == 2
        assert v[2] is None
        assert isinstance(f, CompositeValidationFailure)
        assert isinstance(f[0], ConversionFailure)
        assert f[1] is None
        assert isinstance(f[2], ConversionFailure)
