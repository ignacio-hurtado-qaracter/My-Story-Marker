"""FR-EMB-02, -03, -04. The real embedder: `fastembed` on CPU, with a fallback.

Three decisions worth stating, because each prevents a specific failure:

* **The fallback is a fallback, not a choice.** `EMBED_MODEL` may fail to load for reasons
  that have nothing to do with this project -- the pinned `fastembed` may not know it, a
  download may fail, a platform may lack a wheel. Falling back to the other 384-d model keeps
  the backend usable, and the model actually loaded is recorded in the index (FR-IDX-07) so
  nobody later compares vectors from two different models. A cosine distance between vectors
  from different models is a number with no meaning.
* **Only 384 dimensions are accepted.** The `vec0` table is declared `float[384]`. Accepting
  a 768-d model would mean either a schema migration or an index that silently cannot be
  queried; refusing at load time turns that into one clear error.
* **`EMBED_OFFLINE=1` never reaches the network**, and a missing model is an error that names
  the directory to populate. NFR-06 limits outbound traffic to the model API and, only during
  `rebuild()`, the model download host; an embedder that quietly downloaded inside a request
  would breach that and stall the request for minutes on a cold cache.

FR-EMB-04: embedding runs on CPU, batched, synchronously inside `rebuild()` and incremental
updates. It never runs inside a request that a role is waiting on.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

from app.commons.config import EMBEDDING_DIM, Settings

logger = logging.getLogger(__name__)


class TextEmbeddingModel(Protocol):
    """The one method this module uses from `fastembed`.

    `fastembed` ships no type information, so without a narrow protocol every value taken from
    it would be `Any` and NFR-02 forbids that. Naming the one call we depend on also makes the
    coupling visible: if a future version changes `embed`, this is the line that has to move.
    """

    def embed(self, documents: Sequence[str]) -> Iterable[Iterable[float]]: ...

DEFAULT_BATCH_SIZE = 32


class EmbeddingModelUnavailableError(RuntimeError):
    """Neither the configured model nor the fallback could be loaded.

    A `RuntimeError` rather than a `HarnessError`: this is a startup and rebuild condition,
    not something a request can be given a status code for. It names the cache directory,
    because under `EMBED_OFFLINE=1` the fix is to populate that directory.
    """


class FastEmbedEmbedder:
    """`fastembed` behind the `Embedder` protocol."""

    def __init__(self, settings: Settings, *, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self._cache_dir = settings.model_cache_dir
        self._offline = settings.embed_offline
        self._batch_size = batch_size
        self._model_name: str
        self._model: TextEmbeddingModel
        self._model_name, self._model = self._load(
            settings.embed_model, settings.embed_fallback_model
        )

    @property
    def dim(self) -> int:
        return EMBEDDING_DIM

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        """FR-EMB-04. Batched, on CPU, synchronous."""
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            produced = self._model.embed(batch)
            vectors.extend([float(value) for value in vector] for vector in produced)

        for index, vector in enumerate(vectors):
            if len(vector) != EMBEDDING_DIM:
                message = (
                    f"{self._model_name} produced a {len(vector)}-d vector for input {index}; "
                    f"the vec0 table is declared float[{EMBEDDING_DIM}]"
                )
                raise EmbeddingModelUnavailableError(message)
        return vectors

    def _load(self, configured: str, fallback: str) -> tuple[str, TextEmbeddingModel]:
        """Try the configured model, then the fallback, and say which one is active."""
        attempts: list[str] = []
        for name in (configured, fallback):
            if name in attempts:
                continue
            attempts.append(name)
            try:
                model = self._build(name)
            # Any failure to load is a reason to try the fallback: the point of FR-EMB-02 is
            # that the backend stays usable whatever went wrong with one model.
            except Exception as error:
                logger.warning("embedding model %s could not be loaded: %s", name, error)
                continue
            if name != configured:
                logger.warning(
                    "embedding model %s is in use; %s could not be loaded. The active model is "
                    "recorded in the index, and changing it forces a rebuild (FR-IDX-07).",
                    name,
                    configured,
                )
            else:
                logger.info("embedding model %s is in use", name)
            return name, model

        message = (
            f"neither {configured} nor {fallback} could be loaded. "
            + (
                f"EMBED_OFFLINE is set, so nothing was downloaded: populate {self._cache_dir}."
                if self._offline
                else f"Check the network and {self._cache_dir}."
            )
        )
        raise EmbeddingModelUnavailableError(message)

    def _build(self, name: str) -> TextEmbeddingModel:
        # Imported lazily: loading `fastembed` pulls in onnxruntime, which costs a second
        # or two, and nothing should pay that at import time just to read a scene record.
        from fastembed import TextEmbedding

        cache: Path = self._cache_dir
        cache.mkdir(parents=True, exist_ok=True)
        embedding: TextEmbeddingModel = TextEmbedding(
            model_name=name,
            cache_dir=str(cache),
            local_files_only=self._offline,
            threads=None,
        )
        return embedding


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "EmbeddingModelUnavailableError",
    "FastEmbedEmbedder",
    "TextEmbeddingModel",
]
