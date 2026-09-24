"""Guardrails and the policy engine (spec 009, block B5).

from app.policy import register_validators, PolicyEngine, find_forbidden, normalise
from app.policy import FORBIDDEN_WORD_LIMIT_REASON, MAX_FORBIDDEN_REWRITES
"""

from __future__ import annotations

from app.policy.engine import (
    FORBIDDEN_WORDS_POLICY,
    GUARDRAIL_SCORE,
    INJECTION_POLICY,
    PolicyDecision,
    PolicyEngine,
    injection_markers,
)
from app.policy.normalise import Match, Term, find_forbidden, normalise, term_variants
from app.policy.validators import (
    CHAPTER_VALIDATOR,
    FORBIDDEN_WORD_LIMIT_REASON,
    MAX_FORBIDDEN_REWRITES,
    SCENE_VALIDATOR,
    ForbiddenWordsValidator,
    register_validators,
    rewrite_instruction,
)

__all__ = [
    "CHAPTER_VALIDATOR",
    "FORBIDDEN_WORDS_POLICY",
    "FORBIDDEN_WORD_LIMIT_REASON",
    "GUARDRAIL_SCORE",
    "INJECTION_POLICY",
    "MAX_FORBIDDEN_REWRITES",
    "SCENE_VALIDATOR",
    "ForbiddenWordsValidator",
    "Match",
    "PolicyDecision",
    "PolicyEngine",
    "Term",
    "find_forbidden",
    "injection_markers",
    "normalise",
    "register_validators",
    "rewrite_instruction",
    "term_variants",
]
