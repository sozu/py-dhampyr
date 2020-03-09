# Python simple validator for dictionary-like objects

## Overview

This library provides data validation functionalities designed for HTTP applications. Compared to other validation libraries, this library has following features.

- Validation schemes are declared in annotation context which is introduced in python 3.5.
- Each validation scheme can be composed of simple functions including lambda expressions.
- Errors in validations are represented with informative objects, not with just an error message.

## Installation

This library requires python 3.6 or higher.

```
$ pip install dhampyr
```

## Tutorial

### Declaration of validation scheme

The module `dhampyr.validator` exports a function `v` which creates a `Validator`. This function is designed to be used in annotation context of a class attribute.

```
from dhampyr import *

class C:
    a: v(int, lambda x: x < 5, lambda x: x > 2) = 0
```

In above code, `C` is considered as a *validatable type* and `a` is a *validatable attribute*. While you can use any name for validatable type, the name of each validatable attribute corresponds to the key in input dictionary which is associated with a value the `Validator` will be applied to.

A validation scheme of this library is composed of two phases, type conversion by `Converter` and value verifications by `Verifier`s. The first argument in `v` specifies the `Converter` and each of following optional arguments specifies `Verifier`. 

This code shows the simplest but intrinsic declaration style of `Converter`, just a function `int`. Similarly, two `Verifier`s are declared by simple functions (lambda expressions) which takes a value and returns `bool`. Verification phase is regarded as successful only when all `Verifier`s return `True`.

Each validation scheme is executed as follows.

1. Creates an instance of a validatable type (= *validated instance*).
2. Applies the `Converter` to an input value and obtains converted value.
3. Applies `Verifier`s to the converted value.
4. If both phase succeed, assigns the converted value to the validated instance as an attribute of the same name as the validatable attribute.

`validate_dict` is a function which applies every validation scheme of a validatable type to an input dictionary.

```
r = validate_dict(C, dict(a = "3"))
d = r.get()

assert type(d) == C
assert d.a == 3
```

`validate_dict` returns a `ValidationResult` object which contains validated instance and errors. In this case, as the input value can be converted by `int` and fulfills both verifications, converted value is assigned to an attribute of validated instance successfully.

### Error handling

Every kind of error in the validation scheme is repreesented with `ValidationFailure` object which can be accessed via `failures` attribute of `ValidationResult`. `failures` attribute gives `CompositeValidationFailure` which behaves as both dictionary of errors and an iterator of pairs of `ValidationPath` and an error. The former is useful to know whether the validation succeeds or not on a certain attribute, whereas the latter provides a way to traverse all errors in the validation scheme.

A `ValidationFailure` has a `name` attribute which corresponds to the name of `Converter` or `Verifier` (described below) which caused the error, that is, programmers can recognize the reason of the error via this attribute. `ValidationFailure` also has attributes `args` and `kwargs` which correspond to freezed arguments when `Converter` or `Verifier` is declared by using `functools.partial` as described below.

```
def lt3(x):
    return x < 3
def gt1(x):
    return x > 1

class C:
    a: v(int) = 0
    b: v(int, lt3) = 0
    c: v(int, lt3, gt1) = 0

r = validate_dict(C, dict(a = "a", b = "3", c = "1"))

assert "a" in r.failures
assert r.failures["a"].name == "int"
assert dict([(str(k), f.name) for k, f in r.failures]) == {"a": "int", "b": "lt3", "c": "gt1"}
```

`ValidationResult` provides a method `or_else`, which returns the validated instance if validation succeeded, otherwise invokes given function with the validation error. This feature is useful especially when the application is developed on a framework which has its own exception handling functionality.

```
def handle_error(e):
    raise e

d = r.or_else(handle_error)
```

### Requiring constraint

`+` operator lets a `Validator` require an input value and fail if the value is missing, `None` or considered to be *empty*. The error caused by this constraint is represented with `MissingFailure` whose name is `missing`.

```
class C:
    a: +v(int) = 0

r = validate_dict(C, dict())

assert r.failures["a"].name == "missing"
```

### Converter specifiers

As shown in next example, `Converter` can be declared by multiple styles besides by a function.

```
from functools import partial as p
from enum import Enum, auto

class D:
    a: v(int) = 0

class E(Enum):
    E1 = auto()
    E2 = auto()

class C:
    a: v(int) = 0
    b: v(p(int, base=2)) = 0
    c: v(("first", lambda x: x.split(",")[0])) = None
    d: v({D}) = None
    e: v(E) = E.E1

r = validate_dict(C, dict(a = "3", b = "101", c = "a,b,c", d = dict(a = "4"), e = "E2"))
d = r.get()

assert d.a == 3
assert d.b == 5
assert d.c == "a"
assert d.d.a == 4
assert d.e == E.E2
```

The `Converter` for `b` is declared with a callable object created by `functools.partial` with freezed arguments `base = 2`. Input value for `b` is considered as a string of binary number and converted to an integer value. If this `Converter` fails, the corresponding `ValidationError` has `kwargs` attribute which is a dictionary holding key value pairs of freezed keyword arguments, that is, `{"base": 2}`.

