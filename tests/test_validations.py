import pytest
from enum import Enum, auto
from functools import partial as p
from typing import Annotated, Optional
from dhampyr.api import v, parse_validators, validate_dict, validatable
from dhampyr.context import ValidationContext


# pyright: reportOptionalMemberAccess=false


class TestParse:
    class Requirement:
        v1 = None
        v2: int
        v3: int = v()
        v4: int = +v()
        v5 = v(..., default=5) / ... & None

    def test_parse(self):
        vs = parse_validators(TestParse.Requirement)
        assert set(vs.keys()) == {"v3", "v4", "v5"}


class TestMalformed:
    def test_malformed(self):
        class C:
            v1: int = v()
        r = validate_dict(C, [])
        assert [(str(p), f.name) for p, f in r.failures] == [("", "malformed")]


class TestKey:
    def test_success(self):
        @validatable()
        class C:
            v1: int = v(alias="value-1")
        r = validate_dict(C, {"value-1": "3"})
        assert r.get().v1 == 3

    def test_failure(self):
        @validatable()
        class C:
            v1: int = v(alias="value-1")
        r = validate_dict(C, {"value-1": "a"})
        assert r.failures['v1'] is not None
        assert [(str(p), f.name) for p,f in r.failures] == [("v1", "int")]


# Types
class E(Enum):
    E1 = auto()
    E2 = auto()
    E3 = auto()
    E4 = auto()
    E5 = auto()


# Verifier functions
def gt0(v):
    return v > 0

def lt(v):
    return v < 101

def gt(v, th):
    return v > th

def longer(vs):
    return len(vs) > 3


class TestFlat:
    def _validate(self, values, share=False):
        class V:
            # don't fail
            v1: Annotated[str, v()] = "v1"
            # required
            v2: Annotated[str, +v()] = "v2"
            # converter
            v3: Annotated[int, v()] = 3
            # converter without default
            v4: Annotated[int, v()]
            # named converter
            v5: Annotated[int, v(("c5", int))] = 5
            # Enum
            v6: Annotated[E, v()] = E.E2
            # converter with partial
            v7: Annotated[int, v(p(int, base=2))] = 7
            # verifier
            v8: Annotated[int, v(..., gt0)] = 8
            # verifier without default
            v9: Annotated[int, v(..., gt0)]
            # multiple verifiers
            v10: Annotated[int, v(..., gt0, lt)] = 10
            # named verifier
            v11: Annotated[int, v(..., ("v13", gt0))] = 11
            # verifier with partial
            v12: Annotated[int, v(..., p(gt, th=0))] = 12

        return validate_dict(V, values, ValidationContext().configure(share_context=share))

    @pytest.mark.parametrize("share", [False, True])
    def test_empty(self, share):
        r = self._validate(dict(), share)
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
        assert (not share) or r.context._contexts == {}

    @pytest.mark.parametrize("share", [False, True])
    def test_success(self, share):
        r = self._validate(dict(
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
        ), share)
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
        assert (not share) or r.context._contexts == {}

    @pytest.mark.parametrize("share", [False, True])
    def test_fail(self, share):
        r = self._validate(dict(
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
        ), share)
        assert not r
        assert [str(p) for p, f in r.failures] == [f"v{i}" for i in range(2, 13)]
        assert r.failures["v7"].kwargs == dict(base=2)
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
        assert (not share) or r.context._contexts == {}


