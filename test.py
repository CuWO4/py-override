import unittest
from unittest.mock import patch

import override as override_module
from override import override


class Animal:
  pass


class Dog(Animal):
  pass


class QualnameContainer:
  class Base:
    def add(self, value: int) -> int:
      return value + 1

  class Child(Base):
    @override
    def add(self, value: object) -> int:
      return int(value) + 2


class GrandParentLookup:
  def hop(self, value: int) -> int:
    return value + 10


class MiddleLookup(GrandParentLookup):
  pass


class ChildLookup(MiddleLookup):
  @override
  def hop(self, value: object) -> int:
    return int(value) + 20


class MROFirstBase:
  def pick(self, value: int) -> int:
    return value + 1


class MROSecondBase:
  def pick(self, value: int) -> str:
    return str(value)


class MROChild(MROFirstBase, MROSecondBase):
  @override
  def pick(self, value: object) -> int:
    return int(value) + 2


class NoParentMethod:
  @override
  def brand_new(self) -> int:
    return 1


class PosCountParent:
  def calc(self, left: int, /, right: int) -> int:
    return left + right


class PosCountChild(PosCountParent):
  @override
  def calc(self, left: object, /) -> int:
    return int(left)


class PosTypeParent:
  def calc(self, value: int) -> int:
    return 1


class PosTypeChild(PosTypeParent):
  @override
  def calc(self, value: str) -> int:
    return 1


class KwNameParent:
  def calc(self, *, left: int, right: int) -> int:
    return left + right


class KwNameChild(KwNameParent):
  @override
  def calc(self, *, left: object, middle: int) -> int:
    return 1


class NoStarParent:
  def calc(self, value: int) -> int:
    return value


class ChildAddsStar(NoStarParent):
  @override
  def calc(self, value: object, *args) -> int:
    return int(value)


class StarParent:
  def calc(self, value: int, *args) -> int:
    return value


class ChildLacksStar(StarParent):
  @override
  def calc(self, value: object) -> int:
    return int(value)


class NoKwParent:
  def calc(self, *, value: int) -> int:
    return value


class ChildAddsKw(NoKwParent):
  @override
  def calc(self, *, value: object, extra: int, **kwargs) -> int:
    return int(value)


class KwParent:
  def calc(self, *, value: int, **kwargs) -> int:
    return value


class ChildLacksKw(KwParent):
  @override
  def calc(self, *, value: object) -> int:
    return int(value)


class StarParentAllowed:
  def calc(self, value: int, *args) -> int:
    return value + len(args)


class StarChildAllowed(StarParentAllowed):
  @override
  def calc(self, value: object, extra: object, *args) -> int:
    return int(value) + int(extra) + sum(args, 0)


class KwParentAllowed:
  def calc(self, *, value: int, **kwargs) -> int:
    return value


class KwChildAllowed(KwParentAllowed):
  @override
  def calc(self, *, value: object, extra: int, bonus: int, **kwargs) -> int:
    return int(value) + extra + bonus


class DefaultParentOk:
  def calc(self, value: int = 1) -> int:
    return value + 1


class DefaultChildOk(DefaultParentOk):
  @override
  def calc(self, value: object = 2) -> int:
    return int(value) + 2


class DefaultParentBad:
  def calc(self, value: int = 1) -> int:
    return value + 1


class DefaultChildBad(DefaultParentBad):
  @override
  def calc(self, value: object) -> int:
    return int(value) + 2


class TypedParamParent:
  def typed(self, value: int) -> int:
    return value


class TypedParamChild(TypedParamParent):
  @override
  def typed(self, value: object):
    return value


class UntypedParamParent:
  def untyped(self, value):
    return value


class UntypedParamChild(UntypedParamParent):
  @override
  def untyped(self, value: int) -> int:
    return value


class ReturnParent:
  def make(self) -> Animal:
    return Animal()


class ReturnChild(ReturnParent):
  @override
  def make(self) -> Dog:
    return Dog()


class ReturnMismatchParent:
  def make(self) -> Dog:
    return Dog()


class ReturnMismatchChild(ReturnMismatchParent):
  @override
  def make(self) -> Animal:
    return Animal()


