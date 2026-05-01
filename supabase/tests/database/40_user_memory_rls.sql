-- 40_user_memory_rls.sql
-- Asserts: user_memory table exists with the right shape; RLS isolates users;
-- service_role can write/update for ingestion + reflection.

begin;
select plan(8);

select has_table('public', 'user_memory', 'user_memory table exists');

select has_column('public', 'user_memory', 'user_id', 'has user_id');
select has_column('public', 'user_memory', 'ticker', 'has ticker');
select has_column('public', 'user_memory', 'trade_date', 'has trade_date');
select has_column('public', 'user_memory', 'decision', 'has decision');
select has_column('public', 'user_memory', 'resolved', 'has resolved');
select has_column('public', 'user_memory', 'reflection', 'has reflection');

-- RLS: users can SELECT own rows but cannot SELECT others'
select tests.create_supabase_user('alice');
select tests.create_supabase_user('bob');

set role service_role;
insert into public.user_memory (user_id, ticker, trade_date, rating, decision)
values
  (tests.get_supabase_uid('alice'), 'NVDA', '2026-01-15', 'Buy', 'alice decision'),
  (tests.get_supabase_uid('bob'),   'AAPL', '2026-01-15', 'Buy', 'bob decision');
reset role;

select tests.authenticate_as('alice');
select results_eq(
  $$ select count(*)::int from public.user_memory $$,
  $$ values (1) $$,
  'alice sees only her own memory entries'
);

select * from finish();
rollback;
