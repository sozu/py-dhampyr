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

The module `dhampyr` exports a function `v` which creates a `Validator`. This function is designed to be used in annotation context of a class attribute.

```
from dhampyr import *

class C:
    a: +v(int, lambda x: x < 5, lambda x: x > 2) = 0
```

In above code, `C` is considered as a *validatable type* and `a` is a *validatable attribute*. While you can use any name for validatable type, the name of each validatable attribute corresponds to the key in input dictionary which is associated with a value the `Validator` will be applied to.

A validation scheme of this library is composed of three phases, existence check by `Requirement`, type conversion by `Converter` and value verifications by `Verifier`s. The first argument in `v` specifies the `Converter` and each of following optional arguments specifies `Verifier`. As described below, prepended `+` operator specifies the validator requires that the input value exists.

This code shows the simplest but intrinsic declaration style of `Converter`, just a function `int`. Similarly, two `Verifier`s are declared by simple functions (lambda expressions) which takes a value and returns `bool`. Verification phase is regarded as successful only when all `Verifier`s return `True`.

Each validation scheme is executed as follows.

1. Creates an instance of a validatable type (*validated instance*).
2. Applies the `Requirement` to check the existence of input value (*requirement phase*).
3. Applies the `Converter` to an input value and obtains converted value (*conversion phase*).
4. Applies `Verifier`s to the converted value (*verification phase*).
5. If all phases succeed, assigns the converted value to the validated instance as an attribute of the same name as the validatable attribute.

`validate_dict` is a function which applies every validation scheme of a validatable type to an input dictionary.

```
r = validate_dict(C, dict(a = "3"))
d = r.get()

assert type(d) == C
assert d.a == 3
```

`validate_dict` returns a `ValidationResult` object which contains validated instance and errors. In this case, as the input value can be converted by `int` and satisfies both verifications, converted value is assigned to an attribute of validated instance successfully.

`v` takes additional keyword argument `key` whose value is used as the key in input dictionary instead of attribute name. Keys containing a character which is not available in attribute name are also dealt with by this feature. Be aware that this key is used only when extracting a value from the input dictionary, thereby it will never be exposed in the result of validation such as the path of failure which is described below.

### Composite validation

Nested validatable types are able to be validated by declaring `Converter` with `set` including a child type.

```
from dhampyr import *

class D:
    a: v(int)

class C:
    a: v({D})

r = validate_dict(C, dict(a = dict(a = "3")))
d = r.get()

assert type(d) == C
assert type(d.a) == D
assert d.a.a == 3
```

Each value in iterable input can be converted and verified respectively. In this case, `Coverter` and `Verifier`s should be declared as a `list` which includes their specifier. Nested type declaration are available as well.

```
class D:
    a: v(int)

class C:
    a: v([int], [lambda x: x > 0])
    b: v([{D}])

r = validate_dict(C, dict(a = [1, 2, 3], b = [dict(a = 4), dict(a = 5), dict(a = 6)]))
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
    a: v(int) = 0
    b: v(int, lt3) = 0
    c: v(int, lt3, gt1) = 0

r = validate_dict(C, dict(a = "a", b = "3", c = "1"))

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
    b: v([int]) = []

class C:
    a: v([{D}]) = []

r = validate_dict(C, dict(a = [dict(b = "123"), dict(b = "45a"), dict(b = "789")]))

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

`+` operator lets a `Validator` fail if the input value is missing, `None` or determined to be *empty*.

```
from dhampyr import *

class C:
    a: +v(int) = 0

r = validate_dict(C, dict())

assert r.failures["a"].name == "missing"
```

By default, The *empty* condition is applied only to the input whose type is `str` or `bytes`. For both types, whether the length of the input is not 0 is checked. You can add conditions associated with types by configuration interfaces.

Although all of those 3 conditions must be satisfied by default, we sometimes need to change the behavior against each condition respectively. This can be done by bitwise operator and condition specifiers.

|operator|behavior|
|:---|:---|
|`&`|Let validator fail when the next condition is not satisfied.|
|`\|`|Let validator continue to subsequent phases even when the next condition is not satisfied.|
|`^`|Let validator skip subsequent phases without failure when the next condition is not satisfied.|

Conditions for `None` and *empty* are specified with `None` and `...` respectively.

```
def longer5(x):
    return len(x) > 5

class C:
    a: +v(str) = "a"
    b: +v(str, longer5) ^ None = "b"
    c: +v(str, longer5) | ... = "c"
    d: +v(str, longer5) ^ ... = "d"

r = validate_dict(C, dict(a = "", b = None, c = "", d = ""))
d = r.get()

