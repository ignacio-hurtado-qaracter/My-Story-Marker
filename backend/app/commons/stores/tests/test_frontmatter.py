"""DR-02, and the property that made this module hand-written: the body survives byte for
byte.

For `manuscript/NNN.md` the body *is* the novel. A deliberate blank line at the end of a
scene is a beat, an indented opening is a choice, and `literal_tail` exists because
"summaries preserve what happened and lose how it sounded". A store layer that normalises
prose loses bytes the writer meant, and loses them invisibly: the file still parses, still
validates, and reads almost the same.

`python-frontmatter`, which plan decision P2 chose, strips leading and trailing whitespace
from the body. That is the one thing this layer may not do, so the split is written out in
`frontmatter.py` and these are the cases that pin it.
"""

from __future__ import annotations

import pytest

from app.commons.stores.frontmatter import (
    is_markdown,
    parse_markdown,
    parse_yaml,
    render_markdown,
    render_yaml,
)

BODIES = [
    "The gate held.\n\nShe counted the seconds and did not move.\n",
    "  an indented opening\n",
    "a scene that ends on a deliberate blank line\n\n",
    "",
    "\na leading newline that is part of the prose\n",
    "no trailing newline at all",
    "a line with --- inside it\nand another after\n",
    "trailing spaces matter too   \n",
    "unicode: the fold drive hummed - en dash, curly quotes\n",
]


# spec 001 / AC 4 — DR-02.
@pytest.mark.parametrize("body", BODIES, ids=repr)
def test_the_body_survives_byte_for_byte(body: str) -> None:
    record = {"scene_ref": "014", "words": 3, "body": body}
    assert parse_markdown(render_markdown(record))["body"] == body


# spec 001 / AC 4 — and so does the frontmatter beside it.
@pytest.mark.parametrize("body", BODIES, ids=repr)
def test_the_frontmatter_survives_with_it(body: str) -> None:
    record = {"scene_ref": "014", "words": 3, "level": "scene", "body": body}
    parsed = parse_markdown(render_markdown(record))
    assert parsed["scene_ref"] == "014"
    assert parsed["words"] == 3
    assert parsed["level"] == "scene"


# spec 001 / AC 4 — rendering is idempotent, so a rewrite with no change writes no diff.
@pytest.mark.parametrize("body", BODIES, ids=repr)
def test_rendering_is_idempotent(body: str) -> None:
    record = {"scene_ref": "014", "body": body}
    once = render_markdown(record)
    assert render_markdown(parse_markdown(once)) == once


# spec 001 / AC 4 — a file with no frontmatter is all body, and a model that needs fields
# then fails validation naming them, which is the right error rather than a parse crash.
def test_a_file_without_frontmatter_is_all_body() -> None:
    assert parse_markdown("Just prose.\n") == {"body": "Just prose.\n"}


# spec 001 / AC 4 — an unterminated block is an error, not a guess.
def test_an_unclosed_frontmatter_block_is_refused() -> None:
    with pytest.raises(ValueError, match="never closed"):
        parse_markdown("---\nscene_ref: '014'\nstill going\n")


# spec 001 / AC 4 — CRLF is normalised on read; the repository is checked out on Windows.
def test_crlf_input_parses() -> None:
    parsed = parse_markdown("---\r\nscene_ref: '014'\r\n---\r\n\r\nThe gate held.\r\n")
    assert parsed["scene_ref"] == "014"
    assert parsed["body"] == "The gate held.\n"


# spec 001 / NFR-03 — nothing here can construct an arbitrary Python object.
def test_yaml_loading_is_safe() -> None:
    with pytest.raises(yaml_error_types()):
        parse_yaml("!!python/object/apply:os.system ['echo unsafe']\n")


def yaml_error_types() -> type[Exception] | tuple[type[Exception], ...]:
    import yaml

    return (yaml.YAMLError, ValueError)


# spec 001 / AC 4 — an empty YAML file is an empty mapping, not `None`.
def test_empty_yaml_is_an_empty_mapping() -> None:
    assert parse_yaml("") == {}
    assert parse_yaml("\n# only a comment\n") == {}


# spec 001 / AC 4 — a YAML file whose top level is not a mapping is refused.
@pytest.mark.parametrize("text", ["- a\n- b\n", "just a string\n", "42\n"], ids=repr)
def test_non_mapping_yaml_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="mapping at the top level"):
        parse_yaml(text)


# spec 001 / AC 4 — field order follows the model, so the file reads like definitions.md.
def test_yaml_keeps_field_order() -> None:
    rendered = render_yaml({"schema_version": 1, "id": "014", "pov": "mara"})
    assert rendered.index("schema_version") < rendered.index("id") < rendered.index("pov")


# spec 001 / AC 4 — extension decides the shape, and nothing else does.
@pytest.mark.parametrize(
    ("path", "markdown"),
    [
        ("manuscript/014.md", True),
        ("manuscript/digests/014.md", True),
        ("canon/project.md", True),
        ("scenes/014.yaml", False),
        ("ledger/violations.yaml", False),
    ],
)
def test_the_extension_decides_the_shape(path: str, markdown: bool) -> None:
    assert is_markdown(path) is markdown
