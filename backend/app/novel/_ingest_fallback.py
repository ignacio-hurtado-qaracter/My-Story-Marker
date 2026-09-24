"""Minimal brief ingest, used only when B2's `app.interview.service.ingest_brief` is not
importable (spec 007). It follows the contracts page: the same fact keys and kinds, the
same mandatory set, characters for recipient and people, places, novel-scope forbidden
terms. No schema validation beyond "is a JSON object with a recipient name".
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from pydantic import JsonValue

from app.bible import BibleRepository


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-") or "x"


def _items(brief: Mapping[str, JsonValue], key: str) -> list[Mapping[str, JsonValue]]:
    raw = brief.get(key)
    return [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def _s(value: JsonValue | None) -> str:
    return value if isinstance(value, str) else ""


def _list(value: JsonValue | None) -> list[str]:
    return [str(v) for v in value if isinstance(v, str)] if isinstance(value, list) else []


def ingest_brief(
    repo: BibleRepository, brief: Mapping[str, JsonValue], *, novel_id: str | None = None
) -> str:
    recipient = brief.get("recipient")
    if not isinstance(recipient, Mapping) or not _s(recipient.get("name")):
        message = "the brief needs recipient.name"
        raise ValueError(message)
    name = _s(recipient.get("name"))
    novel = repo.create_novel(
        novel_id=novel_id, recipient_name=name, dedication=_s(brief.get("dedication")) or None
    )
    nid = novel.id
    repo.save_brief(nid, dict(brief), valid=True)

    def fact(key: str, value: str, kind: str, *, mandatory: bool) -> int:
        return repo.add_fact(
            nid, key=key, value=value, kind=kind, source="interview", mandatory=mandatory
        ).id

    rid = fact("recipient.name", name, "recipient", mandatory=True)
    age = recipient.get("age")
    if isinstance(age, int):
        fact("recipient.age", str(age), "recipient", mandatory=False)
    if _s(recipient.get("profession")):
        fact("recipient.profession", _s(recipient.get("profession")), "recipient", mandatory=False)
    for n, trait in enumerate(_list(recipient.get("traits")) + _list(recipient.get("hobbies")), 1):
        fact(f"trait.{n}", trait, "trait", mandatory=False)
    repo.add_character(
        nid,
        name=name,
        role="protagonista",
        birth_date=_s(recipient.get("birth_date")) or None,
        description=", ".join(_list(recipient.get("traits"))),
        fact_id=rid,
    )
    if _s(brief.get("occasion")):
        fact("occasion", _s(brief.get("occasion")), "occasion", mandatory=False)
    for person in _items(brief, "people"):
        pname = _s(person.get("name"))
        if not pname:
            continue
        pid = fact(f"person.{slug(pname)}.name", pname, "person", mandatory=True)
        repo.add_character(
            nid,
            name=pname,
            role=_s(person.get("relation")),
            birth_date=_s(person.get("birth_date")) or None,
            description=", ".join(_list(person.get("traits"))),
            fact_id=pid,
        )
    for pet in _items(brief, "pets"):
        pname = _s(pet.get("name"))
        if not pname:
            continue
        pid = fact(f"pet.{slug(pname)}.name", pname, "pet", mandatory=True)
        repo.add_character(
            nid,
            name=pname,
            role=f"mascota ({_s(pet.get('species'))})",
            description=_s(pet.get("description")),
            fact_id=pid,
        )
    for place in _items(brief, "places"):
        pname = _s(place.get("name"))
        if not pname:
            continue
        pid = fact(f"place.{slug(pname)}", pname, "place", mandatory=False)
        repo.add_place(nid, name=pname, description=_s(place.get("description")), fact_id=pid)
    for memory in _items(brief, "memories"):
        title = _s(memory.get("title"))
        text = f"{title}: {_s(memory.get('description'))}"
        if _s(memory.get("date")):
            text += f" (fecha: {_s(memory.get('date'))})"
        fact(f"memory.{slug(title)}", text, "memory", mandatory=True)
    for n, element in enumerate(_list(brief.get("mandatory_elements")), 1):
        fact(f"element.{n}", element, "element", mandatory=True)
    for term in _list(brief.get("forbidden_terms")):
        repo.add_forbidden_term(term, scope="novel", novel_id=nid, reason="brief")
    return nid


__all__ = ["ingest_brief", "slug"]
