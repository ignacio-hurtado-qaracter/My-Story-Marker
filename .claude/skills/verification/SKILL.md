---
name: verification
description: Decide how a change is proven correct, and write or review docs/verification.md. Use when choosing a verification method, assigning a Trust Spec letter (T/A/I/D/U) to an acceptance criterion, filling a spec's "Verification plan", auditing the coverage matrix or the accepted-risk register, or when the user asks how we know the code or an agent's output is correct.
---

# Verification

This project verifies two different objects and they fail differently. **Code** —
`backend/` (FastAPI, Python) and `frontend/` (React, three.js) — is deterministic, so the
classical toolbox applies. **Agents** — the roles in Figure 3 of
[`docs/architecture.md`](../../../docs/architecture.md) — are stochastic, so a single
passing run proves nothing and verification is about the *process*: visible, bounded,
checked, recoverable.

The closed list of methodologies, with definitions and sources, is in
[`references/methodologies.md`](./references/methodologies.md). **Read it before choosing a
method.** Do not invent a method that is not on that list; if one is genuinely missing, add
the row there first, with a source, and say so.

The project's own answers — which method covers which claim, at which letter — live in
[`docs/verification.md`](../../../docs/verification.md). That document is the deliverable;
this skill is how it is built and kept honest.

## The Trust Spec letters

| Letter | Verified by |
|---|---|
| **T** Test | Running the system against concrete inputs and comparing outputs |
| **A** Analysis | Static reasoning without running: types, SAST, symbolic execution, proof |
| **I** Inspection | A human or a critic model reading the artefact and judging it |
| **D** Demonstration | Observing correct operation in a realistic scenario: staging, sandbox, a full writing turn |
| **U** Unverifiable | No method applies or none is worth its cost — named, never silently assumed |

Rules that always hold:

1. **A claim with no letter is a U**, and that is a defect in the documentation, not in the
   claim. Every acceptance criterion in `specs/` carries one.
2. **The letter attaches to the claim, not to the tool.** The same tool yields a T for one
   claim and a D for another.
3. **Prefer T and A** where they apply: repeatable and cheap to re-run. I and D are what
   remain when the answer depends on judgement or on a realistic environment.
4. **Upgrades (U → I → T) are free; downgrades are recorded with a reason.**
5. **Every U is listed in the accepted-risk register** in `docs/verification.md`, with why
   it is unverified and what mitigates it. An unlisted U is a defect.

## Assigning a letter to a claim

Ask, in order, and take the first that genuinely applies:

1. Can it be decided without running the code — a type, a schema, a lint rule, a proof?
   → **A**. This is the cheapest and it is where the permission boundary belongs.
2. Can it be decided by running code against inputs, with a pass/fail assertion?
   → **T**. Example-based when the cases are known, property-based when they are not.
3. Does it need a realistic run to be believable — a full turn, a staged environment, a
   trace? → **D**.
4. Does it need judgement — a human or a critic model reading the output? → **I**. Say
   which, because a model judge is itself stochastic and belongs in the U register as a
   calibration risk.
5. Otherwise → **U**, and write the register row in the same edit.

A claim that needs two of these gets both letters (e.g. `A, T`): the static rule states it,
the test proves the rule bites.

## Writing or reviewing `docs/verification.md`

The document has a fixed shape. Keep it:

1. **Two things to verify** — code vs agents.
2. **Classification framework** — the letters and their rules.
3. **Code-level verification** — one section per artifact-level methodology, in the
   reference sheet's order. Each says: what it catches, where it applies *in this project*,
   and its letter in the heading.
4. **Process-level verification** — same, for the process-level methodologies.
5. **Coverage matrix** — claim → method(s) → letter. This is the deliverable; the sections
   above justify it.
6. **Accepted risks (U register)** — risk → why unverified → mitigation.
7. **Order of adoption** — what to build first, most protection per unit of effort.

When reviewing it against the current state of the project, check in this order and report
findings before editing:

- **Every methodology in the reference sheet has a section.** A missing one is a gap; say
  so even if the answer is "not worth it here", and then it is a U with a register row.
- **Every section names a concrete anchor in this repository** — a real path, tool, store or
  operation. A section that could be pasted into any project verifies nothing.
- **The stack is current.** Read `docs/architecture.md` before trusting any statement about
  `backend/`, `frontend/`, the store layout, the code layout or the permission table, and
  reconcile anything stale.
- **Every invariant in `docs/definitions.md` appears in the coverage matrix** with a method
  and a letter, or has a U row. This is the check that `AGENTS.md` Process 1 step 6 depends
  on.
- **Every row of the permission table** in `architecture.md` Figure 3 is covered. It is the
  load-bearing wall and it is enforced in `backend/`, never in the client or a prompt.
- **Every U in the matrix has a register row**, and every register row is still true.
- **Cross-references resolve** and no other doc or open spec contradicts what you changed.

## Working with specs

A spec's "Acceptance criteria" carry letters; its "Verification plan" says which test,
check, eval or review covers each and *where it lives*. A criterion whose verification does
not yet exist is not done. When you add a test for a criterion, reference the spec in it
(`# spec 012 / AC 3`) so the closing commit can list it.

Changing this document is a Process 1 docs change: see [`AGENTS.md`](../../../AGENTS.md).
Adding or changing an invariant means adding or updating its row in the coverage matrix in
the same commit.
