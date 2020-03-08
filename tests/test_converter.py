import  pytest
from dhampyr.failures import ValidationFailure, CompositeValidationFailure
from dhampyr.context import ValidationContext, IterativeContext
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
            raise ValidationFailure(name="context")
        c = Converter("test", fail, False)
        v, f = c.convert("1")
        assert v is None
        assert f.name == "context"


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
        cxt = IterativeContext()
        cxt.joint_failure = False
        v, f = c.convert(["1", "a", "3"], cxt)
        assert v == [1, None, 3]
        assert isinstance(f, CompositeValidationFailure)
        assert isinstance(f[1], ConversionFailure)

    def test_context(self):
        def fail(v, cxt:ValidationContext):
            raise ValidationFailure(name="context")
        c = Converter("test", fail, True)
        v, f = c.convert(["1", "2", "3"])
        assert v is None
        assert [f[i].name for i in range(3)] == ["context", "context", "context"]