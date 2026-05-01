# Hedgentic AI — web app

Next.js 16 (App Router) + Tailwind v4 + shadcn/ui + Supabase SSR auth. Deploys to Vercel.

## Local development

```bash
cd apps/web
pnpm install
pnpm dev
```

Open [http://localhost:3737](http://localhost:3737).

> The dev server runs on **port 3737** (not Next.js's default 3000) because we run multiple Next.js apps locally and 3000 is too crowded. Override via `pnpm dev -p <other-port>` if you need a different one.

## Required env vars

Create `apps/web/.env.local` (gitignored) with:

```
NEXT_PUBLIC_SUPABASE_URL=https://<your-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOi...
NEXT_PUBLIC_RENDER_API_BASE_URL=https://tradingagents-api-XXXX.onrender.com
NEXT_PUBLIC_APP_URL=http://localhost:3737
```

For production, these are set in Vercel project settings (`vercel env add` or dashboard).

## Tests

```bash
pnpm tsc --noEmit       # type-check
pnpm build              # production build (also catches more errors)
```

## Architecture

See [`docs/superpowers/specs/2026-04-30-tradingagents-app-design.md`](../../docs/superpowers/specs/2026-04-30-tradingagents-app-design.md) for the system-level design.
