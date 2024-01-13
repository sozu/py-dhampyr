# Python simple validator for dictionary-like objects

## Overview

This library provides data validation functionalities designed for HTTP applications. Compared to other validation libraries, this library has following features.

- Validation schemes are declared like dataclass field specifier.
- Each validation scheme can be composed of simple functions including lambda expressions.
- Errors in validations are represented with informative objects, not with just error messages.

## Installation

This library requires python 3.6 or higher.

```
$ pip install dhampyr==1.0-a3
```

## Tutorial

### Declaration of validation scheme

The module `dhampyr` exports a function `v` which creates a `Validator`. This function is designed to be used like *dataclass* field specifier.

```
from dhampyr import *

class C:
    a: int = +v(..., lambda x: x < 5, lambda x: x > 2, default=0)
```

`v` can be used as the metadata in `Annotated` annotation. In this case, the value assigned to the attribute becomes a default value.

```
from dhampyr import *
from typing import Annotated

class C:
    a: Annotated[int, +v(..., lambda x: x < 5, lambda x: x > 2)] = 0
```

`v` has additional keyword arguments. For example, `alias` specifies the corresponding key in the input explicitly, Arguments of *dataclass* field specifier such as `default` or `default_factory` are also available. See API document to know all possible arguments.

The validation scheme starts with the declaration of *validatable type* like `C` and an input dict-like object. Each key-value pair in the input becomes an input value to an attribute whose name (or specified alias) matches to the key. For each attribute, three phases run in order.

1. Checks whether the input value exists or not. `Requirement` setting of the `Validator` determines the behavior according to the existence.
2. Converts the input value by `Converter` which by default is the annotated type of the attribute. Conversion function can be set in the first argument of `v` .
3. Converted value is verified by `Verifier`s given in positional arguments in `v` . A function which takes a converted value and returns `bool` is the most simple one representing `Verifier` .

The scheme finally returns an instance of the *validatable type* where values passing those phases are assigned to the attributes.

`validate_dict` is the function which runs the scheme.

```
r = validate_dict(C, dict(a="3"))
d = r.get()

assert bool(r)
assert type(d) == C
assert d.a == 3
```

`validate_dict` returns a `ValidationResult` object which contains validated instance and errors. It also is available in boolean context to check if the scheme has succeeded or not.

### Composite validation

Nested validatable types are available without any special declaration.

```
from dhampyr import *

class D:
    a: int = v()

class C:
    a: D = v()

r = validate_dict(C, dict(a=dict(a="3")))
d = r.get()

assert type(d) == C
assert type(d.a) == D
assert d.a.a == 3
```

Each value in iterable input are converted and verified respectively. In this case, `Coverter` and `Verifier`s should be declared as a `list` which includes their specifier. Nested type declaration are available as well.

```
class D:
    a: int = v()

class C:
    a: list[int] = v(..., [lambda x: x > 0])
    b: list[D] = v()

r = validate_dict(C, dict(a=[1, 2, 3], b=[dict(a=4), dict(a=5), dict(a=6)]))
d = r.get()

assert d.a == [1, 2, 3]
assert [b.a for b in d.b] == [4, 5, 6]
```

### Error handling

Every kind of error in the validation scheme is repreesented with `ValidationFailure` object which can be accessed via `failures` attribute of `ValidationResult`. This attributes is always not `None` and tells where and what kind of error happened in an invocation of `validate_dict`.

- Evaluate `ValidationResult` as `bool` to know every validation scheme succeeded or not.
- `len` returns the number of erroneous keys (on the root validated instance, nested errors are not counted).
- `in` operator is available to know whether errors happened at the specific key.
- Access with Square bracket (`[]`) returns the error at the key, or `None` if no error.
- Iteration yields all errors including nested ones in depth-first traversal order.

