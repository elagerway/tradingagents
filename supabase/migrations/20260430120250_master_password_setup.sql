-- 20260430120250_master_password_setup.sql
-- Creates a Vault-stored master password used by vault_save_key /
-- vault_load_keys for symmetric encryption of BYO API keys via pgcrypto.
--
-- Why pgcrypto and not pgsodium directly:
-- pgsodium.crypto_aead_det_encrypt is gated behind the `pgsodium_keyiduser`
-- role, and `postgres` lacks `ADMIN OPTION` to grant it in Supabase's bundled
-- local image. pgcrypto's pgp_sym_* functions are unrestricted and give us
-- equivalent symmetric AEAD-with-prefix-AAD semantics.

create extension if not exists pgcrypto;

-- Idempotent: only create the secret if it doesn't already exist. Re-running
-- this migration MUST NOT replace the password — that would render every
-- previously-encrypted api_key undecryptable.
do $$
declare
  v_secret_id uuid;
begin
  select id into v_secret_id
    from vault.secrets
   where name = 'tradingagents_master_password';

  if v_secret_id is null then
    perform vault.create_secret(
      -- 32 random bytes, base64-encoded -> a strong symmetric password
      encode(gen_random_bytes(32), 'base64'),
      'tradingagents_master_password',
      'Master password for BYO API key encryption (pgp_sym_*).'
    );
  end if;
end;
$$;

-- Helper: returns the plaintext master password. Locked down to nothing — only
-- callable from inside SECURITY DEFINER vault_save_key / vault_load_keys
-- functions running as `postgres`.
create function public._byo_master_password()
returns text
language sql
stable
security definer
set search_path = vault, public
as $$
  select decrypted_secret
    from vault.decrypted_secrets
   where name = 'tradingagents_master_password'
$$;

revoke all on function public._byo_master_password() from public, anon, authenticated;
