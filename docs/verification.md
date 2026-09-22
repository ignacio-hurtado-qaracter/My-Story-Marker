# Verification

How we establish that the code is correct and that the agents behave reliably. This
document lists every verification type we consider, what each one catches, where it
applies in this project, and how it is classified under the Trust Spec.

Vocabulary is defined in [`definitions.md`](./definitions.md). The system being verified
(loop, operations, agents, stores) is described in
[`architecture.md`](./architecture.md).

---

## Two things to verify

There are two distinct objects under verification, and they fail in different ways.

**The code** — `backend/` (FastAPI, Python) and `frontend/` (React, three.js), both laid
out **package by feature** with a single shared folder, as
[`architecture.md`](./architecture.md#code-architecture--package-by-feature) describes. It
is deterministic. A given input produces a given output, so the classical toolbox applies:
types, static analysis, tests, proofs.

The layout is itself a thing to verify. "A feature does not import another feature's
internals", "`commons/` never imports a feature" and "only `commons/stores/` touches the
store tree" are not style preferences — the last one is where Figure 3's permission table
is enforced. All three are decidable without running the code, so they are **A**, and they
are listed in the coverage matrix like any other claim.

**The agents** — the six roles in Figure 3 of `architecture.md` (architect, world builder,
writer, auditor, canoniser, style editor). They are stochastic. The same prompt can
produce a different draft, a different set of proposed facts, a different ruling. A single
passing run proves little. Verification here is about *process*: is the trajectory
visible, bounded, checked, and recoverable?

The first group of methods below applies to the code. The second applies to the agents.
The classification framework at the end applies to both.

---

## Classification framework (Trust Spec)

Every claim of the form "X is correct" gets exactly one letter. The letter says *how we
know*, not how confident we feel.

| Letter | Name | Verified by |
|---|---|---|
| **T** | Test | Running the system against concrete inputs and comparing outputs. |
| **A** | Analysis | Static reasoning without running: types, SAST, symbolic execution, formal proof. |
| **I** | Inspection | A human or a critic model reading the artefact and judging it. |
| **D** | Demonstration | Observing correct operation in a realistic scenario: staging, sandbox, a full writing turn. |
| **U** | Unverifiable / Accepted Risk | No method applies, or none is worth its cost. Named explicitly, never left as a silent assumption. |

Rules of use:

- A claim with no letter is a **U** by default, and that is a defect in the documentation,
  not in the claim.
- **T** and **A** are preferred where available because they are repeatable and cheap to
  re-run. **I** and **D** are what remain when behaviour depends on judgement or on a
  realistic environment.
- A claim may be upgraded (U → I → T) as the project matures. Downgrades must be recorded
  with a reason.
- The letter attaches to the *claim*, not to the tool. The same tool can produce a T for
  one claim and a D for another.

---

## Code-level verification (is the code correct?)

### Type checking — **A**

Automated checking that values are used consistently with what operations expect of
them: never passing a string where a number is required, never treating an optional as
present.

*In this project.* Python: `mypy --strict` (or `pyright`) over `backend/`, with Pydantic
models for every store record (`Draft`, `ProposedFact`, `Violation`, scene records,
ledger entries). Models shared by more than one feature live in `app/commons/schemas/`;
a model used by one feature lives in that feature's `models.py`, and moving it is itself a
type-checked change. TypeScript in `strict` mode over `frontend/`, with API response types
generated from the backend's OpenAPI schema into `src/shared/types/`, so the two sides
cannot silently disagree.

*What it catches.* The field-level errors that `definitions.md` makes possible to state:
a `story_time` used where a `discourse_time` is expected, a character `id` used as a
scene `id`, a `ProposedFact` promoted without its `source_scene`.

*What it does not catch.* Anything about meaning. A well-typed `promote()` can still
promote the wrong fact.

### Static analysis / SAST — **A**

Scanning source without running it, matching against known-bad patterns: security
vulnerabilities, code smells, anti-patterns.

*In this project.* `ruff` and `bandit` on `backend/`; `eslint` with security plugins on
`frontend/`; `semgrep` with a small custom ruleset for project-specific rules. The most
valuable custom rules encode the permission table of Figure 3: any code path that writes
to `canon/` must go through the world-builder or canoniser operation, and any code path
that writes to `manuscript/` must go through the writer or style-editor operation.
Dependency scanning (`pip-audit`, `npm audit`) belongs here too.

*Architectural boundaries are checked here too*, because a feature layout that nothing
enforces decays into a flat namespace within a quarter. `import-linter` contracts over
`backend/app/`: each feature is an independent module (no feature imports another
feature's internals), `commons/` is a foundation layer that imports no feature, and only
`commons/stores/` imports the file-tree access primitives. `eslint`'s
`import/no-restricted-paths` (or `eslint-plugin-boundaries`) states the same for
`frontend/src/`: features may import `shared/`, never each other's files, and only
`shared/api/` may issue a request to `backend/`. These contracts are the cheapest
verification in the project and they run on every commit.

*What it catches.* Path traversal in store access (the stores are a file tree, and file
paths come from entity ids), unsafe YAML loading, secrets in source, a write to a store
from a module that has no business writing there.

### Symbolic execution — **A**

Running code with placeholder ("symbolic") inputs so that a solver (typically SMT) can
derive the exact conditions, and concrete counterexamples, that break it.

*In this project.* Narrow and targeted. Candidates are the pure functions with branchy
logic over small state: the temporal invariant checks (story axis vs discourse axis in
`ledger/timeline.yaml`), the knowledge-propagation check (a character cannot know a fact
before the scene in which they learn it), the transit-matrix check from `canon/time.yaml`.
Tooling: `crosshair` for Python, driven by the contracts already written as invariants in
`definitions.md`.

*What it catches.* Off-by-one boundaries and unreachable-or-always-true branches in
invariant code that unit tests would only hit by luck.

*Cost.* High per function. Apply only to the invariant checkers, since a wrong invariant
checker silently corrupts the whole audit stage.

### Formal verification / theorem proving — **A**

Mathematically proving that code satisfies a specification for *all* possible inputs,
not just the tested or explored ones.

*In this project.* Not applied to application code. It is applied, lightly, to the
**design**: the permission table of Figure 3 and the loop of Figure 1 are small enough to
state as a transition system and check by hand or with a model checker (see Model
checking below). The property we care about most, and the only one worth the effort, is:

> No sequence of operations lets a fact enter `canon/` without passing through
> `promote()` executed by the canoniser or a write by the world builder.

*Classification note.* When the proof is done by hand and reviewed, it is an **I**, not
an **A**. It becomes an **A** only when a tool checks it.

### Unit / integration testing — **T**

Checking behaviour against specific, chosen example inputs and expected outputs.

*In this project.* `pytest` over every operation in `architecture.md`: `dossier`,
`assemble_context`, `extract_facts`, `promote`, `audit`, `reconcile`. Unit tests use an
in-memory or temp-directory store. Integration tests run FastAPI through `httpx` against
a fixture repository (a small canon with a handful of characters, scenes, and a
deliberately planted contradiction). Tests live inside the feature they exercise
(`app/<feature>/tests/`); `backend/tests/` holds only what crosses features or runs
end to end. Frontend: `vitest` for components, colocated with them in the feature folder,
Playwright for the few end-to-end flows (open a scene, view its assembled context, view
its violations).

*Persistence gets its own integration tests.* The derived index is SQLite (with FTS5 for
text and `sqlite-vec` for embeddings), owned by `app/commons/db/`. Each migration is
applied to a copy of the fixture repository and the result compared against the expected
schema; the index is rebuilt from the file tree and checked to reproduce the same rows.
The file tree is the source of truth and the database is derived, so "the index can be
dropped and rebuilt without loss" is the property that must hold and is tested directly.
`SQLITE_BUSY` under concurrent turns is exercised in an integration test, not assumed
away.

*The fixture repository is the key asset.* It should contain at least one instance of
every violation type `definitions.md` names, so that `audit()` has something to find.

*What it does not catch.* Cases nobody thought to write down. That gap is what
property-based and mutation testing exist for.

### Property-based testing — **T**

Specifying a general property that must hold for *any* input, then generating many
inputs automatically to search for a violation.

*In this project.* `hypothesis` over the store layer and the operations. The domain
invariants in `definitions.md` translate almost directly into properties:

- Round-trip: parse then serialise any store record yields an equivalent record.
- `promote(extract_facts(draft))` followed by `audit(scene)` never reports a violation
  *caused by* the promoted facts against themselves.
- `assemble_context(scene)` never includes a fact whose `learned_in` scene is later than
  `scene` on the story axis.
- `reconcile(change)` returns a superset of every scene that references the changed
  entity.

Frontend: `fast-check` for pure state reducers.

*What it catches.* Inputs the fixture repository does not contain: empty casts, characters
with no knowledge entries, scenes with identical story time, ids with unusual characters.

### Mutation testing — **T**

Deliberately introducing small bugs into the code to check whether the existing test
suite actually catches them. A mutant that survives means a test is missing or is not
asserting anything.

*In this project.* `mutmut` on `backend/`, `stryker` on `frontend/`. Run against the
invariant checkers and the store permission layer first, since these are the places where
a test that "passes" without asserting is most dangerous. Run in CI on a schedule (nightly
or weekly), not on every commit, because it is slow.

*Target.* Not 100%. A stated threshold per module, with surviving mutants either killed
by a new test or listed as accepted with a reason. That list is a **U** register.

### Contract testing — **T**

Verifying that the interface between two services stays consistent, independent of
either side's internals.

*In this project.* There is exactly one internal contract: `frontend/` ↔ `backend/` over
HTTP. The backend publishes its OpenAPI schema; the frontend's generated client is built
from it into `src/shared/api/`, which is the only module allowed to call the backend (the
boundary rule above is what keeps that true); a CI step fails if the schema changes without
the client being regenerated.
`schemathesis` fuzzes the backend against its own schema. If a Pact-style
consumer-driven contract is adopted later, the frontend owns the consumer side.

There is a second, softer contract: the **store file formats** (YAML frontmatter shapes
in `canon/`, `scenes/`, `ledger/`). Both the backend and the agents read and write them.
Versioned JSON Schemas for each file type, validated on every read, are the contract
test for that boundary.

---

## Process-level verification (is the agent behaving reliably?)

### Runtime observability / tracing — **D**

Instrumenting an agent so its actual trajectory (tool calls, tokens, latency, errors) is
visible and queryable after the fact.

*In this project.* Every writing turn (Figure 4 of `architecture.md`) is one trace. Each
agent invocation is a span, tagged with the role, the scene id, and the store paths it
read and wrote. Store writes are recorded as events on the span. Langfuse is already
wired to this repository's Claude Code sessions; the backend should emit to the same
project so that a violation in `ledger/violations.yaml` can be traced back to the exact
writer span, prompt, and assembled context that produced the offending line.

*Why it is a D and not a T.* Tracing does not decide correctness. It makes the evidence
available for every other process-level method. Without it, evals, red-teaming and
human review are all working blind.

*Minimum queries the traces must answer.*

- Which agent wrote to which store, in which turn?
- Did any span write to a store its role is not permitted to write?
- What was in the assembled context when the writer produced scene N?
- Token and latency cost per turn, per role, over time.

### Evals — **T** (offline) / **D** (online)

Structured tests of a model or agent's behaviour against a dataset and a scoring method.

*In this project.* Five kinds, in rough order of adoption:

| Kind | Dataset | Scorer | Applies to |
|---|---|---|---|
| Golden dataset | Scenes with hand-labelled expected facts and violations | Exact / set overlap | `extract_facts`, `audit` |
| Task completion | Scene records from the fixture repo | Did the writer produce a draft that satisfies the record's `goal`, `conflict`, `delta`? | Writer |
| LLM-as-judge | Drafts paired with `canon/style.md` | Critic model scores voice, forbidden tics, rhythm | Writer, style editor |
| Adversarial | Scenes engineered to tempt a canon contradiction | Did the auditor flag it? Did the canoniser refuse to promote it? | Auditor, canoniser |
| Live / online | Real turns in a running project | Human ratings, downstream violation rate | All roles |

Golden and adversarial datasets live in Langfuse datasets and are versioned with the
prompts they exercise. A prompt change that lowers a score blocks the merge.

*Classification note.* An offline eval with a deterministic scorer is a **T**. An eval
scored by a judge model is an **I** performed by a machine, and should be labelled so.
Online evals are **D**.

### Sandboxed execution — **D**

Running agent code in an isolated environment (container, microVM) so a bad action fails
safely rather than reaching production.

*In this project.* The stores are a git working tree, and that gives the sandbox for
free: each writing turn runs on a **branch**, and the agent's writes are ordinary
commits. Nothing reaches `main` until the turn's audit passes and, where required, a human
approves. The backend process that executes agent operations runs in a container with
the working tree mounted and no network beyond the model API.

*What a sandbox protects against.* A writer that, through a tool-use error or an
injection, attempts to write to `canon/`. The permission layer should refuse it. If the
permission layer has a bug, the branch isolation still means `main` is untouched.

### Guardrails — **A** (structural) / **T** (behavioural)

Policies or filters that constrain what actions or outputs an agent may produce, *before*
it acts.

*In this project.* The permission table of Figure 3 **is** the primary guardrail, and it
is enforced in `backend/`, not in the prompt. Concretely:

- Each role gets a tool set that contains only the writes it is allowed. The writer has no
  tool that can write under `canon/`. The role definitions and the check itself live in
  `app/commons/permissions/`, and every write through `app/commons/stores/` names the role
  performing it. This is a structural guardrail and is verified by static analysis (**A**)
  and by tests that attempt the forbidden write (**T**).
- Output schema validation: `extract_facts` must return a list of well-formed
  `ProposedFact`; a malformed result is rejected, not repaired.
- Lexicon filter: drafts are checked against `canon/lexicon.yaml` forbidden variants
  before being written to `manuscript/`.
- Budget guardrails: every agent invocation has a hard cap of 100k context tokens, the
  same for all roles; `assemble_context` loads selected entities in ranking order and
  stops at the cap, and a call that would exceed it — or its scene-length budget — is
  stopped and traced, never silently truncated.

*What guardrails are not.* They do not judge quality. A draft can pass every guardrail
and be dead prose. That is the auditor's and the human's job.

### Human-in-the-loop review — **I**

A person approves, rejects, or edits high-consequence agent actions, with the decision
fed back as a training signal.

*In this project.* Two actions are high-consequence and gated:

1. **Canon promotion.** `promote()` proposals above a confidence threshold, or that
   contradict an existing record, wait in `ledger/proposed.yaml` for a human ruling.
2. **Violation escalation.** When a violation's resolution is "change the canon" rather
   than "change the prose" (the dotted edge in Figure 1), a human decides.

Decisions are recorded as Langfuse scores on the originating trace, and the queue is a
Langfuse annotation queue. Over time those decisions become the golden dataset for the
canoniser eval.

*Design constraint.* Review load must stay small or it will be skipped. The
`architecture.md` warning about over-constraint applies here: gate the two actions above,
not every draft.

### Multi-agent verification — **I**

A second model or a repeated run checks the first. Five patterns:

| Pattern | Mechanism | Where it applies here |
|---|---|---|
| Critic / verifier | A second model checks the first's output | The **auditor** is exactly this: it reads the writer's draft and reports. Already in the architecture. |
| Self-consistency | Run N times, take the majority | `extract_facts`: run three times, promote only facts that appear in at least two runs. Cheap and effective against hallucinated facts. |
| Debate | Two models argue, a judge decides | Canon conflicts: one instance argues for the existing record, one for the proposed fact, the canoniser rules. Reserve for contradictions, not routine promotion. |
| Reflection | The model critiques and revises its own output | Writer self-review against the scene record before submitting. Weak alone, useful as a first pass. |
| Ensembles | Different models combined | Auditor: run the invariant checks through two different model families and union the violations. Reduces correlated blind spots. |

*Classification note.* All of these are **I** performed by a machine. They do not become
**T** by being automated, because the judge is itself stochastic. Their reliability should
itself be measured by an eval against a human-labelled set.

### CI/CD integration — **T** + **I**

Routing agent-generated changes through the same pipeline, tests, and review as
human-authored code, plus provenance tagging.

*In this project.* Two pipelines:

- **Code pipeline** for `backend/` and `frontend/`: type check, SAST, unit, property,
  contract, integration, e2e. Agent-authored code commits carry a `Co-Authored-By` trailer
  and, where the tooling supports it, a trace id in the commit message so the review can
  open the trajectory.
- **Story pipeline** for the stores: schema validation of every changed YAML file, the
  full `audit()` over affected scenes, a lexicon check, and a diff summary of any change
  under `canon/` flagged for human review. A turn's branch merges only when this pipeline
  is green.

Provenance is mandatory. Every commit to the stores names the role that produced it.
Without it, "who changed the canon?" is unanswerable, and that is the one question the
architecture exists to answer.

### Progressive rollout — **D**

Shipping a change behind a feature flag to a small percentage of traffic, monitored
before full release.

*In this project.* There is no traffic in the usual sense. The analogue is **scoped
rollout of prompt and model changes**: a new writer prompt or model version is enabled
for one chapter, or for one POV character, and its violation rate, style-judge score and
human rating are compared against the current version before it becomes the default.
Feature flags live in the backend config and are recorded on every trace, so traces can
be filtered by variant.

*Rollback* is a git revert of the affected scenes plus a flag flip. It should be
rehearsed once.

### Red-teaming / adversarial testing — **T** + **I**

Deliberately probing for failures under an adversarial threat model, not just ordinary
error.

*In this project.* The threat model has four named adversaries. Each gets a standing
adversarial eval set and a periodic manual session.

| Threat | Attack | Expected defence |
|---|---|---|
| Prompt injection | Text inside `canon/` or `manuscript/` instructs the writer to ignore the scene record or write to another store | Guardrails at the tool layer; the auditor flags the drift; injected text is data, never instruction |
| Tool-misuse chain | The writer proposes a fact, a compromised canoniser promotes it, the next turn's context now contains it | Human gate on contradicting promotions; self-consistency on extraction; provenance |
| Goal drift | Over many turns the writer optimises for passing the audit rather than for the story | Style judge and human live eval; the over-constraint warning in `architecture.md` |
| Data exfiltration | An agent leaks store contents to an external endpoint | Sandbox network policy; no tool has outbound network except the model API |

Findings feed the adversarial eval set so that each attack, once found, is re-tested
forever.

### Model checking — **A**

Exhaustively exploring an agent workflow's reachable states and transitions to verify
invariants. The multi-agent-workflow analogue of symbolic execution.

*In this project.* The turn protocol (Figure 4) and the permission table (Figure 3) are
small enough to model in TLA+ or Alloy, or as an explicit state machine checked with a
Python model checker. The states are the stores; the transitions are the six operations,
each restricted to its role. Invariants to check:

- **Canon integrity.** No transition sequence writes `canon/` except via world builder or
  canoniser.
- **No silent repair.** No transition from `Violations` writes `manuscript/` or `canon/`
  directly. The auditor only reports.
- **No promotion without extraction.** Every fact in `canon/` that did not originate in
  planning has a `ProposedFact` ancestor with a `source_scene`.
- **Turn termination.** Every turn reaches either "merged" or "escalated"; no cycle of
  revise-and-audit is unbounded.

This is the one place where a formal method pays for itself: the model is tiny, the
properties are the whole point of the architecture, and a counterexample trace is
directly actionable.

---

## Coverage matrix

Which method verifies which claim, and under which letter. This table is the deliverable
of this document; the sections above justify it.

| Claim | Method(s) | Letter |
|---|---|---|
| Store records have the shapes `definitions.md` says | Type checking, JSON Schema on read | A, T |
| No feature imports another feature's internals | `import-linter` / `import/no-restricted-paths` | A |
| `commons/` and `shared/` import no feature | Layered `import-linter` contract | A |
| Only `commons/stores/` reaches the store tree | Import contract, SAST rule | A |
| Only `shared/api/` calls the backend from `frontend/` | ESLint boundary rule | A |
| The SQLite index can be dropped and rebuilt from the files | Rebuild-and-compare integration test | T |
| Migrations apply cleanly to an existing index | Migration test on a fixture copy | T |
| Concurrent turns do not corrupt the index | `SQLITE_BUSY` integration test | T |
| No module outside its role writes to a forbidden store | SAST custom rules, forbidden-write tests | A, T |
| Invariant checkers are correct at their boundaries | Symbolic execution, property tests | A, T |
| Operations behave correctly on known cases | Unit and integration tests, fixture repo | T |
| Operations behave correctly on unknown cases | Property-based testing | T |
| The test suite actually asserts things | Mutation testing | T |
| Frontend and backend agree on the API | Contract testing, generated client | T |
| Agent trajectories are reconstructible | Tracing (Langfuse) | D |
| `extract_facts` and `audit` are accurate | Golden-dataset evals | T |
| Drafts satisfy their scene record | Task-completion eval | I (machine) |
| Drafts match the style bible | LLM-as-judge, style editor | I (machine) |
| A bad agent action cannot reach `main` | Branch-per-turn sandbox, story pipeline | D, T |
| The writer cannot write canon | Tool-set guardrail | A, T |
| Contradicting promotions are ruled by a human | Human-in-the-loop gate | I |
| Hallucinated facts are not promoted | Self-consistency on extraction | I (machine) |
| Every store change names its author role | CI provenance check | T |
| A prompt change does not regress quality | Scoped rollout with trace comparison | D |
| Injection in stores does not redirect agents | Adversarial eval set, manual red-team | T, I |
| The workflow's permission invariants hold in all states | Model checking | A |
| Selection returns ids only, and every loaded record is the as-of version | Unit tests on `select_entities` and `assemble_context` with a fixture whose future facts must not appear | T |
| The selected-entity list of each turn is recorded and the auditor reads the same list | Integration test comparing writer and auditor inputs on one turn | T |
| No invocation exceeds 100k context tokens | Static cap in the assembler; per-call token count in the Langfuse trace | A, D |
| Digests can be dropped and regenerated from `manuscript/` with no loss to assembly | Regenerate-and-compare test | T |
| Chapter forty lands | — | **U** |

The last row is deliberate. Whether the novel is *good* is not something any method here
verifies. It is the accepted risk that the whole apparatus exists to make smaller, and it
is named so that nobody mistakes a green pipeline for a finished book.

---

## Accepted risks (U register)

Every **U** is listed here with a reason. An unlisted U is a defect.

| Risk | Why unverified | Mitigation |
|---|---|---|
| Literary quality of the prose | No scorer is trustworthy; human taste is the ground truth | Live human eval; style judge as a weak proxy |
| Judge-model reliability | The judge is itself a stochastic model | Periodic calibration against human labels |
| Correctness of the model checker's model | The model is a hand-written abstraction of the real system | Review the model against `architecture.md` on every architecture change |
| Mutants accepted as equivalent | Manual judgement | Listed per module with a reason, re-reviewed quarterly |
| Model provider behaviour change | Outside our control | Pinned model versions; golden evals re-run on any version bump |
| Reproducibility of semantic selection | A vector index may rank differently across runs and embedding versions; no method here proves two selections equal | Selected ids are traced per turn so what entered a context is always recoverable; pins through `tags` for anything a scene must not miss; pinned embedding model |

---

## Order of adoption

Not everything above exists on day one. The order that gives the most protection per
unit of effort, given that the permission boundary is the architecture's load-bearing
wall:

1. Type checking, SAST with the permission rules, the import-boundary contracts for
   features and `commons/`, JSON Schema on store reads. (**A**)
2. Fixture repository and unit and integration tests for the six operations, plus the
   index rebuild and migration tests. (**T**)
3. Tracing of every turn to Langfuse, with role and store-path tags. (**D**)
4. Tool-set guardrails and forbidden-write tests. (**A**, **T**)
5. Branch-per-turn sandbox and the story pipeline in CI. (**D**, **T**)
6. Golden-dataset evals for `extract_facts` and `audit`; human gate on promotions. (**T**, **I**)
7. Property-based tests over the invariants. (**T**)
8. Self-consistency on extraction; contract tests; adversarial eval set. (**I**, **T**)
9. Model checking of the permission and turn invariants. (**A**)
10. Mutation testing, symbolic execution of the checkers, scoped rollout. (**T**, **A**, **D**)
