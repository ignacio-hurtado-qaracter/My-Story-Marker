# Vectors with sqlite-vec

**This page is the policy. For the API surface, use the `sqlite-vec` skill**, which is
vendored separately and covers the parts not repeated here: int8 and binary vector types,
quantisation, the binary serialisation format, constructor and arithmetic functions, and
metadata filtering in depth.

Read the ruling below first. It constrains what any of that may be used for in this
project, and it takes precedence over the vendored skill, which knows nothing about this
architecture.

## Read this before using it

`architecture.md` splits assembly into **two** operations, and the line between them is
what this page is about:

- **`select_entities(scene)` — semantic, not reproducible.** It embeds the scene record
  (`goal`, `conflict`, `value_change`, `pov`, `location`, `entry_state`, `exit_state`,
  `notes`) and queries the entity index for the nearest entities. Vector search **is** this
  path, fused with FTS5 BM25. It returns **identifiers ranked by relevance, never text**.
- **The load — deterministic and reproducible.** Each returned identifier is fetched
  through the store layer in its as-of form (`dossier(id, at=T)` for characters, the full
  record for axioms and locations, the chapter digest for prose) in ranking order until the
  100k cap.

**The rule vector search must not cross is the load, not the selection.** Similarity chooses
*which* records are considered; it never produces the text handed to a role and it never
decides *which version* of a record that is. Retrieval therefore cannot introduce a fact —
it can only choose among facts that already exist in the stores. The index is derived and
rebuildable; a row with no backing record is a bug.

Selection being unreproducible is accepted, not accidental: two runs may rank differently.
It is registered in [`verification.md`](../../../../docs/verification.md#accepted-risks-u-register),
and it is why the selected identifiers are written to the turn record — what entered a
context is always recoverable, even when *why* it was chosen is not. The auditor of a turn
reads that same recorded list, so "which axioms apply to this scene" has one answer per turn.

Two hard constraints on the vector side:

- **The extension is optional.** The backend must start, and selection must still work, when
  `sqlite-vec` does not load: FTS5-only ranking, `/health` reporting `vector: unavailable`.
  No code path may fail for a missing extension.
- **384 dimensions, fixed.** Only 384-d embedding models are accepted so the `vec0` schema
  never changes.

Uses beyond selection that remain sound:

- Finding probable duplicates or near-collisions in `ledger/proposed.yaml` before a fact is
  promoted.
- Human-facing search over the manuscript, where the result is shown to a person rather than
  fed to a model.
- Suggesting candidate links for a human to confirm, never committing them.

## Status

`sqlite-vec` is pre-v1. The project says plainly to expect breaking changes, and its
documentation site is marked alpha and a work in progress. Pin the exact version and treat
an upgrade as a change that needs testing, not a routine bump.

## Loading it in Python

```python
import sqlite3
import sqlite_vec

db = sqlite3.connect(path)
db.enable_load_extension(True)
sqlite_vec.load(db)
db.enable_load_extension(False)

db.execute("SELECT vec_version()").fetchone()
```

Install with `pip install sqlite-vec`. SQLite 3.41 or newer is recommended. The system Python
on macOS ships a SQLite build without extension support, so use a Homebrew or uv-managed
Python there.

Note that the extension must be loaded on **every** connection that needs it, and that
enabling extension loading is itself a privilege worth turning off again immediately, as
above.

## Declaring a table

```sql
CREATE VIRTUAL TABLE vec_chunks USING vec0(
  document_id integer partition key,
  contents_embedding float[768],
  label text,
  +contents text
);
```

Four kinds of column:

- **Vector columns**, with an explicit dimension.
- **Metadata columns**, usable in the `WHERE` clause of a nearest-neighbour query. Operators
  are `=`, `!=`, `>`, `>=`, `<`, `<=`. Booleans support only `=` and `!=`.
- **Partition keys**, at most four. They shard the table internally. They need hundreds of
  vectors per distinct value to pay off, so partitioning by something high cardinality like a
  scene id will over-shard.
- **Auxiliary columns**, prefixed with `+`. Unindexed, and not usable in the `WHERE` clause of
  a nearest-neighbour query.

## Querying

```sql
SELECT document_id, distance
FROM vec_chunks
WHERE contents_embedding MATCH :query
  AND k = 10;
```

On SQLite 3.41 and newer a plain `LIMIT` works instead of `k =`.

Bind vectors with `sqlite_vec.serialize_float32([...])`, or pass a NumPy array cast to
`float32`.

Distance metrics are chosen with `distance_metric=` at table creation. L2 is the default, and
L1 and cosine are available, with matching scalar functions `vec_distance_L2`,
`vec_distance_L1` and `vec_distance_cosine`.

## The limitation that matters

**Search is brute force.** There is no approximate nearest-neighbour index, no HNSW and no
IVF. Every query scans the vectors, and partition keys are the only documented way to reduce
how many get scanned.

For a novel this is fine, because the corpus is small. It becomes the wrong tool the moment
the vector count grows into the millions, and it is a reason not to build anything
latency-critical on it.

`sqlite-vec` is the successor to `sqlite-vss`. Use it rather than `sqlite-vss` in new work.

## Embeddings are derived data

An embedding is a function of the text and of a specific model. Store the model identifier
and the dimension alongside every vector, because a model change invalidates every vector
computed with the previous one and there is no way to detect that from the numbers alone.

Like the rest of the database, vectors are derived. They can be recomputed from the files,
they are never the source of truth, and nothing in `canon/` may depend on them.
