-- 20260430120400_vault_rpcs.sql
-- BYO API key vault RPCs (pgcrypto symmetric encryption with prefix-AAD):
--   - vault_save_key(provider, plaintext): encrypt + upsert
--   - vault_load_keys(uid, providers[]): decrypt subset (service_role only)
--
-- Encryption details:
--   - Master password lives in Supabase Vault (see 20260430120250_master_password_setup.sql)
--   - The plaintext is prefixed with `<user_id>:` before encryption to give
--     us AAD-equivalent: a row copied to a different user will fail prefix
--     verification on decrypt, even though pgp_sym_decrypt itself succeeds.
--   - pgp_sym_encrypt uses AES-256-CFB internally with random IV per call.

-- ----- vault_save_key ---------------------------------------------------

create function public.vault_save_key(
  p_provider  text,
  p_plaintext text
)
returns void
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  v_user_id  uuid := auth.uid();
  v_password text := public._byo_master_password();
  v_payload  text;
  v_cipher   bytea;
begin
  if v_user_id is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;

  if v_password is null then
    raise exception 'master password not configured' using errcode = '55000';
  end if;

  -- Prefix-AAD: bind ciphertext to the user that owns it.
  v_payload := v_user_id::text || ':' || p_plaintext;

  v_cipher := extensions.pgp_sym_encrypt(
    v_payload,
    v_password,
    'cipher-algo=aes256, compress-algo=2, s2k-mode=3'
  )::bytea;

  insert into public.api_keys (user_id, provider, key_encrypted)
  values (v_user_id, p_provider, v_cipher)
  on conflict (user_id, provider) do update
    set key_encrypted = excluded.key_encrypted,
        created_at    = now(),
        last_used_at  = null;
end;
$$;

revoke all on function public.vault_save_key(text, text) from public, anon;
grant execute on function public.vault_save_key(text, text) to authenticated;
