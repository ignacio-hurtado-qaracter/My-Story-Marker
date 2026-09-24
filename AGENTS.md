# AGENTS.md

## Documentation map

| File | Contains | Read it when |
|---|---|---|
| `docs/definitions.md` | Entity vocabulary, fields, domain invariants | You need to know what a field means |
| `docs/domain-knowledge.md` | Entity graph, knowledge model, temporal axes | You need to know how entities relate |
| `docs/architecture.md` | Loop, operations, stores, turn protocol | You need to know how the system runs |
| `docs/verification.md` | Verification methods, Trust Spec letters, coverage matrix | You need to decide how a change is proven correct |
| `docs/process/` | The **record** of how the system was built: initial spec, trade-offs, explainers, diagrams, iteration log, red-team log. It cites `docs/`, never defines design, and is edited without Process 1 unless it states how the system works (spec 004, D10) | You need the history or the rationale of a decision, not the decision itself |
| `specs/` | One folder per change, holding its spec (scope, acceptance criteria, verification plan) and, once approved, its implementation plan | You are about to change code |
| `AGENTS.md` | This file — what you may do, right now | Every session |

---

## Rules

- Backend is done with Python + FastAPI
- Frontend with React + three.js
- Limit of concurrent tokens of context: 100k tokens
- SQL Lite -> con sin vector compatible
- All diagrams must be in mermaid format

---

## Repository

