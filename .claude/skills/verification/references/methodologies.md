# Verification methodologies — reference sheet

Every methodology this project considers, with a plain definition and a link that explains
the *methodology itself*, not a product that sells it. This is the closed list: a
verification plan that uses none of these is either wrong or is proposing a new row here.

Source: "Verification Methodologies — Reference Sheet", a third-party artifact (see
[`../../README.md`](../../README.md) for provenance). Definitions are the artifact's;
the project-specific columns live in [`docs/verification.md`](../../../../docs/verification.md).

## Artifact-level verification — is the code correct?

| Methodology | Definition | Explanation |
|---|---|---|
| Type checking | Automated checking that values are used consistently with what operations expect of them | [Type system — Wikipedia](https://en.wikipedia.org/wiki/Type_system) |
| Static analysis / SAST | Scanning source code without running it, to match against known-bad patterns | [Static program analysis — Wikipedia](https://en.wikipedia.org/wiki/Static_program_analysis) |
| Symbolic execution | Running code with placeholder inputs to derive exact failure conditions via an SMT solver | [Symbolic execution — Wikipedia](https://en.wikipedia.org/wiki/Symbolic_execution) |
| Formal verification / theorem proving | Mathematically proving code satisfies a specification for all possible inputs | [Formal verification — Wikipedia](https://en.wikipedia.org/wiki/Formal_verification) |
| Unit / integration testing | Checking behaviour against specific, chosen example inputs and expected outputs | [Unit testing — Wikipedia](https://en.wikipedia.org/wiki/Unit_testing) |
| Property-based testing | Specifying a general property, then generating many inputs to search for a violation | [QuickCheck — Claessen & Hughes, 2000](https://dl.acm.org/doi/10.1145/351240.351266) |
| Mutation testing | Deliberately introducing small bugs to check whether the test suite catches them | [Mutation testing — Wikipedia](https://en.wikipedia.org/wiki/Mutation_testing) |
| Contract testing | Verifying the interface between two services stays consistent, independent of internals | [Contract Test — Martin Fowler](https://martinfowler.com/bliki/ContractTest.html) |

## Process-level verification — is the agent behaving reliably?

| Methodology | Definition | Explanation |
|---|---|---|
| Runtime observability / tracing | Instrumenting an agent so its trajectory is visible and queryable after the fact | [Observability primer — OpenTelemetry](https://opentelemetry.io/docs/concepts/observability-primer/) |
| Evals | Structured tests of agent behaviour against a dataset and scoring method | [HELM — Liang et al., 2022](https://arxiv.org/abs/2211.09110) |
| Sandboxed execution | Running agent code in an isolated environment so bad actions fail safely | [Sandbox (computer security) — Wikipedia](https://en.wikipedia.org/wiki/Sandbox_(computer_security)) |
| Guardrails | Policies/filters constraining what actions an agent is allowed to produce | [AI Risk Management Framework — NIST](https://www.nist.gov/itl/ai-risk-management-framework) |
| Human-in-the-loop review | A person approves/rejects/edits high-consequence agent actions | [Human-in-the-loop — Wikipedia](https://en.wikipedia.org/wiki/Human-in-the-loop) |
| Multi-agent verification | Critic, debate, self-consistency, reflection or ensemble patterns checking model output | [AI Safety via Debate — Irving et al., 2018](https://arxiv.org/abs/1805.00899) |
| CI/CD integration | Routing agent-generated changes through the same pipeline as human-authored code | [Continuous integration — Wikipedia](https://en.wikipedia.org/wiki/Continuous_integration) |
| Progressive rollout | Shipping a change to a small percentage of traffic behind a flag before full release | [Feature toggle — Wikipedia](https://en.wikipedia.org/wiki/Feature_toggle) |
| Red-teaming / adversarial testing | Deliberately probing for failures under an adversarial threat model | [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) |
| Model checking | Exhaustively exploring an agent's reachable states/transitions to verify invariants | [Model checking — Wikipedia](https://en.wikipedia.org/wiki/Model_checking) |

## Classification framework

| Method | Definition | Explanation |
|---|---|---|
| T / A / I / D / U (Trust Spec) | Test / Analysis / Inspection / Demonstration / Unverifiable classification for each requirement | [Verification and validation — Wikipedia](https://en.wikipedia.org/wiki/Verification_and_validation) |

| Letter | Verified by |
|---|---|
| **T** — Test | Running the system against concrete inputs and comparing outputs |
| **A** — Analysis | Static reasoning without running: types, SAST, symbolic execution, formal proof |
| **I** — Inspection | A human or a critic model reading the artefact and judging it |
| **D** — Demonstration | Observing correct operation in a realistic scenario: staging, sandbox, a full run |
| **U** — Unverifiable / Accepted Risk | No method applies, or none is worth its cost. Named, never silently assumed |

**A caveat carried over from the source.** Property-based testing and evals have no single
neutral founding reference the way formal verification does. QuickCheck and HELM are the
papers that introduced or formalised each, not the only defensible citation.
