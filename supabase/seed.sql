-- supabase/seed.sql
-- Local-dev seed: one allowlisted user so /login works on a fresh DB.
-- Runs after migrations on `supabase db reset`.

-- Create a dev user. Email is fixed; password is irrelevant for magic-link.
do $$
declare
  v_user_id uuid;
begin
  -- If the user already exists (re-run), skip.
  select id into v_user_id from auth.users where email = 'dev@snapsonic.local';
  if v_user_id is not null then
    return;
  end if;

  -- supabase_test_helpers will create the user + a matching profiles row
  -- via the on_auth_user_created trigger.
  -- NOTE: called with explicit email param so the email is exactly
  -- 'dev@snapsonic.local' (single-arg form appends '@test.com').
  v_user_id := tests.create_supabase_user('dev', 'dev@snapsonic.local');

  -- Mark allowed.
  update public.profiles
     set allowed_at = now(), display_name = 'Dev'
   where id = v_user_id;
end;
$$;
