from functools import wraps
from types import FunctionType
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints
import inspect
import os
import types

__all__ = [
  'override'
]

_UNION_ORIGINS = {Union}
if hasattr(types, 'UnionType'):
  _UNION_ORIGINS.add(types.UnionType)


def _resolve_owner_class(func: FunctionType, first_arg=None) -> type:
  qualname = func.__qualname__
  parts = qualname.split('.')

  if first_arg is not None and '<locals>' in parts:
    runtime_class = first_arg if isinstance(first_arg, type) else type(first_arg)

    for base in runtime_class.__mro__:
      candidate = base.__dict__.get(func.__name__)
      if candidate is not None and getattr(candidate, '__wrapped__', None) is func:
        return base

  if len(parts) < 2:
    raise TypeError(f'{qualname} is not a class method')

  obj = func.__globals__.get(parts[0], None)
  assert obj is not None, f"Cannot resolve class from qualname: {qualname}"

  for p in parts[1:-1]:
    obj = getattr(obj, p, None)
    assert obj is not None, f"Cannot resolve nested class from qualname: {qualname}"

  assert isinstance(obj, type), f"Resolved object is not a class: {qualname}"

  return obj


def _find_parent_method(owning_class: type, func_name: str) -> FunctionType | None:
  for base in owning_class.__mro__[1:]:
    if func_name in base.__dict__:
      return base.__dict__[func_name]
  return None


def _format_class_path(path: list[type]) -> str:
  return ' -> '.join(cls.__qualname__ for cls in path)


def _collect_parent_methods(owning_class: type, func_name: str) -> tuple[list[FunctionType], list[list[type]]]:
  prototypes: list[FunctionType] = []
  missing_paths: list[list[type]] = []
  seen_prototypes: set[int] = set()

  def dfs(current_class: type, path: list[type]):
    if func_name in current_class.__dict__:
      prototype = current_class.__dict__[func_name]
      prototype_id = id(prototype)

      if prototype_id not in seen_prototypes:
        seen_prototypes.add(prototype_id)
        prototypes.append(prototype)

      return

    next_bases = [base for base in current_class.__bases__]

    if not next_bases:
      missing_paths.append(path)
      return

    for base in next_bases:
      dfs(base, path + [base])

  direct_bases = [base for base in owning_class.__bases__]

  if not direct_bases:
    missing_paths.append([owning_class])
    return prototypes, missing_paths

  for base in direct_bases:
    dfs(base, [base])

  return prototypes, missing_paths


def _format_type(value) -> str:
  if value is None:
    return 'unknown'

  if isinstance(value, TypeVar):
    return value.__name__

  origin = get_origin(value)
  if origin in _UNION_ORIGINS:
    return ' | '.join(_format_type(arg) for arg in get_args(value))

  if isinstance(value, type):
    return value.__qualname__.split('.')[-1]

  name = getattr(value, '__name__', None)
  if name:
    return name.split('.')[-1]

  text = str(value)
  if text.startswith("<class '") and text.endswith("'>"):
    text = text[8:-2]
  if text.startswith('ForwardRef(') and text.endswith(')'):
    text = text[len('ForwardRef('):-1].strip("'\"")
  return text.removeprefix('typing.').split('.')[-1]


def _format_param_names(parameters) -> str:
  return ', '.join(parameter.name for parameter in parameters) if parameters else '(none)'


def _format_presence(value: bool) -> str:
  return 'present' if value else 'absent'


def _format_signature_line(func: FunctionType) -> str:
  try:
    file_path = inspect.getsourcefile(func) or inspect.getfile(func)
  except TypeError:
    file_path = '<unknown>'
  try:
    _, start_line = inspect.getsourcelines(func)
  except TypeError:
    start_line = '<unknown>'
  file_name = os.path.basename(file_path)
  signature = inspect.signature(func)
  parameters = []
  seen_keyword_only = False
  has_positional_only = any(parameter.kind == inspect.Parameter.POSITIONAL_ONLY
                            for parameter in signature.parameters.values())
  positional_only_remaining = sum(
    1 for parameter in signature.parameters.values()
    if parameter.kind == inspect.Parameter.POSITIONAL_ONLY
  )

  for parameter in signature.parameters.values():
    if parameter.kind == inspect.Parameter.KEYWORD_ONLY \
      and not seen_keyword_only and parameter.kind != inspect.Parameter.VAR_KEYWORD:
      if not any(item == '*' for item in parameters) \
        and not any(part.startswith('*') for part in parameters):
        parameters.append('*')
      seen_keyword_only = True

    if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
      text = parameter.name
    elif parameter.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
      text = parameter.name
    elif parameter.kind == inspect.Parameter.VAR_POSITIONAL:
      text = f"*{parameter.name}"
    elif parameter.kind == inspect.Parameter.KEYWORD_ONLY:
      text = parameter.name
    else:
      text = f"**{parameter.name}"

    if parameter.annotation is not inspect.Parameter.empty:
      text += f": {_format_type(parameter.annotation)}"

    if parameter.default is not inspect.Parameter.empty:
      text += f" = {parameter.default!r}"

    parameters.append(text)

    if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
      positional_only_remaining -= 1
      if positional_only_remaining == 0 and has_positional_only:
        parameters.append('/')

  if parameters and parameters[-1] == '*':
    parameters.pop()

  return_annotation = ''
  if signature.return_annotation is not inspect.Signature.empty:
    return_annotation = f" -> {_format_type(signature.return_annotation)}"

  return f"{file_name}:{start_line} def {func.__name__}" \
         f"({', '.join(parameters)}){return_annotation}"


