---
id: 009
title: B5 — Guardrails, policy engine and Claude Code hooks
status: implemented      # closed 2026-09-25 on the user's delegation (programme 004 close-out)
supersedes: null
programme: 004
block: B5
owns:
  - backend/app/policy/**
  - backend/app/commons/db/authoritative/migrations/13xx_*.sql
  - .claude/settings.json
  - .claude/hooks/**
depends_on: [B1, B6]
provides: [app.policy.register_validators, FORBIDDEN_WORD_LIMIT_REASON]
consumes: [K1, K2, K3]
closes: [G01, G02, G03, G04, G05, H03, H04]
docs:
  - docs/definitions.md#invariants
  - docs/verification.md#guardrails--a-structural--t-behavioural
---

> **Approved 2026-09-24** on the user's delegation for this session (plan 004, deviation
> V6). Process 0 for this block is the programme's: spec 004 § 1.7 rows G01–G05, § 1.3 rows
> H03–H04, and round 1 question 12 (one implementation, two triggers).

## Motivation

Exam § 7 asks for a forbidden-word guardrail applied in code to every chapter before it is
accepted, with lists in SQLite by level, normalisation before comparing, a bounded rewrite,
an audit log and Langfuse traces; exam § 3 asks for two Claude Code hooks (chapter
validation and policy). Today only `forbidden_variants` in canon files exist, matched as
case-insensitive substrings (spec 004 § 1.7, G01 "contradicts", G02 "partial").

## Scope

**In.**
- `app/policy/normalise.py`: the normaliser of invariant 7 in `definitions.md` — case,
  accents, Spanish/English plurals (`-s`, `-es`, `-ces → z`), repeated letters, leetspeak
  (`0→o 1→i 3→e 4→a 5→s 7→t @→a $→s`), single-letter separators (`t.o.n.t.o`,
  `t-o-n-t-o`, `t o n t o`), whole-word and whole-phrase matching.
- `app/policy/engine.py`: `PolicyEngine(repo, observer)` — `check_text` (forbidden words,
  three levels: `global` and `novel` from the authoritative DB, optional `lexicon` passed
  by the caller) and `check_free_text` (prompt-injection markers). Every decision, `allow`
  included, is a `policy_decision` row; every rejection also a Langfuse score
  `guardrail:forbidden_words` with the terms in the comment.
- `app/policy/validators.py`: `forbidden_words_scene` (`scene_accept`) and
  `forbidden_words_chapter` (`chapter_close`), registered by
  `app.policy.register_validators()`. `FORBIDDEN_WORD_LIMIT_REASON = "forbidden_word_limit"`
  and `MAX_FORBIDDEN_REWRITES = 2` (the `MAX_SCENE_RETRIES` of `verification.md`).
- Migration `1300_forbidden_terms_global.sql`: a modest Spanish global seed list.
- `.claude/settings.json` hooks and `.claude/hooks/{validate_chapter,policy_guard}.py`.

**Out.** The rewrite loop itself (B3 runs the validators at its hook points and stops with
our reason), the chapter-length validator of the pipeline (B4; the hook reuses
`app.bible.word_count` for its own length check), the interview's own free-text pre-scan
(B2 may call `check_free_text`), `docs/` (B0), the bible repository (B1).

## Design

- Terms come from `BibleRepository.list_forbidden_terms(novel_id)` (K1): scope `global`
  and `novel`. A validator may add lexicon variants through `ctx.extra["lexicon_forbidden"]`
  (list of strings, level `lexicon`).
- Matching is token-based: text and term go through the same fold, each token gets a set of
  singular candidates; a term matches when every token of the term intersects the matching
  window of text tokens. Repeated-letter squeezing only applies to tokens that were
  stretched (a run of three or more), so `perro` never matches `pero`.
- `check_text` returns `PolicyDecision(decision="allow"|"reject", matches)`. A reject logs
  one `policy_decision` row per distinct term (`policy="forbidden_words"`,
  `decision="reject"`, `term`, surfaces in `detail`); an allow logs one summary row (terms
  checked, words).
- The validator's explanation lists the offending terms and asks for a rewrite without
  them; the pipeline feeds it back to the writer, at most `MAX_FORBIDDEN_REWRITES` times,
  then stops with `forbidden_word_limit`.
- Hooks. `validate_chapter.py` (PostToolUse, `Write|Edit`) runs on chapter-export paths
  only (`capitulo-N*.md`, `chapter-N*.md`, `.md` files under `chapters/` or `capitulos/`):
  word count 1000–1500 plus the forbidden-word check with the global list (the DB at
  `HARNESS_DB` if it exists, else the seed migration applied to an in-memory DB — one
  source). `policy_guard.py` (PreToolUse, `Write|Edit|Bash`) blocks `.env` files other than
  `.env.example`, API-key shaped content (`sk-ant-`, `sk-lf-`, `pk-lf-`), direct writes to
  `data/harness.sqlite*`, and forbidden words in chapter files. Both exit 2 with the reason
  on stderr. Non-chapter edits take a stdlib-only fast path. Decisions are appended to
  `.claude/hooks/policy-audit.log` (git-ignored); denials are also written to the policy log
  in the DB when it exists.

## Acceptance criteria

1. **G01** — A global term seeded by migration 1300 and a novel term added through K1 are
   both detected in a chapter. **T**
2. **G02** — `estúpido`/`estupido` and `tontos`/`tonto` are detected, as are `t0nt0`,
   `tontooo` and `t.o.n.t.o`; `tonto` is not found inside `tontería`, nor `culo` inside
   `ridículo`. **T**
3. **G03** — On a match the validator fails with an explanation listing the terms and asking
   for a rewrite; `FORBIDDEN_WORD_LIMIT_REASON` is exported for the pipeline's stop.
   **T** (validator) · **I** (loop, B3)
4. **G04** — Every decision is a `policy_decision` row (reject per term, allow summarised);
   a reject is also a `guardrail:forbidden_words` score of 0 with the terms. **T**
5. **G05** — Tests cover each level and one variant. **T**
6. **H03** — The chapter hook exits 2 on a short or dirty chapter file and 0 on other files. **D**
7. **H04** — The policy hook blocks `.env`, key-shaped content and writes to the harness DB,
   and lets ordinary code edits through in well under 2 s. **D**

## Verification plan

- AC 1–5: `backend/app/policy/tests/test_forbidden_words.py` (tests tagged `# spec 009 / AC n`).
- AC 6–7: the pipe commands of `.claude/hooks/README.md`, run once and pasted in the
  `chore:` commit body.
- Static: `ruff check app/policy`, `mypy --strict app/policy`.

## Open questions

- None blocking. The compliance checker's G04 rule looks for a table named `*audit*`; the
  audit log here is the existing K1 table `policy_decision`. Adjusting the check is B12's.

## Closing note (2026-09-25)

Closed on the user's delegation (programme 004 close-out, Process 2 step 12). Evidence at
`proyecto-desde-cero` @ `0e8118c`: backend gate `ruff check .` clean, `mypy --strict .`
clean (290 files), `pytest` 1758 passed / 8 skipped / 1 failed. The one failure is
`tests/test_boundaries_mirror.py`, the spec 001 store-boundary guard, which flags file I/O
in the new modules; it is not an acceptance criterion of this spec and is left to the
author (`docs/process/README.md`, "Pendiente para el autor").

| AC | Satisfied by |
|---|---|
| G01 | T — `app/policy/tests/test_forbidden_words.py` (global + novel term) |
| G02 | T — `test_forbidden_words.py` (accents, plurals, leetspeak, stretched and dotted variants; no `tontería` / `ridículo` false positive) |
| G03 | T — `test_forbidden_words.py` (explanation lists terms) · I — pipeline stop reviewed in `app/novel/pipeline.py` |
| G04 | T — `test_forbidden_words.py` (`policy_decision` rows, `guardrail:forbidden_words` score) |
| G05 | T — `test_forbidden_words.py` (each level and one variant) |
| H03 | D — `validate_chapter.py` sample runs in the `54854d3` commit body (exit 2 on dirty/short chapter, 0 otherwise) |
| H04 | D — `policy_guard.py` runs in `54854d3` (blocks `.env`, key-shaped content, DB writes; ordinary edits in ~0.05 s); it also blocked this close-out's own shell command naming the DB |
