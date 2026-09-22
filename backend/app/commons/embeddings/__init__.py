"""The embedder: `fastembed` in production, a deterministic fake in the offline suite.

`commons/embeddings/` is the only module that may name `fastembed` (NFR-04), which is why the
import contract lists it by name. Everything else takes the `Embedder` protocol, so the
offline suite never loads a model and never reaches the network (NFR-06, NFR-09).
"""

from __future__ import annotations

from app.commons.embeddings.fake import FAKE_MODEL_NAME, FakeEmbedder
from app.commons.embeddings.fastembed_impl import (
    EmbeddingModelUnavailableError,
    FastEmbedEmbedder,
)
from app.commons.embeddings.protocol import Embedder

__all__ = [
    "FAKE_MODEL_NAME",
    "Embedder",
    "EmbeddingModelUnavailableError",
    "FakeEmbedder",
    "FastEmbedEmbedder",
]
