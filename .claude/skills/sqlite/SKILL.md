---
name: sqlite
description: SQLite conventions for this project's Python backend. Use for schemas, queries, connection setup, transactions and SQLITE_BUSY, FTS5 search, and sqlite-vec vectors.
---

# SQLite

Conventions for SQLite in `backend/`, accessed from Python. Written against the official
SQLite and Python documentation. This skill is owned by this repository, not by the SQLite
project, which publishes no agent tooling.

Versions this was written against: `sqlite-vec` 0.1.9, `aiosqlite` 0.22.1, Python 3.12 or
newer.

## What the database is for in this project

**The file tree is the source of truth.** `canon/`, `structure/`, `scenes/`, `manuscript/`
and `ledger/` are the stores, and git gives them versioning and continuity diffs. That does
not change.

**SQLite is a derived index over those files.** It exists so that the operations in
`architecture.md` can run without walking the whole tree: as-of dossier queries, graph
traversal, `reconcile` finding which scenes depended on a changed fact, timeline checks
across the story and discourse axes. Everything in it can be rebuilt from the files.

Two consequences:

* A write to the database is never a write to canon. The permission boundaries in Figure 3
  of `architecture.md` are enforced over the stores. The index follows the files, never the
  other way around.
* If the index and the files disagree, the files win and the index is rebuilt.

**On vector search.** `architecture.md` states that context assembly walks the entity graph
rather than searching by semantic similarity, because the relations are known in advance and
explicit traversal is both faster and reproducible. Vector capability is available through
`sqlite-vec`, but it must not become the retrieval path for assembling context. Legitimate
secondary uses are things like spotting a probable duplicate in the canonisation queue or
helping a human search the manuscript. This reading reconciles the architecture document
with the project rule requiring vector compatibility, and it is an assumption: if the
intent was different, the architecture document is what needs changing first.

## Connection setup

Set these on every new connection, in this order, before any work.

```sql
PRAGMA journal_mode = WAL;      -- persistent: survives close and reopen
PRAGMA synchronous = NORMAL;    -- official best balance for WAL
PRAGMA foreign_keys = ON;       -- OFF by default, and per connection
PRAGMA busy_timeout = 5000;     -- milliseconds; per connection
```

What each one is doing:

**`journal_mode = WAL`** is persistent. It is a property of the database file, so it stays
in effect across connections and reopens, and setting it once is enough. Readers do not
block writers and writers do not block readers, the input and output is more sequential, and
there are fewer calls to fsync.

**`synchronous = NORMAL`** is the official recommendation for WAL. The exact tradeoff: WAL
at NORMAL is safe from corruption and always consistent, but a committed transaction can be
rolled back by a power loss or a system crash. For a derived index that can be rebuilt from
the files, that is the correct trade. For anything that could not be rebuilt, use `FULL`.

**`foreign_keys`** is off by default and is a per-connection setting, so it must be set
every time. It is a no-op inside a transaction, so set it before opening one.

**`busy_timeout`** is per connection. No official source recommends a number; choose one
that matches how long a writer may reasonably hold the database.

### When WAL is the wrong choice

- **Network filesystems.** WAL needs shared memory between processes, so all of them must be
  on the same host. It does not work over a network filesystem at all.
- **Read-only media.** Switch to `journal_mode = DELETE` first.
- **Very large transactions.** Above roughly 100 MB it gets slower, and above a gigabyte it
  can fail outright.
- **Read-heavy workloads with rare writes**, where WAL is marginally slower.

## Transactions and SQLITE_BUSY

SQLite allows unlimited concurrent readers and exactly one writer at a time.

The default transaction type is DEFERRED, which does not take a write lock until the first
write statement. If another connection has written in the meantime, that upgrade fails with
`SQLITE_BUSY` in the middle of your transaction.

**The rule: `BEGIN IMMEDIATE` for anything that will write, plain `BEGIN` only for pure
reads.** The official guarantee is precise. `BEGIN IMMEDIATE` may itself return
`SQLITE_BUSY`, but if it succeeds, no operation through the following `COMMIT` will return
`SQLITE_BUSY`. That turns a failure that can strike anywhere into one that can only strike
at a single retryable point.

In WAL mode, watch for `SQLITE_BUSY_SNAPSHOT`, raised when a read transaction tries to
become a write transaction after another connection has already written. There is no way to
recover in place. Roll back and retry the whole transaction.

Long-running read transactions hold back checkpointing and let the write-ahead log grow.
Keep read transactions short.

## Concurrency from a web backend

One writer at a time is the constraint everything else follows from. A FastAPI backend in
front of SQLite is the officially sanctioned pattern: the documented thing to avoid is many
machines reaching the same database file over a network without an application server in
between.

Practical consequences:

* Serialise writes. One writer connection, or a lock around the write path.
* Use as many read connections as you like.
* Keep the operations that write, such as `promote`, short and batched rather than holding a
  transaction open across model calls.

Python specifics, including the transaction handling that surprises people and how to run a
blocking driver under an async framework, are in [python](references/python.md).

## References

* [Python integration](references/python.md) — the `sqlite3` module, transaction control, threads, async.
* [Schema and queries](references/schema-and-queries.md) — indexing, query plans, `ANALYZE`, FTS5.
* [Vectors](references/vectors.md) — `sqlite-vec`, and the limits on how it may be used here.
