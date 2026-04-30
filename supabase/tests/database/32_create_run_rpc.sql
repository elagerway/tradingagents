-- 32_create_run_rpc.sql
-- Asserts create_run(input jsonb) inserts a runs row owned by the
-- authenticated user, and rejects waitlisted users.

begin;
select plan(5);

select tests.create_supabase_user('alice');
select tests.create_supabase_user('waitlisted');

-- Mark alice as allowed; waitlisted stays null.
set role service_role;
update public.profiles set allowed_at = now()
  where id = tests.get_supabase_uid('alice');
reset role;

-- Function exists.
select has_function(
  'public', 'create_run', array['jsonb'],
  'create_run(jsonb) exists'
);

-- Allowed user can create a run.
select tests.authenticate_as('alice');

select isa_ok(
  (select public.create_run(
    jsonb_build_object(
      'ticker', 'NVDA',
      'trade_date', '2026-01-15',
      'config', jsonb_build_object('llm_provider', 'openai')
    )
  )),
  'uuid',
  'create_run returns a uuid'
);

select results_eq(
  $$ select count(*)::int from public.runs
       where user_id = tests.get_supabase_uid('alice')
         and ticker = 'NVDA' $$,
  $$ values (1) $$,
  'create_run inserted the row'
);

-- Waitlisted user is rejected.
select tests.clear_authentication();
select tests.authenticate_as('waitlisted');

select throws_ok(
  $$ select public.create_run(
       jsonb_build_object(
         'ticker', 'AAPL',
         'trade_date', '2026-01-15',
         'config', '{}'::jsonb
       )
     ) $$,
  null, null,
  'waitlisted user cannot create_run'
);

select results_eq(
  $$ select count(*)::int from public.runs
       where user_id = tests.get_supabase_uid('waitlisted') $$,
  $$ values (0) $$,
  'no row inserted for waitlisted user'
);

select * from finish();
rollback;
