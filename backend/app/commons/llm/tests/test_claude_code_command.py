"""AC 34: the `claude -p` invocation isolates the role and never uses an API key.

Every test replaces the subprocess with a `Recorder` (FR-LLM-02's runner seam), so nothing
here reaches a model or spends the user's Claude Code usage (NFR-06). What is inspected is
exactly what would have been spawned: the argv, the working directory and what is in it at
the moment of the call, the environment, stdin, and the system prompt file.

The recorder and the envelope builder below are also used by the other live-client tests of
this package (`test_structured_output`, `test_refusal`, `test_over_cap`).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import BaseModel, JsonValue

from app.commons.config import Settings
from app.commons.errors import ModelCallFailed
from app.commons.llm.claude_code_client import (
    REPOSITORY_ROOT,
    ClaudeCodeModelClient,
    RunResult,
    json_schema_argument,
    resolve_executable,
    run_subprocess,
    scrubbed_environment,
)
from app.commons.llm.protocol import (
    DATA_STATEMENT,
    INSTRUCTION_HEADER,
    Document,
    render_system,
)
from app.commons.permissions import AgentRole
from app.commons.schemas.role_outputs import (
    DigestOutput,
    ExtractOutput,
    PolishOutput,
    ReviseOutput,
    SemanticAuditOutput,
    WriterOutput,
)

VERSION_OUTPUT = "2.1.273 (Claude Code)\n"
REAL_MODEL = "claude-haiku-4-5-20251001"
SYSTEM = "You are the writer. Write the scene the instruction describes."
INSTRUCTION = "Write scene 004: the goal is to cross the gate before the fold closes."
DOCUMENTS = (
    Document("canon/project.md", "PROJECT-MARKER: a generation ship, told in close third."),
    Document("cast/ana/dossier.md", "DOSSIER-MARKER: Ana, pilot, afraid of open water."),
)
ROLE_SETTINGS = [
    f"{prefix}_{role.value.upper()}" for prefix in ("MODEL", "EFFORT") for role in AgentRole
]


def writer_payload() -> dict[str, JsonValue]:
    """A structured output that satisfies `WriterOutput`."""
    return {"body": "The gate held. Ana counted the seconds.", "proposed_facts": []}


def envelope(
    structured_output: JsonValue | None = None,
    *,
    stop_reason: str = "end_turn",
    subtype: str = "success",
    is_error: bool = False,
    api_error_status: JsonValue = None,
    stop_details: JsonValue = None,
    usage: Mapping[str, int] | None = None,
    model_usage: Mapping[str, Mapping[str, int]] | None = None,
    result: str = "",
    omit_structured_output: bool = False,
) -> str:
    """A `--output-format json` envelope shaped like Claude Code 2.1.273's."""
    body: dict[str, JsonValue] = {
        "type": "result",
        "subtype": subtype,
        "is_error": is_error,
        "stop_reason": stop_reason,
        "api_error_status": api_error_status,
        "result": result,
        "usage": dict(usage) if usage is not None else {"input_tokens": 12, "output_tokens": 34},
        "modelUsage": (
            {name: dict(entry) for name, entry in model_usage.items()}
            if model_usage is not None
            else {REAL_MODEL: {"inputTokens": 12, "outputTokens": 34}}
        ),
        "num_turns": 2,
        "total_cost_usd": 0.0,
        "duration_ms": 1,
        "session_id": "00000000-0000-0000-0000-000000000000",
    }
    if stop_details is not None:
        body["stop_details"] = stop_details
    if not omit_structured_output:
        body["structured_output"] = (
            structured_output if structured_output is not None else writer_payload()
        )
    return json.dumps(body)


@dataclass
class Invocation:
    """One spawn as the recorder saw it, including the state of the filesystem at that
    moment -- the working directory and the prompt file are gone once the call returns."""

    argv: list[str]
    stdin: str
    cwd: Path
    env: dict[str, str]
    timeout: float
    cwd_existed: bool
    cwd_entries: list[str]
    prompt_file: Path | None
    prompt_text: str | None

    def value_after(self, flag: str) -> str:
        return self.argv[self.argv.index(flag) + 1]


