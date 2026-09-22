"""The operations of the manuscript feature: whole-record reads, and writes whose measured
fields are taken from the prose rather than from the caller.

Reads are pass-through by design. FR-STORE-06 already says what a read is -- validated, or
`InvalidRecord` naming file and field, never repaired and never partially returned -- and a
service that added anything on top would be a second opinion about a file the store layer has
already ruled on.

Writes are not pass-through, and this is the feature where that matters most.

**`words` and `literal_tail` are derived here, on every write, from the text itself**
(DR-11, FR-AGENT-03). Whatever the request supplied in those fields is overwritten before the
record reaches the store layer. Two different failures are being closed:

* `words` is checked against the scene `budget` on the turn record. A count the writer reports
  about its own output is a claim, not a measurement, and accepting it would turn that check
  into a check on the model's arithmetic instead of on the draft.
* `literal_tail` is the only verbatim prose that reaches the next scene at all -- everything
  else arrives compressed, as a digest. A model that could set its own tail could quietly
  change what the next scene inherits: not what happened, which the digest carries, but *how
  it sounded*, which is the whole reason the tail exists. Summaries preserve what happened and
  lose how it sounded, so a forged tail is a voice change nothing downstream can detect.

The same reasoning gives the digest its `words`: it is the length of `delta`, measured, and
the turn records it against the word target for its level (DR-11, `DIGEST_WORD_TARGETS`).

The other check here is the one the path cannot make for itself: the id in the path is the
scene the record must name. `manuscript/012.md` whose `scene_ref` is `003` is a file that
validates, reads cleanly and is wrong everywhere it matters -- the audit runs over scene 012's
record against scene 003's prose, and both halves report success.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from app.commons.config import LITERAL_TAIL_WORDS
from app.commons.errors import InvalidRecord
from app.commons.permissions import Actor, AgentRole
from app.commons.schemas import DigestLevel, Draft, SceneDigest
from app.commons.stores import Store
from app.commons.stores.provenance import ProvenanceRecord
from app.manuscript import repository

_WORD: Final[re.Pattern[str]] = re.compile(r"\S+")
"""A word is a run of non-whitespace.

Deliberately not a linguistic definition. It has to be the same rule every time it is applied,
because `words` is compared against a budget an architect wrote; a counter that argued about
hyphens and ellipses would make two drafts of the same length report different numbers
depending on their punctuation.
"""


@dataclass(frozen=True, slots=True)
class ProseMeasures:
    """What code measures about a piece of prose, as opposed to what a model says about it."""

    words: int
    """Count of whitespace-separated runs."""

    literal_tail: str
    """The trailing slice, verbatim. Empty exactly when the text holds no words."""


def measure_prose(text: str, *, tail_words: int = LITERAL_TAIL_WORDS) -> ProseMeasures:
    """Count the words of `text` and cut its last `tail_words` of them, verbatim.

    **This function is the producer of the only verbatim prose that reaches the next scene.**
    Everything else a finished scene contributes to the book arrives compressed, as a digest;
    the slice returned here is handed forward whole by `assemble_context` (FR-OPS-03) and is
    what keeps the next scene in the register the book has been building instead of resetting
    it to the model's default voice.

    Because it travels forward verbatim, the cut is made *between* words and never inside one,
    and the whitespace between the words it keeps is preserved byte for byte: the line breaks
    and the blank lines of the tail are its rhythm, and a tail normalised into one paragraph
    would hand the next scene the words without the pacing. The slice therefore starts at the
    first character of the first word it keeps, which is why a text shorter than `tail_words`
    comes back without its leading whitespace rather than with it.

    Pure, and it takes the bound as an argument so a test can exercise the boundary without a
    501-word fixture. `LITERAL_TAIL_WORDS` is a module constant and not a settings key
    (DR-11): a deployment that could shorten the tail could change the voice of the book
    without changing a line of prose.
    """
    starts = [match.start() for match in _WORD.finditer(text)]
    if not starts:
        return ProseMeasures(words=0, literal_tail="")
    kept = min(tail_words, len(starts))
    return ProseMeasures(words=len(starts), literal_tail=text[starts[len(starts) - kept] :])


def _refuse_foreign_scene(*, path: str, identifier: str, scene_ref: str) -> None:
    """DR-08. The record names a different scene from the file it is being written to.

    A 422 rather than a silent correction to the path's id: the backend never renames, and a
    record the system quietly rewrote is a record whose author and whose reader believe
    different things -- here, about which scene this prose is.
    """
    if scene_ref != identifier:
        message = (
            f"{path} is scene {identifier!r} but the record names {scene_ref!r}; "
            "identifiers are stable and the backend never renames (DR-08)"
        )
        raise InvalidRecord(message, file=path, field="scene_ref")


def read_draft(store: Store, identifier: str) -> Draft:
    """IF-03, `GET /manuscript/{id}`."""
    return repository.read_draft(store, identifier)


def read_digest(store: Store, identifier: str) -> SceneDigest:
    """IF-03, `GET /manuscript/digests/{id}`."""
    return repository.read_digest(store, identifier)


def save_draft(
    store: Store,
    identifier: str,
    record: Draft,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /manuscript/{id}` (writer, style_editor).

    What lands is the submitted record with `words` and `literal_tail` replaced by what
    `measure_prose` found in `body` (DR-11, FR-AGENT-03). `model_copy` rather than a rebuilt
    `Draft`, so that every field this function does not measure survives untouched: a field
    added to `Draft` later must not be silently dropped by the one call site that rewrites
    two of them.
    """
    path = repository.draft_path(identifier)
    _refuse_foreign_scene(path=path, identifier=identifier, scene_ref=record.scene_ref)
    measured = measure_prose(record.body)
    derived = record.model_copy(
        update={"words": measured.words, "literal_tail": measured.literal_tail}
    )
    return repository.write_draft(store, identifier, derived, role=role, actor=actor)


def save_digest(
    store: Store,
    identifier: str,
    record: SceneDigest,
    *,
    role: AgentRole,
    actor: Actor,
) -> ProvenanceRecord:
    """IF-04, `PUT /manuscript/digests/{id}` (writer).

    `words` is measured from `delta`, for the reason it is measured on a draft: the turn
    records it against the target for the digest's level, and a length the summariser reports
    about its own summary is not a measurement.

    The scene check applies at `scene` level only. A chapter or arc digest carries the *range*
    it covers in `scene_ref` (DR-11), so there is nothing for the file's id to equal; whether
    that range agrees with the structure is a cross-file question for `reconcile` (FR-OPS-08),
    which can read `structure/chapters.yaml` and this feature may not (NFR-04).
    """
    path = repository.digest_path(identifier)
    if record.level is DigestLevel.SCENE:
        _refuse_foreign_scene(path=path, identifier=identifier, scene_ref=record.scene_ref)
    measured = measure_prose(record.delta)
    derived = record.model_copy(update={"words": measured.words})
    return repository.write_digest(store, identifier, derived, role=role, actor=actor)


__all__ = [
    "ProseMeasures",
    "measure_prose",
    "read_digest",
    "read_draft",
    "save_digest",
    "save_draft",
]
