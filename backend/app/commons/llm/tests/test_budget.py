"""AC 22 and AC 33 at unit level: the estimate, the cap, and pruning whole entries by rank.

The rule under test is the user's (spec decisions R3-2 and R3-5): only input tokens count,
they are estimated before the call over what the system sends -- never the CLI's own
overhead -- and a call over 100k is never made. Pruning is how a context that
would exceed the cap is brought under it without cutting a record in half or hiding what was
left out (FR-CTX-03, FR-CTX-05).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.commons.config import CONTEXT_TOKEN_CAP
from app.commons.errors import ContextBudgetExceeded
from app.commons.llm.tokens import (
    CLI_OVERHEAD_TOKENS,
    Entry,
    estimate_input,
    estimate_tokens,
    fit_to_budget,
    is_over_cap,
    require_within_cap,
)


def entry(key: str, tokens: int) -> Entry:
    """An entry whose estimate is exactly `tokens` (three characters per token)."""
    return Entry(key=key, text="x" * (tokens * 3))


# spec 001 / AC 22 — the estimate is pessimistic and never zero for real text.
@pytest.mark.parametrize(
    ("text", "expected"),
    [("", 0), ("a", 1), ("abc", 1), ("abcd", 2), ("x" * 300, 100)],
    ids=repr,
)
def test_estimate_rounds_up(text: str, expected: int) -> None:
    assert estimate_tokens(text) == expected


# spec 001 / AC 22 — English prose is overestimated, the safe direction for a hard cap.
def test_the_estimate_overestimates_english_prose() -> None:
    prose = "The gate held. She counted the seconds and did not move. " * 40
    assert estimate_tokens(prose) > len(prose.split())


# spec 001 / AC 22, AC 35 — R3-5: the CLI's overhead is outside the cap and never in the
# estimate, so an empty call estimates at zero.
def test_the_cli_overhead_is_never_estimated() -> None:
    assert estimate_input("", [], "") == 0
    assert estimate_input("abc", ["abc", "abc"], "abc") == 4


# spec 001 / AC 22 — over the cap, the call is refused and says by how much.
def test_an_estimate_over_the_cap_is_refused() -> None:
    require_within_cap(CONTEXT_TOKEN_CAP)
    with pytest.raises(ContextBudgetExceeded) as raised:
        require_within_cap(CONTEXT_TOKEN_CAP + 1)
    body = raised.value.as_body()
    assert body["counted"] == CONTEXT_TOKEN_CAP + 1
    assert body["cap"] == CONTEXT_TOKEN_CAP


# spec 001 / AC 33 — everything fits: nothing is removed.
def test_everything_kept_when_it_fits() -> None:
    fit = fit_to_budget(
        system="",
        instruction="",
        mandatory=[entry("fixed", 10)],
        prunable=[entry("a", 10), entry("b", 10)],
        cap=30,
    )
    assert [e.key for e in fit.kept] == ["fixed", "a", "b"]
    assert fit.removed == []
    assert fit.truncated_at is None
    assert fit.estimate == 30


# spec 001 / AC 33 — the lowest-ranked entries go first, whole, and are named.
def test_lowest_ranked_entries_are_removed_whole_and_named() -> None:
    fit = fit_to_budget(
        system="",
        instruction="",
        mandatory=[entry("fixed", 10)],
        prunable=[entry("a", 10), entry("b", 10), entry("c", 10)],
        cap=25,
    )
    assert [e.key for e in fit.kept] == ["fixed", "a"]
    assert fit.removed == ["b", "c"]
    assert fit.truncated_at == "b"
    assert all(e.text == "x" * 30 for e in fit.kept[1:]), "an entry was cut"


# spec 001 / AC 33 — a smaller, lower-ranked entry is not slipped in behind a larger one.
def test_rank_order_is_never_reordered_to_pack_more_in() -> None:
    fit = fit_to_budget(
        system="",
        instruction="",
        mandatory=[],
        prunable=[entry("big", 50), entry("small", 1)],
        cap=10,
    )
    assert fit.kept == []
    assert fit.removed == ["big", "small"]


# spec 001 / AC 33 — the mandatory part is never pruned; if it alone does not fit, refuse.
def test_mandatory_overflow_refuses_rather_than_shortens() -> None:
    with pytest.raises(ContextBudgetExceeded):
        fit_to_budget(
            system="",
            instruction="",
            mandatory=[entry("fixed", 100)],
            prunable=[],
            cap=50,
        )


# spec 001 / AC 33 — the system prompt and the instruction count too.
def test_system_and_instruction_count_against_the_budget() -> None:
    fit = fit_to_budget(
        system="s" * 30,
        instruction="i" * 30,
        mandatory=[],
        prunable=[entry("a", 10)],
        cap=25,
    )
    assert fit.removed == ["a"]


# spec 001 / AC 33 — property: the result never exceeds the cap, never cuts an entry, and
# what was kept is a prefix of the ranking.
@given(
    mandatory=st.lists(st.integers(min_value=0, max_value=40), max_size=4),
    prunable=st.lists(st.integers(min_value=0, max_value=40), max_size=12),
    slack=st.integers(min_value=0, max_value=300),
)
def test_fit_is_a_ranked_prefix_under_the_cap(
    mandatory: list[int], prunable: list[int], slack: int
) -> None:
    cap = slack
    required = [entry(f"m{i}", t) for i, t in enumerate(mandatory)]
    ranked = [entry(f"p{i}", t) for i, t in enumerate(prunable)]
    try:
        fit = fit_to_budget(system="", instruction="", mandatory=required, prunable=ranked, cap=cap)
    except ContextBudgetExceeded:
        assert sum(mandatory) > cap
        return

    assert fit.estimate <= cap
    kept_prunable = [e.key for e in fit.kept if e.key.startswith("p")]
    assert kept_prunable == [e.key for e in ranked[: len(kept_prunable)]]
    assert fit.removed == [e.key for e in ranked[len(kept_prunable) :]]
    assert [e.key for e in fit.kept if e.key.startswith("m")] == [e.key for e in required]


# spec 001 / AC 35 — R3-5: `over_cap` reads the real count with the overhead subtracted. A
# call that carried 100k of system context plus the CLI's own ~2.5k is not over the cap.
@pytest.mark.parametrize(
    ("real", "over"),
    [
        (CONTEXT_TOKEN_CAP, False),
        (CONTEXT_TOKEN_CAP + CLI_OVERHEAD_TOKENS, False),
        (CONTEXT_TOKEN_CAP + CLI_OVERHEAD_TOKENS + 1, True),
        (0, False),
    ],
    ids=["exactly-cap", "cap-plus-overhead", "one-over", "empty"],
)
def test_over_cap_subtracts_the_cli_overhead(real: int, over: bool) -> None:
    assert is_over_cap(real) is over


# spec 001 / AC 35 — a real count between the cap and cap plus the overhead is not flagged.
def test_the_band_between_cap_and_cap_plus_overhead_is_not_flagged() -> None:
    for real in range(CONTEXT_TOKEN_CAP, CONTEXT_TOKEN_CAP + CLI_OVERHEAD_TOKENS + 1, 250):
        assert is_over_cap(real) is False
