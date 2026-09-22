-- FR-IDX-02. FTS5 over the row text. Always present: selection is FTS5-ranked even when
-- `sqlite-vec` does not load (FR-IDX-03), so this is the half that must never be optional.
--
-- `content=''` makes it an external-content-free table: rows are inserted explicitly by the
-- rebuild rather than mirrored by triggers. Triggers would be less code and would also mean
-- two write paths into the index, and `rebuild()` has to be the only one for AC 6 to hold.

create virtual table entity_fts using fts5(
    entity_id unindexed,
    kind unindexed,
    text,
    tokenize = 'unicode61 remove_diacritics 2'
);
