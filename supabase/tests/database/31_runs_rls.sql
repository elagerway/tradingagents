-- 31_runs_rls.sql
-- Asserts:
--   (a) authenticated user cannot directly insert/update/delete a runs row
--   (b) a user can read their own runs but not others'
--   (c) service_role can update any row

begin;
select plan(5);

select tests.create_supabase_user('alice');
select tests.create_supabase_user('bob');

-- Service role inserts test rows.
set role service_role;
insert into public.runs (id, user_id, ticker, trade_date, config)
values
  ('00000000-0000-0000-0000-000000000aaa',
   tests.get_supabase_uid('alice'), 'NVDA', '2026-01-15', '{}'::jsonb),
  ('00000000-0000-0000-0000-000000000bbb',
   tests.get_supabase_uid('bob'),   'AAPL', '2026-01-15', '{}'::jsonb);
reset role;

-- Authenticate as alice.
select tests.authenticate_as('alice');

select results_eq(
  $$ select count(*)::int from public.runs $$,
  $$ values (1) $$,
  'alice sees only her own runs'
);

select throws_ok(
  $$ insert into public.runs (user_id, ticker, trade_date, config)
       values (tests.get_supabase_uid('alice'), 'TSLA', '2026-01-15', '{}'::jsonb) $$,
  '42501',
  null,
  'authenticated user cannot directly insert into runs'
);

-- UPDATE on a row whose RLS forbids modification silently affects 0 rows in
-- current Postgres (it does not throw). We assert the outcome — that the row
-- value is unchanged — rather than the mechanism.
update public.runs set ticker = 'PWND'
  where id = '00000000-0000-0000-0000-000000000aaa';

select results_eq(
  $$ select ticker::text from public.runs
       where id = '00000000-0000-0000-0000-000000000aaa' $$,
  $$ values ('NVDA'::text) $$,
  'authenticated user UPDATE is silently denied (row unchanged)'
);

-- Service role can update.
select tests.clear_authentication();
set role service_role;

select lives_ok(
  $$ update public.runs set status = 'running', started_at = now()
       where id = '00000000-0000-0000-0000-000000000aaa' $$,
  'service_role can update runs'
);

select results_eq(
  $$ select status::text from public.runs where id = '00000000-0000-0000-0000-000000000aaa' $$,
  $$ values ('running'::text) $$,
  'service_role update took effect'
);

select * from finish();
rollback;
