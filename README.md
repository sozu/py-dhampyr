# Python simple validator for dictionary-like objects

## Overview

This library provides data validation functionalities designed to be used for HTTP applications. Compared to other validation libraries, this library has following features.

- Validations are declared by annotations which is introduced in python 3.5.
- Each validation can be composed of simple functions including lambda expressions.
- Errors in validation scheme are represented with informative objects, not with just an error message.

## Installation

This library needs python 3.6 or higher.

```
$ pip install dhampyr
```

## Tutorial

### Declaration of validation scheme

The module `dhampyr.validator` exports a function `v` used for the declaration of a `Validator`. This function is designed to be used in annotation context of class attribute.

```
from dhampyr.validator import *

class C:
    a: v(int, lambda x: x < 5, lambda x: x > 2) = 0
```

In above code, `C` is considered as a *validatable* type and `a` is a *validatable* attribute. While you can use any name for validatable type, the name of each validatable attribute corresponds to the key by which a value applied to the declared `Validator` is obtained from input dictionary.

The validation scheme of this library is composed of two phases, type conversion by `Converter` and value verifications by `Verifier`s. The first argument in `v` specifies the `Converter` and each of following optional arguments specifies `Verifier`. 

This code shows the simplest but intrinsic declaration style of `Converter`, just a function `int`. Every `Converter` converts an input data with a function like `int` which takes a `str` and returns an `int`, and then, the converted value is propagated to verification phase and finally assigned to an attribute of validated instance. Similar to `Converter`, 2 `Verifier`s are declared by simple functions (lambda expressions) which takes a value and returns `bool`. Validation is regarded as successful only when all `Verifier`s return `True`.

`validate_dict` is a function which applies validation scheme to an input dictionary.

```
r = validate_dict(C, dict(a = "3"))
d = r.get()

assert type(d) == C
assert d.a == 3
```

`validate_dict` returns a `ValidationResult` object which contains validated instance of validatable type and errors. In this case, as the input value can be converted by `int` and fulfills both verifications, converted value is assigned to an attribute of validated instance successfully.

### Error handling

Every error in the validation scheme is repreesented with `ValidationFailure` object which can be accessed via `failures` attribute of `ValidationResult`. `failures` attribute gives `CompositeValidationFailure` which behaves as both dictionary of errors and iterator of pairs of `ValidationPath` and error. The former is useful to know whether the validation succeeds or not on an attribute, and the latter provides a way to collect all errors in the validation scheme.

Every kind of `ValidationFailure` has a `name` attribute which corresponds to the name of `Converter` or `Verifier` (described below) where the error happens. Therefore, it enables programmers to recognize the reason of the error. `ValidationFailure` also has attributes `args` and `kwargs` which correspond to freezed arguments when `Converter` or `Verifier` is declared by using `functools.partial` as described below.

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

`ValidationResult` provides a method `or_else`, which returns the validated instance if validation succeeded, otherwise invokes a function with the validation error. This feature is useful especially when the application is developed on a framework which has its own exception handling functionalily.

```
def handle_error(e):
    raise e

d = r.or_else(handle_error)
```

### Validator requiring input

`+` operator lets a `Validator` requires an input value and fails if it does not exist. The error on this constraint is represented with `MissingFailure` whose name is `missing`.

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

class D:
    a: v(int) = 0

class C:
    a: v(int) = 0
    b: v(p(int, base=2)) = 0
    c: v(("first", lambda x: x.split(",")[0])) = None
    d: v({D}) = None

r = validate_dict(C, dict(a = "3", b = "101", c = "a,b,c", d = dict(a = "4")))
d = r.get()

assert d.a == 3
assert d.b == 5
assert d.c == "a"
assert d.d.a = 4
```

Function created by `functools.partial` is available as shown in `Converter` of `b`. Freezed arguments, in this case `base = 2`, are available in the error handling.

`c` uses a tuple of a string and a function for the specifier of `Converter`. This style sets the name of the `Converter` with the string explicitly. By default, the name of the `Converter` described in error handling chapter is set to the value of `__name__` attribute of the function, that is why the name of the `Converter` specified by `int` is `int`. Although this default naming strategy works fine for normal functions, it is not suitable for the use of lambda expression. The tuple style specifier should be used in such cases to handle error correctly.

`Converter` for `d` is specified by a set of another validatable type `D`. This style declares the nested validation on the attribute, that is, the input for `d` is also a dictionary like object and the attribute `d` should be assigned with `D`'s instance obtained from the result of validation for `D`.

Additionally, by enclosing the specifier with `[]`, `Converter` considers the input as iterable values and applies converting function to a value got in each iteration. Next code lets you understand this behavior easily.

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

`Verifier` can be declared by using `functools.partial` and freezed arguments will be set to `ValidationFailure` attributes when this `Verifier` causes error.

The `Verifier` for `c` is declared by tuple which set the name of the `Verifier` to the first string, in this case `less_than_3`. By enclosing the specifier, `Verifier` considers the input as iterable values and applies verification function to each value respectively.

### Advanced error handling

Access to errors in `CompositeValidationFailure` gets a little more complicated when using `Converter` or `Verifier` for iterable values and when using nested validation. In such cases, errors are no longer flat because multiple errors can happen in an attribute. To get the error at iterative/nested validation, you should descend the `CompositeValidationFailure` by corresponding keys.

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

As shown in the above example, `CompositeValidationFailure` can give you the complete information why and where the validation failed. This feature enables flexible conding associated with validation errors, for example, you can generate hierarchical JSON response, insert error messages to suitable positions of HTML pages and control behaviors of application in detail according to the cause of errors.

## Flask support

This library supports `werkzeug.datastructures.MultiDict` which is used in [Flask](http://flask.pocoo.org/docs/1.0/) to store request forms and queries. In addition to `dict`, the instance of `MultiDict` can be an input of `Validator`.

In many web application frameworks, although form values and queries can associate multiple values with a single key, the request object tends to return a single value when accessed as a dictionary. To solve this inconsitency between `dict` and request object, this library first checks the input is `MultiDict` or not and change accessors according to the type of the input. Thus, you can give `request.form`, `request.args` and any other `MultiDict` values to `validate_dict`.