class TestList:
    def _validate(self, values, share):
        class V:
            v1: list[int] = v(..., default_factory=lambda: [1])
            v2: list[int] = +v(..., default_factory=lambda: [2])
            v3: list[int] = v(("c2", [int]), default_factory=lambda: [3])
            v4: list[E] = v(..., default_factory=lambda: [E.E5])
            v5: list[int] = v([p(int, base=2)], default_factory=lambda: [5])
            v6: list[int] = v(..., [gt0], default_factory=lambda: [6])
            v7: list[int] = v(..., [gt0], [lt], default_factory=lambda: [7])
            v8: list[int] = v(..., [gt0], longer, default_factory=lambda: [8])

        return validate_dict(V, values, ValidationContext().configure(share_context=share))

    @pytest.mark.parametrize("share", [False, True])
    def test_empty(self, share):
        r = self._validate(dict(), share)
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
        assert (not share) or r.context._contexts == {}

    @pytest.mark.parametrize("share", [False, True])
    def test_success(self, share):
        r = self._validate(dict(
            v1 = "123",
            v2 = "123",
            v3 = "123",
            v4 = ["E1", "E3", "E5"],
            v5 = ["1011", "1100", "1001"],
            v6 = ["1", "2", "3"],
            v7 = ["1", "2", "3"],
            v8 = "1234",
        ), share)
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
        assert (not share) or r.context._contexts == {}

    @pytest.mark.parametrize("share", [False, True])
    def test_fail(self, share):
        r = self._validate(dict(
            v1 = "1ab",
            v2 = "",
            v3 = "1a3",
            v4 = ["E1", "E10", "E11"],
            v5 = ["1011", "2100", "1001"],
            v6 = ["1", "-2", "3"],
            v7 = ["1", "102", "3"],
            v8 = "123",
        ), share)
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
        assert r.failures["v1"][1].name == "int" # type: ignore
        assert r.failures["v1"][2].name == "int" # type: ignore
        assert r.failures["v2"].name == "empty"
        assert r.failures["v3"][1].name == "c2" # type: ignore
        assert r.failures["v5"][1].name == "int" # type: ignore
        assert r.failures["v5"][1].kwargs == dict(base=2) # type: ignore
        assert r.failures["v8"].name == "longer"
        assert r.get().v1 == [1]
        assert r.get().v2 == [2]
        assert r.get().v3 == [3]
        assert r.get().v4 == [E.E5]
        assert r.get().v5 == [5]
        assert r.get().v6 == [6]
        assert r.get().v7 == [7]
        assert r.get().v8 == [8]
        assert (not share) or r.context._contexts == {}


class TestNest:
    def _validate(self, values, context=None, share=False):
        class C:
            c1: +v([int], [gt0]) = [1]
            c2: +v(int, gt0) = 2

        class P:
            p1: +v(C) = None
            p2: +v([C]) = []

        class V:
            v1: +v(P) = None
            v2: +v([P]) = []

        context = (context or ValidationContext()).configure(share_context=share)

        return validate_dict(V, values, context)

    @pytest.mark.parametrize("share", [False, True])
    def test_empty(self, share):
        r = self._validate(dict(), share=share)
        assert not r
        assert [str(p) for p, f in r.failures] \
            == ["v1", "v2"]
        assert r.get().v1 is None
        assert r.get().v2 == []
        assert (not share) or r.context._contexts == {}

    @pytest.mark.parametrize("share", [False, True])
    def test_empty_parent(self, share):
        r = self._validate(dict(
            v1 = dict(),
            v2 = [dict()],
        ), share=share)
        assert not r
        assert [str(p) for p, f in r.failures] \
            == ["v1.p1", "v1.p2", "v2[0].p1", "v2[0].p2"]
        assert r.get().v1 is None
        assert r.get().v2 == []
        assert (not share) or r.context._contexts == {}

    @pytest.mark.parametrize("share", [False, True])
    def test_empty_parent_unjointed(self, share):
        r = self._validate(dict(
            v1 = dict(),
            v2 = [
                dict(),
                dict(
                    p1=dict(c1="12", c2="4"),
                    p2=[dict(c1="34", c2="5")],
                ),
            ],
        ), ValidationContext().configure(join_on_fail=False), share=share)
        assert not r
        assert [str(p) for p, f in r.failures] \
            == ["v1.p1", "v1.p2", "v2[0].p1", "v2[0].p2"]
        assert r.get().v1 is None
        assert r.get().v2[0] is None
        assert r.get().v2[1].p1.c1 == [1,2]
        assert r.get().v2[1].p1.c2 == 4
        assert r.get().v2[1].p2[0].c1 == [3,4]
        assert r.get().v2[1].p2[0].c2 == 5
        assert (not share) or r.context._contexts == {}

    @pytest.mark.parametrize("share", [False, True])
    def test_success(self, share):
        r = self._validate(dict(
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
        ), share=share)
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
        assert (not share) or r.context._contexts == {}

    @pytest.mark.parametrize("share", [False, True])
    def test_fail(self, share):
        r = self._validate(dict(
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
        ), share=share)
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
        assert (not share) or r.context._contexts == {}