@dataclass
class Recorder:
    """The runner seam, recording. `--version` is answered on its own; every model call
    consumes one scripted response, and running out is a test bug, loudly."""

    responses: list[RunResult | str] = field(default_factory=list)
    invocations: list[Invocation] = field(default_factory=list)

    def __call__(
        self,
        argv: Sequence[str],
        *,
        stdin: str,
        cwd: Path,
        env: Mapping[str, str],
        timeout: float,
    ) -> RunResult:
        arguments = list(argv)
        prompt_file: Path | None = None
        prompt_text: str | None = None
        if "--system-prompt-file" in arguments:
            prompt_file = Path(arguments[arguments.index("--system-prompt-file") + 1])
            # Bytes, so a `\r\n` written on Windows would show rather than be read away.
            prompt_text = prompt_file.read_bytes().decode("utf-8")
        self.invocations.append(
            Invocation(
                argv=arguments,
                stdin=stdin,
                cwd=cwd,
                env=dict(env),
                timeout=timeout,
                cwd_existed=cwd.is_dir(),
                cwd_entries=sorted(entry.name for entry in cwd.iterdir()) if cwd.is_dir() else [],
                prompt_file=prompt_file,
                prompt_text=prompt_text,
            )
        )
        if arguments[1:] == ["--version"]:
            return RunResult(returncode=0, stdout=VERSION_OUTPUT, stderr="")
        assert self.responses, "the recorder has no scripted response left for this call"
        response = self.responses.pop(0)
        if isinstance(response, str):
            return RunResult(returncode=0, stdout=response, stderr="")
        return response

    @property
    def calls(self) -> list[Invocation]:
        """The model calls, without the version probe."""
        return [invocation for invocation in self.invocations if "-p" in invocation.argv]


@dataclass
class Harness:
    client: ClaudeCodeModelClient
    recorder: Recorder
    executable: Path
    store_root: Path
    sleeps: list[float]
    which_calls: list[str]


def harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *responses: RunResult | str,
    env: Mapping[str, str] | None = None,
    cap: int | None = None,
) -> Harness:
    """A live client whose subprocess is a recorder, bound to a temporary store root."""
    for name in [*ROLE_SETTINGS, "CLAUDE_CLI", "CLAUDE_TIMEOUT_SECONDS"]:
        monkeypatch.delenv(name, raising=False)
    store_root = tmp_path / "story"
    store_root.mkdir()
    monkeypatch.setenv("STORY_ROOT", str(store_root))
    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)
    executable = tmp_path / "bin" / "claude.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"")
    recorder = Recorder(list(responses))
    sleeps: list[float] = []
    which_calls: list[str] = []

    def which(name: str) -> str | None:
        which_calls.append(name)
        return str(executable)

    settings = Settings(_env_file=None)
    client = (
        ClaudeCodeModelClient(settings, runner=recorder, which=which, sleep=sleeps.append)
        if cap is None
        else ClaudeCodeModelClient(
            settings, runner=recorder, which=which, sleep=sleeps.append, cap=cap
        )
    )
    return Harness(client, recorder, executable, store_root, sleeps, which_calls)


def complete_writer(h: Harness, role: AgentRole = AgentRole.WRITER) -> WriterOutput:
    completion = h.client.complete(
        role=role,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )
    return completion.output


# spec 001 / AC 34 -- the command carries every isolation flag, and never --bare.
def test_the_command_isolates_the_role(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = harness(tmp_path, monkeypatch, envelope())
    complete_writer(h)

    [call] = h.recorder.calls
    argv = call.argv
    assert argv[0] == str(h.executable)
    assert "-p" in argv
    assert call.value_after("--output-format") == "json"
    assert call.value_after("--tools") == ""
    assert call.value_after("--setting-sources") == ""
    assert "--strict-mcp-config" in argv
    assert "--mcp-config" not in argv
    assert "--disable-slash-commands" in argv
    assert "--no-session-persistence" in argv
    assert json.loads(call.value_after("--json-schema")) == WriterOutput.model_json_schema()
    assert call.value_after("--model") == "claude-haiku-4-5"
    assert "--system-prompt-file" in argv
    assert "--system-prompt" not in argv
    assert "--bare" not in argv
    assert not any(argument.startswith("--bare") for argument in argv)


# spec 001 / AC 34 -- no positional prompt: nothing the model reads travels on the command line.
def test_no_prompt_text_is_on_the_command_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, envelope())
    complete_writer(h)

    [call] = h.recorder.calls
    command_line = "\n".join(call.argv)
    for text in [SYSTEM, INSTRUCTION, *(document.text for document in DOCUMENTS)]:
        assert text not in command_line


