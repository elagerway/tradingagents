// apps/web/app/actions/keys.ts
"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";
import { z } from "zod";

const PROVIDERS = [
  "openai",
  "anthropic",
  "google",
  "xai",
  "deepseek",
  "dashscope",
  "zhipu",
  "openrouter",
  "alpha_vantage",
] as const;

const saveKeySchema = z.object({
  provider: z.enum(PROVIDERS),
  plaintext: z.string().min(8).max(500),
});

export async function saveApiKey(formData: FormData) {
  const parsed = saveKeySchema.safeParse({
    provider: formData.get("provider"),
    plaintext: formData.get("plaintext"),
  });
  if (!parsed.success) {
    return { error: "Invalid input" };
  }

  const supabase = await createClient();
  const { error } = await supabase.rpc("vault_save_key", {
    p_provider: parsed.data.provider,
    p_plaintext: parsed.data.plaintext,
  });

  if (error) {
    return { error: error.message };
  }
  revalidatePath("/settings");
  return { ok: true };
}

export async function deleteApiKey(formData: FormData) {
  const provider = formData.get("provider");
  if (typeof provider !== "string") {
    return { error: "Invalid provider" };
  }

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { error: "Not authenticated" };

  const { error } = await supabase
    .from("api_keys")
    .delete()
    .eq("user_id", user.id)
    .eq("provider", provider);

  if (error) {
    return { error: error.message };
  }
  revalidatePath("/settings");
  return { ok: true };
}
