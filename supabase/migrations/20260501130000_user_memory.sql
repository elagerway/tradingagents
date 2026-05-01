-- 20260501130000_user_memory.sql
-- Per-user memory log replacing the upstream TradingMemoryLog's local file.
-- Used by SupabaseMemoryLog (apps/api/src/api/memory_log.py).
--
-- Schema mirrors the parsed dict fields from the upstream's _parse_entry
-- method. The unique constraint on (user_id, ticker, trade_date) replicates
-- the idempotency check at memory.py:43-44.

create table public.user_memory (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  run_id          uuid references public.runs(id) on delete set null,
  ticker          text not null,
  trade_date      date not null,
  rating          text not null,
  decision        text not null,
  resolved        boolean not null default false,
  raw_return      numeric,
  alpha_return    numeric,
  holding_days    smallint,
  reflection      text,
  created_at      timestamptz not null default now(),
  resolved_at     timestamptz,
  unique (user_id, ticker, trade_date)
);

create index user_memory_user_resolved_created_idx
  on public.user_memory (user_id, resolved, created_at desc);

create index user_memory_user_ticker_idx
  on public.user_memory (user_id, ticker, trade_date desc);

alter table public.user_memory enable row level security;

create policy "users can select own memory"
  on public.user_memory
  for select
  to authenticated
  using (user_id = auth.uid());

-- INSERT, UPDATE, DELETE all go through the FastAPI service-role.
-- Memory is engine-managed; users don't manually mutate it.
