"""The pinned price table (spec 010, AC 1).

USD per million tokens, first-party Claude API rates (claude-api skill, cached 2026-06-24).
Cache read is 0.1x the input rate and a 5-minute cache write 1.25x, the standard prompt
caching multipliers. Pinned in code, never fetched: a cost figure recorded on a trace must
be reproducible from the token counts beside it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """USD per million tokens."""

    input: float
    output: float
    cache_read: float
    cache_write: float


def _standard(input_rate: float, output_rate: float) -> ModelPrice:
    return ModelPrice(
        input=input_rate,
        output=output_rate,
        cache_read=round(input_rate * 0.1, 6),
        cache_write=round(input_rate * 1.25, 6),
    )


PRICES: Final[dict[str, ModelPrice]] = {
    "claude-haiku-4-5": _standard(1.00, 5.00),
    "claude-sonnet-5": _standard(2.00, 10.00),
    "claude-sonnet-4-6": _standard(3.00, 15.00),
    "claude-sonnet-4-5": _standard(3.00, 15.00),
    "claude-opus-5": _standard(5.00, 25.00),
}
"""Keyed by alias. A dated snapshot id (`claude-haiku-4-5-20251001`) resolves to its alias by
prefix, so the CLI's reported model id prices the same as the requested alias."""

_MILLION: Final[float] = 1_000_000.0


def price_for(model: str) -> ModelPrice | None:
    """The price of `model`, matching a dated snapshot to its alias; None when unknown."""
    if model in PRICES:
        return PRICES[model]
    for alias in sorted(PRICES, key=len, reverse=True):
        if model.startswith(alias):
            return PRICES[alias]
    return None


def cost_usd(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read: int = 0,
    cache_creation: int = 0,
) -> float:
    """Cost of one call in USD. An unknown model costs 0.0 (and is visible as such)."""
    price = price_for(model)
    if price is None:
        return 0.0
    total = (
        input_tokens * price.input
        + output_tokens * price.output
        + cache_read * price.cache_read
        + cache_creation * price.cache_write
    ) / _MILLION
    return round(total, 8)


__all__ = ["PRICES", "ModelPrice", "cost_usd", "price_for"]