```
from dhampyr import *

def lt3(x):
    return x < 3
def gt1(x):
    return x > 1

class C:
    a: int = v(default=0)
    b: int = v(..., lt3, default=0)
    c: int = v(..., lt3, gt1, default=0)

r = validate_dict(C, dict(a="a", b="3", c="1"))

assert bool(r) is False
assert len(r.failures) == 3
assert "a" in r.failures
assert r.failures["a"].name == "int"
assert dict([(str(k), f.name) for k, f in r.failures]) == {"a": "int", "b": "lt3", "c": "gt1"}
```

Each `ValidationFailure` has a `name` attribute which corresponds to the name of `Converter` or `Verifier` causing the error. You can recognize the cause of each error by this attribute. Basically the name is set to `__name__` of the function used to declare them, but there are various ways to set the name explicitly as described below.

Next table shows predefined names.

|name|cause|
|:---|:---|
|`malformed`|Input value was not dictionary-like.|
|`missing`|The key did not exist in input dictionary.|
|`null`|Input value was `None`.|
|`empty`|Input value was determined to be *empty*.|

Composite validation makes errors hierarchical. You should use *path* composed of string keys and numerical indexes. To get an error at the specific position, apply path components with square bracket in order. On the other hand, iteration over `ValidationFailure` yields pairs of path and error in depth-first traversal order, where the path is represented with `ValidationPath` object. It provides intuitive textual representation like `a.b[0].c[0].d`.

```
from dhampyr import *

class D:
    b: list[int] = v(default_factory=list)

class C:
    a: list[D] = v(default_factory=list)

r = validate_dict(C, dict(a=[dict(b="123"), dict(b="45a"), dict(b="789")]))

assert r.failures["a"][1]["b"][2].name == "int"
assert [(str(p), list(p)) for p, f in r.failures] == [("a[1].b[2]", ["a", 1, "b", 2])]
```

As shown in the above example, developers can get complete information why and where the validation failed. This feature enables flexible and user-oriented error handling.

Besides, `ValidationResult` provides a method `or_else`, which returns the validated instance if validation succeeded, otherwise invokes given function with the validation error.

```
def handle_error(e):
    raise e

d = r.or_else(handle_error)
```

### Requirement phase

`+` operator lets a `Validator` fail if the input value is missing, `None` or considered to be *empty*.

```
from dhampyr import *

class C:
    a: int = +v(default=0)

r = validate_dict(C, dict())

assert r.failures["a"].name == "missing"
```

By default, The *empty* condition is applied to the input whose type is `str` `bytes` `list` or `set` . The input is considered empty when its length (returned by `len` ) is 0.  You can add conditions for other types by configuration interfaces.

Although all of those 3 conditions must be satisfied by default, we sometimes need to change the behavior against each condition respectively. This can be done by bitwise operator and condition specifiers.

|operator|behavior|
|:---|:---|
|`&`|Let validator fail when the next condition is not satisfied.|
|`/`|Let validator continue to subsequent phases even when the next condition is not satisfied.|
|`^`|Let validator skip subsequent phases without failure when the next condition is not satisfied.|

Conditions for `None` and *empty* are specified with `None` and `...` respectively.

```
def longer5(x):
    return len(x) > 5

class C:
    a: str = +v(default="a")
    b: str = +v(..., longer5, default="b") ^ None
    c: str = +v(..., longer5, default="c") / ...
    d: str = +v(..., longer5, default="d") ^ ...

r = validate_dict(C, dict(a="", b=None, c="", d=""))
d = r.get()

assert r.failures["a"].name == "empty"
assert r.failures["b"] is None
assert r.failures["c"].name == "longer5"
assert r.failures["d"] is None
assert d.b == "b"
assert d.d == "d"
```

The example shows that validation on `c` failed at verification phase because `/` continues validation scheme to empty input.

### Conversion phase

Conversion phase is done by a `Conveter` which can be declared by multiple styles.

