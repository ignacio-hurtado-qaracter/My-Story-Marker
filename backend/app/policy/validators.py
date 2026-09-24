"""The forbidden-words validators (spec 009, contract K3).

Two registrations of one check: `forbidden_words_scene` at `scene_accept` and
`forbidden_words_chapter` at `chapter_close`. A failure's explanation lists the offending
terms and asks the writer for a rewrite without them. The pipeline (B3) sends it back at
most `MAX_FORBIDDEN_REWRITES` times; exhausted, it stops with `FORBIDDEN_WORD_LIMIT_REASON`.

`ctx.extra` keys read here: `lexicon_forbidden` (list of str, third level, optional) and
`attempt` (int, optional, recorded in the policy log).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.policy.engine import PolicyEngine
from app.policy.normalise import Term
from app.validators import ValidationContext, ValidationPoint, ValidationResult, register

FORBIDDEN_WORD_LIMIT_REASON: Final[str] = "forbidden_word_limit"
MAX_FORBIDDEN_REWRITES: Final[int] = 2
"""`MAX_SCENE_RETRIES` of docs/verification.md, Guardrails."""

SCENE_VALIDATOR: Final[str] = "forbidden_words_scene"
CHAPTER_VALIDATOR: Final[str] = "forbidden_words_chapter"


def rewrite_instruction(terms: list[str]) -> str:
    """The feedback the writer receives on a match."""
    listed = ", ".join(f"«{t}»" for t in terms)
    return (
        f"El texto contiene términos prohibidos: {listed}. Reescríbelo sin ellos, "
        "sin sus plurales, variantes ni alusiones evidentes, conservando el resto."
    )


def _lexicon(ctx: ValidationContext) -> list[Term]:
    raw = ctx.extra.get("lexicon_forbidden")
    if not isinstance(raw, list):
        return []
    return [Term(item, "lexicon") for item in raw if isinstance(item, str) and item.strip()]


@dataclass(frozen=True, slots=True)
class ForbiddenWordsValidator:
    """K3 validator over the three forbidden-term levels."""

    name: str
    point: ValidationPoint

    def run(self, ctx: ValidationContext) -> ValidationResult:
        attempt = ctx.extra.get("attempt")
        decision = PolicyEngine(ctx.repo, ctx.observer).check_text(
            ctx.novel_id,
            ctx.text,
            version=ctx.version,
            chapter=ctx.chapter,
            scene=ctx.scene,
            extra_terms=_lexicon(ctx),
            attempt=attempt if isinstance(attempt, int) else None,
            trace_id=ctx.trace_id,
            source=self.name,
        )
        if decision.allowed:
            return ValidationResult(
                name=self.name, passed=True, score=1.0, explanation="sin términos prohibidos"
            )
        evidence = [
            f"{m.level}:{m.term} ← «{m.surface}» [{m.span[0]}:{m.span[1]}]"
            for m in decision.matches
        ]
        return ValidationResult(
            name=self.name,
            passed=False,
            score=0.0,
            evidence=evidence,
            explanation=rewrite_instruction(decision.terms),
        )


FORBIDDEN_WORDS_SCENE: Final[ForbiddenWordsValidator] = ForbiddenWordsValidator(
    SCENE_VALIDATOR, ValidationPoint.SCENE_ACCEPT
)
FORBIDDEN_WORDS_CHAPTER: Final[ForbiddenWordsValidator] = ForbiddenWordsValidator(
    CHAPTER_VALIDATOR, ValidationPoint.CHAPTER_CLOSE
)


def register_validators() -> None:
    """Register both validators with K3 (idempotent)."""
    register(FORBIDDEN_WORDS_SCENE)
    register(FORBIDDEN_WORDS_CHAPTER)


__all__ = [
    "CHAPTER_VALIDATOR",
    "FORBIDDEN_WORDS_CHAPTER",
    "FORBIDDEN_WORDS_SCENE",
    "FORBIDDEN_WORD_LIMIT_REASON",
    "MAX_FORBIDDEN_REWRITES",
    "SCENE_VALIDATOR",
    "ForbiddenWordsValidator",
    "register_validators",
    "rewrite_instruction",
]
