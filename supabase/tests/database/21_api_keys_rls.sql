-- 21_api_keys_rls.sql
-- Asserts that:
--  (a) a user can select their own api_keys row,
--  (b) a user CANNOT select another user's api_keys row,
--  (c) authenticated users CANNOT insert directly (must use vault_save_key).

begin;
select plan(3);

select tests.create_supabase_user('alice');
select tests.create_supabase_user('bob');

-- Service role inserts a fake api_key row for each (we test plumbing here;
-- real flow uses vault_save_key, tested in 22_vault_save_key.sql).
set role service_role;
insert into public.api_keys (user_id, provider, key_encrypted)
values
  (tests.get_supabase_uid('alice'), 'openai', '\x01'::bytea),
  (tests.get_supabase_uid('bob'),   'openai', '\x02'::bytea);
reset role;

-- Authenticate as alice.
select tests.authenticate_as('alice');

select results_eq(
  $$ select count(*)::int from public.api_keys where user_id = tests.get_supabase_uid('alice') $$,
  $$ values (1) $$,
  'alice sees her own api_key row'
);

select results_eq(
  $$ select count(*)::int from public.api_keys where user_id = tests.get_supabase_uid('bob') $$,
  $$ values (0) $$,
  'alice cannot see bob''s api_keys'
);

select throws_ok(
  $$ insert into public.api_keys (user_id, provider, key_encrypted)
       values (tests.get_supabase_uid('alice'), 'anthropic', '\x03'::bytea) $$,
  '42501',
  null,
  'authenticated user cannot directly insert into api_keys'
);

select * from finish();
rollback;
