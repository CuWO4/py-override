# py_override

[![en](https://img.shields.io/badge/lang-en-green)](README.md)
[![zh-cn](https://img.shields.io/badge/lang-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-green)](README.zh-cn.md)

`py_override` 把 Java 风格的 `@Override` 带进 Python, 并且会在运行时严格检查子类方法是否仍然符合父类契约.

## 快速示例

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

检查会在函数第一次运行时自动执行, 并且如果通过检查, 则后续运行不会再执行检查. 当校验失败时, 错误会同时带上原因和签名位置, 例如:

```text
Return type error: Animal vs. Dog
base signature filename.py:114 def make(self) -> Animal
derived signature filename.py:514 def make(self) -> Dog
```

这个装饰器也支持嵌套类以及定义在函数内部的局部类. 另外, 它也能处理一些常见的注解类型, 包括 `typing.Union` / `|` 联合类型、`TypeVar` 和前向引用.

## 检查规则

### 覆盖目标

- 被装饰的方法必须重写父类里同名的方法.
- 如果找不到父类方法, 会直接报错, 并且只显示子类签名.

### 参数类型

- 子类形参与父类形参在以下任一情况下视为兼容:

- 任一侧没有 type hint
- 子类注解是父类注解的父类

### 参数形状

- 仅位置参数: 个数必须一致, 并逐个检查.
- 仅关键字参数: 个数必须一致, 且参数名必须完全一致.
- 既可位置也可关键字的参数: 按位置参数处理.
- `*args`: 允许子类省略父类尾部的固定位置参数.
- `**kwargs`: 允许子类省略父类的 keyword-only 参数.
- 如果子类新增位置参数或 keyword-only 参数, 这些新增参数必须带默认值.

### 默认值

- 如果父类参数有默认值, 则子类对应参数也必须保留默认值.
- 如果父类参数没有默认值, 则子类可以保留默认值, 也可以不保留.

### 返回类型

- 如果任一返回值标注缺失, 则跳过检查.
- 否则, 子类返回类型必须是父类返回类型的子类.

## 说明

- 这是运行时检查, 不是静态类型检查器, 所以只有在被重写的方法第一次调用时才会验证.
- 注解解析使用 `typing.get_type_hints`, 因此注解应当来自可信代码.
- 如果签名无法被正常解析, 错误信息会尽量带上相关方法的文件名和行号.

## 运行测试

```bash
python -m unittest test.py
```

## 已知问题

- 局部类中被标记为 `@staticmethod` 的方法无法被正确处理.

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

- 未正确使用 `functools.wraps` 的自定义 wrapper 会干扰 `@override`

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

  将 `@override` 写在离函数最近的地方来使其正常工作.

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
