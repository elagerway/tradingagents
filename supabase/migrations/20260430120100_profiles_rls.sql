-- 20260430120100_profiles_rls.sql
-- Enables RLS on profiles and adds a self-only select policy.

alter table public.profiles enable row level security;

create policy "users can select own profile"
  on public.profiles
  for select
  to authenticated
  using (id = auth.uid());

-- No insert/update/delete policies for `authenticated`. Profile rows are
-- created by the on_auth_user_created trigger; updates (e.g. setting
-- display_name) will be added in a future plan as a separate Server Action.
