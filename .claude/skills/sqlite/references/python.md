# Python integration

## Never build SQL with string formatting

The official documentation carries an explicit "never do this, insecure" example of
percent-formatting a query. Always bind parameters.

```python
cur.execute("SELECT * FROM scene WHERE pov = ?", (pov_id,))
cur.execute("SELECT * FROM scene WHERE pov = :pov", {"pov": pov_id})
```

Two styles are supported: question marks with a sequence, and `:name` with a dict. PEP 249
numeric placeholders are not supported and are silently read as named placeholders, which
fails in a confusing way.

Identifiers cannot be bound. If a table or column name has to be dynamic, validate it
against a fixed allowlist rather than interpolating whatever arrived.

## Transaction control

This is the part of the `sqlite3` module that behaves unexpectedly, and it is worth knowing
exactly why.

The legacy behaviour, still the default, implicitly issues a `BEGIN` before data
modification statements only. Not before DDL, not before `SELECT`. And it does not commit
on its own. So a `CREATE TABLE` runs outside a transaction while an `INSERT` silently opens
one.

Python 3.12 added `Connection.autocommit`, which is PEP 249 compliant. Its default is still
`LEGACY_TRANSACTION_CONTROL`, and the documentation says the default will change in a future
release.

**For new code in this project, take control explicitly:**

```python
con = sqlite3.connect(path, autocommit=False)   # Python 3.12+
```

With `autocommit=False` the module keeps a transaction open and you use `commit()` and
`rollback()`. With `autocommit=True` you are in SQLite's own autocommit mode and those calls
do nothing.

Because the project rule is `BEGIN IMMEDIATE` for writes, the clearest arrangement is to
manage transactions by hand:

```python
con = sqlite3.connect(path, isolation_level=None)   # no implicit BEGIN
con.execute("BEGIN IMMEDIATE")
try:
    ...
    con.execute("COMMIT")
except Exception:
    con.execute("ROLLBACK")
    raise
```

The alternative, if you stay on legacy control, is `isolation_level="IMMEDIATE"`, which
makes the implicit `BEGIN` an immediate one. That works, but it only applies to the
statements the module decides to wrap, so it is less predictable than issuing the statement
yourself.

## Rows

Rows are plain tuples by default. Set a row factory on the connection so every cursor
inherits it:

```python
con.row_factory = sqlite3.Row
```

`sqlite3.Row` gives access by index and by column name, case insensitively, plus `keys()`.
A dict factory is the other common choice and the documentation shows one.

`detect_types` is off by default. `PARSE_DECLTYPES` resolves converters from the column's
declared type and `PARSE_COLNAMES` from `AS "x [type]"` aliases. They can be combined, and
column names win over declared types. Given this project stores dates on two different axes,
be explicit about conversion rather than relying on implicit type detection.

## Threads

`check_same_thread` defaults to `True`, so using a connection from another thread raises.
Setting it to `False` permits sharing, but the documentation is clear that you then have to
serialise writes yourself to avoid corruption.

`sqlite3.threadsafety` reports what the underlying library allows: 0 means threads may not
share the module, 1 means they may share the module but not connections, 3 means module,
connections and cursors may all be shared. SQLite's own default build mode is serialized.

The safe default here is one connection per thread, with a single dedicated writer.

## Async

There is no official guidance from either SQLite or Python on using SQLite with an async
framework. What is official: `sqlite3` is a blocking, synchronous driver, and
`asyncio.to_thread()` exists for running blocking input and output off the event loop.

So, two workable approaches for this backend:

**Run blocking calls in a thread.** Either `await asyncio.to_thread(fn, ...)`, or declare
the FastAPI endpoint with `def` rather than `async def` and let the framework move it to its
threadpool.

```python
row = await asyncio.to_thread(repo.get_scene, scene_id)
```

**Use `aiosqlite`**, which wraps the same module in a worker thread and gives an async API.
It does not remove the one-writer constraint. It only keeps the event loop free.

What is not acceptable is calling blocking `sqlite3` functions directly inside an
`async def` endpoint. That stalls the event loop for every other request.

## Rebuilding the index

Because the database is derived from the file tree, a rebuild has to be a normal, tested
operation rather than an emergency procedure. Keep it as an explicit command, make it
idempotent, and have it record which git commit of the stores it was built from. That commit
identifier is what lets you tell a stale index from a corrupt one.
