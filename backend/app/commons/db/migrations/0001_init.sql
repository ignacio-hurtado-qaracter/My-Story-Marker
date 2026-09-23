-- FR-IDX-02, FR-IDX-05. The derived entity index.
--
-- Every row here is derived from a file in the tree and can be dropped and rebuilt with no
-- loss. "The entity index is derived, never a source. An index entry with no backing record
-- in the stores is a bug." That is why `path` is NOT NULL and why `/index/status` reports an
-- orphan count that AC 6 asserts is zero: retrieval must not be able to introduce a fact, it
-- can only choose among facts that exist.
--
-- `id` is an explicit INTEGER PRIMARY KEY because two other tables point at it: the FTS5 row
-- and the vec0 row of an entity share its value. A table keyed only by (entity_id, kind)
-- still has a rowid, but an implicit one, and VACUUM may renumber an implicit rowid - which
-- would silently re-point every vector at another entity. An alias of the rowid is stable.
--
-- `updated_at` is nullable. It is the time of the last write of the backing file recorded
-- in the provenance log (FR-STORE-04), and NULL when the file was never written through the
-- backend (seeded by hand, or edited only outside it). It is never the wall clock of the
-- rebuild: AC 6 asserts that two rebuilds of the same tree yield identical rows, and a
-- rebuild timestamp would make that false by construction.

create table entity (
    id           integer primary key,
    entity_id    text not null,
    kind         text not null,
    path         text not null,
    text         text not null,
    content_hash text not null,
    updated_at   text,
    unique (entity_id, kind)
);

create index entity_path on entity (path);
create index entity_kind on entity (kind);

-- FR-IDX-07. What the vectors were built with. A change here forces a rebuild, because
-- vectors from two different models are not comparable and a cosine distance between them is
-- a number with no meaning.
create table index_metadata (
    key   text primary key,
    value text not null
);
