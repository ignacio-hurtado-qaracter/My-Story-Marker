"""AC 9, the real half: `FastEmbedEmbedder` loads a 384-d model, or falls back to the other.

Two kinds of test live here.

* **Marked `model`**, run by default and slow on a cold cache: they load the real model
  through `fastembed`, so the first run downloads it (about 90 MB, the one outbound connection
  NFR-06 allows, and the reason the network guard exempts this marker). The cache is not the
  test's temporary directory -- that would download the model on every run -- but a persistent
  one: `EMBED_CACHE_DIR` when the environment sets it, else `backend/.index/models`, which
  `.gitignore` already keeps out of the repository (plan, "Known constraints").
* **Unmarked**, offline: the fallback chain and the 384-d refusal, with the model builder
  replaced, because proving the fallback against the real network would need the primary
  model to fail to download on demand.
"""

from __future__ import annotations

import importlib
import math
import os
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest

from app.commons.config import (
    DEFAULT_EMBED_MODEL,
    EMBEDDING_DIM,
    FALLBACK_EMBED_MODEL,
    Settings,
    get_settings,
)
from app.commons.embeddings import EmbeddingModelUnavailableError, FastEmbedEmbedder

BACKEND = Path(__file__).resolve().parents[4]
REAL_MODEL_CACHE = Path(os.environ.get("EMBED_CACHE_DIR") or BACKEND / ".index" / "models")


def _runtime_error() -> str | None:
    """Why `onnxruntime` -- the engine under `fastembed` -- cannot load here, if it cannot."""
    try:
        importlib.import_module("onnxruntime")
    except ImportError as error:
        return str(error)
    return None


RUNTIME_ERROR = _runtime_error()
requires_onnxruntime = pytest.mark.skipif(
    RUNTIME_ERROR is not None,
    reason=(
        f"onnxruntime cannot load on this machine ({RUNTIME_ERROR}). On Windows this is the "
        "missing Microsoft Visual C++ 2015-2022 x64 runtime (msvcp140.dll): install the "
        "redistributable. CI runs these tests for real."
    ),
)
"""Skipped, visibly and with the fix named, only when the runtime itself cannot load -- the
same stance as `requires_sqlite_vec` for the vector extension. A model that loads and then
misbehaves still fails."""

TEXTS = [
    "The vault's brine absorbs every wavelength a hand-lamp makes past four metres.",
    "Ilan's graft hand closes on the throat latch.",
    "",
]


