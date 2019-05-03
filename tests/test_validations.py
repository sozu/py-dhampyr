import pytest
from dhampyr.validator import *

def test_create_validator_no_verifiers():
    val = v(int)
    assert not val.requires
    assert len(val.verifiers) == 0
    assert val.validate("1")[0] == 1
    assert isinstance(val.validate("a")[1], ConversionFailure)

def test_create_validator_one_verifier():
    val = v(int, lambda x: x <= 1)
    assert not val.requires
    assert len(val.verifiers) == 1
    assert val.validate("1")[0] == 1
    assert isinstance(val.validate("2")[1], VerificationFailure)

def test_create_validator_multi_verifiers():
    v1, v2 = lambda x: x >= 0, lambda x: x <= 1
    val = v(int, v1, v2)
    assert not val.requires
    assert len(val.verifiers) == 2
    assert val.validate("1")[0] == 1
    assert val.validate("2")[1].verifier is val.verifiers[1]

def test_create_validator_requires():
    val = +v(int)
    assert val.requires

class V:
    a1: +v(int) = None
    a2: v(int) = None
    a3: v(int, lambda x: x == 3) = None
    a4: v(int, lambda x: x > 3, lambda x: x < 5) = None

def test_validate_dict():
    r = validate_dict(V, dict(a1="1", a2="2", a3="3", a4="4"))
    assert len(r.failures) == 0
    d = r.get()
    assert d.a1 == 1
    assert d.a2 == 2
    assert d.a3 == 3
    assert d.a4 == 4

def test_validate_dict_allow_missing():
    r = validate_dict(V, dict(a1="1", a3="3", a4="4"))
    assert len(r.failures) == 0
    d = r.get()
    assert d.a1 == 1
    assert d.a2 is None
    assert d.a3 == 3
    assert d.a4 == 4

def test_validate_dict_fail_missing():
    r = validate_dict(V, dict(a2="2", a3="3", a4="4"))
    assert len(r.failures) == 1
    assert isinstance(r.failures["a1"], MissingFailure)

def test_validate_dict_fail_convert():
    r = validate_dict(V, dict(a1="1", a2="a", a3="3", a4="b"))
    assert len(r.failures) == 2
    assert isinstance(r.failures["a2"], ConversionFailure)
    assert isinstance(r.failures["a4"], ConversionFailure)

def test_validate_dict_fail_verify():
    r = validate_dict(V, dict(a1="1", a2="2", a3="2", a4="5"))
    assert len(r.failures) == 2
    assert isinstance(r.failures["a3"], VerificationFailure)
    assert isinstance(r.failures["a4"], VerificationFailure)

class W:
    b1: +v([int]) = None
    b2: +v([int], ("v21", lambda x: len(x) > 2), ("v22", lambda x: len(x) < 4)) = None
    b3: +v([int], [("v31", lambda x: x >= 0)], [("v32", lambda x: x <= 1)]) = None
    b4: +v([int], ("v41", lambda x: len(x) == 3), [("v42", lambda x: x > 0 and x < 4)]) = None

def test_validate_dict_iter():
    r = validate_dict(W, dict(b1=["1", "2"], b2=["0", "1", "2"], b3=["0", "1"], b4=["1", "2", "3"]))
    assert len(r.failures) == 0
    d = r.get()
    assert d.b1 == [1, 2]
    assert d.b2 == [0, 1, 2]
    assert d.b3 == [0, 1]
    assert d.b4 == [1, 2, 3]

def test_validate_fail_iter():
    r = validate_dict(W, dict(b1=["a", "2"], b2=["0", "1"], b3=["1", "2"], b4=["2", "3", "4"]))
    assert len(r.failures) == 4
    assert isinstance(r.failures["b1"][0], ConversionFailure)
    assert isinstance(r.failures["b2"], VerificationFailure)
    assert r.failures["b2"].verifier.name == "v21"
    assert isinstance(r.failures["b3"][1], VerificationFailure)
    assert r.failures["b3"][1].verifier.name == "v32"
    assert isinstance(r.failures["b4"][2], VerificationFailure)
    assert r.failures["b4"][2].verifier.name == "v42"

