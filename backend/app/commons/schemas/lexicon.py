"""DR-09. The canonical vocabulary: `canon/lexicon.yaml`.

Of everything the harness checks, this is the cheapest win. Drift in a neologism reduces to
string comparison, so the lexicon is the one invariant that needs no model to enforce and no
judgement to adjudicate - provided the wrong forms are written down next to the right one.

The file is a document with a named key rather than a bare YAML list, because DR-10 puts
`schema_version` on the file itself. The world builder writes it; the style editor and the
auditor read it (Figure 3).
"""

from __future__ import annotations

from pydantic import Field

from app.commons.schemas.common import EntityId, HarnessModel, StoreDocument


class CanonicalTerm(HarnessModel):
    """DR-09. One neologism, proper noun or piece of jargon, in its exact form.

    **Failure mode** (`definitions.md` CanonicalTerm): registering the term but not the set
    of wrong forms. The right spelling alone tells a checker nothing - it cannot know which
    of the thousand strings in a draft were meant to be this term and came out wrong. With
    `forbidden_variants` the check exists and is trivial: FR-AUD-05 is a case-insensitive
    search of every variant in the draft, and its evidence is the quote and its offset. With
    an empty list the term is simply unchecked, which is why DR-09 asks for the field to be
    present rather than merely allowed: an empty list is a visible decision, a missing key
    is an oversight nobody sees.

    `plural` and `gender` are decided here rather than improvised in a scene, because a
    neologism pluralised two ways in one chapter reads as two words.

    **`used_by` is what binds a term into a context.** FR-OPS-03 loads the lexicon through
    it: a term enters the writer's context when one of the entities already loaded for the
    scene is in this list. It is therefore not a note about who happens to say the word - it
    is the rule that nobody else says it, and the mechanism by which jargon stays with the
    faction it belongs to instead of leaking into every mouth in the book.
    """

    id: EntityId = Field(description="Stable identifier for the term; the index keys a row on it.")
    canonical_form: str = Field(
        min_length=1,
        description="The single definitive spelling; everything else about the term hangs on it.",
    )
    plural: str | None = Field(
        default=None,
        description="The plural, decided in advance; `None` when the term has none.",
    )
    gender: str | None = Field(
        default=None,
        description="Grammatical gender where the language needs it; `None` when it does not.",
    )
    forbidden_variants: list[str] = Field(
        default_factory=list,
        description="The wrong forms FR-AUD-05 searches for, case-insensitively. Present always"
        " (DR-09); empty means the term is deliberately unchecked.",
    )
    used_by: list[EntityId] = Field(
        default_factory=list,
        description="Characters and factions that use the term; nobody else says it, and"
        " FR-OPS-03 loads the term into a scene through this list.",
    )
    pronunciation: str | None = Field(
        default=None,
        description="How it is said, to keep the cadence stable when the prose is read aloud.",
    )


class LexiconFile(StoreDocument):
    """DR-09, DR-10. The whole of `canon/lexicon.yaml`.

    One file for the project's whole vocabulary, not one per term: the checker runs every
    variant over every draft, so splitting it would buy nothing and cost a directory walk.
    The index still stores one row per term (plan step 9), which is what makes a term
    retrievable on its own.
    """

    terms: list[CanonicalTerm] = Field(
        default_factory=list,
        description="Every registered term; empty is a legitimate state for a project that has"
        " not coined anything yet.",
    )


__all__ = [
    "CanonicalTerm",
    "LexiconFile",
]
