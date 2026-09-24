# Live runs (spec 001, AC 26 and AC 27)

Written by `tests/live/`; newest last.

## AC 27 - live extraction on Draft A -- 2026-09-24 08:45 UTC

- Extraction on scene 002 (Draft A): 6 fact(s), model `claude-haiku-4-5`, estimate 11066, input 9, cache read 0, over_cap False

| Hand-labelled fact | Target | Found |
|---|---|---|
| F1 | `pump_vault`.`geometry` | **NO** |
| F2 | `ax_cold_soak`.`exceptions` | **NO** |

Every fact returned:
- `ilan`.`perfluorocarbon_tolerance`: "No"
- `ilan`.`left_hand_status`: "Lost in throat door"
- `pump_vault`.`read_key_seating`: "Two fingers lower than drawing, turned out of true"
- `pump_vault`.`throat_cycle`: "Controlled by board; diver can request hold but cannot enforce it"
- `pump_vault`.`throat_release_location`: "Out in the brine behind a diver already through"
- `hard_line`.`method`: "Hood and hose breathing apparatus using gallery air; for divers without perfluorocarbon tolerance"

## AC 26 - live turn on the tempting scene -- 2026-09-24 08:54 UTC

- Turn `006-1` on scene 006: outcome **merged**
- Draft (stays in the run's private store copy, NFR-10): `C:\Users\student\AppData\Local\Temp\pytest-of-student\pytest-612\test_a_live_turn_on_the_tempti0\story\manuscript\006.md`
- Words 1203 against a budget of 1200
- Revisions: 0; revise rejections: 0

| Check | Result |
|---|---|
| `ax_brine_dark` in the selected list | yes |
| Axiom violation flagged (inv 6, model) | yes |
| Unregistered body change flagged (inv 3, model, not the hand) | **NO** |
| Registered change (the graft hand) NOT flagged | yes |
| Outcome merged or awaiting_ruling | yes |
| Every call reports a real model id | yes |
| Every estimate <= 100k and real - 2500 <= 100k | yes |

| Step | Role | Model id | Estimate | Input | Cache read | Output | over_cap |
|---|---|---|---|---|---|---|---|
| write | writer | claude-haiku-4-5 | 13008 | 9 | 0 | 20228 | False |
| audit | auditor | claude-haiku-4-5 | 7099 | 9 | 0 | 16383 | False |
| polish | style_editor | claude-haiku-4-5 | 4190 | 9 | 0 | 12335 | False |
| digest | writer | claude-haiku-4-5 | 3414 | 9 | 0 | 1380 | False |
| extract | canoniser | claude-haiku-4-5 | 11529 | 9 | 0 | 8196 | False |

Model findings on scene 006:
- inv 6, reviewable: "the last calving window, the last seventy hours before the co-op's sealing order closed the vault forever"

A missing invariant 6 or 3 finding is a miss only if the draft contains the breach: an obedient writer leaves nothing to flag. Read the draft above to tell which.

## AC 26 - live audit of a planted draft (the auditor's half) -- 2026-09-24 09:37 UTC

- Scene 006, hand-authored draft written under the writer; draft at `C:\Users\student\AppData\Local\Temp\pytest-of-student\pytest-649\test_a_live_audit_catches_the_0\story\manuscript\006.md`
- Selected axioms: pinned ax_brine_dark; ranked ax_cold_soak, ax_indemnity_burn, ax_calving_window; `ax_brine_dark` pinned: yes
- Semantic half ran
- Model `claude-haiku-4-5`, estimate 5716, input 9, cache creation 8394, cache read 0, output 17645, over_cap False
- Adjusted finding 1 (inv 3): relocated, offset 555 moved to 550

| Planted | Finding wanted | Findings hitting it | Result |
|---|---|---|---|
| (a) seeing past four metres | inv 6 | 1 | yes |
| (b) rigless swim, breathing brine | inv 3 | 1 | yes |
| (c) registered graft hand | no inv 3 | 0 | yes |

Every model finding, as the model returned it:
- inv 6, blocking: "From the ledge she raised her lamp and saw the seal ring plainly across the open water, eleven metres out, every bolt on it lit and whole." -- ax_brine_dark: The vault's brine absorbs all light wavelengths past four metres. Vance cannot see the ring at eleven metres; the axiom permits sight only when a lamp is held against a surface, which is not the case here. [hits: (a) seeing past four metres]
- inv 3, blocking: "Halfway across he opened his mouth and drew the brine deep into his chest, breathing it as easily as the gallery air behind the throat." -- Ilan's lungs are unmodified with no perfluorocarbon tolerance and no certification to take a wet breath. He cannot breathe brine. The prose assigns him a physiological capability his body rules out. [hits: (b) rigless swim, breathing brine]

## AC 27 - live extraction on Draft A -- 2026-09-24 09:39 UTC

- Extraction on scene 002 (Draft A): 2 fact(s), model `claude-haiku-4-5`, estimate 12990, input 9, cache creation 13865, cache read 0, over_cap False

| Hand-labelled fact | Target | Found |
|---|---|---|
| F1 | `pump_vault`.`geometry` | yes |
| F2 | `ax_cold_soak`.`exceptions` | **NO** |

Every fact returned:
- `pump_vault`.`geometry`: "The throat's sole release is located in the vault's brine, behind a diver who has exited, and can only be accessed from within the vault."
- `pump_vault`.`geometry`: "The read-key seating is installed two fingers lower than the documented drawing and is turned out of true."

## AC 26 - live turn on the tempting scene -- 2026-09-24 09:50 UTC

- Turn `006-1` on scene 006: outcome **awaiting_ruling**
- Draft (stays in the run's private store copy, NFR-10): `C:\Users\student\AppData\Local\Temp\pytest-of-student\pytest-649\test_a_live_turn_on_the_tempti0\story\manuscript\006.md`
- Words 1266 against a budget of 1200
- Revisions: 0; revise rejections: 0

| Check | Result |
|---|---|
| `ax_brine_dark` in the selected list | yes |
| Invariant-6 model findings (a count to judge against the draft; not asserted) | 0 |
| Unregistered body change flagged (inv 3, model, not the hand) | yes |
| Registered change (the graft hand) NOT flagged | yes |
| Outcome merged or awaiting_ruling | yes |
| Every call reports a real model id | yes |
| Every estimate <= 100k and real - 2500 <= 100k | yes |

| Step | Role | Model id | Estimate | Input | Cache creation | Cache read | Output | over_cap |
|---|---|---|---|---|---|---|---|---|
| write | writer | claude-haiku-4-5 | 13008 | 17 | 30380 | 14656 | 17609 | False |
| audit | auditor | claude-haiku-4-5 | 7616 | 9 | 9764 | 0 | 19229 | False |
| polish | style_editor | claude-haiku-4-5 | 4325 | 9 | 5943 | 0 | 12227 | False |
| digest | writer | claude-haiku-4-5 | 3579 | 9 | 5336 | 0 | 2191 | False |
| extract | canoniser | claude-haiku-4-5 | 13618 | 9 | 14321 | 0 | 9253 | False |

Model findings on scene 006:
- inv 3, reviewable: "he was feeling the work the way a splicer feels a line and knows whether it will hold, whether the knot is sound, whether the thing will stand"

A missing invariant 6 or 3 finding is a miss only if the draft contains the breach: an obedient writer leaves nothing to flag. Read the draft above to tell which.

## AC 26 - live audit of a planted draft (the auditor's half) -- 2026-09-24 10:24 UTC

- Scene 006, hand-authored draft written under the writer; draft at `C:\Users\student\AppData\Local\Temp\pytest-of-student\pytest-655\test_a_live_audit_catches_the_0\story\manuscript\006.md`
- Selected axioms: pinned ax_brine_dark; ranked ax_cold_soak, ax_indemnity_burn, ax_calving_window; `ax_brine_dark` pinned: yes
- Semantic half ran
- Model `claude-haiku-4-5`, estimate 6188, input 9, cache creation 8724, cache read 0, output 17940, over_cap False

| Planted | Finding wanted | Findings hitting it | Result |
|---|---|---|---|
| (a) seeing past four metres | inv 6 | 1 | yes |
| (b) rigless swim, breathing brine | inv 3 | 1 | yes |
| (c) registered graft hand | no inv 3 | 0 | yes |

Every model finding, as the model returned it:
- inv 6, blocking: "From the ledge she raised her lamp and saw the seal ring plainly across the open water, eleven metres out, every bolt on it lit and whole." -- ax_brine_dark states that brine absorbs every wavelength of a hand-lamp past four metres and that 'nothing in the vault is identified by sight at distance.' The passage shows Vance seeing the seal ring plainly at eleven metres with her lamp, which directly contradicts this axiom's core statement about the brine's light-absorption properties. [hits: (a) seeing past four metres]
- inv 3, blocking: "Halfway across he opened his mouth and drew the brine deep into his chest, breathing it as easily as the gallery air behind the throat." -- Ilan's recorded physical attributes state his lungs are 'unmodified; no perfluorocarbon tolerance and no certification to take a wet breath.' The prose shows him breathing brine—an action his unmodified lungs cannot perform, as no human body without modification can extract oxygen from saltwater. This capability is ruled out by his recorded attributes. [hits: (b) rigless swim, breathing brine]

## AC 27 - live extraction on Draft A -- 2026-09-24 10:26 UTC

- Extraction on scene 002 (Draft A): 5 fact(s), model `claude-haiku-4-5`, estimate 13909, input 9, cache creation 14504, cache read 0, over_cap False

| Hand-labelled fact | Target | Found |
|---|---|---|
| F1 | `pump_vault`.`geometry` | yes |
| F2 | `ax_cold_soak`.`exceptions` | yes |

Every fact returned:
- `ax_cold_soak`.`exceptions`: "A cold soak may be cut to four hours on a co-op indemnity dive"
- `pump_vault`.`geometry`: "The throat runs on a cycle set by the board two hundred metres up the gallery; a diver on the wire may ask for it to be held and may not hold it himself"
- `pump_vault`.`geometry`: "The throat releases from the vault side only; there is no release on the gallery side"
- `pump_vault`.`geometry`: "The read-key seating sits two fingers lower than the drawing specification and turned out of true"
- `ilan`.`immutable_physical`: "left_hand: lost"

Addresses promotion could not write: 0 in the first answer (retried once), 0 still after the retry (not kept):

## AC 26 - live turn on the tempting scene -- 2026-09-24 10:46 UTC

- Turn `006-1` on scene 006: outcome **escalated**, escalated at `audit` (revision_bound: 1 blocking violation(s) still open after 3 revisions (FR-TURN-02): model-006-i03-f759ee946a7a)
- Draft (stays in the run's private store copy, NFR-10): `C:\Users\student\AppData\Local\Temp\pytest-of-student\pytest-655\test_a_live_turn_on_the_tempti0\story\manuscript\006.md`
- Words 1286 against a budget of 1200
- Revisions: 3; revise rejections: 0

| Check | Result |
|---|---|
| `ax_brine_dark` in the selected list | yes |
| Invariant-6 model findings (a count to judge against the draft; not asserted) | 0 |
| Unregistered body change flagged (inv 3, model, not the hand) | yes |
| Registered change (the graft hand) NOT flagged | yes |
| Outcome merged or awaiting_ruling | **NO** |
| Every call reports a real model id | yes |
| Every estimate <= 100k and real - 2500 <= 100k | yes |

| Step | Role | Model id | Estimate | Input | Cache creation | Cache read | Output | over_cap |
|---|---|---|---|---|---|---|---|---|
| write | writer | claude-haiku-4-5 | 13707 | 9 | 15198 | 0 | 17480 | False |
| audit | auditor | claude-haiku-4-5 | 8129 | 9 | 10109 | 0 | 27031 | False |
| revise | writer | claude-haiku-4-5 | 15177 | 9 | 15609 | 0 | 5990 | False |
| audit | auditor | claude-haiku-4-5 | 8133 | 9 | 10112 | 0 | 22555 | False |
| revise | writer | claude-haiku-4-5 | 15161 | 9 | 15601 | 0 | 2952 | False |
| audit | auditor | claude-haiku-4-5 | 8124 | 9 | 10106 | 0 | 18492 | False |
| revise | writer | claude-haiku-4-5 | 15142 | 9 | 15580 | 0 | 3872 | False |
| audit | auditor | claude-haiku-4-5 | 8114 | 9 | 10103 | 0 | 15275 | False |

Model findings on scene 006:
- inv 3, blocking: "Ilan was behind her—she couldn't see him, the water had eaten the light from her lamp at the threshold line, but she could hear him. The sharp inhale-hold."

A missing invariant 6 or 3 finding is a miss only if the draft contains the breach: an obedient writer leaves nothing to flag. Read the draft above to tell which.

## AC 26 - live audit of a planted draft (the auditor's half) -- 2026-09-24 12:34 UTC

- Scene 006, hand-authored draft written under the writer; draft at `C:\Users\student\AppData\Local\Temp\pytest-of-student\pytest-710\test_a_live_audit_catches_the_0\story\manuscript\006.md`
- Selected axioms: pinned ax_brine_dark; ranked ax_cold_soak, ax_indemnity_burn, ax_calving_window; `ax_brine_dark` pinned: yes
- Semantic half ran
- Model `claude-haiku-4-5`, estimate 6473, input 17, cache creation 22033, cache read 8927, output 13618, over_cap False
- Adjusted finding 0 (inv 6): relocated, offset 208 moved to 210
- Adjusted finding 1 (inv 3): relocated, offset 553 moved to 550

| Planted | Finding wanted | Findings hitting it | Result |
|---|---|---|---|
| (a) seeing past four metres | inv 6 | 1 | yes |
| (b) rigless swim, breathing brine | inv 3 | 1 | yes |
| (c) registered graft hand | no inv 3 | 0 | yes |

Every model finding, as the model returned it:
- inv 6, blocking: "From the ledge she raised her lamp and saw the seal ring plainly across the open water, eleven metres out, every bolt on it lit and whole." -- Axiom ax_brine_dark states that the vault's brine absorbs every wavelength a hand-lamp makes past four metres, and that nothing beyond that distance is identified by sight. The seal ring at eleven metres cannot be seen by Vance's lamp. The prose contradicts this by showing her seeing the ring plainly with every bolt illuminated and whole. [hits: (a) seeing past four metres]
- inv 3, blocking: "Halfway across he opened his mouth and drew the brine deep into his chest, breathing it as easily as the gallery air behind the throat." -- Ilan's physical attributes record states his lungs are unmodified with no perfluorocarbon tolerance and no certification to take a wet breath. The prose shows him breathing the brine as easily as air, an action his body cannot perform. His unmodified lungs lack any capability to breathe liquid. [hits: (b) rigless swim, breathing brine]

## AC 27 - live extraction on Draft A -- 2026-09-24 12:35 UTC

- Extraction on scene 002 (Draft A): 2 fact(s), model `claude-haiku-4-5`, estimate 13909, input 9, cache creation 14505, cache read 0, over_cap False

| Hand-labelled fact | Target | Found |
|---|---|---|
| F1 | `pump_vault`.`geometry` | **NO** |
| F2 | `ax_cold_soak`.`exceptions` | yes |

Every fact returned:
- `ax_cold_soak`.`exceptions`: "Cold soak may be reduced to four hours on a co-op indemnity dive"
- `ilan`.`immutable_physical`: "left_hand: absent"

Addresses promotion could not write: 0 in the first answer (retried once), 0 still after the retry (not kept):

## AC 26 - live turn on the tempting scene -- 2026-09-24 12:43 UTC

- Turn `006-1` on scene 006: outcome **awaiting_ruling**
- Draft (stays in the run's private store copy, NFR-10): `C:\Users\student\AppData\Local\Temp\pytest-of-student\pytest-709\test_a_live_turn_on_the_tempti0\story\manuscript\006.md`
- Words 964 against a budget of 1200
- Revisions: 0; revise rejections: 0

| Check | Result |
|---|---|
| `ax_brine_dark` in the selected list | yes |
| Invariant-6 model findings (a count to judge against the draft; not asserted) | 0 |
| Unregistered body change flagged (inv 3, model, not the hand) | **NO** |
| Registered change (the graft hand) NOT flagged | yes |
| Outcome merged or awaiting_ruling | yes |
| Every call reports a real model id | yes |
| Every estimate <= 100k and real - 2500 <= 100k | yes |

| Step | Role | Model id | Estimate | Input | Cache creation | Cache read | Output | over_cap |
|---|---|---|---|---|---|---|---|---|
| write | writer | claude-haiku-4-5 | 14091 | 9 | 15442 | 0 | 16405 | False |
| audit | auditor | claude-haiku-4-5 | 7841 | 9 | 9896 | 0 | 12056 | False |
| polish | style_editor | claude-haiku-4-5 | 3793 | 9 | 5549 | 0 | 15801 | False |
| digest | writer | claude-haiku-4-5 | 3468 | 9 | 5210 | 0 | 1375 | False |
| extract | canoniser | claude-haiku-4-5 | 13993 | 9 | 14567 | 0 | 12377 | False |

Model findings on scene 006:

A missing invariant 6 or 3 finding is a miss only if the draft contains the breach: an obedient writer leaves nothing to flag. Read the draft above to tell which.

## AC 27 - live extraction on Draft A -- 2026-09-24 12:46 UTC

- Extraction on scene 002 (Draft A): 2 fact(s), model `claude-haiku-4-5`, estimate 13909, input 9, cache creation 14502, cache read 0, over_cap False

| Hand-labelled fact | Target | Found |
|---|---|---|
| F1 | `pump_vault`.`geometry` | yes |
| F2 | `ax_cold_soak`.`exceptions` | yes |

Every fact returned:
- `ax_cold_soak`.`exceptions`: "Co-op indemnity dives may shorten the soak to four hours from the standard six hours; the indemnity covers the lung damage incurred by the shortened soak"
- `pump_vault`.`geometry`: "The throat is controlled by a cycle set by the board; a diver may request the cycle be held but cannot hold it themselves; the cycle operates on a fixed schedule and the door will close when the cycle arrives regardless of who is in the throat"

Addresses promotion could not write: 0 in the first answer (retried once), 0 still after the retry (not kept):

## AC 27 - live extraction on Draft A -- 2026-09-24 12:46 UTC

- Extraction on scene 002 (Draft A): 3 fact(s), model `claude-haiku-4-5`, estimate 13909, input 9, cache creation 14501, cache read 0, over_cap False

| Hand-labelled fact | Target | Found |
|---|---|---|
| F1 | `pump_vault`.`geometry` | **NO** |
| F2 | `ax_cold_soak`.`exceptions` | yes |

Every fact returned:
- `ax_cold_soak`.`exceptions`: "Indemnity dive: soak may be reduced to four hours"
- `ilan`.`immutable_physical`: "perfluorocarbon_tolerance: absent"
- `ilan`.`immutable_physical`: "left_hand: absent"

Addresses promotion could not write: 0 in the first answer (retried once), 0 still after the retry (not kept):

## AC 27 - live extraction on Draft A -- 2026-09-24 12:47 UTC

- Extraction on scene 002 (Draft A): 4 fact(s), model `claude-haiku-4-5`, estimate 13909, input 9, cache creation 14500, cache read 0, over_cap False

| Hand-labelled fact | Target | Found |
|---|---|---|
| F1 | `pump_vault`.`geometry` | yes |
| F2 | `ax_cold_soak`.`exceptions` | yes |

Every fact returned:
- `ax_cold_soak`.`exceptions`: "Co-op indemnity dives permit the soak window to be shortened from six hours to four hours"
- `pump_vault`.`geometry`: "eleven metres from the throat to the core cradle; the throat is a remotely controlled access cycle managed by the board two hundred metres up the gallery; a diver on the wire may request it be held but cannot hold it themselves; the throat cycle may close on a diver during egression; the throat releases from the vault side only; no guide line, no fixed lamp"
- `ilan`.`immutable_physical`: "left_hand: lost"
- `ilan`.`competences`: "execute learned splicing procedures without conscious recollection of their steps"

Addresses promotion could not write: 0 in the first answer (retried once), 0 still after the retry (not kept):
