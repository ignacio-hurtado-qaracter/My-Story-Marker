-- Spec 018 (X03, SEC-01): users and the owner of each novel. Range 1700-1749.
--
-- `local` is the built-in owner of every novel created without one: the CLI pipeline and
-- every novel that existed before this migration. Its password hash `!` is not a bcrypt
-- hash, so nobody can log in as `local`; it is only reachable with AUTH_REQUIRED=0 or from
-- the local CLI / MCP stdio server.
--
-- Briefs, validator results and policy decisions are keyed by `novel_id`; their owner is
-- `novel.owner_id` by join, so no second owner column can drift from the novel's.
create table app_user (
    id              text primary key,
    email           text not null unique,
    password_hash   text not null,
    created_at      text not null
);

insert into app_user (id, email, password_hash, created_at)
    values ('local', 'local@localhost', '!', '2026-09-24T00:00:00+00:00');

alter table novel add column owner_id text references app_user (id);

update novel set owner_id = 'local' where owner_id is null;

create index novel_owner on novel (owner_id);
