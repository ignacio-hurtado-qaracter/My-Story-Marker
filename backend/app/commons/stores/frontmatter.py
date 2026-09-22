"""Serialisation for the two file shapes the storage layout uses.

The layout is explicit about the split and why it exists: *YAML frontmatter for what must be
queried, prose for what the model must feel*. So there are exactly two shapes here, and a
store file is one or the other:

* **YAML** (`.yaml`) -- a whole record as a mapping.
* **Markdown with frontmatter** (`.md`) -- typed frontmatter plus a body (DR-02). The body is
  the part a model reads for texture: the canonical sample prose in `style.md`, the sensory
  palette of a location, and the scene itself in `manuscript/NNN.md`.

Everything goes through `safe_load` and `safe_dump` (NFR-03). Nothing here can construct an
arbitrary Python object out of a file an agent wrote, which is the whole of bandit's B506 in
one sentence.

**Why the split is written out here rather than taken from `python-frontmatter`.** Plan
decision P2 chose that library, and it is a good one, but it strips leading and trailing
whitespace from the body. For `manuscript/NNN.md` the body *is* the novel: a deliberate blank
line at the end of a scene is a beat, an indented opening is a choice, and `literal_tail` is
carried forward precisely because "summaries preserve what happened and lose how it sounded".
A store layer that silently normalises prose loses bytes the writer meant, and the loss is
invisible -- the file still parses, still validates, and reads almost the same. The round-trip
property of AC 4 is what surfaced it. The frontmatter block itself is still `yaml.safe_load`,
so P2's actual reason -- safety, and no `ruamel` -- is untouched; only the body is handled
here, and it is handled by not touching it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

import yaml

BODY_FIELD: Final[str] = "body"
"""DR-02. The field every Markdown-backed model carries beside its frontmatter."""

DELIMITER: Final[str] = "---"


def parse_yaml(text: str) -> dict[str, object]:
    """A YAML store file as a mapping. An empty file is an empty mapping, not `None`."""
    loaded = yaml.safe_load(text)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        message = f"expected a YAML mapping at the top level, got {type(loaded).__name__}"
        raise ValueError(message)
    return {str(key): value for key, value in loaded.items()}


def render_yaml(data: Mapping[str, object]) -> str:
    """`safe_dump`, block style, keys in the order the model declares them.

    `sort_keys=False` on purpose: a record whose fields keep the order of the model reads like
    the table in `definitions.md`, and these files are edited by hand as often as by the
    backend.
    """
    return yaml.safe_dump(
        dict(data),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )


def parse_markdown(text: str) -> dict[str, object]:
    """A Markdown-with-frontmatter file as one mapping, the prose under `body` (DR-02).

    Returning a single mapping rather than a pair is deliberate: the model declares the
    frontmatter fields and `body` together, so the reader hands the whole thing to
    `model_validate` and a missing `body` is a validation error like any other.

    The body is returned **verbatim**, apart from the single newline that separates it from
    the closing delimiter, which `render_markdown` puts there and this takes back out.
    """
    normalised = text.replace("\r\n", "\n")
    if not normalised.startswith(f"{DELIMITER}\n"):
        # No frontmatter at all: the whole file is the body. A model that requires
        # frontmatter fields will then fail validation naming them, which is the right error.
        return {BODY_FIELD: text}

    closing = normalised.find(f"\n{DELIMITER}\n", len(DELIMITER))
    if closing == -1:
        message = "frontmatter block is opened but never closed"
        raise ValueError(message)

    block = normalised[len(DELIMITER) + 1 : closing + 1]
    body = normalised[closing + len(DELIMITER) + 2 :]
    if body.startswith("\n"):
        body = body[1:]

    record: dict[str, object] = dict(parse_yaml(block))
    record[BODY_FIELD] = body
    return record


def render_markdown(record: Mapping[str, object]) -> str:
    """The inverse. `body` becomes the prose, byte for byte; everything else is frontmatter."""
    metadata = {key: value for key, value in record.items() if key != BODY_FIELD}
    body = record.get(BODY_FIELD, "")
    if not isinstance(body, str):
        message = f"{BODY_FIELD!r} must be a string, got {type(body).__name__}"
        raise TypeError(message)
    return f"{DELIMITER}\n{render_yaml(metadata)}{DELIMITER}\n\n{body}"


def is_markdown(relative: str) -> bool:
    """Which of the two shapes a store path uses, decided by extension alone."""
    return relative.endswith(".md")


__all__ = [
    "BODY_FIELD",
    "DELIMITER",
    "is_markdown",
    "parse_markdown",
    "parse_yaml",
    "render_markdown",
    "render_yaml",
]
