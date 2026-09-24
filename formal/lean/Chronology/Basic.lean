/-!
# Chronology of a story — model and invariants

Spec 012 (block B8 of programme 004), requirements L01–L04.

A story's chronology is a list of events. Each event has a discourse position (`seq`, the
order in which the novel tells it), a story date, a place, the characters present, a kind
(`normal`, `death`, `departure`) and the ages the text declares for some participants.

Characters and places are `Nat` indices: the exporter
(`backend/app/formal/lean_export.py`) maps the database's string ids to indices and keeps
the original ids and names in a string table the checks never read. Keeping the checked
model on `Nat` means every check reduces in the kernel with GMP-accelerated arithmetic,
so `by decide` is the proof.

Every invariant exists twice:

* a `Bool` check (`temporalOrderB`, …) that `decide` evaluates, and
* a `Prop` statement (`TemporalOrder`, …) that says what the check means,

linked by a soundness theorem (`temporalOrder_sound`, …), so a passing check is a proof
of the `Prop`, not merely a `true`.
-/

namespace Chronology

/-- A proleptic Gregorian calendar date. The exporter only emits valid dates, year ≥ 1. -/
structure Date where
  y : Nat
  m : Nat
  d : Nat
  deriving Repr, DecidableEq

/-- Day number of a date (days since 0000-03-01), Howard Hinnant's `days_from_civil`
restricted to years ≥ 1, where every subtraction below is non-negative. -/
def Date.dayNumber (t : Date) : Nat :=
  let y := if t.m ≤ 2 then t.y - 1 else t.y
  let era := y / 400
  let yoe := y - era * 400
  let mp := (t.m + 9) % 12
  let doy := (153 * mp + 2) / 5 + t.d - 1
  let doe := yoe * 365 + yoe / 4 - yoe / 100 + doy
  era * 146097 + doe

/-- Full years elapsed from `birth` to `t`: the age a person born on `birth` has on `t`. -/
def fullYears (birth t : Date) : Nat :=
  if t.m < birth.m ∨ (t.m = birth.m ∧ t.d < birth.d) then
    t.y - birth.y - 1
  else
    t.y - birth.y

inductive Kind where
  | normal
  | death
  | departure
  deriving Repr, DecidableEq

/-- `true` for the kinds after which the first participant leaves the story. -/
def Kind.isExit : Kind → Bool
  | .normal => false
  | .death => true
  | .departure => true

structure Character where
  id : Nat
  birth : Option Date
  deriving Repr

structure Place where
  id : Nat
  deriving Repr

structure Event where
  id : Nat
  seq : Nat
  date : Date
  /-- `date.dayNumber`, precomputed by the exporter: the kernel shares no work, so the
  pairwise checks compare this field instead of recomputing the calendar n² times.
  `datesConsistent` checks it, linearly, inside every check that relies on it. -/
  day : Nat
  place : Nat
  participants : List Nat
  kind : Kind
  /-- `(character, declared age)` pairs. -/
  declaredAges : List (Nat × Nat)
  deriving Repr

structure Story where
  characters : List Character
  places : List Place
  events : List Event
  deriving Repr

/-- Birth date of a character, if the character is known and has one. -/
def Story.birthOf (s : Story) (c : Nat) : Option Date :=
  (s.characters.find? (·.id == c)).bind (·.birth)

/-- Every event's precomputed `day` is its date's day number. -/
def datesConsistent (s : Story) : Bool :=
  s.events.all fun e => e.day == e.date.dayNumber

theorem day_eq_of_consistent {s : Story} (h : datesConsistent s = true) {e : Event}
    (he : e ∈ s.events) : e.day = e.date.dayNumber := by
  simp only [datesConsistent, List.all_eq_true] at h
  simpa using h e he

/-! ## Invariant 1 — temporal order

Events told later (greater `seq`) never happen earlier in story time.

The check is linear: the exporter lists events by `seq`, and `seqChain` checks each
adjacent pair has a strictly greater `seq` and a day no earlier. `seqChain_pairwise` lifts
that to every pair, so the `Prop` quantifies over all pairs, whatever the list order the
check was given. (A pairwise check costs the kernel about 200 µs a pair.) -/

/-- The ordering an adjacent pair must satisfy. -/
def Before (a b : Event) : Prop := a.seq < b.seq ∧ a.day ≤ b.day

def seqChain : List Event → Bool
  | a :: b :: rest => decide (a.seq < b.seq) && decide (a.day ≤ b.day) && seqChain (b :: rest)
  | _ => true

theorem seqChain_pairwise : ∀ l : List Event, seqChain l = true → l.Pairwise Before
  | [], _ => List.Pairwise.nil
  | [_], _ => List.pairwise_singleton _ _
  | a :: b :: rest, h => by
    simp only [seqChain, Bool.and_eq_true, decide_eq_true_eq] at h
    obtain ⟨⟨hs, hd⟩, hr⟩ := h
    have ih := seqChain_pairwise (b :: rest) hr
    refine List.Pairwise.cons ?_ ih
    intro x hx
    cases List.mem_cons.mp hx with
    | inl hxb => subst hxb; exact ⟨hs, hd⟩
    | inr hxr =>
      have hbx := (List.pairwise_cons.mp ih).1 x hxr
      exact ⟨Nat.lt_trans hs hbx.1, Nat.le_trans hd hbx.2⟩

