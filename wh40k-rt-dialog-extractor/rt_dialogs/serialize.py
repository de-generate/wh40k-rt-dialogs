"""Generic dataclass <-> JSON-compatible value conversion.

* Fields whose value equals their default are omitted.
* Node subclasses carry a ``"kind"`` discriminator (their ``KIND`` class var) so
  that ``Cue | Answer | …`` unions can be reconstructed.
* ``Any`` typed values are passed through unchanged.
"""

from __future__ import annotations

import dataclasses
import functools
import types
import typing
from typing import Any

MISSING = dataclasses.MISSING


@functools.cache
def _fields(cls: type) -> tuple[tuple[str, Any, Any], ...]:
    """(name, type hint, default or factory marker) for each dataclass field."""
    hints = typing.get_type_hints(cls)
    out = []
    for f in dataclasses.fields(cls):
        if f.default is not MISSING:
            default = ("value", f.default)
        elif f.default_factory is not MISSING:
            default = ("factory", f.default_factory)
        else:
            default = None
        out.append((f.name, hints[f.name], default))
    return tuple(out)


def to_json(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out: dict[str, Any] = {}
        kind = getattr(type(obj), "KIND", None)
        if kind:
            out["kind"] = kind
        for name, _, default in _fields(type(obj)):
            value = getattr(obj, name)
            if default is not None:
                how, d = default
                if value == (d if how == "value" else d()):
                    continue
            out[name] = to_json(value)
        return out
    if isinstance(obj, (list, tuple)):
        return [to_json(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_json(v) for k, v in obj.items()}
    return obj


def from_json(tp: Any, data: Any) -> Any:
    if tp is Any or data is None:
        return data
    origin = typing.get_origin(tp)
    if origin in (typing.Union, types.UnionType):
        options = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(options) == 1:
            return from_json(options[0], data)
        by_kind = {getattr(a, "KIND", None): a for a in options}
        if isinstance(data, dict) and data.get("kind") in by_kind:
            return from_json(by_kind[data["kind"]], data)
        raise TypeError(f"cannot decide union member of {tp} for {str(data)[:80]}")
    if origin is list:
        (item,) = typing.get_args(tp)
        return [from_json(item, v) for v in data]
    if origin is dict:
        _, value = typing.get_args(tp)
        return {k: from_json(value, v) for k, v in data.items()}
    if dataclasses.is_dataclass(tp):
        kwargs = {}
        for name, hint, _ in _fields(tp):
            if name in data:
                kwargs[name] = from_json(hint, data[name])
        unknown = set(data) - {f[0] for f in _fields(tp)} - {"kind"}
        if unknown:
            raise ValueError(f"unknown fields for {tp.__name__}: {sorted(unknown)}")
        return tp(**kwargs)
    if tp is float and isinstance(data, int):
        return float(data)
    return data
