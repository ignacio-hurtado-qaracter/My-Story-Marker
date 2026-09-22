"""DR-06. Plot threads: `ledger/threads.yaml`.

A thread is a plot running across non-contiguous chapters. The file is a document with a
named key rather than a bare YAML list, because DR-10 puts `schema_version` on the file.
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas.common import (
    EntityId,
    HarnessModel,
    Order,
    SceneId,
    StoreDocument,
    ThreadState,
)


class PlotThread(HarnessModel):
    """DR-06. One plot line, and how long it may be away before the reader loses it.

    `definitions.md` PlotThread says this exists so that "how long since we touched the
    sister subplot?" gets a number rather than an impression. That is the whole design: the
    question is answerable only if the scenes a thread appears in are listed **in discourse
    order**, because latency is a reading-order distance, not a story-time one. A subplot can
    be set in the past and still be fresh on the page, and one set yesterday can still have
    vanished for eighty pages.

    **Failure mode** (`definitions.md`): no maximum latency. Secondary threads evaporate and
    nobody notices until the final read-through, at which point the fix is structural and
    expensive. `max_latency` is required (DR-06) so that FR-AUD-08 can compare the gap in
    `discourse_order` since the thread's last scene against the number this thread was given,
    per thread: a slow-burn romance and a ticking bomb do not tolerate the same silence.

    **FR-OPS-03.** A thread whose `state` is `resolved` or `abandoned` has left the working
    tier and never enters a context again. That is the same rule that drops closed setups and
    resolved violations: what is finished stops competing for the 100k budget with what is
    still live. `dormant` is not finished - it is a thread deliberately quiet, still counted
    by the latency check, still eligible for assembly.
    """

    id: EntityId = Field(description="Stable identifier for the thread; the backend never renames.")
    state: ThreadState = Field(
        description="`planted`, `developing`, `dormant`, `resolved` or `abandoned`. The last two"
        " leave the working tier and never enter a context (FR-OPS-03).",
    )
    scenes: list[SceneId] = Field(
        default_factory=list,
        description="Where the thread advances, in discourse order. FR-AUD-08 measures the gap"
        " in `discourse_order` since the last of these, so the order is load-bearing.",
    )
    max_latency: Order = Field(
        description="How many scenes it may vanish for before the reader loses it. Required"
        " (DR-06) and per thread: a thread with no bound can never be reported as late.",
    )
    depends_on: list[EntityId] = Field(
        default_factory=list,
        description="Threads that must resolve first; empty means this one is free to close"
        " whenever the structure allows.",
    )


class ThreadsFile(StoreDocument):
    """DR-06, DR-10. The whole of `ledger/threads.yaml`.

    One file for the book. A thread by definition spans non-contiguous chapters, so there is
    no scene, chapter or arc that owns one, and the latency question is asked across all of
    them at once.
    """

    threads: list[PlotThread] = Field(
        default_factory=list,
        description="Every plot thread, live and closed; FR-AUD-08 checks the latency of the"
        " `planted` and `developing` ones.",
    )


__all__ = [
    "PlotThread",
    "ThreadsFile",
]
