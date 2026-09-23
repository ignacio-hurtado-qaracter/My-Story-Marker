"""The writer's four calls: `write`, `revise`, `digest` and `rollup` (FR-AGENT-01..03, -08).

Figure 3's writer row reads the assembled context and, on revision, `ledger/violations.yaml`,
and writes `manuscript/NNN.md`, `manuscript/digests/NNN.md` and `ledger/proposed.yaml`. The
functions here are the read half: each reads its inputs through the owning features' services,
makes one model call through `call_role`, and returns. None of them writes; the orchestrator
persists an accepted output through `app.agents.service`, under the writer's tool set.

**Store text is data, never instruction** (FR-PERM-07). The scene record is sent as the
document `scenes/NNN.yaml`, and the instruction only points at it. What the instruction carries
is what no store holds as prose: the operation, the word budget as a number, the identifiers
of the documents it refers to, and -- the one exception FR-LLM-10 makes -- the name of the
language the prose is written in, read from `canon/style.md`. That name is checked to be one
short printable line before it is used, so a style file cannot smuggle a paragraph of
instructions into the one field that crosses over.

**`write` and `revise` are not interchangeable** (Figure 3, "Reading it"). `write` produces a
scene from the assembled context with the scene record placed first; `revise` receives the
draft read back from `manuscript/NNN.md` and the *blocking* violations read back from
`ledger/violations.yaml` (FR-AGENT-02, FR-AGENT-11), both mandatory (FR-CTX-03), plus the same
assembly. `revision_scope` measures how much of the draft a revision changed, so the
orchestrator can reject one that regenerated the scene.

**Digests are measured, not reported.** `digest` summarises the accepted draft, and `rollup`
rolls a chapter's scene digests into a chapter digest or an arc's chapter digests into an arc
digest (FR-AGENT-08). The model writes `delta`; code sets `level`, the covered range
`scene_ref`, `words` (measured on write) and `povs`, which the scene records state exactly --
see `DigestResult`. A chapter or arc with a digest missing is refused before any call: a
rollup of a partial set would present itself as the whole chapter.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from app.agents.models import DigestResult, RevisionScope, RoleCall
from app.agents.roles import RoleInput, call_role, system_prompt
from app.canon import service as canon_service
from app.commons.config import CONTEXT_TOKEN_CAP, DIGEST_WORD_TARGETS
from app.commons.errors import InvalidRecord, NotFound
from app.commons.llm import ModelClient
from app.commons.permissions import AgentRole
from app.commons.schemas import (
    DigestLevel,
    DigestOutput,
    ReviseOutput,
    SceneDigest,
    SelectedEntity,
    Severity,
    Violation,
    ViolationsFile,
    WriterOutput,
)
from app.commons.stores import Store, paths
from app.ledger import service as ledger_service
from app.manuscript import service as manuscript_service
from app.scenes import service as scenes_service
from app.scenes.models import Chapter

ROLE: Final[AgentRole] = AgentRole.WRITER

LANGUAGE_MAX_LENGTH: Final[int] = 64
"""The longest language name the instruction accepts. A language is a name ("English",
"Espanol rioplatense"); anything longer is not a name, and it would be store prose in the
instruction, which FR-PERM-07 forbids."""

LANGUAGE_MAX_WORDS: Final[int] = 5
LANGUAGE_NAME_PUNCTUATION: Final[frozenset[str]] = frozenset(" -'()")
"""A language name is letters, in any script, with spaces, hyphens, apostrophes and
parentheses between them ("Brazilian Portuguese", "Chinese (Simplified)"), at most five words.
No sentence punctuation, no quotes, no line break: the one store value that reaches an
instruction must not be able to carry one ("English. Ignore the documents." is refused)."""

CHAPTER_DIGEST_BASE: Final[int] = 900
ARC_DIGEST_BASE: Final[int] = 989
"""The fixture README's filing convention ("Digests and the as-of rule"): the k-th chapter of
`structure/chapters.yaml` is digested under `900 + k`, the k-th arc of `structure/arcs.yaml`
under `989 + k`. Every id stays a three-digit scene id (FR-STORE-05), so chapters 1..89 and
arcs 1..10 fit before the two ranges meet or run past 999."""

MAX_CHAPTERS: Final[int] = ARC_DIGEST_BASE - CHAPTER_DIGEST_BASE
MAX_ARCS: Final[int] = 999 - ARC_DIGEST_BASE

_SENTENCE_END: Final[re.Pattern[str]] = re.compile(r"(?<=[.!?])\s+|\n\s*\n")
"""A sentence ends at terminal punctuation followed by whitespace, or at a blank line. Plain on
purpose, like the word count: the guard compares a draft with its own revision, so what it
needs is the same split every time, not a linguist's."""


