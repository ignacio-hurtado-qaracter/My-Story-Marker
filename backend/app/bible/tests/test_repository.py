"""Spec 005 — K1 round trips."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.bible import BibleRepository, VersionFrozenError, text_hash
from app.commons.db.authoritative import applied_migrations


@pytest.fixture
def repo(tmp_path: Path) -> BibleRepository:
    return BibleRepository.open(tmp_path / "harness.sqlite")


# spec 005 / AC 1 — M01
def test_fact_usage_roundtrip(repo: BibleRepository) -> None:
    assert applied_migrations(repo.connection) == ["1000_init"]
    assert repo.connection.execute("pragma journal_mode").fetchone()[0] == "wal"
    novel = repo.create_novel(title="El verano de Lucía", recipient_name="Lucía")
    assert novel.session_id == novel.id
    repo.save_brief(novel.id, {"recipient": {"name": "Lucía", "age": 34}}, valid=True)
    brief = repo.get_brief(novel.id)
    assert brief is not None
    assert brief.data == {"recipient": {"name": "Lucía", "age": 34}}

    dog = repo.add_fact(
        novel.id, key="pet.name", value="Toby", kind="pet", source="interview", mandatory=True
    )
    repo.record_fact_usage(dog.id, chapter=2, scene=1)
    repo.record_fact_usage(dog.id, chapter=2, scene=3)
    repo.record_fact_usage(dog.id, chapter=7, scene=2)
    repo.record_fact_usage(dog.id, chapter=7, scene=2)  # idempotent

    assert repo.chapters_using_fact(dog.id) == [2, 7]
    assert len(repo.fact_usages(dog.id)) == 3
    assert repo.update_fact_value(dog.id, "Nala").value == "Nala"
    assert [f.key for f in repo.list_facts(novel.id, mandatory=True)] == ["pet.name"]

    repo.add_forbidden_term("violencia", scope="global")
    repo.add_forbidden_term("exmarido", scope="novel", novel_id=novel.id)
    repo.add_forbidden_term("exmarido", scope="novel", novel_id=novel.id)
    assert sorted(t.term for t in repo.list_forbidden_terms(novel.id)) == ["exmarido", "violencia"]
    assert [t.term for t in repo.list_forbidden_terms()] == ["violencia"]


# spec 005 / AC 2 — M02
def test_chronology_json_format(repo: BibleRepository) -> None:
    novel = repo.create_novel(novel_id="n1")
    lucia = repo.add_character(novel.id, name="Lucía", birth_date="1990-05-12")
    abuelo = repo.add_character(novel.id, name="Abuelo Tomás")
    valencia = repo.add_place(novel.id, name="Valencia")
    repo.add_event(
        novel.id,
        seq=1,
        story_date="2020-06-01",
        place_id=valencia.id,
        participants={lucia.id: 30, abuelo.id: None},
        chapter=1,
        description="Lucía vuelve a casa.",
    )
    repo.add_event(novel.id, seq=2, participants=[abuelo.id], kind="death", chapter=4)

    assert repo.chronology_json(novel.id) == {
        "novel_id": "n1",
        "characters": [
            {"id": "c1", "name": "Lucía", "birth_date": "1990-05-12"},
            {"id": "c2", "name": "Abuelo Tomás", "birth_date": None},
        ],
        "places": [{"id": "p1", "name": "Valencia"}],
        "events": [
            {
                "id": "e1",
                "seq": 1,
                "story_date": "2020-06-01",
                "place_id": "p1",
                "participants": ["c1", "c2"],
                "kind": "normal",
                "declared_ages": {"c1": 30},
                "chapter": 1,
                "description": "Lucía vuelve a casa.",
            },
            {
                "id": "e2",
                "seq": 2,
                "story_date": None,
                "place_id": None,
                "participants": ["c2"],
                "kind": "death",
                "declared_ages": {},
                "chapter": 4,
                "description": "",
            },
        ],
    }


# spec 005 / AC 3 — R07
def test_versions_keep_parent(repo: BibleRepository) -> None:
    novel = repo.create_novel()
    v1 = repo.create_version(novel.id)
    for chapter in (1, 2):
        repo.save_chapter_version(novel.id, v1.version, chapter, text=f"Capítulo {chapter}.")
        repo.set_checkpoint(novel.id, v1.version, chapter, "complete")
    assert repo.first_incomplete_chapter(novel.id, v1.version) == 3
    repo.set_version_status(novel.id, v1.version, "published")
    with pytest.raises(VersionFrozenError):
        repo.save_chapter_version(novel.id, v1.version, 1, text="overwrite")

    v2 = repo.create_version(novel.id, parent=v1.version, note="el perro se llama Nala")
    assert v2.version == 2
    assert v2.parent_version == 1
    repo.save_chapter_version(novel.id, v2.version, 2, text="Capítulo 2 con Nala.")
    published = repo.set_version_status(novel.id, v2.version, "published")
    assert published.changed_chapters == (2,)

    old = repo.get_chapter(novel.id, 1, 2)
    assert old is not None
    assert old.text == "Capítulo 2."
    assert old.hash == text_hash("Capítulo 2.")
    assert [v.status for v in repo.list_versions(novel.id)] == ["published", "published"]
