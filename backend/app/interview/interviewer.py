"""The interviewer agent: one conversational turn per call (spec 006, C01, C03).

`Interviewer.step(draft, answer)` sends the partial brief, the validator's report on it and
the client's last answer (all three as delimited documents; the answer is client data, not
an instruction) to role INTERVIEWER with prompt `interviewer.md`, merges the returned
updates, re-validates, and decides the next question.

The model never decides alone that the brief is complete: `done` is honoured only when
`validate_brief` passes. A contradiction always wins the next question, asked
deterministically, so it is never resolved silently (definitions, Brief rule 2).

Every call runs inside a trace of the novel's Langfuse session (the novel id, minted at the
start of the interview) and a `role:interviewer` span from `traced_complete`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, Field, JsonValue

from app.bible import BibleRepository
from app.commons.llm import (
    ContextBudgetExceeded,
    Document,
    MalformedModelOutput,
    ModelCallFailed,
    ModelClient,
    ModelRefused,
    OutputTruncated,
)
from app.commons.observability import CallScope, Observer, load_prompt, traced_complete
from app.commons.permissions import AgentRole
from app.interview.brief import BriefReport, Gender, Genre, Occasion, Tone, validate_brief
from app.interview.extract import log_injection, prescan_injection

PROMPT_NAME: Final[str] = "interviewer"

MODEL_ERRORS: Final[tuple[type[Exception], ...]] = (
    ModelCallFailed,
    MalformedModelOutput,
    OutputTruncated,
    ModelRefused,
    ContextBudgetExceeded,
)
"""What a role call may raise once `traced_complete`'s bounded retry is spent."""

OPENING_QUESTION: Final[str] = (
    "¡Hola! Vamos a preparar una novela única. ¿Para quién es el regalo? "
    "Dime su nombre, su edad y qué relación tienes con esa persona."
)

QUESTIONS: Final[dict[str, str]] = {
    "recipient.name": "¿Cómo se llama la persona que recibirá la novela?",
    "recipient.age": "¿Cuántos años tiene (o cumplirá) cuando reciba el regalo?",
    "recipient.traits": "¿Cómo es? Cuéntame dos o tres rasgos de su carácter o de su aspecto.",
    "memories": "Cuéntame un recuerdo real con esa persona: qué pasó, cuándo y dónde.",
    "genre": (
        "¿Qué género prefieres: aventura, fantasía, comedia, romance, misterio, "
        "ciencia ficción, realista o fábula?"
    ),
    "tone": "¿Y qué tono: tierno, divertido, emotivo, épico, nostálgico u oscuro?",
    "length": "¿Cuántos capítulos quieres? Por defecto son 10, de 1000 a 1500 palabras.",
    "dedication": "¿Qué dedicatoria quieres que aparezca en la portada?",
}


class RecipientUpdate(BaseModel):
    name: str | None = None
    age: int | None = None
    gender: Gender | None = None
    birth_date: str | None = Field(default=None, description="YYYY-MM-DD")
    relation_to_buyer: str | None = None
    traits: list[str] | None = None
    hobbies: list[str] | None = None
    profession: str | None = None


class PersonUpdate(BaseModel):
    name: str
    relation: str = ""
    traits: list[str] = Field(default_factory=list)
    birth_date: str | None = None


class PetUpdate(BaseModel):
    name: str
    species: str = ""
    description: str = ""


class PlaceUpdate(BaseModel):
    name: str
    description: str = ""


class MemoryUpdate(BaseModel):
    title: str
    description: str = ""
    date: str | None = None
    place: str | None = None
    people: list[str] = Field(default_factory=list)


class LengthUpdate(BaseModel):
    chapters: int | None = None
    words_min: int | None = None
    words_max: int | None = None


class BriefUpdate(BaseModel):
    """Fields the last answer gave. None = unchanged; a list replaces the whole list."""

    recipient: RecipientUpdate | None = None
    occasion: Occasion | None = None
    buyer_name: str | None = None
    dedication: str | None = None
    people: list[PersonUpdate] | None = None
    pets: list[PetUpdate] | None = None
    places: list[PlaceUpdate] | None = None
    memories: list[MemoryUpdate] | None = None
    genre: Genre | None = None
    tone: Tone | None = None
    length: LengthUpdate | None = None
    forbidden_terms: list[str] | None = None
    mandatory_elements: list[str] | None = None


class InterviewTurn(BaseModel):
    """The model's output for one turn."""

    updates: BriefUpdate = Field(default_factory=BriefUpdate)
    next_question: str
    done: bool = False


class TurnResult(BaseModel):
    """What a caller gets back: the merged draft, the question to ask, and the report."""

    novel_id: str
    draft: dict[str, JsonValue]
    next_question: str
    done: bool
    report: BriefReport
    degraded: str | None = Field(
        default=None,
        description="Set when the model call failed and the question is the deterministic one.",
    )