`c` uses a tuple of a string and a function as the specifier of `Converter`. This style sets the name of the `Converter` with the string explicitly. By default, the name of the `Converter` is set to the value of `__name__` attribute of the function, that is why the name of the `Converter` specified by `int` is `int`. Although this default naming strategy works fine for normal functions, it is not suitable for the use of lambda expression. The tuple style specifier should be used in such cases to handle error correctly.

`Converter` for `d` is specified by a set of another validatable type `D`. This style declares the nested validation on the attribute, that is, the input for `d` is also a dictionary like object and the attribute `d` should be assigned with `D`'s instance obtained as a result of validation scheme for `D`.

On `e`, `Converter` is specified by `Enum` type. Input value for `e` is converted to `E` by its name, that is, `lambda x: E[x]` is the equivalent function.

Additionally, by enclosing the specifier with `[]`, `Converter` considers the input as iterable values and applies converting function to each value in them. Next code will let you understand this behavior easily.

```
class C:
    a: v(int) = 0
    b: v([int]) = []

r = validate_dict(C, dict(a = "123", b = "123"))

assert r.get().a == 123
assert r.get().b == [1, 2, 3]
```

### Verifier specifiers

Similarly to `Converter`, there also are multiple declaration styles for `Verifier`. 

```
def lt3(x):
    return x < 3

def lt(x, threshold):
    return x < threshold

class C:
    a: v(int, lt3) = 0
    b: v(int, p(lt, threshold = 3))
    c: v(int, ("less_than_3", lambda x: x < 3)) = 0
    d: v([int], [lt3]) = []
```

`b` declares a `Verifier` which verifies an input by a partial function. Freezed arguments will be set to the attribute of `ValidationFailure` when this `Verifier` causes error. The name of `Verifier` for `c` is set to `less_than_3` because it is specified by a tuple. The `Verifier` of `d`, whose specifier is enclosed by `[]`, considers the input as iterable values and applies verification function to each value respectively.

### Undeclared items

This library just ignores items in input dictionary whose keys are not declared by any of validatable attribute. Those items remain in the `ValidationContext` which can be accessed via `context` attribute of the result. When the validatable type is nested, `ValidationContext` takes hierarchical form providing key access. Also, when nested type is validated in iterative context, index access is available. Next example shows ways to get undeclared items in various cases.

```
class D:
    d: v(int) = 0

class C:
    a: v(int) = 0
    b: v({D}) = None
    c: v([{D}]) = []

r = validate_dict(C, dict(a = "1", b = dict(d = "2", e = "a"), c = [dict(d = "3", e1 = "b"), dict(d = "4", e2 = "c")], d = "d"))
cxt = r.context

assert cxt.remainders == dict(d = "d")
assert cxt["b"].remainders == dict(e = "a")
assert cxt["c"].remainders == [dict(e1 = "b"), dict(e2 = "c")]
assert cxt["c"][0].remainders == dict(e1 = "b")
assert cxt["c"][1].remainders == dict(e2 = "c")
```

### Advanced error handling

Access to errors in `CompositeValidationFailure` gets a little more complicated when `Converter` or `Verifier` is declared to accept iterable values and when using nested validation. In such cases, errors are no longer flat because multiple errors can happen in an attribute. To get the error at iterative/nested validation, you should descend the `CompositeValidationFailure` by corresponding keys.

In the iteration context of `CompositeValidationFailure`, each iteration yields a pair of a `ValidationPath` and an error. `ValidationPath` contains the complete positional information of the error as a list of attribute name or index of iterable input. This object has its own string representation useful for debugging or any other purposes.

```
class D:
    b: v([int]) = []

class C:
    a: v([{D}]) = []

r = validate_dict(C, dict(a = [dict(b = "123"), dict(b = "45a"), dict(b = "789")]))
assert r.failures["a"][1]["b"][2].name == "int"

p, f = list(r.failures)[0]
assert str(p) == "a[1].b[2]"
assert list(p) == ["a", 1, "b", 2]
```

As shown in the above example, `CompositeValidationFailure` can give you the complete information why and where the validation failed. This feature enables flexible coding associated with validation errors, for example, you can generate hierarchical JSON response, insert error messages to suitable positions of HTML pages and control behaviors of application in detail according to the cause of errors.

## Flask support

This library supports `werkzeug.datastructures.MultiDict` which is used in [Flask](http://flask.pocoo.org/docs/1.0/) to store request forms and queries. In addition to `dict`, the instance of `MultiDict` can be an input of `Validator`.

In many web application frameworks, although form values and queries can associate multiple values with a single key, the request object tends to return a single value when accessed as a dictionary. To solve this difference between `dict` and request object, this library first checks the input is `MultiDict` or not and changes accessors according to the type of the input. Thus, you can give `request.form`, `request.args` and any other `MultiDict` values to `validate_dict`.