class TestRemainders:
    def _validate(self, context=None, share=False):
        class C:
            c1: +v([int]) = [1]
            c2: +v(int) = 2

        class P:
            p1: +v(C) = None
            p2: +v([C]) = []

        class V:
            v1: +v(P) = None
            v2: +v([P]) = []

        context = (context or ValidationContext()).configure(share_context=share)

        return validate_dict(V, dict(
            v1 = dict(
                p1 = dict(c1 = ["1"], c2 = "2", c3 = "c3"),
                p2 = [
                    dict(c1 = ["11"], c2 = "22", c3 = "c3_1"),
                    dict(c1 = ["11"], c2 = "22", c3 = "c3_2"),
                ],
                p3 = 43,
            ),
            v2 = [
                dict(
                    p1 = dict(c1 = ["1"], c2 = "2", c3 = "c23_1"),
                    p2 = [
                        dict(c1 = ["11"], c2 = "22", c3 = "c23_1_1"),
                        dict(c1 = ["11"], c2 = "22", c3 = "c23_1_2"),
                    ],
                    p3 = 54,
                ),
                dict(
                    p1 = dict(c1 = ["1"], c2 = "2", c3 = "c23_2"),
                    p2 = [
                        dict(c1 = ["11"], c2 = "22", c3 = "c23_2_1"),
                        dict(c1 = ["11"], c2 = "22", c3 = "c23_2_2"),
                    ],
                    p3 = 65,
                ),
            ],
            v3 = 32,
        ), context)

    @pytest.mark.parametrize("share", [False, True])
    def test_remainders(self, share):
        r = self._validate(share=share)
        if share:
            assert r.context.remainders == dict(
                v1 = dict(
                    p1 = dict(c3 = "c3"),
                    p2 = {0: dict(c3 = "c3_1"), 1: dict(c3 = "c3_2") },
                    p3 = 43,
                ),
                v2 = {
                    0: dict(
                        p1 = dict(c3 = "c23_1"),
                        p2 = {0: dict(c3 = "c23_1_1"), 1: dict(c3 = "c23_1_2")},
                        p3 = 54,
                    ),
                    1: dict(
                        p1 = dict(c3 = "c23_2"),
                        p2 = {0: dict(c3 = "c23_2_1"), 1: dict(c3 = "c23_2_2")},
                        p3 = 65,
                    ),
                },
                v3 = 32,
            )
            assert r.context._contexts == {}
        else:
            assert r.context.remainders == dict(v3 = 32)
            assert r.context["v1"].remainders == dict(p3 = 43)
            assert r.context["v1"]["p1"].remainders == dict(c3 = "c3")
            assert r.context["v1"]["p2"][0].remainders == dict(c3 = "c3_1")
            assert r.context["v1"]["p2"][1].remainders == dict(c3 = "c3_2")
            assert r.context["v2"][0].remainders == dict(p3 = 54)
            assert r.context["v2"][1].remainders == dict(p3 = 65)
            assert r.context["v2"][0]["p1"].remainders == dict(c3 = "c23_1")
            assert r.context["v2"][1]["p1"].remainders == dict(c3 = "c23_2")
            assert r.context["v2"][0]["p2"][0].remainders == dict(c3 = "c23_1_1")
            assert r.context["v2"][0]["p2"][1].remainders == dict(c3 = "c23_1_2")
            assert r.context["v2"][1]["p2"][0].remainders == dict(c3 = "c23_2_1")
            assert r.context["v2"][1]["p2"][1].remainders == dict(c3 = "c23_2_2")
            assert r.context._contexts != {}

    def test_ignore(self):
        c = ValidationContext()
        c["v1"].configure(ignore_remainders = True)
        c["v2"][0].configure(ignore_remainders = True)
        r = self._validate(c)
        assert r.context.remainders == dict(v3 = 32)
        assert r.context["v1"].remainders == dict()
        assert r.context["v1"]["p1"].remainders == dict()
        assert r.context["v1"]["p2"][0].remainders == dict()
        assert r.context["v1"]["p2"][1].remainders == dict()
        assert r.context["v2"][0].remainders == dict()
        assert r.context["v2"][1].remainders == dict(p3 = 65)
        assert r.context["v2"][0]["p1"].remainders == dict()
        assert r.context["v2"][1]["p1"].remainders == dict(c3 = "c23_2")
        assert r.context["v2"][0]["p2"][0].remainders == dict()
        assert r.context["v2"][0]["p2"][1].remainders == dict()
        assert r.context["v2"][1]["p2"][0].remainders == dict(c3 = "c23_2_1")
        assert r.context["v2"][1]["p2"][1].remainders == dict(c3 = "c23_2_2")
        assert r.context._contexts != {}


