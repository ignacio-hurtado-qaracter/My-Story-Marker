"""Validator registration for the pipeline (contracts page, K3 "Registration convention").

Each validator-providing block exposes `register_validators() -> None` in its package
`__init__` or in a `validators` module. They are imported guarded by `ImportError`, so the
blocks merge in any order; a point with no validator registered passes (spec 007).

**One Lean project per novel.** `lean_chronology` (B4) writes one generated `Story.lean`
per Lake project, so two novels generated at the same time in two processes would overwrite
each other's story. `register_lean_for(novel_id, base)` copies `formal/lean` (with its
`.lake` build cache when present) to `<base>/lean/<novel_id>` once and registers a
`LeanChronology` bound to that copy, replacing the default one.
"""

from __future__ import annotations

import importlib
import re
import shutil
from collections.abc import Callable
from pathlib import Path
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


def lean_dir_for(novel_id: str, base: Path) -> Path | None:
    """`<base>/lean/<novel_id>`, a private copy of `formal/lean`; None without B8/B4."""
    try:
        runner = importlib.import_module("app.formal.lean_runner")
    except ImportError:
        return None
    source = getattr(runner, "DEFAULT_LEAN_DIR", None)
    if not isinstance(source, Path) or not (source / "lakefile.toml").is_file():
        return None
    target = base / "lean" / re.sub(r"[^A-Za-z0-9_.-]", "_", novel_id)
    if not (target / "lakefile.toml").is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True)
    return target


def register_lean_for(novel_id: str, base: Path) -> Path | None:
    try:
        module = importlib.import_module("app.validators.programmatic")
        from app.validators import register
    except ImportError:
        return None
    lean_cls = getattr(module, "LeanChronology", None)
    if lean_cls is None:
        return None
    target = lean_dir_for(novel_id, base)
    if target is not None:
        register(lean_cls(lean_dir=target))
    return target


__all__ = ["PROVIDERS", "lean_dir_for", "register_all", "register_lean_for"]
