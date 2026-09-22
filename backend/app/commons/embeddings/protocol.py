"""FR-EMB-01. What an embedder is, as a `Protocol`, and nothing about how one works.

The protocol exists so the offline test suite never loads a model. `rebuild()` takes an
`Embedder`; the suite hands it `FakeEmbedder`, which is deterministic and needs no weights and
no network, and production hands it `FastEmbedEmbedder`. Neither knows about the other.

`dim` is on the interface because the `vec0` table is declared with a fixed width: an embedder
whose dimension disagrees with the index is not a slower embedder, it is an index that cannot
be queried. `model_name` is on it because FR-IDX-07 records the active model in the index and
forces a rebuild when it changes -- vectors from two different models are not comparable, and
a cosine distance between them is a number with no meaning.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    """A deterministic map from text to a fixed-width vector."""

    @property
    def dim(self) -> int:
        """The width of every vector this embedder produces. Must be 384 (FR-EMB-02)."""
        ...

    @property
    def model_name(self) -> str:
        """The model actually in use, which is not always the one that was configured: the
        fallback of FR-EMB-02 may have chosen the other one, and the index records what was
        used rather than what was asked for."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per input, in the same order. Batched by the implementation."""
        ...


__all__ = ["Embedder"]
