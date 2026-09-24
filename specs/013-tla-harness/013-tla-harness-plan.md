---
spec: 013                 # the approved spec this plan implements
status: approved          # approved 2026-09-24 on the user's delegation (plan 004, V6)
---

# Plan 013 — TLA+ model of the harness flow

## Files to touch

- `formal/tla/.gitignore` — ignores `tools/` and TLC's `states/` directory.
- `formal/tla/run-tlc.sh` — downloads the pinned `tla2tools.jar` if missing, checks its
  SHA-256, runs TLC on the model and tees the output to `tlc-output.txt`.
- `formal/tla/GiftNovelHarness.tla` — the model.
- `formal/tla/GiftNovelHarness.cfg` — constants, `SPECIFICATION`, `INVARIANT`s, `PROPERTY`s.
- `formal/tla/tlc-output.txt` — the output of the final TLC run.
- `formal/tla/COUNTEREXAMPLES.md` — every counterexample found during development.
- `formal/tla/README.md` — what is modelled, how to run, invariants, liveness, mapping.
- `specs/013-tla-harness/*` — this spec and plan.

## Steps

1. Commit spec and plan (`spec(013):`). — all ACs (contract)
2. Toolchain script and `.gitignore`; check that TLC starts. — AC 3
3. Write the first draft of the model and config; run TLC; for every violation, save the
   trace, record it in `COUNTEREXAMPLES.md`, fix the model (the fix must be a rule the code
   can follow), re-run. Repeat until TLC reports no error. — AC 1, AC 2, AC 3, AC 5
4. Save the final TLC output; write the README with the mapping table. — AC 3, AC 4
5. Commit (`formal:`): toolchain, model, config, output and records.

## Verification mapping

| AC | Letter | Satisfied by | Lives in |
|---|---|---|---|
| AC 1 | A · I | TLC explores the model without parse or semantic error; review | `tlc-output.txt` |
| AC 2 | A | Five invariants and the temporal properties in the `.cfg`, no violation | `GiftNovelHarness.cfg`, `tlc-output.txt` |
| AC 3 | A · D | `run-tlc.sh` run, N = 5, retries = 2, under 10 minutes | `tlc-output.txt` |
| AC 4 | I | Mapping table, flagged for wave C confirmation | `README.md` |
| AC 5 | I | One entry per real counterexample, each tied to a TLC trace | `COUNTEREXAMPLES.md` |

## Risks and stop conditions

- **State explosion** (TLC over 10 minutes): reduce `SCENES` first, never `MaxCrashes`
  below 1, and record the reduction in the `.cfg` and README. N = 5 and retries = 2 are not
  reduced (T03).
- **A fix would require a role to write a store it cannot write** (Figure 3), or change a
  K1 table: stop; that is a change to spec 005 or to the docs, raised to the orchestrator.
  Rules that only constrain *how* B1/B3 write (atomicity, insert-only versions) are recorded
  as rules for the code, not edited here.
- **The pipeline in wave B diverges from the modelled flow**: the mapping stays marked
  "to be confirmed", and wave C either updates the model or files the divergence against
  spec 007.
