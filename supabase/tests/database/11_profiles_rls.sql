-- 11_profiles_rls.sql
-- Asserts that a user can read only their own profile.

begin;
select plan(3);

-- Create two users via the test helpers.
select tests.create_supabase_user('alice');
select tests.create_supabase_user('bob');

-- Authenticate as alice and confirm she sees only her row.
select tests.authenticate_as('alice');

select results_eq(
  $$ select count(*)::int from public.profiles where id = tests.get_supabase_uid('alice') $$,
  $$ values (1) $$,
  'alice can see her own profile'
);

select results_eq(
  $$ select count(*)::int from public.profiles where id = tests.get_supabase_uid('bob') $$,
  $$ values (0) $$,
  'alice cannot see bob''s profile'
);

select results_eq(
  $$ select count(*)::int from public.profiles $$,
  $$ values (1) $$,
  'alice''s unfiltered query returns only her own row'
);

select * from finish();
rollback;
