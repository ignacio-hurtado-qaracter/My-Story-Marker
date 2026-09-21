# Definitions

The domain vocabulary of the novel-writing harness. Every entity the system reasons
about, what it means in narrative terms, the fields that make it queryable, and the
failure mode it produces when modelled badly.

This document is **descriptive, not operational**. It says what things *are*. How they
are assembled, stored, audited and written to is in [`architecture.md`](./architecture.md).
Visual maps of how these entities relate are in [`domain-knowledge.md`](./domain-knowledge.md).

---

## The layered model

The ontology has four layers, ordered by rate of change.

| Layer | Name | Changes | Covered here |
|---|---|---|---|
| L0 | Project | Never, after planning | Yes |
| L1 | World | Slowly, additively | Yes |
| L2 | Cast | Per scene, in knowledge and relationships | Yes |
| L3 | Narrative structure | Per revision pass | Yes |
| L4 | Text | Constantly | No — see `architecture.md` |

L0–L3 are **canon**: small, curated, authoritative. L4 is the prose and the working
artifacts the system produces around it, which are large, disposable and subordinate.
The split is deliberate and it is the single most important idea in the model. Canon is
what the novel *is*; text is what the novel *currently reads like*.

Identifiers are stable forever. Renaming an entity breaks every edge that points at it.

---

## Layer 0 — Project

Invariable for the whole book. This layer is present in every call without filtering, so
if it does not fit in roughly 800 tokens it is written badly.

### Premise

The dramatic question of the book in a single sentence, with protagonist, desire and
obstacle. It is not a summary. It is the test for deciding whether a scene belongs to
*this* novel rather than some adjacent one.

| Field | Meaning |
|---|---|
| `statement` | One sentence, no chained subordinate clauses |
| `dramatic_question` | What the reader wants to know |
| `answer` | How it resolves; decided before writing starts |

**Failure mode.** A three-paragraph premise. It stops working as a filter, and the
writer ignores it.

### ThematicThesis

What the novel *argues*, not what it is about. Expressed as an arguable proposition plus
its counterargument embodied in a character who is allowed to win sometimes.

| Field | Meaning |
|---|---|
| `proposition` | "Inherited memory is a form of servitude" |
| `antithesis` | Who defends the opposite, and how strongly |
| `test_scenes` | Where the thesis is put under real pressure |

**Failure mode.** Confusing thesis with theme. "Identity" is not a thesis — you cannot
disagree with it, so it orders nothing.

### GenreContract

The explicit promises made to the reader and how they will be paid. Fixes the level of
scientific rigour, whether the mystery resolves, whether the ending admits ambiguity, and
how much violence or intimacy happens on the page rather than off it.

| Field | Meaning |
|---|---|
| `subgenre` | Hard SF, space opera, social SF… |
| `rigour` | What may be hand-waved and what may not |
| `promises[]` | Each with its intended payoff scene |
| `limits` | What this novel will never do |

**Failure mode.** Leaving it undeclared. The prose drifts from thriller to space opera
and nothing detects it, because no rule forbids it.

### StyleBible

Rules governing the textual surface. The cheapest layer to maintain and the one that
prevents the most drift, because readers notice inconsistency of voice long before
inconsistency of plot.

| Field | Meaning |
|---|---|
| `tense` | Past or present; never mixed without cause |
| `pov_policy` | Third limited, one per scene, no internal head-hopping |
| `register` | Lexical density, jargon tolerance, narrative distance |
| `metrics` | Target mean sentence length and variance |
| `forbidden[]` | Tics, verbal crutches, images already spent in this book |
| `exposition_policy` | How much backstory per scene, and through which vehicle |

**Failure mode.** Writing it abstractly. It works far better with two or three paragraphs
of canonical sample prose the writer can imitate directly.

---

## Layer 1 — World

Stable canon, loaded by **scope**: only entries whose tags intersect the current scene's
tags enter context. This is the layer that grows most, so its indexing determines whether
the model still holds together at chapter forty.

### Axiom

A physical, biological or social rule of the universe that the prose may not violate. In
science fiction this is the highest-leverage entity in the whole ontology. **An axiom with
no declared consequences is the origin of most plot holes** — the rule gets stated once,
nobody derives what it forbids, and three hundred pages later something impossible happens
without anyone noticing.

| Field | Meaning |
|---|---|
| `statement` | The rule, phrased positively |
| `scope[]` | Domain tags that trigger loading |
| `consequences[]` | What necessarily follows; what becomes impossible |
| `exceptions[]` | Closed and numbered, or they are not exceptions |
| `cost` | What it costs to use this; conflict comes from here |

**Failure mode.** Declaring the capability and forgetting the limit. An axiom that only
permits things drains the tension from every scene it touches.

### Technology

An artifact or system with capabilities **and operating limits**. Derives from one or
more axioms and inherits their restrictions.

| Field | Meaning |
|---|---|
| `derives_from[]` | Axioms that license it |
| `can` | Capabilities, with magnitudes |
| `cannot` | The field that actually matters |
| `failure_mode` | How it breaks and what happens then |
| `who_has_it` | Factions with access, and since when |
| `sensory` | How it sounds, smells and feels in use |