assert r.failures["a"].name == "empty"
assert r.failures["b"] is None
assert r.failures["c"].name == "longer5"
assert r.failures["d"] is None
assert d.b == "b"
assert d.d == "d"
```

Validation on `c` fails at verification phase because `|` continues validation scheme to empty input.

### Conversion phase

Conversion phase is done by a `Conveter` which can be declared by multiple styles. In any style, the input values is treated as an argument.

|specifier|example|name|behavior|
|:---|:---|:---|:---|
|function or type|`int`|name of the function or type.|Invoke the function or constructor of the type.|
|`functools.partial`|`partial(int, base=2)`|name of base function|Invoke the `partial` object.|
|tuple of `str` and another specifier|`("integer", int)`|first element|Same as the specifier at second element.|
|`enum.Enum` type|`E`|name of the type|Get an enum value whose name matches the input.|
|`set` of child type|`{D}`|name of the type|Invoke `validate_dict` recursively. See nested validation.|

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

Freezed arguments of `partial` function (for `b`, `base = 2`) are passed to error object when the converter fails. They can be obtained via `args` or `kwargs` attribute of `ValidationFailure`. They are for example needed to construct error message.

Tuple style shown at `c` is available to give an explicit name to a `Converter`, especially for the case using lambda expression. 

`Enum` type is also a type but it is treated in another way. The `Converter` invokes `__getitem__` class method to find an enum value by its name. Be sure that this method is case sensitive.

As described in composite validation section, enclosing the specifier with `[]` let `Converter` consider input as iterable values and convert each value respectively. Next code will let you understand this behavior easily.

```
class C:
    a: v(int) = 0
    b: v([int]) = []

r = validate_dict(C, dict(a = "123", b = "123"))

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
    a: v(int, lt3) = 0
    b: v(int, p(lt, threshold = 3))
    c: v(int, ("less_than_3", lambda x: x < 3)) = 0
    d: v([int], [lt3], lambda x: len(x) < 5) = []

r = validate_dict(C, dict(a = 3, b = 3, c = 3, d = [1, 1, 1, 1, 1]))
assert {str(p) for p, _ in r.failures} == {"a", "b", "c", "d"}

r = validate_dict(C, dict(a = 2, b = 2, c = 2, d = [1, 1, 1, 1]))
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
    a: +v(int)
    b: +v(int)
    c: +v(int)

    @validate()
    def v1(self):
        return self.a > 0

    @validate(a=True)
    def v2(self):
        return self.a > 0

    @validate(a=True, b=False)
    def v3(self):
        return self.a > 0

r = validate_dict(C, dict(a = "0", b = "0", c = "0"))
assert {str(p) for p, _ in r.failures} == {"v1", "v2", "v3"}

r = validate_dict(C, dict(a = "0", b = "a", c = "a"))
assert {str(p) for p, _ in r.failures} == {"b", "c", "v2"}
assert r.failures["v2"].name == "v2"

r = validate_dict(C, dict(a = "0", b = "0", c = "a"))
assert {str(p) for p, _ in r.failures} == {"c", "v2", "v3"}
assert r.failures["v3"].name == "v3"
```

Above code shows examples of verifier methods with various dependencies.

`v1` has no dependencies so that it is executed only when validations of all attribute succeeded. `v2` is executed in every case because validation results on `b` and `c` have no concern. As for `v3` which has negative dependency on `b`, it is not executed in second case where the validation on `b` fails.

As shown in the code, an error caused by a verifier method is stored on the path of its name, and `name` of the error is also its name.

### Variable

*experimental*

Verifiers can be declared by any kind of `callable`s such as normal functions and lambda expressions. However, it is sometimes bothersome to define functions explicitly, and, lambda expression of python is somewhat verbose. To make things better in that point, `dhampyr` package exports a variable object `x`.

`x` is a variable which will be replaced with the input value, and various operations applied to it are evaluated lazily in verification phase.

```
class C:
    a: v(int, x > 0)
    b: v(str, x.len % 2 == 0)
    c: v(int, x.in_(1, 2, 3))
    d: v(int, x.not_.in_(1, 2, 3))

r = validate_dict(C, dict(a = 0, b = "abc", c = 0, d = 1))

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

`validate_dict` takes `ValidationContext` at the optional third argument. Functionalities of this object are listed below.

- Stores object on its attributes of arbitrary names.
- Stores key-value pairs in input dictionary to which validation schemes are not applied.
- Provides an interface to modify configurations which are effective under certain path.

Here describes the overview of `ValidationContext` and the first functionality as others are described in following sections.

`ValidationContext` instance is created at every path where `Validator` works, that is, root, each key of dictionary, each index of iterable value and each nested type. The instances make hierarchical structure providing bracket access like error object. Features of the context are:

- Descendant context is created when it is accessed even before validation.
- Each context refers parent context and inherits its attributes spontaneously.
- Settings of a context affect validations only on its path and descendant paths.

```
context = ValidationContext()

context["a"].put(value = 1)
context["b"].put(value = 2)
context["a"][0].put(value = 3)

def lt(x, cxt:ValidationContext):
    return x > cxt.value

class C:
    a: v([int], [lt])
    b: v(int, lt)

r = validate_dict(C, dict(a = ["2", "2"], b = "2"), context)

assert {str(p) for p, _ in r.failures} == {"a[0]", "b"}
```

