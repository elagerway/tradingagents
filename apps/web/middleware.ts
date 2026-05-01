// apps/web/middleware.ts
import { NextRequest, NextResponse } from "next/server";
import { createMiddlewareClient } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  const response = NextResponse.next({ request });
  const supabase = createMiddlewareClient(request, response);

  // Refresh + validate the access token. Writes updated cookies into
  // both request and response.
  const { data } = await supabase.auth.getClaims();
  const uid = data?.claims?.sub ?? null;

  const { pathname } = request.nextUrl;

  // Always-public paths
  if (pathname === "/login" || pathname.startsWith("/auth/callback")) {
    return response;
  }

  // No session → login
  if (!uid) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  // Allowlist check — single-row read against profiles
  const { data: profile } = await supabase
    .from("profiles")
    .select("allowed_at")
    .eq("id", uid)
    .single();

  if (!profile?.allowed_at) {
    const url = new URL("/login", request.url);
    url.searchParams.set("reason", "waitlisted");
    return NextResponse.redirect(url);
  }

  return response;
}

export const config = {
  matcher: [
    // Run on everything EXCEPT static assets + auth callback (which
    // must run unauthenticated to do the code exchange).
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
