import pytest
from enum import Enum, auto
from functools import partial as p
from dhampyr.api import v, parse_validators, validate_dict
from dhampyr.context import ValidationContext


class TestParse:
    class Requirement:
        v1 = None
        v2: int
        v3: v(int)
        v4: +v(int)
        v5: v(int) & None | ... = 5

    def test_parse(self):
        vs = parse_validators(TestParse.Requirement)
        assert set(vs.keys()) == {"v3", "v4", "v5"}


class TestMalformed:
    def test_malformed(self):
        class C:
            v1: v(int)
        r = validate_dict(C, [])
        assert [(str(p), f.name) for p, f in r.failures] == [("", "malformed")]


class E(Enum):
    E1 = auto()
    E2 = auto()
    E3 = auto()
    E4 = auto()
    E5 = auto()


def gt0(v):
    return v > 0

def lt(v):
    return v < 101

def gt(v, th):
    return v > th

class V1:
    # don't fail
    v1: v(str) = "v1"
    # required
    v2: +v(str) = "v2"
    # converter
    v3: v(int) = 3
    # converter without default
    v4: v(int)
    # named converter
    v5: v(("c5", int)) = 5
    # Enum
    v6: v(E) = E.E2
    # converter with partial
    v7: v(p(int, base=2)) = 7
    # verifier
    v8: v(int, gt0) = 8
    # verifier without default
    v9: v(int, gt0)
    # multiple verifiers
    v10: v(int, gt0, lt) = 10
    # named verifier
    v11: v(int, ("v13", gt0)) = 11
    # verifier with partial
    v12: v(int, p(gt, th=0)) = 12


class TestFlat:
    def test_empty(self):
        r = validate_dict(V1, dict())
        assert not r
        assert [str(p) for p, f in r.failures] == ["v2"]
        assert r.get().v1 == "v1"
        assert r.get().v3 == 3
        assert not hasattr(r.get(), "v4")
        assert r.get().v5 == 5
        assert r.get().v6 == E.E2
        assert r.get().v7 == 7
        assert r.get().v8 == 8
        assert not hasattr(r.get(), "v9")
        assert r.get().v10 == 10
        assert r.get().v11 == 11
        assert r.get().v12 == 12

    def test_success(self):
        r = validate_dict(V1, dict(
            v1 = "s1",
            v2 = "s2",
            v3 = "30",
            v4 = "40",
            v5 = "50",
            v6 = "E1",
            v7 = "1000110",
            v8 = "80",
            v9 = "90",
            v10 = "100",
            v11 = "110",
            v12 = "120",
        ))
        assert r
        assert not r.failures
        assert r.get().v1 == "s1"
        assert r.get().v2 == "s2"
        assert r.get().v3 == 30
        assert r.get().v4 == 40
        assert r.get().v5 == 50
        assert r.get().v6 == E.E1
        assert r.get().v7 == 70
        assert r.get().v8 == 80
        assert r.get().v9 == 90
        assert r.get().v10 == 100
        assert r.get().v11 == 110
        assert r.get().v12 == 120

    def test_fail(self):
        r = validate_dict(V1, dict(
            v1 = "",
            v2 = None,
            v3 = "f3",
            v4 = "f4",
            v5 = "f5",
            v6 = "E10",
            v7 = "70",
            v8 = "-8",
            v9 = "-9",
            v10 = "1000",
            v11 = "-11",
            v12 = "-12",
        ))
        assert not r
        assert [str(p) for p, f in r.failures] == [f"v{i}" for i in range(2, 13)]
        assert r.get().v1 == "v1"
        assert r.get().v2 == "v2"
        assert r.get().v3 == 3
        assert not hasattr(r.get(), "v4")
        assert r.get().v5 == 5
        assert r.get().v6 == E.E2
        assert r.get().v7 == 7
        assert r.get().v8 == 8
        assert not hasattr(r.get(), "v9")
        assert r.get().v10 == 10
        assert r.get().v11 == 11
        assert r.get().v12 == 12


