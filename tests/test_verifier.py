import  pytest
from dhampyr.failures import ValidationFailure, CompositeValidationFailure
from dhampyr.context import ValidationContext
from dhampyr.verifier import Verifier, VerificationFailure


class TestVerify:
    def test_verify(self):
        v = Verifier("test", bool, False)
        f = v.verify("1")
        assert f is None

    def test_false(self):
        v = Verifier("test", bool, False)
        f = v.verify("")
        assert isinstance(f, VerificationFailure)
        assert f.name == "test"
        assert f.verifier is v

    def test_exception(self):
        def fail(v):
            raise Exception()
        v = Verifier("test", fail, False)
        f = v.verify("1")
        assert isinstance(f, VerificationFailure)
        assert f.name == "test"
        assert f.verifier is v

    def test_validation_failure(self):
        def fail(v):
            raise ValidationFailure()
        v = Verifier("test", fail, False)
        f = v.verify("1")
        assert isinstance(f, ValidationFailure)
        assert not isinstance(f, VerificationFailure)
        assert f.name == "invalid"

    def test_verification_failure(self):
        def fail(v):
            VerificationFailure.abort("verification failed")
        v = Verifier("test", fail, False)
        f = v.verify("1")
        assert isinstance(f, VerificationFailure)
        assert f.name == "test"
        assert f.verifier is v

    def test_context(self):
        def fail(v, cxt:ValidationContext):
            raise ValidationFailure(name="context")
        v = Verifier("test", fail, False)
        f = v.verify("1")
        assert isinstance(f, ValidationFailure)
        assert f.name == "context"


class TestIterativeVerify:
    def test_verify(self):
        def ver(v):
            return v > 0
        v = Verifier("test", ver, True)
        f = v.verify([3, 2, 1])
        assert f is None

    def test_false(self):
        def ver(v):
            return v > 0
        v = Verifier("test", ver, True)
        f = v.verify([2, 1, 0])
        assert isinstance(f, CompositeValidationFailure)
        assert len(f) == 1
        assert f[2].name == "test" # type: ignore

    def test_context(self):
        def fail(v, cxt:ValidationContext):
            raise ValidationFailure(name=str(cxt.path))
        v = Verifier("test", fail, True)
        f = v.verify([3, 2, 1], ValidationContext())
        assert isinstance(f, CompositeValidationFailure)
        assert len(f) == 3
        assert [f[i].name for i in range(3)] == ["[0]", "[1]", "[2]"] # type: ignore