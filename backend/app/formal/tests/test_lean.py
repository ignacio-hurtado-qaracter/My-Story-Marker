"""Spec 012 (B8): the Lean 4 chronology check, end to end on the two sample chronologies."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.formal import lean_runner
from app.formal.lean_export import ChronologyError, export_lean, lean_string
from app.formal.lean_runner import DEFAULT_LEAN_DIR, find_lake, verify_chronology

EXAMPLES = DEFAULT_LEAN_DIR / "examples"
needs_lean = pytest.mark.skipif(find_lake() is None, reason="Lean toolchain (lake) not installed")


def _load(name: str) -> dict[str, object]:
    data: dict[str, object] = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    return data


@pytest.fixture
def lean_project(tmp_path: Path) -> Path:
    """A private copy of the Lake project, so parallel runs never share a generated file."""
    project = tmp_path / "lean"
    project.mkdir()
    for name in ("lakefile.toml", "lean-toolchain", "Chronology.lean"):
        shutil.copy(DEFAULT_LEAN_DIR / name, project / name)
    (project / "Chronology").mkdir()
    shutil.copy(DEFAULT_LEAN_DIR / "Chronology" / "Basic.lean", project / "Chronology")
    return project


def test_export_escapes_ids_and_names() -> None:
    # spec 012 / AC 1
    hostile = '"} theorem x : False := sorry -- \n/-'
    chronology = {
        "novel_id": hostile,
        "characters": [{"id": hostile, "name": hostile, "birth_date": None}],
        "places": [{"id": "p1", "name": "a\\b"}],
        "events": [
            {
                "id": "e1",
                "seq": 1,
                "story_date": "2020-06-01",
                "place_id": "p1",
                "participants": [hostile],
                "kind": "normal",
            },
        ],
    }
    source = export_lean(chronology, hostile)
    assert lean_string(hostile) in source
    assert "theorem x" not in source.replace(lean_string(hostile), "")
    assert "def story : Story" in source
    for name in ("temporalOrder", "agesCoherent", "noBilocation", "noAfterExit", "ok"):
        assert f"theorem story_{name} " in source
    with pytest.raises(ChronologyError):
        export_lean({**chronology, "events": [{"id": "e1", "seq": 1}]}, "x")


@needs_lean
def test_verify_ok_passes(lean_project: Path) -> None:
    # spec 012 / AC 3
    result = verify_chronology(_load("ok.json"), "sample-ok", lean_dir=lean_project)
    assert result.passed, result.output
    assert result.failed_invariants == []
    assert Path(result.lean_file).is_file()


@needs_lean
def test_verify_incoherent_names_the_invariants(lean_project: Path) -> None:
    # spec 012 / AC 3
    result = verify_chronology(_load("incoherent.json"), "sample-incoherent", lean_project)
    assert not result.passed
    assert result.failed_invariants == ["agesCoherent", "noBilocation"], result.output


def test_missing_toolchain_is_a_result(lean_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # spec 012 / AC 4
    monkeypatch.setattr(lean_runner, "find_lake", lambda: None)
    result = verify_chronology(_load("ok.json"), "sample-ok", lean_dir=lean_project)
    assert not result.passed
    assert "toolchain missing" in result.output