**Failure mode.** No sensory field. The writer improvises the texture each time, and the
ship sounds different in every chapter.

### Faction

Any collective agent with interests of its own: state, corporation, cult, crew. Exists so
that pressure on the characters has an origin and a direction.

| Field | Meaning |
|---|---|
| `wants` | Stated goal and actual goal |
| `resources` | What it can mobilise, and how fast |
| `stance[]` | Relation to other factions, dated |
| `register` | How its members speak; feeds the lexicon |

**Failure mode.** Monolithic factions. With no internal dissenting fraction they generate
no scenes, only geopolitical scenery.

### Location

A hierarchical place — system → body → settlement → enclosure — from which context is
inherited downward. Loading a cabin implies loading its ship and its orbit.

| Field | Meaning |
|---|---|
| `parent` | Reference to the level above |
| `sensory_palette` | Light, sound, smell, gravity, temperature |
| `geometry` | What constrains blocking: exits, heights, cover, sightlines |
| `access[]` | Where you can arrive from, and how long it takes |

**Failure mode.** No explicit geometry. Two scenes set in the same room end up with
incompatible floor plans.

### CanonicalTerm

Every neologism, proper noun and piece of jargon in its exact form. A large source of
drift and, at the same time, the cheapest to eliminate: it reduces to string comparison.

| Field | Meaning |
|---|---|
| `canonical_form` | The single definitive spelling |
| `plural` / `gender` | Decided in advance, not improvised |
| `forbidden_variants[]` | What the checker searches for |
| `used_by[]` | Characters and factions; nobody else says it |
| `pronunciation` | Keeps the cadence stable when read aloud |

**Failure mode.** Registering the term but not the set of wrong forms. Without those
there is no automatic check possible.

### TemporalSystem

Calendars, time zones, transit durations and, where applicable, relativistic dilation.
Turns "it took weeks" into a verifiable quantity.

| Field | Meaning |
|---|---|
| `epoch_zero` | The absolute origin everything is dated against |
| `calendars[]` | One per culture, with conversions between them |
| `transit_matrix` | Minimum travel time between pairs of locations |
| `dilation_factor` | Offset between proper time and coordinate time |

**Failure mode.** Skipping the transit matrix. Characters get teleported and nobody can
prove it.

### HistoricalEvent

A fact predating page one. Distinguished from a scene beat by the fact that nobody
witnesses it on the page: it is only remembered, argued about, or lied about.

| Field | Meaning |
|---|---|
| `date` | In epoch zero |
| `official_version` | What is said in public |
| `actual_version` | What happened; may never be revealed |
| `who_knows_what` | Links to KnowledgeState |

**Failure mode.** A single version. Without the gap between official and actual, the past
generates no plot.

---

## Layer 2 — Cast

A character dossier is never loaded whole. It is trimmed to the moment of the scene.

### Character

Identity, body and internal architecture. The *wants / needs / lies* structure is not
psychological decoration: it determines which choice the character makes at each fork,
which is precisely what the writer has to resolve on the page.

| Field | Meaning |
|---|---|
| `immutable_physical` | Does not change without a registered ChangeEvent |
| `wants` | The conscious goal pursued in scenes |
| `needs` | What is actually missing; usually contradicts `wants` |
| `lies` | The false belief about the self that sustains the arc |
| `arc[]` | Successive states, each anchored to a specific scene |
| `competences` | What they can do; bounds what they can solve |

**Failure mode.** An arc written as a prose summary. Without scene anchors you cannot
answer "where is she at chapter 19?".

### VoiceProfile

Kept separate from the dossier because it is consulted at a different moment: when
writing dialogue, and when auditing style. It is defined mostly **by negation**.

| Field | Meaning |
|---|---|
| `own_lexicon[]` | Words only this person uses |
| `syntax` | Long or clipped; subordination; ellipsis |
| `never_says[]` | The most useful field in the whole record |
| `under_pressure` | How the voice degrades when control is lost |
| `sample` | Six canonical lines of dialogue to imitate |

**Failure mode.** Describing voice with adjectives — "ironic, dry" — instead of samples.
Adjectives are not imitable.

### KnowledgeState

What each character knows and **from which exact scene**. This is the highest-value entity
in the system: most serious continuity errors in a long novel are characters who know
something they could not yet have learned.

| Field | Meaning |
|---|---|
| `character` | Whose knowledge this is |
| `fact_ref` | Points at a canon entity |
| `acquired_in` | Scene id; before that, they are unaware |
| `via` | Witnessed, was told, deduced, suspects |
| `certainty` | `unaware` · `suspects` · `believes` · `knows` · `believes_falsely` |
| `may_tell[]` | Social constraints on disclosure |

**Failure mode.** Modelling it as a boolean. Without `believes_falsely` you cannot write
deception or dramatic irony at all.

### Relationship

A directed edge between two characters, with valence that changes over time. Directed,
because A can trust B while B despises A, and that asymmetry is dramatic material.

