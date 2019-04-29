import pytest
from enum import Enum, auto
from dhampyr.validator import *

def test_convert_value():
    c = Converter("a", int, False)
    r, f = c.convert("1")
    assert r == 1
    assert f is None

def test_fail_convert_value():
    c = Converter("a", int, False)
    r, f = c.convert("a")
    assert r is None
    assert isinstance(f, ConversionFailure)
    assert f.converter is c

def test_convert_iterable():
    c = Converter("a", int, True)
    r, f = c.convert(["1", "2", "3"])
    assert r == [1, 2, 3]
    assert f is None

def test_fail_convert_iterable():
    c = Converter("a", int, False)
    r, f = c.convert(["1", "a", "3"])
    assert r is None
    assert isinstance(f, ConversionFailure)
    assert f.converter is c

def test_general_exception_in_convert():
    def ex(x):
        raise ValueError("test")
    c = Converter("a", ex, False)
    r, f = c.convert("a")
    assert isinstance(f, ConversionFailure)
    assert f.converter is c
    assert f.message == "test"

def test_defined_exception_in_convert():
    def ex(x):
        raise ConversionFailure("test", None)
    c = Converter("a", ex, False)
    r, f = c.convert("a")
    assert isinstance(f, ConversionFailure)
    assert f.converter is c
    assert f.message == "test"

def test_verify_value():
    v = Verifier("a", lambda x: len(x) == 3, False)
    f = v.verify("abc")
    assert f is None

def test_fail_verify_value():
    v = Verifier("a", lambda x: len(x) == 3, False)
    f = v.verify("ab")
    assert isinstance(f, VerificationFailure)
    assert f.verifier is v

def test_verify_iterable():
    v = Verifier("a", lambda x: len(x) == 3, True)
    f = v.verify(["abc", "def", "ghi"])
    assert f is None

def test_fail_verify_iterable():
    v = Verifier("a", lambda x: len(x) == 3, True)
    f = v.verify(["abc", "de", "fhi"])
    assert isinstance(f[1], VerificationFailure)
    assert f[1].verifier is v

def test_general_exception_in_verify():
    def ex(x):
        raise ValueError("test")
    v = Verifier("a", ex, False)
    f = v.verify("a")
    assert isinstance(f, VerificationFailure)
    assert f.verifier is v
    assert f.message == "test"

def test_defined_exception_in_verify():
    def ex(x):
        raise VerificationFailure("test", None)
    v = Verifier("a", ex, False)
    f = v.verify("a")
    assert isinstance(f, VerificationFailure)
    assert f.verifier is v
    assert f.message == "test"

def test_validate_value():
    d = Validator(Converter("c", int, False), [
        Verifier("v", lambda x: x > 0, False)
    ])
    assert not d.accept_list
    r, f = d.validate("1")
    assert r == 1
    assert f is None

def test_validate_iterable():
    d = Validator(Converter("c", int, True), [
        Verifier("v", lambda x: x > 0, True)
    ])
    assert d.accept_list
    r, f = d.validate(["1", "2", "3"])
    assert r == [1, 2, 3]
    assert f is None

def test_validate_multiple_verifier():
    v1, v2 = Verifier("v", lambda x: x > 0, False), Verifier("v", lambda x: x < 4, False)
    d = Validator(Converter("c", int, False), [v1, v2])
    r, f = d.validate("2")
    assert r == 2
    assert f is None

def test_fail_validate_multiple_verifier():
    v1, v2 = Verifier("v", lambda x: x > 0, False), Verifier("v", lambda x: x < 4, False)
    d = Validator(Converter("c", int, False), [v1, v2])
    r, f = d.validate("4")
    assert r is None
    assert isinstance(f, VerificationFailure)
    assert f.verifier is v2

def test_validate_value_to_iterable():
    d = Validator(Converter("c", lambda x: x.split(','), False), [
        Verifier("v", lambda x: int(x) > 0, True)
    ])
    assert not d.accept_list
    r, f = d.validate("1,2,3")
    assert r == ["1", "2", "3"]
    assert f is None

def test_validate_iterable_to_value():
    d = Validator(Converter("c", int, True), [
        Verifier("v", lambda x: len(x) == 3, False)
    ])
    assert d.accept_list
    r, f = d.validate(["1", "2", "3"])
    assert r == [1, 2, 3]
    assert f is None

def test_fail_validate_value_on_convert():
    d = Validator(Converter("c", int, False), [
        Verifier("v", lambda x: x > 0, False)
    ])
    r, f = d.validate("a")
    assert r is None
    assert isinstance(f, ConversionFailure)

def test_fail_validate_iterable_on_convert():
    d = Validator(Converter("c", int, True), [
        Verifier("v", lambda x: x > 0, True)
    ])
    r, f = d.validate(["1", "a", "3"])
    assert r is None
    assert isinstance(f[1], ConversionFailure)

def test_fail_validate_value_on_verify():
    d = Validator(Converter("c", int, False), [
        Verifier("v", lambda x: x > 0, False)
    ])
    r, f = d.validate("-1")
    assert r is None
    assert isinstance(f, VerificationFailure)

def test_fail_validate_iterable_on_verify():
    d = Validator(Converter("c", int, True), [
        Verifier("v", lambda x: x > 0, True)
    ])
    r, f = d.validate(["1", "-2", "3"])
    assert r is None
    assert isinstance(f[1], VerificationFailure)

def test_create_converter_func():
    def f(v):
        return int(v)
    c = converter(f)
    assert not c.is_iter
    assert c.name == "f"
    assert c.convert("1")[0] == 1

def test_create_converter_type():
    c = converter(int)
    assert not c.is_iter
    assert c.name == "int"
    assert c.convert("1")[0] == 1

def test_create_converter_enum():
    class E(Enum):
        E1 = auto()
    c = converter(E)
    assert not c.is_iter
    assert c.name == "E"
    assert c.convert("E1")[0] == E.E1

def test_create_converter_tuple():
    c = converter(("c", lambda x: int(x)))
    assert not c.is_iter
    assert c.name == "c"
    assert c.convert("1")[0] == 1

def test_create_converter_iter():
    c = converter([("c", lambda x: int(x))])
    assert c.is_iter
    assert c.name == "c"
    assert c.convert(["1", "2", "3"])[0] == [1, 2, 3]

def test_create_verifier_func():
    def f(v):
        return v <= 1
    v = verifier(f)
    assert not v.is_iter
    assert v.name == "f"
    assert v.verify(1) is None
    assert v.verify(2) is not None

def test_create_verifier_tuple():
    def f(v):
        return v <= 1
    v = verifier(("v", f))
    assert not v.is_iter
    assert v.name == "v"
    assert v.verify(1) is None
    assert v.verify(2) is not None

def test_create_verifier_iter():
    def f(v):
        return v <= 1
    v = verifier([("v", f)])
    assert v.is_iter
    assert v.name == "v"
    assert v.verify([-1, 0, 1]) is None
    assert v.verify([0, 1, 2]) is not None