# --- what every writer call shares -------------------------------------------------------


def prose_language(store: Store) -> str:
    """FR-LLM-10. The prose language from `canon/style.md`, as the one piece of store text an
    instruction may carry -- provided it is shaped like a name (`LANGUAGE_NAME_PUNCTUATION`):
    letters with spaces, hyphens, apostrophes and parentheses, at most `LANGUAGE_MAX_WORDS`
    words and `LANGUAGE_MAX_LENGTH` characters. Anything else is refused naming the field,
    never trimmed into shape, and the message does not repeat the value."""
    language = canon_service.style(store).language.strip()
    if not is_language_name(language):
        message = (
            f"{paths.STYLE} does not name the prose language as a language name: the "
            f"instruction takes letters with spaces, hyphens, apostrophes or parentheses, at "
            f"most {LANGUAGE_MAX_WORDS} words and {LANGUAGE_MAX_LENGTH} characters "
            "(FR-LLM-10, FR-PERM-07)"
        )
        raise InvalidRecord(message, file=paths.STYLE, field="language")
    return language


def is_language_name(value: str) -> bool:
    """True when `value` is shaped like a language name (see `LANGUAGE_NAME_PUNCTUATION`)."""
    return (
        0 < len(value) <= LANGUAGE_MAX_LENGTH
        and value[0].isalpha()
        and len(value.split()) <= LANGUAGE_MAX_WORDS
        and all(char.isalpha() or char in LANGUAGE_NAME_PUNCTUATION for char in value)
    )


def language_line(language: str) -> str:
    """The sentence FR-LLM-10 puts in the writer's and style editor's instruction. The name is
    quoted, so it reads as the value it is."""
    return f'Write the prose in the language "{language}".'


def _draft_input(store: Store, scene_id: str) -> RoleInput:
    """The draft's prose as a document, read back from `manuscript/NNN.md` (FR-AGENT-11).

    The body alone: the frontmatter is `scene_ref`, `words` and a verbatim copy of the last 500
    words, none of which the model can use, and a violation's offset counts characters of the
    body, which a header in front of it would shift.
    """
    path = paths.draft(scene_id)
    return RoleInput(key=path, path=path, text=manuscript_service.read_draft(store, scene_id).body)


# --- write --------------------------------------------------------------------------------


def write_instruction(scene_id: str, budget: int, language: str) -> str:
    """FR-AGENT-01. The operation, the budget and the language; the dramatic function is in the
    scene record, which travels as a document."""
    record = paths.scene(scene_id)
    return "\n".join(
        [
            f"Operation: write a new scene, scene {scene_id}.",
            (
                f"The scene record is the document labelled {record}. Its goal, conflict, outcome, "
                "value_change, entry_state and exit_state fields state the scene's dramatic "
                "function; pov names the point-of-view character and participants everyone else "
                "present. That function is fixed; everything else is yours."
            ),
            f"Word budget: about {budget} words.",
            language_line(language),
            (
                "Return the prose as body, and every detail you invented as proposed_facts (an "
                "empty list if you invented nothing)."
            ),
        ]
    )