| Field | Meaning |
|---|---|
| `from` / `to` | Directed; never symmetric by default |
| `valence[]` | Dated series per scene, −3 to +3 |
| `shared_history` | Events both remember, possibly differently |
| `unspoken` | What is between them and never gets said |

**Failure mode.** Valence as a single value. Without the time series there is no queryable
evolution, and relationships flatten.

---

## Layer 3 — Narrative structure

The bridge between canon and prose. This is where the plan lives.

### Arc · Act · Sequence · Chapter

Nested containers that contribute exactly three things: **word budget, dramatic function,
and position on the tension curve**. They contain no prose.

| Field | Meaning |
|---|---|
| `function` | What must have changed by the end of it |
| `budget` | Words assigned; controls global pacing |
| `target_tension` | 0–10, on entry and on exit |
| `active_threads[]` | Which plots advance here |

**Failure mode.** Not budgeting. Act two eats eighty per cent of the book and the climax
arrives compressed.

### Scene

The atomic unit of writing and the only unit of context. The entire harness exists to
answer one question: *what must be placed in front of the writer to produce this scene and
no other?*

| Field | Meaning |
|---|---|
| `id` | `NNN`, stable forever |
| `pov` | A single character; determines the knowledge trim |
| `story_time` | When it happens in the world |
| `discourse_order` | Where the reader encounters it |
| `location` | A leaf of the location tree |
| `goal` | What the POV wants on entering |
| `conflict` | What prevents it |
| `outcome` | `yes` · `no` · `yes-but` · `no-and-furthermore` |
| `value_change` | Which value moves, and in which direction |
| `entry_state` / `exit_state` | Verifiable delta to the world |
| `tags[]` | What triggers loading of axioms and lexicon |
| `budget` | Assigned words |

**Failure mode.** Specifying the *how* as well as the *what*. An over-prescriptive scene
record produces dead prose: the writer writes to satisfy the record rather than to write
well. Scene records specify dramatic function and leave execution free.

### PlotThread

A plot running across non-contiguous chapters. Exists so you can ask "how long since we
touched the sister subplot?" and get a number.

| Field | Meaning |
|---|---|
| `state` | `planted` · `developing` · `dormant` · `resolved` · `abandoned` |
| `scenes[]` | Where it advances, in discourse order |
| `max_latency` | How many scenes it can vanish for before the reader loses it |
| `depends_on[]` | Threads that must resolve first |

**Failure mode.** No maximum latency. Secondary threads evaporate and nobody notices until
the final read-through.

### Setup · Payoff

Explicit pairs carrying an open obligation — the Chekhov ledger. Every setup is a debt
incurred with the reader and must be closed by a payoff or by a *declared* abandonment
before the end.

| Field | Meaning |
|---|---|
| `planted_in` | Scene where it appears |
| `promise` | What the reader now expects |
| `paid_in` | Scene; empty while it remains open |
| `due_by` | Latest scene at which it can still be collected |
| `resolution` | `paid` · `subverted` · `deliberately_abandoned` |

**Failure mode.** Not distinguishing deliberate abandonment from forgetting. Without that
mark the checker produces noise, and noisy checkers get ignored.

### TemporalAxes

Two separate axes that must never be merged. **Story time** is when events happen.
**Discourse time** is the order in which the reader receives them. Consistency is verified
against the first; tension is designed on the second.

| Field | Meaning |
|---|---|
| `story_axis` | Causal order; all invariants run over this |
| `discourse_axis` | Reading order; admits jumps, ellipsis, analepsis |
| `mapping` | Correspondence between the two, scene by scene |

**Failure mode.** A single axis. The moment the first flashback or the first relativistic
ship appears, nothing can be validated any more.

---

## Domain invariants

These are properties of a coherent novel, stated so that they can be checked
mechanically. They are domain rules, not system machinery; the mechanism that runs them
is described in `architecture.md`. All of them evaluate against the **story-time** axis.

1. **Knowledge monotonicity.** Nobody references information whose `acquired_in` is later
   than the current scene, except under an explicit state of deception, deduction or
   memory loss.
2. **Closed debts.** Every setup has a payoff or a declared abandonment before the book ends.
3. **Stable bodies.** `immutable_physical` attributes do not change without a registered
   ChangeEvent.
4. **Spatial uniqueness.** No character occupies two locations at the same `story_time`.
5. **Possible transits.** Every movement respects the `transit_matrix`.
6. **Axiomatic respect.** No scene violates an axiom whose `scope` intersects its `tags`.
7. **Canonical lexicon.** Zero occurrences of any `forbidden_variants` in the manuscript.
8. **No inert scenes.** Every scene declares a signed `value_change`, and the prose delivers it.
9. **Recognisable voice.** No dialogue contains material marked `never_says` for that speaker.
10. **Thread latency.** No active thread exceeds its `max_latency` without reappearing.

---

## What is deliberately not here

The **Text layer (L4)** — drafts, proposed facts, violation reports — is not part of the
domain vocabulary. Those are working artifacts of the writing system rather than facts
about the fictional world, and they are defined in `architecture.md` alongside the
operations, agent roles and storage layout that produce them.
