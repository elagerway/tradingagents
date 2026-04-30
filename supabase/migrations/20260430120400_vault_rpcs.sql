-- 20260430120400_vault_rpcs.sql
-- BYO API key vault RPCs:
--   - vault_save_key(provider, plaintext): encrypt + upsert
--   - vault_load_keys(uid, providers[]): decrypt subset (service_role only)

-- ----- vault_save_key ---------------------------------------------------

create function public.vault_save_key(
  p_provider  text,
  p_plaintext text
)
returns void
language plpgsql
security definer
set search_path = public, vault, pgsodium
as $$
declare
  v_user_id   uuid := auth.uid();
  v_secret_id uuid;
  v_cipher    bytea;
begin
  if v_user_id is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;

  -- Encrypt via vault.create_secret (SECURITY DEFINER, owned by supabase_admin)
  -- which uses pgsodium AEAD-det encryption internally.  We pass the secret
  -- under a namespaced name so the vault entry can be cleaned up afterward.
  -- The raw ciphertext is then stored in api_keys.key_encrypted as bytea so
  -- all key material stays in this table and vault.secrets is used only as
  -- a transient encryption oracle.
  v_secret_id := vault.create_secret(
    p_plaintext,
    v_user_id::text || '/' || p_provider
  );

  -- Read back the base64-encoded ciphertext and convert to bytea.
  select decode(secret, 'base64')
    into v_cipher
    from vault.secrets
   where id = v_secret_id;

  -- Discard the vault entry – we only needed the encryption service.
  delete from vault.secrets where id = v_secret_id;

  insert into public.api_keys (user_id, provider, key_encrypted)
  values (v_user_id, p_provider, v_cipher)
  on conflict (user_id, provider) do update
    set key_encrypted = excluded.key_encrypted,
        created_at    = now(),
        last_used_at  = null;
end;
$$;

-- Only authenticated users can call it. Service role doesn't need it
-- (Plan 2 will use vault_load_keys, not vault_save_key).
revoke all on function public.vault_save_key(text, text) from public, anon;
grant execute on function public.vault_save_key(text, text) to authenticated;
