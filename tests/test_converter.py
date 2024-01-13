import pytest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Optional, Union
from uuid import UUID, uuid4
from dhampyr.failures import ValidationFailure, CompositeValidationFailure
from dhampyr.context import ValidationContext
from dhampyr.converter import *


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
        assert f is not None
        assert f.name == "context"

    def test_strict_builtin(self):
        cxt = ValidationContext().configure(strict_builtin=True)
        #c = get_builtin_factory(int, "test", False, False).create(cxt)
        factory = get_builtin_factory(int, "test")
        assert factory
        c = factory.create(cxt)
        v, f = c.convert("1", cxt)
        assert v is None
        assert isinstance(f, ConversionFailure)
        assert f.converter is c
        assert f.name == "test"
        v, f = c.convert(1, cxt)
        assert v == 1
        assert f is None

    def test_strict(self):
        class T:
            def __init__(self, t):
                self.t = t
        cxt = ValidationContext().configure(strict=True)
        c = get_user_factory(T, "test", lambda v, cxt: T(v)).create(cxt)
        v, f = c.convert("1", cxt)
        assert v is None
        assert isinstance(f, ConversionFailure)
        assert f.converter is c
        assert f.name == "test"
        v, f = c.convert(T("1"), cxt)
        assert v is not None
        assert v.t == "1"
        assert f is None


class TestIterativeConvert:
    def test_convert(self):
        c = Converter("test", int, True)
        v, f = c.convert(["1", "2", "3"])
        assert v == [1, 2, 3]
        assert f is None

    def test_not_iterable(self):
        c = Converter("test", int, True)
        with pytest.raises(TypeError):
            c.convert(1)

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
        assert f is not None
        assert [f[i].name for i in range(3)] == ["[0]", "[1]", "[2]"] # type: ignore

    def test_strict_builtin(self):
        cxt = ValidationContext().configure(strict_builtin=True, join_on_fail=False)
        factory = get_builtin_factory(int, "test")
        assert factory
        c = ListFactory(factory).create(cxt)
        v, f = c.convert(["1", 2, "3"], cxt)
        assert v == [None, 2, None]
        assert isinstance(f, CompositeValidationFailure)
        assert isinstance(f[0], ConversionFailure)
        assert f[1] is None
        assert isinstance(f[2], ConversionFailure)

    def test_strict(self):
        class T:
            def __init__(self, t):
                self.t = t
        cxt = ValidationContext().configure(strict=True, join_on_fail=False)
        c = ListFactory(get_user_factory(T, "test", lambda v, cxt: T(v))).create(cxt)
        v, f = c.convert(["1", T(2), "3"], cxt)
        assert v is not None
        assert v[0] is None
        assert v[1].t == 2
        assert v[2] is None
        assert isinstance(f, CompositeValidationFailure)
        assert isinstance(f[0], ConversionFailure)
        assert f[1] is None
        assert isinstance(f[2], ConversionFailure)


