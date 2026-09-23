"""`ClaudeCodeModelClient`: every role call as one `claude -p` subprocess (FR-LLM-01, plan P14).

Model calls go through the Claude Code CLI under the user's own Claude Code login, and **no
Anthropic API key is ever used** (spec decision R3-1). Three things make that true rather than
hoped for:

* `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` are removed from the subprocess environment,
  so a key exported in the shell cannot silently take over from the login;
* `--bare` is never passed: in that mode the CLI never reads the login and accepts only a key;
* nothing here reads, writes or names a credential.

**Isolation (FR-LLM-05, AC 34).** The role must see only what the orchestrator hands it
(FR-AGENT-09), so every call runs with `--tools ""` (no tools: the model can neither read nor
write the tree), `--setting-sources ""` (no user or project settings, hence no hooks),
`--strict-mcp-config` with no servers, `--disable-slash-commands`, `--no-session-persistence`,
and a fresh, **empty** temporary working directory outside the repository and the store root,
so no `CLAUDE.md` is discovered from it. The role system prompt goes in a file in a *second*
temporary directory, so the working directory stays empty. Documents and the instruction go on
stdin: a 100k-token context does not fit on a Windows command line.

**The executable.** On Windows `shutil.which("claude")` finds the npm shim `claude.CMD`, which
only forwards its arguments to the native `claude.exe` beside it. The shim is never run:
passing a JSON Schema through `cmd.exe`'s quoting is fragile, and the native executable takes
an argv list directly. `CLAUDE_CLI` overrides the lookup.

**The call (FR-LLM-06..08).** Before anything is spawned the input is estimated and checked
against the cap (FR-LLM-07, AC 22). After, the result envelope is checked before
`structured_output` is read, and every failure is classified by `app.commons.llm.errors`. The
real input count, cached tokens included, is read against the cap with the CLI's measured
overhead subtracted (FR-CTX-06, R3-5).

The subprocess runner is injected, so every test replaces it with a recorder and no test ever
reaches a model (NFR-06).
"""

from __future__ import annotations

import json
import os
import re
import shutil

# Bandit B404: spec 001 FR-LLM-01 and NFR-04 make this the one module that spawns a process;
# the model is reached through the `claude -p` subprocess and nothing else.
import subprocess  # nosec B404
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from app.commons.config import CONTEXT_TOKEN_CAP, Settings, get_settings
from app.commons.errors import ModelCallFailed
from app.commons.llm.errors import (
    api_status_failure,
    process_failure,
    refused,
    run_attempts,
    structured_output_rejected,
    truncated,
    validate_output,
)
from app.commons.llm.protocol import (
    Completion,
    Document,
    Usage,
    checked_cap,
    estimate_call,
    preflight,
    render_prompt,
    render_system,
)
from app.commons.llm.tokens import is_over_cap
from app.commons.permissions import AgentRole

