// apps/web/components/agent-timeline-card.tsx
"use client";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useState } from "react";

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

export interface AgentTimelineCardProps {
  agent: string;
  status: AgentStatus;
  activity?: string;
  report?: string;
  isActive?: boolean;
}

export function AgentTimelineCard({
  agent,
  status,
  activity,
  report,
  isActive,
}: AgentTimelineCardProps) {
  const [open, setOpen] = useState(false);
  const pretty = PRETTY_AGENT[agent] ?? agent;
  const ringClass =
    isActive && status === "running"
      ? "ring-2 ring-primary/30 animate-pulse"
      : "";

  return (
    <Card className={ringClass}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <h3 className="text-sm font-semibold">{pretty}</h3>
        <Badge variant={STATUS_VARIANT[status]}>{status}</Badge>
      </CardHeader>
      <CardContent className="space-y-2">
        {activity && (
          <p className="text-sm text-muted-foreground">{activity}</p>
        )}
        {report && (
          <Collapsible open={open} onOpenChange={setOpen}>
            <CollapsibleTrigger className="text-xs text-muted-foreground underline">
              {open ? "Hide" : "Show"} report
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-2">
              <pre className="whitespace-pre-wrap text-xs text-muted-foreground">
                {report}
              </pre>
            </CollapsibleContent>
          </Collapsible>
        )}
      </CardContent>
    </Card>
  );
}