# spec 001 / AC 34, FR-LLM-03 -- the model is the role's; --effort only when the role has one.
@pytest.mark.parametrize(
    ("env", "role", "model", "effort"),
    [
        ({}, AgentRole.WRITER, "claude-haiku-4-5", None),
        ({"EFFORT_WRITER": "high"}, AgentRole.WRITER, "claude-haiku-4-5", "high"),
        ({"EFFORT_WRITER": ""}, AgentRole.WRITER, "claude-haiku-4-5", None),
        (
            {"MODEL_AUDITOR": "claude-sonnet-5", "EFFORT_AUDITOR": "xhigh"},
            AgentRole.AUDITOR,
            "claude-sonnet-5",
            "xhigh",
        ),
        ({"MODEL_AUDITOR": "claude-sonnet-5"}, AgentRole.WRITER, "claude-haiku-4-5", None),
    ],
    ids=["default", "effort-set", "effort-empty", "auditor-raised", "other-role-untouched"],
)
def test_model_and_effort_come_from_the_role(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    role: AgentRole,
    model: str,
    effort: str | None,
) -> None:
    h = harness(tmp_path, monkeypatch, envelope(), env=env)
    complete_writer(h, role)

    [call] = h.recorder.calls
    assert call.value_after("--model") == model
    if effort is None:
        assert "--effort" not in call.argv
    else:
        assert call.value_after("--effort") == effort


# spec 001 / AC 34, FR-LLM-03 -- an effort the CLI does not accept is a startup error.
def test_an_unknown_effort_is_a_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EFFORT_WRITER", "extreme")
    with pytest.raises(ValueError, match="EFFORT_WRITER"):
        Settings(_env_file=None)


# spec 001 / AC 34 -- the working directory is empty, and outside the repository and the store.
def test_the_working_directory_is_empty_and_outside_repository_and_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, envelope())
    complete_writer(h)

    [call] = h.recorder.calls
    cwd = call.cwd.resolve()
    assert call.cwd_existed
    assert call.cwd_entries == [], "the working directory must stay empty"
    assert not cwd.is_relative_to(REPOSITORY_ROOT)
    assert not cwd.is_relative_to(h.store_root.resolve())
    assert not h.store_root.resolve().is_relative_to(cwd)
    assert call.prompt_file is not None
    assert not call.prompt_file.resolve().is_relative_to(cwd), "the prompt file is elsewhere"
    assert not call.cwd.exists(), "the temporary working directory is removed afterwards"


# spec 001 / AC 34 -- each call gets a fresh working directory, never one reused.
def test_each_call_gets_a_fresh_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, envelope(), envelope())
    complete_writer(h)
    complete_writer(h)

    first, second = h.recorder.calls
    assert first.cwd != second.cwd


# spec 001 / AC 34, FR-LLM-05 -- a temporary directory inside the store root is refused.
def test_a_working_directory_inside_the_store_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, envelope(), env={"STORY_ROOT": tempfile.gettempdir()})
    h.client = ClaudeCodeModelClient(
        Settings(_env_file=None), runner=h.recorder, which=lambda _: str(h.executable)
    )
    with pytest.raises(ModelCallFailed) as raised:
        complete_writer(h)
    assert raised.value.context["reason"] == "workdir_not_isolated"
    assert h.recorder.invocations == []


# spec 001 / AC 34, FR-LLM-01 -- no Anthropic credential reaches the CLI, even when the
# parent's environment has both. The values are obvious test dummies.
def test_the_environment_carries_no_anthropic_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-dummy-api-key")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-dummy-auth-token")
    monkeypatch.setenv("MSM_TEST_MARKER", "kept")
    h = harness(tmp_path, monkeypatch, envelope())
    complete_writer(h)

    assert os.environ["ANTHROPIC_API_KEY"] == "test-dummy-api-key", "the parent is untouched"
    for invocation in h.recorder.invocations:
        names = {name.upper() for name in invocation.env}
        assert "ANTHROPIC_API_KEY" not in names
        assert "ANTHROPIC_AUTH_TOKEN" not in names
        assert invocation.env.get("MSM_TEST_MARKER") == "kept", "the rest is inherited"


