"""Configuration, and the constants that no configuration key is allowed to move.

Spec 001. The numbers below the settings class are **module constants** on purpose: the
context cap is "one hard cap, 100k tokens per invocation, for every role, with no per-role
targets below it" (NFR-05, architecture.md "Memory and context budget"), and the revision
bound is what makes the turn state machine terminate (FR-TURN-02). A settings key that
could raise either of them would be a hole in the design, not a feature.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CONTEXT_TOKEN_CAP: Final[int] = 100_000
"""NFR-05, FR-OPS-03, FR-LLM-07. Per model call, never accumulated across a turn."""

TURN_MAX_REVISIONS: Final[int] = 3
"""FR-TURN-02. The bound that makes every path through Figure 4 terminate."""

FIXED_BLOCK_TOKEN_BUDGET: Final[int] = 800
"""FR-OPS-04. Exceeding it is a warning on the response, not an error."""

EMBEDDING_DIM: Final[int] = 384
"""FR-EMB-02. Only 384-d models are accepted, so the vec0 schema never changes."""

LITERAL_TAIL_WORDS: Final[int] = 500
"""DR-11. The only verbatim prose that reaches the next scene."""

DIGEST_WORD_TARGETS: Final[dict[str, int]] = {"scene": 100, "chapter": 250, "arc": 400}
"""DR-11 and architecture.md SceneDigest. Recorded against actual words on the turn record."""

EffortLevel = Literal["low", "medium", "high", "xhigh", "max"]
"""FR-LLM-03. The values `claude --effort` accepts (Claude Code 2.1.273). Anything else in an
`EFFORT_<ROLE>` key is a configuration error at startup, not a value passed through for the
CLI to reject in the middle of a turn."""

DEFAULT_CLAUDE_TIMEOUT_SECONDS: Final[float] = 600.0
"""FR-LLM-08. One `claude -p` call over a 100k-token context that writes a whole scene takes
minutes, not seconds; ten minutes is the ceiling past which the call is treated as hung,
killed, and retried once."""

DEFAULT_MODEL: Final[str] = "claude-haiku-4-5"
"""FR-LLM-03, Decision R2-4. Raised per role through MODEL_<ROLE>, never globally."""

DEFAULT_EMBED_MODEL: Final[str] = "sentence-transformers/all-MiniLM-L6-v2"
FALLBACK_EMBED_MODEL: Final[str] = "BAAI/bge-small-en-v1.5"

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
"""The monorepo root (`backend/app/commons/config.py` → three levels up from `app/`)."""

ROLE_NAMES: Final[tuple[str, ...]] = (
    "architect",
    "world_builder",
    "writer",
    "style_editor",
    "auditor",
    "canoniser",
    "interviewer",
    "planner",
    "editor",
    "judge",
)
"""The roles as plain strings (Figure 3's six, then spec 005's four). commons.config sits
below commons.permissions in the import contract, so it cannot import AgentRole; the enum is
checked against this tuple in
permissions/roles.py so the two cannot drift."""


class Settings(BaseSettings):
    """Environment-backed settings, one explicit alias per field."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    story_root: Path = Field(default=Path(), validation_alias="STORY_ROOT")
    story_index: Path | None = Field(default=None, validation_alias="STORY_INDEX")

    embed_model: str = Field(default=DEFAULT_EMBED_MODEL, validation_alias="EMBED_MODEL")
    embed_fallback_model: str = Field(
        default=FALLBACK_EMBED_MODEL, validation_alias="EMBED_FALLBACK_MODEL"
    )
    embed_cache_dir: Path | None = Field(default=None, validation_alias="EMBED_CACHE_DIR")
    embed_offline: bool = Field(default=False, validation_alias="EMBED_OFFLINE")

    turn_revise_max_changed_ratio: float = Field(
        default=0.35, ge=0.0, le=1.0, validation_alias="TURN_REVISE_MAX_CHANGED_RATIO"
    )

    architect_model: str = Field(default=DEFAULT_MODEL, validation_alias="MODEL_ARCHITECT")
    world_builder_model: str = Field(default=DEFAULT_MODEL, validation_alias="MODEL_WORLD_BUILDER")
    writer_model: str = Field(default=DEFAULT_MODEL, validation_alias="MODEL_WRITER")
    style_editor_model: str = Field(default=DEFAULT_MODEL, validation_alias="MODEL_STYLE_EDITOR")
    auditor_model: str = Field(default=DEFAULT_MODEL, validation_alias="MODEL_AUDITOR")
    canoniser_model: str = Field(default=DEFAULT_MODEL, validation_alias="MODEL_CANONISER")
    interviewer_model: str = Field(default=DEFAULT_MODEL, validation_alias="MODEL_INTERVIEWER")
    planner_model: str = Field(default=DEFAULT_MODEL, validation_alias="MODEL_PLANNER")
    editor_model: str = Field(default=DEFAULT_MODEL, validation_alias="MODEL_EDITOR")
    judge_model: str = Field(default=DEFAULT_MODEL, validation_alias="MODEL_JUDGE")

    architect_effort: EffortLevel | None = Field(default=None, validation_alias="EFFORT_ARCHITECT")
    world_builder_effort: EffortLevel | None = Field(
        default=None, validation_alias="EFFORT_WORLD_BUILDER"
    )
    writer_effort: EffortLevel | None = Field(default=None, validation_alias="EFFORT_WRITER")
    style_editor_effort: EffortLevel | None = Field(
        default=None, validation_alias="EFFORT_STYLE_EDITOR"
    )
    auditor_effort: EffortLevel | None = Field(default=None, validation_alias="EFFORT_AUDITOR")
    canoniser_effort: EffortLevel | None = Field(
        default=None, validation_alias="EFFORT_CANONISER"
    )
    interviewer_effort: EffortLevel | None = Field(
        default=None, validation_alias="EFFORT_INTERVIEWER"
    )
    planner_effort: EffortLevel | None = Field(default=None, validation_alias="EFFORT_PLANNER")
    editor_effort: EffortLevel | None = Field(default=None, validation_alias="EFFORT_EDITOR")
    judge_effort: EffortLevel | None = Field(default=None, validation_alias="EFFORT_JUDGE")

    # Spec 005 / spec 004 D1. The authoritative database; relative paths resolve against
    # the repository root, so the backend and the scripts find the same file.
    harness_db: Path = Field(default=Path("data/harness.sqlite"), validation_alias="HARNESS_DB")

    # Spec 010. Langfuse is on when both keys are set and LANGFUSE_ENABLED is not "0".
    langfuse_public_key: str | None = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(
        default=None, validation_alias="LANGFUSE_SECRET_KEY", repr=False
    )
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com", validation_alias="LANGFUSE_BASE_URL"
    )
    langfuse_enabled: bool = Field(default=True, validation_alias="LANGFUSE_ENABLED")

    claude_cli: Path | None = Field(default=None, validation_alias="CLAUDE_CLI")
    claude_timeout_seconds: float = Field(
        default=DEFAULT_CLAUDE_TIMEOUT_SECONDS,
        gt=0,
        le=3600,
        validation_alias="CLAUDE_TIMEOUT_SECONDS",
    )

    @field_validator(
        "architect_effort",
        "world_builder_effort",
        "writer_effort",
        "style_editor_effort",
        "auditor_effort",
        "canoniser_effort",
        "interviewer_effort",
        "planner_effort",
        "editor_effort",
        "judge_effort",
        "claude_cli",
        mode="before",
    )
    @classmethod
    def _empty_means_unset(cls, value: object) -> object:
        """`EFFORT_WRITER=` in a `.env` file means "not set", which is the CLI default
        (FR-LLM-03). Read literally it would be an invalid effort, or for `CLAUDE_CLI` the
        path `.`, which is a directory rather than an executable."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def harness_db_path(self) -> Path:
        """Spec 005. `HARNESS_DB`, with a relative path anchored at the repository root."""
        if self.harness_db.is_absolute():
            return self.harness_db
        return REPO_ROOT / self.harness_db

    @property
    def langfuse_active(self) -> bool:
        """Spec 010. Both keys present and not switched off."""
        return bool(self.langfuse_public_key and self.langfuse_secret_key) and (
            self.langfuse_enabled
        )

    @property
    def index_path(self) -> Path:
        """FR-IDX-01. Outside the store tree, never committed."""
        return self.story_index or self.story_root / ".index" / "index.sqlite"

    @property
    def index_dir(self) -> Path:
        """`.index/`: the index, the turn records and the provenance log (Decision R2-1)."""
        return self.index_path.parent

    @property
    def model_cache_dir(self) -> Path:
        """FR-EMB-03."""
        return self.embed_cache_dir or self.story_root / ".index" / "models"

    def model_for(self, role: str) -> str:
        """FR-LLM-03. Passed to the CLI as `--model`. The model id the CLI reports having
        used is recorded on the turn record beside it, so a provider-side change stays
        attributable."""
        return _for_role(
            role,
            {
                "architect": self.architect_model,
                "world_builder": self.world_builder_model,
                "writer": self.writer_model,
                "style_editor": self.style_editor_model,
                "auditor": self.auditor_model,
                "canoniser": self.canoniser_model,
                "interviewer": self.interviewer_model,
                "planner": self.planner_model,
                "editor": self.editor_model,
                "judge": self.judge_model,
            },
        )

    def effort_for(self, role: str) -> EffortLevel | None:
        """FR-LLM-03. Passed to the CLI as `--effort` only when set; None means the flag is
        omitted and the CLI's own default applies."""
        return _for_role(
            role,
            {
                "architect": self.architect_effort,
                "world_builder": self.world_builder_effort,
                "writer": self.writer_effort,
                "style_editor": self.style_editor_effort,
                "auditor": self.auditor_effort,
                "canoniser": self.canoniser_effort,
                "interviewer": self.interviewer_effort,
                "planner": self.planner_effort,
                "editor": self.editor_effort,
                "judge": self.judge_effort,
            },
        )


def _for_role[V](role: str, values: Mapping[str, V]) -> V:
    """One lookup for every per-role setting, so an unknown role fails the same way for all
    of them rather than defaulting to somebody else's value."""
    if role not in values:
        message = f"unknown role: {role!r}"
        raise ValueError(message)
    return values[role]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached so the process reads the environment once. Tests call
    get_settings.cache_clear() after moving STORY_ROOT."""
    return Settings()
