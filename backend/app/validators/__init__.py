"""Contract K3: validators (interface by spec 005; concrete validators by spec 008, B4).

from app.validators import ValidationPoint, ValidationContext, ValidationResult
from app.validators import register, run_point
"""

from __future__ import annotations

from app.validators.protocol import (
    ValidationContext,
    ValidationPoint,
    ValidationResult,
    Validator,
)
from app.validators.registry import (
    SCORE_PREFIX,
    all_passed,
    clear_registry,
    register,
    run_point,
    unregister,
    validators_for,
)

__all__ = [
    "SCORE_PREFIX",
    "ValidationContext",
    "ValidationPoint",
    "ValidationResult",
    "Validator",
    "all_passed",
    "clear_registry",
    "register",
    "run_point",
    "unregister",
    "validators_for",
]