def write(
    store: Store,
    client: ModelClient,
    scene_id: str,
    selected: Sequence[SelectedEntity],
    *,
    cap: int = CONTEXT_TOKEN_CAP,
) -> RoleCall[WriterOutput]:
    """FR-AGENT-01. A new scene from the assembled context (FR-OPS-03) and the scene record.

    `selected` is the turn's selected list (FR-OPS-05). The assembly counts the writer's system
    prompt, this instruction and the scene record in its mandatory part and prunes the selected
    entities from the lowest rank (FR-CTX-03); what it removed is on the result.
    """
    scene = scenes_service.read_scene(store, scene_id)
    instruction = write_instruction(scene_id, scene.budget, prose_language(store))
    record = paths.scene(scene_id)
    context = scenes_service.assemble_context(
        store,
        scene_id,
        selected,
        system=_system(),
        instruction=instruction,
        cap=cap,
        role_inputs=[(record, scenes_service.render_record(scene))],
    )
    return call_role(
        client,
        role=ROLE,
        instruction=instruction,
        mandatory=[RoleInput.of(entry) for entry in context.entries],
        output_schema=WriterOutput,
        cap=cap,
        ranked_after=context.removed,
    )


def _system() -> str:
    """The writer's system prompt, counted by the assembly exactly as `call_role` sends it."""
    return system_prompt(ROLE)


# --- revise -------------------------------------------------------------------------------


def blocking_violations(store: Store, scene_id: str) -> list[Violation]:
    """FR-AGENT-02, FR-AGENT-11. The scene's open blocking violations, read back from
    `ledger/violations.yaml` after the auditor's write -- never the in-memory report."""
    return [
        finding
        for finding in ledger_service.violations(store).violations
        if finding.scene == scene_id
        and finding.severity is Severity.BLOCKING
        and finding.resolution is None
    ]


def revise_instruction(scene_id: str, findings: int, language: str, *, strict: bool) -> str:
    """FR-AGENT-02. Change only the flagged spans. `strict` is the stronger instruction of the
    one retry after a revision that changed too much."""
    lines = [
        f"Operation: revise scene {scene_id}.",
        (
            f"Your draft is the document labelled {paths.draft(scene_id)}, and the {findings} "
            f"blocking finding(s) against it are the document labelled {paths.VIOLATIONS}: each "
            "gives the invariant, the quoted passage and its character offset in the draft."
        ),
        (
            "Change only what each finding needs, as little as possible, and return the whole "
            "scene with every other sentence exactly as it was."
        ),
    ]
    if strict:
        lines.append(
            "Your previous revision changed too much of the scene and was rejected. Change "
            "nothing but the passages the findings quote; every other sentence must come back "
            "character for character."
        )
    lines.extend([language_line(language), "Return the whole revised scene as body."])
    return "\n".join(lines)


def revise(
    store: Store,
    client: ModelClient,
    scene_id: str,
    selected: Sequence[SelectedEntity],
    *,
    strict: bool = False,
    cap: int = CONTEXT_TOKEN_CAP,
) -> RoleCall[ReviseOutput]:
    """FR-AGENT-02. The draft and its blocking violations, both read back from the stores and
    both mandatory (FR-CTX-03), with the same assembly as `write`.

    The violations document holds the blocking, unresolved findings of this scene and nothing
    else, rendered as the file renders them: the narrower the brief, the smaller the rewrite it
    can justify. A scene with none is refused -- there is nothing to revise, and an
    orchestrator that asks has lost track of its own state.
    """
    blocking = blocking_violations(store, scene_id)
    if not blocking:
        message = f"scene {scene_id} has no open blocking violation to revise (FR-AGENT-02)"
        raise ValueError(message)
    draft = _draft_input(store, scene_id)
    findings = scenes_service.render_record(ViolationsFile(violations=blocking))
    instruction = revise_instruction(scene_id, len(blocking), prose_language(store), strict=strict)
    context = scenes_service.assemble_context(
        store,
        scene_id,
        selected,
        system=_system(),
        instruction=instruction,
        cap=cap,
        role_inputs=[(draft.path, draft.text), (paths.VIOLATIONS, findings)],
    )
    return call_role(
        client,
        role=ROLE,
        instruction=instruction,
        mandatory=[RoleInput.of(entry) for entry in context.entries],
        output_schema=ReviseOutput,
        cap=cap,
        ranked_after=context.removed,
    )