# spec 001 / AC 34 -- the scrub is case-insensitive, as Windows environment names are.
def test_the_scrub_ignores_case() -> None:
    parent = {
        "anthropic_api_key": "test-dummy",
        "Anthropic_Auth_Token": "test-dummy",
        "ANTHROPIC_BASE_URL": "http://localhost",
        "PATH": "/usr/bin",
    }
    assert scrubbed_environment(parent) == {
        "ANTHROPIC_BASE_URL": "http://localhost",
        "PATH": "/usr/bin",
    }


# spec 001 / AC 34, FR-PERM-07 -- documents and instruction arrive on stdin, each document
# delimited and labelled with its path; the data statement is in the system prompt instead.
def test_documents_and_instruction_go_on_stdin_labelled_with_their_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, envelope())
    complete_writer(h)

    [call] = h.recorder.calls
    stdin = call.stdin
    assert stdin.startswith("=== BEGIN DOCUMENT ")
    assert DATA_STATEMENT not in stdin
    positions = []
    for document in DOCUMENTS:
        label = f"path={document.path} ==="
        assert label in stdin
        assert document.text in stdin
        positions.append(stdin.index(document.text))
    assert positions == sorted(positions), "documents keep the order they were given in"
    assert stdin.index(INSTRUCTION_HEADER) > max(positions)
    assert stdin.rstrip().endswith(INSTRUCTION)


# spec 001 / AC 34, FR-PERM-07 -- the system prompt file holds the role prompt byte for byte,
# then the fixed "documents are data" system instruction, and no document text.
def test_the_system_prompt_file_holds_the_system_prompt_and_no_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    system = "Line one of the role prompt.\nLine two.\n"
    h = harness(tmp_path, monkeypatch, envelope())
    h.client.complete(
        role=AgentRole.WRITER,
        system=system,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )

    [call] = h.recorder.calls
    assert call.prompt_file is not None
    assert call.prompt_text == render_system(system), "byte for byte, no newline translation"
    assert (call.prompt_text or "").startswith(system.rstrip())
    assert (call.prompt_text or "").rstrip().endswith(DATA_STATEMENT)
    for document in DOCUMENTS:
        assert document.text not in (call.prompt_text or "")


# spec 001 / AC 34 -- on Windows, `which` finds the npm shim; the native executable it forwards
# to is what runs, and the shim itself never does.
@pytest.mark.parametrize("shim_name", ["claude.CMD", "claude.cmd", "claude.bat"])
def test_the_npm_shim_is_never_executed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shim_name: str
) -> None:
    npm = tmp_path / "npm"
    native = npm / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"")
    shim = npm / shim_name
    shim.write_text("@ECHO off\n", encoding="utf-8")

    h = harness(tmp_path, monkeypatch, envelope())
    h.client = ClaudeCodeModelClient(
        Settings(_env_file=None), runner=h.recorder, which=lambda _: str(shim)
    )
    complete_writer(h)

    assert h.recorder.invocations, "the recorder saw the calls"
    for invocation in h.recorder.invocations:
        assert invocation.argv[0] == str(native)
        assert Path(invocation.argv[0]).suffix.lower() not in {".cmd", ".bat"}


# spec 001 / AC 34 -- Windows spellings of the shim whose suffix does not read `.cmd` (a
# trailing dot or space, the `::$DATA` stream) still name the shim; CreateProcess would run it
# through cmd.exe. The canonical name is checked, so the native executable runs instead.
@pytest.mark.skipif(sys.platform != "win32", reason="Windows path normalisation")
@pytest.mark.parametrize(
    "spelling", [".", " ", ". ", "::$DATA"], ids=["dot", "space", "dot-space", "ads"]
)
def test_a_disguised_shim_spelling_is_still_resolved(tmp_path: Path, spelling: str) -> None:
    npm = tmp_path / "npm"
    native = npm / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"")
    shim = npm / "claude.cmd"
    shim.write_text("@ECHO off\n", encoding="utf-8")

    resolved = resolve_executable(Path(str(shim) + spelling))
    assert resolved.suffix.lower() == ".exe"
    assert resolved.samefile(native)


