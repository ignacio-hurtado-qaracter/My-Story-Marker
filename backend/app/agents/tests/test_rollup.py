"""FR-AGENT-08, IF-06 -- rolling digests up the ladder, and `POST /agents/digests/rollup`.

The fixture (README "Digests and the as-of rule") has scene digests for 002 and 003 only, and
chapter digests 901 (ch01, 001-003) and 902 (ch02, 004-006), so:

* ch01 is **partial** until a digest of scene 001 is written, and must be refused -- a rollup
  of two scenes out of three would read as the whole chapter;
* the arc `ar_descent` is complete at chapter level and rolls up into 990, the file the
  fixture already carries for it.

Filing follows the fixture's convention: the k-th chapter of `structure/chapters.yaml` under
`900 + k`, the k-th arc under `989 + k`. `scene_ref` is the min-max range of the covered scene
ids, and `povs` the POVs of the covered scene records, in order, each once.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents import service
from app.agents.roles import writer
from app.commons.deps import get_model_client
from app.commons.errors import InvalidRecord, NotFound
from app.commons.llm import FakeModelClient, Reply
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import DigestLevel, DigestOutput, SceneDigest
from app.commons.stores import Store, paths
from app.manuscript import service as manuscript_service

CHAPTER = DigestOutput(delta="Every lawful road into the vault closes.", povs=["vance", "ilan"])
ARC = DigestOutput(delta="Vance stops buying the vault and pays for it.", povs=["vance"])


def write_scene_digest(store: Store, scene: str, pov: str) -> None:
    """The digest a finished turn would have left for `scene`, written as the writer."""
    record = SceneDigest(
        scene_ref=scene, level=DigestLevel.SCENE, povs=[pov], delta="What changed.", words=0
    )
    manuscript_service.save_digest(store, scene, record, role=AgentRole.WRITER, actor=Actor.AGENT)


def use(client: TestClient, fake: FakeModelClient) -> None:
    app = client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_model_client] = lambda: fake


# spec 001 / FR-AGENT-08 -- a partial chapter is refused before any call.
def test_a_chapter_with_a_scene_digest_missing_is_refused(fixture_store: Store) -> None:
    client = FakeModelClient()
    with pytest.raises(NotFound) as refused:
        writer.rollup(fixture_store, client, chapter_id="ch01")
    assert "manuscript/digests/001.md" in refused.value.message
    assert client.calls == []
    with pytest.raises(NotFound):
        writer.rollup(fixture_store, client, chapter_id="ch02")
    assert client.calls == []


# spec 001 / FR-AGENT-08 -- a complete chapter rolls into 900 + k, its range and its POVs.
def test_a_complete_chapter_rolls_up_into_its_chapter_digest(fixture_store: Store) -> None:
    write_scene_digest(fixture_store, "001", "vance")
    client = FakeModelClient([Reply.of(CHAPTER)])
    result = writer.rollup(fixture_store, client, chapter_id="ch01")
    [call] = client.calls
    assert call.role is AgentRole.WRITER
    assert [document.path for document in call.documents] == [
        "manuscript/digests/001.md",
        "manuscript/digests/002.md",
        "manuscript/digests/003.md",
    ]
    assert "about 250 words" in call.instruction
    assert result.digest_id == "901"
    assert result.record.level is DigestLevel.CHAPTER
    assert result.record.scene_ref == "001-003"
    assert result.record.povs == ["vance", "ilan"]
    assert result.povs_agree

    record = service.persist_digest(fixture_store, result)
    assert (record.path, record.role, record.actor) == (
        "manuscript/digests/901.md",
        AgentRole.WRITER,
        Actor.AGENT,
    )
    written = fixture_store.read(paths.digest("901"), SceneDigest)
    assert written.delta == CHAPTER.delta
    assert written.words == 7


# spec 001 / FR-AGENT-08 -- an arc rolls its chapter digests into 989 + k.
def test_an_arc_rolls_up_its_chapter_digests(fixture_store: Store) -> None:
    client = FakeModelClient([Reply.of(ARC)])
    result = writer.rollup(fixture_store, client, arc_id="ar_descent")
    [call] = client.calls
    assert [document.path for document in call.documents] == [
        "manuscript/digests/901.md",
        "manuscript/digests/902.md",
    ]
    assert "about 400 words" in call.instruction
    assert result.digest_id == "990"
    assert result.record.level is DigestLevel.ARC
    assert result.record.scene_ref == "001-006"
    assert result.record.povs == ["vance", "ilan", "quiej"]
    assert not result.povs_agree, "the model named one POV of three; the records name three"


# spec 001 / FR-AGENT-08 -- a digest at the wrong level is not rolled up as if it were right.
def test_a_digest_at_the_wrong_level_is_refused(fixture_store: Store) -> None:
    misfiled = SceneDigest(
        scene_ref="004", level=DigestLevel.SCENE, povs=["vance"], delta="x", words=1
    )
    fixture_store.write(paths.digest("902"), misfiled, role=AgentRole.WRITER)
    client = FakeModelClient()
    with pytest.raises(InvalidRecord, match="is a scene digest") as refused:
        writer.rollup(fixture_store, client, arc_id="ar_descent")
    assert refused.value.context == {"file": "manuscript/digests/902.md", "field": "level"}
    assert client.calls == []


# spec 001 / IF-06 -- the route writes the digest under the writer and answers what it wrote.
def test_the_rollup_route_writes_under_the_writer(
    fixture_client: TestClient, fixture_store: Store
) -> None:
    fake = FakeModelClient([Reply.of(ARC)])
    use(fixture_client, fake)
    response = fixture_client.post(
        "/agents/digests/rollup",
        json={"arc_id": "ar_descent"},
        headers={"X-Agent-Role": "writer"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["digest_id"] == "990"
    assert body["digest"]["scene_ref"] == "001-006"
    assert body["digest"]["level"] == "arc"
    assert body["persisted"]["path"] == "manuscript/digests/990.md"
    assert body["persisted"]["role"] == "writer"
    assert body["persisted"]["actor"] == "agent"
    assert body["povs_agree"] is False
    assert len(fake.calls) == 1
    [line] = fixture_store.provenance()
    assert line.path == "manuscript/digests/990.md"


# spec 001 / IF-02, FR-PERM-06 -- the wrong role, no role, a bad body, a partial chapter: all
# refused before the model is called.
@pytest.mark.parametrize(
    ("body", "headers", "status"),
    [
        ({"arc_id": "ar_descent"}, {"X-Agent-Role": "style_editor"}, 403),
        ({"arc_id": "ar_descent"}, {"X-Agent-Role": "auditor"}, 403),
        ({"arc_id": "ar_descent"}, {}, 400),
        ({"arc_id": "ar_descent", "chapter_id": "ch01"}, {"X-Agent-Role": "writer"}, 422),
        ({}, {"X-Agent-Role": "writer"}, 422),
        ({"chapter_id": "ch01"}, {"X-Agent-Role": "writer"}, 404),
        ({"chapter_id": "ch09"}, {"X-Agent-Role": "writer"}, 404),
    ],
    ids=["style-editor", "auditor", "no-role", "both", "neither", "partial", "unknown"],
)
def test_the_rollup_route_refuses_before_calling_the_model(
    fixture_client: TestClient,
    fixture_store: Store,
    body: dict[str, str],
    headers: dict[str, str],
    status: int,
) -> None:
    fake = FakeModelClient()
    use(fixture_client, fake)
    response = fixture_client.post("/agents/digests/rollup", json=body, headers=headers)
    assert response.status_code == status, response.text
    assert fake.calls == []
    assert fixture_store.provenance() == []
