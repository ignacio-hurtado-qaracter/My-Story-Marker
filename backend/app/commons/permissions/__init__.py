"""The permission layer: the six roles, Figure 3's two tables, and the checks that read them.

Import from here rather than from the submodules. The split inside is by table -- who may
write what (`table`), what may be placed in a role's prompt (`inputs`), and the tool sets
derived from the first (`toolsets`, plan step 16) -- and that split is an implementation
detail of this package, not part of its surface.
"""

from __future__ import annotations

from app.commons.permissions.inputs import INPUT_TABLE, may_receive, readable_patterns
from app.commons.permissions.roles import Actor, AgentRole
from app.commons.permissions.table import (
    SCENE_FILE,
    STORE_FAMILIES,
    WRITE_TABLE,
    compile_store_glob,
    may_write,
    normalise,
    writable_patterns,
)

__all__ = [
    "INPUT_TABLE",
    "SCENE_FILE",
    "STORE_FAMILIES",
    "WRITE_TABLE",
    "Actor",
    "AgentRole",
    "compile_store_glob",
    "may_receive",
    "may_write",
    "normalise",
    "readable_patterns",
    "writable_patterns",
]
