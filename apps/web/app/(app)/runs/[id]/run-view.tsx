// apps/web/app/(app)/runs/[id]/run-view.tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AgentTimelineCard,
  type AgentStatus,
} from "@/components/agent-timeline-card";
import {
  EventStreamConsumer,
  type AgentEvent,
} from "@/components/event-stream-consumer";
import { createClient } from "@/lib/supabase/browser";
import { env } from "@/lib/env";

const AGENTS = [
  "market_analyst",
  "social_analyst",
  "news_analyst",
  "fundamentals_analyst",
  "research_manager",
  "trader",
  "portfolio_manager",
];

interface Run {
  id: string;
  ticker: string;
  trade_date: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  final_decision: { decision?: string } | null;
  error: string | null;
  events: AgentEvent[] | null;
}

interface AgentState {
  status: AgentStatus;
  activity?: string;
  report?: string;
}

function buildInitialStates(events: AgentEvent[] | null) {
  const states = new Map<string, AgentState>();
  for (const a of AGENTS) states.set(a, { status: "pending" });
  if (events) {
    for (const ev of events) applyEvent(states, ev);
  }
  return states;
}

function applyEvent(states: Map<string, AgentState>, ev: AgentEvent) {
  if ("agent" in ev) {
    const cur = states.get(ev.agent) ?? { status: "pending" };
    if (ev.type === "agent_started")
      states.set(ev.agent, { ...cur, status: "running" });
    if (ev.type === "agent_thinking")
      states.set(ev.agent, { ...cur, activity: "Thinking…" });
    if (ev.type === "agent_completed")
      states.set(ev.agent, {
        ...cur,
        status: "completed",
        activity: undefined,
        report: ev.summary,
      });
    if (ev.type === "agent_error")
      states.set(ev.agent, {
        ...cur,
        status: "failed",
        activity: ev.error,
      });
  }
}

export function RunView({ run }: { run: Run }) {
  const router = useRouter();
  const [states, setStates] = useState(() =>
    buildInitialStates(run.events as AgentEvent[] | null)
  );
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [terminal, setTerminal] = useState(
    run.status === "completed" || run.status === "failed"
  );

  const onEvent = useCallback((ev: AgentEvent) => {
    setStates((prev) => {
      const next = new Map(prev);
      applyEvent(next, ev);
      return next;
    });
    if ("agent" in ev) setActiveAgent(ev.agent);
  }, []);

  const onTerminal = useCallback(() => {
    setTerminal(true);
    router.refresh();
  }, [router]);

  // Trigger /start once for pending runs
  useEffect(() => {
    if (run.status !== "pending") return;
    let cancelled = false;
    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session || cancelled) return;
      await fetch(`${env.RENDER_API_BASE_URL}/runs/${run.id}/start`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [run.id, run.status]);

  const decision =
    typeof run.final_decision === "object" && run.final_decision
      ? run.final_decision.decision
      : undefined;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">
            {run.ticker} <span className="text-muted-foreground">·</span>{" "}
            <span className="font-mono text-base text-muted-foreground">
              {run.trade_date}
            </span>
          </h1>
          <p className="text-sm text-muted-foreground">
            Run {run.id.slice(0, 8)} · started{" "}
            {new Date(run.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {decision && <Badge>{decision}</Badge>}
          <Badge
            variant={
              run.status === "failed"
                ? "destructive"
                : run.status === "completed"
                  ? "default"
                  : "secondary"
            }
          >
            {run.status}
          </Badge>
        </div>
      </div>

      {run.error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {run.error}
        </div>
      )}

      <div className="space-y-3">
        {AGENTS.map((agent) => {
          const s = states.get(agent) ?? { status: "pending" as AgentStatus };
          return (
            <AgentTimelineCard
              key={agent}
              agent={agent}
              status={s.status}
              activity={s.activity}
              report={s.report}
              isActive={activeAgent === agent}
            />
          );
        })}
      </div>

      {!terminal && run.status !== "pending" && (
        <EventStreamConsumer
          runId={run.id}
          onEvent={onEvent}
          onTerminal={onTerminal}
        />
      )}

      {!terminal && run.status === "pending" && (
        <p className="text-sm text-muted-foreground">Starting run…</p>
      )}

      {terminal && (
        <div className="flex justify-end">
          <Button variant="outline" onClick={() => router.push("/")}>
            Back to runs
          </Button>
        </div>
      )}
    </div>
  );
}
