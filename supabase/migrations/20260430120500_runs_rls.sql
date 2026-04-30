-- 20260430120500_runs_rls.sql
-- Creates the runs table and enables select-only RLS for users.
-- Inserts go through create_run() (next migration), which is SECURITY DEFINER.
-- Updates go through service_role from the FastAPI worker (Plan 2).

create table public.runs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  ticker          text not null,
  trade_date      date not null,
  status          text not null default 'pending'
                    check (status in ('pending','running','completed','failed')),
  config          jsonb not null,
  events          jsonb not null default '[]'::jsonb,
  final_decision  jsonb,
  error           text,
  created_at      timestamptz not null default now(),
  started_at      timestamptz,
  completed_at    timestamptz
);

create index runs_user_id_created_at_idx
  on public.runs (user_id, created_at desc);

alter table public.runs enable row level security;

-- Users can read their own runs.
create policy "users can select own runs"
  on public.runs
  for select
  to authenticated
  using (user_id = auth.uid());

-- INSERT, UPDATE, DELETE all denied for `authenticated`. Inserts go through
-- create_run() (SECURITY DEFINER); updates happen on the FastAPI side via
-- service_role.
