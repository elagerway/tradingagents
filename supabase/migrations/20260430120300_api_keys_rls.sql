-- 20260430120300_api_keys_rls.sql
-- Creates the api_keys table holding pgsodium-encrypted BYO LLM keys.
-- key_encrypted is opaque ciphertext; encrypt/decrypt happens only through
-- the SECURITY DEFINER RPCs in 20260430120400_vault_rpcs.sql.

create table public.api_keys (
  user_id        uuid not null references auth.users(id) on delete cascade,
  provider       text not null check (provider in (
    'openai','anthropic','google','xai','deepseek',
    'dashscope','zhipu','openrouter','alpha_vantage'
  )),
  key_encrypted  bytea not null,
  last_used_at   timestamptz,
  created_at     timestamptz not null default now(),
  primary key (user_id, provider)
);

alter table public.api_keys enable row level security;

-- Authenticated users can SEE their own rows (to display masked last-4 in
-- /settings UI), but never the plaintext (which is encrypted in
-- key_encrypted).
create policy "users can select own api_keys"
  on public.api_keys
  for select
  to authenticated
  using (user_id = auth.uid());

-- Authenticated users can DELETE their own rows (UI: "remove key").
create policy "users can delete own api_keys"
  on public.api_keys
  for delete
  to authenticated
  using (user_id = auth.uid());

-- INSERT and UPDATE are denied for `authenticated` — they happen exclusively
-- through vault_save_key() (next migration), which is SECURITY DEFINER and
-- handles encryption.