def longer(vs):
    return len(vs) > 3


class V2:
    v1: v([int]) = [1]
    v2: +v([int]) = [2]
    v3: v([("c2", int)]) = [3]
    v4: v([E]) = [E.E5]
    v5: v([p(int, base=2)]) = [5]
    v6: v([int], [gt0]) = [6]
    v7: v([int], [gt0], [lt]) = [7]
    v8: v([int], [gt0], longer) = [8]


class TestList:
    def test_empty(self):
        r = validate_dict(V2, dict())
        assert not r
        assert [str(p) for p, f in r.failures] == ["v2"]
        assert r.get().v1 == [1]
        assert r.get().v2 == [2]
        assert r.get().v3 == [3]
        assert r.get().v4 == [E.E5]
        assert r.get().v5 == [5]
        assert r.get().v6 == [6]
        assert r.get().v7 == [7]
        assert r.get().v8 == [8]

    def test_success(self):
        r = validate_dict(V2, dict(
            v1 = "123",
            v2 = "123",
            v3 = "123",
            v4 = ["E1", "E3", "E5"],
            v5 = ["1011", "1100", "1001"],
            v6 = ["1", "2", "3"],
            v7 = ["1", "2", "3"],
            v8 = "1234",
        ))
        assert r
        assert not r.failures
        assert r.get().v1 == [1, 2, 3]
        assert r.get().v2 == [1, 2, 3]
        assert r.get().v3 == [1, 2, 3]
        assert r.get().v4 == [E.E1, E.E3, E.E5]
        assert r.get().v5 == [11, 12, 9]
        assert r.get().v6 == [1, 2, 3]
        assert r.get().v7 == [1, 2, 3]
        assert r.get().v8 == [1, 2, 3, 4]

    def test_fail(self):
        r = validate_dict(V2, dict(
            v1 = "1ab",
            v2 = "",
            v3 = "1a3",
            v4 = ["E1", "E10", "E11"],
            v5 = ["1011", "2100", "1001"],
            v6 = ["1", "-2", "3"],
            v7 = ["1", "102", "3"],
            v8 = "123",
        ))
        assert not r
        assert [str(p) for p, f in r.failures] == [
            "v1[1]", "v1[2]",
            "v2",
            "v3[1]",
            "v4[1]", "v4[2]",
            "v5[1]",
            "v6[1]",
            "v7[1]",
            "v8",
        ]
        assert r.failures["v1"][1].name == "int"
        assert r.failures["v1"][2].name == "int"
        assert r.failures["v2"].name == "empty"
        assert r.failures["v3"][1].name == "c2"
        assert r.failures["v8"].name == "longer"
        assert r.get().v1 == [1]
        assert r.get().v2 == [2]
        assert r.get().v3 == [3]
        assert r.get().v4 == [E.E5]
        assert r.get().v5 == [5]
        assert r.get().v6 == [6]
        assert r.get().v7 == [7]
        assert r.get().v8 == [8]


class C:
    c1: +v([int], [gt0]) = [1]
    c2: +v(int, gt0) = 2


class P:
    p1: +v({C}) = None
    p2: +v([{C}]) = []


class V3:
    v1: +v({P}) = None
    v2: +v([{P}]) = []