STRIPPED_ENVIRONMENT: Final[frozenset[str]] = frozenset(
    {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"}
)
"""FR-LLM-01, R3-1. Removed from the subprocess environment, compared case-insensitively
because Windows environment names are."""

SHIM_SUFFIXES: Final[frozenset[str]] = frozenset({".cmd", ".bat"})
NATIVE_FROM_SHIM: Final[tuple[str, ...]] = (
    "node_modules",
    "@anthropic-ai",
    "claude-code",
    "bin",
    "claude.exe",
)
"""Where the npm shim forwards to, relative to the shim's own directory."""

RESULT_TYPE: Final[str] = "result"
"""The `type` of the CLI's `--output-format json` envelope (Claude Code 2.1.273)."""

STRUCTURED_OUTPUT_EXHAUSTED: Final[str] = "error_max_structured_output_retries"
"""The envelope `subtype` the CLI (2.1.273) reports when the model called its structured-
output tool but no attempt passed the `--json-schema` validation. That is FR-LLM-04's
malformed output, caught one layer earlier, so it is classified as such rather than as a
generic CLI error."""

VERSION_TIMEOUT_SECONDS: Final[float] = 30.0
VERSION_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d+(?:\.\d+)+")
DETAIL_LIMIT: Final[int] = 300
"""Characters of CLI output quoted in an error message. Enough to carry "usage limit
reached" or a login prompt; short enough that no prompt text could ride along (NFR-10)."""

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[4]
"""`backend/app/commons/llm/` -> the repository. The working directory must not be inside it:
the CLI would discover the repository's `CLAUDE.md` and agent instructions from there."""


@dataclass(frozen=True, slots=True)
class RunResult:
    """What one subprocess run produced. `returncode` is None when it never finished."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


class Runner(Protocol):
    """The subprocess seam. The default runs the process; tests inject a recorder."""

    def __call__(
        self,
        argv: Sequence[str],
        *,
        stdin: str,
        cwd: Path,
        env: Mapping[str, str],
        timeout: float,
    ) -> RunResult: ...


def run_subprocess(
    argv: Sequence[str],
    *,
    stdin: str,
    cwd: Path,
    env: Mapping[str, str],
    timeout: float,
) -> RunResult:
    """The default runner: one process from an argv list, never through a shell.

    Bytes in and out rather than text mode, because text mode on Windows rewrites every `\\n`
    written to stdin as `\\r\\n`, which would alter the documents the model reads. On timeout
    `subprocess.run` kills the process before returning.
    """
    try:
        # Bandit B603: spec 001 FR-LLM-01/-05. An argv list, `shell=False`, and argv[0] the
        # absolute path `resolve_executable` checked; no element is ever parsed by a shell.
        completed = subprocess.run(  # nosec B603
            list(argv),
            input=stdin.encode("utf-8"),
            capture_output=True,
            cwd=cwd,
            env=dict(env),
            timeout=timeout,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return RunResult(returncode=None, stdout="", stderr="", timed_out=True)
    except OSError as error:
        message = f"the Claude Code CLI could not be started: {error}"
        raise ModelCallFailed(message, reason="cli_unavailable") from None
    return RunResult(
        returncode=completed.returncode,
        stdout=completed.stdout.decode("utf-8", errors="replace"),
        stderr=completed.stderr.decode("utf-8", errors="replace"),
    )


def resolve_executable(
    explicit: Path | None, which: Callable[[str], str | None] = shutil.which
) -> Path:
    """The native `claude` executable: `CLAUDE_CLI` if set, else the one on PATH.

    A `.cmd`/`.bat` npm shim is resolved to the native `claude.exe` it forwards to and is never
    run itself. Raises `ModelCallFailed(reason="cli_missing")` when there is nothing to run,
    because a missing CLI is a fact about the machine, not a model outcome to retry.
    """
    if explicit is not None:
        candidate = explicit
        origin = f"CLAUDE_CLI={explicit}"
    else:
        found = which("claude")
        if found is None:
            message = (
                "the Claude Code CLI (`claude`) is not on PATH and CLAUDE_CLI is not set; "
                "install Claude Code and log in, or point CLAUDE_CLI at the executable"
            )
            raise ModelCallFailed(message, reason="cli_missing")
        candidate = Path(found)
        origin = f"PATH ({found})"

    # Canonicalise before reading the suffix. Windows strips trailing dots and spaces and
    # accepts `::$DATA`, so `claude.cmd.` or `claude.cmd ` names the shim while its suffix
    # reads as something else -- and CreateProcess runs a batch file through `cmd.exe`
    # whatever argv says. Checking the canonical name is what makes "never run the shim"
    # hold for every spelling (AC 34).
    candidate = _canonical(candidate)
    if candidate.suffix.lower() in SHIM_SUFFIXES:
        candidate = _canonical(candidate.parent.joinpath(*NATIVE_FROM_SHIM))
    if candidate.suffix.lower() in SHIM_SUFFIXES or not candidate.is_file():
        message = (
            f"the Claude Code CLI found through {origin} resolves to {candidate}, which does "
            "not exist; point CLAUDE_CLI at the native executable"
        )
        raise ModelCallFailed(message, reason="cli_missing")
    return candidate


def _canonical(path: Path) -> Path:
    """The file's canonical path when it exists (symlinks followed, Windows spelling
    normalised); the path unchanged when it does not, so the caller reports it missing."""
    try:
        return path.resolve(strict=True)
    except OSError:
        return path


def scrubbed_environment(parent: Mapping[str, str]) -> dict[str, str]:
    """FR-LLM-01, AC 34. The parent environment without any Anthropic credential."""
    return {
        name: value for name, value in parent.items() if name.upper() not in STRIPPED_ENVIRONMENT
    }


def json_schema_argument(output_schema: type[BaseModel]) -> str:
    """FR-LLM-04, plan P10. The DR-12 model's own JSON Schema, compact and key-sorted so the
    command line is identical for identical schemas."""
    return json.dumps(output_schema.model_json_schema(), separators=(",", ":"), sort_keys=True)


def build_argv(
    executable: Path,
    *,
    model: str,
    effort: str | None,
    json_schema: str,
    system_prompt_file: Path,
) -> list[str]:
    """FR-LLM-03, FR-LLM-05, plan P14, AC 34. The whole command, as a list.

    No positional prompt: the CLI reads it from stdin. `--effort` only when the role has one,
    so an unset `EFFORT_<ROLE>` means the CLI's default. Never `--bare`.
    """
    argv = [str(executable), "-p", "--output-format", "json", "--model", model]
    if effort is not None:
        argv += ["--effort", effort]
    argv += [
        "--json-schema",
        json_schema,
        "--system-prompt-file",
        str(system_prompt_file),
        "--tools",
        "",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--no-session-persistence",
    ]
    return argv


class _Lenient(BaseModel):
    """The envelope is the CLI's, not ours: fields it adds in a later version are ignored,
    and only the ones read here are typed."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class _EnvelopeUsage(_Lenient):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_input_tokens: int = Field(default=0, ge=0)
    cache_creation_input_tokens: int = Field(default=0, ge=0)


