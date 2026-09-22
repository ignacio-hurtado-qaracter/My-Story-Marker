"""Configuration, and the constants that no configuration key is allowed to move.

Spec 001. The numbers below the settings class are **module constants** on purpose: the
context cap is "one hard cap, 100k tokens per invocation, for every role, with no per-role
targets below it" (NFR-05, architecture.md "Memory and context budget"), and the revision
bound is what makes the turn state machine terminate (FR-TURN-02). A settings key that
could raise either of them would be a hole in the design, not a feature.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

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

MIN_THINKING_BUDGET: Final[int] = 1024
"""FR-LLM-03. Below this the provider rejects the request."""

DEFAULT_MODEL: Final[str] = "claude-haiku-4-5"
"""FR-LLM-03, Decision R2-4. Raised per role through MODEL_<ROLE>, never globally."""

DEFAULT_EMBED_MODEL: Final[str] = "sentence-transformers/all-MiniLM-L6-v2"
FALLBACK_EMBED_MODEL: Final[str] = "BAAI/bge-small-en-v1.5"

ROLE_NAMES: Final[tuple[str, ...]] = (
    "architect",
    "world_builder",
    "writer",
    "style_editor",
    "auditor",
    "canoniser",
)
"""The six roles as plain strings. commons.config sits below commons.permissions in the
import contract, so it cannot import AgentRole; the enum is checked against this tuple in
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

    architect_thinking_budget: int | None = Field(
        default=None, validation_alias="THINKING_BUDGET_ARCHITECT"
    )
    world_builder_thinking_budget: int | None = Field(
        default=None, validation_alias="THINKING_BUDGET_WORLD_BUILDER"
    )
    writer_thinking_budget: int | None = Field(
        default=None, validation_alias="THINKING_BUDGET_WRITER"
    )
    style_editor_thinking_budget: int | None = Field(
        default=None, validation_alias="THINKING_BUDGET_STYLE_EDITOR"
    )
    auditor_thinking_budget: int | None = Field(
        default=None, validation_alias="THINKING_BUDGET_AUDITOR"
    )
    canoniser_thinking_budget: int | None = Field(
        default=None, validation_alias="THINKING_BUDGET_CANONISER"
    )

    @field_validator(
        "architect_thinking_budget",
        "world_builder_thinking_budget",
        "writer_thinking_budget",
        "style_editor_thinking_budget",
        "auditor_thinking_budget",
        "canoniser_thinking_budget",
    )
    @classmethod
    def _thinking_budget_is_usable(cls, value: int | None) -> int | None:
        """FR-LLM-03: a budget below the provider minimum is a configuration error, not a
        value to round up silently."""
        if value is not None and value < MIN_THINKING_BUDGET:
            message = f"thinking budget must be at least {MIN_THINKING_BUDGET}, got {value}"
            raise ValueError(message)
        return value

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
        """FR-LLM-03. The model id used is recorded on the turn record, so a provider-side
        change stays attributable."""
        models = {
            "architect": self.architect_model,
            "world_builder": self.world_builder_model,
            "writer": self.writer_model,
            "style_editor": self.style_editor_model,
            "auditor": self.auditor_model,
            "canoniser": self.canoniser_model,
        }
        if role not in models:
            message = f"unknown role: {role!r}"
            raise ValueError(message)
        return models[role]

    def thinking_budget_for(self, role: str) -> int | None:
        """FR-LLM-03. None means extended thinking is off for this role, which is the
        default: Haiku 4.5 takes a budget_tokens block and no effort setting."""
        budgets = {
            "architect": self.architect_thinking_budget,
            "world_builder": self.world_builder_thinking_budget,
            "writer": self.writer_thinking_budget,
            "style_editor": self.style_editor_thinking_budget,
            "auditor": self.auditor_thinking_budget,
            "canoniser": self.canoniser_thinking_budget,
        }
        if role not in budgets:
            message = f"unknown role: {role!r}"
            raise ValueError(message)
        return budgets[role]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached so the process reads the environment once. Tests call
    get_settings.cache_clear() after moving STORY_ROOT."""
    return Settings()
