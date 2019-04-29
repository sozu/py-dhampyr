# Python simple validator for dictionary-like objects

## Overview

This library provides data validation functionalities designed to be used for HTTP applications. Compared to other validation libraries, this library has following features.

- Validations are declared by annotations which is introduced in python 3.5.
- Each validation can be composed of simple functions including lambda expressions.
- Errors in validation scheme are represented with informative objects, not with just an error message.

## Installation

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

Every kind of `ValidationFailure` has a `name` attribute which corresponds to the name of `Converter` or `Verifier` (described below) where the error happens. Therefore, it enables programmers to recognize the reason of the error.

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

### Validator requiring input

`+` operator let a `Validator` requires an input value and fails if it does not exist. The error on this constraint is represented with `MissingFailure` whose name is `missing`.

```
class C:
    a: +v(int) = 0

r = validate_dict(C, dict())

assert r.failures["a"].name == "missing"
```

### Converter specifiers

As shown in next example, `Converter` can be declared by multiple styles besides by a function.

```
class D:
    a: v(int) = 0

class C:
    a: v(int) = 0
    b: v(("first", lambda x: x.split(",")[0])) = None
    c: v({D}) = None

r = validate_dict(C, dict(a = "3", b = "a,b,c", c = dict(a = "4")))
d = r.get()

assert d.a == 3
assert d.b == "a"
assert d.c.a = 4
```

`b` uses a tuple of a string and a function for the specifier of `Converter`. This style sets the name of the `Converter` with the string explicitly. By default, the name of the `Converter` described in error handling chapter is set to the value of `__name__` attribute of the function, that is why the name of the `Converter` specified by `int` is `int`. Although this default naming strategy works fine for normal functions, it is not suitable for the use of lambda expression. The tuple style specifier should be used in such cases to handle error correctly.

`Conterter` for `c` is specified by a set of another validatable type `D`. This style declares the nested validation on the attribute, that is, the input for `c` is also a dictionary like object and the attribute `c` should be assigned with `D`'s instance obtained from the result of validation for `D`.

Additionally, by enclosing the specifier with `[]`, `Converter` considers the input as iterable values and applies converting function to a value got in each iteration. Next code let you understand this behavior easily.

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

class C:
    a: v(int, lt3) = 0
    b: v(int, ("less_than_3", lambda x: x < 3)) = 0
    c: v([int], [lt3]) = []
```

The `Verifier` for `b` is declared by tuple which set the name of the `Verifier` to the first string, in this case `less_than_3`. By enclosing the specifier, `Verifier` considers the input as iterable values and applies verification function to each value respectively.

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