-- 20260430120600_create_run_rpc.sql
-- create_run(input jsonb) — SECURITY DEFINER insert into runs.
--
-- input shape: {
--   "ticker":     text,
--   "trade_date": date (ISO),
--   "config":     jsonb
-- }
--
-- Validates:
--   - caller is authenticated
--   - caller has profiles.allowed_at set (not waitlisted)
--   - required keys are present and well-typed

create function public.create_run(input jsonb)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id   uuid := auth.uid();
  v_allowed   timestamptz;
  v_ticker    text;
  v_trade_date date;
  v_config    jsonb;
  v_run_id    uuid;
begin
  if v_user_id is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;

  select allowed_at into v_allowed
    from public.profiles
   where id = v_user_id;

  if v_allowed is null then
    raise exception 'beta access pending' using errcode = '42501';
  end if;

  v_ticker     := input->>'ticker';
  v_trade_date := (input->>'trade_date')::date;
  v_config     := input->'config';

  if v_ticker is null or length(v_ticker) = 0 then
    raise exception 'ticker is required' using errcode = '22023';
  end if;
  if v_trade_date is null then
    raise exception 'trade_date is required' using errcode = '22023';
  end if;
  if v_config is null then
    raise exception 'config is required' using errcode = '22023';
  end if;

  insert into public.runs (user_id, ticker, trade_date, config)
  values (v_user_id, v_ticker, v_trade_date, v_config)
  returning id into v_run_id;

  return v_run_id;
end;
$$;

revoke all on function public.create_run(jsonb) from public, anon;
grant execute on function public.create_run(jsonb) to authenticated;