|specifier|example|name|behavior|
|:---|:---|:---|:---|
|function or type|`int`|name of the function or type.|Invoke the function or constructor of the type.|
|`functools.partial`|`partial(int, base=2)`|name of base function|Invoke the `partial` object.|
|tuple of `str` and another specifier|`("integer", int)`|first element|Same as the specifier at second element.|
|`enum.Enum` type|`E`|name of the type|Get an enum value whose name matches the input.|

```
from functools import partial as p
from enum import Enum, auto

class D:
    a: int = v(default=0)

class E(Enum):
    E1 = auto()
    E2 = auto()

class C:
    a: int = v(default=0)
    b: int = v(p(int, base=2), default=0)
    c: str = v(("first", lambda x: x.split(",")[0]), default="")
    d: D = v()
    e: E = v(default=E.E1)

r = validate_dict(C, dict(a = "3", b = "101", c = "a,b,c", d = dict(a = "4"), e = "E2"))
d = r.get()

assert d.a == 3
assert d.b == 5
assert d.c == "a"
assert d.d.a == 4
assert d.e == E.E2
```

Freezed arguments of `partial` function (for `b`, `base=2`) are passed to error object when the converter fails. They can be obtained via `args` or `kwargs` attribute of `ValidationFailure` for the use of such as error message creation.

Tuple style shown at `c` is available to give an explicit name to a `Converter`, especially for the case using lambda expression. 

`Enum` type is also a type but it is treated in another way. The `Converter` invokes `__getitem__` class method to find an enum value by its name. Be sure that this method is case sensitive.

As described in composite validation section, the `Converter` of iterable attribute interprets the input as iterable values and convert each value respectively, which is clarified in following code.

```
class C:
    a: int = v(default=0)
    b: list[int] = v(default_factory=list)

r = validate_dict(C, dict(a="123", b="123"))

assert r.get().a == 123
assert r.get().b == [1, 2, 3]
```

### Verification phase

Similar to `Converter`, there also are multiple declaration styles for `Verifier`. 

|specifier|example|name|behavior|
|:---|:---|:---|:---|
|function or type|`lt3`|name of the function or type.|Invoke the function or constructor of the type.|
|`functools.partial`|`partial(lt, threshold = 3)`|name of base function|Invoke the `partial` object.|
|tuple of `str` and another specifier|`("less_than_3", lt3)`|first element|Same as the specifier at second element.|

```
def lt3(x):
    return x < 3

def lt(x, threshold):
    return x < threshold

class C:
    a: int = v(..., lt3, default=0)
    b: int = v(..., p(lt, threshold = 3))
    c: int = v(..., ("less_than_3", lambda x: x < 3), default=0) = 0
    d: list[int] = v(..., [lt3], lambda x: len(x) < 5, default_factory=list)

r = validate_dict(C, dict(a=3, b=3, c=3, d=[1, 1, 1, 1, 1]))
assert {str(p) for p, _ in r.failures} == {"a", "b", "c", "d"}

r = validate_dict(C, dict(a=2, b=2, c=2, d=[1, 1, 1, 1]))
assert {str(p) for p, _ in r.failures} == {}
```

These styles work similarly to equivalent style of `Converter` specifier. As for list expression in `d`, second `Verifier` is not enclosed by `[]`, so that it takes a list of converted values, not each value in the list. Therefore it fails when the length of the input list is not shorter than `5`.

### Verifier method

Validatable type is able to contain *verifier method*s which are invoked at the end of verification phase. `@validate()` decorator marks a method as *verifier method*. Be aware that the bracket is necessary if no arguments are given.

This decorator takes keyword arguments which represent dependencies determining whether the verifier method will be invoked. Each key of argument denotes an attribute name and the value is a boolean. If the value is `True`, the attribute has *positive dependency*, otherwise *negative dependency*.

- If no arguments are given, the verifier method is invoked only when all validations on attributes succeeded.
- If validations on all of attributes having positive dependency succeeded, the verifier method is invoked even when there are failed validations on other attributes.
- If validations on attributes having negative dependency failed, the verifier method is not invoked even when positive dependencies are satisfied.