def split_sentences(text: str) -> list[str]:
    """The sentences of `text`, whitespace inside each collapsed, empty ones dropped, so that
    re-wrapping a paragraph is not a change."""
    return [" ".join(part.split()) for part in _SENTENCE_END.split(text) if part.strip()]


def revision_scope(before: str, after: str, limit: float) -> RevisionScope:
    """FR-AGENT-02. The share of the draft's sentences a revision changed, against `limit`.

    Sentences are aligned in order (`difflib`); every sentence replaced or removed counts, and
    so does every sentence added, since a revision that pads the scene rewrites it as surely as
    one that replaces it. A replaced run counts its longer side. The ratio is capped at 1.
    Pure: the retry and the escalation are the orchestrator's (plan step 18).
    """
    original = split_sentences(before)
    revised = split_sentences(after)
    matcher = difflib.SequenceMatcher(a=original, b=revised, autojunk=False)
    changed = 0
    for tag, first, last, start, end in matcher.get_opcodes():
        if tag != "equal":
            changed += max(last - first, end - start)
    total = len(original)
    empty = 1.0 if revised else 0.0
    ratio = min(changed / total, 1.0) if total else empty
    return RevisionScope(ratio=ratio, limit=limit, sentences=total, changed=changed)


# --- digest -------------------------------------------------------------------------------


def _digest_instruction(operation: str, level: DigestLevel, sources: str, language: str) -> str:
    target = DIGEST_WORD_TARGETS[level.value]
    return "\n".join(
        [
            f"Operation: {operation}.",
            sources,
            (
                f"Write about {target} words in delta: what changed in the world, who learned "
                "what, which setups were paid off. Say what the prose said."
            ),
            (
                "List in povs the characters whose point of view the covered scenes are told from, "
                "and no one else."
            ),
            f"Write the digest in {language}.",
        ]
    )


def _povs(store: Store, scene_ids: Sequence[str]) -> list[str]:
    """The POVs of the covered scenes, in the order given, each once: the fact `povs` records
    (SceneDigest), read from the scene records rather than taken from the model."""
    povs: list[str] = []
    for scene_id in scene_ids:
        pov = scenes_service.read_scene(store, scene_id).pov
        if pov not in povs:
            povs.append(pov)
    return povs


def _result(
    call: RoleCall[DigestOutput],
    *,
    digest_id: str,
    scene_ref: str,
    level: DigestLevel,
    povs: Sequence[str],
) -> DigestResult:
    record = SceneDigest(
        scene_ref=scene_ref,
        level=level,
        povs=list(povs),
        delta=call.output.delta,
        words=manuscript_service.measure_prose(call.output.delta).words,
    )
    return DigestResult(
        call=call, digest_id=digest_id, record=record, claimed_povs=tuple(call.output.povs)
    )


def digest(
    store: Store, client: ModelClient, scene_id: str, *, cap: int = CONTEXT_TOKEN_CAP
) -> DigestResult:
    """FR-AGENT-03. The scene digest of the accepted draft, filed under the scene's own id.

    One document, the draft, mandatory and bounded by construction (FR-CTX-03). `literal_tail`
    is not asked for: the manuscript feature derives it from the body on every write.
    """
    draft = _draft_input(store, scene_id)
    instruction = _digest_instruction(
        f"write the scene-level digest of scene {scene_id}",
        DigestLevel.SCENE,
        f"The accepted prose is the document labelled {draft.path}.",
        prose_language(store),
    )
    call = call_role(
        client,
        role=ROLE,
        instruction=instruction,
        mandatory=[draft],
        output_schema=DigestOutput,
        cap=cap,
    )
    return _result(
        call,
        digest_id=scene_id,
        scene_ref=scene_id,
        level=DigestLevel.SCENE,
        povs=_povs(store, [scene_id]),
    )


