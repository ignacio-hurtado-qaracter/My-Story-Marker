-- FR-IDX-02. FTS5 over the row text. Always present: selection is FTS5-ranked even when
-- `sqlite-vec` does not load (FR-IDX-03), so this is the half that must never be optional.
--
-- A regular FTS5 table, holding its own copy of the columns, and neither contentless
-- (`content=''`) nor external-content. A contentless table cannot return `entity_id` and
-- `kind` from a MATCH, which is the whole of what a search answers. Rows are inserted
-- explicitly by the index module, with the FTS rowid equal to `entity.id`, rather than
-- mirrored by triggers: triggers would be less code and would also mean a second write path
-- into the index, and the rebuild and the incremental update have to be the only ones for
-- AC 6 to hold.

create virtual table entity_fts using fts5(
    entity_id unindexed,
    kind unindexed,
    text,
    tokenize = 'unicode61 remove_diacritics 2'
);
