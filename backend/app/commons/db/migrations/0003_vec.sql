-- FR-IDX-03. The vector half, applied only when `sqlite-vec` loads.
--
-- This migration is conditional, which no other one is: the CI matrix runs a cell with the
-- package uninstalled, and "no code path fails for a missing extension". When the extension
-- is absent this file is skipped and recorded as skipped, `/health` reports
-- `vector: unavailable`, and selection falls back to FTS5 alone.
--
-- float[384] is fixed by FR-EMB-02, which accepts only 384-d models precisely so this schema
-- never has to change. Cosine because the embedders produce unit vectors.

create virtual table entity_vec using vec0(
    entity_rowid integer primary key,
    embedding float[384] distance_metric=cosine
);
