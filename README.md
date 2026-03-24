# py_override

[![en](https://img.shields.io/badge/lang-en-green)](README.md)
[![zh-cn](https://img.shields.io/badge/lang-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-green)](README.zh-cn.md)

`py_override` brings Java-style `@Override` to Python, but with runtime signature checks that fail fast when an override drifts.

## Quick example

```python
from override import override


class X: ...
class Y(X): ...
class Z(Y): ...


class Base:
  def f(self) -> Y: ...
  def g(self) -> Y: ...
  def h(self) -> Y: ...

  def i(self, x: Y): ...
  def j(self, x: Y): ...
  def k(self, x: Y): ...

  def o(self, x, *args): ...
  def v(self, *, x, **kwargs): ...


class Derived(Base):
  @override
  def f(self) -> Y: ...            # OK

  @override
  def g(self) -> Z: ...            # OK: covariant return type

  @override
  def h(self) -> X: ...            # error: return type mismatch

  @override
  def i(self, x: Y): ...           # OK

  @override
  def j(self, x: Z): ...           # error: parameter type is too narrow

  @override
  def k(self, x: X): ...           # OK: type hint missing on one side skips the check

  @override
  def o(self, x): ...              # error: *args presence mismatch

  @override
  def v(self, *, x, extra, **kwargs): ... # OK: parent has **kwargs, so extra keywords are allowed
```

The check is performed automatically the first time the function runs, and if the check passes, it will not be performed again in subsequent runs. When a check fails, the message includes the reason plus the base and derived signatures with file and line numbers, for example:

```text
Return type error: Animal vs. Dog
base signature filename.py:114 def make(self) -> Animal
derived signature filename.py:514 def make(self) -> Dog
```

## What it checks

### Override target

- The decorated method must override a method with the same name in a parent class.
- If no parent method exists, validation fails and the message shows only the child signature.

### Parameter types

- A child parameter is compatible with its parent parameter when either side has no type hint.
- Otherwise, the child annotation must be a subclass of the parent annotation.

### Parameter shapes

- Positional-only parameters: same count, checked one by one.
- Keyword-only parameters: same count and same names.
- Parameters that are both positional-or-keyword: treated like positional-only for validation.
- `*args`: must exist on both sides or neither side.
- `**kwargs`: must exist on both sides or neither side.
- If the parent has `*args`, the child may have additional positional parameters.
- If the parent has `**kwargs`, the child may have additional keyword parameters.

### Default values

- If the parent parameter has a default value, the child parameter must also keep a default value.
- If the parent parameter has no default value, the child may choose to add one or not.

### Return types

- If either return annotation is missing, validation is skipped.
- Otherwise, the child return type must be a subclass of the parent return type.

## Run tests

```bash
python -m unittest test.py
```
