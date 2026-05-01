# User runbook — Plan 2 Render Blueprint apply

> **Purpose:** Provision the FastAPI service on Render so we can run the end-to-end smoke and merge Plan 2 to `main`. Estimated total time: **~10 minutes** of your hands-on work plus ~5–8 min of Render build time you can wait through.

> **Status references:** PR https://github.com/elagerway/tradingagents/pull/2 · branch `feature/api` · CI is green (33 tests pass on Ubuntu).

> **Do these in order.** Each task ends with a "✅ Done when…" line so you know what success looks like before moving on.

---

## Task 1 — Apply the Render Blueprint

**Why:** Render's Blueprint reads `render.yaml` from the repo and provisions both services (web + janitor cron) from a single click. We've already committed `render.yaml` on the `feature/api` branch.

**Steps:**

1. Open https://dashboard.render.com/blueprints in your browser. Make sure you're in the right account (top-left team switcher).

2. Click **New Blueprint Instance** (or "New +" → "Blueprint" if the URL above redirects).

3. Render will ask you to connect a GitHub repository. Pick **`elagerway/tradingagents`**.

   - If Render says "no repos found", you may need to install/authorize the Render GitHub App on your account first. Use the link Render provides in that message — it'll take you to GitHub's app authorization screen.

4. **Branch selection:** choose **`feature/api`** (NOT `main` — Plan 2 isn't merged yet).

5. Render parses `render.yaml` and shows you a preview of two services:
   - `tradingagents-api` (web, Docker, Starter plan)
   - `tradingagents-janitor` (cron, runs every 5 min)

   Both should show as "Will be created" (✅).

6. **Don't click Apply yet** — Task 2 has the secret values you need to paste before Render actually creates anything.

**✅ Done when:** the Blueprint preview shows both services and asks you for the `sync: false` env var values. Move to Task 2 (don't navigate away).

---

## Task 2 — Paste 3 secret values into Render's prompt

**Why:** `render.yaml` declares secrets as `sync: false` so they aren't committed to the repo. Render asks for them at apply time and stores them in its secret store going forward.

You'll see a form with three rows (one per secret), each with an empty value field. Paste these in:

### Secret 1 — `SUPABASE_URL`

```
https://rhkxooyygufqgkpxmjvr.supabase.co
```

(This is also in your `.env.local` at line `SUPABASE_URL=`.)

### Secret 2 — `SUPABASE_SERVICE_ROLE_KEY`

Copy the value from your `.env.local` — the line starting with `SUPABASE_SERVICE_ROLE_KEY=`. It's a long JWT-shaped string starting with `eyJhbGciOi...`.

> **If you can't find it:** Supabase dashboard → your project → **Project Settings → API** → in the "Project API keys" section, copy the **`service_role`** key (NOT the `anon` key). Treat this as a password — anyone with it can read/write your entire database bypassing RLS.

### Secret 3 — `SUPABASE_JWT_SECRET`

Supabase dashboard → your project → **Project Settings → API** → scroll down to **"JWT Settings"** → click "Reveal" next to **"JWT Secret"** → copy the value.

> Looks like `your-super-secret-jwt-token-with-at-least-32-characters-long` or a long base64-ish string. Render uses this to verify Supabase-issued user JWTs (ours uses HS256 by default).

> If your project uses ES256/RS256 instead (newer Supabase projects), the JWT Secret field may be empty. In that case, paste an empty string or any placeholder — the FastAPI code falls back to fetching the JWKS endpoint automatically.

### Apply

Once all three fields have values, click **Apply** (or "Create New Resources").

**✅ Done when:** Render shows two services in the dashboard and starts building the Docker image. The first build takes ~5–8 minutes.

---

## Task 3 — Paste the deployed Render service URL back into chat

**Why:** I need the URL to run the cURL smoke (Task 5 in chat).

**Steps:**

1. Wait for the build to finish. Render shows a green "Deploy live" status when it's ready.

   - Watch the **Logs** tab during the build. If something fails, copy the last ~50 log lines and paste them in chat — I'll diagnose.

2. Once live, click into the `tradingagents-api` service. The URL is shown at the top of the page, under the service name. Format:

   ```
   https://tradingagents-api-XXXX.onrender.com
   ```

3. **Quick sanity check** before pasting back:

   ```bash
   curl -s https://tradingagents-api-XXXX.onrender.com/healthz
   ```

   Expected response:

   ```json
   {"status":"ok"}
   ```

   If you get a different response (e.g. an HTML error page or a connection error), copy the response into chat instead of the URL — I'll debug.

4. Paste the URL into chat as `RENDER_URL=https://...onrender.com` (or just paste the URL on its own line; I'll figure it out).

**✅ Done when:** I have the URL and it returns `{"status":"ok"}` for `/healthz`.

---

## Task 4 — Allowlist a real Supabase user (one-time)

**Why:** Plan 2's `POST /runs/{id}/start` checks `profiles.allowed_at` (the beta gate from Plan 1's `create_run` RPC). Plan 1's `seed.sql` only ran against the LOCAL Supabase — your Cloud project has zero allowlisted users right now. Without this step, the smoke test will fail at the auth gate.

You have two paths. Pick whichever you prefer:

### Path A — Use your real email (recommended for ongoing dev)

1. Supabase dashboard → your project → **Authentication → Users**.
2. Click **Add user** → choose **"Send invitation"** or **"Create new user"**.
3. Enter your real email; Supabase emails you a magic link. Click it.

4. Once the user appears in the Users table, switch to **SQL Editor** (left sidebar) and run:

   ```sql
   update public.profiles
      set allowed_at = now()
    where id = (select id from auth.users where email = '<your-email>');
   ```

5. Verify:

   ```sql
   select au.email, p.allowed_at
     from public.profiles p
     join auth.users au on p.id = au.id
    where p.allowed_at is not null;
   ```

   Should show one row with your email + a recent timestamp.

### Path B — Synthetic test user (faster, throwaway)

1. Supabase dashboard → SQL Editor → run this entire block:

   ```sql
   -- Create a synthetic user with a fixed email
   insert into auth.users (id, email, raw_user_meta_data, raw_app_meta_data, created_at, updated_at)
   values (
     gen_random_uuid(),
     'smoke@snapsonic.local',
     '{"test_identifier":"smoke"}'::jsonb,
     '{}'::jsonb,
     now(),
     now()
   );

   -- Allowlist it
   update public.profiles
      set allowed_at = now()
    where id = (select id from auth.users where email = 'smoke@snapsonic.local');

   -- Capture the user_id for the smoke test
   select id from auth.users where email = 'smoke@snapsonic.local';
   ```

2. Copy the UUID from the last query and paste it into chat **after** the Render URL.

**✅ Done when:** at least one row in `public.profiles` has a non-null `allowed_at`, and you've shared either your email (Path A) or the user UUID (Path B) in chat.

---

## After all 4 tasks

Reply in chat with:

```
RENDER_URL=https://tradingagents-api-XXXX.onrender.com
USER_EMAIL=<your email>           # if Path A
USER_ID=<uuid from query>         # if Path B
```

I'll then:

1. Generate an HS256 JWT for that user signed with `SUPABASE_JWT_SECRET`.
2. Manually create a `pending` `runs` row for the smoke test.
3. POST `/runs/{run_id}/start` against the Render URL with the JWT.
4. GET `/runs/{run_id}/stream` to watch the fake-engine event sequence.
5. Confirm the run row transitions through `running` → `completed` in Supabase.
6. Mark PR #2 ready and squash-merge to `main`.

---

## If something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| Render build fails on `apt-get update` | Network blip during base image fetch | Click **Manual Deploy → Clear build cache & deploy** in the service settings |
| `/healthz` returns 502 | Container started but uvicorn isn't binding to `$PORT` | Look at Render Logs — should show `Uvicorn running on 0.0.0.0:<PORT>`. If not, the Dockerfile CMD line might have shell-escaped the `$PORT` wrong |
| `/healthz` returns 401 or 422 | Healthcheck endpoint accidentally got auth — shouldn't happen with current code | Paste the response in chat |
| `start_run` returns 400 "No API key configured for openai" | Expected if you haven't called `vault_save_key` for the test user. Path B test users won't have keys | We can fix this for the smoke by inserting into `api_keys` directly via SQL |
| `start_run` returns 401 even with a valid JWT | Likely `SUPABASE_JWT_SECRET` mismatch between Render and Supabase | Re-fetch the secret from Supabase dashboard and update Render's env var |
| `start_run` returns 403 "not your run" | The `runs` row's `user_id` doesn't match the JWT's `sub` | Make sure the row was created with the same `user_id` as the JWT |

Paste any unexpected error in chat — I can diagnose from a single log line or response body.

---

## Why this isn't automated

Two hard blockers prevent me from doing tasks 1–4 myself:

1. **Render account auth.** Render's API requires an API key tied to your account. We agreed not to share API keys in chat (the Render key you shared earlier is treated as burned). Even with a rotated key, putting it back into chat re-creates the same exposure problem. You authorizing access via the Render dashboard is the cleaner path.

2. **Supabase JWT Secret.** This is the single most security-critical secret in the system — anyone with it can mint tokens for any user. Putting it in chat would be a permanent compromise. Pasting it directly into Render's secret store is the only safe path.

If you'd rather automate future runs of this kind of work, the right approach is to set up a CI/CD pipeline (GitHub Actions deploys to Render via Render's Deploy Hook URL, which is per-service and lower-privilege than the account API key). That's worth doing once we're past v1.
