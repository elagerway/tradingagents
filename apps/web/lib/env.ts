// apps/web/lib/env.ts
export const env = {
  SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL!,
  SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  RENDER_API_BASE_URL: process.env.NEXT_PUBLIC_RENDER_API_BASE_URL!,
  APP_URL: process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000",
};

if (!env.SUPABASE_URL || !env.SUPABASE_ANON_KEY) {
  throw new Error(
    "Missing required env vars: NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY"
  );
}
if (!env.RENDER_API_BASE_URL) {
  throw new Error("Missing NEXT_PUBLIC_RENDER_API_BASE_URL");
}