# spec 001 / AC 34 -- CLAUDE_CLI overrides the lookup, and PATH is not consulted.
def test_claude_cli_overrides_the_lookup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    explicit = tmp_path / "custom" / "claude.exe"
    explicit.parent.mkdir()
    explicit.write_bytes(b"")
    h = harness(tmp_path, monkeypatch, envelope(), env={"CLAUDE_CLI": str(explicit)})
    complete_writer(h)

    assert h.which_calls == []
    assert {invocation.argv[0] for invocation in h.recorder.invocations} == {str(explicit)}


# spec 001 / AC 34 -- no CLI: a clear error, and nothing spawned.
def test_a_missing_cli_fails_clearly_and_spawns_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = harness(tmp_path, monkeypatch, envelope())
    h.client = ClaudeCodeModelClient(
        Settings(_env_file=None), runner=h.recorder, which=lambda _: None
    )
    with pytest.raises(ModelCallFailed) as raised:
        complete_writer(h)
    assert raised.value.context["reason"] == "cli_missing"
    assert raised.value.status_code == 502
    assert "CLAUDE_CLI" in raised.value.message
    assert h.recorder.invocations == []


# spec 001 / AC 34 -- a shim whose native executable is missing is not run as a fallback.
def test_a_shim_without_its_native_executable_is_refused(tmp_path: Path) -> None:
    shim = tmp_path / "npm" / "claude.CMD"
    shim.parent.mkdir()
    shim.write_text("@ECHO off\n", encoding="utf-8")
    with pytest.raises(ModelCallFailed) as raised:
        resolve_executable(None, lambda _: str(shim))
    assert raised.value.context["reason"] == "cli_missing"


# spec 001 / AC 34 -- the default runner: an argv list, no shell, bytes on stdin so no newline
# is rewritten. `subprocess.run` is replaced, so nothing is spawned.
def test_the_default_runner_uses_an_argv_list_and_no_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    def fake_run(args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        seen["args"] = args
        seen.update(kwargs)
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"{}", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_subprocess(
        ["claude.exe", "-p"], stdin="one\ntwo\n", cwd=tmp_path, env={"A": "1"}, timeout=5.0
    )

    assert isinstance(seen["args"], list)
    assert seen["shell"] is False
    assert seen["input"] == b"one\ntwo\n"
    assert seen["cwd"] == tmp_path
    assert seen["env"] == {"A": "1"}
    assert seen["timeout"] == 5.0
    assert result == RunResult(returncode=0, stdout="{}", stderr="")


# spec 001 / AC 34, FR-LLM-08 -- a timeout is reported, not raised through.
def test_the_default_runner_reports_a_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd="claude.exe", timeout=1.0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_subprocess(["claude.exe"], stdin="", cwd=tmp_path, env={}, timeout=1.0)
    assert result.timed_out
    assert result.returncode is None


# spec 001 / AC 34, NFR-01 -- the CLI version is probed once per client and recorded.
def test_the_cli_version_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = harness(tmp_path, monkeypatch, envelope(), envelope())
    first = h.client.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )
    second = h.client.complete(
        role=AgentRole.WRITER,
        system=SYSTEM,
        documents=DOCUMENTS,
        instruction=INSTRUCTION,
        output_schema=WriterOutput,
    )
    assert first.cli_version == second.cli_version == "2.1.273"
    probes = [i for i in h.recorder.invocations if i.argv[1:] == ["--version"]]
    assert len(probes) == 1


# spec 001 / AC 34 -- every DR-12 schema fits on a Windows command line (32 767 characters)
# with room to spare, so passing it as `--json-schema` is safe for every role.
@pytest.mark.parametrize(
    "schema",
    [WriterOutput, ReviseOutput, PolishOutput, ExtractOutput, SemanticAuditOutput, DigestOutput],
    ids=lambda schema: schema.__name__,
)
def test_every_role_schema_fits_on_a_windows_command_line(schema: type[BaseModel]) -> None:
    argument = json_schema_argument(schema)
    assert json.loads(argument) == schema.model_json_schema()
    assert len(argument) < 16_000