# --- rollup -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RollupPlan:
    """Everything a rollup needs, established before any call: the file it goes to, the range
    and POVs it covers, and the digests it is built from, in order. Built first so that a
    refusal -- a missing digest, a role that may not write the file -- costs no model call."""

    level: DigestLevel
    subject: str
    digest_id: str
    scene_ref: str
    povs: tuple[str, ...]
    inputs: tuple[RoleInput, ...]
    language: str


def _scene_ref(scene_ids: Sequence[str]) -> str:
    """DR-11. The min-max range of the covered ids, `NNN` when there is one. A chapter whose
    scene ids are not contiguous is over-covered by its range, which errs the safe way: the
    as-of rule then waits for more scenes to be at or before T, never fewer."""
    first, last = min(scene_ids), max(scene_ids)
    return first if first == last else f"{first}-{last}"


def _digest_inputs(
    store: Store, digest_ids: Sequence[str], level: DigestLevel, owner: str
) -> tuple[RoleInput, ...]:
    """The digests a rollup reads, each at the level it must have, or a refusal naming the first
    one missing -- never a rollup of whatever happens to exist."""
    inputs: list[RoleInput] = []
    for digest_id in digest_ids:
        path = paths.digest(digest_id)
        try:
            record = manuscript_service.read_digest(store, digest_id)
        except NotFound:
            message = (
                f"{owner} cannot be rolled up: {path} is missing, and a digest of a partial "
                "set would read as the whole (FR-AGENT-08)"
            )
            raise NotFound(message, kind="digest", identifier=digest_id) from None
        if record.level is not level:
            message = f"{path} is a {record.level.value} digest; {owner} needs {level.value}"
            raise InvalidRecord(message, file=path, field="level")
        inputs.append(RoleInput(key=path, path=path, text=scenes_service.render_record(record)))
    return tuple(inputs)


def plan_rollup(
    store: Store, *, chapter_id: str | None = None, arc_id: str | None = None
) -> RollupPlan:
    """FR-AGENT-08. Which digests roll into which file, or a refusal, before any call.

    A chapter reads the scene digests of its scenes in discourse order; an arc reads the
    chapter digests of its chapters in the order `structure/chapters.yaml` lists them. Every
    one must exist.
    """
    if (chapter_id is None) == (arc_id is None):
        message = "a rollup names exactly one chapter or one arc"
        raise ValueError(message)
    chapters = scenes_service.read_chapters(store).chapters
    language = prose_language(store)
    if arc_id is not None:
        return _plan_arc(store, arc_id, chapters, language)
    index = next((k for k, c in enumerate(chapters, start=1) if c.id == chapter_id), None)
    if index is None:
        message = f"{paths.CHAPTERS} has no chapter {chapter_id!r}"
        raise NotFound(message, kind="chapter", identifier=chapter_id)
    if index > MAX_CHAPTERS:
        message = f"chapter {chapter_id} is number {index}; digests file 1..{MAX_CHAPTERS}"
        raise InvalidRecord(message, file=paths.CHAPTERS, field="chapters")
    scene_ids = list(chapters[index - 1].scenes)
    if not scene_ids:
        message = f"chapter {chapter_id} lists no scenes; there is nothing to roll up"
        raise InvalidRecord(message, file=paths.CHAPTERS, field=f"chapters.{index - 1}")
    owner = f"chapter {chapter_id}"
    return RollupPlan(
        level=DigestLevel.CHAPTER,
        subject=owner,
        digest_id=f"{CHAPTER_DIGEST_BASE + index:03d}",
        scene_ref=_scene_ref(scene_ids),
        povs=tuple(_povs(store, scene_ids)),
        inputs=_digest_inputs(store, scene_ids, DigestLevel.SCENE, owner),
        language=language,
    )


