"""AC 9, the offline half — the fake embedder's three guarantees.

The fake is not a model and does not pretend to be one: similar texts get unrelated vectors,
and no test here asserts otherwise. What it must guarantee is exactly what AC 6 leans on when
it says two rebuilds of the same tree yield identical embeddings: **same text, same vector,
every time, in any process, on any platform.**

The cross-process case is the one worth running rather than reasoning about. Python's builtin
`hash()` is randomised per interpreter by `PYTHONHASHSEED`, so an implementation built on it
would pass every assertion inside one process and fail the only one that matters.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from app.commons.config import EMBEDDING_DIM
from app.commons.embeddings import Embedder, FakeEmbedder
from app.commons.embeddings.fake import FAKE_MODEL_NAME

SAMPLES = [
    "The gate held.",
    "the gate held.",
    "",
    "a" * 5000,
    "unicode: fold drive, curly quotes, en dash",
    "  leading and trailing whitespace  ",
]


# spec 001 / AC 9
def test_it_satisfies_the_protocol() -> None:
    assert isinstance(FakeEmbedder(), Embedder)


# spec 001 / AC 9 — 384-d, because the vec0 table is declared float[384].
@pytest.mark.parametrize("text", SAMPLES, ids=lambda t: repr(t[:20]))
def test_every_vector_is_384_dimensional(text: str) -> None:
    [vector] = FakeEmbedder().embed([text])
    assert len(vector) == EMBEDDING_DIM == 384


# spec 001 / AC 9 — unit norm, so cosine and dot product agree with the index.
@pytest.mark.parametrize("text", SAMPLES, ids=lambda t: repr(t[:20]))
def test_every_vector_is_unit_norm(text: str) -> None:
    [vector] = FakeEmbedder().embed([text])
    assert sum(value * value for value in vector) == pytest.approx(1.0, abs=1e-9)


# spec 001 / AC 9 — deterministic within a process.
def test_the_same_text_gives_the_same_vector() -> None:
    embedder = FakeEmbedder()
    assert embedder.embed(["The gate held."]) == embedder.embed(["The gate held."])
    assert FakeEmbedder().embed(["The gate held."]) == embedder.embed(["The gate held."])


# spec 001 / AC 9 — and across two process starts, which is the case that rules out `hash()`.
def test_the_same_text_gives_the_same_vector_in_another_process() -> None:
    script = (
        "from app.commons.embeddings import FakeEmbedder;"
        "print(FakeEmbedder().embed(['The gate held.'])[0][:6])"
    )
    # The environment is inherited and only PYTHONHASHSEED overridden: on Windows a child
    # python with an emptied environment cannot find SYSTEMROOT and exits before it runs.
    runs = []
    for seed in ("0", "12345"):
        environment = dict(os.environ, PYTHONHASHSEED=seed)
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            env=environment,
        )
        runs.append(completed.stdout.strip())
    assert runs[0] == runs[1]
    assert runs[0] == str(FakeEmbedder().embed(["The gate held."])[0][:6])


# spec 001 / AC 9 — different texts differ, or the fake would make every retrieval test pass
# by accident.
def test_different_texts_give_different_vectors() -> None:
    embedder = FakeEmbedder()
    vectors = embedder.embed(SAMPLES)
    assert len({tuple(vector) for vector in vectors}) == len(SAMPLES)


# spec 001 / AC 9 — order is preserved, because rows are zipped with ids by position.
def test_order_is_preserved() -> None:
    embedder = FakeEmbedder()
    batch = embedder.embed(SAMPLES)
    for index, text in enumerate(SAMPLES):
        assert batch[index] == embedder.embed([text])[0]


# spec 001 / AC 9
def test_an_empty_batch_is_an_empty_result() -> None:
    assert FakeEmbedder().embed([]) == []


# spec 001 / AC 9, FR-IDX-07 — the fake names itself, so an index it built is visibly not one
# a real embedder built and the mismatch forces a rebuild.
def test_it_names_itself() -> None:
    assert FakeEmbedder().model_name == FAKE_MODEL_NAME
    assert "fake" in FAKE_MODEL_NAME