class TestBuiltin:
    def converter(self, factory: Optional[ConverterFactory], **kwargs) -> tuple[Converter, ValidationContext]:
        assert factory
        cxt = ValidationContext().configure(**kwargs)
        c = factory.create(cxt)
        return c, cxt

    def test_any(self):
        factory = get_builtin_factory(Any, "test")
        val = object()

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Any, Any)
        v, f = c.convert(val, cxt)
        assert v is val
        assert f is None
        v, f = c.convert(None, cxt)
        assert v is None
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (Any, Any)
        v, f = c.convert(val, cxt)
        assert v is val
        assert f is None
        v, f = c.convert(None, cxt)
        assert v is None
        assert f is None

    def test_bool(self):
        factory = get_builtin_factory(bool, "test")

        # int -> bool
        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[bool, str, int], bool)
        v, f = c.convert(0, cxt)
        assert v is False
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (bool, bool)
        v, f = c.convert(0, cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(False, cxt)
        assert v is False
        assert f is None

    def test_int(self):
        factory = get_builtin_factory(int, "test")

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, int, float, Decimal], int)
        v, f = c.convert(3, cxt)
        assert v == 3
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert("3", cxt)
        assert v == 3
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert("abc", cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (int, int)
        v, f = c.convert("3", cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(3, cxt)
        assert v == 3
        assert f is None

    def test_float(self):
        factory = get_builtin_factory(float, "test")

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, int, float, Decimal], float)
        v, f = c.convert(1.5, cxt)
        assert v == 1.5
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert("1.5", cxt)
        assert v == 1.5
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (Union[float, int], float)
        v, f = c.convert("1.5", cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(1.5, cxt)
        assert v == 1.5
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(3, cxt)
        assert v == 3
        assert f is None

    def test_decimal(self):
        factory = get_builtin_factory(Decimal, "test")

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, int, float, Decimal], Decimal)
        v, f = c.convert("1.5", cxt)
        assert v == 1.5
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(1.5, cxt)
        assert v == 1.5
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(3, cxt)
        assert v == 3
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (Union[Decimal, str, int, float], Decimal)
        v, f = c.convert("1.5", cxt)
        assert v == 1.5
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(1.5, cxt)
        assert v == 1.5
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(3, cxt)
        assert v == 3
        assert f is None

    def test_bytes(self):
        factory = get_builtin_factory(bytes, "test")

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, bytes, bytearray], bytes)
        v, f = c.convert(b"abc", cxt)
        assert v == b"abc"
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert("abc", cxt)
        assert v == b"abc"
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(3, cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (Union[bytes, str], bytes)
        v, f = c.convert(b"abc", cxt)
        assert v == b"abc"
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert("abc", cxt)
        assert v == b"abc"
        assert f is None

    def test_str(self):
        factory = get_builtin_factory(str, "test")

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, bytes, bytearray], str)
        v, f = c.convert("abc", cxt)
        assert v == "abc"
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(b"abc", cxt)
        assert v == "abc"
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(3, cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (str, str)
        v, f = c.convert("abc", cxt)
        assert v == "abc"
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(b"abc", cxt)
        assert v is None
        assert f is not None

    def test_date(self):
        factory = get_builtin_factory(date, "test")

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, date], date)
        v, f = c.convert("2020-01-02", cxt)
        assert v == date(2020, 1, 2)
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(date(2020, 1, 2), cxt)
        assert v == date(2020, 1, 2)
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(123456789, cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (date, date)
        v, f = c.convert("2020-01-02", cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(date(2020, 1, 2), cxt)
        assert v == date(2020, 1, 2)
        assert f is None

    def test_datetime(self):
        factory = get_builtin_factory(datetime, "test")

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, date, datetime], datetime)
        v, f = c.convert("2020-01-02T01:23:45", cxt)
        assert v == datetime(2020, 1, 2, 1, 23, 45)
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(datetime(2020, 1, 2, 1, 23, 45), cxt)
        assert v == datetime(2020, 1, 2, 1, 23, 45)
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(123456789, cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (datetime, datetime)
        v, f = c.convert("2020-01-02T01:23:45", cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(datetime(2020, 1, 2, 1, 23, 45), cxt)
        assert v == datetime(2020, 1, 2, 1, 23, 45)
        assert f is None

    def test_time(self):
        factory = get_builtin_factory(time, "test")

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, time], time)
        v, f = c.convert("01:23:45", cxt)
        assert v == time(1, 23, 45)
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(time(1, 23, 45), cxt)
        assert v == time(1, 23, 45)
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(123456789, cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (time, time)
        v, f = c.convert("01:23:45", cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(time(1, 23, 45), cxt)
        assert v == time(1, 23, 45)
        assert f is None

    def test_timedelta(self):
        factory = get_builtin_factory(timedelta, "test")

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, timedelta], timedelta)
        v, f = c.convert("P10DT5H4M3S", cxt)
        assert v == timedelta(days=10, hours=5, minutes=4, seconds=3)
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert("PT5H4M3S", cxt)
        assert v == timedelta(hours=5, minutes=4, seconds=3)
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert("P6W", cxt)
        assert v == timedelta(weeks=6)
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(timedelta(days=10, hours=5, minutes=4, seconds=3), cxt)
        assert v == timedelta(days=10, hours=5, minutes=4, seconds=3)
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(123456789, cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (timedelta, timedelta)
        v, f = c.convert("P10DT5H4M3S", cxt)
        assert v is None
        assert f is not None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(timedelta(days=10, hours=5, minutes=4, seconds=3), cxt)
        assert v == timedelta(days=10, hours=5, minutes=4, seconds=3)
        assert f is None

    def test_uuid(self):
        factory = get_builtin_factory(UUID, "test")

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[UUID, str, bytes], UUID)
        v, f = c.convert("12345678-1234-5678-1234-567812345678", cxt)
        assert v == UUID('12345678123456781234567812345678')
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert(b'\x12\x34\x56\x78'*4, cxt)
        assert v == UUID('12345678123456781234567812345678')
        assert f is None

        c, cxt = self.converter(factory)
        v, f = c.convert("abcdefhg-abcd-efgh-abcd-efghabcdefgh", cxt)
        assert v is None
        assert f is not None

        val = uuid4()
        c, cxt = self.converter(factory)
        v, f = c.convert(val, cxt)
        assert v == val
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (Union[UUID, str, bytes], UUID)
        v, f = c.convert("12345678-1234-5678-1234-567812345678", cxt)
        assert v == UUID('12345678123456781234567812345678')
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(b'\x12\x34\x56\x78'*4, cxt)
        assert v == UUID('12345678123456781234567812345678')
        assert f is None

        c, cxt = self.converter(factory, strict_builtin=True)
        v, f = c.convert(val, cxt)
        assert v == val
        assert f is None

    def test_optional(self):
        factory = get_builtin_factory(int, "test")
        assert factory

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, int, float, Decimal], int)
        v, f = c.convert(None, cxt)
        assert v is None
        assert f is not None

        factory = OptionalFactory(factory)

        c, cxt = self.converter(factory)
        assert (c.accepts, c.returns) == (Union[str, int, float, Decimal, None], Optional[int])
        v, f = c.convert(None, cxt)
        assert v == None
        assert f is None

    def test_optional_strict(self):
        factory = get_builtin_factory(int, "test")
        assert factory

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (int, int)
        v, f = c.convert(None, cxt)
        assert v is None
        assert f is not None

        factory = OptionalFactory(factory)

        c, cxt = self.converter(factory, strict_builtin=True)
        assert (c.accepts, c.returns) == (Union[int, None], Optional[int])
        v, f = c.convert(None, cxt)
        assert v == None
        assert f is None