class OverrideTests(unittest.TestCase):
  def test_nested_qualname_resolution_and_cache(self):
    with patch.object(
      override_module,
      "_check_signature",
      wraps=override_module._check_signature,
    ) as mocked:
      a = QualnameContainer.Child()
      b = QualnameContainer.Child()

      self.assertEqual(a.add(1), 3)
      self.assertEqual(b.add(2), 4)
      self.assertEqual(mocked.call_count, 1)

  def test_recursive_parent_lookup_through_ancestor_chain(self):
    obj = ChildLookup()
    self.assertEqual(obj.hop(5), 25)

  def test_first_mro_match_wins(self):
    obj = MROChild()
    self.assertEqual(obj.pick(7), 9)

  def test_missing_parent_method_raises(self):
    with self.assertRaisesRegex(
      TypeError,
      r"not override any methods\nsignature test\.py:\d+ def brand_new\(self\) -> int",
    ):
      NoParentMethod().brand_new()

  def test_positional_count_mismatch_raises(self):
    with self.assertRaisesRegex(
      TypeError,
      r"Positional parameter count error: 2 vs\. 3\nbase signature test\.py:\d+ def calc\(self, left: int, /, right: int\) -> int\nderived signature test\.py:\d+ def calc\(self, left: object, /\) -> int",
    ):
      PosCountChild().calc(1)

  def test_positional_type_mismatch_raises(self):
    with self.assertRaisesRegex(
      TypeError,
      r"Positional parameter type error \(value\): str vs\. int\nbase signature test\.py:\d+ def calc\(self, value: int\) -> int\nderived signature test\.py:\d+ def calc\(self, value: str\) -> int",
    ):
      PosTypeChild().calc(1)

  def test_keyword_only_name_mismatch_raises(self):
    with self.assertRaisesRegex(
      TypeError,
      r"Keyword-only parameter names error: left, middle vs\. left, right\nbase signature test\.py:\d+ def calc\(self, \*, left: int, right: int\) -> int\nderived signature test\.py:\d+ def calc\(self, \*, left: object, middle: int\) -> int",
    ):
      KwNameChild().calc(left=1, middle=2)

  def test_star_args_presence_mismatch_raises_when_child_adds_star_args(self):
    with self.assertRaisesRegex(
      TypeError,
      r"\*args presence error: present vs\. absent\nbase signature test\.py:\d+ def calc\(self, value: int\) -> int\nderived signature test\.py:\d+ def calc\(self, value: object, \*args\) -> int",
    ):
      ChildAddsStar().calc(1)

  def test_star_args_presence_mismatch_raises_when_parent_has_star_args(self):
    with self.assertRaisesRegex(
      TypeError,
      r"\*args presence error: absent vs\. present\nbase signature test\.py:\d+ def calc\(self, value: int, \*args\) -> int\nderived signature test\.py:\d+ def calc\(self, value: object\) -> int",
    ):
      ChildLacksStar().calc(1)

  def test_double_star_kwargs_presence_mismatch_raises_when_child_adds_kwargs(self):
    with self.assertRaisesRegex(
      TypeError,
      r"\*\*kwargs presence error: present vs\. absent\nbase signature test\.py:\d+ def calc\(self, \*, value: int\) -> int\nderived signature test\.py:\d+ def calc\(self, \*, value: object, extra: int, \*\*kwargs\) -> int",
    ):
      ChildAddsKw().calc(value=1, extra=2)

  def test_double_star_kwargs_presence_mismatch_raises_when_parent_has_kwargs(self):
    with self.assertRaisesRegex(
      TypeError,
      r"\*\*kwargs presence error: absent vs\. present\nbase signature test\.py:\d+ def calc\(self, \*, value: int, \*\*kwargs\) -> int\nderived signature test\.py:\d+ def calc\(self, \*, value: object\) -> int",
    ):
      ChildLacksKw().calc(value=1)

  def test_extra_positionals_allowed_when_parent_has_star_args(self):
    self.assertEqual(StarChildAllowed().calc(1, 2, 3), 6)

  def test_extra_keyword_only_allowed_when_parent_has_double_star_kwargs(self):
    self.assertEqual(KwChildAllowed().calc(value=1, extra=2, bonus=3), 6)

  def test_untyped_hints_are_skipped(self):
    self.assertEqual(TypedParamChild().typed(10), 10)
    self.assertEqual(UntypedParamChild().untyped(11), 11)

  def test_local_class_defined_inside_function_is_supported(self):
    def factory():
      class LocalBase:
        def ping(self, value: int = 1) -> int:
          return value + 1

      class LocalChild(LocalBase):
        @override
        def ping(self, value: object = 2) -> int:
          return int(value) + 2

      return LocalChild()

    obj = factory()
    self.assertEqual(obj.ping(), 4)
    self.assertEqual(obj.ping(3), 5)

  def test_default_parameters_with_matching_optional_semantics_are_supported(self):
    self.assertEqual(DefaultChildOk().calc(), 4)
    self.assertEqual(DefaultChildOk().calc(3), 5)

  def test_parent_default_but_child_requires_argument_is_rejected(self):
    with self.assertRaisesRegex(
      TypeError,
      r"Positional parameter default error \(value\): absent vs\. present\nbase signature test\.py:\d+ def calc\(self, value: int = 1\) -> int\nderived signature test\.py:\d+ def calc\(self, value: object\) -> int",
    ):
      DefaultChildBad().calc(1)

  def test_return_type_covariance_accepted(self):
    self.assertIsInstance(ReturnChild().make(), Dog)

  def test_return_type_mismatch_raises(self):
    with self.assertRaisesRegex(
      TypeError,
      r"Return type error: Animal vs\. Dog\nbase signature test\.py:\d+ def make\(self\) -> Dog\nderived signature test\.py:\d+ def make\(self\) -> Animal",
    ):
      ReturnMismatchChild().make()


if __name__ == "__main__":
  unittest.main()