"""Spec 009 — the forbidden-words guardrail: levels, variants, audit log, validator."""

from __future__ import annotations

import pytest

from app.bible import BibleRepository
from app.commons.observability import NoopObserver
from app.policy import (
    CHAPTER_VALIDATOR,
    GUARDRAIL_SCORE,
    SCENE_VALIDATOR,
    PolicyEngine,
    Term,
    find_forbidden,
    register_validators,
)
from app.validators import ValidationContext, ValidationPoint, clear_registry, validators_for


@pytest.fixture
def repo() -> BibleRepository:
    return BibleRepository.open(":memory:")


# spec 009 / AC 1, AC 4, AC 5 — global level (seeded by migration 1300) and the audit log
def test_global_term_rejects_and_is_logged(repo: BibleRepository) -> None:
    observer = NoopObserver()
    novel = repo.create_novel(title="Prueba", recipient_name="Ana")
    decision = PolicyEngine(repo, observer).check_text(
        novel.id, "Le gritó: ¡eres un IMBÉCIL!", version=1, chapter=2
    )
    assert decision.decision == "reject"
    assert decision.terms == ["imbécil"]
    rows = repo.list_policy_decisions(novel.id)
    assert [(r.policy, r.decision, r.term, r.chapter) for r in rows] == [
        ("forbidden_words", "reject", "imbécil", 2)
    ]
    assert observer.scores[-1].name == GUARDRAIL_SCORE
    assert observer.scores[-1].value == 0.0
    assert "imbécil" in (observer.scores[-1].comment or "")

    clean = PolicyEngine(repo, observer).check_text(novel.id, "Un día tranquilo en el mar.")
    assert clean.allowed
    assert repo.list_policy_decisions(novel.id)[-1].decision == "allow"


# spec 009 / AC 1, AC 3, AC 5 — novel level, through the registered chapter validator
def test_novel_term_fails_chapter_validator(repo: BibleRepository) -> None:
    novel = repo.create_novel(title="Prueba", recipient_name="Ana")
    other = repo.create_novel(title="Otra", recipient_name="Luis")
    repo.add_forbidden_term("Marcos Pérez", scope="novel", novel_id=novel.id, reason="expareja")
    clear_registry()
    register_validators()
    [validator] = validators_for(ValidationPoint.CHAPTER_CLOSE)
    assert validator.name == CHAPTER_VALIDATOR
    assert [v.name for v in validators_for(ValidationPoint.SCENE_ACCEPT)] == [SCENE_VALIDATOR]

    text = "Aquella tarde apareció marcos perez en la puerta."
    ctx = ValidationContext(novel.id, 1, 3, None, text, repo, NoopObserver())
    result = validator.run(ctx)
    assert not result.passed
    assert "«Marcos Pérez»" in result.explanation
    assert "Reescríbelo" in result.explanation
    ctx_other = ValidationContext(other.id, 1, 3, None, text, repo, NoopObserver())
    assert validator.run(ctx_other).passed  # the novel's term does not leak to others
    clear_registry()


# spec 009 / AC 2, AC 5 — accent, plural and simple variants; the lexicon (third) level
@pytest.mark.parametrize(
    ("text", "term"),
    [
        ("Eres un estupido.", "estúpido"),
        ("Eres un estúpido.", "estupido"),
        ("No seáis tontos.", "tonto"),
        ("Qué tontooo eres.", "tonto"),
        ("Eres un t0nt0.", "tonto"),
        ("Eres un t.o.n.t.o de verdad.", "tonto"),
        ("Brillaban las luces.", "luz"),
        ("Menudos cabrones.", "cabrón"),
    ],
)
def test_variants_are_found(text: str, term: str) -> None:
    [match] = find_forbidden(text, [Term(term, "lexicon")])
    assert match.level == "lexicon"
    assert match.term == term
    assert text[match.span[0] : match.span[1]] == match.surface


# spec 009 / AC 2 — whole words only: no false positive inside a longer word
@pytest.mark.parametrize(
    ("text", "term"),
    [
        ("Fue una tontería sin importancia.", "tonto"),
        ("Un sombrero ridículo.", "culo"),
        ("Pero el perro no vino.", "perro"),
    ],
)
def test_no_false_positive_inside_words(text: str, term: str) -> None:
    hits = find_forbidden(text, [term])
    assert [m.surface for m in hits] == (["perro"] if term == "perro" else [])