@pytest.fixture
def real_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Settings that load the configured model into the persistent cache, online."""
    monkeypatch.setenv("EMBED_CACHE_DIR", str(REAL_MODEL_CACHE))
    monkeypatch.setenv("EMBED_OFFLINE", "0")
    monkeypatch.delenv("EMBED_MODEL", raising=False)
    get_settings.cache_clear()
    try:
        return Settings()
    finally:
        get_settings.cache_clear()


# spec 001 / AC 9 -- the real model loads (the primary, or the fallback when the primary cannot
# be loaded) and is 384-dimensional, whatever the text, including the empty string.
@pytest.mark.model
@requires_onnxruntime
def test_the_real_model_loads_and_yields_384_d_unit_vectors(real_settings: Settings) -> None:
    embedder = FastEmbedEmbedder(real_settings)

    assert embedder.model_name in {DEFAULT_EMBED_MODEL, FALLBACK_EMBED_MODEL}
    assert embedder.dim == EMBEDDING_DIM
    vectors = embedder.embed(TEXTS)
    assert len(vectors) == len(TEXTS)
    for vector in vectors:
        assert len(vector) == EMBEDDING_DIM
        assert math.isclose(math.fsum(value * value for value in vector), 1.0, rel_tol=1e-4)


# spec 001 / AC 9 -- two process starts embed the same text to the same vector. FR-IDX-04's
# "identical embeddings" across rebuilds rests on this: a rebuild after a restart must not
# move every row.
@pytest.mark.model
@requires_onnxruntime
def test_the_same_text_embeds_identically_across_two_process_starts(
    real_settings: Settings,
) -> None:
    script = (
        "from app.commons.config import Settings;"
        "from app.commons.embeddings import FastEmbedEmbedder;"
        f"vector = FastEmbedEmbedder(Settings()).embed([{TEXTS[0]!r}])[0];"
        "print(FastEmbedEmbedder(Settings()).model_name);"
        "print(','.join(repr(value) for value in vector))"
    )
    environment = dict(
        os.environ,
        EMBED_CACHE_DIR=str(real_settings.model_cache_dir),
        EMBED_OFFLINE="0",
    )
    runs = [
        subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            env=environment,
            cwd=BACKEND,
            timeout=600,
        ).stdout
        for _ in range(2)
    ]
    assert runs[0] == runs[1]
    model, vector = runs[0].splitlines()
    assert model in {DEFAULT_EMBED_MODEL, FALLBACK_EMBED_MODEL}
    assert len(vector.split(",")) == EMBEDDING_DIM


# --- the fallback chain, offline ---------------------------------------------------------


class _Model:
    """Stands in for a loaded `fastembed` model: fixed-size, unit vectors."""

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def embed(self, documents: Sequence[str]) -> Iterable[Iterable[float]]:
        unit = 1.0 / math.sqrt(self.dim)
        return [[unit] * self.dim for _ in documents]


def _offline_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline: bool) -> Settings:
    monkeypatch.setenv("EMBED_CACHE_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("EMBED_OFFLINE", "1" if offline else "0")
    monkeypatch.delenv("EMBED_MODEL", raising=False)
    get_settings.cache_clear()
    try:
        return Settings()
    finally:
        get_settings.cache_clear()


# spec 001 / AC 9 -- FR-EMB-02: a primary that cannot be loaded falls back to the other 384-d
# model, and the embedder says which one is active (FR-IDX-07 records it).
def test_an_unloadable_primary_falls_back_to_the_secondary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def build(_self: FastEmbedEmbedder, name: str) -> _Model:
        if name == DEFAULT_EMBED_MODEL:
            message = "unsupported by the pinned fastembed"
            raise ValueError(message)
        return _Model(EMBEDDING_DIM)

    monkeypatch.setattr(FastEmbedEmbedder, "_build", build)
    embedder = FastEmbedEmbedder(_offline_settings(tmp_path, monkeypatch, offline=False))

    assert embedder.model_name == FALLBACK_EMBED_MODEL
    assert len(embedder.embed(["x"])[0]) == EMBEDDING_DIM


# spec 001 / AC 9 -- FR-EMB-03: when neither loads, the error names the directory to populate,
# and says so explicitly under EMBED_OFFLINE, where nothing will ever be downloaded.
@pytest.mark.parametrize("offline", [True, False], ids=["offline", "online"])
def test_when_neither_model_loads_the_error_names_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline: bool
) -> None:
    def build(_self: FastEmbedEmbedder, name: str) -> _Model:
        message = f"cannot load {name}"
        raise OSError(message)

    monkeypatch.setattr(FastEmbedEmbedder, "_build", build)
    settings = _offline_settings(tmp_path, monkeypatch, offline=offline)

    with pytest.raises(EmbeddingModelUnavailableError) as raised:
        FastEmbedEmbedder(settings)
    assert str(settings.model_cache_dir) in str(raised.value)
    assert ("EMBED_OFFLINE" in str(raised.value)) is offline


# spec 001 / AC 9 -- FR-EMB-02: only 384-d models are accepted, so a model that yields any other
# width is refused rather than written into a float[384] table.
def test_a_model_of_another_width_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(FastEmbedEmbedder, "_build", lambda _self, _name: _Model(768))
    embedder = FastEmbedEmbedder(_offline_settings(tmp_path, monkeypatch, offline=False))

    with pytest.raises(EmbeddingModelUnavailableError, match="768-d"):
        embedder.embed(["x"])