class TestEnum:
    class E(Enum):
        e1 = auto()
        e2 = auto()

    def converter(self, is_optional: bool = False, **kwargs) -> tuple[Converter, ValidationContext]:
        name, call = get_enum_conversion(TestEnum.E)
        cxt = ValidationContext().configure(**kwargs)
        f = get_factory(name, call)
        if is_optional:
            f = OptionalFactory(f)
        c = f.create(cxt)
        return c, cxt

    def test_convert(self):
        c, cxt = self.converter()
        assert (c.accepts, c.returns) == (Union[TestEnum.E, str], TestEnum.E)
        v, f = c.convert("e1", cxt)
        assert v is TestEnum.E.e1
        assert f is None

    def test_instance(self):
        c, cxt = self.converter()
        assert (c.accepts, c.returns) == (Union[TestEnum.E, str], TestEnum.E)
        v, f = c.convert(TestEnum.E.e1, cxt)
        assert v is TestEnum.E.e1
        assert f is None

    def test_invalid(self):
        c, cxt = self.converter()
        assert (c.accepts, c.returns) == (Union[TestEnum.E, str], TestEnum.E)
        v, f = c.convert("e0", cxt)
        assert v is None
        assert f is not None

    def test_optional(self):
        c, cxt = self.converter(True)
        assert (c.accepts, c.returns) == (Union[TestEnum.E, str, None], Optional[TestEnum.E])
        v, f = c.convert("e1", cxt)
        assert v is TestEnum.E.e1
        assert f is None
        v, f = c.convert(None, cxt)
        assert v is None
        assert f is None


class TestUserDefined:
    class C:
        def __init__(self, value: Any) -> None:
            self.value = value

    def converter(self, is_optional: bool = False, **kwargs) -> tuple[Converter, ValidationContext]:
        def conv(v: int, cxt: ValidationContext) -> TestUserDefined.C:
            return TestUserDefined.C(v)
        def conv_opt(v: Optional[int], cxt: ValidationContext) -> Optional[TestUserDefined.C]:
            return TestUserDefined.C(v) if v is not None else None
        factory = get_user_factory(TestUserDefined.C, None, conv)
        if is_optional:
            factory = OptionalFactory(factory)
        cxt = ValidationContext().configure(**kwargs)
        c = factory.create(cxt)
        return c, cxt

    def test_convert(self):
        c, cxt = self.converter()
        assert (c.accepts, c.returns) == (Union[TestUserDefined.C, int], TestUserDefined.C)
        v, f = c.convert(5, cxt)
        assert isinstance(v, TestUserDefined.C)
        assert v.value == 5
        assert f is None

    def test_instance(self):
        c, cxt = self.converter(strict=True)
        assert (c.accepts, c.returns) == (TestUserDefined.C, TestUserDefined.C)

        v, f = c.convert(5, cxt)
        assert v is None
        assert f is not None

        v, f = c.convert(TestUserDefined.C(5), cxt)
        assert isinstance(v, TestUserDefined.C)
        assert v.value == 5
        assert f is None

    def test_optional(self):
        c, cxt = self.converter(True)
        assert (c.accepts, c.returns) == (Union[TestUserDefined.C, int, None], Union[TestUserDefined.C, None])
        v, f = c.convert(None, cxt)
        assert v is None
        assert f is None

    def test_optional_strict(self):
        c, cxt = self.converter(True, strict=True)
        assert (c.accepts, c.returns) == (Union[TestUserDefined.C, None], Union[TestUserDefined.C, None])
        v, f = c.convert(None, cxt)
        assert v is None
        assert f is None