class C:
    c1: +v(int, ("c1", lambda x: x > 0)) = None
    c2: +v([int], [("c2", lambda x: x > 0)]) = None

class P:
    p1: +v({C}, ("p1", lambda x: x.c1 > 10)) = None
    p2: +v([{C}], [("p2", lambda x: x.c1 > 10)]) = None

def test_nested_dict():
    r = validate_dict(P, dict(
        p1 = dict(c1 = "11", c2 = ["1", "2", "3"]),
        p2 = [
            dict(c1 = "11", c2 = ["1", "2", "3"]),
            dict(c1 = "12", c2 = ["4", "5", "6"]),
        ],
    ))
    assert len(r.failures) == 0
    d = r.get()
    assert d.p1.c1 == 11
    assert d.p1.c2 == [1, 2, 3]
    assert d.p2[0].c1 == 11
    assert d.p2[0].c2 == [1, 2, 3]
    assert d.p2[1].c1 == 12
    assert d.p2[1].c2 == [4, 5, 6]

def test_fail_nested_dict_on_child():
    r = validate_dict(P, dict(
        p1 = dict(c1 = "0", c2 = ["1", "-2", "3"]),
        p2 = [
            dict(c1 = "11", c2 = ["1", "-2", "3"]),
            dict(c1 = "0", c2 = ["4", "5", "6"]),
        ],
    ))
    assert len(r.failures) == 2
    assert len(r.failures["p1"]) == 2
    assert len(r.failures["p2"]) == 2
    assert len(r.failures["p2"][0]) == 1
    assert len(r.failures["p2"][1]) == 1
    assert r.failures["p1"]["c1"].name == "c1"
    assert r.failures["p1"]["c2"][1].name == "c2"
    assert r.failures["p2"][0]["c2"][1].name == "c2"
    assert r.failures["p2"][1]["c1"].name == "c1"
    keyset = set([str(k) for k, f in r.failures])
    assert keyset == {"p1.c1", "p1.c2[1]", "p2[0].c2[1]", "p2[1].c1"}

def test_fail_nested_dict_on_parent():
    r = validate_dict(P, dict(
        p1 = dict(c1 = "10", c2 = ["1", "2", "3"]),
        p2 = [
            # Verification of 'p2' iteself is not done because the first child fails.
            # Therefore, the result does not contain the failure supposed to happen by `x.c1 > 10`.
            dict(c1 = "10", c2 = ["1", "-2", "3"]),
            dict(c1 = "10", c2 = ["4", "5", "6"]),
        ],
    ))
    assert len(r.failures) == 2
    assert isinstance(r.failures["p1"], VerificationFailure)
    assert len(r.failures["p2"]) == 1
    assert len(r.failures["p2"][0]) == 1
    assert r.failures["p1"].name == "p1"
    assert r.failures["p2"][0]["c2"][1].name == "c2"
    keyset = set([str(k) for k, f in r.failures])
    assert keyset == {"p1", "p2[0].c2[1]"}

def test_context():
    class C:
        a: v(int) = 0
    r = validate_dict(C, dict(a = "1", b = "a", c = dict(d="b")))
    assert len(r.failures) == 0
    assert r.get().a == 1
    assert r.context.remainders == dict(b = "a", c = dict(d = "b"))

def test_context_nested():
    class D:
        b: v(int, lambda x: x < 2) = 0
    class C:
        a: v({D}) = None
    r = validate_dict(C, dict(a = dict(b = "1", c = "c"), b = "b"))
    assert len(r.failures) == 0
    assert r.get().a.b == 1
    assert r.context.remainders == dict(b = "b")
    assert r.context["a"].remainders == dict(c = "c")

def test_context_iter_nested():
    class D:
        b: v(int, lambda x: x < 3) = 0
    class C:
        a: v([{D}]) = []
    r = validate_dict(C, dict(a = [dict(b = "1", c = "c"), dict(b = "2", d = "d")], b = "b"))
    assert len(r.failures) == 0
    assert r.get().a[0].b == 1
    assert r.context.remainders == dict(b = "b")
    assert r.context["a"].remainders == [dict(c = "c"), dict(d = "d")]