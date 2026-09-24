--------------------------- MODULE GiftNovelHarness ---------------------------
(***************************************************************************)
(* Gift-novel harness flow (spec 013, block B9 of spec 004).                *)
(*                                                                         *)
(* One novel: Configured (brief valid) -> Planned -> per chapter: scenes   *)
(* with scene_accept and bounded rewrite, editor pass, chapter_close with  *)
(* bounded chapter rewrite, Checkpoint(c) -> pre_publish with one bounded  *)
(* repair round -> Published(v) or StoppedError. A crash may happen at any *)
(* non-terminal step; Resume restarts from the database. A reader change   *)
(* on a published version creates version v+1 and regenerates only the    *)
(* affected chapters through the same loop. Validator outcomes are         *)
(* nondeterministic.                                                       *)
(*                                                                         *)
(* Durable variables stand for K1 rows (they survive Crash); volatile ones *)
(* are the pipeline's memory (reset by Crash); ghost ones exist only for   *)
(* the properties. Counterexamples found while developing the model and    *)
(* the fixes they caused are in COUNTEREXAMPLES.md (CE1-CE4 below).        *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS N, SCENES, MAX_SCENE_RETRIES, MAX_CHAPTER_RETRIES, MAX_REPAIR_ROUNDS,
          MaxCrashes, MaxChanges

Chapters == 1..N
Versions == 1..(MaxChanges + 1)
Terminal == {"Published", "StoppedError"}
Phases   == {"Configured", "Planned", "Next", "Scene", "Editor", "Close",
             "Checkpoint", "PrePublish", "Publish", "Published", "StoppedError",
             "Crashed"}
VStatus  == {"none", "draft", "blocked", "published"}

Min(S) == CHOOSE x \in S : \A y \in S : x <= y
Max(S) == CHOOSE x \in S : \A y \in S : x >= y

VARIABLES
  \* durable: rows of the authoritative database (K1); survive a crash
  vstatus,    \* novel_version.status
  changed,    \* novel_version.changed_chapters
  rows,       \* number of chapter_version rows stored per (version, chapter)
  origin,     \* version in which the stored text was written (0 = none)
  passed,     \* the stored text passed scene_accept and chapter_close
  ckpt,       \* checkpoint rows: chapters complete per version
  ppOk,       \* persisted pre_publish validator_result passed, per version
  factRev,    \* revision of the brief facts
  chFails,    \* chapter_close failures in validator_result since the chapter
              \* was last opened (CE2: was an in-memory counter)
  repairRounds, \* pre_publish repair rounds used, on novel_version
              \* (CE4: was an in-memory counter)
  \* volatile: memory of the pipeline process; lost on a crash
  pc, ver, cur, scene, sceneTry,
  \* ghost: bookkeeping for the properties only
  crashes, changes, everPublished, snap

durable  == <<vstatus, changed, rows, origin, passed, ckpt, ppOk, factRev, chFails,
             repairRounds>>
volatile == <<pc, ver, cur, scene, sceneTry>>
ghost    == <<crashes, changes, everPublished, snap>>
vars     == <<durable, volatile, ghost>>

Row(v, c) == <<rows[v][c], origin[v][c], passed[v][c]>>

TypeOK ==
  /\ vstatus \in [Versions -> VStatus]
  /\ changed \in [Versions -> SUBSET Chapters]
  /\ rows    \in [Versions -> [Chapters -> Nat]]
  /\ origin  \in [Versions -> [Chapters -> 0..(MaxChanges + 1)]]
  /\ passed  \in [Versions -> [Chapters -> BOOLEAN]]
  /\ ckpt    \in [Versions -> SUBSET Chapters]
  /\ ppOk    \in [Versions -> BOOLEAN]
  /\ factRev \in 0..MaxChanges
  /\ pc      \in Phases
  /\ ver     \in 0..(MaxChanges + 1)
  /\ cur     \in 0..N
  /\ scene   \in 0..SCENES
  /\ sceneTry \in Nat
  /\ crashes \in 0..MaxCrashes /\ changes \in 0..MaxChanges
  /\ everPublished \subseteq Versions
  /\ chFails \in [Versions -> [Chapters -> Nat]]
  /\ repairRounds \in [Versions -> Nat]

Init ==
  /\ vstatus = [v \in Versions |-> "none"]
  /\ changed = [v \in Versions |-> {}]
  /\ rows    = [v \in Versions |-> [c \in Chapters |-> 0]]
  /\ origin  = [v \in Versions |-> [c \in Chapters |-> 0]]
  /\ passed  = [v \in Versions |-> [c \in Chapters |-> FALSE]]
  /\ ckpt    = [v \in Versions |-> {}]
  /\ ppOk    = [v \in Versions |-> FALSE]
  /\ factRev = 0
  /\ pc = "Configured" /\ ver = 0 /\ cur = 0 /\ scene = 0
  /\ sceneTry = 0
  /\ crashes = 0 /\ changes = 0 /\ everPublished = {}
  /\ snap = [v \in Versions |-> [c \in Chapters |-> <<0, 0, FALSE>>]]
  /\ chFails = [v \in Versions |-> [c \in Chapters |-> 0]]
  /\ repairRounds = [v \in Versions |-> 0]

(* Configured (brief valid) -> Planned: version 1 is created as a draft.   *)
Plan ==
  /\ pc = "Configured"
  /\ vstatus' = [vstatus EXCEPT ![1] = "draft"]
  /\ changed' = [changed EXCEPT ![1] = Chapters]
  /\ ver' = 1 /\ pc' = "Planned"
  /\ UNCHANGED <<rows, origin, passed, ckpt, ppOk, factRev, chFails,
                 repairRounds, cur, scene, sceneTry, ghost>>

(* Pick the first chapter of the version without a checkpoint.            *)
NextChapter ==
  /\ pc \in {"Planned", "Next"}
  /\ LET todo == Chapters \ ckpt[ver] IN
       IF todo # {}
       THEN /\ cur' = Min(todo) /\ scene' = 1 /\ sceneTry' = 0
            /\ pc' = "Scene"
       ELSE /\ pc' = "PrePublish"
            /\ UNCHANGED <<cur, scene, sceneTry>>
  /\ UNCHANGED <<durable, ver, ghost>>

(* Write one scene and run scene_accept (forbidden words, schema).         *)
WriteScene ==
  /\ pc = "Scene"
  /\ \/ /\ scene < SCENES                                  \* pass, more scenes
        /\ scene' = scene + 1 /\ sceneTry' = 0 /\ UNCHANGED pc
     \/ /\ scene = SCENES                                  \* pass, last scene
        /\ pc' = "Editor" /\ UNCHANGED <<scene, sceneTry>>
     \/ /\ sceneTry < MAX_SCENE_RETRIES                    \* fail, rewrite
        /\ sceneTry' = sceneTry + 1 /\ UNCHANGED <<pc, scene>>
     \/ /\ sceneTry = MAX_SCENE_RETRIES                    \* fail, exhausted
        /\ pc' = "StoppedError" /\ UNCHANGED <<scene, sceneTry>>
  /\ UNCHANGED <<durable, ver, cur, ghost>>

Editor ==
  /\ pc = "Editor" /\ pc' = "Close"
  /\ UNCHANGED <<durable, ver, cur, scene, sceneTry, ghost>>

(* chapter_close: length, exact names, judge.                               *)
CloseChapter ==
  /\ pc = "Close"
  /\ \/ /\ pc' = "Checkpoint"                              \* pass
        /\ UNCHANGED <<scene, sceneTry, chFails>>
     \/ /\ chFails[ver][cur] < MAX_CHAPTER_RETRIES         \* fail, rewrite chapter
        /\ chFails' = [chFails EXCEPT ![ver][cur] = @ + 1]
        /\ scene' = 1 /\ sceneTry' = 0 /\ pc' = "Scene"
     \/ /\ chFails[ver][cur] = MAX_CHAPTER_RETRIES         \* fail, exhausted
        /\ pc' = "StoppedError"
        /\ UNCHANGED <<scene, sceneTry, chFails>>
  /\ UNCHANGED <<vstatus, changed, rows, origin, passed, ckpt, ppOk, factRev,
                 repairRounds, ver, cur, ghost>>

(* Checkpoint(c): the chapter_version row and the checkpoint row are      *)
(* written in ONE transaction (CE1). The row is keyed by (version,         *)
(* chapter) and upserted, never inserted twice, and only a version that is *)
(* not published may be written (CE3).                                     *)
Checkpoint ==
  /\ pc = "Checkpoint"
  /\ vstatus[ver] # "published"
  /\ rows'   = [rows   EXCEPT ![ver][cur] = 1]
  /\ origin' = [origin EXCEPT ![ver][cur] = ver]
  /\ passed' = [passed EXCEPT ![ver][cur] = TRUE]
  /\ ckpt'   = [ckpt   EXCEPT ![ver] = @ \cup {cur}]
  /\ chFails' = [chFails EXCEPT ![ver][cur] = 0]
  /\ pc' = "Next"
  /\ UNCHANGED <<vstatus, changed, ppOk, factRev, repairRounds,
                 ver, cur, scene, sceneTry, ghost>>

(* pre_publish: brief coverage, Lean, visual check.                         *)
PrePublish ==
  /\ pc = "PrePublish"
  /\ \/ /\ ppOk' = [ppOk EXCEPT ![ver] = TRUE]             \* pass
        /\ pc' = "Publish"
        /\ UNCHANGED <<vstatus, ckpt, chFails, repairRounds>>
     \/ /\ repairRounds[ver] < MAX_REPAIR_ROUNDS           \* fail, repair round
        /\ \E R \in (SUBSET Chapters) \ {{}} :
             /\ ckpt' = [ckpt EXCEPT ![ver] = @ \ R]
             /\ chFails' = [chFails EXCEPT ![ver] =
                              [c \in Chapters |-> IF c \in R THEN 0 ELSE @[c]]]
        /\ vstatus' = [vstatus EXCEPT ![ver] = "blocked"]
        /\ repairRounds' = [repairRounds EXCEPT ![ver] = @ + 1]
        /\ pc' = "Next"
        /\ UNCHANGED ppOk
     \/ /\ repairRounds[ver] = MAX_REPAIR_ROUNDS           \* fail, exhausted
        /\ vstatus' = [vstatus EXCEPT ![ver] = "blocked"]
        /\ pc' = "StoppedError"
        /\ UNCHANGED <<ppOk, ckpt, chFails, repairRounds>>
  /\ UNCHANGED <<changed, rows, origin, passed, factRev,
                 ver, cur, scene, sceneTry, ghost>>

(* Published(version).                                                      *)
Publish ==
  /\ pc = "Publish"
  /\ vstatus' = [vstatus EXCEPT ![ver] = "published"]
  /\ everPublished' = everPublished \cup {ver}
  /\ snap' = [snap EXCEPT ![ver] = [c \in Chapters |-> Row(ver, c)]]
  /\ pc' = "Published"
  /\ UNCHANGED <<changed, rows, origin, passed, ckpt, ppOk, factRev,
                 chFails, repairRounds, ver, cur, scene, sceneTry,
                 crashes, changes>>

(* The reader changes a fact of the published version: version v+1 copies *)
(* the unaffected chapters and regenerates the affected ones.              *)
ChangeFact ==
  /\ pc = "Published"
  /\ changes < MaxChanges
  /\ LET w == ver + 1 IN
       /\ w \in Versions
       /\ vstatus[w] = "none"
       /\ \E A \in (SUBSET Chapters) \ {{}} :
            /\ vstatus' = [vstatus EXCEPT ![w] = "draft"]
            /\ changed' = [changed EXCEPT ![w] = A]
            /\ rows'   = [rows   EXCEPT ![w] = [c \in Chapters |->
                              IF c \in A THEN 0 ELSE rows[ver][c]]]
            /\ origin' = [origin EXCEPT ![w] = [c \in Chapters |->
                              IF c \in A THEN 0 ELSE origin[ver][c]]]
            /\ passed' = [passed EXCEPT ![w] = [c \in Chapters |->
                              IF c \in A THEN FALSE ELSE passed[ver][c]]]
            /\ ckpt'   = [ckpt EXCEPT ![w] = Chapters \ A]
       /\ ver' = w
  /\ factRev' = factRev + 1
  /\ changes' = changes + 1
  /\ pc' = "Next"
  /\ UNCHANGED <<ppOk, chFails, repairRounds, cur, scene, sceneTry,
                 crashes, everPublished, snap>>

