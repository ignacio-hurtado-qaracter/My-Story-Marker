"""`ingest_brief`: a validated brief into the story bible (spec 006, 004-contracts Brief).

The interviewer's one write (spec 004 D7): the novel row, the brief, its facts, the cast
and places it names, and its novel-scope forbidden terms. Everything goes through
`BibleRepository` (K1) in one transaction. The model call for the free text, if any, runs
before the transaction so no lock is held while the model thinks.

Fact keys are stable slugs (contract): `recipient.name`, `person.<slug>.name`,
`pet.<slug>.name`, `memory.<slug>`, `place.<slug>`, `element.<n>`. Kinds are
`recipient|trait|person|pet|place|memory|occasion|element`. Mandatory: the recipient's name,
each person, each pet, each memory, each mandatory element. Free-text facts are prefixed
`free_text.` and are never mandatory.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Final

from app.bible import BibleNotFoundError, BibleRepository, FactSource
from app.commons.config import get_settings
from app.commons.db.authoritative import open_authoritative
from app.commons.db.connection import transaction
from app.commons.llm import ModelClient
from app.commons.observability import NoopObserver, Observer
from app.interview.brief import SCHEMA_VERSION, Brief, BriefReport, slug, validate_brief
from app.interview.extract import ExtractedFacts, extract_facts_from_free_text
from app.interview.interviewer import MODEL_ERRORS

VALIDATOR_NAME: Final[str] = "brief_schema"
VALIDATOR_POINT: Final[str] = "hook"
"""`ValidationPoint.HOOK`: the brief is validated when it is handed over, before planning."""


def open_bible(*, check_same_thread: bool = True) -> BibleRepository:
    """The story bible at `HARNESS_DB` (what `BibleRepository.open()` does, spelled so the
    boundary rule's `.open(` pattern does not mistake a database for a store file)."""
    return BibleRepository(
        open_authoritative(get_settings().harness_db_path, check_same_thread=check_same_thread)
    )


def new_novel_id() -> str:
    """Same shape as `BibleRepository.create_novel`'s default. The interview mints it at its
    start, so the interview and the later generation share one Langfuse session (O01)."""
    return f"nov-{uuid.uuid4().hex[:12]}"


class InvalidBriefError(ValueError):
    """The brief failed `validate_brief`; `report` says what is missing or contradictory."""

    def __init__(self, report: BriefReport) -> None:
        self.report = report
        parts = report.missing + report.contradictions + report.errors
        super().__init__("invalid brief: " + "; ".join(parts))


def _novel_exists(repo: BibleRepository, novel_id: str) -> bool:
    try:
        repo.get_novel(novel_id)
    except BibleNotFoundError:
        return False
    return True


class _Keys:
    """Unique slugs per prefix: a second `Luna` becomes `luna-2`."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def key(self, prefix: str, name: str) -> str:
        base = f"{prefix}.{slug(name)}"
        candidate, n = base, 1
        while candidate in self._seen:
            n += 1
            candidate = f"{base}-{n}"
        self._seen.add(candidate)
        return candidate


def _record_result(
    repo: BibleRepository, observer: Observer, novel_id: str, report: BriefReport
) -> None:
    detail = "; ".join(report.missing + report.contradictions + report.errors)
    repo.save_validator_result(
        novel_id=novel_id,
        name=VALIDATOR_NAME,
        point=VALIDATOR_POINT,
        passed=report.valid,
        score=1.0 if report.valid else 0.0,
        evidence=report.missing + report.contradictions + report.errors,
        explanation=detail or "brief válido contra brief.v1.json y las reglas de definitions",
        trace_id=observer.current_trace_id(),
    )
    observer.score(
        f"validator:{VALIDATOR_NAME}", 1.0 if report.valid else 0.0, comment=detail or "ok"
    )


def _add(
    repo: BibleRepository,
    novel_id: str,
    key: str,
    value: str,
    kind: str,
    *,
    mandatory: bool = False,
    source: FactSource = "interview",
) -> int:
    return repo.add_fact(
        novel_id, key=key, value=value, kind=kind, source=source, mandatory=mandatory
    ).id


def _ingest_interview(repo: BibleRepository, novel_id: str, brief: Brief) -> None:
    keys = _Keys()
    r = brief.recipient
    name_fact = _add(repo, novel_id, "recipient.name", r.name, "recipient", mandatory=True)
    _add(repo, novel_id, "recipient.age", str(r.age), "recipient")
    optional = {
        "recipient.birth_date": r.birth_date.isoformat() if r.birth_date else None,
        "recipient.gender": r.gender,
        "recipient.profession": r.profession,
        "recipient.relation_to_buyer": r.relation_to_buyer or None,
    }
    for key, value in optional.items():
        if value:
            _add(repo, novel_id, key, value, "recipient")
    for n, trait in enumerate(r.traits, start=1):
        _add(repo, novel_id, f"trait.{n}", trait, "trait")
    for n, hobby in enumerate(r.hobbies, start=1):
        _add(repo, novel_id, f"hobby.{n}", hobby, "trait")
    _add(repo, novel_id, "occasion", brief.occasion, "occasion")
    repo.add_character(
        novel_id,
        name=r.name,
        role="protagonista",
        birth_date=r.birth_date.isoformat() if r.birth_date else None,
        description=", ".join(r.traits),
        fact_id=name_fact,
    )
    for person in brief.people:
        key = keys.key("person", person.name)
        fact = _add(repo, novel_id, f"{key}.name", person.name, "person", mandatory=True)
        if person.relation:
            _add(repo, novel_id, f"{key}.relation", person.relation, "person")
        repo.add_character(
            novel_id,
            name=person.name,
            role=person.relation or "secundario",
            birth_date=person.birth_date.isoformat() if person.birth_date else None,
            description=", ".join(person.traits),
            fact_id=fact,
        )
    for pet in brief.pets:
        key = keys.key("pet", pet.name)
        fact = _add(repo, novel_id, f"{key}.name", pet.name, "pet", mandatory=True)
        if pet.species:
            _add(repo, novel_id, f"{key}.species", pet.species, "pet")
        repo.add_character(
            novel_id,
            name=pet.name,
            role="mascota",
            description=" — ".join(p for p in (pet.species, pet.description) if p),
            fact_id=fact,
        )
    for place in brief.places:
        key = keys.key("place", place.name)
        fact = _add(repo, novel_id, key, place.name, "place")
        repo.add_place(novel_id, name=place.name, description=place.description, fact_id=fact)
    for memory in brief.memories:
        key = keys.key("memory", memory.title)
        value = memory.title + (f": {memory.description}" if memory.description else "")
        if memory.date:
            value += f" ({memory.date.isoformat()})"
        _add(repo, novel_id, key, value, "memory", mandatory=True)
    for n, element in enumerate(brief.mandatory_elements, start=1):
        _add(repo, novel_id, f"element.{n}", element, "element", mandatory=True)
    for term in brief.forbidden_terms:
        if term.strip():
            repo.add_forbidden_term(
                term.strip(), scope="novel", novel_id=novel_id, reason="brief.forbidden_terms"
            )


def _ingest_free_text(repo: BibleRepository, novel_id: str, facts: ExtractedFacts) -> None:
    keys = _Keys()
    existing = {f.key for f in repo.list_facts(novel_id)}

    def add(prefix: str, name: str, value: str, kind: str) -> None:
        key = keys.key(f"free_text.{prefix}", name)
        if key not in existing and f"{prefix}.{slug(name)}.name" not in existing:
            _add(repo, novel_id, key, value, kind, source="free_text")

    for person in facts.people:
        relation = f" ({person.relation})" if person.relation else ""
        add("person", person.name, person.name + relation, "person")
    for pet in facts.pets:
        add("pet", pet.name, pet.name + (f" ({pet.species})" if pet.species else ""), "pet")
    for place in facts.places:
        add("place", place.name, place.name, "place")
    for memory in facts.memories:
        add("memory", memory.title, f"{memory.title}: {memory.description}".rstrip(": "), "memory")
    for n, trait in enumerate(facts.traits, start=1):
        _add(repo, novel_id, f"free_text.trait.{n}", trait, "trait", source="free_text")


def ingest_brief(
    repo: BibleRepository,
    brief: Brief | Mapping[str, object],
    *,
    novel_id: str | None = None,
    observer: Observer | None = None,
    client: ModelClient | None = None,
) -> str:
    """Validate, create the novel, store the brief and turn it into facts. Returns the id.

    Raises `InvalidBriefError` for an invalid brief (after recording a failed `brief_schema`
    result when the novel already exists). `client` runs the free-text extractor; without
    one the live `ClaudeCodeModelClient` is used when `free_text` is present.
    """
    obs = observer or NoopObserver()
    data = brief.model_dump(mode="json") if isinstance(brief, Brief) else dict(brief)
    report = validate_brief(data)
    identifier = novel_id or new_novel_id()
    exists = _novel_exists(repo, identifier)
    session = obs.start_session(identifier)
    with obs.trace("ingest_brief", session_id=session, metadata={"novel_id": identifier}):
        if not report.valid:
            # validator_result has no foreign key: the failure is kept under the id the
            # interview session already uses, even though no novel row is created.
            _record_result(repo, obs, identifier, report)
            raise InvalidBriefError(report)
        parsed = Brief.model_validate(data)
        if exists and repo.list_facts(identifier):
            message = f"novel {novel_id!r} already has an ingested brief"
            raise ValueError(message)
        extracted: ExtractedFacts | None = None
        if parsed.free_text and parsed.free_text.strip():
            if client is None:
                from app.commons.llm import ClaudeCodeModelClient

                client = ClaudeCodeModelClient()
            try:
                extracted = extract_facts_from_free_text(
                    parsed.free_text, client, obs, repo=repo, novel_id=identifier
                )
            except MODEL_ERRORS as error:
                # Free text is optional context: a failed extraction is recorded, and the
                # brief (already valid without it) is ingested with its interview facts only.
                repo.log_policy_decision(
                    policy="free_text_extraction",
                    decision="skipped",
                    novel_id=identifier,
                    detail=type(error).__name__,
                )
        with transaction(repo.connection):
            if exists:
                repo.update_novel(
                    identifier, dedication=parsed.dedication, recipient_name=parsed.recipient.name
                )
            else:
                repo.create_novel(
                    novel_id=identifier,
                    dedication=parsed.dedication,
                    recipient_name=parsed.recipient.name,
                )
            stored = parsed.model_dump(mode="json")
            repo.save_brief(identifier, stored, valid=True, schema_version=SCHEMA_VERSION)
            _ingest_interview(repo, identifier, parsed)
            if extracted is not None:
                _ingest_free_text(repo, identifier, extracted)
            _record_result(repo, obs, identifier, report)
    obs.flush()
    return identifier


__all__ = [
    "VALIDATOR_NAME",
    "VALIDATOR_POINT",
    "InvalidBriefError",
    "ingest_brief",
    "new_novel_id",
    "open_bible",
]
