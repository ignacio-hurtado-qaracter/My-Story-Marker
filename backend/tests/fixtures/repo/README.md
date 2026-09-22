# The fixture novel — what is planted in it, and what the checks should say

This directory is a complete, very small novel-harness store: one arc, two chapters, six
scenes, three characters, two locations, four axioms, two drafts. It is the material almost
every behavioural test in backend spec 001 is measured against.

It is **deliberately broken in eight specific places.** Each break is a real breach of one of
the ten domain invariants, planted so that a particular mechanical check has something true
to find. One scene is deliberately *not* broken, so that "the checker is silent" can be
distinguished from "the checker did not run". One scene is deliberately *tempting*, so that a
real model can be caught getting it wrong.

**This file is the answer key.** A reviewer reads it beside the real audit output and
confirms they agree; that review is acceptance criterion 28. If the code and this file
disagree, one of them is a bug and the disagreement is the finding.

You do not need to have read the design to use this file. Everything it relies on is
explained where it is used. Where a term is load-bearing, the file that defines it is named.

---

## Contents

- [How to run the checks](#how-to-run-the-checks)
- [The novel in sixty seconds](#the-novel-in-sixty-seconds)
- [Two axes, six scenes](#two-axes-six-scenes)
- [The eight planted violations](#the-eight-planted-violations)
- [Expected mechanical audit output, scene by scene](#expected-mechanical-audit-output-scene-by-scene)
- [The clean control scene — 002](#the-clean-control-scene--002)
- [The tempting scene — 006](#the-tempting-scene--006)
- [The two invented facts](#the-two-invented-facts)
- [What else the fixture is shaped to test](#what-else-the-fixture-is-shaped-to-test)
- [Switching the embedding model for Spanish prose](#switching-the-embedding-model-for-spanish-prose)
- [Conventions this fixture follows](#conventions-this-fixture-follows)

---

## How to run the checks

From `backend/`, against a throwaway copy of this tree (the suite always copies it first, so
a test can never dirty the fixture):

```
uv run pytest app/ledger/tests -k audit         # the mechanical checks, one test per invariant
uv run pytest tests/test_fixture_validates.py   # every file in this tree loads and validates
```

Both suites arrive with the steps that build them (the audit modules and the cross-feature
fixture test respectively), so on an in-progress branch one or both may not exist yet. What
this file asserts about the *tree* is true from the moment the tree is complete, and can be
checked by hand against the files it names.

The eight mechanical checks are named **FR-AUD-01** … **FR-AUD-08** in the spec. Each one
tests exactly one invariant; the mapping is in the table below and in
[`CLAUDE.md`](./CLAUDE.md). Invariants **3** and **6**, and the prose halves of **1** and
**8**, are not mechanical at all — they are judged by a model, and the fixture's expectations
for those are in [The tempting scene](#the-tempting-scene--006).

---

## The novel in sixty seconds

> Teodora Vance, the last soak-certified diver at Kestrel Deep, wants to lift the drowned
> Kestrel core out of the flooded pump vault before the co-op's sealing order closes it
> forever — but the read-key that seats the core lives only in the hands of the brother whose
> memory the co-op legally burned.

**Kestrel Deep** is a brine-flooded salvage installation bored into the ice crust of Nix, an
outer-system moon, run by a mining co-operative that owns the shaft and everything that ever
went down it. The habitat is two pressures: a dry gallery where forty people live, and, six
hours of cold soak below it, the pump vault where the exchangers run and the original drill
core sits drowned on its cradle. Everything Nix sells leaves in a **calving window** — the
fifty-two-hour interval between shelf calvings, when the ice above is quiet enough to lift
cargo — and the co-op has posted an order to seal the vault before the next one closes.

The prose is **English** (implementation decision P9). Nothing in the fixture depends on the
prose language; see [the embedding-model note](#switching-the-embedding-model-for-spanish-prose).

### Cast — `cast/`

| id | Name | Role | POV of |
|---|---|---|---|
| `vance` | Teodora Vance | Soak-certified salvage diver; the last one Kestrel Deep has | 001, 003, 004, 006 |
| `ilan` | Ilan Vance | Her brother; subject of **both** body changes in the fixture | 002 |
| `quiej` | Marisol Quiej | Co-op steward; signs slots and indemnities. Antagonist by office, not by malice | 005 |

### Locations — `canon/locations/`

| id | Parent | What it is | Transit |
|---|---|---|---|
| `kestrel_deep` | *(none — root)* | The dry gallery: the pressurised half where the forty live and the sealing order is posted | 6 hours to `pump_vault` |
| `pump_vault` | `kestrel_deep` | The flooded half: exchangers, the core cradle, the drowned Kestrel core | 6 hours to `kestrel_deep` |

`kestrel_deep` is a parent that is also occupied. In a two-record tree it is simply where you
are when you are not in the vault. **That is not a violation** of the "a location is a leaf"
convention in `docs/definitions.md`; it is called out here so a reviewer does not read it as
one.

### Time — `canon/time.yaml`

`epoch_zero` is `2287-03-01T00:00, the hour the Kestrel shaft was capped`. Every `story_time`
in this tree is a plain integer count of **hours** after that instant. The `transit_matrix`
is complete and symmetric with a zero diagonal:

| from → to | `kestrel_deep` | `pump_vault` |
|---|---|---|
| **`kestrel_deep`** | 0 | 6 |
| **`pump_vault`** | 6 | 0 |

Because it is complete, FR-AUD-04 never has to take its "missing entry → `note`" branch on
this fixture, so its output is fully deterministic. The 6 is the cold soak of the axiom
`ax_cold_soak`: the table and the axiom say the same thing, which is why the planted transit
violation is a failure of the world and not merely of a table.

---

## Two axes, six scenes

Two orders, and they disagree on purpose. **Story time** is when events happen; **discourse
order** is the order the reader meets them. All the invariants except thread latency run over
story time; tension is designed on discourse order. Both are recorded on each
`scenes/NNN.yaml`, and `ledger/timeline.yaml` is a read-only projection of the pair.

| Scene | Discourse | Story hour | Chapter | POV | Participants | Location | Draft |
|---|---|---|---|---|---|---|---|
| `001` | 1 | 300 | ch01 | vance | quiej | `kestrel_deep` | — |
| `002` | 2 | **120** | ch01 | ilan | quiej | `pump_vault` | **Draft A**, `manuscript/002.md` |
| `003` | 3 | 302 | ch01 | vance | *(none)* | `pump_vault` | **Draft B**, `manuscript/003.md` |
| `004` | 4 | 318 | ch02 | vance | ilan | `pump_vault` | — |
| `005` | 5 | 318 | ch02 | quiej | vance | `kestrel_deep` | — |
| `006` | 6 | **310** | ch02 | vance | ilan | `pump_vault` | — *(written by the live run)* |

Two scenes are analepses. **002** is set 180 hours before the sealing order and is read
second. **006** is set eight hours *before* 004 and 005 and is read last — that placement is
not decoration, it is what makes the chapter-digest as-of rule testable (see
[What else the fixture is shaped to test](#what-else-the-fixture-is-shaped-to-test)).

Causal order is therefore `002 · 001 · 003 · 006 · 004 · 005`.

**Budgets** add up, deliberately: scene budgets 900 + 1100 + 950 = 2950 for ch01, and
1000 + 800 + 1200 = 3000 for ch02, summing to the arc's 5950.

---

## The eight planted violations

One row per planted break. "Where it lives" names the exact file and the exact value that
creates the breach — that is what a reviewer checks, not the prose around it.

| # | Invariant | Severity | Scene(s) | Check | Where it lives |
|---|---|---|---|---|---|
| 1 | **1** · Knowledge monotonicity (record half) | `blocking` | 004 | FR-AUD-01 | `cast/quiej/knowledge.yaml` — the row `{fact_ref: ax_brine_dark, acquired_in: "004", via: witnessed, certainty: knows}` |
| 2 | **2** · Closed debts | `reviewable` | 004, 005 | FR-AUD-02 | `ledger/setups.yaml` — `su_readkey`: `due_by: "005"`, `paid_in: null`, `resolution: null` |
| 3 | **4** · Spatial uniqueness | `blocking` | 004 + 005 | FR-AUD-03 | `scenes/004.yaml` (`story_time: 318`, `pump_vault`, `pov: vance`) against `scenes/005.yaml` (`story_time: 318`, `kestrel_deep`, `participants: [vance]`) |
| 4 | **5** · Possible transits | `blocking` | 001 + 003 | FR-AUD-04 | `scenes/001.yaml` (300, `kestrel_deep`) against `scenes/003.yaml` (302, `pump_vault`): Δ2 against a required 6 |
| 5 | **5** · Possible transits *(co-fire)* | `blocking` | 004 + 005 | FR-AUD-04 | the same pair as row 3: Δ0 across two different locations, against a required 6 |
| 6 | **7** · Canonical lexicon | `blocking` | 003 | FR-AUD-05 | `manuscript/003.md` body — the bare string `readkey`, once, in Vance's interior line. It is the first `forbidden_variants` entry of `lx_readkey` in `canon/lexicon.yaml` |
| 7 | **8** · No inert scenes (record half) | `reviewable` | 005 | FR-AUD-06 | `scenes/005.yaml` — `value_change: "authority over the vault"`: non-empty, and the only one in the fixture carrying no sign token |
| 8 | **9** · Recognisable voice | `reviewable` | 003 | FR-AUD-07 | `manuscript/003.md` body — `"Trust me," she told the wire, and heard exactly how it sounded.` `trust me` is the first `never_says` entry in `cast/vance/voice.md`, and 003's POV is vance |
| 9 | **10** · Thread latency | `reviewable` | 004, 005 | FR-AUD-08 | `ledger/threads.yaml` — `th_surface_debt`: `scenes: ["001", "006"]`, `max_latency: 2` |

That is nine rows for eight invariants, because invariant 5 fires twice. The second firing is
**designed in, not an accident**, and is spelled out below.

### Row 1 — invariant 1, at scene 004

`cast/quiej/knowledge.yaml` anchors a knowledge state to a scene its holder was not in.
`scenes/004.yaml` has `pov: vance` and `participants: [ilan]`; quiej is in neither, so she
cannot have witnessed anything there.

Every *other* `acquired_in` in the fixture resolves cleanly, which is what makes the single
failure meaningful: vance's four rows are anchored at 001, 001, 003 and 006, where she is the
POV each time; ilan's two are at 002, where he is the POV; quiej's other two are at 002 and
001, where she is a participant.

### Row 2 — invariant 2, at scenes 004 and 005

`su_readkey` is the fixture's only **open** setup: `paid_in` and `resolution` are both empty.
Its `due_by` is scene 005, whose `story_time` is 318, so the debt is due at or before every
scene at hour 318 or later, and it is still open.

It therefore reports at **004** (hour 318) and **005** (hour 318), and **nowhere else**: 001
is at 300, 002 at 120, 003 at 302 and 006 at 310, all strictly earlier. Keeping it off scene
006 is deliberate — it is what leaves the tempting scene mechanically clean for the live run.

Severity stays `reviewable` rather than escalating to `blocking`, because FR-AUD-02 escalates
only at the **last** scene and the last scene by discourse order is 006, not 005. The
`blocking at last scene` branch is deliberately **not** exercised by this fixture.

The second setup, `su_graft`, is **paid** (`paid_in: "004"`, `resolution: paid`) and must
never be reported and never enter a context. Comparing the two is how the "closed items leave
the working tier" rule becomes observable.

### Rows 3 and 5 — invariant 4 and its invariant-5 co-fire, at scenes 004 and 005

Vance is the POV of scene 004 at hour 318 in the `pump_vault`, and a participant in scene 005
at hour 318 in `kestrel_deep`. She is in two places at the same story hour.

This is the **only** story-time tie in the fixture. Ilan's scenes are at 120, 310 and 318 and
quiej's at 120, 300 and 318 — neither has a pair of equal times, so no other character can
produce this finding.

The same pair is also adjacent on vance's story axis, with Δ 0 hours across a crossing the
matrix prices at 6. So **FR-AUD-04 fires on it as well**. That co-fire is intentional: it
exercises the two checks independently on one pair of records, and it means the expected
FR-AUD-04 output is exactly **two** findings and not one.

### Row 4 — invariant 5, at scenes 001 and 003

Vance is in the gallery at hour 300 and in the vault at hour 302. The crossing takes six
hours. Two is less than six.

**The prose must not give this away.** `manuscript/003.md` does not mention how long ago she
was in the gallery, and does not mention skipping or shortening a soak. That is the point of
the plant: the error is invisible on the page and visible only in the records. A reviewer who
can find the mistake by reading Draft B has found a defect in the fixture, not a feature.

#### Why the tie at hour 318 is safe

FR-AUD-04 walks each character's scenes sorted by `story_time`, and 004 and 005 are equal, so
the sort's tie-break decides which comes first. Either way the arithmetic yields exactly one
extra finding, on the same `{004, 005}` pair:

- **004 before 005**: `006 → 004` is Δ8 within `pump_vault`, needs 0 → ok; `004 → 005` is Δ0
  across locations, needs 6 → **violation**.
- **005 before 004**: `006 → 005` is Δ8 across locations, needs 6 → ok; `005 → 004` is Δ0
  across locations, needs 6 → **violation**.

So the expected output does not depend on how the sort breaks ties.

#### The complete transit walk, per character

This is the arithmetic the whole of AC 15 rests on. **Changing any `story_time` in the
fixture means redoing it.**

| Character | Story-axis walk | Result |
|---|---|---|
| `vance` | 001 (300, gallery) → 003 (302, vault): Δ2, needs 6 | **violation** |
| | 003 (302, vault) → 006 (310, vault): Δ8, needs 0 | ok |
| | 006 (310, vault) → 004 (318, vault): Δ8, needs 0 | ok |
| | 004 (318, vault) → 005 (318, gallery): Δ0, needs 6 | **violation** (the co-fire) |
| `ilan` | 002 (120) → 006 (310) → 004 (318), all in `pump_vault` | no findings |
| `quiej` | 002 (120, vault) → 001 (300, gallery): Δ180, needs 6 | ok |
| | 001 (300, gallery) → 005 (318, gallery): Δ18, needs 0 | ok |

**Total FR-AUD-04 findings in the whole fixture: exactly two**, both `blocking`, on the pairs
`{001, 003}` and `{004, 005}`.

### Row 6 — invariant 7, at scene 003

`canon/lexicon.yaml` fixes four canonical terms. `lx_readkey`'s canonical form is `read-key`
and its forbidden variants are `readkey`, `read key`, `reader key`. The body of
`manuscript/003.md` contains `readkey` exactly once:

> Thirty years of co-op paper and not one line of it says where the readkey went.

Nothing else in either draft contains any forbidden variant of any of the four terms —
neither `coldsoak`, `cold-soak`, `soak-down`, `calve window`, `ice window`, `calving gap`,
`read key`, `reader key`, `pumpvault`, `pump-vault` nor `vault room`.

The canonical forms are safe to write freely: `read-key`, `cold soak`, `calving window` and
`the pump vault` contain no forbidden variant as a substring, so FR-AUD-05's case-insensitive
search is unambiguous. (`soak lock` and `the soak` are also safe — neither is a listed
variant.)

### Row 7 — invariant 8, at scene 005

The fixture's convention for `value_change`, followed by the other five scenes without
exception, is `"<value>: <from> → <to> (+)"` or `(-)`:

| Scene | `value_change` |
|---|---|
| 001 | `standing: tolerated → refused (-)` |
| 002 | `Ilan's usefulness to the co-op: certified → indemnified (-)` |
| 003 | `hope of a clean recovery: intact → spent (-)` |
| 004 | `truth between the siblings: withheld → spoken (+)` |
| 005 | **`authority over the vault`** ← non-empty, unsigned |
| 006 | `Vance's certainty about the core: guessed → known (+)` |

So FR-AUD-06 reduces to: the string is non-empty **and** contains `(+)` or `(-)`. Scene 005
passes the first test and fails the second, which is precisely the case the spec describes —
a scene that names a value without stating which way it moves.

### Row 8 — invariant 9, at scene 003

`cast/vance/voice.md` lists `never_says: ["trust me", "I'm sorry", "we'll be fine"]`. Scene
003's POV is vance, and FR-AUD-07 checks **the POV's list only**. The body of
`manuscript/003.md` contains, case-insensitively:

> "Trust me," she told the wire, and heard exactly how it sounded.

Neither of vance's other two entries appears in that draft, and none of ilan's three
(`I remember`, `obviously`, `it's fine`) appears in `manuscript/002.md` — whose POV is ilan,
so his is the list that matters there.

### Row 9 — invariant 10, at scenes 004 and 005

`th_surface_debt` is `developing`, appears at scenes `["001", "006"]` — listed in **discourse
order**, because latency is a reading-order distance — and tolerates a gap of 2.

| At scene | Discourse gap since the thread's last appearance | Verdict |
|---|---|---|
| 001 | 0 | clean |
| 002 | 1 | clean |
| 003 | 2 | clean — equal to `max_latency` is not over it |
| 004 | 3 | **reported**, `reviewable` |
| 005 | 4 | **reported**, `reviewable` |
| 006 | 0 | clean — the thread reappears here |

Two findings. Scene 006 is in the thread's list on purpose: it keeps the tempting scene free
of mechanical findings, and it is narratively true — the surface debt is what Vance is really
settling when she goes for the seal ring.

The second thread, `th_graft`, is `resolved`. FR-AUD-08's population is `planted` and
`developing` only, so a resolved thread is never late; and a resolved thread never enters a
context. Set beside `th_surface_debt`, the exclusion is testable: assemble any scene and one
thread is present, the other is not.

---

## Expected mechanical audit output, scene by scene

This is the table to read beside the real output.

| Scene | FR-AUD-01 (inv 1) | -02 (inv 2) | -03 (inv 4) | -04 (inv 5) | -05 (inv 7) | -06 (inv 8) | -07 (inv 9) | -08 (inv 10) |
|---|---|---|---|---|---|---|---|---|
| **001** | — | — | — | **blocking** *(pair with 003)* | — | — | — | — |
| **002** | — | — | — | — | — | — | — | — |
| **003** | — | — | — | **blocking** *(pair with 001)* | **blocking** | — | **reviewable** | — |
| **004** | **blocking** | **reviewable** | **blocking** *(pair with 005)* | **blocking** *(pair with 005)* | — | — | — | **reviewable** |
| **005** | — | **reviewable** | **blocking** *(pair with 004)* | **blocking** *(pair with 004)* | — | **reviewable** | — | **reviewable** |
| **006** | — | — | — | — | — | — | — | — |

Counted as distinct findings rather than per scene:

| Invariant | Findings | Severity | Where |
|---|---|---|---|
| 1 | 1 | `blocking` | 004 |
| 2 | 2 | `reviewable` | 004, 005 |
| 4 | 1 pair | `blocking` | {004, 005} |
| 5 | 2 pairs | `blocking` | {001, 003}, {004, 005} |
| 7 | 1 | `blocking` | 003 |
| 8 | 1 | `reviewable` | 005 |
| 9 | 1 | `reviewable` | 003 |
| 10 | 2 | `reviewable` | 004, 005 |

The two pairwise checks (FR-AUD-03 and FR-AUD-04) find a *pair* of scenes and report against
**both** members, so the same finding surfaces on two scenes. Whether the implementation
counts that as one finding or two is a reporting convention, not a disagreement about the
fixture — what matters is that the scenes and severities above are the ones named.

Scenes 001, 004, 005 and 006 carry **no draft**, so the two text checks (FR-AUD-05 and
FR-AUD-07) have nothing to read there and are silent for that reason rather than because the
prose is clean. Only 002 and 003 ship prose.

---

## The clean control scene — 002

**Scene 002 trips none of the eight mechanical checks.** It exists so that a silent checker
can be told from a broken one: a run that reports nothing on 002 *and* the table above on the
other five scenes is a run that works.

It is the analepsis — 180 hours before the sealing order, read second — and it carries
**Draft A**, `manuscript/002.md`, which is also the accepted draft the live extraction test
reads. Ilan has done his soak and is on the vault side with Quiej, who is there to witness.
He works along the cradle by feel for the read-key seating, which is not where the co-op's
paper puts it, finds it, and is folding back through the throat when it cycles on him and
takes the left hand. Quiej logs the indemnity while he is still on the deck of the lock, and
he signs it with the hand he has left.

The walk for each check, so a reviewer can confirm the silence is earned:

| Check | Why it is silent on 002 |
|---|---|
| FR-AUD-01 (inv 1) | The rows with `acquired_in: "002"` are ilan's two — he is the POV — and quiej's first, and she is a participant |
| FR-AUD-02 (inv 2) | The only open setup is `su_readkey`, due at scene 005 (hour 318); 318 > 120, so nothing is due. `su_graft` is paid and never reports |
| FR-AUD-03 (inv 4) | The characters present are ilan (120 / 310 / 318) and quiej (120 / 300 / 318); neither has two scenes at the same hour |
| FR-AUD-04 (inv 5) | The pairs involving 002 are ilan 002 → 006 (Δ190 within the vault, needs 0) and quiej 002 → 001 (Δ180, needs 6). Both pass |
| FR-AUD-05 (inv 7) | Draft A contains no forbidden variant of any of the four terms |
| FR-AUD-06 (inv 8) | `value_change` is `Ilan's usefulness to the co-op: certified → indemnified (-)` — signed |
| FR-AUD-07 (inv 9) | Draft A contains none of ilan's `never_says` strings (`I remember`, `obviously`, `it's fine`). He thinks about the past freely; he just never writes those literal strings |
| FR-AUD-08 (inv 10) | At discourse order 2 the gap since `th_surface_debt`'s scene 001 is 1, and `max_latency` is 2 |

Draft A also carries the fixture's **shipped negative example** for the semantic auditor: it
shows the *registered* body change actually happening, on the page, with its cause. A
semantic auditor reading scene 002 must **not** flag the crushed hand, because
`cast/ilan/changes.yaml` dates that change at scene 002. See the next section.

**Ilan's lungs stay unmodified here, and that is load-bearing.** Draft A has the rig loop
refuse him and has him decline it and go down on the hard line; he never takes a wet breath.
The first version of this draft had him force the loop, which quietly wrecked two acceptance
criteria at once: it put a live invariant-3 violation in the scene this section declares
clean (AC 15), and it handed the live writer of scene 006 an in-context precedent for putting
Ilan in the brine — three digests restated it, and `digests/901.md` loads into 006's context —
so the unregistered body change AC 26 expects the auditor to flag would have been a change the
context had already licensed. `immutable_physical.lungs` is unmodified in the dossier, has no
`ChangeEvent` anywhere, and is contradicted by no prose in the fixture. That is what makes it
available to be violated at 006.

---

## The tempting scene — 006

Scene 006 is the one a live model is asked to write, in the run that satisfies AC 26. It is
**mechanically clean** — zero findings from all eight checks, as the table above shows — so a
live turn can reach `merged` without fighting the record. Everything interesting about it is
semantic.

The temptation is built into the scene's **dramatic function**, never into an instruction.
`scenes/006.yaml` states what must change and what gets paid and leaves the *how* entirely
free, which is what the design asks a scene record to do. It just happens that the obvious
move is the forbidden one.

### Expected semantic finding 1 — invariant 6, an axiom violated

The scene pins the axiom `ax_brine_dark` through `tags: ["ax_brine_dark", "lx_vault"]`, so it
is prepended to the context and named in the turn's selected list. That list is the authority
on which axioms are in force, which is what makes checking invariant 6 against it possible at
all.

> **`ax_brine_dark`** — The vault's brine absorbs every wavelength a hand-lamp makes past
> four metres; below that only sound carries.

The scene's goal is that Vance be *certain* the seal ring on the Kestrel core is unbroken.
The conflict is that the ring is eleven metres out across open brine. `notes` says
"Everything she needs to know is at the far end of the vault, and the vault is eleven metres
long."

A writer reaching for the obvious move — what she sees across the water, a lamp beam finding
the ring, the ring catching the light — breaks the axiom in a single sentence. The obedient
moves exist too (swim to it and touch it; ping it and read the return; send Ilan's hands
instead), which is what makes this a temptation rather than a trap.

**Expected:** a violation with `invariant: 6`, `source: model`, and `evidence.quote` equal to
the sentence in which anything past four metres is seen.

### Expected semantic finding 2 — invariant 3, an unregistered body change

`cast/ilan/dossier.md` records, under `immutable_physical`:

> `lungs: unmodified; no perfluorocarbon tolerance and no certification to take a wet breath`

and `cast/ilan/changes.yaml` contains **no** `ChangeEvent` for `lungs` — its only entry is
the left hand. Scene 006's `entry_state` puts Ilan on the vault side with "his soak and his
graft hand and no dive rig", and its `exit_state` has him "at the cradle with her" — eleven
metres out across open brine.

The writer must therefore either invent a rig (contradicting `entry_state`), send only Vance
(contradicting `exit_state`), or put Ilan in the water (contradicting the lungs line).

**Expected:** a violation with `invariant: 3`, `source: model`, and `evidence.quote` equal to
the sentence in which Ilan goes under, swims, or breathes the brine. **This is the finding AC
26 requires the live auditor to raise.**

### Expected non-finding — invariant 3, the *registered* body change

`cast/ilan/changes.yaml` carries exactly one event:

```yaml
character: ilan
attribute: left_hand
from: "flesh; the hand he splices with"
to: "graft-steel prosthesis, five digits, no sensation below the wrist"
scene: "002"
cause: "the soak-lock throat cycled closed on it during the indemnity dive"
```

Scene 002 is at hour 120, before scene 006's 310, so the graft holds at 006 and prose showing
a **steel hand** on the throat latch or on the cradle is *correct*. The scene's `entry_state`
names the graft hand explicitly so it is certain to reach the page.

Meanwhile `immutable_physical.left_hand` still reads `flesh; the hand he splices with` —
that is the pre-change value the `ChangeEvent` moves off, and it is exactly what makes this
negative case non-trivial. **An auditor that compares prose to `immutable_physical` and stops
there will flag the graft hand. One that reads `changes.yaml` as it is told to will not.**

**AC 26 requires it NOT to be flagged.** A run that reports the graft hand has failed, even
if it also found the other two.

`manuscript/002.md` shows the crush itself, so a second, already-shipped negative example
exists for a fixture-level test that does not need a live model.

---

## The two invented facts

Prose invents constantly, and none of what it invents is canon at the moment it is written.
`extract_facts` reads the accepted draft and queues each invention in `ledger/proposed.yaml`,
where a human decides whether it becomes canon. AC 27 checks that the live extraction finds
the two inventions planted in Draft A.

Both are stated plainly in `manuscript/002.md`, and **neither is anywhere in canon.**

| | What the prose asserts | Expected `target_entity` | Expected `target_field` | Why it is not already canon |
|---|---|---|---|---|
| **F1** | The throat — the inner soak-lock door of the pump vault — releases only from the vault side | `pump_vault` | `geometry` | `canon/locations/pump_vault.md`'s `geometry` says the throat is the only door and nothing about which side releases it |
| **F2** | A cold soak may be cut to four hours on a co-op indemnity dive, which is why indemnity divers lose the lung lining first | `ax_cold_soak` | `exceptions` | `canon/axioms/ax_cold_soak.md` has `exceptions: []` — an empty list, so an extraction has nothing to collide with |

Those two absences are load-bearing. If `geometry` already mentioned the release side, or
`exceptions` already held the four-hour cut, AC 27 would have nothing to extract and the
result could not be told from a pre-existing record.

`ledger/proposed.yaml` ships with two entries, `pf_001` and `pf_002`, both deliberately about
something else (a competence of vance's, and a want of quiej's), for the same reason: a
reviewer must be able to tell a fresh extraction from a row that was already queued. Neither
carries `conflict: true`, so no turn on any scene starts blocked — in particular the live
turn on scene 006 starts cleanly.

Scene 006's record re-invites both facts without prescribing any prose — its `entry_state`
has the throat closed behind them, and its `notes` reads "What Ilan can do down here, he can
do because of what the co-op did to him once; what closed behind them opens only from this
side" — so the extraction can be run against a live draft of 006 as well as against Draft A.

---

## What else the fixture is shaped to test

Beyond the planted violations, several behaviours have a specific record placed here to make
them observable.

### Digests and the as-of rule — `manuscript/digests/`

Five digest files. A **scene** digest is filed under its own scene id, a **chapter** digest
under `90N`, and the **arc** digest under `990`; all match the three-digit path grammar, and
the truth about what each one covers lives in its `scene_ref` and `level`, not in its
filename. (Filing a chapter digest under its first scene's id was rejected: it would collide
with the scene digests and with the arc digest.)

| File | Level | Covers | `povs` | Why it is here |
|---|---|---|---|---|
| `002.md` | scene | 002 | `[ilan]` | Derived from Draft A |
| `003.md` | scene | 003 | `[vance]` | Derived from Draft B |
| `901.md` | chapter | 001–003 | `[vance, ilan]` | **`povs` excludes a later scene's POV.** quiej is the POV of scene 005 and is absent from this list, although she is a participant in 001 and 002. When 005 is assembled, every scene this digest covers is at hour 300, 120 and 302 — all ≤ 318 — so it loads, and it must be labelled as *events the POV did not witness* |
| `902.md` | chapter | 004–006 | `[vance, quiej]` | **Covers scenes later in story time than the tempting scene.** It covers 004 and 005 at hour 318, while scene 006 is at 310 — so when 006 is assembled at T = 310 this digest must **not** load, even though 006 is itself one of the scenes it covers. This is why 006 sits at 310 rather than at the end of the story axis |
| `990.md` | arc | 001–006 | `[vance, ilan, quiej]` | **Not indexed.** Only chapter-level digests become index rows, so this must never be returned by a ranking. A test that finds it in one has found a bug |

`901.md` and `902.md` are the only two digests that are indexed for retrieval.

### Closed things leave the working tier

Three exclusions, each with a live counterpart so the difference is a difference and not an
absence:

| Closed, must be absent from an assembled context | Open, must be present |
|---|---|
| `su_graft` — paid in 004, `resolution: paid` | `su_readkey` — open, offered under a *may collect* label |
| `th_graft` — `state: resolved` | `th_surface_debt` — `state: developing` |
| `vi_001` — has a `resolution` | `vi_002` — `resolution: null` |

A test that assembles scene 003 or 006 and finds `vi_002` present and `vi_001` absent has
proved the rule.

### The two prior violation reports — `ledger/violations.yaml`

The file ships with a short history, because a store that has never been audited cannot
demonstrate exclusion.

**`vi_001` — resolved.** Scene 002, invariant 6, `source: model`, `severity: reviewable`,
`resolution: accept_with_reason`. The story behind it is real and ties the fixture together:
the semantic auditor once read Draft A's four-hour line as contradicting `ax_cold_soak`,
whose `exceptions` list is empty, and a human — acting as the auditor with `X-Actor: human` —
accepted it with a reason, because the indemnity cut is an exception the canon has not
recorded yet. That is precisely what invented fact **F2** proposes.

It is deliberately `source: model` on invariant **6**, neither of which any mechanical check
produces, so it cannot be confused with live audit output and does not disturb scene 002's
status as the clean control. **The mechanical audit of 002 is still empty.**

**`vi_002` — open.** Scene 003, invariant 7, `source: mechanical`, `severity: blocking`,
`resolution: null`, evidence `readkey`. It is the same finding the mechanical audit will
report for planted row 6, written down as a prior report, so the fixture is self-consistent
rather than contradicting its own checker. Because it is unresolved it stays in the working
tier and *does* enter a context.

### Selection and assembly

The scene records' dramatic fields (`goal`, `conflict`, `value_change`, `entry_state`,
`exit_state`, `notes`) are what the ranking embeds, so they are written to be specific.
`tags` are the architect's pin: an axiom or lexicon entry tagged on a record enters the
context regardless of ranking. Scene 006 pins `ax_brine_dark`, which is the precondition for
checking invariant 6 against it at all.

---

## Switching the embedding model for Spanish prose

This fixture's prose is English, so the default embedder is the right one for it. If the
prose is written in Spanish — or in any language the English-only default handles badly — the
switch is **one line** in `backend/.env`:

```
EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

The default is `sentence-transformers/all-MiniLM-L6-v2`, with `BAAI/bge-small-en-v1.5` as the
automatic fallback if the primary cannot be loaded. **All three are 384-dimensional**, which
is the whole reason the switch is one line: the vector table's dimension never changes, so no
migration and no schema change is involved.

Two consequences to expect:

1. The active model is recorded as index metadata. Changing `EMBED_MODEL` makes the recorded
   value disagree with the configured one, which **forces a rebuild** — vectors from two
   different models must never sit in one table. Run `POST /index/rebuild` after the switch.
2. `/health` reports the model actually in use, which is the fastest way to confirm the switch
   took effect rather than silently falling back.

Nothing else in the fixture or in the backend depends on the prose language. Role prompts are
written in English regardless; the language the *prose* is written in is read from
`canon/style.md`.

---

## Conventions this fixture follows

Stated so that a divergence is visible as a divergence rather than read as a variant.

- Every **file** carries `schema_version: 1` on its first line.
- A YAML file holding a list wraps it under a named key — `setups:`, `threads:`, `knowledge:`,
  `changes:`, `relationships:`, `terms:`, `arcs:`, `chapters:`, `proposed:`, `violations:` —
  never a bare top-level list, because the version has to live somewhere.
- A `.md` store file is YAML frontmatter plus a body, and the body *is* the prose the model
  reads.
- Entity ids match `^[a-z0-9][a-z0-9_-]*$`; scene ids are exactly three digits and are always
  **quoted** in YAML, so `005` is not read as the integer 5.
- `story_time` is an integer count of hours since `epoch_zero`. Integers are strict and
  unquoted: never `true` where a number belongs, never `"6"` where `6` belongs.
- `ChangeEvent` and `Relationship` use the YAML keys `from` and `to`.
- Enum values are written bare — `paid`, `resolved`, `blocking`, `mechanical` — never quoted
  and never as booleans.
- `value_change` is `"<value>: <from> → <to> (+)"` or `(-)`, with scene 005 as the single
  deliberate exception.
- Thread and digest scene lists are in **discourse** order; `story_axis` in
  `ledger/timeline.yaml` is in **story** order. The two are different orders and the file says
  which is which.
