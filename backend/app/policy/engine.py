"""The policy engine (spec 009): forbidden words and free-text injection markers.

Every decision is written to the policy decision log (`policy_decision`, K1) — a reject as
one row per distinct term, an allow as one summary row — and scored in Langfuse (K2) as
`guardrail:forbidden_words` (1 allow, 0 reject, terms in the comment). The engine decides
and records; it never rewrites. Sending the text back to the writer is the pipeline's job.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from app.bible import BibleRepository
from app.commons.observability import NoopObserver, Observer
from app.policy.normalise import Match, Term, find_forbidden, normalise

FORBIDDEN_WORDS_POLICY: Final[str] = "forbidden_words"
INJECTION_POLICY: Final[str] = "free_text_injection"
GUARDRAIL_SCORE: Final[str] = "guardrail:forbidden_words"
INJECTION_SCORE: Final[str] = "guardrail:free_text_injection"

Decision = Literal["allow", "reject", "flag"]

# Matched against `normalise(text)`: lower case, no accents, tokens separated by one space.
_W: Final[str] = r"(?:\w+ ){0,3}"
_INJECTION_MARKERS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (label, re.compile(pattern))
    for label, pattern in (
        ("ignore_instructions", rf"\bignor\w* {_W}(?:instruc\w*|reglas|normas|rules)\b"),
        (
            "forget_previous",
            rf"\b(?:olvida\w*|forget|disregard) {_W}(?:anterior\w*|previous|above)\b",
        ),
        ("role_override", r"\b(?:ahora eres|you are now|act as|actua como)\b"),
        ("system_prompt", r"\b(?:system prompt|prompt del sistema|developer mode)\b"),
        ("jailbreak", r"\b(?:jailbreak|dan mode)\b"),
        ("store_write", rf"\b(?:escribe en|write to) {_W}(?:canon|base de datos|database)\b"),
        ("reveal_secrets", r"\b(?:api key|clave api|contrasena|password)\b"),
    )
)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """What the engine decided about one text."""

    policy: str
    decision: Decision
    matches: tuple[Match, ...] = ()
    markers: tuple[str, ...] = ()
    detail: str = ""
    log_ids: tuple[int, ...] = field(default=())

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"

    @property
    def terms(self) -> list[str]:
        """Distinct offending terms, in order of first appearance."""
        return list(dict.fromkeys(m.term for m in self.matches))


def injection_markers(text: str) -> list[str]:
    """Labels of the prompt-injection markers found in `text` (pure; B2 may reuse it)."""
    key = normalise(text)
    return [label for label, pattern in _INJECTION_MARKERS if pattern.search(key)]


def _terms_comment(matches: Sequence[Match]) -> str:
    by_term: dict[str, list[str]] = {}
    for match in matches:
        by_term.setdefault(match.term, []).append(match.surface)
    return "; ".join(f"{term} ({', '.join(dict.fromkeys(s))})" for term, s in by_term.items())


class PolicyEngine:
    """Checks text against the forbidden-term levels and logs every decision."""

    def __init__(self, repo: BibleRepository, observer: Observer | None = None) -> None:
        self._repo = repo
        self._observer: Observer = observer if observer is not None else NoopObserver()

    def terms_for(self, novel_id: str | None, extra: Iterable[Term] = ()) -> list[Term]:
        """Global terms, the novel's own, and any extra (lexicon) terms."""
        stored = [
            Term(t.term, "novel" if t.scope == "novel" else "global")
            for t in self._repo.list_forbidden_terms(novel_id)
        ]
        return [*stored, *extra]

    def check_text(
        self,
        novel_id: str | None,
        text: str,
        *,
        version: int | None = None,
        chapter: int | None = None,
        scene: int | None = None,
        extra_terms: Iterable[Term] = (),
        attempt: int | None = None,
        trace_id: str | None = None,
        source: str = "",
    ) -> PolicyDecision:
        """Forbidden words in `text`; `allow` when none, `reject` with the matches otherwise."""
        terms = self.terms_for(novel_id, extra_terms)
        matches = tuple(find_forbidden(text, terms))
        trace = trace_id or self._observer.current_trace_id()
        where = {"source": source} if source else {}
        ids: list[int] = []
        if matches:
            decision: Decision = "reject"
            for term in dict.fromkeys(m.term for m in matches):
                hits = [m for m in matches if m.term == term]
                detail = json.dumps(
                    {
                        "level": hits[0].level,
                        "surfaces": list(dict.fromkeys(m.surface for m in hits)),
                        "spans": [list(m.span) for m in hits],
                        **where,
                    },
                    ensure_ascii=False,
                )
                ids.append(
                    self._repo.log_policy_decision(
                        policy=FORBIDDEN_WORDS_POLICY,
                        decision="reject",
                        novel_id=novel_id,
                        version=version,
                        chapter=chapter,
                        scene=scene,
                        term=term,
                        detail=detail,
                        attempt=attempt,
                        trace_id=trace,
                    )
                )
            comment = f"reject: {_terms_comment(matches)}"
        else:
            decision = "allow"
            summary = {"terms_checked": len(terms), "words": len(text.split()), **where}
            ids.append(
                self._repo.log_policy_decision(
                    policy=FORBIDDEN_WORDS_POLICY,
                    decision="allow",
                    novel_id=novel_id,
                    version=version,
                    chapter=chapter,
                    scene=scene,
                    detail=json.dumps(summary),
                    attempt=attempt,
                    trace_id=trace,
                )
            )
            comment = f"allow: {len(terms)} terms checked"
        self._observer.score(
            GUARDRAIL_SCORE, 0.0 if matches else 1.0, comment=comment[:1000], trace_id=trace
        )
        return PolicyDecision(
            policy=FORBIDDEN_WORDS_POLICY,
            decision=decision,
            matches=matches,
            detail=comment,
            log_ids=tuple(ids),
        )

    def check_free_text(self, novel_id: str | None, text: str) -> PolicyDecision:
        """Injection markers in client free text. `flag` means: treat it as data only."""
        markers = tuple(injection_markers(text))
        decision: Decision = "flag" if markers else "allow"
        detail = json.dumps({"markers": list(markers), "chars": len(text)})
        log_id = self._repo.log_policy_decision(
            policy=INJECTION_POLICY, decision=decision, novel_id=novel_id, detail=detail
        )
        self._observer.score(
            INJECTION_SCORE,
            0.0 if markers else 1.0,
            comment=f"{decision}: {', '.join(markers) or 'no markers'}",
        )
        return PolicyDecision(
            policy=INJECTION_POLICY,
            decision=decision,
            markers=markers,
            detail=detail,
            log_ids=(log_id,),
        )


__all__ = [
    "FORBIDDEN_WORDS_POLICY",
    "GUARDRAIL_SCORE",
    "INJECTION_POLICY",
    "INJECTION_SCORE",
    "Decision",
    "PolicyDecision",
    "PolicyEngine",
    "injection_markers",
]
