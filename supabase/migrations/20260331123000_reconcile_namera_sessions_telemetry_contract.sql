create schema if not exists namera;

create table if not exists namera.sessions (
    id uuid primary key default gen_random_uuid(),
    names text[] not null default '{}'::text[],
    niche text,
    profile text not null default 'default',
    top_name text,
    top_score double precision,
    num_candidates integer not null default 0,
    created_at timestamptz not null default now()
);

alter table namera.sessions
    add column if not exists names text[] default '{}'::text[],
    add column if not exists niche text,
    add column if not exists profile text default 'default',
    add column if not exists top_name text,
    add column if not exists top_score double precision,
    add column if not exists num_candidates integer default 0,
    add column if not exists created_at timestamptz default now();

alter table namera.sessions
    drop column if exists top_names,
    drop column if exists num_viable,
    drop column if exists input_flags,
    drop column if exists outcome;

update namera.sessions
set
    names = coalesce(names, '{}'::text[]),
    profile = coalesce(profile, 'default'),
    num_candidates = coalesce(num_candidates, coalesce(cardinality(names), 0)),
    created_at = coalesce(created_at, now())
where
    names is null
    or profile is null
    or num_candidates is null
    or created_at is null;

alter table namera.sessions alter column names set default '{}'::text[];
alter table namera.sessions alter column names set not null;
alter table namera.sessions alter column profile set default 'default';
alter table namera.sessions alter column profile set not null;
alter table namera.sessions alter column num_candidates set default 0;
alter table namera.sessions alter column num_candidates set not null;
alter table namera.sessions alter column created_at set default now();
alter table namera.sessions alter column created_at set not null;

alter table namera.sessions enable row level security;

grant usage on schema namera to anon, authenticated, service_role;
revoke all on table namera.sessions from anon, authenticated;
grant insert, select on table namera.sessions to service_role;

drop policy if exists "Allow insert from service role" on namera.sessions;
drop policy if exists "Allow read from service role" on namera.sessions;