(* The process dies: memory is lost, the database is kept.                  *)
Crash ==
  /\ pc \notin Terminal \cup {"Crashed"}
  /\ crashes < MaxCrashes
  /\ crashes' = crashes + 1
  /\ pc' = "Crashed" /\ ver' = 0 /\ cur' = 0 /\ scene' = 0
  /\ sceneTry' = 0
  /\ UNCHANGED <<durable, changes, everPublished, snap>>

(* Resume from the database: the latest version, first chapter without a   *)
(* complete checkpoint.                                                     *)
Resume ==
  /\ pc = "Crashed"
  /\ IF \A v \in Versions : vstatus[v] = "none"
     THEN /\ pc' = "Configured" /\ UNCHANGED ver
     ELSE LET v == Max({x \in Versions : vstatus[x] # "none"}) IN
            /\ ver' = v
            /\ pc' = IF vstatus[v] = "published" THEN "Published" ELSE "Next"
  /\ UNCHANGED <<durable, cur, scene, sceneTry, ghost>>

Done == pc \in Terminal /\ UNCHANGED vars

Progress == Plan \/ NextChapter \/ WriteScene \/ Editor \/ CloseChapter
            \/ Checkpoint \/ PrePublish \/ Publish \/ Resume

Next == Progress \/ ChangeFact \/ Crash \/ Done

Spec == Init /\ [][Next]_vars /\ WF_vars(Progress)

-----------------------------------------------------------------------------
(* Safety *)

NoUnvalidatedPublish ==
  \A v \in Versions : vstatus[v] = "published" =>
      /\ ppOk[v]
      /\ ckpt[v] = Chapters
      /\ \A c \in Chapters : rows[v][c] >= 1 /\ passed[v][c]

ResumeNoDupNoLoss ==
  \A v \in Versions : \A c \in Chapters :
      /\ rows[v][c] <= 1                        \* no chapter stored twice
      /\ c \in ckpt[v] => rows[v][c] = 1        \* no checkpoint without its text

PreviousVersionKept ==
  \A v \in everPublished :
      /\ vstatus[v] = "published"
      /\ \A c \in Chapters : Row(v, c) = snap[v][c]

RetriesBounded ==
  /\ sceneTry <= MAX_SCENE_RETRIES
  /\ \A v \in Versions : repairRounds[v] <= MAX_REPAIR_ROUNDS
  /\ \A v \in Versions : \A c \in Chapters : chFails[v][c] <= MAX_CHAPTER_RETRIES

(* A crash and the resume that follows change nothing in the database.     *)
StoreSurvivesCrash == [][(Crash \/ Resume) => UNCHANGED durable]_vars

(* Liveness *)

Termination == <>[](pc \in Terminal)
EveryGenerationEnds == (pc \notin Terminal) ~> (pc \in Terminal)
=============================================================================
