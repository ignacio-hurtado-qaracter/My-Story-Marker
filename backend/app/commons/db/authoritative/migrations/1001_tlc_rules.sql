-- Spec 005 (B1). Rules implied by the TLA+ block's TLC counterexamples (spec 013):
-- CE2: one run id per validation run, so chapter retries are countable from persisted rows.
-- CE3: rejected chapter texts are kept, never deleted (D6).
-- CE4: the repair rounds that led to a blocked version, set with the status.

alter table validator_result add column run_id text;
create index validator_result_by_run on validator_result (novel_id, version, chapter, point, run_id);

create table chapter_attempt (
    id              integer primary key,
    novel_id        text not null,
    version         integer not null,
    chapter         integer not null,
    attempt         integer not null,
    text            text not null,
    hash            text not null,
    reason          text not null default '',
    created_at      text not null,
    unique (novel_id, version, chapter, attempt),
    foreign key (novel_id, version) references novel_version (novel_id, version)
);

alter table novel_version add column repair_rounds integer not null default 0;
