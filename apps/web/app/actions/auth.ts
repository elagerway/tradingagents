// apps/web/app/actions/auth.ts
"use server";

import { createClient } from "@/lib/supabase/server";
import { env } from "@/lib/env";
import { redirect } from "next/navigation";
import { z } from "zod";

const emailSchema = z.string().email().max(254);

export async function sendMagicLink(formData: FormData) {
  const email = emailSchema.safeParse(formData.get("email"));
  if (!email.success) {
    redirect("/login?error=invalid_email");
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithOtp({
    email: email.data,
    options: {
      emailRedirectTo: `${env.APP_URL}/auth/callback`,
    },
  });

  if (error) {
    redirect("/login?error=send_failed");
  }
  redirect("/login?sent=1");
}

export async function signOut() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}
