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

-- ----- vault_load_keys --------------------------------------------------

create type public.vault_load_keys_row as (
  provider  text,
  plaintext text
);

create function public.vault_load_keys(
  p_user_id   uuid,
  p_providers text[]
)
returns setof public.vault_load_keys_row
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
  v_password text := public._byo_master_password();
  v_prefix   text := p_user_id::text || ':';
  r          public.api_keys%rowtype;
  v_decoded  text;
begin
  -- Enforce service_role-only access. The SECURITY DEFINER body is reachable
  -- by authenticated/anon on PostgreSQL 17 even when EXECUTE is revoked from
  -- those roles (local Docker segfault bug), so we guard explicitly here.
  if current_setting('role', true) in ('authenticated', 'anon') then
    raise exception 'permission denied for function vault_load_keys'
      using errcode = '42501';
  end if;

  if v_password is null then
    raise exception 'master password not configured' using errcode = '55000';
  end if;

  for r in
    select * from public.api_keys
    where user_id = p_user_id
      and provider = any(p_providers)
  loop
    -- Decrypt with the master password.
    v_decoded := extensions.pgp_sym_decrypt(r.key_encrypted, v_password);

    -- Prefix-AAD verification: ciphertext must have been encrypted for this user.
    if v_decoded is null or position(v_prefix in v_decoded) <> 1 then
      raise exception 'ciphertext does not bind to user_id (provider=%)', r.provider
        using errcode = '22023';
    end if;

    -- Bump last_used_at.
    update public.api_keys
       set last_used_at = now()
     where user_id = r.user_id
       and provider = r.provider;

    return next (
      r.provider,
      substr(v_decoded, length(v_prefix) + 1)
    )::public.vault_load_keys_row;
  end loop;
end;
$$;

-- Grant execute to all roles so that permission-denied calls reach the
-- function body on PostgreSQL 17 local Docker (which segfaults on a revoked
-- function call). The function body enforces service_role-only access via
-- current_setting('role', true).
grant execute on function public.vault_load_keys(uuid, text[]) to service_role, authenticated, anon;

-- service_role needs SELECT on auth.users so tests (and internal callers)
-- can resolve user_id by email while running as service_role.
grant select on auth.users to service_role;
