-- 20260430120200_pgsodium_setup.sql
-- Enables pgsodium and creates a deterministic AEAD key for BYO API key
-- encryption. The key UUID is referenced by encrypt/decrypt RPCs (see later
-- migrations).

create extension if not exists pgsodium;

-- Create the master key once. Idempotent: re-running this migration won't
-- create duplicates because we look it up by name.
do $$
declare
  key_id uuid;
begin
  select id into key_id from pgsodium.key where name = 'tradingagents_byo_keys';

  if key_id is null then
    perform pgsodium.create_key(
      key_type := 'aead-det',
      name := 'tradingagents_byo_keys'
    );
  end if;
end;
$$;

-- Helper: returns the UUID of our master key. Used by RPCs in later migrations.
create function public._byo_master_key_id()
returns uuid
language sql
stable
security definer
set search_path = pgsodium, public
as $$
  select id from pgsodium.key where name = 'tradingagents_byo_keys'
$$;

-- Lock down: only superuser/service_role and our SECURITY DEFINER RPCs may call this.
revoke all on function public._byo_master_key_id() from public, anon, authenticated;
