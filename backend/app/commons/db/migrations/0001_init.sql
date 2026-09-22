-- FR-IDX-02, FR-IDX-05. The derived entity index.
--
-- Every row here is derived from a file in the tree and can be dropped and rebuilt with no
-- loss. "The entity index is derived, never a source. An index entry with no backing record
-- in the stores is a bug." That is why `path` is NOT NULL and why `/index/status` reports an
-- orphan count that AC 6 asserts is zero: retrieval must not be able to introduce a fact, it
-- can only choose among facts that exist.

create table entity (
    entity_id    text not null,
    kind         text not null,
    path         text not null,
    text         text not null,
    content_hash text not null,
    updated_at   text not null,
    primary key (entity_id, kind)
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
