"""Typed reads. Every store file becomes a validated record or an error naming what is wrong.

FR-STORE-06: a file that fails validation raises `InvalidRecord` naming file and field; **it
is never repaired and never partially returned.** The temptation to fill in a missing field
with a default is the thing this refuses. A record the system quietly fixed is a record whose
author and whose reader believe different things, and nothing downstream can tell.

FR-STORE-08: no in-process cache across requests, so an edit made in an editor or by a human
between two calls is seen immediately. The tree is a git working tree that people edit.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.commons.errors import InvalidRecord, NotFound
from app.commons.stores import frontmatter as fm
from app.commons.stores import paths


def exists(root: Path, relative: str) -> bool:
    try:
        return paths.resolve(root, relative).is_file()
    except ValueError:
        return False


def read_raw(root: Path, relative: str) -> str:
    """The file's text, for the few callers that need bytes rather than a record: hashing a
    tree, diffing a draft. Everything that reasons about content goes through `read_record`."""
    target = paths.resolve(root, relative)
    if not target.is_file():
        raise NotFound(f"no store file at {relative}", identifier=relative)
    return target.read_text(encoding="utf-8")


def read_record[RecordT: BaseModel](root: Path, relative: str, model: type[RecordT]) -> RecordT:
    """Read, parse by extension, validate. The only way a store file becomes an object.

    The model is a parameter rather than something looked up here on purpose: `commons/` must
    not know a feature's name (NFR-04), so `app/canon/repository.py` passes `Axiom` and the
    store layer stays ignorant of what an axiom is.
    """
    text = read_raw(root, relative)
    try:
        record = fm.parse_markdown(text) if fm.is_markdown(relative) else fm.parse_yaml(text)
    except (ValueError, TypeError) as error:
        raise InvalidRecord(f"{relative} is not readable: {error}", file=relative) from error

    if fm.is_markdown(relative) and fm.BODY_FIELD not in model.model_fields:
        record = _without_empty_body(relative, record, model)

    try:
        return model.model_validate(record)
    except ValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or None
        raise InvalidRecord(
            f"{relative} does not match {model.__name__}: {first['msg']}"
            + (f" (at {field})" if field else ""),
            file=relative,
            field=field,
        ) from error


def _without_empty_body(
    relative: str, record: dict[str, object], model: type[BaseModel]
) -> dict[str, object]:
    """Drop the `body` a Markdown file always has when the model has no place for it.

    Not every `.md` store file carries prose. A scene digest is all frontmatter -- its prose
    *is* `delta` (DR-11) -- and `manuscript/digests/NNN.md` is a `.md` file only because the
    storage layout says so. `parse_markdown` cannot know that, so it always produces a `body`,
    and a model with `extra="forbid"` would reject every such file.

    Prose that is actually there is a different matter and is **not** dropped: a file with a
    body under a model that has nowhere to put it means someone wrote text the system will
    never read, and losing it silently is exactly the kind of quiet divergence FR-STORE-06
    exists to prevent.
    """
    body = record.pop(fm.BODY_FIELD, "")
    if isinstance(body, str) and body.strip():
        message = (
            f"{relative} carries prose in its body, but {model.__name__} has no `body` field "
            "to put it in; the text would be silently lost"
        )
        raise InvalidRecord(message, file=relative, field=fm.BODY_FIELD)
    return record


def parse_for_test[RecordT: BaseModel](
    relative: str, text: str, model: type[RecordT]
) -> dict[str, object]:
    """The parse half of `read_record`, without the filesystem.

    Exists so a test can round-trip a record through its real **file format** rather than
    through `model_dump`. That distinction is not academic: it is the difference the digest
    defect fell through, where every file was unreadable while the object-level round trip
    was green.
    """
    record = fm.parse_markdown(text) if fm.is_markdown(relative) else fm.parse_yaml(text)
    if fm.is_markdown(relative) and fm.BODY_FIELD not in model.model_fields:
        record = _without_empty_body(relative, record, model)
    return record


def list_records(root: Path, directory: str, suffix: str) -> list[str]:
    """Store-relative paths of every file directly under `directory`, sorted.

    Sorted because callers iterate it to build the index and to reconcile, and an order that
    depends on the filesystem would make `rebuild()` twice produce two different row orders --
    which AC 6 asserts cannot happen.
    """
    try:
        target = paths.resolve(root, directory)
    except ValueError:
        return []
    if not target.is_dir():
        return []
    return sorted(
        paths.relative_to_root(root, child)
        for child in target.iterdir()
        if child.is_file() and child.name.endswith(suffix)
    )


def list_subdirectories(root: Path, directory: str) -> list[str]:
    """Immediate subdirectory names, sorted. `cast/` is the only place this is needed: one
    directory per character, named by the character's id."""
    try:
        target = paths.resolve(root, directory)
    except ValueError:
        return []
    if not target.is_dir():
        return []
    return sorted(child.name for child in target.iterdir() if child.is_dir())


__all__ = [
    "exists",
    "list_records",
    "list_subdirectories",
    "parse_for_test",
    "read_raw",
    "read_record",
]
