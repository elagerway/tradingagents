-- 20260430120000_init_schema.sql
-- Creates the profiles table and a trigger that auto-creates a profile
-- whenever a new auth.users row appears.

create table public.profiles (
  id           uuid primary key references auth.users(id) on delete cascade,
  email        text not null,
  display_name text,
  allowed_at   timestamptz,
  created_at   timestamptz not null default now()
);

comment on column public.profiles.allowed_at is
  'Null = waitlisted. Non-null = beta member; set by an admin when granting access.';

-- Trigger: when a new auth.users row is inserted, create a corresponding profile.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();