Monorepo with two top-level folders: `backend/` (FastAPI, Python) and `frontend/`
(React, three.js). Details in
[`docs/architecture.md`](./docs/architecture.md#repository-and-application-stack).

Three layers of artefacts, in order of authority:

1. **Docs** (`docs/`) — the design. What the system *is*.
2. **Specs** (`specs/`) — the changes. What we are *about to do*, and how we will know it worked.
3. **Code** (`backend/`, `frontend/`) — the implementation.

A lower layer never contradicts a higher one. If implementing a spec reveals that a doc is
wrong, stop and fix the doc first (Process 1), then the spec (Process 2), then the code
(Process 3). Never patch the contradiction at the lower layer and move on.

---

## Parallel work

When several agents build blocks of one programme at the same time (spec 004 § 5, as
adapted by its plan's deviation V1), these rules hold on top of the processes below:

1. **One worktree per block.** Each block agent works in its own git worktree and branch.
   The orchestrating session merges the blocks into the integration branch
   (`proyecto-desde-cero` for spec 004), the only branch it pushes; `main` is not touched.
2. **Ownership.** A block writes only the paths its row of the block map assigns it. A file
   it needs outside them is a stop condition: the orchestrator arbitrates and records it.
3. **Shared files** (`backend/app/main.py`, `backend/app/commons/config.py`,
   `backend/pyproject.toml`, `uv.lock`, `frontend/src/app/routes.tsx`,
   `frontend/package.json`) are edited in small, separate commits, never mixed with
   feature work. `backend/openapi.json` and the generated frontend types are regenerated,
   never hand-merged.
4. **Contracts first.** A contract between blocks (K1–K5 in spec 004) is published by its
   provider, as an interface with a fake, before consumers code against it. Changing a
   published contract is a change to the provider's spec.
5. **Migrations** of the authoritative database use per-block number ranges so parallel
   migrations never collide.
6. **Sync one way.** A block merges the integration branch into its own, with a clean
   worktree, before drafting and before merging.
7. **Approvals** may be delegated by the user for a session; the delegation is recorded in
   the spec it approves, and Process 0 still closes before any edit.

---

## Which process applies?

| You want to… | Process |
|---|---|
| Change what a field means, how entities relate, how the loop runs, or how we verify | 1 — Edit docs |
| Propose, refine or close a change to the system | 2 — Edit specs |
| Write or revise the implementation plan for an approved spec | 3 — Edit code |
| Change anything under `backend/` or `frontend/` | 3 — Edit code |
| Fix a typo or a broken link, with no change of meaning | Edit directly, commit with `chore:` |

When a change touches more than one layer, run the processes in order: 1, then 2, then 3.
Each layer gets its own commit, so the history shows the design decision before the code
that follows from it.

**Every one of the three processes starts with Process 0.** No edit to docs, specs or code
begins until the agent and the user have reached a shared understanding of what is being
asked and why.

---

## Process 0 — Shared understanding before any edit

Most damage to this system comes from an agent that understood the request slightly
wrong and edited confidently. The permission table, the invariants and the store layout
are precisely the kind of thing that breaks when a "small" edit is made under a
misreading. So the agent interrogates before it edits.

**The form.** The interrogation runs in rounds: every open decision is asked as a
numbered question with the agent's recommended answer, the user answers, and the agent
recomputes what is still undecided until nothing is left silently assumed. Facts are the
agent's job to look up; decisions are the user's to make.

**When it is mandatory.** Before any edit under Process 1, 2 or 3, unless the change is
one of the exemptions below.

**How to run it**

1. Read the request and the relevant docs and specs first. Look up every fact you can
   from the repository yourself. Do not ask the user something a grep would answer.
2. Ask the whole current frontier of decisions in one round, each with a recommended
   answer. At minimum the first round covers:
   - **Intent.** What the user wants to be true afterwards, in their words, restated by
     the agent for confirmation.
   - **Layer.** Whether this is a docs, spec or code change, and whether a higher layer
     must change first.
   - **Blast radius.** Which invariants in `definitions.md`, which rows of the permission
     table in `architecture.md` Figure 3, and which store paths the change touches.
   - **Out of scope.** What the user explicitly does not want changed.
   - **Verification.** How the user expects to know it worked, in Trust Spec letters.
3. Continue in rounds until the frontier is empty. A question whose answer depends on
   another open question waits for the next round.
4. Close with a written summary of the shared understanding: intent, layer, scope in and
   out, files to be touched, verification. For Process 2 and 3 this summary becomes the
   spec's "Scope" and "Acceptance criteria"; for Process 1 it goes into the commit body.
5. **Wait for the user's explicit confirmation of the summary.** Only then start editing.

**Exemptions.** The interrogation may be skipped only for:

- Typos, broken links and formatting, with no change of meaning (`chore:`).
- Changes where the user has already approved a spec that covers the exact edit and
  nothing new has been learned since. The spec *is* the recorded understanding.
- A change the user asked for by pointing at a line and stating the exact new value.

If in doubt, it is not exempt.

**Stop conditions during editing.** If, while editing, the agent discovers something that
was not covered by the shared understanding (a second call site, a doc that says
otherwise, an invariant that would need to bend), it stops, reopens the interrogation with the
new fact, and does not proceed until the summary is re-confirmed. Discovering a surprise
and pressing on is the failure this process exists to prevent.

---

## Process 1 — Editing the docs

The docs are the source of truth for the design. They are edited rarely and carefully.

**Before editing**

0. Run Process 0. A docs change rewrites what the system *is*, so the interrogation must
   surface which invariants, permissions and cross-references the change touches, and the
   user must confirm the summary before step 1.
1. Identify the single doc that owns the concept, using the documentation map. A concept
   is defined in exactly one place; the others link to it.
   - Meaning of a field or an invariant → `definitions.md`
   - Relationship between entities, knowledge or time model → `domain-knowledge.md`
   - Loop, operations, agent permissions, stores, stack → `architecture.md`
   - How something is proven correct → `verification.md`
2. Read the owning section in full and grep the other docs for the term you are changing.
   List every cross-reference before touching anything.
3. If the change alters an **invariant**, an **agent permission**, or a **store layout**,
   write a spec first (Process 2). These three things are load-bearing and get discussed
   before they are edited.

**Editing**

4. Edit the owning doc. Keep the file's existing structure, tone and language (English).
   Use the existing heading levels; do not add a new top-level section without reason.
5. Propagate. Update every cross-reference you listed in step 2 so that no doc describes
   the old behaviour. Do this in the same commit.
6. If you changed an entity, a field or an invariant, add or update the corresponding row
   in the **coverage matrix** of `verification.md`. Every invariant has a verification
   method and a Trust Spec letter, or an explicit **U** entry in the accepted-risk
   register.
7. If a Mermaid figure is affected, update the figure *and* its "Reading it" prose. A
   figure that disagrees with its text is worse than no figure.
8. If you added or renamed a doc, update the documentation map at the top of this file.

**Checks before committing**

9. Every relative link resolves. Every Mermaid block renders (paste it into a preview if
   in doubt).
10. Grep the term once more across `docs/`, `specs/` and this file. Zero stale mentions.
11. Any open spec in `specs/` that cites the changed section is still consistent. If not,
    flag it in the spec (Process 2, "Revising a spec").

**Commit**

12. One commit per conceptual change, prefixed `docs:`. The body states *what* changed in
    the design and *why*, not just which file was edited. Do not mix doc changes with code
    changes in one commit.

---

## Process 2 — Editing the specs

A spec is a short, versioned statement of one change: what it is, why, how far it goes,
and how we will verify it. Specs live in `specs/` and are the contract between the design
and the implementation. **No non-trivial code change without a spec.**

**Layout and naming**

```
specs/
  NNN-short-slug/            one folder per spec; NNN is zero-padded and sequential, never reused
    NNN-short-slug.md        the spec
    NNN-short-slug-plan.md   the implementation plan, written only once the spec is approved
```

The files keep the `NNN-short-slug` prefix inside the folder, so a filename is unique across
the repository and a grep for the spec id finds both. Links from a spec to `docs/` are
therefore `../../docs/…`.

The spec says *what* and *why*; the implementation plan says *how* and *in what order*. The
plan is a Process 3 artefact even though it lives next to the spec — it is written, approved
and revised under [Process 3, "The implementation plan"](#the-implementation-plan). Process 2
never writes it.

Each spec has YAML frontmatter followed by fixed sections:

```markdown
---
id: 012
title: Forbidden-write guard for canon/
status: draft            # draft · approved · implemented · superseded
supersedes: null         # id of the spec this replaces, if any
docs:                    # the doc sections this spec relies on
  - docs/architecture.md#figure-3--agents-and-write-permissions
  - docs/verification.md#guardrails
---

## Motivation
Why this change, and what fails today without it.

## Scope
What is in. What is explicitly out.

## Design
How it works, at the level of operations, stores and API. Refer to the docs; do not
restate them.

## Acceptance criteria
Numbered. Each criterion is observable and carries a Trust Spec letter (T · A · I · D · U)
from docs/verification.md saying how it will be verified.

## Verification plan
Which tests, checks, evals or reviews will exercise each criterion, and where they live.

## Open questions
Anything that must be settled before status can move to approved.
```

**Creating a spec**

0. Run Process 0. The spec is the written form of the shared understanding, so it is not
   drafted until the interrogation has closed. Its "Scope" and "Acceptance criteria" are taken
   from the confirmed summary, not invented afterwards.
1. Check `specs/` for an existing spec on the same subject. Extend or supersede it rather
   than duplicating. A superseding spec sets `supersedes:` and the old one moves to
   `superseded`.
2. Take the next free `NNN` and create the folder `specs/NNN-short-slug/`.
3. Fill every section. "Scope" must name what is *out*. "Acceptance criteria" must each
   carry a letter; a criterion with no letter is a **U** and must be justified in
   "Open questions" or moved to the accepted-risk register in `verification.md`.
4. Every claim about how the system works links to the doc section that says so. If no
   doc says so, the spec is proposing a design change: go to Process 1 first.
5. Status starts at `draft`.

**Approving a spec**

6. A human reviews it. Agents may draft and revise specs; only a human moves status to
   `approved`. Approval means: the scope is right, the criteria are verifiable, the open
   questions are closed or explicitly deferred.
7. Commit with `spec(NNN): approve <title>`.
8. Approval is the gate that unlocks the implementation plan. No plan may be written,
   committed or acted on while the spec is `draft` (Process 3, "The implementation plan").

**Revising a spec**

9. Small clarifications that do not change scope or criteria: edit in place, keep status,
   commit `spec(NNN): clarify …`.
10. Changes to scope, design or criteria after approval: status returns to `draft` and the
    spec is re-approved. Any implementation plan already written for it returns to `draft`
    too, and coding stops until both are approved again. Note the reason at the top of
    "Open questions".
11. If a doc the spec cites is changed (Process 1), re-read the spec and either confirm it
    still holds or revise it. Never leave a spec pointing at a section that no longer says
    what the spec assumes.

**Closing a spec**

12. When every acceptance criterion is met and its verification is in place and passing,
    status moves to `implemented`. The closing commit lists, per criterion, the test,
    check or review that satisfies it.
13. Specs are never deleted, and neither are their implementation plans. `superseded` and
    `implemented` are terminal states and stay in `specs/` as history.

**Commit**

14. Prefix `spec(NNN):`. One spec per commit. The implementation plan is not committed
    under this prefix — it belongs to Process 3 and uses `plan(NNN):`.

---

## Process 3 — Editing the code (`backend/` and `frontend/`)

Code is the lowest layer. It implements an approved spec, follows an approved
implementation plan, and is proven correct by the methods in `docs/verification.md`.

The order is fixed and has no shortcut:

```
Process 0 (interrogation)  →  spec  →  spec approved by a human
                           →  implementation plan  →  plan approved by a human
                           →  code
```

**Before writing code**

0. Run Process 0, unless the approved spec already covers the exact edit and nothing new
   has been learned. Even then, restate in one paragraph which files you will touch and
   which acceptance criteria you are implementing, and wait for confirmation. If the
   implementation reveals anything the spec did not anticipate, stop and reopen the
   interrogation (Process 0, "Stop conditions").
1. Locate the approved spec. If there is none, and the change is more than a typo, a
   comment or a dependency bump, write one (Process 2) and get it approved. Do not start
   implementing from a `draft`, and do not start *planning* from one either (step 4).
2. Read the doc sections the spec cites. Read `docs/architecture.md` Figure 3 whenever the
   change touches store access: the permission table is the load-bearing wall of the
   system and is enforced in `backend/`, never in the client and never in a prompt.
3. Work on a branch named `spec/NNN-short-slug`. Never commit to `main` directly.
4. Write the implementation plan for the spec, and ask the user whatever the spec leaves
   open before you write it. See "The implementation plan" below.
5. Wait for a human to approve the plan. No code is written before that.

### The implementation plan

The spec is the contract; the plan is the route through the code that honours it. It exists
so that the disagreement about *how* happens before the diff exists, not in review.

**The rule that governs it.** *No implementation plan without an approved spec.* If
`specs/NNN-short-slug/NNN-short-slug.md` is `draft`, `superseded`, or absent, there is nothing to plan
against: go to Process 2 and get a spec approved first. An agent that starts planning from a
`draft` spec has already broken this process, because the plan will encode decisions the
user has not yet made.

**Asking first.** Before writing the plan, the agent asks the user, in the rounds of
Process 0, everything the spec leaves open at the level of implementation: which module
owns the new behaviour, which existing call sites are in scope, what happens to data
already on disk, which test level satisfies each criterion. Facts are the agent's job to
look up in the repository; decisions are the user's to make. A plan whose "Steps" section
contains a silent assumption is a defect, not a draft.

**Layout.** One plan per spec, named after it:

```markdown
---
spec: 012                 # the approved spec this plan implements
status: draft             # draft · approved · done
---

## Files to touch
Each path, and in one line what changes in it. Anything not listed here is out of scope.

## Steps
Numbered and ordered, each one small enough to be a single commit. Each step names the
acceptance criteria it advances (`AC 1, AC 3`).

## Verification mapping
One row per acceptance criterion: criterion → Trust Spec letter → the test, check, review
or run that will satisfy it, and where it will live.

## Risks and stop conditions
What could make this plan wrong, and what the agent does if it happens. At minimum: what
would require reopening Process 0.
```

**Approving it.** Agents draft and revise plans; only a human moves a plan to `approved`,
exactly as with a spec. Approval means: the file list is complete, the steps are in a
workable order, and every acceptance criterion has a verification that a reviewer believes.

**Revising it.** If the code reveals the plan is wrong — a fourth call site, a migration
nobody costed — the agent stops, sets the plan back to `draft`, reopens Process 0 with the
new fact, and does not resume until the plan is re-approved. Discovering a surprise and
pressing on is the failure this process exists to prevent. If the surprise is in the spec
rather than the plan, fix the spec first (Process 2, "Revising a spec"), which sends the
plan back to `draft` with it.

**Committing it.** Commit the plan on the spec's branch before the first code commit,
prefixed `plan(NNN):`. When every step is done and every criterion verified, status moves
to `done` in the commit that closes the spec. Plans are never deleted.

**While writing code — rules that always apply**

6. **Store access goes through the permission layer.** No module reads or writes
   `canon/`, `structure/`, `scenes/`, `manuscript/` or `ledger/` except through the store
   layer, and every write names the agent role performing it. A write path that bypasses
   this is a bug even if it works.
7. **The frontend never touches the stores.** It talks to `backend/` over the API and
   nothing else.
8. **Every store record is typed.** Pydantic models on the backend, generated TypeScript
   types on the frontend. New file types under the stores get a JSON Schema, validated on
   read.
9. **Types are strict.** `mypy --strict` (or `pyright`) clean on `backend/`; TypeScript
   `strict` clean on `frontend/`. No `Any` and no `@ts-ignore` without a comment saying
   why and a link to the spec.
10. **Every acceptance criterion in the spec gets its verification** before the change is
    done: a test (T), a static rule (A), a review note (I), a demonstrated run (D), or an
    entry in the accepted-risk register (U). Add the test in the same commit as the code
    it verifies, as mapped in the plan's "Verification mapping".
11. **Changing the API changes the contract.** If a FastAPI route or model changes,
    regenerate the OpenAPI schema and the frontend client in the same change. CI fails on
    a stale client.
12. **No agent may widen its own permissions.** If implementing a spec seems to need a role
    to write to a store it is not allowed to write to, stop. That is a design change and
    goes to Process 1.
13. Keep the change inside the spec's scope and the plan's file list. Anything you notice
    outside it becomes a note in the spec's "Open questions" or a new spec, not an extra
    commit. A file you need that the plan does not list means the plan is wrong: revise it
    (see "Revising it") rather than touching the file quietly.

**Checks before committing**

14. Run the full local gate and paste its result in the commit body or PR description:

    ```
    backend/    ruff check . && mypy --strict . && bandit -r . && pytest
    frontend/   npm run lint && npm run typecheck && npm test
    contract    schema regenerated · client regenerated · no diff
    ```

15. Every test you added fails without your change and passes with it. If you cannot show
    that, the test is not verifying the criterion.
16. Grep for the spec id in your tests. Each test that satisfies a criterion references it
    (`# spec 012 / AC 3`), so the closing commit of the spec can list them.

**Commit and merge**

17. Commits are small and prefixed by area: `backend:`, `frontend:`, `contract:`. The body
    references the spec (`Implements spec 012, AC 1–3`). Agent-authored commits carry the
    `Co-Authored-By` trailer required by the session.
18. Open a PR against `main` titled `spec(NNN): <title>`. The description lists each
    acceptance criterion and the verification that covers it, with its letter, and links
    the approved implementation plan.
19. A human reviews and merges. Agents do not merge their own PRs.
20. After merge, close the spec (Process 2, "Closing a spec") and move the plan to `done`
    in a separate `spec(NNN):` commit.

---

## Summary of authority

| Layer | Who may change it | Requires | Commit prefix |
|---|---|---|---|
| `docs/` | Human, or agent with a human-reviewed commit | Process 0 confirmed; spec first if it touches invariants, permissions or store layout | `docs:` |
| `specs/NNN-short-slug/NNN-short-slug.md` | Anyone drafts; only a human approves or closes | Process 0 confirmed; consistency with cited docs | `spec(NNN):` |
| `specs/NNN-short-slug/NNN-short-slug-plan.md` | Agent drafts; only a human approves | An **approved** spec; Process 0 confirmed | `plan(NNN):` |
| `backend/`, `frontend/` | Agent or human, on a `spec/NNN-*` branch | An approved spec **and** an approved plan; passing gate; human merge | `backend:` `frontend:` `contract:` |

Process 0 is the one step no layer is exempt from. An agent that is unsure whether it
understood the request asks; it does not edit and hope. And no layer skips the one below
its own gate: no plan without an approved spec, no code without an approved plan.
