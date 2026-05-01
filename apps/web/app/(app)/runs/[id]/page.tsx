// apps/web/app/(app)/runs/[id]/page.tsx
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { RunView } from "./run-view";

export default async function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();
  const { data: run } = await supabase
    .from("runs")
    .select(
      "id, ticker, trade_date, status, created_at, started_at, completed_at, final_decision, error, events"
    )
    .eq("id", id)
    .single();

  if (!run) notFound();

  return <RunView run={run} />;
}
