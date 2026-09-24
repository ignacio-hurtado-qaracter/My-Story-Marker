"""Validator registration for the pipeline (contracts page, K3 "Registration convention").

Each validator-providing block exposes `register_validators() -> None` in its package
`__init__` or in a `validators` module. They are imported guarded by `ImportError`, so the
blocks merge in any order; a point with no validator registered passes (spec 007).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Final

PROVIDERS: Final[tuple[str, ...]] = (
    "app.validators.programmatic",  # B4
    "app.policy",  # B5
    "app.judge",  # B7
    "app.reader.visual_check",  # B10
)

_registered: list[str] = []


def _find(module_name: str) -> Callable[[], None] | None:
    for candidate in (module_name, f"{module_name}.validators"):
        try:
            module = importlib.import_module(candidate)
        except ImportError:
            continue
        hook = getattr(module, "register_validators", None)
        if callable(hook):
            return hook  # type: ignore[no-any-return]  # dynamic import, checked callable
    return None


def register_all(*, force: bool = False) -> list[str]:
    """Import and run every provider's `register_validators`; returns the modules found.
    Idempotent (the registry replaces by name), and cached unless `force`."""
    if _registered and not force:
        return list(_registered)
    _registered.clear()
    for name in PROVIDERS:
        hook = _find(name)
        if hook is not None:
            hook()
            _registered.append(name)
    return list(_registered)


__all__ = ["PROVIDERS", "register_all"]
