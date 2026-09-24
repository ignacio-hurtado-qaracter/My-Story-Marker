"""Spec 017: the read-only tool layer."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.bible import BibleRepository
from app.commons.observability import NoopObserver
from app.tools import REGISTRY, ToolInputError, ToolNotFoundError, call_tool
from app.tools.models import ChapterOutput, ListNovelsOutput, QueryStoryBibleOutput


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[BibleRepository]:
    with BibleRepository.open(tmp_path / "harness.sqlite") as repository:
        novel = repository.create_novel(novel_id="nov-t", title="El faro", recipient_name="Ana")
        repository.add_character(novel.id, name="Ana", role="protagonista")
        repository.add_fact(
            novel.id, key="pet.nala.name", value="Nala", kind="pet", source="interview"
        )
        repository.add_fact(
            novel.id, key="plan.note", value="secret", kind="plan", source="planner"
        )
        repository.create_version(novel.id)
        repository.save_chapter_and_checkpoint(
            novel.id, 1, 1, text="Ana subió al faro.", title="Uno", summary="Ana sube."
        )
        yield repository


# spec 017 / AC 1
def test_invalid_input_is_rejected(repo: BibleRepository) -> None:
    for tool in REGISTRY.values():
        assert tool.input_schema["type"] == "object"
        assert tool.output_schema["type"] == "object"
    bad: list[tuple[str, dict[str, object]]] = [
        ("get_chapter", {"novel_id": "nov-t", "version": 0, "chapter": 1}),
        ("get_chapter", {"novel_id": "nov-t", "version": 1}),
        ("query_story_bible", {"novel_id": "nov-t", "kind": "spells"}),
        ("list_novels", {"unexpected": True}),
        ("no_such_tool", {}),
    ]
    for name, raw in bad:
        with pytest.raises(ToolInputError):
            call_tool(name, repo, raw)
    with pytest.raises(ToolNotFoundError):
        call_tool("get_chapter", repo, {"novel_id": "nov-t", "version": 1, "chapter": 9})


# spec 017 / AC 2 (and AC 3: the call is a `tool:<name>` span)
def test_list_novels_and_get_chapter(repo: BibleRepository) -> None:
    observer = NoopObserver()
    novels = call_tool("list_novels", repo, {}, observer=observer)
    assert isinstance(novels, ListNovelsOutput)
    assert [(n.id, n.title, n.latest_version) for n in novels.novels] == [("nov-t", "El faro", 1)]

    chapter = call_tool(
        "get_chapter", repo, {"novel_id": "nov-t", "version": 1, "chapter": 1}, observer=observer
    )
    assert isinstance(chapter, ChapterOutput)
    assert (chapter.title, chapter.text, chapter.summary) == (
        "Uno",
        "Ana subió al faro.",
        "Ana sube.",
    )

    facts = call_tool("query_story_bible", repo, {"novel_id": "nov-t", "kind": "facts"})
    assert isinstance(facts, QueryStoryBibleOutput)
    assert [f.key for f in facts.facts] == ["pet.nala.name"]  # `plan` facts hidden
    assert observer.spans == ["tool:list_novels", "tool:get_chapter"]