def _wrap_override_error(reason: str, child_func: FunctionType,
                         parent_func: FunctionType | None = None) -> TypeError:
  if parent_func is None:
    return TypeError(f"{reason}\nsignature {_format_signature_line(child_func)}")

  return TypeError(
    f"{reason}\nbase signature {_format_signature_line(parent_func)}"
    f"\nderived signature {_format_signature_line(child_func)}"
  )


def _is_type_compatible(child_t: type | None, parent_t: type | None) -> bool:
  if child_t is None or parent_t is None:
    return True

  if child_t is parent_t or child_t == parent_t:
    return True

  if child_t is Any or parent_t is Any:
    return True

  if isinstance(child_t, TypeVar):
    if child_t.__constraints__:
      return all(_is_type_compatible(constraint, parent_t)
                 for constraint in child_t.__constraints__)
    if child_t.__bound__ is not None:
      return _is_type_compatible(child_t.__bound__, parent_t)
    return True

  if isinstance(parent_t, TypeVar):
    if parent_t.__constraints__:
      return any(_is_type_compatible(child_t, constraint)
                 for constraint in parent_t.__constraints__)
    if parent_t.__bound__ is not None:
      return _is_type_compatible(child_t, parent_t.__bound__)
    return True

  child_origin = get_origin(child_t)
  parent_origin = get_origin(parent_t)

  if child_origin in _UNION_ORIGINS:
    return all(_is_type_compatible(option, parent_t)
               for option in get_args(child_t))

  if parent_origin in _UNION_ORIGINS:
    return any(_is_type_compatible(child_t, option)
               for option in get_args(parent_t))

  child_type = child_origin or child_t
  parent_type = parent_origin or parent_t

  if isinstance(child_type, type) and isinstance(parent_type, type):
    try:
      return issubclass(child_type, parent_type)
    except TypeError:
      return child_type == parent_type

  return child_t == parent_t


def _is_default_compatible(child_param: inspect.Parameter,
                           parent_param: inspect.Parameter) -> bool:
  if parent_param.default is inspect.Parameter.empty:
    return True

  return child_param.default is not inspect.Parameter.empty


def _has_default(parameter: inspect.Parameter) -> bool:
  return parameter.default is not inspect.Parameter.empty


