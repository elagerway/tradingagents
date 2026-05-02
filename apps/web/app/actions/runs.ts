"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
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
] as const;

const createRunSchema = z
  .object({
    ticker: z.string().min(1).max(10).regex(/^[A-Z0-9.-]+$/),
    trade_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    llm_provider: z.enum(PROVIDERS),
    deep_think_llm: z.string().min(1).optional(),
    quick_think_llm: z.string().min(1).optional(),
  })
  .refine(
    (data) =>
      data.llm_provider !== "openrouter" ||
      (!!data.deep_think_llm && !!data.quick_think_llm),
    { message: "openrouter requires deep_think_llm and quick_think_llm" },
  );

export async function createRun(formData: FormData) {
  const parsed = createRunSchema.safeParse({
    ticker: (formData.get("ticker") as string)?.toUpperCase(),
    trade_date: formData.get("trade_date"),
    llm_provider: formData.get("llm_provider"),
    deep_think_llm: formData.get("deep_think_llm") || undefined,
    quick_think_llm: formData.get("quick_think_llm") || undefined,
  });
  if (!parsed.success) {
    redirect("/runs/new?error=invalid");
  }

  const config: Record<string, string> = {
    llm_provider: parsed.data.llm_provider,
  };
  if (parsed.data.deep_think_llm) {
    config.deep_think_llm = parsed.data.deep_think_llm;
  }
  if (parsed.data.quick_think_llm) {
    config.quick_think_llm = parsed.data.quick_think_llm;
  }

  const supabase = await createClient();
  const { data, error } = await supabase.rpc("create_run", {
    input: {
      ticker: parsed.data.ticker,
      trade_date: parsed.data.trade_date,
      config,
    },
  });

  if (error || !data) {
    redirect("/runs/new?error=server");
  }

  redirect(`/runs/${data}`);
}