class TestNest:
    def test_empty(self):
        r = validate_dict(V3, dict())
        assert not r
        assert [str(p) for p, f in r.failures] \
            == ["v1", "v2"]
        assert r.get().v1 is None
        assert r.get().v2 == []

    def test_empty_parent(self):
        r = validate_dict(V3, dict(
            v1 = dict(),
            v2 = [dict()],
        ))
        assert not r
        assert [str(p) for p, f in r.failures] \
            == ["v1.p1", "v1.p2", "v2[0].p1", "v2[0].p2"]
        assert r.get().v1 is None
        assert r.get().v2 == []

    def test_empty_parent_unjointed(self):
        r = validate_dict(V3, dict(
            v1 = dict(),
            v2 = [
                dict(),
                dict(
                    p1=dict(c1="12", c2="4"),
                    p2=[dict(c1="34", c2="5")],
                ),
            ],
        ), ValidationContext().configure(join_on_fail=False))
        assert not r
        assert [str(p) for p, f in r.failures] \
            == ["v1.p1", "v1.p2", "v2[0].p1", "v2[0].p2"]
        assert r.get().v1 is None
        assert r.get().v2[0] is None
        assert r.get().v2[1].p1.c1 == [1,2]
        assert r.get().v2[1].p1.c2 == 4
        assert r.get().v2[1].p2[0].c1 == [3,4]
        assert r.get().v2[1].p2[0].c2 == 5

    def test_success(self):
        r = validate_dict(V3, dict(
            v1 = dict(
                p1 = dict(c1 = "12", c2 = "3"),
                p2 = [
                    dict(c1 = "34", c2 = "5"),
                    dict(c1 = "56", c2 = "7"),
                ]
            ),
            v2 = [
                dict(
                    p1 = dict(c1 = "123", c2 = "4"),
                    p2 = [
                        dict(c1 = "234", c2 = "5"),
                        dict(c1 = "345", c2 = "6"),
                    ],
                ),
                dict(
                    p1 = dict(c1 = "456", c2 = "7"),
                    p2 = [
                        dict(c1 = "567", c2 = "8"),
                        dict(c1 = "678", c2 = "9"),
                    ],
                ),
            ],
        ))
        assert r
        assert not r.failures
        assert r.get().v1.p1.c1 == [1,2]
        assert r.get().v1.p1.c2 == 3
        assert r.get().v1.p2[0].c1 == [3,4]
        assert r.get().v1.p2[0].c2 == 5
        assert r.get().v1.p2[1].c1 == [5,6]
        assert r.get().v1.p2[1].c2 == 7
        assert r.get().v2[0].p1.c1 == [1,2,3]
        assert r.get().v2[0].p1.c2 == 4
        assert r.get().v2[0].p2[0].c1 == [2,3,4]
        assert r.get().v2[0].p2[0].c2 == 5
        assert r.get().v2[0].p2[1].c1 == [3,4,5]
        assert r.get().v2[0].p2[1].c2 == 6
        assert r.get().v2[1].p1.c1 == [4,5,6]
        assert r.get().v2[1].p1.c2 == 7
        assert r.get().v2[1].p2[0].c1 == [5,6,7]
        assert r.get().v2[1].p2[0].c2 == 8
        assert r.get().v2[1].p2[1].c1 == [6,7,8]
        assert r.get().v2[1].p2[1].c2 == 9

    def test_fail(self):
        r = validate_dict(V3, dict(
            v1 = dict(
                p1 = dict(c1 = "12", c2 = "-3"),
                p2 = [
                    dict(c1 = "34", c2 = "5"),
                    dict(c1 = ["-5", "6"], c2 = "7"),
                ]
            ),
            v2 = [
                dict(
                    p1 = dict(c1 = ["1", "-2", "-3"], c2 = "4"),
                    p2 = [
                        dict(c1 = "234", c2 = "5"),
                        dict(c1 = ["-3", "-4", "-5"], c2 = "-6"),
                    ],
                ),
                dict(
                    p1 = dict(c1 = "456", c2 = "7"),
                    p2 = [
                        dict(c1 = "567", c2 = "8"),
                        dict(c1 = "678", c2 = "9"),
                    ],
                ),
            ],
        ))
        assert not r
        assert [str(p) for p, f in r.failures] \
            == [
                "v1.p1.c2",
                "v1.p2[1].c1[0]",
                "v2[0].p1.c1[1]",
                "v2[0].p1.c1[2]",
                "v2[0].p2[1].c1[0]",
                "v2[0].p2[1].c1[1]",
                "v2[0].p2[1].c1[2]",
                "v2[0].p2[1].c2",
            ]