"""Spec 010 — K2 cost and traced calls."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.bible import BibleRepository
from app.commons.llm import FakeModelClient, ProcessFailure, Reply, Usage
from app.commons.observability import (
    CallScope,
    LangfuseObserver,
    NoopObserver,
    cost_usd,
    load_prompt,
    traced_complete,
)
from app.commons.permissions import AgentRole


class _Out(BaseModel):
    text: str


# spec 010 / AC 1 — O02
def test_haiku_price_table() -> None:
    million = 1_000_000
    assert cost_usd("claude-haiku-4-5", input_tokens=million) == pytest.approx(1.00)
    assert cost_usd("claude-haiku-4-5", output_tokens=million) == pytest.approx(5.00)
    assert cost_usd("claude-haiku-4-5", cache_read=million) == pytest.approx(0.10)
    assert cost_usd("claude-haiku-4-5", cache_creation=million) == pytest.approx(1.25)
    assert cost_usd("claude-haiku-4-5-20251001", input_tokens=million) == pytest.approx(1.00)
    assert cost_usd("claude-sonnet-5", output_tokens=million) == pytest.approx(10.00)
    assert cost_usd("unknown-model", input_tokens=million) == 0.0


# spec 010 / AC 4 — O02
def test_traced_complete_records_call(tmp_path: Path) -> None:
    repo = BibleRepository.open(tmp_path / "h.sqlite")
    novel = repo.create_novel()
    usage = Usage(input_tokens=2000, output_tokens=1000, cache_read_input_tokens=10_000)
    client = FakeModelClient(
        [
            ProcessFailure(),
            ProcessFailure(),  # the client's own retry, inside attempt 1
            Reply.of(_Out(text="hola"), usage=usage, model_id="claude-haiku-4-5"),
        ]
    )
    observer = NoopObserver()
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "writer.md").write_text("Escribe.", encoding="utf-8")
    prompt = load_prompt("writer", observer, directory=prompt_dir)
    assert prompt.version.startswith("sha-")

    with observer.trace("generation", session_id=novel.id) as trace:
        completion = traced_complete(
            client,
            role=AgentRole.WRITER,
            system=prompt.text,
            documents=[],
            instruction="Capítulo 1",
            output_schema=_Out,
            observer=observer,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            sink=repo,
            scope=CallScope(novel_id=novel.id, version=1, chapter=1),
        )

    assert completion.output.text == "hola"
    expected = (2000 * 1.0 + 1000 * 5.0 + 10_000 * 0.1) / 1_000_000
    assert observer.spans == ["role:writer"]
    assert observer.generations[0].cost_usd == pytest.approx(expected)
    assert observer.generations[0].parent == "role:writer"
    summary = repo.cost_summary(novel.id)
    assert summary.calls == 1
    assert summary.cost_usd == pytest.approx(expected)
    assert summary.by_chapter[0].chapter == 1
    row = repo.connection.execute(
        "select prompt_version, trace_id, attempts from llm_call"
    ).fetchone()
    assert tuple(row) == (prompt.version, trace.id, 2)


# spec 010 / AC 2 — manual smoke; runs only with --live and real keys.
@pytest.mark.live
def test_live_langfuse_trace_and_score() -> None:  # pragma: no cover - live only
    public, secret = os.environ.get("LANGFUSE_PUBLIC_KEY"), os.environ.get("LANGFUSE_SECRET_KEY")
    if not public or not secret:
        pytest.skip("Langfuse keys not set")
    observer = LangfuseObserver.from_keys(
        public_key=public,
        secret_key=secret,
        base_url=os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
    )
    assert observer.client.auth_check()
    with observer.trace("smoke", session_id="smoke-session") as trace:
        observer.score("smoke", 1.0)
    assert len(trace.id) == 32
    observer.flush()
