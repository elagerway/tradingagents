-- 22_vault_save_key.sql
-- Asserts vault_save_key(provider, plaintext) encrypts plaintext and
-- upserts into api_keys for the authenticated user.

begin;
select plan(4);

select tests.create_supabase_user('alice');
select tests.authenticate_as('alice');

-- The function must exist.
select has_function(
  'public', 'vault_save_key', array['text', 'text'],
  'vault_save_key(text, text) exists'
);

-- Calling it inserts a row with non-empty ciphertext that does NOT contain
-- the plaintext bytes.
select lives_ok(
  $$ select public.vault_save_key('openai', 'sk-test-alice-secret') $$,
  'vault_save_key call succeeds'
);

select results_eq(
  $$ select count(*)::int from public.api_keys
       where user_id = tests.get_supabase_uid('alice')
         and provider = 'openai'
         and length(key_encrypted) > 0
         and position('sk-test-alice-secret'::bytea in key_encrypted) = 0 $$,
  $$ values (1) $$,
  'plaintext is not present in stored ciphertext'
);

-- Calling again with same provider upserts (replaces) the row.
select lives_ok(
  $$ select public.vault_save_key('openai', 'sk-test-alice-NEW') $$,
  'second call upserts'
);

select * from finish();
rollback;
