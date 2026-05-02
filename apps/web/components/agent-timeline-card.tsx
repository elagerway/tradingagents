// apps/web/components/agent-timeline-card.tsx
"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { AgentEvent } from "@/components/event-stream-consumer";

export type AgentStatus = "pending" | "running" | "completed" | "failed";

const STATUS_VARIANT: Record<
  AgentStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  pending: "outline",
  running: "secondary",
  completed: "default",
  failed: "destructive",
};

const PRETTY_AGENT: Record<string, string> = {
  market_analyst: "Market Analyst",
  social_analyst: "Social Analyst",
  news_analyst: "News Analyst",
  fundamentals_analyst: "Fundamentals Analyst",
  research_manager: "Research Manager",
  trader: "Trader",
  portfolio_manager: "Portfolio Manager",
};

const MAX_DETAIL_CHARS = 400;

function truncate(s: string, n: number = MAX_DETAIL_CHARS): string {
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

function formatEvent(
  ev: AgentEvent,
): { label: string; detail?: string } | null {
  switch (ev.type) {
    case "agent_started":
      return { label: "Started" };
    case "agent_thinking":
      return { label: "Thinking…" };
    case "tool_called":
      return {
        label: `Called tool: ${ev.tool}`,
        detail: ev.args,
      };
    case "tool_result":
      return { label: "Tool result", detail: ev.result };
    case "agent_completed":
      return { label: "Completed" };
    case "agent_error":
      return { label: "Error", detail: ev.error };
    default:
      return null;
  }
}

export interface AgentTimelineCardProps {
  agent: string;
  status: AgentStatus;
  events: AgentEvent[];
  report?: string;
  isActive?: boolean;
}

export function AgentTimelineCard({
  agent,
  status,
  events,
  report,
  isActive,
}: AgentTimelineCardProps) {
  const [open, setOpen] = useState(false);
  const pretty = PRETTY_AGENT[agent] ?? agent;
  const ringClass =
    isActive && status === "running"
      ? "ring-2 ring-primary/30 animate-pulse"
      : "";
  const formatted = events.map(formatEvent).filter((e) => e !== null);

  return (
    <Card className={ringClass}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full cursor-pointer text-left"
        aria-expanded={open}
      >
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {open ? "▾" : "▸"}
            </span>
            <h3 className="text-sm font-semibold">{pretty}</h3>
          </div>
          <Badge variant={STATUS_VARIANT[status]}>{status}</Badge>
        </CardHeader>
      </button>
      {open && (
        <CardContent className="space-y-3 border-t pt-3">
          {formatted.length === 0 && status === "pending" && (
            <p className="text-sm text-muted-foreground">Waiting to start.</p>
          )}
          {formatted.length > 0 && (
            <ul className="space-y-2 text-sm">
              {formatted.map((f, i) => (
                <li key={i}>
                  <div className="font-mono text-xs text-muted-foreground">
                    {f.label}
                  </div>
                  {f.detail && (
                    <pre className="mt-0.5 whitespace-pre-wrap text-xs text-muted-foreground/80">
                      {truncate(f.detail)}
                    </pre>
                  )}
                </li>
              ))}
            </ul>
          )}
          {report && (
            <div className="border-t pt-3">
              <h4 className="mb-1 text-xs font-medium text-muted-foreground">
                Report
              </h4>
              <pre className="whitespace-pre-wrap text-xs text-muted-foreground">
                {report}
              </pre>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