class _ModelUsage(_Lenient):
    input_tokens: int = Field(default=0, ge=0, alias="inputTokens")
    output_tokens: int = Field(default=0, ge=0, alias="outputTokens")


class _StopDetails(_Lenient):
    category: str | None = None


class Envelope(_Lenient):
    """The `--output-format json` result of one `claude -p` run, as far as it is read
    (FR-LLM-06). Validated rather than indexed, so an envelope of the wrong shape is
    "unparseable" at one place instead of a `KeyError` somewhere else."""

    type: str | None = None
    subtype: str | None = None
    is_error: bool = False
    stop_reason: str | None = None
    stop_details: _StopDetails | None = None
    api_error_status: int | str | None = None
    result: str | None = None
    structured_output: JsonValue = None
    usage: _EnvelopeUsage | None = None
    model_usage: dict[str, _ModelUsage] = Field(default_factory=dict, alias="modelUsage")
    num_turns: int | None = None

    def status_code(self) -> int | None:
        """`api_error_status` as a number when it is one."""
        status = self.api_error_status
        if isinstance(status, int):
            return status
        if isinstance(status, str) and status.strip().isdigit():
            return int(status.strip())
        return None

    def reported_usage(self) -> Usage:
        report = self.usage or _EnvelopeUsage()
        return Usage(
            input_tokens=report.input_tokens,
            output_tokens=report.output_tokens,
            cache_read_input_tokens=report.cache_read_input_tokens,
            cache_creation_input_tokens=report.cache_creation_input_tokens,
        )

    def model_id(self) -> str | None:
        """FR-LLM-03. The model that answered, from `modelUsage`. When more than one model
        appears, the one that produced the most output is the one that wrote the answer."""
        if not self.model_usage:
            return None
        ranked = sorted(self.model_usage.items())
        return max(ranked, key=lambda item: item[1].output_tokens)[0]