theorem day_le_of_pairwise : ∀ {l : List Event}, l.Pairwise Before →
    ∀ {a b : Event}, a ∈ l → b ∈ l → a.seq < b.seq → a.day ≤ b.day
  | [], _, _, _, ha, _, _ => absurd ha (List.not_mem_nil)
  | x :: xs, hp, a, b, ha, hb, hlt => by
    have hx := (List.pairwise_cons.mp hp).1
    have hxs := (List.pairwise_cons.mp hp).2
    cases List.mem_cons.mp ha with
    | inl hax =>
      cases List.mem_cons.mp hb with
      | inl hbx => subst hax; subst hbx; exact absurd hlt (Nat.lt_irrefl _)
      | inr hbxs => subst hax; exact (hx b hbxs).2
    | inr haxs =>
      cases List.mem_cons.mp hb with
      | inl hbx => subst hbx; exact absurd (Nat.lt_trans hlt (hx a haxs).1) (Nat.lt_irrefl _)
      | inr hbxs => exact day_le_of_pairwise hxs haxs hbxs hlt

def temporalOrderB (s : Story) : Bool :=
  datesConsistent s && seqChain s.events

def TemporalOrder (s : Story) : Prop :=
  ∀ a ∈ s.events, ∀ b ∈ s.events, a.seq < b.seq → a.date.dayNumber ≤ b.date.dayNumber

theorem temporalOrder_sound (s : Story) (h : temporalOrderB s = true) : TemporalOrder s := by
  intro a ha b hb hlt
  simp only [temporalOrderB, Bool.and_eq_true] at h
  rw [← day_eq_of_consistent h.1 ha, ← day_eq_of_consistent h.1 hb]
  exact day_le_of_pairwise (seqChain_pairwise _ h.2) ha hb hlt

/-! ## Invariant 2 — declared ages agree with birth dates

A declared age equals the full years between the character's birth and the event date.
A character with no recorded birth date constrains nothing. -/

def ageOk (s : Story) (e : Event) (ca : Nat × Nat) : Bool :=
  match s.birthOf ca.1 with
  | none => true
  | some b => ca.2 == fullYears b e.date

def agesCoherentB (s : Story) : Bool :=
  s.events.all fun e => e.declaredAges.all fun ca => ageOk s e ca

def AgesCoherent (s : Story) : Prop :=
  ∀ e ∈ s.events, ∀ ca ∈ e.declaredAges, ∀ b, s.birthOf ca.1 = some b →
    ca.2 = fullYears b e.date

theorem agesCoherent_sound (s : Story) (h : agesCoherentB s = true) : AgesCoherent s := by
  intro e he ca hca b hb
  simp only [agesCoherentB, List.all_eq_true] at h
  have := h e he ca hca
  simp_all [ageOk]

/-! ## Invariant 3 — no bilocation

A character is not present in two different places on the same day. -/

def sharesParticipant (a b : Event) : Bool :=
  a.participants.any fun c => b.participants.contains c

def noBilocationB (s : Story) : Bool :=
  datesConsistent s && s.events.all fun a => s.events.all fun b =>
    !(a.day == b.day && a.place != b.place && sharesParticipant a b)

def NoBilocation (s : Story) : Prop :=
  ∀ a ∈ s.events, ∀ b ∈ s.events, ∀ c, c ∈ a.participants → c ∈ b.participants →
    a.date.dayNumber = b.date.dayNumber → a.place = b.place

theorem noBilocation_sound (s : Story) (h : noBilocationB s = true) : NoBilocation s := by
  intro a ha b hb c hca hcb hday
  simp only [noBilocationB, Bool.and_eq_true, List.all_eq_true] at h
  have hab := h.2 a ha b hb
  rw [← day_eq_of_consistent h.1 ha, ← day_eq_of_consistent h.1 hb] at hday
  have hsh : sharesParticipant a b = true := by
    simp only [sharesParticipant, List.any_eq_true, List.contains_iff_mem]
    exact ⟨c, hca, hcb⟩
  simp_all

/-! ## Invariant 4 — nobody acts after leaving

After an event of kind `death` or `departure`, its first participant (the one who dies or
leaves) takes part in no event that happens on a **later day in story time**. The order is
the story axis (`day`), not the discourse axis (`seq`): a flashback told after the death
but dated before it is legitimate, and the day of the exit itself is allowed (the farewell
scene). Tuning iteration 1 moved this invariant from `seq` to `day`. The outer loop runs
over exit events only, so the check costs (exits × events), not events². -/

def noAfterExitB (s : Story) : Bool :=
  datesConsistent s && (s.events.filter (·.kind.isExit)).all fun x => s.events.all fun y =>
    !(decide (x.day < y.day) &&
      (x.participants.head?.map (fun c => y.participants.contains c)).getD false)

def NoAfterExit (s : Story) : Prop :=
  ∀ x ∈ s.events, ∀ y ∈ s.events, ∀ c, x.kind.isExit = true → x.participants.head? = some c →
    x.date.dayNumber < y.date.dayNumber → c ∉ y.participants

theorem noAfterExit_sound (s : Story) (h : noAfterExitB s = true) : NoAfterExit s := by
  intro x hx y hy c hk hc hlt hmem
  simp only [noAfterExitB, Bool.and_eq_true, List.all_eq_true] at h
  rw [← day_eq_of_consistent h.1 hx, ← day_eq_of_consistent h.1 hy] at hlt
  have := h.2 x (List.mem_filter.mpr ⟨hx, hk⟩) y hy
  simp_all

/-! ## The whole story -/

def validStory (s : Story) : Bool :=
  temporalOrderB s && agesCoherentB s && noBilocationB s && noAfterExitB s

def ValidStory (s : Story) : Prop :=
  TemporalOrder s ∧ AgesCoherent s ∧ NoBilocation s ∧ NoAfterExit s

theorem validStory_sound (s : Story) (h : validStory s = true) : ValidStory s := by
  simp only [validStory, Bool.and_eq_true] at h
  exact ⟨temporalOrder_sound s h.1.1.1, agesCoherent_sound s h.1.1.2,
    noBilocation_sound s h.1.2, noAfterExit_sound s h.2⟩

end Chronology