class TestTypeConfiguration:
    def _validate(self, values, context=None):
        @validatable(ignore_remainders=True)
        class Q:
            q1: int = +v()
            q2: int = +v()

        @validatable(strict_builtin=True)
        class P:
            p1: Optional[Q] = +v(Q, default=None)
            p2: Optional[Q] = +v(Q, default=None)

        class V:
            v1: P = +v(P)
            v2: Q = +v(Q)

        return validate_dict(V, values, context=context)

    def test_typed(self):
        c = ValidationContext()
        c["v1"]["p2"].configure(strict_builtin=False, ignore_remainders=False)
        c["v2"].configure(strict_builtin=True)
        c["v2"]["q1"].configure(strict_builtin=False)

        r = self._validate(dict(
            v1 = dict(
                p1 = dict(q1 = 1, q2 = 2, q3 = 11),
                p2 = dict(q1 = "1", q2 = "2", q3 = 12),
                p3 = 3,
            ),
            v2 = dict(q1 = "1", q2 = 2, q3 = 21),
            v3 = 4,
        ), c)

        value = r.get()
        failures = r.failures
        assert (value.v1.p1.q1, value.v1.p1.q2) == (1, 2)
        assert (value.v1.p2.q1, value.v1.p2.q2) == (1, 2)
        assert (value.v1.p2.q1, value.v1.p2.q2) == (1, 2)
        assert (value.v2.q1, value.v2.q2) == (1, 2)
        assert c.remainders == dict(v3 = 4)
        assert c["v1"].remainders == dict(p3 = 3)
        assert c["v2"].remainders == dict()
        assert c["v1"]["p1"].remainders == dict()
        assert c["v1"]["p2"].remainders == dict(q3 = 12)
        assert r.context._contexts != {}

    @pytest.mark.parametrize("share", [False, True])
    def test_fail(self, share):
        c = ValidationContext().configure(share_context=share)

        r = self._validate(dict(
            v1 = dict(
                p1 = dict(q1 = 1, q2 = 2, q3 = 11),
                p2 = dict(q1 = "1", q2 = "2", q3 = 12),
                p3 = 3,
            ),
            v2 = dict(q1 = "1", q2 = 2, q3 = 21),
            v3 = 4,
        ), c)

        value = r.get()
        failures = r.failures
        assert value.v1 is None
        assert (value.v2.q1, value.v2.q2) == (1, 2)
        assert {str(p) for p, _ in failures} == {"v1.p2.q1", "v1.p2.q2"}
        if share:
            assert c.remainders == dict(
                v1 = dict(p3 = 3),
                v3 = 4,
            )
            assert r.context._contexts == {}
        else:
            assert c.remainders == dict(v3 = 4)
            assert c["v1"].remainders == dict(p3 = 3)
            assert c["v2"].remainders == dict()
            assert c["v1"]["p1"].remainders == dict()
            assert c["v1"]["p2"].remainders == dict()
            assert r.context._contexts != {}
