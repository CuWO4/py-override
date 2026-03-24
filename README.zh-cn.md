# py_override

[![en](https://img.shields.io/badge/lang-en-green)](README.md)
[![zh-cn](https://img.shields.io/badge/lang-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-green)](README.zh-cn.md)

`py_override` 把 Java 风格的 `@Override` 带进 Python, 并且会在运行时严格检查子类方法是否仍然符合父类契约.

## 快速示例

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
  def g(self) -> Z: ...            # OK: 返回类型协变

  @override
  def h(self) -> X: ...            # 报错: 返回类型不匹配

  @override
  def i(self, x: Y): ...           # OK

  @override
  def j(self, x: Z): ...           # 报错: 参数类型过窄

  @override
  def k(self, x: X): ...           # OK: 一侧没有 type hint 时跳过检查

  @override
  def o(self, x): ...              # 报错: *args 存在性不一致

  @override
  def v(self, *, x, extra, **kwargs): ... # OK: 父类有 **kwargs, 允许更多关键字参数
```

检查会在函数第一次运行时自动执行, 并且如果通过检查, 则后续运行不会再执行检查. 当校验失败时, 错误会同时带上原因和签名位置, 例如:

```text
Return type error: Animal vs. Dog
base signature filename.py:114 def make(self) -> Animal
derived signature filename.py:514 def make(self) -> Dog
```

## 检查规则

### 覆盖目标

- 被装饰的方法必须重写父类里同名的方法.
- 如果找不到父类方法, 会直接报错, 并且只显示子类签名.

### 参数类型

- 子类形参与父类形参在以下任一情况下视为兼容:

- 任一侧没有 type hint
- 子类注解是父类注解的子类

### 参数形状

- 仅位置参数: 个数必须一致, 并逐个检查.
- 仅关键字参数: 个数必须一致, 且参数名必须完全一致.
- 既可位置也可关键字的参数: 按位置参数处理.
- `*args`: 子类和父类必须同时存在或同时不存在.
- `**kwargs`: 子类和父类必须同时存在或同时不存在.
- 如果父类存在 `*args`, 子类可以有更多位置参数.
- 如果父类存在 `**kwargs`, 子类可以有更多关键字参数.

### 默认值

- 如果父类参数有默认值, 则子类对应参数也必须保留默认值.
- 如果父类参数没有默认值, 则子类可以保留默认值, 也可以不保留.

### 返回类型

- 如果任一返回值标注缺失, 则跳过检查.
- 否则, 子类返回类型必须是父类返回类型的子类.

## 运行测试

```bash
python -m unittest test.py
```
