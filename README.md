# py_override

[![en](https://img.shields.io/badge/lang-en-green)](README.md)
[![zh-cn](https://img.shields.io/badge/lang-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-green)](README.zh-cn.md)

`py_override` brings Java-style `@Override` to Python, but with runtime signature checks that fail fast when an override drifts.

## Quick example

```python
from override import override

from typing import TypeVar

class X: ...
class Y(X): ...
class Z(Y): ...

T = TypeVar('T')

class Base:
  def f(self) -> T | 'Base': ...
  def g(self) -> T | 'Derived': ...
  def h(self, *, x, y: int): ...
  def i(self, *, x, y, **kwargs): ...
  def j(self, *, x, y, **kwargs): ...
  def k(self, x, y, *args): ...
  def l(self, x): ...

class Derived(Base):
  @override
  def f(self) -> T | 'Derived': ...   # OK, T <= T, Derived <= Base
  @override
  def g(self) -> T | 'Base': ...      # Failed, Base is wider than Derived
  @override
  def h(self, *, y: float, x): ...    # Failed, type of y not match
  @override
  def i(self, *, x, **kwargs): ...    # OK, **kwargs allow child omit parameter
  @override
  def j(self, *, x, y): ...           # Failed, **kwargs presence not match
  @override
  def k(self, x, *args): ...          # OK, *args allow child omit position parameter at end
  @override
  def l(self, x, y = 0): ...          # OK, child can have extra parameter with default value
```

The check is performed automatically the first time the function runs, and if the check passes, it will not be performed again in subsequent runs. When a check fails, the message includes the reason plus the base and derived signatures with file and line numbers, for example:

```text
Return type error: Animal vs. Dog
base signature filename.py:114 def make(self) -> Animal
derived signature filename.py:514 def make(self) -> Dog
```

The decorator also works with nested classes and classes defined inside functions. In addition, it understands a few common typing features used in annotations, including `typing.Union` / `|` unions, `TypeVar`, and forward references.

## What it checks

### Override target

- The decorated method must override a method with the same name in a parent class.
- If no parent method exists, validation fails and the message shows only the child signature.

### Parameter types

- A child parameter is compatible with its parent parameter when either side has no type hint.
- Otherwise, the child annotation must be a superclass of the parent annotation.

### Parameter shapes

- Positional-only parameters: same count, checked one by one.
- Keyword-only parameters: same count and same names.
- Parameters that are both positional-or-keyword: treated like positional-only for validation.
- `*args`: allows the child to omit trailing fixed positional parameters from the parent.
- `**kwargs`: allows the child to omit keyword-only parameters from the parent.
- If the child adds extra positional or keyword-only parameters, those extra parameters must have defaults.

### Default values

- If the parent parameter has a default value, the child parameter must also keep a default value.
- If the parent parameter has no default value, the child may choose to add one or not.

### Return types

- If either return annotation is missing, validation is skipped.
- Otherwise, the child return type must be a subclass of the parent return type.

### Multi Inheritance

- In the case of multiple inheritance, `@override` ensures all parent classes have a method with the same name, and the child method conforms to the contract of all parent classes.

## Notes

- This is a runtime check, not a static type checker, so validation happens only when the overridden method is called for the first time.
- Annotation evaluation uses `typing.get_type_hints`, so annotations should come from trusted code.
- If a signature cannot be resolved cleanly, the error message is designed to include the file name and line number of the relevant method.

## Run tests

```bash
python -m unittest test.py
```

## Known Issue

- method marked `@staticmethod` in local class cannot be handled properly.

  ```python
  from override import override

  def outer():
    class Base:
      @staticmethod
      def f(): ...

    class Derived(Base):
      @staticmethod
      @override
      def f(): ...

    Derived().f() # crash

  outer()
  ```

- wrapper not using `functools.wraps` properly would interfere with `@override`.

  ```python
  from override import override

  def wrapper_with_no_wraps(func):
    # ought to use @wraps(func)
    def wrapper(*args, **kwargs):
      return func(*args, **kwargs)
    return wrapper

  class Base:
    def f(self): ...

  class Derived(Base):
    @override
    @wrapper_with_no_wraps
    def f(self): ...

  Derived().f() # failed
  ```

  place `@override` at the closest position to the function to make it work.

  ```python
  from override import override

  def wrapper_with_no_wraps(func):
    # ought to use @wraps(func)
    def wrapper(*args, **kwargs):
      return func(*args, **kwargs)
    return wrapper

  class Base:
    def f(self): ...

  class Derived(Base):
    @wrapper_with_no_wraps
    @override # closest to the function
    def f(self): ...

  Derived().f() # OK
  ```
