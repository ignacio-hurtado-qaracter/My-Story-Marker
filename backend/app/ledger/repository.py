"""The ledger feature's one door to the store layer (FR-STORE-02).

Everything this feature reads or writes goes through `Store`, and every path it names comes
from `app.commons.stores.paths`. Nothing here opens a file and nothing here spells a path:
FR-STORE-05 keeps the identifier-to-path grammar inside the store layer, which is what makes
"a path that would escape the root is rejected" a property of the system rather than a habit
of this module.

**Five files, and only two of them can be written.** Figure 3's `Out` column names
`ledger/proposed.yaml` for the writer and the canoniser, and `ledger/violations.yaml` for the
auditor. It names no role at all for `setups.yaml`, `threads.yaml` or `timeline.yaml`, and the
permission table transcribes that absence faithfully. So those three have a read function here
and no write function -- not as an oversight, but because a write function nothing may call is
an invitation to widen the table until it can, which FR-PERM-05 forbids.

No policy lives here either. Whether a role may write `ledger/proposed.yaml` is `may_write`'s
answer inside `Store.write` (FR-PERM-03), which is why every write below takes its role from
the caller and none of them has a default: a default role would be a guess, and FR-STORE-04
would then record the guess as provenance.
"""

from __future__ import annotations

from typing import Final

from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import ProposedFile, SetupsFile, ThreadsFile, ViolationsFile
from app.commons.stores import Store, paths
from app.commons.stores.provenance import ProvenanceRecord
from app.ledger.models import TimelineFile

SETUPS_PATH: Final[str] = paths.SETUPS
THREADS_PATH: Final[str] = paths.THREADS
TIMELINE_PATH: Final[str] = paths.TIMELINE
PROPOSED_PATH: Final[str] = paths.PROPOSED
VIOLATIONS_PATH: Final[str] = paths.VIOLATIONS
"""The five ledger files, re-exported from the store layer so the service can name the file it
is refusing (FR-STORE-06) without becoming a second module in this feature that knows where a
store file lives. A feature with two ideas of where the ledger sits is a feature that will
eventually write to one and read from the other."""


# --- reads ----------------------------------------------------------------------------
#
# A missing file is a `NotFound` from the store layer naming the path, not an empty document
# synthesised here. The two states are different and a caller has to be able to tell them
# apart: "this project has no ledger yet" and "the ledger is empty" call for different next
# moves, and a route that answered `{}` for both would have made the distinction unaskable.


def read_setups(store: Store) -> SetupsFile:
    """IF-03, `GET /ledger/setups`. DR-05.

    One file for the book rather than one per scene: a debt is planted in one scene and paid
    in another, so it belongs to neither.
    """
    return store.read(SETUPS_PATH, SetupsFile)


def read_threads(store: Store) -> ThreadsFile:
    """IF-03, `GET /ledger/threads`. DR-06.

    Likewise one file: a thread spans non-contiguous chapters by definition, so no chapter
    owns one, and FR-AUD-08 asks its latency question across all of them at once.
    """
    return store.read(THREADS_PATH, ThreadsFile)


def read_timeline(store: Store) -> TimelineFile:
    """IF-03, `GET /ledger/timeline`. The two axes and the mapping between them.

    Read-only from the API because Figure 3 gives it no writer, and derived in any case: the
    authority for both axes is `story_time` and `discourse_order` on `scenes/NNN.yaml`.
    """
    return store.read(TIMELINE_PATH, TimelineFile)


def read_proposed(store: Store) -> ProposedFile:
    """IF-03, `GET /ledger/proposed`. DR-07, the canonisation queue.

    The whole queue, settled entries included. Facts are kept after they are promoted or
    rejected: the record of what was refused, and why, is what stops the same invention being
    proposed and argued about again twenty scenes later.
    """
    return store.read(PROPOSED_PATH, ProposedFile)


def read_violations(store: Store) -> ViolationsFile:
    """IF-03, `GET /ledger/violations`. DR-07, the auditor's only output.

    Also the hand-off surface of FR-AGENT-11: the revise step reads the blocking violations
    back from this file after the auditor's write has landed, rather than from memory.
    """
    return store.read(VIOLATIONS_PATH, ViolationsFile)


def proposed_exists(store: Store) -> bool:
    """Whether `ledger/proposed.yaml` is on disk yet.

    Asked by the append of IF-04, which is the one operation in this feature that has to read
    before it writes. See `service.append_proposed` for why absence is not an error there.
    """
    return store.exists(PROPOSED_PATH)


# --- writes ---------------------------------------------------------------------------
#
# Both writes below name the role they are performed under, and that role arrives from the
# `X-Agent-Role` header (IF-02) rather than from a default here. There is no role argument
# with a value in this file.
#
# Which roles Figure 3 allows -- writer and canoniser on the queue, auditor on the violations
# -- is not restated. `Store.write` calls `may_write`, the single check (FR-PERM-03), and
# refuses with `PermissionDenied` before any byte touches disk. A second guard in this feature
# could only ever drift from the table.


def write_proposed(
    store: Store,
    record: ProposedFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, the store half of `POST /ledger/proposed`.

    The whole file, because that is what a store write is (FR-STORE-07: temp file, fsync,
    rename). The append semantics the route promises are built in the service, which reads the
    queue and hands the extended one down; this function has no opinion about what changed.
    """
    return store.write(PROPOSED_PATH, record, role=role, actor=actor)


def write_violations(
    store: Store,
    record: ViolationsFile,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /ledger/violations` (auditor). The whole report file.

    Whole rather than per violation: `revise` is handed every blocking violation of a scene at
    once (FR-AGENT-02), so the set is what has meaning, and two partial writes could leave the
    writer revising against half of an audit.
    """
    return store.write(VIOLATIONS_PATH, record, role=role, actor=actor)


__all__ = [
    "PROPOSED_PATH",
    "SETUPS_PATH",
    "THREADS_PATH",
    "TIMELINE_PATH",
    "VIOLATIONS_PATH",
    "proposed_exists",
    "read_proposed",
    "read_setups",
    "read_threads",
    "read_timeline",
    "read_violations",
    "write_proposed",
    "write_violations",
]
