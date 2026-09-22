"""FR-STORE-05 — paths derive from identifiers inside the store layer, and nowhere else.

The grammar is not decoration. `definitions.md` opens with it: identifiers are stable
forever, because renaming an entity breaks every edge that points at it. A store that accepts
`Mara`, `mara ` and `mara/../../etc` as three spellings of one character is a store whose
graph has three nodes where the novel has one.

The traversal cases are the security half. Paths come from route parameters, so a check that
lives anywhere other than between the identifier and the filesystem is a check that can be
walked around.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.commons.stores import paths


# spec 001 / AC 2 — the entity grammar.
@pytest.mark.parametrize("good", ["mara", "hab-ring", "fold_drive", "a", "x1", "0rbit"])
def test_valid_entity_ids_are_returned_unchanged(good: str) -> None:
    assert paths.entity_id(good) == good


# spec 001 / AC 2
@pytest.mark.parametrize(
    "bad",
    ["Mara", "mara ", " mara", "-mara", "_mara", "", "mara/ilan", "mara.md", "ma ra", "..", "."],
    ids=repr,
)
def test_identifiers_outside_the_grammar_are_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="not a valid entity id"):
        paths.entity_id(bad)


# spec 001 / AC 2 — `NNN`, and only `NNN`.
@pytest.mark.parametrize("good", ["001", "014", "999", "000"])
def test_valid_scene_ids(good: str) -> None:
    assert paths.scene_id(good) == good


# spec 001 / AC 2
@pytest.mark.parametrize("bad", ["1", "14", "0014", "01a", "", "abc", "-14", " 14"], ids=repr)
def test_scene_ids_outside_the_grammar_are_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="not a valid scene id"):
        paths.scene_id(bad)


# spec 001 / AC 2 — the storage layout, path by path.
def test_paths_match_the_storage_layout() -> None:
    assert paths.PROJECT == "canon/project.md"
    assert paths.STYLE == "canon/style.md"
    assert paths.LEXICON == "canon/lexicon.yaml"
    assert paths.TIME == "canon/time.yaml"
    assert paths.canon_entity("axioms", "fold-drive") == "canon/axioms/fold-drive.md"
    assert paths.cast_file("mara", "dossier") == "cast/mara/dossier.md"
    assert paths.cast_file("mara", "voice") == "cast/mara/voice.md"
    assert paths.cast_file("mara", "knowledge") == "cast/mara/knowledge.yaml"
    assert paths.cast_file("mara", "changes") == "cast/mara/changes.yaml"
    assert paths.RELATIONSHIPS == "cast/relationships.yaml"
    assert paths.ARCS == "structure/arcs.yaml"
    assert paths.CHAPTERS == "structure/chapters.yaml"
    assert paths.scene("014") == "scenes/014.yaml"
    assert paths.draft("014") == "manuscript/014.md"
    assert paths.digest("014") == "manuscript/digests/014.md"
    assert paths.ledger("violations") == "ledger/violations.yaml"


# spec 001 / AC 2 — a kind or file the layout does not name has no path at all.
@pytest.mark.parametrize("kind", ["secrets", "axiom", "Axioms", "", "../canon"], ids=repr)
def test_unknown_canon_kinds_are_refused(kind: str) -> None:
    with pytest.raises(ValueError, match="not a canon kind"):
        paths.canon_entity(kind, "fold-drive")


# spec 001 / AC 2
@pytest.mark.parametrize("name", ["notes", "proposed.yaml", "", "violations "], ids=repr)
def test_unknown_ledger_files_are_refused(name: str) -> None:
    with pytest.raises(ValueError, match="not a ledger file"):
        paths.ledger(name)


# spec 001 / AC 2 — an identifier can never become a path that leaves the root.
@pytest.mark.parametrize(
    "hostile",
    ["../../etc/passwd", "..", "mara/../../..", "/etc/passwd", "C:/Windows", "mara\x00"],
    ids=repr,
)
def test_hostile_identifiers_never_reach_a_path(hostile: str) -> None:
    with pytest.raises(ValueError):
        paths.canon_entity("axioms", hostile)
    with pytest.raises(ValueError):
        paths.cast_file(hostile, "dossier")


# spec 001 / AC 2 — and `resolve` refuses again after resolution, which also catches a
# symlink pointing out of the tree.
def test_resolve_refuses_to_leave_the_root(tmp_path: Path) -> None:
    root = tmp_path / "story"
    root.mkdir()
    for escape in ["../outside.yaml", "canon/../../outside.yaml", "/etc/passwd"]:
        with pytest.raises(ValueError):
            paths.resolve(root, escape)


# spec 001 / AC 2
def test_resolve_and_relative_to_root_are_inverses(tmp_path: Path) -> None:
    root = tmp_path / "story"
    (root / "canon" / "axioms").mkdir(parents=True)
    target = paths.resolve(root, "canon/axioms/fold-drive.md")
    target.write_text("x", encoding="utf-8")
    assert paths.relative_to_root(root, target) == "canon/axioms/fold-drive.md"


# spec 001 / AC 2 — Windows separators are normalised; the layout is written in POSIX.
def test_windows_separators_resolve(tmp_path: Path) -> None:
    root = tmp_path / "story"
    root.mkdir()
    assert paths.resolve(root, "canon\\axioms\\x.md") == paths.resolve(root, "canon/axioms/x.md")