def parse_envelope(stdout: str) -> Envelope | None:
    """The result envelope, or None when stdout holds no readable one (FR-LLM-08).

    Every field of `Envelope` has a default, so any JSON object would validate; only one
    whose `type` is `"result"` is the CLI's envelope. Anything else is "unparseable" and
    retried as a process failure, not read as an empty answer and blamed on the model as
    malformed output.
    """
    text = stdout.strip()
    if not text:
        return None
    candidates = [text, *reversed([line for line in text.splitlines() if line.startswith("{")])]
    for candidate in candidates:
        try:
            envelope = Envelope.model_validate_json(candidate)
        except ValidationError:
            continue
        if envelope.type == RESULT_TYPE:
            return envelope
    return None


def _tail(text: str) -> str:
    cleaned = " ".join(text.split())
    return cleaned[-DETAIL_LIMIT:] if cleaned else "<no output>"


def settle[T: BaseModel](
    result: RunResult, output_schema: type[T], *, role: str
) -> tuple[T, Envelope]:
    """Classify one attempt, most specific first (FR-LLM-06, FR-LLM-08), and return the
    validated output only when nothing earlier objected (FR-LLM-04)."""
    if result.timed_out:
        raise process_failure(role, "timeout", "the CLI did not finish before the call timeout")

    envelope = parse_envelope(result.stdout)
    if envelope is None:
        reason = "unparseable" if result.returncode == 0 else "exit_status"
        detail = f"exit status {result.returncode}; stderr: {_tail(result.stderr)}"
        raise process_failure(role, reason, detail)

    if envelope.api_error_status is not None:
        failure = api_status_failure(role, envelope.status_code(), _tail(envelope.result or ""))
        raise failure

    if envelope.stop_reason == "refusal":
        category = envelope.stop_details.category if envelope.stop_details else None
        raise refused(role, category)

    if envelope.stop_reason == "max_tokens":
        raise truncated(role)

    if envelope.subtype == STRUCTURED_OUTPUT_EXHAUSTED:
        raise structured_output_rejected(role, output_schema.__name__)

    failed = envelope.is_error or envelope.subtype not in (None, "success")
    if failed or result.returncode != 0:
        # `result` is the CLI's error text only when `is_error` says so; otherwise it is the
        # model's own answer, and NFR-10 keeps model text out of error messages and logs.
        said = envelope.result if envelope.is_error else None
        detail = (
            f"subtype {envelope.subtype!r}, exit status {result.returncode}: "
            f"{_tail(said or result.stderr)}"
        )
        raise process_failure(role, "cli_error", detail)

    return validate_output(envelope.structured_output, output_schema, role=role), envelope


def parse_version(stdout: str) -> str | None:
    """`2.1.273 (Claude Code)` -> `2.1.273` (NFR-01)."""
    match = VERSION_PATTERN.match(stdout.strip())
    return match.group(0) if match else None


