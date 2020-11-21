import math
from .context import ValidationContext
from .verifier import Verifier


class Variable:
    """
    Instances of this class behave as variable of validated object in verifying functions.

    A sequence of operations applied to the variable generates a function
    which evaluates those operations to the validated object lazily in verification phase.

    For exmaple, 
    
    >>> x.a.len * 3 > 5

    is a function equivalent to

    >>> lambda x: len(x.a) * 3 > 5

    Available operations are:

    - Operators and builtin functions whose behaviors can be overwritten by magic methods.
    - `len()` should be represented with an attribute `.len`. This is because `__len__()` must be implemented to return `int`.
    - `in_()` verifies that the variable equals to one item of the argument list.
    - `has()` verifies that the variable contains the argument. `in` operator is not available because the returned value of `__contains__()` is evaluated as `bool`.
    - Attribute and index access.

    Additionally, `not_` property returns a variable which inversed the result logically.
    The inversion is always evaluated after other operations. Use `inv()` instead to insert intermediate inversion. 

    Generated function as a result of those operations has `Verifier` which can produce `ValidationFailure`
    with name and arguments corresponding to the operation causing the failure.

    >>> f = (x.len > 5)._verifier.verify("abc")
    >>> f.name, f.kwargs
    ('x.len.gt', {'gt.value': 5})
    >>> class C:
    ...     def __init__(self, a):
    ...         self.a = a
    ...
    >>> c = C("a")
    >>> f = (x.a.len * 3 > 5)._verifier.verify(c)
    >>> f.name, f.kwargs
    ('x.@a.len.mul.gt', {'mul.value': 3, 'gt.value': 5})

    There exists a constraint that, as shown in above example, keys in `kwargs` are overwritten by following operation of the same type.
    """
    def __init__(self, f=lambda x:x, names=None, kwargs=None, not_=False):
        self._id = f
        self._names = names or ['x']
        self._kwargs = kwargs or {}
        self._not = not_

    def _sync(self, f, name, **kwargs):
        kw = {f"{name}.{k}":v for k, v in kwargs.items()}
        return Variable(lambda x: f(self._id(x)), self._names+[name], dict(self._kwargs, **kw), self._not)

    @property
    def len(self):
        return self._sync(lambda x: len(x), 'len')

    def in_(self, *v):
        return self._sync(lambda x: x in v, 'in', value=v)

    def has(self, v):
        return self._sync(lambda x: v in x, 'has', value=v)

    def inv(self):
        return self._sync(lambda x: not x, 'inv')

    @property
    def not_(self):
        return Variable(self._id, self._names, self._kwargs, True)

    @property
    def _verifier(self):
        func = lambda x: self(x)
        names = [n for n in self._names if n]
        if self._not:
            names[1:1] = ['not']
        return Verifier('.'.join(names), func, False, **self._kwargs)

    def __call__(self, x, context:ValidationContext=None):
        b = bool(self._id(x)) 
        return not b if self._not else b

    def __getattr__(self, key):
        if key == '__name__':
            return '.'.join(self._names)
        elif key == '__annotations__':
            return {}
        else:
            return self._sync(lambda x: getattr(x, key), f'@{key}')

    def __getitem__(self, key):
        return self._sync(lambda x: x[key], f'[{key}]')

    def __eq__(self, v):
        return self._sync(lambda x: x == v, 'eq', value=v)

    def __ne__(self, v):
        return self._sync(lambda x: x != v, 'ne', value=v)

    def __lt__(self, th):
        return self._sync(lambda x: x < th, 'lt', value=th)

    def __le__(self, th):
        return self._sync(lambda x: x <= th, 'le', value=th)

    def __gt__(self, th):
        return self._sync(lambda x: x > th, 'gt', value=th)

    def __ge__(self, th):
        return self._sync(lambda x: x >= th, 'ge', value=th)

    def __add__(self, v):
        return self._sync(lambda x: x + v, 'add', value=v)

    def __sub__(self, v):
        return self._sync(lambda x: x - v, 'sub', value=v)

    def __mul__(self, v):
        return self._sync(lambda x: x * v, 'mul', value=v)

    def __matmul__(self, v):
        return self._sync(lambda x: x @ v, 'matmul', value=v)

    def __truediv__(self, v):
        return self._sync(lambda x: x / v, 'truediv', value=v)

    def __floordiv__(self, v):
        return self._sync(lambda x: x // v, 'floordiv', value=v)

    def __mod__(self, v):
        return self._sync(lambda x: x % v, 'mod', value=v)

    def __divmod__(self, v):
        return self._sync(lambda x: divmod(x, v), 'divmod', value=v)

    def __pow__(self, v):
        return self._sync(lambda x: pow(x, v), 'pow', value=v)

    def __lshift__(self, v):
        return self._sync(lambda x: x << v, 'lshift', value=v)

    def __rshift__(self, v):
        return self._sync(lambda x: x >> v, 'rshift', value=v)

    def __and__(self, v):
        return self._sync(lambda x: x & v, 'and', value=v)

    def __xor__(self, v):
        return self._sync(lambda x: x ^ v, 'xor', value=v)

    def __or__(self, v):
        return self._sync(lambda x: x | v, 'or', value=v)

    def __neg__(self):
        return self._sync(lambda x: -x, 'neg')

    def __pos__(self):
        return self._sync(lambda x: +x, 'pos')

    def __abs__(self):
        return self._sync(lambda x: abs(x), 'abs')

    def __invert__(self):
        return self._sync(lambda x: ~x, 'invert')

    def __round__(self):
        return self._sync(lambda x: round(x), 'round')

    def __trunc__(self):
        return self._sync(lambda x: math.trunc(x), 'trunc')

    def __floor__(self):
        return self._sync(lambda x: math.floor(x), 'floor')

    def __ceil__(self):
        return self._sync(lambda x: math.ceil(x), 'ceil')


x = Variable()