def merge(draft: Mapping[str, JsonValue], updates: BriefUpdate) -> dict[str, JsonValue]:
    """Apply `updates` to a copy of `draft`. Nested objects merge; lists and scalars replace."""
    merged: dict[str, JsonValue] = json.loads(json.dumps(dict(draft)))
    for key, value in updates.model_dump(mode="json", exclude_none=True).items():
        current = merged.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            current.update({k: v for k, v in value.items() if v is not None})
        elif isinstance(value, dict):
            merged[key] = {k: v for k, v in value.items() if v is not None}
        else:
            merged[key] = value
    return merged


def question_for(report: BriefReport) -> str | None:
    """The deterministic next question: a contradiction first, then the first missing field."""
    if report.contradictions:
        return (
            "He visto una contradicción: "
            + report.contradictions[0]
            + ". ¿Cuál de los dos datos prefieres cambiar?"
        )
    for path in report.missing:
        if path in QUESTIONS:
            return QUESTIONS[path]
    if report.errors:
        return "Hay un dato con formato incorrecto: " + report.errors[0] + ". ¿Me lo corriges?"
    return None


class Interviewer:
    """Role INTERVIEWER. One instance per interview; `novel_id` is the Langfuse session."""

    def __init__(
        self,
        client: ModelClient,
        observer: Observer,
        *,
        novel_id: str,
        repo: BibleRepository | None = None,
    ) -> None:
        self._client = client
        self._observer = observer
        self._repo = repo
        self.novel_id = novel_id
        self._session = observer.start_session(novel_id)
        self.last_question = OPENING_QUESTION

    def add_free_text(self, draft: Mapping[str, JsonValue], text: str) -> dict[str, JsonValue]:
        """Append pasted free text to the draft's `free_text` (untrusted; extracted at
        ingest). The injection pre-scan runs now and is logged to the policy log."""
        scan = prescan_injection(text)
        if scan.suspected:
            log_injection(
                self._repo, novel_id=self.novel_id, detail="prescan: " + ", ".join(scan.markers)
            )
        merged: dict[str, JsonValue] = dict(draft)
        previous = merged.get("free_text")
        merged["free_text"] = f"{previous}\n\n{text}" if isinstance(previous, str) else text
        return merged

    def fallback(self, draft: Mapping[str, JsonValue], reason: str) -> TurnResult:
        """The turn without the model: the draft unchanged and the deterministic question,
        so a failed call never loses the interview (the client repeats the answer)."""
        report = validate_brief(draft)
        question = question_for(report) or self.last_question
        self.last_question = question
        return TurnResult(
            novel_id=self.novel_id,
            draft=dict(draft),
            next_question=question,
            done=False,
            report=report,
            degraded=reason,
        )

    def safe_step(self, draft: Mapping[str, JsonValue], answer: str) -> TurnResult:
        """`step`, falling back to `fallback` when the model call fails or refuses."""
        try:
            return self.step(draft, answer)
        except MODEL_ERRORS as error:
            return self.fallback(draft, type(error).__name__)

    def step(self, draft: Mapping[str, JsonValue], answer: str) -> TurnResult:
        before = validate_brief(draft)
        prompt = load_prompt(PROMPT_NAME, self._observer)
        documents = [
            Document(path="brief/draft.json", text=json.dumps(dict(draft), ensure_ascii=False)),
            Document(path="brief/report.json", text=before.model_dump_json()),
            Document(
                path="interview/answer",
                text=f"Pregunta: {self.last_question}\nRespuesta: {answer}",
            ),
        ]
        with self._observer.trace(
            "interview_turn", session_id=self._session, metadata={"novel_id": self.novel_id}
        ):
            completion = traced_complete(
                self._client,
                role=AgentRole.INTERVIEWER,
                system=prompt.text,
                documents=documents,
                instruction=(
                    "Update the brief with the client's last answer and return the next "
                    "question in Spanish, following your rules."
                ),
                output_schema=InterviewTurn,
                observer=self._observer,
                prompt_name=prompt.name,
                prompt_version=prompt.version,
                sink=self._repo,
                scope=CallScope(novel_id=self.novel_id),
            )
        turn = completion.output
        merged = merge(draft, turn.updates)
        report = validate_brief(merged)
        forced = question_for(report)
        if report.contradictions and forced is not None:
            question, done = forced, False
        elif turn.done and not report.valid:
            question, done = forced or turn.next_question, False
        else:
            question, done = turn.next_question, turn.done and report.valid
        self.last_question = question
        return TurnResult(
            novel_id=self.novel_id, draft=merged, next_question=question, done=done, report=report
        )


__all__ = [
    "MODEL_ERRORS",
    "OPENING_QUESTION",
    "BriefUpdate",
    "InterviewTurn",
    "Interviewer",
    "TurnResult",
    "merge",
    "question_for",
]
