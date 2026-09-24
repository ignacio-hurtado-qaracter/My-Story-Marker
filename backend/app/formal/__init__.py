"""Formal verification of the story. Spec 012 (B8): the Lean 4 chronology check.

Public surface: ``export_lean`` (chronology JSON → Lean source) and ``verify_chronology``
(Lean source → ``lake build`` → ``LeanResult``).
"""

from app.formal.lean_export import INVARIANTS, ChronologyError, export_lean
from app.formal.lean_runner import LeanResult, find_lake, verify_chronology

__all__ = [
    "INVARIANTS",
    "ChronologyError",
    "LeanResult",
    "export_lean",
    "find_lake",
    "verify_chronology",
]