```
class C:
    a: int = +v()
    b: int = +v()
    c: int = +v()

    @validate()
    def v1(self):
        return self.a > 0

    @validate(a=True)
    def v2(self):
        return self.a > 0

    @validate(a=True, b=False)
    def v3(self):
        return self.a > 0

r = validate_dict(C, dict(a="0", b="0", c="0"))
assert {str(p) for p, _ in r.failures} == {"v1", "v2", "v3"}

r = validate_dict(C, dict(a="0", b="a", c="a"))
assert {str(p) for p, _ in r.failures} == {"b", "c", "v2"}
assert r.failures["v2"].name == "v2"

r = validate_dict(C, dict(a="0", b="0", c="a"))
assert {str(p) for p, _ in r.failures} == {"c", "v2", "v3"}
assert r.failures["v3"].name == "v3"
```

Above code shows examples of verifier methods with various dependencies.

`v1` has no dependencies so that it is executed only when validations of all attribute succeeded. `v2` is executed in every case because validation results on `b` and `c` have no concern. As for `v3` which has negative dependency on `b`, it is not executed in second case where the validation on `b` fails.

As shown in the code, an error caused by a verifier method is stored on the path of its name, and `name` of the error is also its name.

### Variable

Verifiers can be declared by any kind of `callable`s such as normal functions and lambda expressions. However, it is sometimes bothersome to define functions explicitly, and, lambda expression of python is somewhat verbose. To make things better in that point, `dhampyr` package exports a variable object `x`.

`x` is a variable which will be replaced with the input value, and various operations applied to it are evaluated lazily in verification phase.

```
class C:
    a: int = v(..., x > 0)
    b: str = v(..., x.len % 2 == 0)
    c: int = v(..., x.in_(1, 2, 3))
    d: int = v(..., x.not_.in_(1, 2, 3))

r = validate_dict(C, dict(a=0, b="abc", c=0, d=1))

assert r.failures["a"].name == "x.gt"
assert r.failures["a"].kwargs == {"gt.value": 0}
assert r.failures["b"].name == "x.len.mod"
assert r.failures["b"].kwargs == {"mod.value": 2, "eq.value": 0}
assert r.failures["c"].name == "x.in"
assert r.failures["c"].kwargs == {"value": (1, 2, 3)}
assert r.failures["d"].name == "x.not.in"
assert r.failures["d"].kwargs == {"value": (1, 2, 3)}
```

`len` is a property which applies builtin `len` function to the value, which is introduced because python specification restricts that `__len__` returns a value of `int`. `not_` should be prepended to other operations and it inverts their result.

When the verifier fails, it exposes the error whose name is concatenated operation names and which contains parameters of operations in `kwargs` attribute.

**Comparison operators**

|operator|name|remarks|
|:---|:---|:---|
|`<`|`lt`||
|`<=`|`le`||
|`==`|`eq`||
|`!=`|`ne`||
|`>=`|`ge`||
|`>`|`gt`||

**Mathematical binary operators**

|operator|name|remarks|
|:---|:---|:---|
|`+`|`add`||
|`-`|`sub`||
|`*`|`mul`|
|`@`|`matmal`||
|`/`|`truediv`||
|`//`|`floordiv`||
|`%`|`mod`||
|`**`|`pow`||

**Mathematical unary operators**

|operator|name|remarks|
|:---|:---|:---|
|`-`|`neg`|
|`+`|`pos`|
|`~`|`invert`|
|`<<`|`lshift`||
|`>>`|`rshift`||
|`&`|`and`||
|`^`|`xor`||
|`\|`|`or`||

**Mathematical functions**

|function|name|remarks|
|:---|:---|:---|
|`divmod()`|`divmod`|Builtin function.|
|`pow()`|`pow`|Builtin function.|
|`abs()`|`abs`|Builtin function.|
|`round()`|`round`|Builtin function.|
|`math.trunc()`|`trunc`|From `math` package.|
|`math.floor()`|`floor`|From `math` package.|
|`math.ceil()`|`ceil`|From `math` package.|

