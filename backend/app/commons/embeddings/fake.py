"""FR-EMB-01. A deterministic embedder for the offline suite.

It is not a model and does not pretend to be one: similar texts get unrelated vectors. What
it guarantees is everything the tests actually depend on -- the same text always yields the
same 384-d unit vector, in this process and in any other, on any platform -- and those are
exactly the properties AC 6 needs to assert that two rebuilds of the same tree produce
identical embeddings.

Using the real model in the offline suite would make that assertion a statement about
`fastembed`'s determinism and about whichever weights happened to be cached, and it would
need the network on a cold machine. NFR-09 keeps the suite on a temporary copy with no
network; this is what makes that possible.

The hash is SHA-256 rather than `hash()`, which is randomised per process by PYTHONHASHSEED
and would make "the same vector across two process starts" false.
"""

from __future__ import annotations

import hashlib
import math
import struct

from app.commons.config import EMBEDDING_DIM

FAKE_MODEL_NAME = "fake-sha256-384"
"""Recorded in the index like any other model name (FR-IDX-07), so an index built by the
fake is visibly not one built by a real embedder and a rebuild is forced on the switch."""


class FakeEmbedder:
    """Deterministic, offline, 384-d, unit norm."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        if dim <= 0:
            message = f"embedding dimension must be positive, got {dim}"
            raise ValueError(message)
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_name(self) -> str:
        return FAKE_MODEL_NAME

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        """Expand the digest by counter until it is wide enough, then normalise.

        Normalising matters beyond tidiness: the `vec0` table is declared with cosine
        distance, and unit vectors make cosine and dot product agree, so a test that computes
        similarity by hand gets the same answer the index does.
        """
        payload = text.encode("utf-8")
        raw = bytearray()
        counter = 0
        while len(raw) < self._dim * 4:
            raw.extend(hashlib.sha256(payload + counter.to_bytes(4, "big")).digest())
            counter += 1

        values = [
            struct.unpack_from(">i", raw, offset * 4)[0] / 2_147_483_648.0
            for offset in range(self._dim)
        ]
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:  # pragma: no cover - only reachable if every byte is zero
            values[0] = 1.0
            return values
        return [value / norm for value in values]


__all__ = ["FAKE_MODEL_NAME", "FakeEmbedder"]
