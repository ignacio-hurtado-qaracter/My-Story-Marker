"""Prompt versioning in Langfuse (spec 010, O03).

A role prompt lives in `backend/app/prompts/<name>.md`, owned by the role's block. On
load it is published to Langfuse prompt management under the same name with the label
`production`, **only when its content changed** (the served `production` text differs), and
the call records the Langfuse version number. Offline, or when Langfuse fails, the version
is `sha-<first 12 hex of the SHA-256>` so every call still carries a stable version id.

The file is package data, not a store, so it is read through `pkgutil.get_data` like the
legacy role prompts in `app.agents.roles` (never a file primitive outside the store layer:
spec 001 AC 3). The name is one lowercase identifier, so it cannot address anything else.
"""

from __future__ import annotations

import hashlib
import pkgutil
import re
from dataclasses import dataclass
from typing import Final

from app.commons.observability.langfuse_observer import LangfuseObserver, _warn
from app.commons.observability.protocol import Observer

PROMPTS_PACKAGE: Final[str] = "app"
PROMPTS_SUBDIR: Final[str] = "prompts"
"""`backend/app/prompts/<name>.md`."""

_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

PRODUCTION_LABEL: Final[str] = "production"

_cache: dict[tuple[str, str], str] = {}
"""(name, content hash) -> version already resolved in this process."""


@dataclass(frozen=True, slots=True)
class PromptRef:
    """A loaded prompt: its text, and the version to record on every call that uses it."""

    name: str
    text: str
    version: str
    content_hash: str

    @property
    def published(self) -> bool:
        """True when `version` is a Langfuse version number, not the offline hash."""
        return self.version.isdigit()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_prompt_text(name: str) -> str:
    """The text of `app/prompts/<name>.md`, or `FileNotFoundError`."""
    if _NAME.fullmatch(name) is None:
        message = f"a prompt name is one lowercase identifier: {name!r}"
        raise ValueError(message)
    data = pkgutil.get_data(PROMPTS_PACKAGE, f"{PROMPTS_SUBDIR}/{name}.md")
    if data is None:  # pragma: no cover - only for loaders without get_data
        message = f"prompt {name!r} not found"
        raise FileNotFoundError(message)
    return data.decode("utf-8")


def load_prompt(
    name: str, observer: Observer | None = None, *, text: str | None = None
) -> PromptRef:
    """Read `app/prompts/<name>.md` (or use `text`) and resolve its version, publishing it
    to Langfuse if its content changed.

    `observer` defaults to `get_observer()`; pass a `NoopObserver` to stay offline.
    """
    if observer is None:
        from app.commons.observability import get_observer

        observer = get_observer()
    if text is None:
        text = read_prompt_text(name)
    digest = content_hash(text)
    offline = f"sha-{digest[:12]}"
    cached = _cache.get((name, digest))
    if cached is not None:
        return PromptRef(name=name, text=text, version=cached, content_hash=digest)
    version = offline
    if isinstance(observer, LangfuseObserver):
        version = _publish(observer, name, text, digest) or offline
    _cache[(name, digest)] = version
    return PromptRef(name=name, text=text, version=version, content_hash=digest)


def _publish(observer: LangfuseObserver, name: str, text: str, digest: str) -> str | None:
    client = observer.client
    try:
        current = client.get_prompt(name, label=PRODUCTION_LABEL, cache_ttl_seconds=0)
        if isinstance(current.prompt, str) and current.prompt == text:
            version = str(current.version)
            observer.prompt_clients[(name, version)] = current
            return version
    except Exception as exc:  # a missing prompt is an error in the SDK; create it below
        _warn("get prompt", exc)
    try:
        created = client.create_prompt(
            name=name,
            prompt=text,
            labels=[PRODUCTION_LABEL],
            type="text",
            config={"content_hash": digest},
            commit_message=f"content {digest[:12]}",
        )
    except Exception as exc:
        _warn("create prompt", exc)
        return None
    version = str(created.version)
    observer.prompt_clients[(name, version)] = created
    return version


__all__ = [
    "PRODUCTION_LABEL",
    "PROMPTS_PACKAGE",
    "PROMPTS_SUBDIR",
    "PromptRef",
    "content_hash",
    "load_prompt",
    "read_prompt_text",
]
