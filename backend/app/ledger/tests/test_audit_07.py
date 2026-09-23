"""FR-AUD-05 -- invariant 7, canonical lexicon. Golden on the fixture (README planted row 6)
and the edges: case-insensitive, every occurrence, the draft's own spelling in the quote, one
finding per span, blank variants ignored, and an absent lexicon skipped."""

from __future__ import annotations

from app.commons.permissions import AgentRole
from app.commons.schemas import CanonicalTerm, Draft, LexiconFile, Severity, Violation
from app.commons.stores import Store, paths
from app.ledger.audit import audit_scene
from app.manuscript.service import measure_prose

SCENES = ("001", "002", "003", "004", "005", "006")
INVARIANT = 7


def findings(store: Store) -> dict[str, list[Violation]]:
    found: dict[str, list[Violation]] = {}
    for scene in SCENES:
        report = audit_scene(store, scene, semantic=False)
        hits = [finding for finding in report.violations if finding.invariant == INVARIANT]
        if hits:
            found[scene] = hits
    return found


def write_draft(store: Store, identifier: str, body: str) -> None:
    measures = measure_prose(body)
    draft = Draft(
        scene_ref=identifier,
        words=measures.words,
        literal_tail=measures.literal_tail,
        body=body,
    )
    store.write(paths.draft(identifier), draft, role=AgentRole.WRITER)


def with_terms(store: Store, *extra: CanonicalTerm, replace: CanonicalTerm | None = None) -> None:
    lexicon = store.read(paths.LEXICON, LexiconFile)
    terms = [
        replace if replace is not None and term.id == replace.id else term for term in lexicon.terms
    ]
    store.write(paths.LEXICON, LexiconFile(terms=[*terms, *extra]), role=AgentRole.WORLD_BUILDER)


# spec 001 / AC 15 -- README row 6: `readkey` once in Draft B, blocking, quote and offset.
def test_the_planted_variant_is_found_in_draft_b(fixture_store: Store) -> None:
    found = findings(fixture_store)
    assert list(found) == ["003"]
    [finding] = found["003"]
    assert finding.severity is Severity.BLOCKING
    assert finding.evidence.quote == "readkey"
    assert finding.evidence.offset == 2403
    body = fixture_store.read(paths.draft("003"), Draft).body
    assert body[2403 : 2403 + len("readkey")] == "readkey"


# spec 001 / AC 15 -- the prior report vi_002 records the same finding at the same offset.
def test_the_finding_matches_the_fixtures_prior_report(fixture_store: Store) -> None:
    [finding] = findings(fixture_store)["003"]
    raw = fixture_store.read_raw(paths.VIOLATIONS)
    assert 'quote: "readkey"' in raw
    assert f"offset: {finding.evidence.offset}" in raw


# spec 001 / AC 15 -- case-insensitive, every occurrence, quoted in the draft's own spelling.
def test_every_occurrence_is_found_whatever_its_case(fixture_store: Store) -> None:
    body = "The Read Key was gone. So was the READKEY. She swam the Pump-Vault twice."
    write_draft(fixture_store, "004", body)
    hits = findings(fixture_store)["004"]
    assert [(v.evidence.quote, v.evidence.offset) for v in hits] == [
        ("Read Key", body.index("Read Key")),
        ("READKEY", body.index("READKEY")),
        ("Pump-Vault", body.index("Pump-Vault")),
    ]
    assert all(v.severity is Severity.BLOCKING for v in hits)


# spec 001 / AC 15 -- the canonical forms are safe to write freely (README row 6).
def test_the_canonical_forms_are_not_reported(fixture_store: Store) -> None:
    write_draft(
        fixture_store, "004", "The read-key, the cold soak, the calving window, the pump vault."
    )
    assert "004" not in findings(fixture_store)


# spec 001 / AC 15 -- one span listed under two terms is one finding, not two ids for one fact.
def test_one_span_is_one_finding(fixture_store: Store) -> None:
    duplicate = CanonicalTerm(
        id="lx_key",
        canonical_form="key",
        forbidden_variants=["READKEY"],
        used_by=[],
    )
    with_terms(fixture_store, duplicate)
    hits = findings(fixture_store)["003"]
    assert [(v.evidence.quote, v.evidence.offset) for v in hits] == [("readkey", 2403)]


# spec 001 / AC 15 -- a blank variant would match everywhere; it is not searched.
def test_a_blank_variant_is_not_searched(fixture_store: Store) -> None:
    lexicon = fixture_store.read(paths.LEXICON, LexiconFile)
    readkey = next(term for term in lexicon.terms if term.id == "lx_readkey")
    blanked = readkey.model_copy(update={"forbidden_variants": ["", "  ", "readkey"]})
    with_terms(fixture_store, replace=blanked)
    assert [len(hits) for hits in findings(fixture_store).values()] == [1]


# spec 001 / AC 15 -- no lexicon: the check is skipped and says so.
def test_an_absent_lexicon_skips_the_check(fixture_store: Store) -> None:
    (fixture_store.root / paths.LEXICON).unlink()
    report = audit_scene(fixture_store, "003", semantic=False)
    assert [entry.check for entry in report.skipped] == ["FR-AUD-05"]
    assert paths.LEXICON in report.skipped[0].reason
    assert all(finding.invariant != INVARIANT for finding in report.violations)
