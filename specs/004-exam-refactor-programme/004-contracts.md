# Programme 004 — contracts between blocks (wave B reference)

Part of plan 004. Published contracts are code; this page names them so wave-B blocks can
code against them. Changing one is a change to the provider's block spec.

## K1 — story bible (`from app.bible import BibleRepository, ...`) — built (spec 005)

Read `backend/app/bible/repository.py` for exact signatures. Highlights:

- `BibleRepository.open(path=None)` (uses `HARNESS_DB`), context manager; `":memory:"` works via `open_authoritative`.
- Novel: `create_novel(novel_id=, title=, dedication=, recipient_name=, session_id=)`, `get_novel`, `list_novels`, `update_novel`.
- Brief: `save_brief(novel_id, data, valid=, schema_version=)`, `get_brief`.
- Facts: `add_fact(novel_id, key=, value=, kind=, source=interview|free_text|planner, mandatory=)`, `find_fact`, `list_facts`, `update_fact_value`, `record_fact_usage(fact_id, chapter=, scene=, version=)`, `chapters_using_fact(fact_id, version=)`, `facts_used_in_chapter`.
- Cast: `add_character(novel_id, name=, role=, birth_date=, description=, fact_id=)`, `add_place(...)`, `add_event(novel_id, seq=, description=, story_date=, place_id=, participants=list|{id: age}, chapter=, scene=, kind=)`, `list_*`, `chronology_json(novel_id)`.
- Versions: `create_version`, `create_version_from(novel_id, parent, copy_chapters_except=set())`, `latest_version`, `set_version_status`, `block_version(..., repair_rounds=)`, `changed_chapters`.
- Chapters: `save_chapter_and_checkpoint(novel_id, version, chapter, text=, title=, summary=)` (one transaction, TLC CE1), `save_chapter_version` (upsert, frozen once published, CE3), `record_chapter_attempt` (rejected texts, nothing deleted), `count_chapter_attempts` (CE2), `get_chapter`, `list_chapters`, `first_incomplete_chapter(novel_id, version, total_chapters=)`.
- Guardrails: `add_forbidden_term(term, scope=global|novel, novel_id=, reason=)`, `list_forbidden_terms(novel_id)`, `log_policy_decision(policy=, decision=, ...)`, `list_policy_decisions`.
- Validators: `save_validator_result(...)`, `list_validator_results(...)`.
- Cost: `record_llm_call`, `cost_summary(novel_id, version=)`.

## K2 — observability (`from app.commons.observability import ...`) — built (spec 010)

`get_observer()`, `NoopObserver`, `observer.start_session(novel_id)`, `observer.trace(name, session_id, metadata)`,
`observer.span("role:<role>" | "tool:<name>", input=, metadata=)`, `observer.score(name, value, comment=, trace_id=)`, `flush()`.
`traced_complete(client, role=, system=, documents=, instruction=, output_schema=, observer=, prompt_name=, prompt_version=, max_attempts=2, sink=repo, scope=CallScope(novel_id, version, chapter, scene))`.
`load_prompt(name, observer)` → `PromptRef(name, text, version, content_hash)` from `backend/app/prompts/<name>.md`, published to Langfuse.
Model client: `ClaudeCodeModelClient()` from `app.commons.llm`; roles `AgentRole.INTERVIEWER|PLANNER|WRITER|EDITOR|JUDGE|CANONISER`. All roles run `claude-haiku-4-5`.

## K3 — validators (`from app.validators import ...`) — built (spec 005)

`ValidationPoint.{SCENE_ACCEPT, CHAPTER_CLOSE, PRE_PUBLISH, HOOK}`, `ValidationContext(novel_id, version, chapter, scene, text, repo, observer, extra, trace_id)`,
`ValidationResult(name, passed, score, evidence, explanation)`, `register`, `validators_for`, `run_point(point, ctx)` (persists + scores `validator:<name>`), `all_passed`.

**Registration convention.** Each validator-providing block exposes `register_validators() -> None`
in its package `__init__` or a `validators.py`:
`app.validators.programmatic` (B4), `app.policy` (B5), `app.judge` (B7), `app.reader.visual_check` (B10).
The pipeline calls `app.novel.setup.register_all()`, which imports each one guarded by
`ImportError`, so blocks merge in any order. `ctx.extra` carries: `brief` (dict), `plan` (dict),
`scene_texts` (list[str]), `chapter_title`, `feedback_role`.

## Brief (B2 provides `app.interview.brief.Brief`, pydantic; JSON Schema `backend/schemas/brief.v1.json`)

```json
{
  "recipient": {"name": "…", "age": 34, "gender": "femenino|masculino|no_binario|null",
                "birth_date": "1991-04-02|null", "relation_to_buyer": "…",
                "traits": ["…"], "hobbies": ["…"], "profession": "…|null"},
  "occasion": "cumpleaños|boda|aniversario|jubilación|nacimiento|graduación|otro",
  "buyer_name": "…", "dedication": "…",
  "people": [{"name": "…", "relation": "…", "traits": ["…"], "birth_date": "…|null"}],
  "pets": [{"name": "…", "species": "…", "description": "…"}],
  "places": [{"name": "…", "description": "…"}],
  "memories": [{"title": "…", "description": "…", "date": "YYYY-MM-DD|null", "place": "…|null", "people": ["…"]}],
  "genre": "aventura|fantasía|comedia|romance|misterio|ciencia_ficción|realista|fábula",
  "tone": "tierno|divertido|emotivo|épico|nostálgico|oscuro",
  "length": {"chapters": 10, "words_min": 1000, "words_max": 1500},
  "language": "es",
  "forbidden_terms": ["…"],
  "mandatory_elements": ["…"],
  "free_text": "…|null"
}
```

`app.interview.service.ingest_brief(repo, brief, *, novel_id=None, observer=None) -> str` validates, creates the novel
(title may be null until the planner names it), stores the brief, turns it into facts
(`kind ∈ recipient|trait|person|pet|place|memory|occasion|element`, `mandatory=True` for recipient name,
each memory, each pet, each person, each mandatory element), characters (recipient + people, with birth dates),
places, and novel-scope forbidden terms. Fact keys are stable slugs: `recipient.name`, `pet.<slug>.name`,
`person.<slug>.name`, `memory.<slug>`, `place.<slug>`, `element.<n>`.

## K4 / pipeline (B3 provides `app.novel`)

- `app.novel.pipeline.generate(repo, novel_id, *, client=None, observer=None, chapters=None) -> RunResult(novel_id, version, status: published|blocked|stopped_error, detail)`; resumes automatically from `first_incomplete_chapter`.
- `app.novel.pipeline.change_fact(repo, novel_id, fact_key, new_value, *, client=None, observer=None) -> ChangeResult(new_version, changed_chapters, status)`.
- Hook points: `before_scene_accept`, `before_chapter_close`, `before_publish` → `run_point(...)`.
- CLI: `cd backend && uv run python -m app.novel.cli {generate --brief PATH | resume --novel-id ID | change-fact --novel-id ID --fact KEY --value V | status --novel-id ID}`.

## K5 — reader (B10 provides `app.reader`, `app.export`)

Routes under `/novels`: list, versions, chapters of a version, bible (characters/places with chapter links),
`POST /novels/{id}/changes` (fragment or fact + requested change → `change_fact`), `GET /novels/{id}/versions/{v}/pdf`.
