"""Spec 007 — the generation pipeline with a scripted fake model (no real model calls)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import JsonValue

from app.bible import BibleRepository
from app.commons.llm import FakeCall, FakeModelClient, Outcome, Reply
from app.commons.observability import NoopObserver
from app.commons.permissions import AgentRole
from app.novel._ingest_fallback import ingest_brief
from app.novel.models import (
    ChapterEdit,
    NovelPlan,
    PlanChapter,
    PlanCharacter,
    PlanEvent,
    PlanPlace,
    PlanScene,
    SceneDraft,
)
from app.novel.pipeline import change_fact, generate
from app.novel.placeholders import PLACEHOLDER
from app.novel.plan_check import check_plan
from app.validators import (
    ValidationContext,
    ValidationPoint,
    ValidationResult,
    clear_registry,
    register,
)

FIXTURE = Path(__file__).parent / "fixtures" / "brief_smoke.json"


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[BibleRepository]:
    clear_registry()
    with BibleRepository.open(tmp_path / "harness.sqlite") as repository:
        yield repository
    clear_registry()


def _brief(chapters: int) -> dict[str, JsonValue]:
    data: dict[str, JsonValue] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["length"] = {"chapters": chapters, "words_min": 1000, "words_max": 1500}
    return data


def _fact_keys(call: FakeCall) -> list[str]:
    doc = next(d for d in call.documents if d.path == "bible/facts.txt")
    return [line.split(" | ")[0] for line in doc.text.splitlines()]


def _plan(call: FakeCall, chapters: int) -> NovelPlan:
    keys = _fact_keys(call)
    scenes = [
        PlanScene(
            chapter=c,
            scene=s,
            summary=f"escena {c}.{s}",
            place="Casa",
            characters=["Marta", "Toby"],
            story_date=f"2024-0{c}-1{s}",
            facts_used=keys if (c, s) == (1, 1) else [],
            word_budget=400,
        )
        for c in range(1, chapters + 1)
        for s in range(1, 4)
    ]
    events = [
        PlanEvent(
            seq=i,
            chapter=sc.chapter,
            scene=sc.scene,
            story_date=sc.story_date,
            place="Casa",
            description=sc.summary,
            participants=["Marta"],
        )
        for i, sc in enumerate(scenes, start=1)
    ]
    return NovelPlan(
        title="El verano de Marta",
        synopsis="Una historia.",
        characters=[
            PlanCharacter(name="Marta", role="protagonista"),
            PlanCharacter(name="Toby", role="perro"),
            PlanCharacter(name="Lucas", role="hermano"),
        ],
        places=[PlanPlace(name="Casa")],
        chapters=[
            PlanChapter(number=c, title=f"Capítulo {c}", synopsis="...", arc_role="rising")
            for c in range(1, chapters + 1)
        ],
        scenes=scenes,
        events=events,
    )


def _prose(words: int) -> str:
    return " ".join(["Marta paseaba con Toby y su hermano Lucas junto al mar."] * (words // 10))


def fake(chapters: int, *, crash_on_editor: int | None = None) -> FakeModelClient:
    editor_calls = {"n": 0}

    def answer(call: FakeCall) -> Outcome:
        if call.role is AgentRole.PLANNER:
            return Reply.of(_plan(call, chapters))
        if call.role is AgentRole.WRITER:
            return Reply.of(SceneDraft(text=_prose(400)))
        editor_calls["n"] += 1
        if crash_on_editor is not None and editor_calls["n"] == crash_on_editor:
            message = "simulated crash"
            raise KeyboardInterrupt(message)
        return Reply.of(
            ChapterEdit(title="Un día", text=_prose(1200), summary="Resumen.", issues=[])
        )

    return FakeModelClient(fallback=answer)


def _roles(client: FakeModelClient) -> list[AgentRole]:
    return [c.role for c in client.calls]


# spec 007 / AC 1, AC 5
def test_happy_path_two_chapters(repo: BibleRepository) -> None:
    novel_id = ingest_brief(repo, _brief(2))
    client = fake(2)
    result = generate(repo, novel_id, client=client, observer=NoopObserver(), register=False)
    assert result.status == "published", result.detail
    chapters = repo.list_chapters(novel_id, result.version)
    assert [c.chapter for c in chapters] == [1, 2]
    assert all(1000 <= c.word_count <= 1500 for c in chapters)
    roles = _roles(client)
    assert roles.count(AgentRole.PLANNER) == 1
    assert roles.count(AgentRole.WRITER) == 6
    assert roles.count(AgentRole.EDITOR) == 2
    writer_call = next(c for c in client.calls if c.role is AgentRole.WRITER)
    assert "Marta" not in writer_call.system  # data never in the system prompt
    assert repo.get_novel(novel_id).title == "El verano de Marta"
    assert len(repo.list_events(novel_id)) == 6
    assert repo.cost_summary(novel_id).calls == 9


# spec 007 / AC 3
def test_resume_no_duplicate(repo: BibleRepository) -> None:
    novel_id = ingest_brief(repo, _brief(2))
    with pytest.raises(KeyboardInterrupt):
        generate(
            repo,
            novel_id,
            client=fake(2, crash_on_editor=2),
            observer=NoopObserver(),
            register=False,
        )
    version = repo.latest_version(novel_id)
    assert version is not None
    first = repo.get_chapter(novel_id, version.version, 1)
    assert first is not None
    assert repo.first_incomplete_chapter(novel_id, version.version, total_chapters=2) == 2

    client = fake(2)
    result = generate(repo, novel_id, client=client, observer=NoopObserver(), register=False)
    assert result.status == "published"
    assert result.version == version.version
    assert _roles(client) == [AgentRole.WRITER] * 3 + [AgentRole.EDITOR]  # plan reused
    again = repo.get_chapter(novel_id, version.version, 1)
    assert again is not None
    assert again.hash == first.hash
    assert len(repo.list_chapters(novel_id, version.version)) == 2
    assert len(repo.list_events(novel_id)) == 6  # plan persistence is idempotent


class _AlwaysFails:
    name = "always_fails"
    point = ValidationPoint.CHAPTER_CLOSE

    def run(self, ctx: ValidationContext) -> ValidationResult:
        return ValidationResult(self.name, False, 0.0, ["x"], f"falla el capítulo {ctx.chapter}")


# spec 007 / AC 2
def test_chapter_retries_bounded(repo: BibleRepository) -> None:
    register(_AlwaysFails())
    novel_id = ingest_brief(repo, _brief(1))
    client = fake(1)
    result = generate(repo, novel_id, client=client, observer=NoopObserver(), register=False)
    assert result.status == "stopped_error"
    assert "chapter_retry_limit" in result.detail
    assert repo.count_chapter_attempts(novel_id, result.version, 1) == 3  # 1 + 2 retries
    assert len(repo.list_chapter_attempts(novel_id, result.version, 1)) == 3
    assert _roles(client).count(AgentRole.EDITOR) == 3
    assert repo.get_novel(novel_id).status == "stopped_error"
    # CE2: a restart does not buy a fresh budget.
    again = generate(repo, novel_id, client=fake(1), observer=NoopObserver(), register=False)
    assert again.status == "stopped_error"
    assert repo.count_chapter_attempts(novel_id, result.version, 1) == 3


# spec 007 / AC 5
def test_plan_check_names_missing_facts() -> None:
    plan = NovelPlan(
        title="t",
        synopsis="s",
        characters=[],
        places=[],
        chapters=[],
        scenes=[],
        events=[],
    )
    problems = check_plan(
        plan, chapters=1, mandatory_keys=["pet.toby.name"], known_keys=["pet.toby.name"]
    )
    assert any("pet.toby.name" in p for p in problems)
    assert any("chapters must be numbered" in p for p in problems)


# spec 007 / AC 1 — anonymised names are rejected at scene_accept and chapter_close
def test_placeholder_guard() -> None:
    assert PLACEHOLDER.search("Entonces [NOMBRE_ANONIMIZADO] sonrió.")
    assert PLACEHOLDER.search("[PERSONA] y Toby") is not None
    assert PLACEHOLDER.search("Marta [sonrió] en 2024 [1]") is None


# spec 007 / AC 4 (clarified): change_fact is one transaction, as TLA+ `ChangeFact` assumes.
def test_change_fact_rolls_back_when_the_version_cannot_be_created(
    repo: BibleRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    novel_id = ingest_brief(repo, _brief(1))
    result = generate(repo, novel_id, client=fake(1), observer=NoopObserver(), register=False)
    assert result.status == "published", result.detail
    pet = next(f for f in repo.list_facts(novel_id) if f.value == "Toby")
    brief_before = repo.get_brief(novel_id)
    versions_before = len(repo.list_versions(novel_id))

    def boom(*_: object, **__: object) -> object:
        message = "simulated failure inside create_version_from"
        raise RuntimeError(message)

    monkeypatch.setattr(repo, "create_version_from", boom)
    with pytest.raises(RuntimeError, match="simulated failure"):
        change_fact(
            repo, novel_id, pet.key, "Nala", client=fake(1), observer=NoopObserver(), register=False
        )
    assert repo.get_fact(pet.id).value == "Toby"
    assert "Nala" not in {c.name for c in repo.list_characters(novel_id)}
    assert repo.get_brief(novel_id) == brief_before
    assert len(repo.list_versions(novel_id)) == versions_before
    assert not repo.connection.in_transaction
