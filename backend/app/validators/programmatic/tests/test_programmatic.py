"""Spec 008 — programmatic validators (B4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.bible import BibleRepository
from app.commons.observability import NoopObserver
from app.formal import find_lake
from app.validators import ValidationContext, ValidationPoint, unregister, validators_for
from app.validators.programmatic import (
    BriefCoverage,
    ChapterLength,
    ExactNames,
    FactUsageRecorder,
    LeanChronology,
    all_validators,
    register_validators,
)


def _ctx(repo: BibleRepository, novel_id: str, text: str, **extra: object) -> ValidationContext:
    return ValidationContext(
        novel_id=novel_id,
        version=1,
        chapter=1,
        scene=None,
        text=text,
        repo=repo,
        observer=NoopObserver(),
        extra=dict(extra),
    )


@pytest.fixture
def repo() -> BibleRepository:
    return BibleRepository.open(":memory:")


# spec 008 / AC 1 — V01
def test_chapter_length_boundaries(repo: BibleRepository) -> None:
    novel = repo.create_novel()
    brief = {"length": {"chapters": 3, "words_min": 10, "words_max": 20}}
    check = ChapterLength()
    results = {
        n: check.run(_ctx(repo, novel.id, "palabra " * n, brief=brief)) for n in (9, 10, 20, 21, 40)
    }
    assert not results[9].passed and "Añade unas 1" in results[9].explanation
    assert results[10].passed and results[10].score == 1.0
    assert results[20].passed
    assert not results[21].passed and "Recorta unas 1" in results[21].explanation
    assert results[40].score is not None and results[21].score is not None
    assert results[40].score < results[21].score < 1.0
    default = check.run(_ctx(repo, novel.id, "palabra " * 1000))
    assert default.passed  # default range 1000-1500


# spec 008 / AC 2 — V02
def test_exact_names_variants(repo: BibleRepository) -> None:
    novel = repo.create_novel(recipient_name="Lucía Pérez")
    repo.add_character(novel.id, name="Lucía Pérez")
    brief = {"pets": [{"name": "Toby", "species": "perro"}]}
    text = (
        "Lucía salió al jardín con Toby. Nada parecía raro. Pérez era su apellido.\n\n"
        "Más tarde, Lucia llamó a Tobby, pero no vino. Todo estaba en calma."
    )
    result = ExactNames().run(_ctx(repo, novel.id, text, brief=brief))
    assert not result.passed
    joined = " ".join(result.evidence)
    assert "'Lucia' → 'Lucía'" in joined
    assert "'Tobby' → 'Toby'" in joined
    assert "Nada" not in joined and "Todo" not in joined
    clean = ExactNames().run(_ctx(repo, novel.id, "Lucía y Toby. Nada más.", brief=brief))
    assert clean.passed


# spec 008 / AC 3 — V03, M01
def test_brief_coverage_in_memory(repo: BibleRepository) -> None:
    novel = repo.create_novel()
    repo.create_version(novel.id)
    repo.add_fact(
        novel.id, key="pet.nala.name", value="Nala", kind="pet", source="interview", mandatory=True
    )
    memory = repo.add_fact(
        novel.id,
        key="memory.viaje-a-lisboa",
        value="Viaje a Lisboa en tranvía amarillo: se perdieron y cenaron sardinas.",
        kind="memory",
        source="interview",
        mandatory=True,
    )
    plan = {
        "chapters": [
            {"number": 1, "facts": ["pet.nala.name"]},
            {"number": 2, "facts": ["memory.viaje-a-lisboa"]},
        ]
    }
    ch1 = "Nala ladró toda la mañana."
    repo.save_chapter_version(novel.id, 1, 1, text=ch1)
    FactUsageRecorder().run(_ctx(repo, novel.id, ch1))
    nala = repo.find_fact(novel.id, "pet.nala.name")
    assert nala is not None and repo.chapters_using_fact(nala.id, version=1) == [1]

    ctx = _ctx(repo, novel.id, "", plan=plan)
    ctx.chapter = None
    missing = BriefCoverage().run(ctx)
    assert not missing.passed
    assert any("memory.viaje-a-lisboa" in e and "capítulo 2" in e for e in missing.evidence)

    repo.save_chapter_version(novel.id, 1, 2, text="Recordaron Lisboa y aquel tranvía amarillo.")
    covered = BriefCoverage().run(ctx)
    assert covered.passed, covered.evidence
    assert repo.chapters_using_fact(memory.id, version=1) == [2]  # backfilled


# tuning iteration 1 (spec 008 / AC 3): memories match on normalised content words.
def test_memory_coverage_content_words(repo: BibleRepository) -> None:
    from app.validators.programmatic.coverage import fact_in_text
    from app.validators.programmatic.text import normalise

    novel = repo.create_novel()
    brief = {
        "recipient": {"name": "Martina"},
        "memories": [
            {
                "title": "El caracol campeón",
                "description": "Martina organizó una carrera de caracoles en el huerto y el "
                "más lento ganó porque los demás se fueron a comer lechuga.",
            }
        ],
    }
    fact = repo.add_fact(
        novel.id,
        key="memory.el-caracol-campeon",
        value="El caracol campeón: Martina organizó una carrera de caracoles en el huerto.",
        kind="memory",
        source="interview",
        mandatory=True,
    )
    # the title's words, plural and without accents: covered (before: exact phrase only)
    assert fact_in_text(fact, normalise("Los CARACOLES de Martina corrían."), brief)
    # the description's details (≥ 30 %), no title word: covered
    told = "La carrera en el huerto: el más lento ganó, los demás comían lechuga."
    assert fact_in_text(fact, normalise(told), brief)
    # only the recipient's name: not covered
    assert not fact_in_text(fact, normalise("Martina organizó una merienda."), brief)


def _registered_names() -> set[str]:
    register_validators()
    names = {v.name for point in ValidationPoint for v in validators_for(point)}
    for validator in all_validators():
        unregister(validator.name, validator.point)
    return names


# spec 008 / AC 4 — L03 (toolchain absent)
def test_lean_missing_toolchain(repo: BibleRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.formal.lean_runner as runner

    monkeypatch.setattr(runner, "find_lake", lambda: None)
    novel = repo.create_novel()
    result = LeanChronology().run(_ctx(repo, novel.id, ""))
    assert not result.passed and result.score == 0.0
    assert "Lean" in result.explanation
    assert "lean_chronology" in _registered_names()


# spec 008 / AC 4 — L03 (toolchain present)
@pytest.mark.skipif(find_lake() is None, reason="Lean toolchain (lake) not installed")
def test_lean_runs(repo: BibleRepository, tmp_path: Path) -> None:
    novel = repo.create_novel()
    ana = repo.add_character(novel.id, name="Ana", birth_date="1990-01-01")
    casa = repo.add_place(novel.id, name="Casa")
    repo.add_event(
        novel.id, seq=1, story_date="2020-06-01", chapter=1, place_id=casa.id, participants=[ana.id]
    )
    result = LeanChronology().run(_ctx(repo, novel.id, ""))
    assert result.passed, result.explanation


# spec 008 / AC 8 — calendar_consistency (tuning 2)
def test_calendar_consistency_weekdays(repo: BibleRepository) -> None:
    import datetime as dt

    from app.validators.programmatic.calendar import WEEKDAYS, CalendarConsistency

    novel = repo.create_novel()
    real = WEEKDAYS[dt.date(2026, 6, 21).weekday()]
    wrong = WEEKDAYS[(dt.date(2026, 6, 21).weekday() + 2) % 7]
    plan = {"chapters": [{"number": 1, "scenes": [{"story_date": "2026-06-21"}]}]}
    check = CalendarConsistency()
    bad = check.run(_ctx(repo, novel.id, f"El {wrong} 21 de junio de 2026 llovió.", plan=plan))
    assert not bad.passed
    assert f"«{wrong} 21 de junio de 2026»" in bad.explanation
    assert f"es {real}" in bad.explanation and "elimínalo" in bad.explanation
    # the year comes from the plan; the day may be written in words
    text = f"{wrong.capitalize()}, el veintiuno de junio."
    assert not check.run(_ctx(repo, novel.id, text, plan=plan)).passed
    text = f"El {real} 21 de junio de 2026 llovió. El 21 de junio, {real}."
    assert check.run(_ctx(repo, novel.id, text)).passed
    assert "calendar_consistency" in _registered_names()