def _check_signature(child_func: FunctionType, parent_func: FunctionType):
  sig_c = inspect.signature(child_func)
  sig_p = inspect.signature(parent_func)

  hints_c = get_type_hints(child_func)
  hints_p = get_type_hints(parent_func)

  params_c = sig_c.parameters
  params_p = sig_p.parameters

  list_c = list(params_c.values())
  list_p = list(params_p.values())

  def split_params(params):
    pos_only = []
    pos_or_kw = []
    kw_only = []
    var_pos = None
    var_kw = None

    for p in params:
      if p.kind == inspect.Parameter.POSITIONAL_ONLY:
        pos_only.append(p)
      elif p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
        pos_or_kw.append(p)
      elif p.kind == inspect.Parameter.KEYWORD_ONLY:
        kw_only.append(p)
      elif p.kind == inspect.Parameter.VAR_POSITIONAL:
        var_pos = p
      elif p.kind == inspect.Parameter.VAR_KEYWORD:
        var_kw = p

    return pos_only, pos_or_kw, kw_only, var_pos, var_kw

  c_po, c_pk, c_kw, c_varpos, c_varkw = split_params(list_c)
  p_po, p_pk, p_kw, p_varpos, p_varkw = split_params(list_p)

  if bool(c_varpos) != bool(p_varpos):
      if p_varpos and not c_varpos:
        pass
      else:
        raise _wrap_override_error(
          f"*args presence error: "
          f"{_format_presence(bool(c_varpos))} vs. {_format_presence(bool(p_varpos))}",
          child_func,
          parent_func,
        )

  if bool(c_varkw) != bool(p_varkw):
      if p_varkw and not c_varkw:
        pass
      else:
        raise _wrap_override_error(
          f"**kwargs presence error: "
          f"{_format_presence(bool(c_varkw))} vs. {_format_presence(bool(p_varkw))}",
          child_func,
          parent_func,
        )

  c_pos = c_po + c_pk
  p_pos = p_po + p_pk

  shared_pos_count = min(len(c_pos), len(p_pos))

  for i in range(shared_pos_count):
    pc = c_pos[i]
    pp = p_pos[i]

    tc = hints_c.get(pc.name)
    tp = hints_p.get(pp.name)

    if not _is_type_compatible(tp, tc):
      raise _wrap_override_error(
        f"Positional parameter type error ({pc.name}): "
        f"{_format_type(tc)} vs. {_format_type(tp)}",
        child_func,
        parent_func,
      )

    if not _is_default_compatible(pc, pp):
      raise _wrap_override_error(
        f"Positional parameter default error ({pc.name}): "
        f"{_format_presence(_has_default(pc))} vs. {_format_presence(_has_default(pp))}",
        child_func,
        parent_func,
      )

  if len(c_pos) > len(p_pos):
    extra_child_pos = c_pos[len(p_pos):]

    if not all(_has_default(param) for param in extra_child_pos):
      raise _wrap_override_error(
        f"Positional parameter count error: {len(c_pos)} vs. {len(p_pos)}",
        child_func,
        parent_func,
      )

  if len(c_pos) < len(p_pos) and not p_varpos:
    raise _wrap_override_error(
      f"Positional parameter count error: {len(c_pos)} vs. {len(p_pos)}",
      child_func,
      parent_func,
    )

  p_kw_map = {p.name: p for p in p_kw}
  c_kw_map = {p.name: p for p in c_kw}

  shared_kw_names = p_kw_map.keys() & c_kw_map.keys()

  for name in shared_kw_names:
    pc = c_kw_map[name]
    pp = p_kw_map[name]

    tc = hints_c.get(name)
    tp = hints_p.get(name)

    if not _is_type_compatible(tp, tc):
      raise _wrap_override_error(
        f"Keyword-only parameter type error ({name}): "
        f"{_format_type(tc)} vs. {_format_type(tp)}",
        child_func,
        parent_func,
      )

    if not _is_default_compatible(pc, pp):
      raise _wrap_override_error(
        f"Keyword-only parameter default error ({name}): "
        f"{_format_presence(_has_default(pc))} vs. {_format_presence(_has_default(pp))}",
        child_func,
        parent_func,
      )

  extra_child_kw = [c_kw_map[name] for name in c_kw_map.keys() - p_kw_map.keys()]
  if extra_child_kw and not all(_has_default(param) for param in extra_child_kw):
    raise _wrap_override_error(
      f"Keyword-only parameter count error: {len(c_kw)} vs. {len(p_kw)}",
      child_func,
      parent_func,
    )

  missing_parent_kw = [p_kw_map[name] for name in p_kw_map.keys() - c_kw_map.keys()]
  if missing_parent_kw and not p_varkw:
    raise _wrap_override_error(
      f"Keyword-only parameter count error: {len(c_kw)} vs. {len(p_kw)}",
      child_func,
      parent_func,
    )

  rc = hints_c.get('return')
  rp = hints_p.get('return')

  if not _is_type_compatible(rc, rp):
    raise _wrap_override_error(
      f"Return type error: {_format_type(rc)} vs. {_format_type(rp)}",
      child_func,
      parent_func,
    )


def override(func: FunctionType):
  checked = False

  @wraps(func)
  def wrapper(*args, **kwargs):
    nonlocal checked

    if not checked:
      first_arg = args[0] if args else None
      cls = _resolve_owner_class(func, first_arg)

      parent_funcs, missing_paths = _collect_parent_methods(cls, func.__name__)

      if missing_paths:
        raise _wrap_override_error(
          f"override target missing along path(s): "
          f"{'; '.join(_format_class_path(path) for path in missing_paths)}",
          func,
        )

      for parent_func in parent_funcs:
        _check_signature(func, parent_func)

      checked = True

    return func(*args, **kwargs)

  return wrapper