In above code, every value is verified the same function `lt` but the attribute `value` of context is set to different each other on every path. `put` is the method which sets values to attributes, where each pair of keyword arguments corresponds the name and value of an attribute. As a result, `a[0]` compares input value to `3` which is explicitly set to the path whereas `a[1]` uses `1` which is inherited from setting on `a`.

In order to use the context object in `Verifier` function, it should be declared to have an argument which is annotated with `ValidationContext` like `lt`. Context object is given only when the signature satisfies the format, which is the same for `Conterter` function as well. Because the context is created on every path, the argument is always not `None` but the access to unset attribute raises `AttributeError`.

### Undeclared keys

`validate_dict` just ignores items in input dictionary whose keys are not declared on the validatable type. Instead, they remain at `remainders` attribute of `ValidationContext`, which can be accessed via `context` attribute of returned value even if you don't give a context explicitly. To get the undeclared values in nested types, use hierarchical access to the context.

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
assert cxt["c"][0].remainders == dict(e1 = "b")
assert cxt["c"][1].remainders == dict(e2 = "c")
```

### Configurations

There are some configuration options which control the behavior of validations. Next list shows 3 kinds of configuration styles, where the former one has always higher priority.

- Runtime configurations in `ValidationContext` set by `configure` method.
    - Similar to context attributes, configurations are inheited as well.
- Static configurations on the validatable type declared by `dhampyr` decorator.
    - When nested, the validation of child type is affected by configurations declared on enclosing type.
- Global default configurations which can be modified by `dhampyr` function.

At runtime, `config` attribute of `ValidationContext` exposes configurations effective on the path.

```
with dhampyr() as cfg:
    cfg.name = "global"
    cfg.join_on_fail = False

def add_name(x, cxt:ValidationContext):
    return f"{x}.{cxt.config.name}"

@dhampyr(name="static", join_on_fail=False)
class D:
    a: v(add_name)

class C:
    a: v(add_name)
    b: v({D})
    c: v(add_name)

context = ValidationContext()
context["c"].configure(name="runtime", join_on_fail=False)

d = validate_dict(C, dict(a = "a", b = dict(a = "b"), c = "c"), context).get()

assert d.a == "a.global"
assert d.b.a == "b.static"
assert d.c == "c.runtime"
```

Available configuration parameters are listed below:

- `name`
    - type: `str`
    - default: `"default"`
    - description:
        - The name of this configuration.
        - This configuration has no effect on validation. Use for debugging purpose etc.

- `skip_null` / `skip_empty`
    - type: `bool`
    - default: `True`
    - phase: Requirement
    - description:
        - Determines whether `v` validator (no `+`) skips subsequent phases when the input value is `None` or *empty value*.

- `allow_null` / `allow_empty`
    - type: `bool`
    - default: `False`
    - phase: Requirement
    - description:
        - Determines whether `+v` validator skips subsequent phases when the input value is `None` or *empty value*.

- `empty_specs`
    - type: `[(type[T], (T) -> bool)]`
    - default: `[]`
    - phase: Requirement
    - description:
        - List of pairs composed of a type and a function, where the function takes a value of the type and returns whether it is *empty* or not.
        - The function is invoked when the input value is an instance of the paired type.

- `isinstance_builtin` / `isinstance_any`
    - type: `bool`
    - default: `False`
    - phase: Conversion
    - description:
        - This configuration has effect on `Converter`s declared by type constructor (`int`, `float` etc).
        - If `True`, `Converter` checks the type of input value and returns it as it is if it is an instance of the type, otherwise fails.
        - `_builtin` works only for builtin types, whereas `_any` works for any type.

- `join_on_fail`
    - type: `bool`
    - default: `True`
    - phase: Conversion, Verification
    - description:
        - Determines what is assigned to the iterable attribute when the validation on it fails.
        - If `True`, `None` is assigned even when validations to some items succeeds.
        - Otherwise, a list is assigned which contains successfully validated values and `None`s on failed index.

- `ignore_remainders`
    - type: `bool`
    - default: `False`
    - description:
        - Determines whether undeclared keys are simply ignored and discarded.
        - If `True`, `remainders` attribute is always empty dictionary.

- `share_context`
    - type: `bool`
    - default: `False`
    - description:
        - If `True`, validation context is never created newly, that is, an instance is shared at every path.
        - Also, `remainders` takes hierarchical form equivalent to the structure of nested validatable types.

## Multidict support

This library supports `werkzeug.datastructures.MultiDict` which is used in [Flask](http://flask.pocoo.org/docs/1.0/) to store request forms and queries. In addition to `dict`, the instance of `MultiDict` can be an input of `Validator`.

In many web application frameworks, although form values and queries can associate multiple values with a single key, the request object tends to return a single value when accessed as a dictionary. To solve this difference between `dict` and request object, this library first checks the input is `MultiDict` or not and changes accessors according to the type of the input. Thus, you can give `request.form`, `request.args` and any other `MultiDict` values to `validate_dict`.