class ClaudeCodeModelClient:
    """FR-LLM-02's live implementation. See the module docstring for what each call does and
    why. Construct once per process; the executable and its version are resolved lazily, on
    the first call that passes the cap, and cached."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        runner: Runner | None = None,
        which: Callable[[str], str | None] = shutil.which,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        environ: Mapping[str, str] | None = None,
        cap: int = CONTEXT_TOKEN_CAP,
    ) -> None:
        self._settings = settings or get_settings()
        # Looked up when the client is built rather than bound as a default argument, so the
        # offline suite can replace `run_subprocess` once, in conftest, and no test that forgets
        # to inject a recorder can ever start the real CLI (NFR-09).
        self._runner = runner if runner is not None else run_subprocess
        self._which = which
        self._sleep = sleep
        self._clock = clock
        self._environ = environ
        self._cap = checked_cap(cap)
        self._executable: Path | None = None
        self._version: str | None = None
        self._version_probed = False

    def estimate_input_tokens(
        self, system: str, documents: Sequence[Document], instruction: str
    ) -> int:
        """FR-LLM-07, FR-CTX-02. What the system sends, never the CLI's overhead (R3-5)."""
        return estimate_call(system, documents, instruction)

    def complete[T: BaseModel](
        self,
        *,
        role: AgentRole,
        system: str,
        documents: Sequence[Document],
        instruction: str,
        output_schema: type[T],
    ) -> Completion[T]:
        """FR-LLM-02. One role call through `claude -p`.

        The cap check is the first statement: over it, `ContextBudgetExceeded` is raised and
        nothing is resolved, probed or spawned (AC 22).
        """
        estimate = preflight(system, documents, instruction, cap=self._cap)
        executable = self._resolve()
        role_name = role.value
        model = self._settings.model_for(role_name)
        stdin = render_prompt(documents, instruction)
        environment = scrubbed_environment(os.environ if self._environ is None else self._environ)
        timeout = self._settings.claude_timeout_seconds

        started = self._clock()
        with (
            tempfile.TemporaryDirectory(
                prefix="msm-claude-cwd-", ignore_cleanup_errors=True
            ) as cwd_name,
            tempfile.TemporaryDirectory(
                prefix="msm-claude-prompt-", ignore_cleanup_errors=True
            ) as prompt_name,
        ):
            workdir = Path(cwd_name)
            self._require_isolated(workdir, role_name)
            prompt_file = Path(prompt_name) / "system-prompt.md"
            # The one file primitive outside commons/stores, exempted by name in the
            # forbidden-store-write rule: a temporary file, never a store path.
            prompt_file.write_text(render_system(system), encoding="utf-8", newline="")
            version = self._probe_version(executable, workdir, environment)
            argv = build_argv(
                executable,
                model=model,
                effort=self._settings.effort_for(role_name),
                json_schema=json_schema_argument(output_schema),
                system_prompt_file=prompt_file,
            )

            def attempt() -> tuple[T, Envelope]:
                result = self._runner(
                    argv, stdin=stdin, cwd=workdir, env=environment, timeout=timeout
                )
                return settle(result, output_schema, role=role_name)

            (output, envelope), attempts = run_attempts(attempt, sleep=self._sleep)
        elapsed = self._clock() - started

        usage = envelope.reported_usage()
        return Completion(
            output=output,
            role=role,
            model_id=envelope.model_id(),
            requested_model=model,
            usage=usage,
            estimate=estimate,
            over_cap=is_over_cap(usage.context_tokens, self._cap),
            attempts=attempts,
            elapsed_seconds=elapsed,
            cli_version=version,
            num_turns=envelope.num_turns,
        )

    def _resolve(self) -> Path:
        if self._executable is None:
            self._executable = resolve_executable(self._settings.claude_cli, self._which)
        return self._executable

    def _require_isolated(self, workdir: Path, role: str) -> None:
        """FR-LLM-05. The working directory is outside the repository and the store root,
        or the CLI would discover instructions from them. A temporary directory normally is;
        this refuses the call on a machine where the temporary directory is not."""
        resolved = workdir.resolve()
        for root in (REPOSITORY_ROOT, self._settings.story_root.resolve()):
            if resolved.is_relative_to(root):
                message = (
                    f"the temporary working directory {resolved} lies inside {root}; the "
                    "CLI would read instructions from there. Point TMP/TEMP elsewhere."
                )
                raise ModelCallFailed(message, reason="workdir_not_isolated", role=role)

    def _probe_version(
        self, executable: Path, workdir: Path, environment: Mapping[str, str]
    ) -> str | None:
        """NFR-01. `claude --version`, once per client, recorded on every completion. A probe
        that fails leaves the version unknown rather than failing the call."""
        if not self._version_probed:
            self._version_probed = True
            result = self._runner(
                [str(executable), "--version"],
                stdin="",
                cwd=workdir,
                env=environment,
                timeout=VERSION_TIMEOUT_SECONDS,
            )
            if result.returncode == 0 and not result.timed_out:
                self._version = parse_version(result.stdout)
        return self._version


__all__ = [
    "STRIPPED_ENVIRONMENT",
    "ClaudeCodeModelClient",
    "Envelope",
    "RunResult",
    "Runner",
    "build_argv",
    "json_schema_argument",
    "parse_envelope",
    "parse_version",
    "resolve_executable",
    "run_subprocess",
    "scrubbed_environment",
    "settle",
]