**Attributes and methods**

|attribute|name|remarks|
|:---|:---|:---|
|`.not_`|`not`|Invert results of subsequent operations.|
|`.len`|`len`|Length of the input value.|
|`.inv`|`inv`|Invert result of previous operation.|
|`.has()`|`has`|Contains argument value or not?|
|`.in_()`|`in`|Be contained in argument values?|
|`.x`|`@x`|Return `x` attribute.|
|`[x]`|`[x]`|Return value on index `x`.|

Because this feature is added for the purpose of simplicity and intuitivity, it has some limitations listed below. Do not use `x` in these situations.

- `x` can not appear multiple times in an equation.
- Logical combinations, which are expressed by operators such as `or`, are not available.
- When using the same operator multiple times, their parameters in the error object are overwritten by later one's.

### Validation context

`validate_dict` takes `ValidationContext` optionally. Features of this object are listed below.

- Arbitrary values can be set to its attributes and they are available in conversion or verification function.
- Keeps key-value pairs which exist in the input but are not used in the validation scheme.
- Provides an interface to modify configurations which are effective under certain path.

First of all, `ValidationContext` is the object used at each validation path. The state of the context can be set independently beforehand and the state propagates to descendant paths. Next example show how it works.

```
context = ValidationContext()

context["a"].put(value=1)
context["b"].put(value=2)
context["a"][0].put(value=3)

def gt(x, cxt:ValidationContext):
    return x > cxt.value

class C:
    a: list[int] = v(..., [gt])
    b: int = v(..., gt)

r = validate_dict(C, dict(a=["2", "2"], b="2"), context)

assert {str(p) for p, _ in r.failures} == {"a[0]", "b"}
```

- Each value for `a` is verified by `gt` which checks the input is greater than `cxt.value` which is set to `1` by `put` .
- Only the first item in `a` fails because `cxt.value` at `a[0]` is set to `3` .
- As for `b` , verification fails because `cxt.value` is `2` .

In order to use the context object in `Verifier` function, it should be declared to have an argument which is annotated with `ValidationContext` like `lt`. Context object is given only when the signature satisfies the format, which is the same for `Conterter` function as well. Because the context is created on every path, the argument is always not `None` but the access to unset attribute raises `AttributeError`.

### Undeclared keys

`validate_dict` just ignores items in input dictionary whose keys are not declared on the validatable type. Instead, they are kept in `remainders` of `ValidationContext` after the validation. The context can be obtained from `ValidationResult` via `context` attribute even if you don't give a context explicitly. To get the undeclared values in nested types, use hierarchical access to the context.

```
class D:
    d: int = v(default=0)

class C:
    a: int = v(default=0) = 0
    b: Optional[D] = v(default=None)
    c: list[D] = v(default_factory=list)

r = validate_dict(C, dict(a="1", b=dict(d="2", e="a"), c=[dict(d="3", e1="b"), dict(d="4", e2="c")], d="d"))
cxt = r.context

assert cxt.remainders == dict(d="d")
assert cxt["b"].remainders == dict(e="a")
assert cxt["c"][0].remainders == dict(e1="b")
assert cxt["c"][1].remainders == dict(e2="c")
```

### Configurations

There are some configuration options which control the behavior of validations. Global configuration can be obtained by `default_config` . Meanwhile, configuration used at each path can be set via `configure` of `ValidationContext` .

Due to the configuration object is also a context manager, it can be changed locally by using *with* block.

At runtime, `config` attribute of `ValidationContext` exposes configurations effective on the path.

```
with default_config() as cfg:
    cfg.name = "modified"
    cfg.skip_null = False

    assert default_config().name is "modified"
    assert default_config().skip_null is False

assert default_config().name is "default"
assert default_config().skip_null is True
```

See the documentation of `ValidationConfiguration` to know all possible configurable parameters.