# Working conventions

The full rules are in `AGENTS.md`. This is the short form to keep in mind.

## Processes

- **Process 0 before any edit**: agree intent, layer, blast radius, out of scope and
  verification with the user. In this session the user delegated approvals; the agent
  decides and records the decision, it still does not skip the written summary.
- Order of authority: `docs/` > `specs/` > code. A contradiction is fixed at the highest
  layer first (Process 1 docs, 2 specs, 3 code), one commit per layer.
- No code without an approved spec **and** an approved plan
  (`specs/NNN-slug/NNN-slug.md`, `NNN-slug-plan.md`).
- Each block of programme 004 writes only the paths it owns (spec 004 § 3). Needing
  another block's file is a stop condition.
- `docs/process/` is a record area (spec 004 D10): no Process 1 needed unless a page
  starts defining design.

## Commit prefixes

| Prefix | For |
|---|---|
| `docs:` | design docs under `docs/` (Process 1) |
| `docs(process):` | the record area `docs/process/` |
| `spec(NNN):` | a spec, its approval or closing |
| `plan(NNN):` | an implementation plan |
| `backend:` · `frontend:` · `contract:` | code, and OpenAPI + generated client |
| `chore:` | typos, links, tooling, config with no change of meaning |

Agent commits end with the `Co-Authored-By` and `Claude-Session` trailers of the session.
Never push to `main`; never merge your own PR.

## Verification — light mode (plan 004, deviation V3)

The user asked for light verification in this programme:

- new modules: `ruff` + `mypy --strict` on the new package + **1–3 focused tests** per block;
- no schemathesis or hypothesis for new code; slow tests are cut first;
- the legacy gate of `AGENTS.md` step 14 stays as it is for legacy code;
- recorded as **U** in the accepted-risk register of `docs/verification.md`.

Every acceptance criterion still carries a Trust Spec letter (T · A · I · D · U), and
tests reference it (`# spec NNN / AC n`). `python exam/check.py` must not regress.

## Other rules

- All diagrams in Mermaid.
- No secrets anywhere: `.env.example` files hold empty placeholders only.
- Store access only through the store layer / `BibleRepository`; the frontend talks to
  the API only.
