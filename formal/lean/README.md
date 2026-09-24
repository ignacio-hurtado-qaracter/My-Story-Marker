# Lean 4: formal check of the story chronology

Spec [012](../../specs/012-lean-chronology/012-lean-chronology.md) (block B8 of
programme 004), requirements L01–L04. Lean 4 checks the **story's** chronology, not the
harness's code: a Lean file generated from the novel's chronology table is compiled with
`lake build`, and the build only succeeds if every invariant holds.

Core Lean only. No Mathlib, no dependencies: the pinned toolchain is all it needs.

## What is modelled

`Chronology/Basic.lean` defines:

| Type | Fields |
|---|---|
| `Date` | `y m d : Nat` (proleptic Gregorian), `Date.dayNumber` (days since 0000-03-01) |
| `Character` | `id : Nat`, `birth : Option Date` |
| `Place` | `id : Nat` |
| `Event` | `id`, `seq` (position in the telling), `date`, `day` (= `date.dayNumber`, precomputed), `place`, `participants : List Nat`, `kind : normal \| death \| departure`, `declaredAges : List (Nat × Nat)` |
| `Story` | `characters`, `places`, `events` |

Ids are `Nat` indices. The exporter maps the database's string ids to indices and keeps
the original ids and names in tables (`characterTable`, `placeTable`, `eventTable`) that
the checks never read, so no text from the novel is ever Lean code.

## The four invariants

Each is a `Bool` check that `decide` evaluates and a `Prop` saying what it means, linked
by a soundness theorem, so a passing build is a proof of the `Prop`.

| Invariant | `Prop` | Holds when |
|---|---|---|
| `temporalOrder` | `TemporalOrder` | every event told later (greater `seq`) happens on the same day or later |
| `agesCoherent` | `AgesCoherent` | every declared age equals the full years between the character's birth and the event date (no birth date: nothing to check) |
| `noBilocation` | `NoBilocation` | no character is in two different places on the same day |
| `noAfterExit` | `NoAfterExit` | after a `death` or `departure` event, its first participant (the one who dies or leaves; the others are witnesses) takes part in no event on a **later day of the story** — the exit day itself and flashbacks dated before it are fine |

`datesConsistent` (every `day` equals `date.dayNumber`) is checked inside
`temporalOrder`, `noBilocation` and `noAfterExit`, which compare `day`.

**Story axis, not discourse axis (tuning iteration 1).** Until 2026-09-24 `noAfterExit`
compared `seq`, the order of the telling, so a flashback narrated after a death but dated
before it would have failed; invariant 16 of `docs/definitions.md` is on the story axis.
It now compares `day`. In the pipeline the plan's `seq` is renumbered in date order
(`app/novel/chronology.normalise_events`), so the two readings only differed on same-day
ties. The Python mirror that phrases Lean's failures for the editor
(`app/validators/programmatic/chronology.diagnose`) had a worse divergence: it exited
**every** participant of a death, so in `b4-temporal` the recipient, who buries his dog,
"could not appear" afterwards and the plan stage stopped. Both now agree
(`app/formal/tests/test_lean.py::test_no_after_exit_is_on_the_story_axis`).

## The generated file

`backend/app/formal/lean_export.py` writes `Chronology/Generated/Story.lean` (git-ignored,
regenerated on every run) with `def story : Story`, and:

```lean
theorem story_temporalOrder : temporalOrderB story = true := by decide +kernel
theorem story_agesCoherent  : agesCoherentB  story = true := by decide +kernel
theorem story_noBilocation  : noBilocationB  story = true := by decide +kernel
theorem story_noAfterExit   : noAfterExitB   story = true := by decide +kernel
theorem story_ok    : validStory story = true := by simp [validStory, story_temporalOrder, …]
theorem story_valid : ValidStory story := validStory_sound story story_ok
```

A false invariant is a build error on the theorem that names it:

```
error: Chronology/Generated/Story.lean:49:62: Tactic `decide` proved that the proposition
  agesCoherentB story = true
is false
```

`decide +kernel` rather than plain `decide`: plain `decide` first reduces the check in
the elaborator, which hits `maxRecDepth` beyond about a hundred events. `native_decide`
is not used, since it trusts the compiler rather than the kernel.

**Cost.** Build time for the generated module, on the development container: 5 events
0.6 s, 100 events 3 s, 300 events 17 s. `temporalOrder` and `agesCoherent` are linear;
`noAfterExit` is exits × events; `noBilocation` is events² and dominates.

## Install and run

```sh
# elan (the Lean version manager) and the toolchain pinned in lean-toolchain
curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
  | sh -s -- -y --default-toolchain none
# or, without running a shell script: the release binary
curl -sSfL -o elan.tar.gz \
  https://github.com/leanprover/elan/releases/latest/download/elan-x86_64-unknown-linux-gnu.tar.gz
tar xzf elan.tar.gz && ./elan-init -y --default-toolchain none

export PATH="$HOME/.elan/bin:$PATH"
cd formal/lean
lake build                              # the library; fetches the pinned toolchain once
```

Check a chronology by hand:

```sh
cd backend
uv run python -c "import json; from app.formal import verify_chronology as v; \
  r = v(json.load(open('../formal/lean/examples/incoherent.json')), 'demo'); \
  print(r.passed, r.failed_invariants)"
# False ['agesCoherent', 'noBilocation']
```

`examples/ok.json` passes; `examples/incoherent.json` declares an age one day before the
birthday and puts a character in two cities on one day.

## How the harness calls it

- **Input.** The chronology JSON of contract K1 (`chronology_json`, from the story
  bible): characters with `birth_date`, places, events with `seq`, `story_date`,
  `place_id`, `participants`, `kind` and `declared_ages`.
- **API.** `verify_chronology(chronology, novel_id, lean_dir=None, timeout=300) ->
  LeanResult(passed, failed_invariants, output, lean_file)`. It never raises: a malformed
  chronology, a timeout or a missing toolchain is `passed=False` with the reason in
  `output` (a missing `lake` says "Lean toolchain missing").
- **Gate.** It runs at `pre_publish` (spec 004, decision D4), registered as a validator of
  the protocol K3. `passed=False` blocks the version: it is not published, and the failed
  invariants with Lean's message go back to the editor as feedback, naming the events
  involved.
- **Observability.** The result is the Langfuse score `lean_chronology` (1 pass, 0 fail)
  on the novel's trace, with `failed_invariants` as its comment (contract K2).

The registration as a validator and the score are wired by the pipeline and validator
blocks (B3, B4, B6); this block provides `verify_chronology`.

## L04 — a case Lean caught that no other validator did

None yet, and this is why: at the time of writing (2026-09-24) no real novel has been
exported, because the chronology table the exporter reads (K1, block B1) and the
pre-publish hook (K4, block B3) are being built in parallel. The samples show the class of
error Lean is there for — an age off by one around a birthday and a bilocation across
chapters — which the per-scene audit cannot see, since each scene is correct on its own.
The first real run through the gate (block B11's evals) records its result here: the case
caught, or the statement that Lean agreed with every other validator on it.
