-- 23_vault_load_keys.sql
-- Asserts vault_load_keys(user_id, providers[]) returns the original
-- plaintext for the requested providers, bumps last_used_at, and is
-- callable only by service_role.

begin;
select plan(5);

select tests.create_supabase_user('alice');
select tests.authenticate_as('alice');

-- Save two keys as alice.
select public.vault_save_key('openai',    'sk-alice-openai');
select public.vault_save_key('anthropic', 'sk-alice-anthropic');

-- Reset to no role; impersonate the service role for vault_load_keys.
select tests.clear_authentication();
set role service_role;

-- Function exists.
select has_function(
  'public', 'vault_load_keys', array['uuid', 'text[]'],
  'vault_load_keys(uuid, text[]) exists'
);

-- Returns the requested providers only, with correct plaintext.
select results_eq(
  $$ select provider, plaintext from public.vault_load_keys(
       (select id from auth.users where email like 'alice%'),
       array['openai']::text[]
     ) order by provider $$,
  $$ values ('openai'::text, 'sk-alice-openai'::text) $$,
  'returns only requested providers with correct plaintext'
);

select results_eq(
  $$ select count(*)::int from public.vault_load_keys(
       (select id from auth.users where email like 'alice%'),
       array['openai','anthropic']::text[]
     ) $$,
  $$ values (2) $$,
  'returns multiple providers when requested'
);

-- last_used_at gets bumped after a load.
select isnt(
  (select last_used_at from public.api_keys
     where provider = 'openai'
       and user_id = (select id from auth.users where email like 'alice%')),
  null::timestamptz,
  'last_used_at is updated by vault_load_keys'
);

-- Authenticated role cannot call vault_load_keys.
reset role;
select tests.authenticate_as('alice');
select throws_ok(
  $$ select * from public.vault_load_keys(auth.uid(), array['openai']::text[]) $$,
  '42501',
  null,
  'authenticated user cannot call vault_load_keys'
);

select * from finish();
rollback;
