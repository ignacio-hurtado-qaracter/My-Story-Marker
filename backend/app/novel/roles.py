"""The three model-backed roles of the pipeline (spec 007): PLANNER, WRITER, EDITOR.

Each call goes through `traced_complete` (K2): one `role:<role>` span, the prompt name and
version, tokens and cost recorded in Langfuse and in the `llm_call` table (`sink=repo`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.bible import BibleRepository
from app.commons.llm import Document, ModelClient
from app.commons.observability import CallScope, Observer, PromptRef, load_prompt, traced_complete
from app.commons.permissions import AgentRole
from app.novel.models import ChapterEdit, NovelPlan, SceneDraft


@dataclass(slots=True)
class Roles:
    client: ModelClient
    observer: Observer
    repo: BibleRepository
    novel_id: str
    _prompts: dict[str, PromptRef] = field(default_factory=dict)

    def prompt(self, name: str) -> PromptRef:
        if name not in self._prompts:
            self._prompts[name] = load_prompt(name, self.observer)
        return self._prompts[name]

    def _call[T: BaseModel](
        self,
        role: AgentRole,
        prompt_name: str,
        documents: Sequence[Document],
        instruction: str,
        schema: type[T],
        scope: CallScope,
    ) -> T:
        prompt = self.prompt(prompt_name)
        completion = traced_complete(
            self.client,
            role=role,
            system=prompt.text,
            documents=documents,
            instruction=instruction,
            output_schema=schema,
            observer=self.observer,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
            max_attempts=2,
            sink=self.repo,
            scope=scope,
        )
        return completion.output

    def plan(
        self, documents: Sequence[Document], *, chapters: int, feedback: Sequence[str] = ()
    ) -> NovelPlan:
        instruction = (
            f"Diseña el plan completo de la novela: exactamente {chapters} capítulos numerados "
            f"1..{chapters}, cada uno con exactamente 3 escenas, cuyas word_budget sumen entre "
            "1100 y 1350 por capítulo. Usa en facts_used las claves del documento "
            "bible/facts.txt; cada hecho con mandatory=true debe estar en al menos una escena. "
            "Al menos un evento de cronología por escena. Fechas en formato YYYY-MM-DD."
        )
        if feedback:
            instruction += (
                "\n\nTu plan anterior tenía estos problemas; corrígelos todos:\n- "
                + "\n- ".join(feedback)
            )
        return self._call(
            AgentRole.PLANNER,
            "planner",
            documents,
            instruction,
            NovelPlan,
            CallScope(novel_id=self.novel_id, version=None),
        )

    def write_scene(
        self,
        documents: Sequence[Document],
        *,
        version: int,
        chapter: int,
        scene: int,
        words: int,
        feedback: str = "",
    ) -> SceneDraft:
        instruction = (
            f"Escribe la escena {scene} del capítulo {chapter} siguiendo el documento "
            f"plan/chapter-{chapter}.txt, en español, con unas {words} palabras. Continúa de "
            "forma natural desde manuscript/previous-tail.txt. Respeta exactamente los nombres "
            "de bible/exact-names.txt y no uses ningún término de bible/forbidden-terms.txt. "
            "Solo prosa: sin títulos, sin encabezados, sin comentarios."
        )
        if feedback:
            instruction += (
                "\n\nFEEDBACK del intento anterior (en manuscript/feedback.txt): corrígelo."
            )
        return self._call(
            AgentRole.WRITER,
            "writer",
            documents,
            instruction,
            SceneDraft,
            CallScope(novel_id=self.novel_id, version=version, chapter=chapter, scene=scene),
        )

    def edit_chapter(
        self,
        documents: Sequence[Document],
        *,
        version: int,
        chapter: int,
        words_min: int,
        words_max: int,
        task: str,
    ) -> ChapterEdit:
        target = (words_min + words_max) // 2
        instruction = (
            f"{task}\n\nEl capítulo final debe tener entre {words_min} y {words_max} palabras "
            f"(objetivo: unas {target}). Conserva exactamente los nombres de "
            "bible/exact-names.txt y los hechos del plan; ningún término de "
            "bible/forbidden-terms.txt. Devuelve title, text, summary (~120 palabras) e issues."
        )
        return self._call(
            AgentRole.EDITOR,
            "editor",
            documents,
            instruction,
            ChapterEdit,
            CallScope(novel_id=self.novel_id, version=version, chapter=chapter),
        )


__all__ = ["Roles"]