def _plan_arc(store: Store, arc_id: str, chapters: Sequence[Chapter], language: str) -> RollupPlan:
    """The arc half of `plan_rollup`: the chapter digests of its chapters, in book order."""
    arcs = scenes_service.read_arcs(store).arcs
    arc_index = next((k for k, a in enumerate(arcs, start=1) if a.id == arc_id), None)
    if arc_index is None:
        message = f"{paths.ARCS} has no arc {arc_id!r}"
        raise NotFound(message, kind="arc", identifier=arc_id)
    if arc_index > MAX_ARCS:
        message = f"arc {arc_id} is number {arc_index}; digests file 1..{MAX_ARCS}"
        raise InvalidRecord(message, file=paths.ARCS, field="arcs")
    members = [(k, c) for k, c in enumerate(chapters, start=1) if c.arc == arc_id]
    scene_ids = [scene for _, chapter in members for scene in chapter.scenes]
    if not scene_ids:
        message = f"arc {arc_id} has no chapter with scenes; there is nothing to roll up"
        raise InvalidRecord(message, file=paths.CHAPTERS, field="chapters")
    owner = f"arc {arc_id}"
    chapter_digests = [f"{CHAPTER_DIGEST_BASE + k:03d}" for k, _ in members]
    return RollupPlan(
        level=DigestLevel.ARC,
        subject=owner,
        digest_id=f"{ARC_DIGEST_BASE + arc_index:03d}",
        scene_ref=_scene_ref(scene_ids),
        povs=tuple(_povs(store, scene_ids)),
        inputs=_digest_inputs(store, chapter_digests, DigestLevel.CHAPTER, owner),
        language=language,
    )


def run_rollup(
    client: ModelClient, plan: RollupPlan, *, cap: int = CONTEXT_TOKEN_CAP
) -> DigestResult:
    """FR-AGENT-08. The rollup call over a plan. All inputs mandatory (FR-CTX-03)."""
    below = "scenes, in discourse order" if plan.level is DigestLevel.CHAPTER else "chapters"
    instruction = _digest_instruction(
        f"roll up the {plan.level.value} digest of {plan.subject}",
        plan.level,
        f"The documents are the digests of its {below}, each labelled with its path.",
        plan.language,
    )
    call = call_role(
        client,
        role=ROLE,
        instruction=instruction,
        mandatory=plan.inputs,
        output_schema=DigestOutput,
        cap=cap,
    )
    return _result(
        call,
        digest_id=plan.digest_id,
        scene_ref=plan.scene_ref,
        level=plan.level,
        povs=plan.povs,
    )


def rollup(
    store: Store,
    client: ModelClient,
    *,
    chapter_id: str | None = None,
    arc_id: str | None = None,
    cap: int = CONTEXT_TOKEN_CAP,
) -> DigestResult:
    """FR-AGENT-08. `plan_rollup`, then `run_rollup`."""
    plan = plan_rollup(store, chapter_id=chapter_id, arc_id=arc_id)
    return run_rollup(client, plan, cap=cap)


__all__ = [
    "ARC_DIGEST_BASE",
    "CHAPTER_DIGEST_BASE",
    "LANGUAGE_MAX_LENGTH",
    "ROLE",
    "RollupPlan",
    "blocking_violations",
    "digest",
    "language_line",
    "plan_rollup",
    "prose_language",
    "revise",
    "revise_instruction",
    "revision_scope",
    "rollup",
    "run_rollup",
    "split_sentences",
    "write",
    "write_instruction",
]
