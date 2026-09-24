-- Spec 005 (B1), contract K1. The authoritative story bible. Range 1000-1099 is B1's
-- (spec 004 § 5.4). Nothing here is deleted by the application: versions are new rows.

create table novel (
    id              text primary key,
    session_id      text not null,
    title           text,
    dedication      text,
    recipient_name  text,
    status          text not null default 'draft',
    created_at      text not null,
    updated_at      text not null
);

create table brief (
    novel_id        text primary key references novel (id),
    data_json       text not null,
    schema_version  text not null default '1',
    valid           integer not null default 0,
    created_at      text not null,
    updated_at      text not null
);

create table fact (
    id              integer primary key,
    novel_id        text not null references novel (id),
    key             text not null,
    value           text not null,
    kind            text not null,
    source          text not null check (source in ('interview', 'free_text', 'planner')),
    mandatory       integer not null default 0,
    created_at      text not null,
    updated_at      text not null,
    unique (novel_id, key)
);

create table fact_usage (
    id              integer primary key,
    fact_id         integer not null references fact (id),
    version         integer not null,
    chapter         integer not null,
    scene           integer not null,
    created_at      text not null,
    unique (fact_id, version, chapter, scene)
);
create index fact_usage_by_fact on fact_usage (fact_id);

create table character (
    id              text not null,
    novel_id        text not null references novel (id),
    name            text not null,
    role            text not null default '',
    birth_date      text,
    description     text not null default '',
    fact_id         integer references fact (id),
    primary key (novel_id, id)
);

create table place (
    id              text not null,
    novel_id        text not null references novel (id),
    name            text not null,
    description     text not null default '',
    fact_id         integer references fact (id),
    primary key (novel_id, id)
);

create table chronology_event (
    id              text not null,
    novel_id        text not null references novel (id),
    seq             integer not null,
    story_date      text,
    chapter         integer,
    scene           integer,
    place_id        text,
    description     text not null default '',
    kind            text not null default 'normal' check (kind in ('normal', 'death', 'departure')),
    primary key (novel_id, id),
    unique (novel_id, seq),
    foreign key (novel_id, place_id) references place (novel_id, id)
);

create table event_participant (
    novel_id        text not null,
    event_id        text not null,
    character_id    text not null,
    age_at_event    integer,
    primary key (novel_id, event_id, character_id),
    foreign key (novel_id, event_id) references chronology_event (novel_id, id),
    foreign key (novel_id, character_id) references character (novel_id, id)
);

create table novel_version (
    novel_id        text not null references novel (id),
    version         integer not null,
    parent_version  integer,
    status          text not null default 'draft' check (status in ('draft', 'published', 'blocked')),
    changed_chapters text not null default '[]',
    note            text not null default '',
    trace_id        text,
    created_at      text not null,
    updated_at      text not null,
    primary key (novel_id, version)
);

create table chapter_version (
    novel_id        text not null,
    version         integer not null,
    chapter         integer not null,
    title           text not null default '',
    text            text not null,
    hash            text not null,
    summary         text not null default '',
    word_count      integer not null,
    created_at      text not null,
    primary key (novel_id, version, chapter),
    foreign key (novel_id, version) references novel_version (novel_id, version)
);

create table checkpoint (
    novel_id        text not null,
    version         integer not null,
    chapter         integer not null,
    status          text not null check (status in ('pending', 'in_progress', 'complete', 'failed')),
    detail          text not null default '',
    updated_at      text not null,
    primary key (novel_id, version, chapter),
    foreign key (novel_id, version) references novel_version (novel_id, version)
);

create table forbidden_term (
    id              integer primary key,
    scope           text not null check (scope in ('global', 'novel')),
    novel_id        text references novel (id),
    term            text not null,
    reason          text not null default '',
    created_at      text not null,
    check ((scope = 'global' and novel_id is null) or (scope = 'novel' and novel_id is not null))
);
create unique index forbidden_term_unique on forbidden_term (scope, coalesce(novel_id, ''), term);

create table policy_decision (
    id              integer primary key,
    novel_id        text,
    version         integer,
    chapter         integer,
    scene           integer,
    policy          text not null,
    decision        text not null,
    term            text,
    detail          text not null default '',
    attempt         integer,
    trace_id        text,
    created_at      text not null
);
create index policy_decision_by_novel on policy_decision (novel_id);

create table validator_result (
    id              integer primary key,
    novel_id        text not null,
    version         integer,
    chapter         integer,
    scene           integer,
    name            text not null,
    point           text not null,
    passed          integer not null,
    score           real,
    evidence_json   text not null default '[]',
    explanation     text not null default '',
    trace_id        text,
    created_at      text not null
);
create index validator_result_by_novel on validator_result (novel_id, version);

create table llm_call (
    id              integer primary key,
    novel_id        text,
    version         integer,
    chapter         integer,
    role            text not null,
    model           text not null,
    input_tokens    integer not null default 0,
    output_tokens   integer not null default 0,
    cache_read      integer not null default 0,
    cache_creation  integer not null default 0,
    cost_usd        real not null default 0,
    latency_s       real not null default 0,
    attempts        integer not null default 1,
    prompt_name     text,
    prompt_version  text,
    trace_id        text,
    ts              text not null
);
create index llm_call_by_novel on llm_call (novel_id, chapter);
