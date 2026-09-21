# Schema and queries

## Reading a query plan

`EXPLAIN QUERY PLAN` reports the strategy, and most usefully how indexes are used. The
output format is for interactive debugging only and changes between releases, so never
parse it in code or assert on it in a test.

What the lines mean:

- **SCAN** is a full table scan, including iterating every row in index order.
- **SEARCH** visits only a subset of rows.
- `SEARCH t USING INDEX i (a=?)` is an index lookup.
- `SEARCH t USING COVERING INDEX i (a=?)` answered the query from the index alone.
- `USE TEMP B-TREE FOR ORDER BY` means a sort is being materialised. An index on the ordering
  column removes it.

A SCAN on a small lookup table is fine. A SCAN on the scene or fact tables in a query that
runs during context assembly is a defect.

## Indexing

For a `WHERE` clause with several terms joined by AND, the official advice is a single
multi-column index covering those terms, not several single-column indexes. Column order
matters, leftmost first.

Add the output columns to the end of an index to make it covering. SQLite then never
consults the table, which the documentation describes as roughly halving the binary searches
for the query.

Do not keep two indexes where one is a prefix of the other. Drop the shorter one.

Given the access patterns in `architecture.md`, the indexes that earn their place are the
ones supporting the as-of dossier query, which is a character plus a story time bound, and
the reverse lookup used by `reconcile`, which is an entity to the scenes that referenced it.

## Statistics

`ANALYZE` collects statistics into `sqlite_stat1` for the query planner.

The recommended way to run it is `PRAGMA optimize`, which is usually a no-op and only runs
`ANALYZE` where it will help.

- Short-lived connections: run `PRAGMA optimize;` just before closing.
- Long-lived connections: `PRAGMA optimize=0x10002;` when the connection opens, then
  `PRAGMA optimize;` periodically, roughly daily.
- Also after creating an index or changing the schema.

## Full-text search with FTS5

```sql
CREATE VIRTUAL TABLE scene_fts USING fts5(title, body);
```

Columns take no types, no constraints and no primary key. There is an implicit integer
`rowid`. A column may not be named `rowid` or `rank`.

### External content tables

When the text already lives in a normal table, store only the index:

```sql
CREATE VIRTUAL TABLE fts_idx USING fts5(b, c, content='t1', content_rowid='a');
```

FTS5 keeps the index and fetches column values from the content table on demand.

**Keeping them consistent is your responsibility.** The official warning is explicit: if the
index and its content table drift apart, query results become unintuitive and inconsistent.
There is no automatic reconciliation.

The documented mechanism is triggers:

```sql
CREATE TRIGGER t1_ai AFTER INSERT ON t1 BEGIN
  INSERT INTO fts_idx(rowid, b, c) VALUES (new.a, new.b, new.c);
END;
CREATE TRIGGER t1_ad AFTER DELETE ON t1 BEGIN
  INSERT INTO fts_idx(fts_idx, rowid, b, c) VALUES('delete', old.a, old.b, old.c);
END;
CREATE TRIGGER t1_au AFTER UPDATE ON t1 BEGIN
  INSERT INTO fts_idx(fts_idx, rowid, b, c) VALUES('delete', old.a, old.b, old.c);
  INSERT INTO fts_idx(fts_idx, rowid, b, c) VALUES (new.a, new.b, new.c);
END;
```

Two details that cause silent corruption if missed. A delete is expressed as a special
`'delete'` command row, not a `DELETE` statement, and it must carry the **old** values. And
when updating by hand rather than by trigger, update the FTS table first, while the content
row is still available to it.

Triggers do not backfill rows that already existed. After adding them to a populated table,
rebuild:

```sql
INSERT INTO fts_idx(fts_idx) VALUES('rebuild');
```

### Contentless tables

`content=''` stores only the index. There is no UPDATE or DELETE, no INSERT without an
explicit rowid, no REPLACE conflict handling, and reads return NULL for every column but
`rowid`. Useful only when the text is definitely elsewhere and you need nothing back but
identifiers.

## When SQLite is the wrong tool

The official guidance, applied to this project:

- **Many machines reaching one database file over a network, with no application server in
  between.** Not our shape. The FastAPI backend is exactly the intervening server the
  documentation describes.
- **Genuine concurrent writes.** One writer at a time. If the harness ever runs many writing
  turns in parallel against one index, this is the constraint that breaks first.
- **Write-intensive load needing several servers.** Use a client/server engine.
- **Very large datasets.** The hard limit is 281 TB, and the filesystem's own file size limit
  applies first. Not a concern for a novel.
