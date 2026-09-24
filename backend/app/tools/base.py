"""The validated tool contract (spec 017, H05).

A tool is a read-only function over the story bible with a pydantic input model and a
pydantic output model. `call_tool` is the only way to run one: it validates the raw input
against the input model's JSON Schema (via pydantic), runs the handler inside an observer
span `tool:<name>` (K2), and validates the result against the output model before returning
it. A tool never writes: handlers only call `BibleRepository` read methods.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from app.bible import BibleRepository
from app.commons.observability import NoopObserver, Observer

SPAN_OUTPUT_LIMIT: Final[int] = 2000
"""Characters of a tool's output copied into its span; the rest is summarised."""


class ToolError(Exception):
    """Base of every error a tool call reports to its caller."""


class ToolInputError(ToolError):
    """The input does not match the tool's input schema. The handler never ran."""


class ToolOutputError(ToolError):
    """The handler returned something that does not match the output schema."""


class ToolNotFoundError(ToolError):
    """The novel, version or chapter asked for does not exist."""


class ToolUnavailableError(ToolError):
    """The tool depends on a module that is not installed (e.g. `app.export`)."""


class ToolInput(BaseModel):
    """Inputs are closed: an unknown key is a schema violation, not something ignored."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True, slots=True)
class Tool[In: ToolInput, Out: ToolOutput]:
    name: str
    description: str
    input_model: type[In]
    output_model: type[Out]
    handler: Callable[[BibleRepository, In], Out]

    @property
    def input_schema(self) -> dict[str, object]:
        return self.input_model.model_json_schema()

    @property
    def output_schema(self) -> dict[str, object]:
        return self.output_model.model_json_schema()

    def validate_input(self, raw: Mapping[str, object] | None) -> In:
        try:
            return self.input_model.model_validate(dict(raw or {}))
        except ValidationError as exc:
            message = f"{self.name}: invalid input: {exc.errors(include_url=False)}"
            raise ToolInputError(message) from exc

    def validate_output(self, result: Out) -> Out:
        try:
            return self.output_model.model_validate(result.model_dump(mode="json"))
        except ValidationError as exc:
            message = f"{self.name}: invalid output: {exc.errors(include_url=False)}"
            raise ToolOutputError(message) from exc

    def run(
        self,
        repo: BibleRepository,
        raw: Mapping[str, object] | None,
        *,
        observer: Observer | None = None,
    ) -> Out:
        """Validate, run under `tool:<name>`, validate again."""
        obs = observer or NoopObserver()
        with obs.span(
            f"tool:{self.name}", input=dict(raw or {}), metadata={"tool": self.name}
        ) as span:
            try:
                args = self.validate_input(raw)
                result = self.validate_output(self.handler(repo, args))
            except ToolError as exc:
                span.update(metadata={"error": type(exc).__name__, "detail": str(exc)[:500]})
                raise
            span.update(output=_span_output(result), metadata={"ok": True})
            return result


class AnyTool(Protocol):
    """A `Tool` with its type parameters erased, as the registry and the MCP server see it."""

    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def input_model(self) -> type[ToolInput]: ...
    @property
    def output_model(self) -> type[ToolOutput]: ...
    @property
    def input_schema(self) -> dict[str, object]: ...
    @property
    def output_schema(self) -> dict[str, object]: ...

    def run(
        self,
        repo: BibleRepository,
        raw: Mapping[str, object] | None,
        *,
        observer: Observer | None = None,
    ) -> ToolOutput: ...


def _span_output(result: ToolOutput) -> object:
    text = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    if len(text) <= SPAN_OUTPUT_LIMIT:
        return result.model_dump(mode="json")
    return {"truncated": True, "chars": len(text), "head": text[:SPAN_OUTPUT_LIMIT]}


__all__ = [
    "SPAN_OUTPUT_LIMIT",
    "AnyTool",
    "Tool",
    "ToolError",
    "ToolInput",
    "ToolInputError",
    "ToolNotFoundError",
    "ToolOutput",
    "ToolOutputError",
    "ToolUnavailableError",
]
